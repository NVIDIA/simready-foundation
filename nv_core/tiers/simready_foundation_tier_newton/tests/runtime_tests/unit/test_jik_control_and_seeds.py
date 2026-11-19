# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    _independent_dofs as control,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import jacobian_ik as phase
from simready.foundation.tier_newton.runtime_tests.articulation_phases.ik_targets import IKTarget
from simready.foundation.tier_newton.runtime_tests.articulation_phases.jik_solver import (
    JacobianIKSolver,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import RobotHandle


class Robot:
    dof_names = ["arm", "follower", "passive", "loop"]
    dof_count = 4

    def __init__(self, forbid_full=True):
        self.positions = np.array([0.0, 0.7, -0.2, 0.3])
        self.targets = np.array([0.0, 0.9, -0.5, 0.2])
        self.velocities = np.array([0.0, 0.4, 0.5, 0.6])
        self.writes = []
        self.forbid_full = forbid_full

    def get_joint_positions(self):
        return self.positions.copy()

    def get_joint_position_limits(self):
        return -np.ones(4), np.ones(4)

    def _write(self, key, values, indices):
        self.writes.append((key, np.asarray(indices).copy(), np.asarray(values).copy()))
        getattr(self, key)[indices] = values

    def set_joint_positions_indexed(self, values, indices):
        self._write("positions", values, indices)

    def set_joint_position_targets_indexed(self, values, indices):
        self._write("targets", values, indices)

    def set_joint_velocities_indexed(self, values, indices):
        self._write("velocities", values, indices)

    def _full(self, key, values):
        if self.forbid_full:
            raise AssertionError("constraint-owned DOFs must never receive a full-vector write")
        self._write(key, values, np.arange(4))

    def set_joint_positions(self, values):
        self._full("positions", values)

    def set_joint_position_targets(self, values):
        self._full("targets", values)

    def set_joint_velocities(self, values):
        self._full("velocities", values)

    def get_link_world_transforms(self, paths):
        return {paths[0]: (np.array([self.positions[0], 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))}


class Context:
    def __init__(self, robot):
        self.robot, self.ticks = robot, 0
        self.metrics, self.messages = {}, []
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)

    async def step_one(self):
        self.ticks += 1
        self.robot.positions[0] = self.robot.targets[0]
        self.robot.positions[1] = 0.7 + 2.0 * self.robot.positions[0]
        self.robot.positions[2] += 0.001
        self.robot.positions[3] = 0.3 - self.robot.positions[0]

    async def capture_frame(self, **kwargs):
        return None

    def step(self, message):
        self.messages.append(message)

    log = warn = step

    def add_metric(self, key, value):
        self.metrics[key] = value


def target(index=0):
    return IKTarget(np.array([0.4, 0.0, 0.0]), True, index, np.array([1.0, 0.0, 0.0, 0.0]))


def result(joints, success=False, error=0.1):
    return SimpleNamespace(
        success=success,
        iterations=1,
        converged_joints=np.array(joints, dtype=float),
        final_position=np.array([0.4 - error, 0.0, 0.0]),
        final_orientation=np.array([1.0, 0.0, 0.0, 0.0]),
        final_pos_error=error,
        final_orient_error_deg=0.0,
    )


@pytest.mark.parametrize("key", ["mimic_follower_indices", "passive_joint_indices", "loop_joint_indices"])
def test_exclusion_metadata_selects_controller_owned_dofs(key):
    assert control.excluded_dof_indices({key: [1, 2, 3]}, 4) == {1, 2, 3}


@pytest.mark.parametrize("indices", [[True], [-1], [4], [1.0], ["1"]])
def test_malformed_exclusions_fail_before_command(indices):
    robot = Robot()
    with pytest.raises(RuntimeError, match="index is invalid"):
        control.command_targets(robot, np.zeros(4), indices)
    assert not robot.writes


@pytest.mark.asyncio
async def test_fk_probes_and_jacobian_never_write_coupled_coordinates():
    robot, excluded = Robot(), {1, 2, 3}
    ctx = Context(robot)
    home = robot.positions.copy()
    source_targets, source_velocities = robot.targets.copy(), robot.velocities.copy()
    configs = phase._sample_joint_configs(home, -np.ones(4), np.ones(4), excluded, 3, angular_indices={0})
    assert all(np.array_equal(config[1:], home[1:]) for config in configs)
    solver = JacobianIKSolver(robot, "/Robot/tool", locked_indices=excluded)
    targets, _ = await phase._generate_fk_targets(
        ctx, robot, solver, home, np.zeros(3), -np.ones(4), np.ones(4), excluded, 3, 0, angular_indices={0}
    )
    assert len(targets) == 3
    jacobian = await solver.compute_jacobian(home, ctx.step_one)
    assert jacobian[0, 0] == pytest.approx(1.0)
    assert np.array_equal(jacobian[:, 1:], np.zeros((6, 3)))
    assert all(indices.tolist() == [0] for _, indices, _ in robot.writes)
    assert np.array_equal(robot.targets[1:], source_targets[1:])
    assert np.array_equal(robot.velocities[1:], source_velocities[1:])
    assert robot.positions[0] == home[0]


@pytest.mark.asyncio
async def test_interpolation_and_first_hold_command_leave_followers_uncommanded():
    robot, excluded = Robot(), {1, 2, 3}
    ctx = Context(robot)
    original_targets = robot.targets.copy()
    await phase._interpolate_to_solution(
        ctx,
        robot,
        {},
        robot.positions.copy(),
        np.array([0.4, 99.0, 88.0, 77.0]),
        1.0,
        4.0,
        10,
        [],
        "test",
        "smoothstep",
        None,
        10.0,
        "target_0",
        locked_indices=excluded,
    )
    await phase._hold_after_reach(
        ctx, robot, np.array([0.4, 99.0, 88.0, 77.0]), 0.5, 4.0, 10, [], "test", locked_indices=excluded
    )
    assert all(indices.tolist() == [0] for _, indices, _ in robot.writes)
    assert np.array_equal(robot.targets[1:], original_targets[1:])
    assert robot.positions[0] == pytest.approx(0.4)


def test_motion_evidence_has_no_fabricated_follower_target_or_error():
    rows = [[], []]

    def observer(index):
        return SimpleNamespace(
            history=object(),
            _warn=lambda: pytest.fail("valid uncommanded motion is not missing evidence"),
            sample=lambda values, **kwargs: rows[index].append(values),
        )

    robot = Robot()
    control.sample_joint_motion(robot, {0: observer(0), 1: observer(1)}, np.ones(4), 0.1, "hold", {1})
    assert set(rows[0][0]) == {"position", "target", "error"}
    assert rows[1][0] == {"position": 0.7}


def test_real_newton_adapter_rejects_unqualified_indexed_control_before_dispatch():
    for articulation in (
        SimpleNamespace(dof_names=["arm", "follower"]),
        SimpleNamespace(dof_names=["arm", "follower"], get_joint_position_targets=lambda: np.array([0.0, 0.9])),
        SimpleNamespace(dof_names=["arm", "follower"], get_joint_position_targets=lambda: None),
        SimpleNamespace(
            dof_names=["arm", "follower"],
            get_applied_action=lambda: SimpleNamespace(joint_positions=np.array([0.0, 0.9]), joint_indices=None),
        ),
        SimpleNamespace(dof_names=["arm", "follower"], get_applied_action=lambda: None),
    ):
        robot = RobotHandle.__new__(RobotHandle)
        dispatched = []
        articulation.apply_action = lambda action, out=dispatched: out.append(action)
        robot._articulation = articulation
        robot._is_newton, robot._newton_actuators = True, None
        with pytest.raises(RuntimeError, match="not qualified"):
            robot.set_joint_position_targets_indexed([0.1], [0])
        assert dispatched == []


def test_real_newton_adapter_qualifies_indexed_control_only_when_excluded_dofs_are_unactuated():
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(root)
    arm_joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/arm").GetPrim()
    arm_drive = UsdPhysics.DriveAPI.Apply(arm_joint, "angular")
    arm_drive.GetStiffnessAttr().Set(100.0)
    follower_joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/follower").GetPrim()

    robot = RobotHandle.__new__(RobotHandle)
    robot._stage = stage
    robot._robot_prim_path = "/Robot"
    robot._asset_prim = root
    robot._is_newton = True
    robot._newton_actuators = None
    robot._articulation = SimpleNamespace(
        dof_names=["arm", "follower"],
        get_joint_position_targets=lambda: np.array([0.0, 0.5]),
    )

    # Follower has no active drive -> qualified for indexed control
    robot.require_indexed_joint_control(indices=[0])
    robot.require_indexed_joint_control(excluded={1})

    # If follower has residual non-zero drive stiffness -> rejected
    follower_drive = UsdPhysics.DriveAPI.Apply(follower_joint, "angular")
    follower_drive.GetStiffnessAttr().Set(10.0)
    with pytest.raises(RuntimeError, match="not qualified"):
        robot.require_indexed_joint_control(indices=[0])


def test_physx_adapter_preserves_sparse_indices_and_other_commands():
    robot = RobotHandle.__new__(RobotHandle)
    robot._is_newton, robot._newton_actuators = False, None
    calls = []
    robot._articulation = SimpleNamespace(
        dof_names=["arm", "follower"],
        _backend_utils=None,
        set_joint_positions=lambda values, joint_indices: calls.append(("pose", values, joint_indices)),
        set_joint_velocities=lambda values, joint_indices: calls.append(("velocity", values, joint_indices)),
    )
    robot._apply_action = lambda **kwargs: calls.append(("target", kwargs["joint_positions"], kwargs["joint_indices"]))
    robot.set_joint_positions_indexed([0.1], [0])
    robot.set_joint_position_targets_indexed([0.2], [0])
    robot.set_joint_velocities_indexed([0.0], [0])
    assert [kind for kind, _, _ in calls] == ["pose", "target", "velocity"]
    assert all(indices.tolist() == [0] for _, _, indices in calls)


@pytest.mark.asyncio
async def test_home_seed_can_escape_previous_solution_without_changing_target_or_tolerances(monkeypatch):
    robot = Robot(forbid_full=False)
    robot.positions[:] = 0.8
    ctx, seen = Context(robot), []
    home, previous = np.zeros(4), np.full(4, 0.8)

    async def solve(ctx, solver, target, home_orientation, pos_tol, orient_tol_rad, max_iterations):
        seen.append((robot.positions.copy(), target.position.copy(), pos_tol, orient_tol_rad, max_iterations))
        success = np.array_equal(robot.positions, home)
        return result(np.full(4, 0.6), success=success, error=0.0 if success else 0.1)

    # Keep this seed-sensitive synthetic solver independent of simulation dynamics.
    async def step():
        pass

    ctx.step_one = step
    monkeypatch.setattr(phase, "_solve_target", solve)
    chosen, attempts, iterations = await phase._solve_seeded_target(
        ctx, robot, SimpleNamespace(_locked=set()), target(), home, previous, None, 0.02, 0.1, 7
    )
    assert chosen.success
    assert [attempt["seed"] for attempt in attempts] == ["previous_success", "best_failed", "home"]
    assert len(seen) <= 4 and iterations == 3
    assert all(np.array_equal(row[1], target().position) and row[2:] == (0.02, 0.1, 7) for row in seen)
    assert len({tuple(row[0]) for row in seen}) == len(seen)


@pytest.mark.asyncio
async def test_seed_restarts_stop_at_four_distinct_attempts(monkeypatch):
    robot, home = Robot(forbid_full=False), np.zeros(4)
    robot.positions[:] = 0.2
    ctx = Context(robot)

    async def step():
        pass

    ctx.step_one = step

    async def solve(*args):
        return result(np.full(4, 0.3))

    monkeypatch.setattr(phase, "_solve_target", solve)
    chosen, attempts, _ = await phase._solve_seeded_target(
        ctx, robot, SimpleNamespace(_locked=set()), target(), home, np.full(4, 0.1), None, 0.02, 0.1, 7
    )
    assert not chosen.success
    assert [attempt["seed"] for attempt in attempts] == ["previous_success", "current", "best_failed", "home"]


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [OSError("native failed"), asyncio.CancelledError()])
async def test_seed_exception_or_cancel_stops_immediately_and_restores_only_independent_state(monkeypatch, exception):
    robot, home = Robot(), np.array([0.0, 0.7, -0.2, 0.3])
    ctx = Context(robot)
    solver = SimpleNamespace(_locked={1, 2, 3})
    calls = []

    async def solve(*args):
        calls.append(1)
        raise exception

    monkeypatch.setattr(phase, "_solve_target", solve)
    with pytest.raises(type(exception)) as caught:
        await phase._precompute_solutions(ctx, robot, solver, [target()], home, None, 0.02, 0.1, 7)
    assert caught.value is exception
    assert len(calls) == 1
    assert robot.positions[0] == home[0]
    assert all(indices.tolist() == [0] for _, indices, _ in robot.writes)


@pytest.mark.parametrize("index", [True, 0.5, -1, 4])
def test_solver_rejects_invalid_locked_indices_before_probe(index):
    robot = Robot()
    with pytest.raises(RuntimeError, match="index is invalid"):
        JacobianIKSolver(robot, "/Robot/tool", locked_indices=[index])
    assert robot.writes == []


def test_optional_seed_telemetry_failure_does_not_change_result():
    warnings = []

    def failed_metric(*args):
        raise OSError("diagnostic sink unavailable")

    phase._record_seed_attempts(SimpleNamespace(add_metric=failed_metric, warn=warnings.append), [], 0)
    assert len(warnings) == 1 and "result unchanged" in warnings[0]


def test_lula_facade_retains_native_identity_and_uses_only_declared_subset():
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
        ik_target_reach as lula,
    )

    robot = Robot()
    native = object()
    robot.articulation = native
    art = SimpleNamespace(get_joints_subset=lambda: SimpleNamespace(get_joint_subset_indices=lambda: [0]))
    controlled = lula._lula_controlled_robot(robot, art, {"mimic_follower_indices": [1]})
    assert controlled.articulation is native
    assert controlled.get_joint_positions().tolist() == robot.positions.tolist()
    controlled.set_joint_positions(np.array([0.1, 99.0, 88.0, 77.0]))
    controlled.set_joint_position_targets(np.array([0.2, 99.0, 88.0, 77.0]))
    controlled.set_joint_velocities(np.zeros(4))
    assert all(indices.tolist() == [0] for _, indices, _ in robot.writes)
    assert robot.targets.tolist() == [0.2, 0.9, -0.5, 0.2]


@pytest.mark.parametrize("indices", [[0, 0], [True], [4], [], None])
def test_lula_descriptor_cannot_authorize_malformed_or_empty_control(indices):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
        ik_target_reach as lula,
    )

    robot = Robot()
    art = SimpleNamespace(get_joints_subset=lambda: SimpleNamespace(get_joint_subset_indices=lambda: indices))
    with pytest.raises(RuntimeError):
        lula._lula_controlled_robot(robot, art, {})
    assert robot.writes == []


@pytest.mark.asyncio
async def test_lula_capture_evidence_keeps_uncommanded_followers_position_only(monkeypatch):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
        ik_target_reach as lula,
    )

    robot = Robot()
    ctx = Context(robot)
    controlled = control.IndependentRobot(robot, {1, 2, 3})
    samples = []
    observer = SimpleNamespace(
        history=object(),
        _warn=lambda: pytest.fail("uncommanded position is valid"),
        sample=lambda values, **kwargs: samples.append(values),
        record_capture=lambda path: None,
    )
    monkeypatch.setattr(lula, "_compute_target_error", lambda *args: 1.0)
    await lula._interpolate_ik_motion(
        ctx,
        controlled,
        object(),
        target(),
        np.array([0.4, 99.0, 88.0, 77.0]),
        10,
        [],
        3,
        0.02,
        None,
        None,
        10,
        "target_0",
        {1: observer},
        {"steps": 0},
        4,
    )
    assert samples and all(set(row) == {"position"} for row in samples)
    assert all(indices.tolist() == [0] for _, indices, _ in robot.writes)


def test_finger_branch_name_matches_concatenated_fingers_and_jaw_tips():
    try:
        from simready.foundation.tier_newton.runtime_tests.articulation_phases.ee_discovery import (
            _finger_branch_name,
        )
    except ModuleNotFoundError:
        from simready_benchmark_newton_suite.articulation_phases.ee_discovery import (
            _finger_branch_name,
        )

    for path in (
        "/panda/panda_leftfinger",
        "/panda/panda_rightfinger",
        "/panda/panda_fingertip_centered",
        "/fr3/fr3_leftfinger",
        "/fr3/fr3_rightfinger",
        "/urdf_top_assembly/Geometry/root/base/link1/link2/link3/link4/link5/gripper/tip_left",
        "/urdf_top_assembly/Geometry/root/base/link1/link2/link3/link4/link5/gripper/tip_right",
    ):
        assert _finger_branch_name(path) is True, path

    for path in (
        "/panda/panda_hand",
        "/fr3/fr3_hand",
        "/urdf_top_assembly/Geometry/root/base/link1/link2/link3/link4/link5/gripper",
        "/ur10/wrist_3_link",
    ):
        assert _finger_branch_name(path) is False, path

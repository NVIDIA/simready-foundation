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
"""Required control/verdict views fail honestly without changing valid trajectories."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from simready.evaluate.runner.test_context import RunContext
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    drive_gain_validation,
    full_range_sweep,
    ik_target_reach,
    jacobian_ik,
    jik_solver,
    mimic_joint,
    multi_joint_coordination,
    required_readback,
    robot_state,
    state_accuracy,
    velocity_limit,
)
from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver

INVALID = [None, [float("nan"), 0], [float("inf"), 0], [[0, 0]], [], [0]]
PHASES = {
    "velocity_limit": velocity_limit,
    "full_range_sweep": full_range_sweep,
    "drive_gain_validation": drive_gain_validation,
    "state_accuracy": state_accuracy,
    "multi_joint_coordination": multi_joint_coordination,
    "mimic_joint": mimic_joint,
}


@pytest.mark.parametrize(
    "values",
    [
        np.array([True, False]),
        np.array(["0.1", "0.2"]),
        np.array([0.1, 0.2], dtype=object),
        np.array([complex(0.1, 0.0), complex(0.2, 0.3)]),
        np.array([complex(0.1, float("inf")), complex(0.2, 0.0)]),
    ],
)
def test_required_vectors_reject_coercible_but_non_real_numeric_dtypes(values):
    with pytest.raises(required_readback.RequiredReadbackError):
        required_readback.require_vector(values, "probe", "joint configuration", 2)


@pytest.mark.parametrize("dtype", [np.int32, np.uint32, np.float32, np.float64])
def test_required_vectors_preserve_finite_real_numeric_dtype(dtype):
    values = np.array([1, 2], dtype=dtype)
    result = required_readback.require_vector(values, "probe", "joint configuration", 2)
    assert result.dtype == values.dtype
    assert np.array_equal(result, values)


class _Robot:
    dof_count = 2
    dof_names = ["master", "follower"]
    prim_path = "/Robot"

    def __init__(self, invalid=None):
        self.invalid = invalid
        self.after_step = False
        self.commands = []
        self.reads = 0

    def get_joint_positions(self):
        self.reads += 1
        return self.invalid if self.after_step else np.zeros(2, dtype=np.float32)

    def get_joint_velocities(self):
        return self.invalid if self.after_step else np.ones(2, dtype=np.float32)

    def get_joint_position_limits(self):
        return np.array([-1.0, -1.0]), np.array([1.0, 1.0])

    def get_joint_velocity_limits(self):
        return np.ones(2)

    def set_joint_position_targets(self, targets):
        self.commands.append(np.asarray(targets).copy())

    def set_joint_position_target(self, index, target):
        command = np.zeros(2)
        command[index] = target
        self.set_joint_position_targets(command)

    def set_joint_position_targets_indexed(self, values, indices):
        assert list(indices) == [0]
        self.commands.append(np.asarray(values).copy())

    def set_joint_positions_indexed(self, values, indices):
        raise AssertionError("MIM does not teleport")

    def set_joint_velocities_indexed(self, values, indices):
        raise AssertionError("MIM does not write velocities")

    def apply_velocity_limits_to_tensor_view(self, values):
        pass


class _Context:
    begin_motion_history = None

    def __init__(self, robot):
        self.robot = robot
        self.steps = 0
        self.metrics = {}
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)

    async def step_one(self):
        self.steps += 1
        self.robot.after_step = True

    async def physics_steps(self, count):
        assert count == 0

    async def capture_frame(self, **kwargs):
        return None

    def step(self, *args):
        pass

    log = step
    warn = step

    def add_metric(self, name, value):
        self.metrics[name] = value

    def fail(self, message):
        raise AssertionError("invalid view must not become an asset failure: " + message)

    def skip(self, message):
        raise AssertionError("required view must not become not-applicable: " + message)


@pytest.mark.parametrize("invalid", INVALID)
@pytest.mark.parametrize("method", ["required_positions", "required_velocities"])
def test_required_view_rejects_missing_nonfinite_and_wrong_shape_once(invalid, method):
    robot = _Robot(invalid)
    robot.after_step = True
    with pytest.raises(required_readback.RequiredReadbackError, match="criterion was not evaluated"):
        getattr(required_readback, method)(robot, "probe")
    assert robot.commands == []


@pytest.mark.parametrize(
    "root_pose",
    [
        None,
        (None, [1, 0, 0, 0]),
        ([float("nan"), 0, 0], [1, 0, 0, 0]),
        ([0, 0], [1, 0, 0, 0]),
        ([0, 0, 0], [0, 0, 0, 0]),
        ([0, 0, 0], [float("inf"), 0, 0, 0]),
    ],
)
@pytest.mark.asyncio
async def test_invalid_required_root_pose_cannot_become_identity_reset(root_pose):
    root_commands = []
    robot = _Robot()
    robot.articulation = SimpleNamespace(
        get_world_pose=lambda: root_pose,
        set_world_pose=lambda **pose: root_commands.append(pose),
    )
    with pytest.raises(required_readback.RequiredReadbackError):
        robot_state.capture_default_state(robot)
    assert root_commands == []


@pytest.mark.asyncio
async def test_invalid_saved_root_pose_and_failed_restore_remain_setup_errors():
    commands = []
    robot = _Robot()
    robot.articulation = SimpleNamespace(get_world_pose=lambda: ([2, 3, 4], [1, 0, 0, 0]))
    state = robot_state.capture_default_state(robot)
    state.root_position = [float("nan"), 0, 0]
    robot.set_joint_positions = lambda values: commands.append(values)
    robot.set_joint_velocities = lambda values: commands.append(values)
    with pytest.raises(required_readback.RequiredReadbackError):
        await robot_state.reset_to_default(_Context(robot), robot, state)
    assert commands == []
    state.root_position = [2, 3, 4]
    cause = RuntimeError("native root restore rejected")

    def restore(**pose):
        raise cause

    robot.articulation.set_world_pose = restore
    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        await robot_state.reset_to_default(_Context(robot), robot, state)
    assert caught.value.__cause__ is cause
    assert len(commands) == 2


def test_no_articulation_placeholder_root_is_explicitly_unobserved():
    state = robot_state.capture_default_state(_Robot())
    assert not state.root_pose_observed
    assert state.root_position == (0, 0, 0)
    assert state.root_orientation == (1, 0, 0, 0)


@pytest.mark.asyncio
async def test_unobserved_placeholder_is_never_restored_to_actual_articulation():
    robot = _Robot()
    state = robot_state.capture_default_state(robot)
    commands = []
    robot.articulation = SimpleNamespace(set_world_pose=lambda **pose: commands.append(pose))
    robot.set_joint_positions = lambda values: commands.append(values)
    robot.set_joint_velocities = lambda values: commands.append(values)
    with pytest.raises(required_readback.RequiredReadbackError, match="not observed"):
        await robot_state.reset_to_default(_Context(robot), robot, state)
    assert commands == []


def test_default_state_capture_uses_host_adapter_for_cuda_like_root_values():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )

    reads = []

    class CudaLike:
        def __init__(self, values):
            self.values = np.asarray(values, dtype=np.float32)

        def __array__(self, *args, **kwargs):
            raise TypeError("cannot convert CUDA tensor directly to NumPy")

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    def native_pose():
        reads.append(None)
        return CudaLike([2, 3, 4]), CudaLike([1, 0, 0, 0])

    robot = _Robot()
    robot._articulation = SimpleNamespace(get_world_pose=native_pose)
    robot.articulation = robot._articulation
    robot.get_world_pose = lambda: RobotHandle.get_world_pose(robot)
    state = robot_state.capture_default_state(robot)
    assert reads == [None]
    assert state.root_pose_observed
    assert state.root_position == (2, 3, 4)
    assert state.root_orientation == (1, 0, 0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", INVALID)
async def test_invalid_saved_joint_targets_are_rejected_before_any_reset_command(invalid):
    commands = []
    robot = _Robot()
    state = robot_state.capture_default_state(robot)
    state.joint_positions = invalid
    robot.set_joint_positions = lambda values: commands.append(values)
    robot.set_joint_velocities = lambda values: commands.append(values)
    with pytest.raises(required_readback.RequiredReadbackError):
        await robot_state.reset_to_default(_Context(robot), robot, state)
    assert commands == []


def test_valid_observed_root_pose_preserves_values():
    robot = _Robot()
    robot.articulation = SimpleNamespace(get_world_pose=lambda: ([2, 3, 4], [1, 0, 0, 0]))
    state = robot_state.capture_default_state(robot)
    assert state.root_pose_observed
    assert state.root_position == (2, 3, 4)
    assert state.root_orientation == (1, 0, 0, 0)


def test_required_view_preserves_native_dtype_and_original_cause():
    robot = _Robot()
    array = required_readback.required_positions(robot, "probe")
    assert array.dtype == np.float32 and robot.reads == 1
    cause = RuntimeError("native view acquisition failed")

    def unavailable():
        raise cause

    robot.get_joint_positions = unavailable
    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        required_readback.required_positions(robot, "probe")
    assert caught.value.__cause__ is cause
    with pytest.raises(required_readback.RequiredReadbackError):
        required_readback.required_positions(SimpleNamespace(), "probe")


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", INVALID)
@pytest.mark.parametrize(
    "name",
    [
        "velocity_limit",
        "full_range_sweep",
        "drive_gain_validation",
        "state_accuracy",
        "multi_joint_coordination",
        "mimic_joint",
    ],
)
async def test_production_phase_invalid_existing_read_is_error_not_asset_verdict(monkeypatch, name, invalid):
    module = PHASES[name]
    monkeypatch.setattr(module, "compute_world_aligned_bbox", lambda prim: SimpleNamespace(volume=1.0))
    monkeypatch.setattr(module, "check_bbox_explode", lambda *args: None)
    monkeypatch.setattr(velocity_limit, "resolve_usd_max_velocities", lambda **kwargs: np.ones(2))
    pair = SimpleNamespace(reference_dof_index=0, follower_dof_index=1, gear=-1.0, offset=0.0, backend="physx")
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **kwargs: [pair])
    robot = _Robot(invalid)
    ctx = _Context(robot)
    config = {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "step_fatal": False}
    with pytest.raises(required_readback.RequiredReadbackError):
        await getattr(module, "run_" + name)(ctx, robot, {"passive_joint_indices": []}, config)
    assert ctx.steps == 1
    assert len(robot.commands) == 1
    assert not any(key.endswith("_joints_passed") or key.endswith("_pairs_passed") for key in ctx.metrics)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", INVALID)
async def test_ik_required_start_state_does_not_become_nonconvergence(monkeypatch, invalid):
    robot = _Robot(invalid)
    robot.after_step = True
    ctx = _Context(robot)
    with pytest.raises(required_readback.RequiredReadbackError):
        await ik_target_reach._interpolate_ik_motion(
            ctx, robot, object(), object(), np.ones(2), 1, [], 2, 0.01, None, None, 10, "target_0"
        )
    with pytest.raises(required_readback.RequiredReadbackError):
        await jacobian_ik._settle_and_snapshot(ctx, robot, 0, 4)
    assert ctx.steps == 0 and robot.commands == []


@pytest.mark.parametrize(
    "pose",
    [
        None,
        ([float("nan"), 0, 0], [0, 0, 0, 1]),
        ([float("inf"), 0, 0], [0, 0, 0, 1]),
        ([0, 0], [0, 0, 0, 1]),
        ([0, 0, 0], [0, 0, 0, 0]),
        ([0, 0, 0], [0, 0, float("nan"), 1]),
    ],
)
def test_jik_live_pose_is_required_finite_and_correctly_shaped(pose):
    solver = jik_solver.JacobianIKSolver.__new__(jik_solver.JacobianIKSolver)
    solver.robot = SimpleNamespace(get_link_world_transforms=lambda paths: {paths[0]: pose})
    solver.ee_link_path = "/Robot/tool"
    with pytest.raises(required_readback.RequiredReadbackError):
        solver.get_ee_pose()


@pytest.mark.asyncio
async def test_jik_typed_view_error_survives_solver_and_final_evaluation_catches():
    error = required_readback.RequiredReadbackError("required live pose unavailable")

    class _Solver:
        async def solve(self, **kwargs):
            raise error

        def get_ee_pose(self):
            raise error

    robot = _Robot()
    ctx = _Context(robot)
    target = SimpleNamespace(index=0, position=np.zeros(3), is_reachable=False)
    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        await jacobian_ik._solve_target(ctx, _Solver(), target, None, 0.01, 0.1, 1)
    assert caught.value is error
    with pytest.raises(required_readback.RequiredReadbackError):
        jacobian_ik._evaluate_target(_Solver(), target, 0.01, 5)


@pytest.mark.parametrize("invalid", INVALID[:-1])
def test_lula_missing_warm_start_or_pose_cannot_be_correctly_rejected_target(invalid):
    subset = SimpleNamespace(get_joint_positions=lambda: invalid)
    art_ik = SimpleNamespace(get_joints_subset=lambda: subset)
    with pytest.raises(required_readback.RequiredReadbackError):
        ik_target_reach._compute_inverse_kinematics_host(art_ik, np.zeros(3), 0.01, 0.1)
    with pytest.raises(required_readback.RequiredReadbackError):
        ik_target_reach._compute_target_error(art_ik, SimpleNamespace(position=np.zeros(3)))


@pytest.mark.asyncio
async def test_required_view_error_retains_prior_motion_as_partial_for_execution_cleanup(tmp_path):
    robot = _Robot()
    ctx = RunContext(
        asset_path="/Robot.usd",
        asset_rel_path="Robot.usd",
        output_dir=str(tmp_path),
        test_name="state_accuracy",
        test_version="1.2.2",
        feature_id="feature",
        engine_name="kit",
        engine_version="test",
        session_id="session",
        scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None),
    )
    steps = []

    async def step_one():
        steps.append(None)
        if len(steps) == 2:
            robot.invalid = None
            robot.after_step = True

    async def capture_frame(**kwargs):
        return None

    ctx.step_one = step_one
    ctx.capture_frame = capture_frame
    motion = MotionObserver(
        ctx,
        "trial",
        {
            name: {"unit": "rad/s" if name == "velocity" else "rad", "source": "existing phase observation"}
            for name in ("position", "velocity", "target", "final_goal", "error", "goal_error")
        },
        sample_stride=1,
    )
    with pytest.raises(required_readback.RequiredReadbackError):
        await state_accuracy._run_settle_to_target(
            ctx,
            robot,
            {"index": 0, "name": "master"},
            0.5,
            3,
            1,
            [],
            1,
            "trial",
            motion=motion,
            motion_clock={"steps": 0, "physics_fps": 4, "issued_target": 0.5},
        )
    # The same execution cleanup persists unfinished evidence on runtime errors.
    ctx.finalize_motion_evidence()
    metadata = ctx.metrics["motion_history_trial"]["value"]
    assert metadata["partial"] is True and metadata["sample_count"] == 1
    payload = json.loads((tmp_path / metadata["json"]).read_text(encoding="utf-8"))
    assert len(payload["samples"]) == 1
    assert len(steps) == 2 and robot.commands == []
    assert not ctx.failed and not ctx.skipped


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_pose", [None, ([float("nan"), 0, 0], [0, 0, 0, 1])])
async def test_jik_final_restore_requires_actual_pose_instead_of_stale_fallback(invalid_pose):
    commands = []
    steps = []
    robot = SimpleNamespace(
        dof_count=2,
        dof_names=["a", "b"],
        get_joint_positions=lambda: np.zeros(2),
        get_joint_position_limits=lambda: (np.full(2, -1), np.full(2, 1)),
        set_joint_positions=lambda values: commands.append(np.asarray(values).copy()),
        set_joint_position_targets=lambda values: None,
        set_joint_velocities=lambda values: None,
        get_link_world_transforms=lambda paths: {
            paths[0]: (np.zeros(3), np.array([0, 0, 0, 1])) if len(steps) == 1 else invalid_pose
        },
    )
    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool")

    async def step_one():
        steps.append(None)

    async def jacobian(joints, step_fn):
        return np.zeros((6, 2))

    solver.compute_jacobian = jacobian
    with pytest.raises(required_readback.RequiredReadbackError):
        await solver.solve(np.ones(3), [1, 0, 0, 0], step_one, max_iterations=1)
    # Preserve the original attempted solve and best-state restore, with no retry.
    assert len(steps) == len(commands) == 2


@pytest.mark.parametrize("invalid", INVALID)
@pytest.mark.parametrize("invalid_method", ["get_joint_positions", "get_joint_velocities"])
def test_saved_default_targets_require_finite_correctly_shaped_state(invalid, invalid_method):
    robot = _Robot()
    setattr(robot, invalid_method, lambda: invalid)
    with pytest.raises(required_readback.RequiredReadbackError):
        robot_state.capture_default_state(robot)
    assert robot.commands == []

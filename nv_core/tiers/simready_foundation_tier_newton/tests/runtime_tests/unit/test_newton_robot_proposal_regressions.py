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
import math
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Tf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    ee_discovery,
    ik_target_reach,
    jacobian_ik,
    jik_solver,
    joint_targets,
    multi_joint_coordination,
    required_readback,
    state_accuracy,
)


@pytest.mark.parametrize(
    "values",
    [
        np.array([True, False]),
        np.array(["0", "1"]),
        np.array([0, 1], dtype=object),
        np.array([complex(1, 2), 0]),
        np.array([complex(1, math.inf), 0]),
    ],
)
def test_required_views_reject_non_real_numeric_dtypes(values):
    with pytest.raises(required_readback.RequiredReadbackError):
        required_readback.require_vector(values, "JIK", "joint position", 2)


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.uint32])
def test_required_numeric_views_keep_original_backend_array_and_dtype(dtype):
    values = np.array([0, 1], dtype=dtype)
    result = required_readback.require_vector(values, "JIK", "joint position", 2)
    assert result is values and result.dtype == values.dtype


@pytest.mark.parametrize("sentinel", [math.inf, 3.402823466e38, 3.402823e38])
def test_angular_sentinel_targets_are_finite_and_local(sentinel):
    target = multi_joint_coordination.compute_factor_target(-sentinel, sentinel, 0.1, 0.3, center=0.7, angular=True)
    assert math.isfinite(target) and 0.7 - math.pi <= target <= 0.7 + math.pi
    assert joint_targets.bounded_joint_range(-sentinel, sentinel, 0.7) is None


@pytest.mark.parametrize("bound", [1e12, 1e38])
def test_actual_large_finite_limits_are_not_sdk_sentinels(bound):
    assert joint_targets.bounded_joint_range(-bound, bound, 0, angular=True) == (-bound, bound)


@pytest.mark.parametrize("lower,upper", [(1e308, 1.1e308), (-1.1e308, -1e308)])
def test_collapsed_mjc_margin_keeps_extreme_finite_midpoint_inside_limits(lower, upper):
    for factor in (0, 0.5, 1):
        target = multi_joint_coordination.compute_factor_target(lower, upper, 0.5, factor)
        assert math.isfinite(target) and lower <= target <= upper
        assert target == pytest.approx(lower + (upper - lower) * 0.5)


@pytest.mark.parametrize(
    "lower,upper",
    [(math.nan, 1), (0, math.nan), (2, 1), (1, 1), (math.inf, math.inf), (-math.inf, -math.inf), (-1e308, 1e308)],
)
def test_invalid_ranges_do_not_authorize_guessed_targets(lower, upper):
    assert joint_targets.bounded_joint_range(lower, upper, 0, angular=True) is None


@pytest.mark.parametrize("lower,upper,center", [(-math.inf, 0.2, 9), (0.2, math.inf, -9)])
def test_one_sided_angular_stops_survive_fallback(lower, upper, center):
    effective = joint_targets.bounded_joint_range(lower, upper, center, angular=True)
    assert effective is not None
    for factor in (0, 0.3, 1):
        target = multi_joint_coordination.compute_factor_target(lower, upper, 0.1, factor, center=center, angular=True)
        assert lower <= target <= upper and effective[0] <= target <= effective[1]


@pytest.mark.parametrize("factor,margin", [(math.nan, 0.1), (2, 0.1), (0.5, -1), (0.5, math.inf)])
def test_invalid_mjc_configuration_is_not_a_command(factor, margin):
    with pytest.raises(ValueError):
        multi_joint_coordination.compute_factor_target(-1, 1, margin, factor)


@pytest.mark.asyncio
async def test_empty_mjc_articulation_retains_skip_without_required_readback():
    skipped = []
    robot = SimpleNamespace(
        dof_names=[],
        get_joint_position_limits=lambda: ([], []),
        get_joint_positions=lambda: pytest.fail("applicability must not read an empty required view"),
    )
    ctx = SimpleNamespace(step=lambda *args: None, add_metric=lambda *args: None, skip=skipped.append)
    await multi_joint_coordination.run_multi_joint_coordination(ctx, robot, {}, {})
    assert len(skipped) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [math.inf, 3.402823e38])
async def test_mjc_skip_reports_qualified_unbounded_angular_excursion_not_finite_limits(limit):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joint")
    metrics, skipped = {}, []
    context = SimpleNamespace(
        step=lambda message: None,
        warn=lambda message: None,
        add_metric=lambda key, value: metrics.__setitem__(key, value),
        skip=skipped.append,
    )
    robot = SimpleNamespace(
        dof_names=["joint"],
        get_joint_position_limits=lambda: ([-limit], [limit]),
        get_joint_positions=lambda: pytest.fail("inapplicable coordination must not read required state"),
    )
    await multi_joint_coordination.run_multi_joint_coordination(context, robot, {"asset_prim": root}, {})
    assert metrics["mjc_valid_joints"] == 1 and len(skipped) == 1
    assert "1/1 joints with qualified bounded excursions" in skipped[0]
    assert "unbounded revolute" in skipped[0] and "local +/-pi" in skipped[0]
    assert "with finite position limits" not in skipped[0]
    assert "so it cannot participate" not in skipped[0]


class _HostBoundaryTensor:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def detach(self):
        self.calls.append("detach")
        return self

    def cpu(self):
        self.calls.append("cpu")
        return self

    def numpy(self):
        self.calls.append("numpy")
        return self.values


def _make_host_boundary_articulation(joints, position):
    calls = {"fk": [], "ik": []}

    def forward(frame, values, **kwargs):
        calls["fk"].append(values.copy())
        return position, np.array([1.0, 0.0, 0.0, 0.0])

    def inverse(frame, target, orientation, warm_start, position_tolerance, orientation_tolerance):
        calls["ik"].append(warm_start.copy())
        return np.array([0.1, 0.2, 0.3]), True

    subset = SimpleNamespace(
        get_joint_positions=lambda: joints,
        make_articulation_action=lambda values, velocities: SimpleNamespace(joint_positions=values),
    )
    kinematics = SimpleNamespace(compute_forward_kinematics=forward, compute_inverse_kinematics=inverse)
    articulation = SimpleNamespace(
        get_joints_subset=lambda: subset,
        get_kinematics_solver=lambda: kinematics,
        get_end_effector_frame=lambda: "tip",
    )
    return articulation, calls


@pytest.mark.parametrize(
    "values",
    [
        np.array([True, False, True]),
        np.array(["0", "1", "2"]),
        np.array([0, 1, 2], dtype=object),
        np.array([complex(0, 1), 0, 0]),
        np.array([complex(0, math.inf), 0, 0]),
    ],
)
@pytest.mark.parametrize("boundary", ["fk_joints", "fk_position", "ik_warm_start"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_lula_host_boundary_rejects_malformed_dtype_before_numeric_conversion(values, boundary, wrapped):
    backend = _HostBoundaryTensor(values) if wrapped else values
    joints = backend if boundary != "fk_position" else np.array([0.0, 0.1, 0.2])
    position = backend if boundary == "fk_position" else np.array([1.0, 2.0, 3.0])
    articulation, calls = _make_host_boundary_articulation(joints, position)
    with pytest.raises(required_readback.RequiredReadbackError):
        if boundary == "ik_warm_start":
            ik_target_reach._compute_inverse_kinematics_host(articulation, np.zeros(3), 0.01, 0.1)
        else:
            ik_target_reach._compute_end_effector_pose_host(articulation)
    assert len(calls["fk"]) == (1 if boundary == "fk_position" else 0)
    assert calls["ik"] == []
    if wrapped:
        assert backend.calls == ["detach", "cpu", "numpy"]


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.uint32])
@pytest.mark.parametrize("wrapped", [False, True])
def test_lula_host_boundary_keeps_backend_copy_and_qualified_numeric_float64_contract(dtype, wrapped):
    values = np.array([0, 1, 2], dtype=dtype)
    backend = _HostBoundaryTensor(values) if wrapped else values
    host = ik_target_reach._host_array(backend)
    assert host is values and host.dtype == values.dtype
    if wrapped:
        assert backend.calls == ["detach", "cpu", "numpy"]
        backend.calls.clear()
    articulation, calls = _make_host_boundary_articulation(backend, backend)
    position, _ = ik_target_reach._compute_end_effector_pose_host(articulation)
    action, success = ik_target_reach._compute_inverse_kinematics_host(articulation, np.zeros(3), 0.01, 0.1)
    assert success and action.joint_positions.shape == (3,)
    np.testing.assert_array_equal(position, values)
    assert position.dtype == np.float64
    assert calls["fk"][0].dtype == np.float64 and calls["ik"][0].dtype == np.float64
    np.testing.assert_array_equal(calls["fk"][0], values)
    np.testing.assert_array_equal(calls["ik"][0], values)
    np.testing.assert_array_equal(values, [0, 1, 2])
    if wrapped:
        assert backend.calls == ["detach", "cpu", "numpy"] * 3


def test_angular_identity_requires_unique_joint_inside_loaded_asset():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joint")
    UsdPhysics.PrismaticJoint.Define(stage, "/Other/joint")
    assert joint_targets.joint_is_angular({"asset_prim": root}, "joint")
    UsdPhysics.PrismaticJoint.Define(stage, "/Robot/branch/joint")
    assert not joint_targets.joint_is_angular({"asset_prim": root}, "joint")


@pytest.mark.parametrize("lower,upper", [(0.8, 5.4), (-5.4, -0.8), (0.01, 0.02), (-0.01, 0.01)])
def test_state_accuracy_keeps_every_command_inside_native_limits(lower, upper):
    targets = state_accuracy.compute_test_positions(lower, upper)
    assert len(targets) == 5 and all(lower <= target <= upper for target in targets)
    assert targets[0] == targets[2] == targets[4]


@pytest.mark.parametrize("lower,upper", [(2, 1), (1, 1), (math.nan, 1)])
def test_state_accuracy_rejects_invalid_limits(lower, upper):
    with pytest.raises(ValueError):
        state_accuracy.compute_test_positions(lower, upper)


@pytest.mark.parametrize("model", ["ur30", "ur300", "ur50", "ur100"])
def test_lula_cannot_select_a_different_model_by_substring(model):
    assert ik_target_reach.select_lula_robot_name("ARM", "/robots/" + model + "/robot.usda", None) is None


@pytest.mark.parametrize("model", ["FR3", "UR3e", "UR5e", "UR10e"])
def test_lula_preserves_complete_supported_names(model):
    assert ik_target_reach.select_lula_robot_name("ARM", "/robots/" + model.lower() + "/robot.usda", None) == model


def test_lula_panda_alias_override_and_runtime_catalog_boundaries():
    assert ik_target_reach.select_lula_robot_name("ARM", "/robots/Panda/robot.usda", None) == "Franka"
    assert ik_target_reach.select_lula_robot_name("ARM", "ur30", "ReviewedOverride") == "ReviewedOverride"
    ctx = SimpleNamespace(asset_path="/robots/CustomArm20/robot.usda", log=lambda *args: None)
    loader = SimpleNamespace(get_supported_robots_with_lula_kinematics=lambda: ["CustomArm2"])
    assert ik_target_reach._resolve_lula_robot_name(ctx, SimpleNamespace(), None, loader) is None
    ctx.asset_path = "/robots/CustomArm2/robot.usda"
    assert ik_target_reach._resolve_lula_robot_name(ctx, SimpleNamespace(), None, loader) == "CustomArm2"


def test_indexed_arm_action_preserves_uncommanded_fingers_and_input():
    current = np.array([0.0] * 7 + [0.04, 0.05])
    action = SimpleNamespace(joint_positions=np.arange(7) * 0.1, joint_indices=np.arange(7))
    result = ik_target_reach.expand_ik_action(action, current)
    np.testing.assert_allclose(result[:7], action.joint_positions)
    np.testing.assert_allclose(result[7:], current[7:])
    np.testing.assert_array_equal(current[:7], np.zeros(7))


@pytest.mark.parametrize("indices", [None, [0, 0], [0, 9], [0, 0.5], [0.0, 1.0], [True, 1], [-1, 1]])
def test_invalid_indexed_action_cannot_be_dispatched(indices):
    with pytest.raises(ValueError):
        ik_target_reach.expand_ik_action(
            SimpleNamespace(joint_positions=[0.1, 0.2], joint_indices=indices), np.zeros(9)
        )


def test_indexed_action_cannot_preserve_nonfinite_uncommanded_state():
    with pytest.raises(required_readback.RequiredReadbackError):
        ik_target_reach.expand_ik_action(SimpleNamespace(joint_positions=[0.1], joint_indices=[0]), [0, math.nan])


@pytest.mark.parametrize("values", [[True], [".1"], np.array([0.1], dtype=object), [complex(0.1, math.inf)]])
def test_ik_action_positions_cannot_be_coerced_from_malformed_dtypes(values):
    with pytest.raises(ValueError):
        ik_target_reach.expand_ik_action(SimpleNamespace(joint_positions=values, joint_indices=[0]), np.zeros(2))


class _ProbeRobot:
    dof_count = 1
    dof_names = ["joint"]

    def __init__(self):
        self.positions = np.array([0.1])
        self.targets = np.array([0.9])
        self.calls = []

    def get_joint_positions(self):
        return self.positions.copy()

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def set_joint_positions(self, values):
        self.positions = values.copy()
        self.calls.append("positions")

    def set_joint_position_targets(self, values):
        self.targets = values.copy()
        self.calls.append("targets")

    def set_joint_velocities(self, values):
        self.calls.append("velocities")
        np.testing.assert_array_equal(values, [0])

    def get_link_world_transforms(self, paths):
        return {paths[0]: (np.array([self.positions[0], 0, 0]), np.array([0, 0, 0, 1]))}


@pytest.mark.asyncio
async def test_lula_teleport_synchronizes_controls_and_propagates_dispatch_error():
    robot = _ProbeRobot()
    steps = []

    async def step():
        steps.append(None)

    await ik_target_reach._teleport_to_joints(robot, np.array([0.2]), SimpleNamespace(step_one=step), settle_frames=3)
    assert robot.calls == ["positions", "targets", "velocities"] and len(steps) == 3
    with pytest.raises(ValueError):
        await ik_target_reach._teleport_to_joints(robot, np.array([0.2, 0.3]), SimpleNamespace(step_one=step))
    cause = RuntimeError("backend rejected target")

    def failed_target(values):
        raise cause

    robot.set_joint_position_targets = failed_target
    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        await ik_target_reach._teleport_to_joints(robot, np.array([0.2]), SimpleNamespace(step_one=step))
    assert caught.value.__cause__ is cause and len(steps) == 3


def test_fk_samples_keep_linear_home_one_sided_stop_and_locked_coordinates():
    samples = jacobian_ik._sample_joint_configs(
        np.array([0.1, 0.1, 0.1, 0.1]),
        [-3.402823e38, -math.inf, -math.inf, -1],
        [3.402823e38, 0.2, math.inf, 1],
        {3},
        20,
        angular_indices={0, 1},
    )
    values = np.asarray(samples)
    assert np.isfinite(values).all() and np.max(np.abs(values[:, 0] - 0.1)) <= math.pi
    assert np.max(values[:, 1]) <= 0.2
    np.testing.assert_array_equal(values[:, 2:], np.full((20, 2), 0.1))


@pytest.mark.asyncio
async def test_fk_sampling_exclusion_does_not_freeze_nonlocked_solver_dofs():
    positions, commands = np.zeros(2), []

    def set_positions(values):
        positions[:] = values
        commands.append(values.copy())

    robot = SimpleNamespace(
        dof_count=2,
        dof_names=["bounded_revolute", "unbounded_prismatic"],
        get_joint_positions=lambda: positions.copy(),
        get_joint_position_limits=lambda: (np.array([-1.0, -math.inf]), np.array([1.0, math.inf])),
        set_joint_positions=set_positions,
        set_joint_position_targets=lambda values: None,
        set_joint_velocities=lambda values: None,
        get_link_world_transforms=lambda paths: {
            paths[0]: (np.array([positions.sum(), 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))
        },
    )
    samples = jacobian_ik._sample_joint_configs(
        positions, [-1.0, -math.inf], [1.0, math.inf], set(), 5, angular_indices={0}
    )
    assert all(sample[1] == 0.0 for sample in samples)

    async def step():
        pass

    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool", locked_indices=set())
    result = await solver.solve([0.5, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], step, max_iterations=5)
    assert result.success and result.converged_joints[1] > 0.2
    assert any(command[1] != 0.0 for command in commands)


@pytest.mark.asyncio
async def test_newton_jacobian_synchronizes_every_probe_and_keeps_step_policy():
    robot = _ProbeRobot()
    steps = []

    async def step():
        steps.append(None)
        robot.positions += (robot.targets - robot.positions) * 0.2

    solver = jik_solver.JacobianIKSolver(
        robot, "/Robot/tool", finite_difference_epsilon=0.001, jacobian_propagation_steps=2
    )
    jacobian = await solver.compute_jacobian(np.array([0.1]), step)
    assert jacobian[0, 0] == pytest.approx(1) and len(steps) == 6
    assert robot.calls == ["positions", "targets", "velocities"] * 3
    np.testing.assert_allclose(robot.positions, [0.1])
    np.testing.assert_allclose(robot.targets, [0.1])


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [0.0, 1e-6])
async def test_clipped_probe_uses_actual_displacement_at_both_narrow_limits(position):
    robot = _ProbeRobot()
    robot.get_joint_position_limits = lambda: (np.array([0.0]), np.array([1e-6]))

    async def step():
        pass

    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool", finite_difference_epsilon=0.001)
    jacobian = await solver.compute_jacobian(np.array([position]), step)
    assert jacobian[0, 0] == pytest.approx(1.0)
    np.testing.assert_allclose(robot.positions, [position])
    np.testing.assert_allclose(robot.targets, [position])


@pytest.mark.asyncio
async def test_zero_displacement_probe_has_zero_column_and_no_perturbed_command():
    robot = _ProbeRobot()
    robot.get_joint_position_limits = lambda: (np.array([0.1]), np.array([0.1]))

    async def step():
        pass

    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool", finite_difference_epsilon=0.001)
    jacobian = await solver.compute_jacobian(np.array([0.1]), step)
    np.testing.assert_array_equal(jacobian, np.zeros((6, 1)))
    assert robot.calls == ["positions", "targets", "velocities"] * 2


@pytest.mark.asyncio
@pytest.mark.parametrize("positions", [[True], [".1"], [complex(0.1, math.inf)]])
async def test_malformed_jacobian_input_is_rejected_before_float_conversion_or_restore(positions):
    robot = _ProbeRobot()

    async def step():
        pytest.fail("invalid required configuration cannot propagate")

    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(required_readback.RequiredReadbackError):
        await solver.compute_jacobian(positions, step)
    assert robot.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_failed_or_cancelled_probe_restores_without_extra_steps(cancel):
    robot = _ProbeRobot()
    steps = []
    cause = asyncio.CancelledError() if cancel else RuntimeError("native propagation failure")

    async def step():
        steps.append(None)
        if len(steps) == 2:
            raise cause

    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(type(cause)) as caught:
        await solver.compute_jacobian(np.array([0.1]), step)
    assert (caught.value is cause if cancel else caught.value.__cause__ is cause) and len(steps) == 2
    np.testing.assert_allclose(robot.positions, [0.1])
    np.testing.assert_allclose(robot.targets, [0.1])


@pytest.mark.asyncio
async def test_fk_target_failure_restores_home_and_preserves_required_error():
    robot = _ProbeRobot()
    cause = required_readback.RequiredReadbackError("live pose unavailable")
    reads = []

    def pose():
        reads.append(None)
        if len(reads) == 2:
            raise cause
        return np.zeros(3), np.array([1, 0, 0, 0])

    async def step():
        pass

    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        await jacobian_ik._generate_fk_targets(
            SimpleNamespace(step_one=step, step=lambda *args: None),
            robot,
            SimpleNamespace(get_ee_pose=pose),
            np.array([0.1]),
            np.zeros(3),
            [-1],
            [1],
            set(),
            1,
            0,
        )
    assert caught.value is cause
    np.testing.assert_allclose(robot.positions, [0.1])
    np.testing.assert_allclose(robot.targets, [0.1])


@pytest.mark.asyncio
@pytest.mark.parametrize("home", [np.array([math.nan]), np.array([0.1, 0.2])])
async def test_invalid_fk_home_cannot_be_dispatched_by_error_restoration(home):
    robot = _ProbeRobot()

    async def step():
        pass

    with pytest.raises(ValueError):
        await jacobian_ik._generate_fk_targets(
            SimpleNamespace(step_one=step),
            robot,
            SimpleNamespace(),
            home,
            np.zeros(3),
            [-1],
            [1],
            set(),
            1,
            0,
        )
    assert robot.calls == []


def _body(stage, name):
    prim = UsdGeom.Xform.Define(stage, "/Robot/" + name).GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(prim)
    return str(prim.GetPath())


def _joint(stage, name, parent, child, fixed=False):
    schema = UsdPhysics.FixedJoint if fixed else UsdPhysics.RevoluteJoint
    joint = schema.Define(stage, "/Robot/joints/" + name)
    if parent:
        joint.CreateBody0Rel().SetTargets([parent])
    if child:
        joint.CreateBody1Rel().SetTargets([child])
    return joint


def _arm():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    base, mid, tip = [_body(stage, name) for name in ("base", "right_link", "right_hand")]
    _joint(stage, "root_pin", None, base, fixed=True)
    _joint(stage, "shoulder", base, mid)
    _joint(stage, "wrist", tip, mid)  # A valid reversed endpoint ordering.
    return stage, root, base, tip


def test_ee_graph_wins_over_wrong_link_order_and_keeps_right_hand():
    stage, root, base, tip = _arm()
    torso = _body(stage, "torso")
    _joint(stage, "torso_mount", base, torso, fixed=True)
    finger = _body(stage, "left_finger")
    _joint(stage, "finger", tip, finger)
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets([base, tip, torso])
    assert ee_discovery.discover_end_effector_link(stage, SimpleNamespace(body_names=["torso"]), "/Robot") == tip


@pytest.mark.parametrize("excluded", [False, True])
def test_newton_ee_uses_the_tree_when_a_parallel_linkage_closure_is_excluded(excluded):
    stage, _, base, tip = _arm()
    parallel = _body(stage, "counterbalance")
    _joint(stage, "counterbalance_mount", base, parallel)
    closure = _joint(stage, "external_loop_constraint", parallel, "/Robot/right_link")
    closure.CreateExcludeFromArticulationAttr(excluded)
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == (tip if excluded else None)


@pytest.mark.parametrize("defect", ["dangling", "outside", "several", "isolated", "same_body"])
def test_newton_excluded_constraint_still_requires_resolved_tree_body_endpoints(defect):
    stage, _, base, _ = _arm()
    closure = _joint(stage, "excluded_constraint", base, None)
    closure.CreateExcludeFromArticulationAttr(True)
    if defect == "dangling":
        targets = ["/Robot/absent"]
    elif defect == "outside":
        other = UsdGeom.Xform.Define(stage, "/Other/body").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(other)
        targets = [other.GetPath()]
    elif defect == "several":
        targets = [base, "/Robot/right_link"]
    elif defect == "isolated":
        targets = [_body(stage, "detached")]
    else:
        targets = [base]
    closure.CreateBody1Rel().SetTargets(targets)
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


def test_missing_external_metadata_target_cannot_alias_an_internal_basename():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    _body(stage, "tip")
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Foreign/tip"])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


@pytest.mark.asyncio
async def test_native_probe_dispatch_failure_cannot_become_solver_nonconvergence():
    robot = _ProbeRobot()
    cause = OSError("native target adapter unavailable")

    def failed_target(values):
        raise cause

    robot.set_joint_position_targets = failed_target
    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool")

    async def step():
        pass

    ctx = SimpleNamespace(
        step_one=step, step=lambda *args: None, warn=lambda *args: pytest.fail("not a solver verdict")
    )
    target = SimpleNamespace(position=np.zeros(3), orientation=np.array([1, 0, 0, 0]), index=0)
    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        await jacobian_ik._solve_target(ctx, solver, target, None, 0.02, 0.1, 1)
    assert caught.value.__cause__ is cause


@pytest.mark.asyncio
async def test_native_probe_propagation_failure_cannot_become_solver_nonconvergence():
    robot = _ProbeRobot()
    cause = RuntimeError("native simulation step failed")

    async def step():
        raise cause

    solver = jik_solver.JacobianIKSolver(robot, "/Robot/tool")
    ctx = SimpleNamespace(
        step_one=step, step=lambda *args: None, warn=lambda *args: pytest.fail("not a solver verdict")
    )
    target = SimpleNamespace(position=np.zeros(3), orientation=np.array([1, 0, 0, 0]), index=0)
    with pytest.raises(required_readback.RequiredReadbackError) as caught:
        await jacobian_ik._solve_target(ctx, solver, target, None, 0.02, 0.1, 1)
    assert caught.value.__cause__ is cause


@pytest.mark.asyncio
@pytest.mark.parametrize("locked,num_targets", [(False, 1), (False, 5), (True, 1)])
async def test_no_safe_fk_excursion_skips_before_solver_or_home_only_targets(monkeypatch, locked, num_targets):
    stage, root, _, tip = _arm()
    robot = _ProbeRobot()
    robot.prim_path = "/Robot"
    robot.get_joint_position_limits = lambda: (
        (np.array([-1.0]), np.array([1.0])) if locked else (np.array([-math.inf]), np.array([math.inf]))
    )
    skipped, metrics = [], {}

    async def step_one():
        pass

    ctx = SimpleNamespace(
        step_one=step_one,
        skip=skipped.append,
        add_metric=lambda name, value: metrics.update({name: value}),
        step=lambda *args: None,
        log=lambda *args: None,
    )
    monkeypatch.setattr(jacobian_ik, "is_standalone_gripper", lambda *args: False)
    monkeypatch.setattr(jacobian_ik, "resolve_live_end_effector_link", lambda *args: tip)
    monkeypatch.setattr(
        jacobian_ik, "JacobianIKSolver", lambda **kwargs: pytest.fail("no eligible solver prerequisites")
    )
    scene_info = {"stage": stage, "asset_prim": root, "loop_joint_indices": [0] if locked else []}
    await jacobian_ik.run_jacobian_ik(ctx, robot, scene_info, {"num_targets": num_targets, "ee_link_path": tip})
    assert len(skipped) == 1 and "insufficient coverage" in skipped[0]
    assert metrics["jik_sampling_eligible_dofs"] == 0 and robot.calls == []


@pytest.mark.parametrize("defect", ["ambiguous", "cycle", "disconnected", "external", "multiple_pins"])
def test_invalid_ee_graph_never_falls_back_to_link_order(defect):
    stage, root, base, tip = _arm()
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets([tip])
    if defect == "ambiguous":
        left = _body(stage, "left_link")
        end = _body(stage, "left_hand")
        _joint(stage, "left_shoulder", base, left)
        _joint(stage, "left_wrist", left, end)
    elif defect == "cycle":
        _joint(stage, "loop", base, tip)
    elif defect == "disconnected":
        _joint(stage, "other", _body(stage, "other_base"), _body(stage, "other_tip"))
    elif defect == "external":
        UsdGeom.Xform.Define(stage, "/Foreign/body")
        _joint(stage, "external", tip, "/Foreign/body")
    else:
        _joint(stage, "another_pin", base, None, fixed=True)
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


def test_explicit_ee_is_bounded_and_invalid_identity_never_falls_back():
    stage, _, _, tip = _arm()
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot", explicit_path=tip) == tip
    UsdGeom.Xform.Define(stage, "/Foreign/tool")
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot", explicit_path="/Foreign/tool") is None
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot", explicit_path="right_hand") is None


def test_fixed_tool_alias_ambiguity_and_moving_child_are_not_guessed():
    stage, _, _, tip = _arm()
    UsdGeom.Xform.Define(stage, tip + "/tcp")
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip + "/tcp"
    UsdGeom.Xform.Define(stage, tip + "/flange")
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


@pytest.mark.parametrize("enabled", [True, False])
def test_external_joint_can_disqualify_only_its_connected_loaded_marker(enabled):
    stage, _, _, tip = _arm()
    marker = tip + "/tcp"
    marker_prim = UsdGeom.Xform.Define(stage, marker).GetPrim()
    UsdGeom.Xformable(marker_prim).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(marker_prim)
    fixed = UsdPhysics.FixedJoint.Define(stage, "/Foreign/fixed_marker_joint")
    fixed.CreateBody0Rel().SetTargets([tip])
    fixed.CreateBody1Rel().SetTargets([marker])
    UsdGeom.Xform.Define(stage, "/Foreign/tcp")
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Foreign/moving_marker_joint")
    joint.CreateBody0Rel().SetTargets([tip])
    joint.CreateBody1Rel().SetTargets([marker])
    joint.CreateJointEnabledAttr().Set(enabled)
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == (tip if enabled else marker)
    joint.GetBody1Rel().SetTargets(["/Foreign/tcp"])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == marker


@pytest.mark.parametrize("connected", [True, False])
def test_rigid_marker_requires_a_fixed_enabled_connection(connected):
    stage, _, _, tip = _arm()
    marker = tip + "/tcp"
    prim = UsdGeom.Xform.Define(stage, marker).GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(prim)
    if connected:
        joint = UsdPhysics.FixedJoint.Define(stage, "/Foreign/fixed_marker_joint")
        joint.CreateBody0Rel().SetTargets([tip])
        joint.CreateBody1Rel().SetTargets([marker])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == (marker if connected else tip)


def test_deep_joint_tree_discovery_is_iterative():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Robot")
    previous = _body(stage, "base")
    _joint(stage, "root_pin", previous, None, fixed=True)
    for index in range(1100):
        current = _body(stage, "link_%04d" % index)
        _joint(stage, "joint_%04d" % index, previous, current)
        previous = current
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == previous


@pytest.mark.parametrize("middle", ["inner_link", "outer_arm", "gripper_mount", "paddle", "finger_link"])
def test_serial_arm_names_do_not_prune_a_non_finger_endpoint(middle):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Robot")
    base, mid, tip = [_body(stage, name) for name in ("base", middle, "wrist")]
    _joint(stage, "pin", None, base, fixed=True)
    _joint(stage, "shoulder", base, mid)
    _joint(stage, "wrist", mid, tip)
    UsdGeom.Xform.Define(stage, tip + "/tool0")
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip + "/tool0"


def test_terminal_finger_subtrees_do_not_override_the_wrist_marker():
    stage, _, _, tip = _arm()
    left, knuckle, pad = [_body(stage, name) for name in ("left_finger", "right_knuckle", "finger_pad")]
    _joint(stage, "left", tip, left)
    _joint(stage, "right", tip, knuckle)
    _joint(stage, "pad", knuckle, pad)
    UsdGeom.Xform.Define(stage, tip + "/tool0")
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip + "/tool0"


@pytest.mark.parametrize("forwarded", [False, True])
def test_joint_child_frames_resolve_to_their_owning_rigid_bodies(forwarded):
    stage, root, base, tip = _arm()
    mid = "/Robot/right_link"
    for body in (base, mid, tip):
        for frame in ("in", "out"):
            UsdGeom.Xform.Define(stage, body + "/" + frame)
    for name, parent, child in (
        ("root_pin", None, base + "/in"),
        ("shoulder", base + "/out", mid + "/in"),
        ("wrist", tip + "/in", mid + "/out"),
    ):
        joint = stage.GetPrimAtPath("/Robot/joints/" + name)
        joint.GetRelationship("physics:body0").SetTargets([parent] if parent else [])
        joint.GetRelationship("physics:body1").SetTargets([child])
    if forwarded:
        root.CreateRelationship("wristFrame").SetTargets([tip + "/in"])
        stage.GetPrimAtPath("/Robot/joints/wrist").GetRelationship("physics:body0").SetTargets(["/Robot.wristFrame"])
    UsdGeom.Xform.Define(stage, tip + "/tool0")
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip + "/tool0"


def test_bounded_static_joint_frame_is_a_world_anchor_not_an_arm_body():
    stage, _, _, tip = _arm()
    UsdGeom.Xform.Define(stage, "/Robot/world_frame")
    stage.GetPrimAtPath("/Robot/joints/root_pin").GetRelationship("physics:body0").SetTargets(["/Robot/world_frame"])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip


def test_nested_body_owns_its_frames_instead_of_the_parent_body():
    stage, _, _, tip = _arm()
    nested = _body(stage, "base/nested")
    UsdGeom.Xformable(stage.GetPrimAtPath(nested)).SetResetXformStack(True)
    UsdGeom.Xform.Define(stage, nested + "/frame")
    stage.GetPrimAtPath("/Robot/joints/root_pin").GetRelationship("physics:body1").SetTargets([nested + "/frame"])
    stage.GetPrimAtPath("/Robot/joints/shoulder").GetRelationship("physics:body0").SetTargets([nested + "/frame"])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip


@pytest.mark.parametrize("target", ["/Other/right_hand/frame", "/Robot/right_link/out", "/Robot.invalidProperty"])
def test_invalid_body_identity_cannot_be_promoted_or_recovered_from_inventory(target):
    stage, root, _, tip = _arm()
    foreign = UsdGeom.Xform.Define(stage, "/Other/right_hand").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(foreign)
    UsdGeom.Xform.Define(stage, "/Other/right_hand/frame")
    UsdGeom.Xform.Define(stage, "/Robot/right_link/out")
    stage.GetPrimAtPath("/Robot/joints/wrist").GetRelationship("physics:body0").SetTargets([target])
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets([tip])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


def test_body_owner_outside_the_loaded_root_is_not_a_world_anchor():
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/Parent").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    UsdGeom.Xform.Define(stage, "/Parent/Robot/frame")
    tip = UsdGeom.Xform.Define(stage, "/Parent/Robot/tip").GetPrim()
    UsdGeom.Xformable(tip).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tip)
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Parent/Robot/joint")
    joint.GetBody0Rel().SetTargets(["/Parent/Robot/frame"])
    joint.GetBody1Rel().SetTargets([tip.GetPath()])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Parent/Robot") is None


def test_non_body_tcp_remains_fixed_when_a_joint_targets_its_frame():
    stage, _, _, tip = _arm()
    UsdGeom.Xform.Define(stage, tip + "/tool0")
    stage.GetPrimAtPath("/Robot/joints/wrist").GetRelationship("physics:body0").SetTargets([tip + "/tool0"])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") == tip + "/tool0"


def test_independent_tcp_body_with_dynamic_child_frame_joint_is_not_a_fixed_marker():
    stage, _, _, tip = _arm()
    tcp = UsdGeom.Xform.Define(stage, tip + "/tool0").GetPrim()
    UsdGeom.Xformable(tcp).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tcp)
    UsdGeom.Xform.Define(stage, tip + "/tool0/frame")
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Foreign/dynamic_tcp")
    joint.GetBody0Rel().SetTargets([tip])
    joint.GetBody1Rel().SetTargets([tip + "/tool0/frame"])
    assert ee_discovery._find_fixed_ee_child(stage.GetPrimAtPath(tip)) is None


@pytest.mark.parametrize("defect", ["empty", "cycle", "multi", "scope"])
def test_malformed_forwarded_joint_body_does_not_become_a_world_anchor(defect):
    stage, root, base, tip = _arm()
    forwarded = root.CreateRelationship("forwardedBody")
    if defect == "cycle":
        forwarded.SetTargets(["/Robot.forwardedAgain"])
        root.CreateRelationship("forwardedAgain").SetTargets(["/Robot.forwardedBody"])
    elif defect == "multi":
        UsdGeom.Xform.Define(stage, base + "/frame")
        forwarded.SetTargets([base, base + "/frame"])
    elif defect == "scope":
        UsdGeom.Scope.Define(stage, "/Robot/scope")
        forwarded.SetTargets(["/Robot/scope"])
    stage.GetPrimAtPath("/Robot/joints/root_pin").GetRelationship("physics:body1").SetTargets(["/Robot.forwardedBody"])
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets([tip])
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


@pytest.mark.parametrize("connection", ["parent", "other", "world", "multi"])
def test_independent_tcp_child_frame_requires_a_unique_fixed_parent_connection(connection):
    stage, _, base, tip = _arm()
    tcp = UsdGeom.Xform.Define(stage, tip + "/tool0").GetPrim()
    UsdGeom.Xformable(tcp).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tcp)
    UsdGeom.Xform.Define(stage, tip + "/tool0/frame")
    joint = UsdPhysics.FixedJoint.Define(stage, "/Foreign/fixed_tcp")
    if connection == "parent":
        UsdGeom.Xform.Define(stage, tip + "/frame")
        joint.GetBody0Rel().SetTargets([tip + "/frame"])
    elif connection == "other":
        other = UsdGeom.Xform.Define(stage, "/Foreign/body").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(other)
        joint.GetBody0Rel().SetTargets([other.GetPath()])
    elif connection == "multi":
        joint.GetBody0Rel().SetTargets([tip, base])
    joint.GetBody1Rel().SetTargets([tip + "/tool0/frame"])
    assert ee_discovery._find_fixed_ee_child(stage.GetPrimAtPath(tip)) == (
        str(tcp.GetPath()) if connection == "parent" else None
    )


def test_native_relationship_resolution_error_fails_closed(monkeypatch):
    stage, _, _, _ = _arm()
    original = Usd.Relationship.GetForwardedTargets

    def unavailable(relationship):
        if str(relationship.GetPath()) == "/Robot/joints/root_pin.physics:body1":
            Tf.RaiseCodingError("Relationship resolution unavailable")
        return original(relationship)

    monkeypatch.setattr(Usd.Relationship, "GetForwardedTargets", unavailable)
    assert ee_discovery.discover_end_effector_link(stage, None, "/Robot") is None


def test_unresolved_enabled_constraint_cannot_certify_an_independent_tcp_marker():
    stage, _, base, tip = _arm()
    tcp = UsdGeom.Xform.Define(stage, tip + "/tool0").GetPrim()
    UsdGeom.Xformable(tcp).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tcp)
    fixed = UsdPhysics.FixedJoint.Define(stage, "/Foreign/fixed_tcp")
    fixed.GetBody0Rel().SetTargets([tip])
    fixed.GetBody1Rel().SetTargets([tcp.GetPath()])
    malformed = UsdPhysics.RevoluteJoint.Define(stage, "/Foreign/malformed_tcp")
    malformed.GetBody0Rel().SetTargets([tip])
    malformed.GetBody1Rel().SetTargets([tcp.GetPath(), base])
    assert ee_discovery._find_fixed_ee_child(stage.GetPrimAtPath(tip)) is None

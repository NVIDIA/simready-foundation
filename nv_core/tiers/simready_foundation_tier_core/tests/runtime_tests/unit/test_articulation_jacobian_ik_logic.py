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
"""Tests for jacobian_ik phase pure helpers."""

import math
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.ik_targets import IKTarget
from simready.foundation.tier_core.runtime_tests.articulation_phases.jacobian_ik import (
    _generate_fk_targets,
    _sample_joint_configs,
    _sampling_joint_indices,
    _teleport_to_joints,
    aggregate_jik_summary,
    compute_pass_rate,
    count_distinct_reachable_positions,
    get_defaults,
    interpolate_profile,
    resolve_live_end_effector_link,
    resolve_motion_timing,
    run_jacobian_ik,
    smoothstep,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import (
    RobotType,
    is_standalone_gripper,
)


def test_fk_sampling_limits_unbounded_angular_joints_and_retains_one_sided_stops():
    home = np.array([0.0, 0.0, 0.75])
    configs = _sample_joint_configs(
        home, [-3.402823e38, -math.inf, 0.5], [3.402823e38, 0.1, math.inf], set(), 50, angular_indices={0, 1, 2}
    )
    assert any(not np.array_equal(config, home) for config in configs)
    assert all(abs(config[0]) < math.pi and config[1] <= 0.1 and config[2] >= 0.5 for config in configs)


def test_fk_sampling_holds_unbounded_prismatic_and_unknown_joints():
    configs = _sample_joint_configs([0.2, 0.7], [-math.inf, -3.402823e38], [math.inf, 3.402823e38], set(), 4)
    assert all(np.array_equal(config, [0.2, 0.7]) for config in configs)


@pytest.mark.asyncio
async def test_fk_sampling_exclusion_does_not_freeze_nonlocked_solver_dofs():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.jik_solver import (
        JacobianIKSolver,
    )

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
    samples = _sample_joint_configs(positions, [-1.0, -math.inf], [1.0, math.inf], set(), 5, angular_indices={0})
    assert all(sample[1] == 0.0 for sample in samples)

    async def step():
        pass

    solver = JacobianIKSolver(robot, "/Robot/tool", locked_indices=set())
    result = await solver.solve([0.5, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], step, max_iterations=5)
    assert result.success and result.converged_joints[1] > 0.2
    assert any(command[1] != 0.0 for command in commands)


@pytest.mark.asyncio
async def test_jik_teleport_rejects_controller_failure_without_stepping():
    async def forbidden_step():
        raise AssertionError("must not step a failed probe")

    def fail(value):
        raise OSError("controller write unavailable")

    robot = SimpleNamespace(
        dof_names=["j"],
        set_joint_positions=lambda value: None,
        set_joint_position_targets=fail,
        set_joint_velocities=lambda value: None,
    )
    with pytest.raises(RuntimeError, match="probe configuration") as error:
        await _teleport_to_joints(SimpleNamespace(step_one=forbidden_step), robot, [0.0])
    assert isinstance(error.value.__cause__, OSError)


@pytest.mark.asyncio
async def test_fk_generation_restores_home_on_failure_and_cancellation(monkeypatch):
    import asyncio

    from simready.foundation.tier_core.runtime_tests.articulation_phases import jacobian_ik as phase

    for exception in (RuntimeError("live probe failed"), asyncio.CancelledError()):
        poses = []

        async def fail(*args, error=exception):
            raise error

        async def step():
            pass

        robot = SimpleNamespace(
            dof_names=["joint"],
            set_joint_positions=lambda value, captured_poses=poses: captured_poses.append(value.copy()),
            set_joint_position_targets=lambda value: None,
            set_joint_velocities=lambda value: None,
        )
        monkeypatch.setattr(phase, "_generate_fk_targets_impl", fail)
        with pytest.raises(type(exception)):
            await _generate_fk_targets(
                SimpleNamespace(step_one=step), robot, None, np.array([0.3]), np.zeros(3), [-1], [1], set(), 1, 0
            )
        assert np.array_equal(poses[-1], [0.3])


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["prismatic", "unknown", "locked"])
@pytest.mark.parametrize("target_count", [1, 5])
async def test_jik_skips_without_any_qualified_excursion_before_fk_or_solver(monkeypatch, case, target_count):
    from pxr import Usd, UsdGeom, UsdPhysics
    from simready.foundation.tier_core.runtime_tests.articulation_phases import jacobian_ik as phase

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    UsdGeom.Xform.Define(stage, "/Robot/tool")
    if case == "prismatic":
        UsdPhysics.PrismaticJoint.Define(stage, "/Robot/joints/slide")
    finite = case == "locked"
    robot = SimpleNamespace(
        dof_count=1,
        dof_names=["slide"],
        prim_path="/Robot",
        get_joint_position_limits=lambda: ([-1 if finite else -math.inf], [1 if finite else math.inf]),
    )
    context = SimpleNamespace(skip_message=None, metrics={}, warnings=[])
    context.skip = lambda message: setattr(context, "skip_message", message)
    context.add_metric = lambda key, value: context.metrics.__setitem__(key, value)
    context.step = context.log = lambda message: None
    context.warn = context.warnings.append

    async def settled(*args):
        return np.array([0.0])

    def forbidden(*args, **kwargs):
        raise AssertionError("no solver or FK probe is permitted for home-only coverage")

    monkeypatch.setattr(phase, "is_standalone_gripper", lambda *args: False)
    monkeypatch.setattr(phase, "discover_end_effector_link", lambda **kwargs: "/Robot/tool")
    monkeypatch.setattr(phase, "resolve_live_end_effector_link", lambda *args: "/Robot/tool")
    monkeypatch.setattr(phase, "_settle_and_snapshot", settled)
    monkeypatch.setattr(phase, "JacobianIKSolver", forbidden)
    monkeypatch.setattr(phase, "_generate_fk_targets", forbidden)
    await run_jacobian_ik(
        context,
        robot,
        {"stage": stage, "asset_prim": root, "loop_joint_indices": [0] if finite else []},
        {"num_targets": target_count},
    )
    assert "insufficient coverage" in context.skip_message
    assert context.metrics["jik_sampled_joint_count"] == 0
    if case != "locked":
        assert len(context.warnings) == 1 and "at home for FK target samples" in context.warnings[0]


def test_sampling_eligibility_matches_real_bounded_and_unbounded_angular_policy():
    assert _sampling_joint_indices([0, 0, 0], [-math.inf, -1, -1], [math.inf, 1, 1], {2}, {0}) == {0, 1}


@pytest.mark.asyncio
async def test_jik_skips_standalone_grippers_before_solver_setup():
    ctx = SimpleNamespace(skip_message=None, add_metric=lambda name, value: None)
    ctx.skip = lambda message: setattr(ctx, "skip_message", message)
    await run_jacobian_ik(ctx, robot=object(), scene_info={"robot_type": RobotType.GRIPPER}, config={})
    assert "not applicable to standalone grippers" in ctx.skip_message


@pytest.mark.asyncio
async def test_jik_skips_mimic_gripper_even_when_asset_is_mistagged_as_arm():
    ctx = SimpleNamespace(skip_message=None, add_metric=lambda name, value: None)
    ctx.skip = lambda message: setattr(ctx, "skip_message", message)
    robot = SimpleNamespace(dof_count=6)
    scene_info = {"robot_type": RobotType.ARM, "has_gripper_signals": True, "mimic_follower_indices": [1, 2, 3, 4, 5]}
    await run_jacobian_ik(ctx, robot=robot, scene_info=scene_info, config={})
    assert "not applicable to standalone grippers" in ctx.skip_message


def test_arm_with_attached_gripper_remains_jik_applicable():
    robot = SimpleNamespace(dof_count=7)
    scene_info = {"robot_type": RobotType.ARM, "has_gripper_signals": True, "mimic_follower_indices": [6]}
    assert not is_standalone_gripper(robot, scene_info)


def test_resolve_motion_timing_preserves_physx_defaults_and_overrides():
    defaults = get_defaults()
    assert resolve_motion_timing(defaults) == (0.67, 0.3)
    defaults.update(interpolation_seconds=0.8, hold_after_reach_seconds=0.4)
    assert resolve_motion_timing(defaults) == (0.8, 0.4)


def test_validated_gripper_receipts_do_not_hide_an_independent_arm_chain():
    robot = SimpleNamespace(dof_count=7)
    scene_info = {"robot_type": RobotType.ARM, "has_gripper_signals": False}
    assert not is_standalone_gripper(
        robot, scene_info, ["FET022_DrivenJoints.PhysX.0-2-0", "FET028_Gripper.Isaac.0-1-0"]
    )
    assert not is_standalone_gripper(robot, scene_info, ["FET_022_PHYSX", "FET_028_ISAAC"])
    assert not is_standalone_gripper(
        robot, scene_info, ["FET022_DrivenJointsOther.PhysX.0-2-0", "FET028_Gripper.Isaac.0-1-0"]
    )


def test_distinct_reachable_positions_rejects_collapsed_fk_targets():
    targets = [
        IKTarget(position=[0.0, 0.0, 0.0], is_reachable=True, index=0),
        IKTarget(position=[0.0, 0.0, 0.0], is_reachable=True, index=1),
        IKTarget(position=[1.0, 0.0, 0.0], is_reachable=False, index=2),
    ]
    assert count_distinct_reachable_positions(targets) == 1


def test_distinct_reachable_positions_counts_actual_travel():
    targets = [
        IKTarget(position=[0.0, 0.0, 0.0], is_reachable=True, index=0),
        IKTarget(position=[0.2, 0.0, 0.0], is_reachable=True, index=1),
        IKTarget(position=[0.0, 0.3, 0.0], is_reachable=True, index=2),
    ]
    assert count_distinct_reachable_positions(targets) == 3


class _PhysicsLinkRobot:
    def __init__(self, live_paths):
        self.live_paths = set(live_paths)

    def get_link_world_transforms(self, paths):
        path = paths[0]
        if path not in self.live_paths:
            return {}
        return {path: ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])}


def test_resolve_live_end_effector_link_uses_nearest_physics_ancestor():
    robot = _PhysicsLinkRobot({"/World/robot/wrist_3_link"})
    assert resolve_live_end_effector_link(robot, "/World/robot/wrist_3_link/flange") == "/World/robot/wrist_3_link"


def test_resolve_live_end_effector_link_fails_when_no_ancestor_is_live():
    assert resolve_live_end_effector_link(_PhysicsLinkRobot(set()), "/World/robot/tool") is None


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_get_defaults_shape():
    d = get_defaults()
    # Tuned post-Fanuc smoke 2026-04-27. See jacobian_ik.get_defaults docstring.
    assert d["settle_seconds"] == 1.0
    assert d["num_targets"] == 5
    assert d["out_of_reach_count"] == 2
    assert d["target_radius_factors"] == (0.5, 0.7, 0.9)
    assert d["out_of_reach_factor"] == 1.5
    assert d["position_tolerance"] == 0.05
    assert d["orientation_tolerance_deg"] == 10.0
    assert d["max_solver_iterations"] == 150
    assert d["damping_lambda"] == 0.05
    assert d["finite_difference_epsilon"] == 1.0e-5
    assert d["jacobian_propagation_steps"] == 1
    assert not any(key.startswith("newton_") for key in d)
    assert abs(d["interpolation_seconds"] - 0.67) < 1e-9
    assert d["hold_after_reach_seconds"] == 0.3
    assert d["min_pass_rate"] == 0.40
    assert d["interpolation_profile"] == "smoothstep"
    assert d["physics_fps"] == 240.0
    assert d["show_target_spheres"] is True
    assert d["capture_fps"] == 15


# ---------------------------------------------------------------------------
# Pass-rate
# ---------------------------------------------------------------------------


def test_compute_pass_rate():
    assert compute_pass_rate(0, 0) == 0.0
    assert compute_pass_rate(0, 4) == 0.0
    assert compute_pass_rate(2, 4) == 0.5
    assert compute_pass_rate(4, 4) == 1.0
    # Negative total should also degrade gracefully to 0.
    assert compute_pass_rate(2, -1) == 0.0


# ---------------------------------------------------------------------------
# Smoothstep / interpolation
# ---------------------------------------------------------------------------


def test_smoothstep_endpoints():
    assert smoothstep(0.0) == 0.0
    assert smoothstep(1.0) == 1.0
    # Symmetric midpoint
    assert abs(smoothstep(0.5) - 0.5) < 1e-9


def test_smoothstep_clamps_outside_unit_interval():
    assert smoothstep(-0.5) == 0.0
    assert smoothstep(1.5) == 1.0


def test_interpolate_profile_smoothstep_matches_smoothstep():
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert abs(interpolate_profile("smoothstep", t) - smoothstep(t)) < 1e-9


def test_interpolate_profile_unknown_falls_back_to_linear():
    assert abs(interpolate_profile("not_a_profile", 0.4) - 0.4) < 1e-9


def test_interpolate_profile_smootherstep_endpoints():
    assert interpolate_profile("smootherstep", 0.0) == 0.0
    assert interpolate_profile("smootherstep", 1.0) == 1.0


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------


def _result(idx, reachable, passed, pos_err=0.0, orient_err_deg=0.0):
    return {
        "index": idx,
        "name": "target_%d" % idx,
        "is_reachable": reachable,
        "passed": passed,
        "pos_err": pos_err,
        "orient_err_deg": orient_err_deg,
    }


def test_aggregate_jik_summary_all_pass():
    results = [
        _result(0, True, True, pos_err=0.005, orient_err_deg=1.0),
        _result(1, True, True, pos_err=0.010, orient_err_deg=2.0),
        _result(2, False, True, pos_err=0.500, orient_err_deg=10.0),
    ]
    s = aggregate_jik_summary(results)
    assert s["targets_total"] == 3
    assert s["in_reach_total"] == 2
    assert s["in_reach_passed"] == 2
    assert s["in_reach_failed"] == 0
    assert s["out_of_reach_total"] == 1
    assert s["out_of_reach_correct"] == 1
    assert s["pass_rate"] == 1.0
    assert s["failure_names"] == []
    assert abs(s["max_position_error_m"] - 0.5) < 1e-9
    assert abs(s["max_orientation_error_deg"] - 10.0) < 1e-9


def test_aggregate_jik_summary_mixed():
    results = [
        _result(0, True, True, pos_err=0.005, orient_err_deg=1.0),
        _result(1, True, False, pos_err=0.080, orient_err_deg=8.0),
        _result(2, True, True, pos_err=0.015, orient_err_deg=3.0),
        _result(3, False, True, pos_err=0.500, orient_err_deg=12.0),
        _result(4, False, False, pos_err=0.030, orient_err_deg=4.0),
    ]
    s = aggregate_jik_summary(results)
    assert s["targets_total"] == 5
    assert s["in_reach_total"] == 3
    assert s["in_reach_passed"] == 2
    assert s["in_reach_failed"] == 1
    assert s["out_of_reach_total"] == 2
    assert s["out_of_reach_correct"] == 1
    assert abs(s["pass_rate"] - (2.0 / 3.0)) < 1e-9
    assert s["failure_names"] == ["target_1"]
    assert abs(s["max_position_error_m"] - 0.5) < 1e-9
    assert abs(s["max_orientation_error_deg"] - 12.0) < 1e-9


def test_aggregate_jik_summary_empty():
    s = aggregate_jik_summary([])
    assert s["targets_total"] == 0
    assert s["in_reach_total"] == 0
    assert s["pass_rate"] == 0.0
    assert s["failure_names"] == []
    assert s["max_live_playback_position_error_m"] is None
    assert s["live_playback_targets_observed"] == 0


def test_solver_rejection_residual_is_not_live_playback_error():
    played = dict(_result(0, True, True, pos_err=0.01), playback_position_error_m=0.01)
    rejected = dict(_result(1, False, True, pos_err=10.0), playback_position_error_m=None)
    summary = aggregate_jik_summary([played, rejected])
    assert summary["max_position_error_m"] == 10.0  # Backward-compatible, explicitly mixed basis.
    assert summary["max_live_playback_position_error_m"] == 0.01
    assert summary["live_playback_targets_observed"] == 1
    assert summary["position_error_basis"] == "mixed_solver_or_live_playback_residual"


def test_aggregate_jik_summary_only_out_of_reach():
    results = [
        _result(0, False, True, pos_err=0.5),
        _result(1, False, False, pos_err=0.4),
    ]
    s = aggregate_jik_summary(results)
    # No in-reach targets means pass_rate is 0.0 and there are no
    # failure names (failures only count for in-reach targets).
    assert s["in_reach_total"] == 0
    assert s["out_of_reach_total"] == 2
    assert s["out_of_reach_correct"] == 1
    assert s["pass_rate"] == 0.0
    assert s["failure_names"] == []

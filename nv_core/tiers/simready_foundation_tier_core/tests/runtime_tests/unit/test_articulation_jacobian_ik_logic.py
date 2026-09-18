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
from types import SimpleNamespace

import pytest
from simready_benchmark_kit_suite.articulation_phases.ik_targets import IKTarget
from simready_benchmark_kit_suite.articulation_phases.jacobian_ik import (
    aggregate_jik_summary,
    compute_pass_rate,
    count_distinct_reachable_positions,
    get_defaults,
    interpolate_profile,
    resolve_engine_motion_timing,
    resolve_live_end_effector_link,
    run_jacobian_ik,
    smoothstep,
)
from simready_benchmark_kit_suite.articulation_phases.robot_type import (
    RobotType,
    is_standalone_gripper,
)


@pytest.mark.asyncio
async def test_jik_skips_standalone_grippers_before_solver_setup():
    ctx = SimpleNamespace(skip_message=None)
    ctx.skip = lambda message: setattr(ctx, "skip_message", message)
    await run_jacobian_ik(ctx, robot=object(), scene_info={"robot_type": RobotType.GRIPPER}, config={})
    assert "not applicable to standalone grippers" in ctx.skip_message


@pytest.mark.asyncio
async def test_jik_skips_mimic_gripper_even_when_asset_is_mistagged_as_arm():
    ctx = SimpleNamespace(skip_message=None)
    ctx.skip = lambda message: setattr(ctx, "skip_message", message)
    robot = SimpleNamespace(dof_count=6)
    scene_info = {"robot_type": RobotType.ARM, "has_gripper_signals": True, "mimic_follower_indices": [1, 2, 3, 4, 5]}
    await run_jacobian_ik(ctx, robot=robot, scene_info=scene_info, config={})
    assert "not applicable to standalone grippers" in ctx.skip_message


def test_arm_with_attached_gripper_remains_jik_applicable():
    robot = SimpleNamespace(dof_count=7)
    scene_info = {"robot_type": RobotType.ARM, "has_gripper_signals": True, "mimic_follower_indices": [6]}
    assert not is_standalone_gripper(robot, scene_info)


def test_resolve_engine_motion_timing_preserves_physx_and_tunes_newton():
    defaults = get_defaults()
    assert resolve_engine_motion_timing(defaults, "isaac_sim") == (0.67, 0.3)
    assert resolve_engine_motion_timing(defaults, "newton") == (1.25, 1.0)


def test_validated_driven_joint_gripper_contract_skips_ik_regardless_of_bad_type():
    robot = SimpleNamespace(dof_count=7)
    scene_info = {"robot_type": RobotType.ARM, "has_gripper_signals": False}
    assert is_standalone_gripper(robot, scene_info, ["FET_022_PHYSX", "FET_028_ISAAC"])


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
    assert d["newton_finite_difference_epsilon"] == 1.0e-3
    assert d["newton_jacobian_propagation_steps"] == 2
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

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

"""Malformed phase settings cannot suppress a verdict or begin excitation."""

import asyncio
import importlib
import math

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    validate_phase_config,
)

PHASE_FIELDS = (
    ("velocity_limit", "tolerance_percent"),
    ("effort_limit", "break_tolerance"),
    ("state_accuracy", "position_tolerance_deg"),
    ("drive_gain_validation", "max_overshoot_pct"),
    ("drive_gain_validation", "settling_tolerance"),
    ("mimic_joint", "gear_ratio_tolerance"),
    ("multi_joint_coordination", "position_tolerance_deg"),
    ("ik_target_reach", "position_tolerance"),
    ("ik_target_reach", "min_success_rate"),
    ("jacobian_ik", "position_tolerance"),
    ("jacobian_ik", "min_pass_rate"),
)
PHASES = tuple(dict.fromkeys(phase for phase, _field in PHASE_FIELDS))
BAD_THRESHOLD = (math.nan, math.inf, -math.inf, -0.1, True, "0.1", None, 10**1000)


def _phase(name):
    return importlib.import_module("simready.foundation.tier_core.runtime_tests.articulation_phases." + name)


class _NoSceneWork:
    def __getattr__(self, name):
        pytest.fail("Invalid configuration reached scene work: " + name)


@pytest.mark.parametrize(("phase", "field"), PHASE_FIELDS)
@pytest.mark.parametrize("value", BAD_THRESHOLD)
def test_raw_verdict_settings_fail_before_phase_scene_work(phase, field, value):
    run = getattr(_phase(phase), "run_" + phase)
    with pytest.raises(ValueError, match=field):
        asyncio.run(run(_NoSceneWork(), _NoSceneWork(), {}, {field: value}))


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize(
    "config",
    (
        {"bbox_explode_ratio": math.nan},
        {"bbox_explode_ratio": math.inf},
        {"bbox_explode_ratio": True},
        {"bbox_explode_ratio": 0.0},
        {"capture_fps": False},
        {"capture_fps": 0},
        {"capture_fps": 3.5},
        {"capture_fps": "30"},
    ),
)
def test_common_phase_guards_precede_discovery_or_skip(phase, config):
    with pytest.raises(ValueError):
        asyncio.run(getattr(_phase(phase), "run_" + phase)(_NoSceneWork(), _NoSceneWork(), {}, config))


@pytest.mark.parametrize(
    ("phase", "config"),
    (
        ("velocity_limit", {"test_duration_seconds": 0}),
        ("effort_limit", {"force_magnitude_newtons": 0}),
        ("state_accuracy", {"step_range_fraction": 0}),
        ("state_accuracy", {"step_range_fraction": 1.1}),
        ("drive_gain_validation", {"step_magnitude_deg": 0}),
        ("drive_gain_validation", {"max_oscillations": 0.5}),
        ("drive_gain_validation", {"step_fatal": "false"}),
        ("mimic_joint", {"sweep_margin_ratio": 0.6}),
        ("mimic_joint", {"sweep_seconds": 0}),
        ("multi_joint_coordination", {"num_iterations": 0}),
        ("multi_joint_coordination", {"num_iterations": 1.5}),
        ("multi_joint_coordination", {"target_factors": []}),
        ("multi_joint_coordination", {"target_factors": [math.nan]}),
        ("multi_joint_coordination", {"target_factors": [True]}),
        ("multi_joint_coordination", {"target_factors": [1.1]}),
        ("ik_target_reach", {"num_reachable_targets": 0}),
        ("ik_target_reach", {"num_out_of_reach_targets": -1}),
        ("ik_target_reach", {"min_success_rate": 1.1}),
        ("ik_target_reach", {"radius_factors": []}),
        ("ik_target_reach", {"radius_factors": ["0.5"]}),
        ("ik_target_reach", {"out_of_reach_factor": 1.0}),
        ("ik_target_reach", {"motion_min_seconds": 2.0}),
        ("jacobian_ik", {"num_targets": 0}),
        ("jacobian_ik", {"max_solver_iterations": 0}),
        ("jacobian_ik", {"jacobian_propagation_steps": 0}),
        ("jacobian_ik", {"finite_difference_epsilon": 0}),
        ("jacobian_ik", {"min_pass_rate": 1.1}),
        ("jacobian_ik", {"target_radius_factors": [math.nan]}),
        ("jacobian_ik", {"target_radius_factors": [True]}),
    ),
)
def test_excitation_counts_and_fraction_domains_are_not_silently_coerced(phase, config):
    with pytest.raises(ValueError):
        asyncio.run(getattr(_phase(phase), "run_" + phase)(_NoSceneWork(), _NoSceneWork(), {}, config))


@pytest.mark.parametrize("phase", PHASES)
def test_shipped_defaults_and_whole_number_counts_remain_valid(phase):
    defaults = _phase(phase).get_defaults()
    validate_phase_config(defaults, phase)
    validate_phase_config({**defaults, "capture_fps": 30.0}, phase)


@pytest.mark.parametrize(("phase", "field"), PHASE_FIELDS)
def test_zero_thresholds_remain_exactness_policies(phase, field):
    validate_phase_config({field: 0.0}, phase)


def test_explicit_diagnostic_policy_and_unowned_settings_are_preserved():
    validate_phase_config({"step_fatal": False, "max_overshoot_pct": 1000.0}, "drive_gain_validation")
    validate_phase_config({"bisection_enabled": False, "stop_on_first_break": False}, "effort_limit")
    validate_phase_config({"unknown_plugin_setting": math.nan}, "velocity_limit")
    # This compatibility key is not applied by FK target generation.
    validate_phase_config({"out_of_reach_factor": math.nan}, "jacobian_ik")
    validate_phase_config({"hemisphere_only": "unused compatibility setting"}, "jacobian_ik")
    validate_phase_config({"target_radius_factor": math.nan}, "jacobian_ik")
    validate_phase_config({"target_radius_factors": []}, "jacobian_ik")
    validate_phase_config({"target_radius_factors": [0.0, 2.0]}, "jacobian_ik")
    validate_phase_config({"target_radius_factors": None, "target_radius_factor": 2.0}, "jacobian_ik")
    validate_phase_config({"num_iterations": 3.0, "target_margin_ratio": 0.5}, "multi_joint_coordination")


@pytest.mark.parametrize("tolerance", BAD_THRESHOLD)
@pytest.mark.parametrize("phase", ("velocity_limit", "effort_limit", "state_accuracy", "drive_gain_validation"))
def test_pure_verdict_helpers_cannot_accept_nonfinite_or_coerced_tolerances(phase, tolerance):
    module = _phase(phase)
    with pytest.raises(ValueError):
        if phase == "velocity_limit":
            module.analyze_velocity_results([100.0], 1.0, tolerance)
        elif phase == "effort_limit":
            module.detect_break_from_positions([10.0], -1.0, 1.0, tolerance, [])
        elif phase == "state_accuracy":
            module.classify_position_error(10.0, 0.0, tolerance)
        else:
            module.compute_settling_time([10.0], [0.0], 0.0, tolerance)


def test_valid_zero_tolerances_still_detect_actual_failures():
    assert _phase("velocity_limit").analyze_velocity_results([100.0], 1.0, 0.0)[0]
    assert _phase("effort_limit").detect_break_from_positions([10.0], -1.0, 1.0, 0.0, [])[0]
    assert not _phase("state_accuracy").classify_position_error(10.0, 0.0, 0.0)[0]
    assert _phase("drive_gain_validation").compute_settling_time([10.0], [0.0], 0.0, 0.0) is None


@pytest.mark.parametrize("phase", ("velocity_limit", "effort_limit"))
def test_derived_verdict_bounds_cannot_overflow_to_infinite_allowances(phase):
    with pytest.raises(ValueError, match="nonfinite"):
        if phase == "velocity_limit":
            _phase(phase).analyze_velocity_results([1e308], 1e308, 1e308)
        else:
            _phase(phase).detect_break_from_positions([1e308], -1.0, 1.0, 1e308, [])

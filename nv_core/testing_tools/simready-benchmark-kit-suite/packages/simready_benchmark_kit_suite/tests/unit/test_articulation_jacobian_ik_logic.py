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
from simready_benchmark_kit_suite.articulation_phases.jacobian_ik import (
    aggregate_jik_summary,
    compute_pass_rate,
    get_defaults,
    interpolate_profile,
    smoothstep,
)

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

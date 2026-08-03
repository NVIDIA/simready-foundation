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
"""Tests for multi_joint_coordination pure helpers."""
from simready_benchmark_kit_suite.articulation_phases.multi_joint_coordination import (
    aggregate_mjc_summary,
    compute_factor_target,
    get_defaults,
)


def test_defaults_shape():
    d = get_defaults()
    assert d["num_iterations"] == 3
    assert d["target_factors"] == [0.3, 0.6, 0.5]
    assert d["position_tolerance_deg"] == 1.0
    assert d["target_margin_ratio"] == 0.10
    assert d["capture_fps"] == 15


def test_compute_factor_target_at_low_factor():
    # range [-1, 1], margin 0.10 -> [-0.8, 0.8], factor 0.0 -> -0.8
    assert abs(compute_factor_target(-1.0, 1.0, 0.10, 0.0) - (-0.8)) < 1e-9


def test_compute_factor_target_at_high_factor():
    assert abs(compute_factor_target(-1.0, 1.0, 0.10, 1.0) - 0.8) < 1e-9


def test_compute_factor_target_midpoint():
    assert abs(compute_factor_target(-1.0, 1.0, 0.10, 0.5) - 0.0) < 1e-9


def test_compute_factor_target_v1_factors():
    # V1 default factors land within [-0.8, 0.8] for symmetric range.
    for f in (0.3, 0.6, 0.5):
        t = compute_factor_target(-1.0, 1.0, 0.10, f)
        assert -0.8 <= t <= 0.8


def test_compute_factor_target_collapses_when_margin_too_large():
    # margin 0.5 across range 1.0 -> span <= 0 -> midpoint
    assert abs(compute_factor_target(0.0, 1.0, 0.5, 0.3) - 0.5) < 1e-9


def test_aggregate_mjc_summary_all_pass():
    per_iter = [
        {"iteration": 0, "ok": True, "converged_count": 6, "errors": []},
        {"iteration": 1, "ok": True, "converged_count": 6, "errors": []},
        {"iteration": 2, "ok": True, "converged_count": 6, "errors": []},
    ]
    s = aggregate_mjc_summary(per_iter)
    assert s["iterations_passed"] == 3
    assert s["iterations_failed"] == 0
    assert s["failed_iterations"] == []


def test_aggregate_mjc_summary_partial():
    per_iter = [
        {"iteration": 0, "ok": True, "converged_count": 6, "errors": []},
        {"iteration": 1, "ok": False, "converged_count": 4, "errors": []},
        {"iteration": 2, "ok": True, "converged_count": 6, "errors": []},
    ]
    s = aggregate_mjc_summary(per_iter)
    assert s["iterations_passed"] == 2
    assert s["iterations_failed"] == 1
    assert s["failed_iterations"] == [1]

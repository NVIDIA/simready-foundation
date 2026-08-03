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
"""Tests for state_accuracy pure helpers."""
import math

from simready_benchmark_kit_suite.articulation_phases.state_accuracy import (
    aggregate_sta_summary,
    classify_position_error,
    compute_test_positions,
    get_defaults,
)


def test_defaults_shape():
    d = get_defaults()
    assert d["position_tolerance_deg"] == 5.0
    assert d["velocity_tolerance_percent"] == 0.20
    assert d["max_step_deg"] == 15.0
    assert d["step_range_fraction"] == 0.10
    assert d["test_duration_seconds"] == 3.0
    assert d["settle_seconds"] == 0.5
    assert d["capture_fps"] == 15


def test_compute_test_positions_returns_5_step_sequence():
    positions = compute_test_positions(-1.0, 1.0)
    assert len(positions) == 5
    assert positions[0] == 0.0
    assert positions[2] == 0.0
    assert positions[4] == 0.0
    assert positions[1] > 0.0
    assert positions[3] < 0.0
    assert abs(positions[1] + positions[3]) < 1e-9


def test_compute_test_positions_caps_step_at_max_deg():
    positions = compute_test_positions(-50.0, 50.0, max_step_deg=15.0, step_range_fraction=0.10)
    step = positions[1]
    assert abs(step - math.radians(15.0)) < 1e-9


def test_compute_test_positions_uses_range_fraction_when_smaller():
    positions = compute_test_positions(-0.1, 0.1, max_step_deg=15.0, step_range_fraction=0.10)
    step = positions[1]
    assert abs(step - 0.02) < 1e-9


def test_compute_test_positions_clamps_pos_a_pos_b_to_authored_limits():
    # v1 parity: pos_a and pos_b are clamped, but center=0 is returned uncapped
    # even when 0 is outside [lo, hi]. PhysX will clamp the commanded target
    # to authored limits at apply-time.
    positions = compute_test_positions(0.5, 1.5, max_step_deg=15.0, step_range_fraction=0.10)
    # pos_a (idx 1) and pos_b (idx 3) clamp inside [lo+0.05, hi-0.05]
    for idx in (1, 3):
        assert 0.5 + 0.05 - 1e-9 <= positions[idx] <= 1.5 - 0.05 + 1e-9
    # center (indices 0, 2, 4) stays at 0.0
    assert positions[0] == 0.0 and positions[2] == 0.0 and positions[4] == 0.0


def test_classify_position_error_passes_within_tolerance():
    ok, reason, err = classify_position_error(
        reported_pos=0.10,
        target=0.12,
        tolerance_rad=math.radians(5.0),
    )
    assert ok is True
    assert reason is None
    assert abs(err - 0.02) < 1e-9


def test_classify_position_error_fails_above_tolerance():
    ok, reason, err = classify_position_error(
        reported_pos=0.0,
        target=math.radians(10.0),
        tolerance_rad=math.radians(5.0),
    )
    assert ok is False
    assert "deg" in reason
    assert err > math.radians(5.0)


def test_classify_position_error_fails_on_nonfinite():
    ok, reason, err = classify_position_error(
        reported_pos=float("nan"),
        target=0.0,
        tolerance_rad=0.1,
    )
    assert ok is False
    assert "finite" in reason
    assert err == float("inf")


def test_aggregate_sta_summary_counts_and_extremes():
    per_joint = [
        {"name": "j0", "ok": True, "max_position_error_rad": 0.01},
        {"name": "j1", "ok": False, "max_position_error_rad": math.radians(8.0)},
        {"name": "j2", "ok": True, "max_position_error_rad": 0.005},
    ]
    s = aggregate_sta_summary(per_joint)
    assert s["joints_tested"] == 3
    assert s["joints_passed"] == 2
    assert s["joints_failed"] == 1
    assert abs(s["max_position_error_deg"] - 8.0) < 1e-6
    assert s["failure_names"] == ["j1"]

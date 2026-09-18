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
"""Tests for effort_limit pure helpers."""
from simready_benchmark_kit_suite.articulation_phases.effort_limit import (
    aggregate_eff_summary,
    detect_break_from_positions,
    get_defaults,
)


def test_defaults_shape():
    d = get_defaults()
    # v1.6 parity: test_duration_seconds is the TOTAL budget across all 12
    # directions (frames_per_direction = total // 12), NOT per-direction.
    assert d["force_magnitude_newtons"] == 10.0
    assert d["test_duration_seconds"] == 2.0
    assert d["settle_seconds"] == 0.3
    assert d["capture_fps"] == 8
    assert d["stop_on_first_break"] is True
    assert d["bisection_max_iterations"] == 6


def test_detect_break_from_positions_within_limits():
    positions = [0.0, 0.1, 0.2, 0.3]
    broke, reason = detect_break_from_positions(
        positions,
        authored_lo=-1.0,
        authored_hi=1.0,
        break_tolerance=0.1,
        bbox_msgs=[],
    )
    assert broke is False
    assert reason == ""


def test_detect_break_from_positions_exceeds_upper_by_tolerance():
    # range = 2.0, tolerance*range = 0.2 -> break threshold = 1.2
    positions = [0.5, 1.0, 1.25, 1.4]
    broke, reason = detect_break_from_positions(
        positions,
        authored_lo=-1.0,
        authored_hi=1.0,
        break_tolerance=0.1,
        bbox_msgs=[],
    )
    assert broke is True
    assert "upper" in reason.lower()


def test_detect_break_from_positions_bbox_wins():
    positions = [0.0, 0.1]
    broke, reason = detect_break_from_positions(
        positions,
        authored_lo=-1.0,
        authored_hi=1.0,
        break_tolerance=0.1,
        bbox_msgs=["bbox explode detected"],
    )
    assert broke is True
    assert "bbox" in reason.lower()


def test_aggregate_eff_summary_all_pass():
    per_joint = [
        {"name": "j0", "broke_directions": [], "min_break_force_newtons": None, "ok": True},
        {"name": "j1", "broke_directions": [], "min_break_force_newtons": None, "ok": True},
    ]
    s = aggregate_eff_summary(per_joint)
    assert s["joints_tested"] == 2
    assert s["joints_passed"] == 2
    assert s["failure_names"] == []


def test_aggregate_eff_summary_mixed():
    per_joint = [
        {"name": "j0", "broke_directions": [], "min_break_force_newtons": None, "ok": True},
        {"name": "j1", "broke_directions": ["+X", "-Z"], "min_break_force_newtons": 240.0, "ok": False},
    ]
    s = aggregate_eff_summary(per_joint)
    assert s["joints_passed"] == 1
    assert s["joints_failed"] == 1
    assert s["failure_names"] == ["j1"]

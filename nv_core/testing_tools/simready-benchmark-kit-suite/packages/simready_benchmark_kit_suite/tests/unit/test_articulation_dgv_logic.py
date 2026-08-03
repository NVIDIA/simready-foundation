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
"""Tests for drive_gain_validation pure step-response helpers."""
import math

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.drive_gain_validation import (
    aggregate_dgv_summary,
    compute_overshoot,
    compute_settling_time,
    count_oscillations,
    get_defaults,
)


def test_defaults_shape():
    d = get_defaults()
    # v1.6 parity: 30 deg step, 5 s settling, 50% overshoot, 20 oscillations.
    assert d["step_magnitude_deg"] == 30.0
    assert d["max_overshoot_pct"] == 50.0
    assert d["max_settling_seconds"] == 5.0
    assert d["max_oscillations"] == 20
    assert d["settling_tolerance"] == 0.05
    assert d["step_fatal"] is False


def test_compute_overshoot_critically_damped_is_zero():
    # Positions that rise smoothly to target with no overshoot.
    positions = np.linspace(0.0, 1.0, 200)
    assert compute_overshoot(positions, step_start=0.0, step_target=1.0) < 1e-6


def test_compute_overshoot_underdamped_positive():
    # Synthetic damped oscillation around target = 1.0 with a 15% overshoot.
    t = np.linspace(0.0, 2.0, 400)
    positions = 1.0 + 0.15 * np.exp(-2.0 * t) * np.cos(6.0 * t)
    # Excursion above 1.0 of ~0.15; magnitude of step = 1.0.
    val = compute_overshoot(positions, step_start=0.0, step_target=1.0)
    assert 0.10 < val < 0.25


def test_compute_overshoot_zero_when_never_reaches_target():
    positions = np.linspace(0.0, 0.5, 100)
    # Underhead, never exceeds target.
    assert compute_overshoot(positions, step_start=0.0, step_target=1.0) == 0.0


def test_compute_settling_time_enters_and_stays_in_band():
    # Positions that enter settle_band=0.05 at frame 50 and stay.
    positions = np.concatenate([np.linspace(0.0, 0.9, 50), np.full(150, 1.0)])
    times = np.linspace(0.0, 2.0, 200)
    t_settle = compute_settling_time(positions, times, step_target=1.0, settle_band=0.05)
    assert t_settle is not None
    # frame 50 maps to t ~= 0.5
    assert 0.45 <= t_settle <= 0.55


def test_compute_settling_time_none_when_never_settles():
    positions = np.sin(np.linspace(0.0, 10.0, 300))  # never stops oscillating
    times = np.linspace(0.0, 3.0, 300)
    assert compute_settling_time(positions, times, step_target=0.0, settle_band=0.05) is None


def test_count_oscillations_zero_on_monotonic_trajectory():
    velocities = np.linspace(0.1, 0.0, 100)
    assert count_oscillations(velocities) == 0


def test_count_oscillations_counts_zero_crossings():
    # 3 full oscillations (6 zero crossings of velocity).
    t = np.linspace(0.0, 3.0, 600)
    velocities = np.sin(2.0 * math.pi * t)
    count = count_oscillations(velocities)
    assert 4 <= count <= 8  # zero crossings depend on sample boundary handling


def test_aggregate_dgv_summary():
    per_joint = [
        {"name": "j0", "overshoot_pct": 10.0, "settling_time": 0.5, "oscillations": 1, "ok": True},
        {
            "name": "j1",
            "overshoot_pct": 35.0,
            "settling_time": 3.0,
            "oscillations": 6,
            "ok": False,
            "reason": "overshoot 35 > 20, settle 3.0 > 2.0",
        },
    ]
    s = aggregate_dgv_summary(per_joint)
    assert s["joints_tested"] == 2
    assert s["joints_passed"] == 1
    assert s["joints_failed"] == 1
    assert s["failure_names"] == ["j1"]

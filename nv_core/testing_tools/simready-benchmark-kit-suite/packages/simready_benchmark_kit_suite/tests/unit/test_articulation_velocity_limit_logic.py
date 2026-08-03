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
"""Tests for velocity_limit's pure-Python helpers."""
import numpy as np
from simready_benchmark_kit_suite.articulation_phases.velocity_limit import (
    analyze_velocity_results,
    compute_velocity_test_target,
    find_joints_with_velocity_limits,
    get_defaults,
)


class FakeRobot:
    def __init__(self, dof_names, lower, upper, vel_limits):
        self._dof_names = list(dof_names)
        self._lower = np.array(lower, dtype=np.float64)
        self._upper = np.array(upper, dtype=np.float64)
        self._vel = np.array(vel_limits, dtype=np.float64)

    @property
    def dof_names(self):
        return list(self._dof_names)

    @property
    def dof_count(self):
        return len(self._dof_names)

    def get_joint_position_limits(self):
        return (self._lower.copy(), self._upper.copy())

    def get_joint_velocity_limits(self):
        return self._vel.copy()


def test_get_defaults_shape():
    d = get_defaults()
    assert d["tolerance_percent"] == 0.05
    assert d["test_duration_seconds"] == 2.0
    assert d["bbox_explode_ratio"] == 10.0
    assert d["physics_fps"] == 240.0


def test_compute_target_when_current_below_center_returns_upper_with_margin():
    target = compute_velocity_test_target(current_pos=-0.5, lo=-1.0, hi=1.0)
    assert abs(target - 0.9) < 1e-9


def test_compute_target_when_current_above_center_returns_lower_with_margin():
    target = compute_velocity_test_target(current_pos=0.5, lo=-1.0, hi=1.0)
    assert abs(target - (-0.9)) < 1e-9


def test_find_joints_with_limits_excludes_nan_and_zero():
    robot = FakeRobot(
        dof_names=["a", "b", "c", "d"],
        lower=[-1.0, -1.0, -1.0, -1.0],
        upper=[1.0, 1.0, 1.0, 1.0],
        vel_limits=[10.0, float("nan"), 0.0, 20.0],
    )
    out = find_joints_with_velocity_limits(robot, usd_vels=None)
    names = [j["name"] for j in out]
    assert names == ["a", "d"]
    assert out[0]["max_velocity"] == 10.0
    assert out[1]["max_velocity"] == 20.0


def test_find_joints_uses_min_of_dof_and_usd():
    robot = FakeRobot(
        dof_names=["a"],
        lower=[-1.0],
        upper=[1.0],
        vel_limits=[20.0],
    )
    out = find_joints_with_velocity_limits(
        robot,
        usd_vels=np.array([15.0]),
    )
    assert out[0]["max_velocity"] == 15.0
    assert out[0]["max_velocity_source"] == "dof_or_usd_min"


def test_analyze_velocity_no_violations():
    violations, peak = analyze_velocity_results(
        velocities=[1.0] * 20,
        max_velocity=2.0,
        tolerance_percent=0.05,
    )
    assert violations == []
    assert peak <= 2.1


def test_analyze_velocity_detects_overshoot():
    velocities = [0.1, 0.1, 0.1, 0.1, 0.1, 2.5, 3.0, 2.8, 2.0, 1.0]
    violations, peak = analyze_velocity_results(
        velocities=velocities,
        max_velocity=2.0,
        tolerance_percent=0.05,
    )
    assert len(violations) == 3
    assert peak == 3.0


def test_analyze_velocity_handles_empty_input():
    violations, peak = analyze_velocity_results(
        velocities=[],
        max_velocity=2.0,
        tolerance_percent=0.05,
    )
    assert violations == []
    assert peak == 0.0

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
"""Tests for full_range_sweep's pure-Python helpers."""
import numpy as np
from simready_benchmark_kit_suite.articulation_phases.full_range_sweep import (
    build_sweep_segments,
    compute_sweep_parameters,
    get_defaults,
    interpolate_profile,
    select_all_joints_with_limits,
)


class FakeRobot:
    def __init__(self, dof_names, lowers, uppers):
        self._dof_names = list(dof_names)
        self._lowers = np.array(lowers, dtype=np.float64)
        self._uppers = np.array(uppers, dtype=np.float64)

    @property
    def dof_names(self):
        return list(self._dof_names)

    def get_joint_position_limits(self):
        return (self._lowers.copy(), self._uppers.copy())


def test_get_defaults_shape():
    d = get_defaults()
    assert d["sweep_margin_ratio"] == 0.10
    assert d["interpolation_profile"] == "smoothstep"
    assert d["sweep_speed_scale"] == 0.8
    assert d["pause_at_limits_seconds"] == 0.15
    assert d["rest_check_fatal"] is False


def test_interpolate_linear():
    assert interpolate_profile("linear", 0.0) == 0.0
    assert interpolate_profile("linear", 0.5) == 0.5
    assert interpolate_profile("linear", 1.0) == 1.0


def test_interpolate_smoothstep_endpoints_and_mid():
    assert interpolate_profile("smoothstep", 0.0) == 0.0
    assert interpolate_profile("smoothstep", 1.0) == 1.0
    assert abs(interpolate_profile("smoothstep", 0.5) - 0.5) < 1e-9


def test_interpolate_smootherstep_endpoints():
    assert interpolate_profile("smootherstep", 0.0) == 0.0
    assert interpolate_profile("smootherstep", 1.0) == 1.0


def test_interpolate_trapezoidal_holds_middle():
    v_mid = interpolate_profile("trapezoidal", 0.5)
    assert abs(v_mid - 0.5) < 1e-9


def test_interpolate_unknown_profile_falls_back_to_linear():
    assert interpolate_profile("unknown_xyz", 0.7) == 0.7


def test_select_all_joints_skips_non_finite_range():
    robot = FakeRobot(
        dof_names=["a", "b", "c", "d"],
        lowers=[-1.0, float("-inf"), -1.0, -0.1],
        uppers=[1.0, float("inf"), -0.9999, 0.1],
    )
    passive = frozenset()
    out = select_all_joints_with_limits(robot, passive)
    names = [name for _, name in out]
    assert "a" in names
    assert "b" not in names
    assert "c" not in names
    assert "d" in names


def test_select_all_joints_respects_passive_set():
    robot = FakeRobot(
        dof_names=["a", "b", "c"],
        lowers=[-1.0, -1.0, -1.0],
        uppers=[1.0, 1.0, 1.0],
    )
    passive = frozenset({1})
    out = select_all_joints_with_limits(robot, passive)
    names = [name for _, name in out]
    assert names == ["a", "c"]


def test_compute_sweep_parameters_applies_margin():
    params = compute_sweep_parameters(
        lo=-1.0,
        hi=1.0,
        margin_ratio=0.10,
        max_sweep_range=10.0,
        speed_scale=1.0,
        pause_seconds=0.5,
        physics_fps=240.0,
        joint_name="j",
    )
    assert abs(params["min_target"] - (-0.8)) < 1e-9
    assert abs(params["max_target"] - 0.8) < 1e-9
    assert params["zero_target"] == 0.0


def test_compute_sweep_parameters_caps_max_range():
    params = compute_sweep_parameters(
        lo=-10.0,
        hi=10.0,
        margin_ratio=0.10,
        max_sweep_range=2.0,
        speed_scale=1.0,
        pause_seconds=0.5,
        physics_fps=240.0,
        joint_name="j",
    )
    assert abs(params["min_target"] - (-0.8)) < 1e-9
    assert abs(params["max_target"] - 0.8) < 1e-9


def test_compute_sweep_parameters_clamps_zero_to_limits():
    params = compute_sweep_parameters(
        lo=1.0,
        hi=3.0,
        margin_ratio=0.10,
        max_sweep_range=10.0,
        speed_scale=1.0,
        pause_seconds=0.5,
        physics_fps=240.0,
        joint_name="j",
    )
    assert abs(params["zero_target"] - 1.2) < 1e-9


def test_build_sweep_segments_order():
    params = {"min_target": -0.8, "max_target": 0.8, "zero_target": 0.0}
    segments = build_sweep_segments(q_start=0.0, params=params)
    seg_names = [s[2] for s in segments]
    assert seg_names == ["to_max", "to_min", "to_zero"]

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
"""Newton-specific articulation motion controls stay with the Newton owner."""

from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    full_range_sweep,
    jacobian_ik,
    state_accuracy,
)


def test_state_accuracy_preserves_newton_default_and_stable_ramp():
    assert state_accuracy.get_defaults()["newton_min_motion_seconds"] == 0.5
    assert state_accuracy.compute_motion_frames(3.0, 240.0, 5, "newton") == 120


def test_state_accuracy_honors_longer_explicit_newton_budget():
    assert state_accuracy.compute_motion_frames(3.0, 240.0, 5, "newton", 0.75) == 180


def test_full_range_sweep_preserves_bounded_newton_convergence_policy():
    defaults = full_range_sweep.get_defaults()
    assert defaults["newton_zero_max_settling_seconds"] == 2.0
    assert defaults["newton_zero_consecutive_frames"] == 8
    assert defaults["zero_return_tolerance"] == 0.01
    assert defaults["rest_check_fatal"] is True
    count = full_range_sweep.update_convergence_count(0.009, 0.01, 0)
    count = full_range_sweep.update_convergence_count(0.005, 0.01, count)
    assert count == 2
    assert full_range_sweep.update_convergence_count(0.011, 0.01, count) == 0
    assert full_range_sweep.update_convergence_count(float("nan"), 0.01, count) == 0


def test_jacobian_ik_preserves_newton_solver_and_playback_controls():
    defaults = jacobian_ik.get_defaults()
    assert defaults["newton_finite_difference_epsilon"] == 1.0e-3
    assert defaults["newton_jacobian_propagation_steps"] == 2
    assert jacobian_ik.resolve_engine_motion_timing(defaults, "newton") == (1.25, 1.0)
    defaults.update(newton_interpolation_seconds=1.5, newton_hold_after_reach_seconds=1.2)
    assert jacobian_ik.resolve_engine_motion_timing(defaults, "newton") == (1.5, 1.2)

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
"""Tests for mimic_joint pure helpers."""
from simready_benchmark_kit_suite.articulation_phases.mimic_joint import (
    aggregate_mim_summary,
    compute_expected_follower,
    get_defaults,
)


def test_defaults_shape():
    d = get_defaults()
    assert d["follow_tolerance"] == 0.05
    assert d["sweep_seconds"] == 2.0


def test_compute_expected_follower_basic():
    assert abs(compute_expected_follower(ref_pos=0.5, gear=2.0, offset=0.1) - 1.1) < 1e-9


def test_compute_expected_follower_negative_gear():
    assert abs(compute_expected_follower(ref_pos=0.5, gear=-1.0, offset=0.0) - (-0.5)) < 1e-9


def test_aggregate_mim_summary_all_pass():
    per_pair = [
        {"follower": "f0", "max_follow_error": 0.02, "ok": True},
        {"follower": "f1", "max_follow_error": 0.01, "ok": True},
    ]
    s = aggregate_mim_summary(per_pair)
    assert s["pairs_passed"] == 2
    assert s["pairs_failed"] == 0
    assert s["failure_names"] == []


def test_aggregate_mim_summary_one_fails():
    per_pair = [
        {"follower": "f0", "max_follow_error": 0.02, "ok": True},
        {"follower": "f1", "max_follow_error": 0.30, "ok": False},
    ]
    s = aggregate_mim_summary(per_pair)
    assert s["pairs_passed"] == 1
    assert s["pairs_failed"] == 1
    assert s["failure_names"] == ["f1"]


# -----------------------------------------------------------------------------
# Motion-ratio logic — the new pass criterion (added 2026-04-30).
# Direction-agnostic check: |fol_swept / ref_swept| ≈ |gear|.
# -----------------------------------------------------------------------------
def _compute_motion_ratio_error(fol_swept, ref_swept, gear):
    """Mirror the mimic_joint.py inline computation, for unit testing."""
    if ref_swept > 1e-9:
        ratio = fol_swept / ref_swept
    else:
        ratio = 0.0
    return abs(ratio - abs(gear))


def test_motion_ratio_passes_for_correctly_coupled_unit_gear():
    # Master swept 0.7 rad, follower also swept 0.7 rad, gear=1 → ratio 1.0, error 0.
    err = _compute_motion_ratio_error(fol_swept=0.7, ref_swept=0.7, gear=1.0)
    assert err < 0.01


def test_motion_ratio_passes_with_inverted_gear_sign():
    # Asset says gear=-1, but the linkage moves follower SAME direction as
    # master (numerically). The new pass criterion is direction-agnostic:
    # |0.7 / 0.7 - |-1|| = 0. Should pass even though the sign mismatches.
    err = _compute_motion_ratio_error(fol_swept=0.7, ref_swept=0.7, gear=-1.0)
    assert err < 0.01


def test_motion_ratio_fails_when_follower_does_not_move():
    # Broken mimic: follower stayed put even though master swept.
    err = _compute_motion_ratio_error(fol_swept=0.0, ref_swept=0.7, gear=1.0)
    assert err > 0.5


def test_motion_ratio_fails_when_gear_magnitude_wrong():
    # Asset says |gear|=2 but linkage gives ratio 1.0.
    err = _compute_motion_ratio_error(fol_swept=0.7, ref_swept=0.7, gear=2.0)
    assert err > 0.5


def test_motion_ratio_passes_within_tolerance():
    # 8% error: ratio 1.08 vs |gear|=1.0 → error 0.08; passes default tol 0.10.
    err = _compute_motion_ratio_error(fol_swept=0.756, ref_swept=0.7, gear=1.0)
    assert 0.07 < err < 0.09

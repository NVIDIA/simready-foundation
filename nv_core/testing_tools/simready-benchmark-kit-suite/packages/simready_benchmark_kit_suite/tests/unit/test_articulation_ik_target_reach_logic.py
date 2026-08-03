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
"""Tests for ik_target_reach pure helpers.

The full Kit-side phase needs a stage + articulation + Lula descriptor and
is exercised only by the manual smoke run. These unit tests cover the pure
module-level helpers that ship with the phase: defaults, aggregate
summary, Lula robot-name lookup, EE-candidate lookup.
"""
import math

from simready_benchmark_kit_suite.articulation_phases.ik_target_reach import (
    aggregate_ik_summary,
    default_ee_candidates,
    get_defaults,
    select_lula_robot_name,
)

# --- get_defaults shape ---


def test_get_defaults_shape():
    """All required defaults are present and well-typed."""
    d = get_defaults()
    # JIK-mirroring keys
    assert d["num_reachable_targets"] == 5
    assert d["num_out_of_reach_targets"] == 2
    assert d["radius_factors"] == [0.5, 0.7, 0.9]
    assert d["out_of_reach_factor"] == 1.3
    assert d["hemisphere_only"] is True
    assert d["position_tolerance"] == 0.02
    assert d["orientation_tolerance"] == 0.25
    assert d["min_success_rate"] == 0.5
    assert d["physics_fps"] == 240.0
    assert d["capture_fps"] == 8
    # Lula-specific overrides default to None.
    assert d["lula_robot_name"] is None
    assert d["lula_yaml_path"] is None
    assert d["lula_urdf_path"] is None


def test_get_defaults_returns_fresh_dict():
    """Defaults are not memoized: callers get an independent dict."""
    a = get_defaults()
    a["physics_fps"] = 60.0
    b = get_defaults()
    assert b["physics_fps"] == 240.0


# --- aggregate_ik_summary ---


def test_aggregate_ik_summary_all_pass():
    per_target = [
        {"index": 0, "ok": True, "reachable": True, "pos_error": 0.005},
        {"index": 1, "ok": True, "reachable": True, "pos_error": 0.012},
        {"index": 2, "ok": True, "reachable": True, "pos_error": 0.008},
    ]
    s = aggregate_ik_summary(per_target)
    assert s["targets_total"] == 3
    assert s["targets_reachable"] == 3
    assert s["targets_out_of_reach"] == 0
    assert s["targets_passed"] == 3
    assert s["targets_failed"] == 0
    assert s["in_reach_passed"] == 3
    assert s["in_reach_failed"] == 0
    assert s["failed_indices"] == []
    assert s["pass_rate"] == 1.0
    assert abs(s["max_position_error_m"] - 0.012) < 1e-9


def test_aggregate_ik_summary_mixed():
    """Partial failures + out-of-reach targets contribute correctly."""
    per_target = [
        {"index": 0, "ok": True, "reachable": True, "pos_error": 0.01},
        {"index": 1, "ok": False, "reachable": True, "pos_error": 0.5},
        {"index": 2, "ok": True, "reachable": False, "pos_error": float("inf")},
        {"index": 3, "ok": False, "reachable": False, "pos_error": float("inf")},
        {"index": 4, "ok": True, "reachable": True, "pos_error": 0.015},
    ]
    s = aggregate_ik_summary(per_target)
    assert s["targets_total"] == 5
    assert s["targets_reachable"] == 3
    assert s["targets_out_of_reach"] == 2
    assert s["targets_passed"] == 3
    assert s["targets_failed"] == 2
    assert s["in_reach_passed"] == 2
    assert s["in_reach_failed"] == 1
    assert s["failed_indices"] == [1, 3]
    # max_position_error_m ignores +inf entries.
    assert abs(s["max_position_error_m"] - 0.5) < 1e-9
    # 2 of 3 reachable passed.
    assert abs(s["pass_rate"] - (2.0 / 3.0)) < 1e-9


def test_aggregate_ik_summary_empty():
    s = aggregate_ik_summary([])
    assert s["targets_total"] == 0
    assert s["targets_reachable"] == 0
    assert s["targets_out_of_reach"] == 0
    assert s["targets_passed"] == 0
    assert s["targets_failed"] == 0
    assert s["pass_rate"] == 0.0
    assert s["max_position_error_m"] == 0.0
    assert s["failed_indices"] == []


def test_aggregate_ik_summary_all_unreachable():
    """Out-of-reach-only batch yields 0.0 pass_rate (no in-reach denominator)."""
    per_target = [
        {"index": 0, "ok": True, "reachable": False, "pos_error": float("inf")},
        {"index": 1, "ok": False, "reachable": False, "pos_error": float("inf")},
    ]
    s = aggregate_ik_summary(per_target)
    assert s["targets_reachable"] == 0
    assert s["pass_rate"] == 0.0
    assert s["targets_passed"] == 1
    assert s["targets_failed"] == 1
    # No finite errors -> 0.0
    assert s["max_position_error_m"] == 0.0


def test_aggregate_ik_summary_handles_bad_pos_error():
    """Non-numeric / NaN pos_error values do not crash the helper."""
    per_target = [
        {"index": 0, "ok": True, "reachable": True, "pos_error": float("nan")},
        {"index": 1, "ok": False, "reachable": True, "pos_error": "not-a-number"},
        {"index": 2, "ok": True, "reachable": True, "pos_error": 0.02},
    ]
    s = aggregate_ik_summary(per_target)
    # Only the 0.02 entry is finite -> max_err is 0.02.
    assert math.isfinite(s["max_position_error_m"])
    assert abs(s["max_position_error_m"] - 0.02) < 1e-9


# --- select_lula_robot_name ---


def test_select_lula_robot_name_known_via_asset_name():
    # Asset path containing "Franka" matches the canonical "Franka" entry.
    assert (
        select_lula_robot_name(
            robot_type_name="ARM",
            asset_name="/assets/robots/Franka_Panda/franka.usd",
            override=None,
        )
        == "Franka"
    )


def test_select_lula_robot_name_known_via_robot_type():
    # No asset hit, but the robot type name contains "UR10".
    assert (
        select_lula_robot_name(
            robot_type_name="UR10_arm",
            asset_name="/assets/robots/generic.usd",
            override=None,
        )
        == "UR10"
    )


def test_select_lula_robot_name_override_wins():
    """An explicit override bypasses the lookup table even on a known asset."""
    assert (
        select_lula_robot_name(
            robot_type_name="ARM",
            asset_name="/assets/robots/Franka_Panda/franka.usd",
            override="CustomRobot",
        )
        == "CustomRobot"
    )


def test_select_lula_robot_name_unknown_returns_none():
    assert (
        select_lula_robot_name(
            robot_type_name="SCARA",
            asset_name="/assets/robots/sr12ia.usd",
            override=None,
        )
        is None
    )


def test_select_lula_robot_name_empty_inputs():
    """Empty strings and Nones are tolerated."""
    assert select_lula_robot_name(None, None, None) is None
    assert select_lula_robot_name("", "", "") is None


def test_select_lula_robot_name_case_insensitive():
    """Lowercase asset names still match the canonical capitalized entry."""
    assert (
        select_lula_robot_name(
            robot_type_name=None,
            asset_name="/assets/franka_panda.usd",  # lowercase
            override=None,
        )
        == "Franka"
    )


# --- default_ee_candidates ---


def test_default_ee_candidates():
    """Returns the canonical generic list (same for every robot)."""
    candidates = default_ee_candidates("Franka")
    assert isinstance(candidates, list)
    # Known v1 candidates must be present.
    assert "ee_link" in candidates
    assert "tool0" in candidates
    assert "tcp" in candidates
    assert "flange" in candidates
    assert "panda_hand" in candidates
    # Unknown robots get the same list.
    assert default_ee_candidates("Mystery_Robot_9000") == candidates
    # And a None robot_name still works.
    assert default_ee_candidates(None) == candidates


def test_default_ee_candidates_returns_fresh_list():
    """Caller can mutate the returned list without affecting subsequent calls."""
    a = default_ee_candidates("Franka")
    a.append("custom_ee")
    b = default_ee_candidates("Franka")
    assert "custom_ee" not in b

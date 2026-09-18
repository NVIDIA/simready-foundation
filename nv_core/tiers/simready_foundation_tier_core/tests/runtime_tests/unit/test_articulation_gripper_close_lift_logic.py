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
"""Logic tests for articulation_phases.gripper_close_lift (no Kit required)."""
import math

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
    PassCriterion,
    _authored_hand_frames,
    _classify_hand_endpoint_motion,
    _descent_chunk_count,
    _rotate_vector_xyzw,
    _shape_indices_below_paths,
    _test_scope_skip_unsupported,
    compute_tested_mass,
    evaluate_pass_criterion,
    get_defaults,
    sign_flip_detected,
)


def test_shape_indices_follow_fingertip_paths_not_collider_names():
    labels = [
        "/World/Robot/jaw_alpha/contact_surface_left",
        "/World/Robot/jaw_beta/custom_collision_mesh",
        "/World/Robot/jaw_alpha_aux/not_a_tip_shape",
        "/World/Robot/palm/body_collision",
    ]

    assert _shape_indices_below_paths(
        labels,
        ("/World/Robot/jaw_alpha", "/World/Robot/jaw_beta"),
    ) == {0, 1}


def test_rotate_vector_xyzw_uses_newton_quaternion_order():
    half_sqrt_two = math.sqrt(0.5)
    rotated = _rotate_vector_xyzw((1.0, 0.0, 0.0), (0.0, 0.0, half_sqrt_two, half_sqrt_two))

    assert np.allclose(rotated, (0.0, 1.0, 0.0), atol=1e-7)


def test_descent_chunk_count_bounds_large_approach_steps():
    assert _descent_chunk_count(0.3899, minimum_chunks=12, max_step_m=0.005) == 78
    assert _descent_chunk_count(0.03, minimum_chunks=12, max_step_m=0.005) == 12


def test_authored_hand_frames_derive_palm_from_site_axes():
    local_frame, world_frame = _authored_hand_frames((0.0, 0.0, 2.0), (3.0, 0.0, 0.0))

    assert np.allclose(local_frame[0], (0.0, 0.0, 1.0))
    assert np.allclose(local_frame[1], (1.0, 0.0, 0.0))
    assert np.allclose(local_frame[2], (0.0, 1.0, 0.0))
    assert np.allclose(world_frame[0], (1.0, 0.0, 0.0))
    assert np.allclose(world_frame[1], (0.0, -1.0, 0.0))
    assert np.allclose(world_frame[2], (0.0, 0.0, -1.0))


def test_authored_hand_frames_reject_parallel_site_axes():
    import pytest

    with pytest.raises(ValueError, match="distinct directions"):
        _authored_hand_frames((0.0, 0.0, 1.0), (0.0, 0.0, -2.0))


def test_hand_endpoint_motion_classifies_closure_toward_grasp_center():
    role, endpoint = _classify_hand_endpoint_motion((-0.02, 0.0, -0.05), radial_change=-0.012)

    assert role == "closure"
    assert endpoint == "upper"


def test_hand_endpoint_motion_holds_lateral_positioning_at_upper():
    role, endpoint = _classify_hand_endpoint_motion((-0.01, 0.04, 0.0), radial_change=0.02)

    assert role == "positioning"
    assert endpoint == "upper"


def test_hand_endpoint_motion_holds_non_lateral_positioning_at_lower():
    role, endpoint = _classify_hand_endpoint_motion((-0.01, 0.03, -0.05), radial_change=0.02)

    assert role == "positioning"
    assert endpoint == "lower"


def test_unsupported_message_does_not_claim_centric_or_five_finger_are_unsupported():
    message = _test_scope_skip_unsupported("/World/Robot/gripper_01", "no driven branches")

    assert "Parallel, centric, and independent-finger grippers are supported" in message
    assert "3-jaw centric grippers" not in message
    assert "5-finger humanoid hands" not in message


def test_compute_tested_mass_uses_authored_when_present():
    cfg = get_defaults()
    mass, used_heuristic, max_payload_used = compute_tested_mass(
        max_opening=0.085, max_payload_authored=5.0, config=cfg
    )
    assert math.isclose(mass, 0.85 * 5.0, abs_tol=1e-6)
    assert used_heuristic is False
    assert math.isclose(max_payload_used, 5.0, abs_tol=1e-6)


def test_compute_tested_mass_uses_heuristic_when_authored_missing():
    cfg = get_defaults()
    mass, used_heuristic, max_payload_used = compute_tested_mass(
        max_opening=0.085, max_payload_authored=None, config=cfg
    )
    expected_heuristic = 50.0 * 0.085  # = 4.25
    assert math.isclose(max_payload_used, expected_heuristic, abs_tol=1e-6)
    assert math.isclose(mass, 0.85 * expected_heuristic, abs_tol=1e-6)
    assert used_heuristic is True


def test_compute_tested_mass_override_bypasses_authored_and_heuristic():
    cfg = get_defaults()
    cfg["tested_mass_kg_override"] = 0.1
    mass, used_heuristic, max_payload_used = compute_tested_mass(
        max_opening=0.085, max_payload_authored=5.0, config=cfg
    )
    assert math.isclose(mass, 0.1, abs_tol=1e-9)
    assert used_heuristic is False
    assert math.isclose(max_payload_used, 0.1, abs_tol=1e-9)


def test_compute_tested_mass_override_ignored_when_none_or_zero():
    cfg = get_defaults()
    cfg["tested_mass_kg_override"] = 0.0
    mass, _, _ = compute_tested_mass(max_opening=0.085, max_payload_authored=5.0, config=cfg)
    assert math.isclose(mass, 0.85 * 5.0, abs_tol=1e-6)


def test_compute_tested_mass_clamps_heuristic_floor_and_ceiling():
    cfg = get_defaults()
    _, _, mp = compute_tested_mass(max_opening=0.001, max_payload_authored=None, config=cfg)
    assert math.isclose(mp, 0.1, abs_tol=1e-6)
    _, _, mp = compute_tested_mass(max_opening=2.0, max_payload_authored=None, config=cfg)
    assert math.isclose(mp, 50.0, abs_tol=1e-6)


def test_pass_criterion_succeeds_when_object_follows_carrier():
    cfg = get_defaults()
    result = evaluate_pass_criterion(
        object_pre_close_xy=np.array([0.0, 0.0]),
        object_pre_close_z=0.50,
        object_pre_lift_z=0.50,
        object_post_lift=np.array([0.001, -0.001, 0.701]),
        carrier_pre_lift_z=0.50,
        carrier_post_lift_z=0.70,
        config=cfg,
    )
    assert isinstance(result, PassCriterion)
    assert result.passed is True
    assert result.vertical_follow_dz < cfg["fall_min_delta_z"]
    assert result.horizontal_drift < cfg["horizontal_drift_max"]


def test_pass_criterion_fails_when_object_slips_out_vertically():
    cfg = get_defaults()
    result = evaluate_pass_criterion(
        object_pre_close_xy=np.array([0.0, 0.0]),
        object_pre_close_z=0.50,
        object_pre_lift_z=0.50,
        object_post_lift=np.array([0.0, 0.0, 0.50]),
        carrier_pre_lift_z=0.50,
        carrier_post_lift_z=0.70,
        config=cfg,
    )
    assert result.passed is False
    assert result.vertical_follow_dz >= cfg["fall_min_delta_z"]


def test_pass_criterion_fails_on_horizontal_drift():
    cfg = get_defaults()
    result = evaluate_pass_criterion(
        object_pre_close_xy=np.array([0.0, 0.0]),
        object_pre_close_z=0.50,
        object_pre_lift_z=0.50,
        object_post_lift=np.array([0.10, 0.0, 0.70]),
        carrier_pre_lift_z=0.50,
        carrier_post_lift_z=0.70,
        config=cfg,
    )
    assert result.passed is False
    assert result.horizontal_drift >= cfg["horizontal_drift_max"]


def test_pass_criterion_reports_pre_load_without_rejecting_valid_lift():
    cfg = get_defaults()
    result = evaluate_pass_criterion(
        object_pre_close_xy=np.array([0.0, 0.0]),
        object_pre_close_z=0.50,
        object_pre_lift_z=0.52,  # 2 cm pre-load > 0.01 threshold
        object_post_lift=np.array([0.0, 0.0, 0.72]),
        carrier_pre_lift_z=0.50,
        carrier_post_lift_z=0.70,
        config=cfg,
    )
    assert result.passed is True
    assert result.pre_load_dz >= cfg["pre_load_max_dz"]


def test_sign_flip_not_detected_when_open_succeeded():
    cfg = get_defaults()
    flip = sign_flip_detected(
        commanded_target=0.085,
        measured_separation=0.084,
        max_opening=0.085,
        config=cfg,
    )
    assert flip is False


def test_sign_flip_detected_when_open_command_actually_closed():
    cfg = get_defaults()
    flip = sign_flip_detected(
        commanded_target=0.085,
        measured_separation=0.001,
        max_opening=0.085,
        config=cfg,
    )
    assert flip is True


# ---------------------------------------------------------------------------
# _resolve_gripper_base_path -- prefer ancestors with body descendants over
# the closest body. Catches the "site authored under a finger pad" case
# where the naive resolver would attach the carrier to a finger.
# ---------------------------------------------------------------------------


def _build_gripper_with_layout(site_under: str):
    """Build a stage with /World/Asset/wrist (body) -> finger_left/right (bodies)
    and place the gripper site under either ``wrist`` or ``finger_left``
    depending on ``site_under``."""
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    wrist = UsdGeom.Xform.Define(stage, "/World/Asset/wrist").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(wrist)
    fl = UsdGeom.Xform.Define(stage, "/World/Asset/wrist/finger_left").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(fl)
    fr = UsdGeom.Xform.Define(stage, "/World/Asset/wrist/finger_right").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(fr)
    site_parent = "/World/Asset/wrist" if site_under == "wrist" else "/World/Asset/wrist/finger_left"
    site = UsdGeom.Xform.Define(stage, site_parent + "/gripper_01").GetPrim()
    site.AddAppliedSchema("IsaacSiteAPI")
    return stage, str(site.GetPath())


def test_resolve_gripper_base_picks_wrist_when_site_under_wrist():
    """Conventional authoring -- site under wrist body that has finger
    descendants. Resolver picks wrist."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _resolve_gripper_base_path,
    )

    stage, site_path = _build_gripper_with_layout(site_under="wrist")
    base = _resolve_gripper_base_path(stage, site_path)
    assert base == "/World/Asset/wrist"


def test_resolve_gripper_base_walks_past_finger_to_wrist_when_site_under_finger():
    """Edge case -- site mistakenly authored under a finger pad. Naive
    "first ancestor body" returns the finger; the hardened resolver walks
    past it (finger has no body descendants) to the wrist (which does)."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _resolve_gripper_base_path,
    )

    stage, site_path = _build_gripper_with_layout(site_under="finger_left")
    base = _resolve_gripper_base_path(stage, site_path)
    assert base == "/World/Asset/wrist"


def test_resolve_gripper_base_falls_back_when_no_body_has_descendants():
    """Single-body asset (just a wrist, no fingers as separate bodies). The
    descendant-preference can't fire -- fall back to the closest ancestor
    body so the resolver still returns something usable."""
    from pxr import Usd, UsdGeom, UsdPhysics
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _resolve_gripper_base_path,
    )

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    wrist = UsdGeom.Xform.Define(stage, "/World/Asset/wrist").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(wrist)
    site = UsdGeom.Xform.Define(stage, "/World/Asset/wrist/gripper_01").GetPrim()
    site.AddAppliedSchema("IsaacSiteAPI")
    base = _resolve_gripper_base_path(stage, str(site.GetPath()))
    assert base == "/World/Asset/wrist"


def test_resolve_gripper_base_returns_none_when_no_body_ancestor():
    """Site authored without any RigidBodyAPI ancestor -- malformed asset.
    Resolver returns None; orchestrator escalates to ``precheck_failure``."""
    from pxr import Usd, UsdGeom
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _resolve_gripper_base_path,
    )

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    site = UsdGeom.Xform.Define(stage, "/World/Asset/gripper_01").GetPrim()
    site.AddAppliedSchema("IsaacSiteAPI")
    base = _resolve_gripper_base_path(stage, str(site.GetPath()))
    assert base is None


def test_hand_cup_descent_lowers_fingertip_to_object_reference():
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _hand_cup_descent,
    )

    # Lowest open fingertip is 0.12 m up; sphere centre at 0.03 m; leave 0.005 m gap.
    # Descend so the fingertip stops 0.005 m above the centre: 0.12 - (0.03 + 0.005) = 0.085.
    assert abs(_hand_cup_descent(0.12, 0.03, 0.005) - 0.085) < 1e-9
    # Never returns negative (fingertip already at/below target -> no descent).
    assert _hand_cup_descent(0.02, 0.03, 0.005) == 0.0


def test_contact_inference_excludes_held_positioning_dofs():
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _contact_active_specs,
    )

    specs = [
        {"idx": 0, "open": 0.2, "closed": 0.2, "name": "positioner"},
        {"idx": 1, "open": 0.0, "closed": 1.0, "name": "grasp"},
        {"idx": 2, "open": 0.0, "closed": 1.0, "name": "disabled", "contact_active": False},
    ]

    assert [spec["name"] for spec in _contact_active_specs(specs)] == ["grasp"]


def test_spawn_position_uses_authored_grasp_center_without_offset():
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _authored_spawn_position,
    )

    assert np.array_equal(
        _authored_spawn_position(np.array([0.1, -0.2, 0.9]), 0.03),
        np.array([0.1, -0.2, 0.03]),
    )


def test_retention_distance_is_measured_from_authored_spawn_xy():
    from simready_benchmark_kit_suite.articulation_phases.gripper_close_lift import (
        _lateral_distance,
    )

    assert np.isclose(_lateral_distance([0.13, 0.04, 2.0], [0.1, 0.0, 0.03]), 0.05)

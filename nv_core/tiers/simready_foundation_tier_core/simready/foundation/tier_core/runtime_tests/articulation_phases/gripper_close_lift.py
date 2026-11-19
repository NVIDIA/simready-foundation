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
"""FET028 close-and-lift phase implementation.

Defines the orchestration function ``run_gripper_close_lift`` plus its
pure-logic helpers (config defaults, heuristic, pass criterion, endpoint
mapping). The PhysX-only orchestrator requires Kit and is exercised by the manual
smoke test (Task H); the pure helpers are unit-tested in this task.
"""

import asyncio
import copy
import json
import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Any

import numpy as np
from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_state import (
    validate_selected_native_positions,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.hand_controls import (
    delayed_close_targets,
    effective_trial_controls,
    normalize_hand_trial_controls,
    resolve_hand_trial_specs,
    validate_close_delays,
)

# ----------------------------------------------------------------------
# Shared spec/example reference block used in actionable fix messages.
# Kept in sync with the one in gripper_sites.py so an asset author who
# hits any FET028 message sees the same set of references (spec docs,
# canonical validator, working real-asset example).
# ----------------------------------------------------------------------
_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:      nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_grippers/requirements/\n"
    "  Validator: nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_grippers/validation.py\n"
    "  Example:   sample_content/common_assets/robots_general/Robotiq/"
    "2F-85/simready_usd/2F-85.usda\n"
    '             (search for: def Xform "gripper_01")'
)


# ---------------------------------------------------------------------------
# Test-scope skip messages for topologies with no resolvable position-driven
# finger branches. These skips must not push an author to fabricate a mimic
# relationship or drives that do not match the real mechanism.
# ---------------------------------------------------------------------------


def _test_scope_skip_unsupported(site_prim_path: str, reason: str | None = None) -> str:
    """Skip message for grippers with no resolvable position-driven fingers.

    Triggered when ``discover_fingertips`` returns ``kind="unsupported"``:
    neither a coupled parallel/centric mechanism nor at least two distinct
    driven finger branches can be resolved. Examples include tendon-driven or
    soft grippers that expose no position-driven articulation DOFs.

    ``reason`` is the classifier's diagnostic explaining WHY the parallel-jaw
    branch rejected this asset (DOF list, mimic specs, branch-by-branch
    verdict). Surfacing it here is what lets framework triage tell asset
    issues from classifier bugs and genuine test-scope limitations.
    """
    reason_block = ""
    if reason:
        reason_block = "Classifier diagnostic:\n%s\n\n" % reason
    return (
        "FET028 cannot resolve a position-driven fingertip topology.\n"
        f"  Site that was discovered: {site_prim_path}\n"
        "\n"
        f"{reason_block}"
        "The site is discoverable, but the test found neither a supported\n"
        "coupled mechanism nor two distinct position-driven finger branches.\n"
        "Parallel, centric, and independent-finger grippers are supported when\n"
        "their USD joint graph exposes resolvable driven fingertip motion.\n"
        "\n"
        "Topologies that can legitimately hit this skip include tendon-driven,\n"
        "underactuated, pneumatic, and soft grippers that expose no compatible\n"
        "per-DOF position drive.\n"
        "\n"
        "Do not add fake joints or mimic relationships merely to satisfy this\n"
        "test. If the physical mechanism has position-driven joints, inspect\n"
        "the classifier diagnostic above for missing drives or relationships.\n"
        "\n"
        "If a position-driven gripper is being misclassified, the diagnostic\n"
        "above\n"
        "should tell you which check rejected. That would point at a bug\n"
        "in ``discover_fingertips`` in articulation_phases/fingertip_discovery.py\n"
        "or upstream (e.g. ``detect_mimic_joints``).\n"
        "\n"
        f"{_SPEC_REFERENCE}"
    )


def _fix_message_invalid_max_opening(site_prim_path: str, value: float) -> str:
    """Describe a missing/invalid opening declaration without inventing a rating."""
    return (
        "FET028 cannot run: gripper site has invalid maxOpening.\n"
        f"  Site prim:           {site_prim_path}\n"
        f"  gripper_maxOpening:  {value!r} (must be a positive float in METERS)\n"
        "\n"
        "INSPECT: compare this resolved site with the selected composed variant,\n"
        "static validation evidence and GR.004 (gripper-max-opening). The value\n"
        "declares maximum jaw separation in physical meters, not stage units.\n"
        "If the declaration is missing or incorrect, use the real mechanism's\n"
        "maximum opening; do not invent a width merely to make the test run.\n"
        "\n"
        "ILLUSTRATIVE ATTRIBUTE ONLY (85 mm; not a suggested rating):\n"
        "    custom float gripper_maxOpening = 0.085\n"
        "\n"
        "This message alone does not establish that validation was bypassed:\n"
        "stale evidence, a different selected variant, or a runtime/setup mismatch\n"
        "can also explain the discrepancy. Preserve the original evidence.\n"
        "\n"
        f"{_SPEC_REFERENCE}"
    )


def _fix_message_no_rigidbody_ancestor(site_prim_path: str) -> str:
    """Describe this provider's unresolved carrier mapping, not a marker violation."""
    return (
        "FET028 cannot resolve a physical carrier attachment from the gripper site's "
        "current ancestor/mapping path.\n"
        f"  Site prim: {site_prim_path}\n\n"
        "This provider prerequisite is not itself GR.001: that marker requirement "
        "defines an Xform and grasp-center position, not a mandatory rigid-body "
        "ancestor or mass API. An unresolved attachment does not prove the site "
        "is mis-parented or the asset is missing a body schema.\n\n"
        "DIAGNOSE: preserve the marker's authored local frame and source topology. "
        "Inspect the selected composed layout/variant, physical base-body identity, "
        "loader/importer mapping and runtime carrier support. Compare the site's "
        "world/local transform with the intended grasp center and resolve the "
        "actual attachment body; sibling/wrapper layouts can need a provider "
        "mapping correction rather than an asset edit.\n\n"
        "Do not reparent the marker or add RigidBodyAPI/MassAPI to decorators "
        "solely to satisfy this test. A justified repair requires separate "
        "evidence of an authored contract violation.\n\n" + _SPEC_REFERENCE
    )


def _fix_message_open_mapping_wrong(
    *,
    joint_name: str,
    actual_pos: float,
    expected_pos: float,
    error: float,
    tolerance: float,
    shape: str,
) -> str:
    """Describe the observed opening error without prescribing an asset repair."""
    return (
        "Open command did not reach the selected open target.\n"
        f"  Driven joint:       {joint_name}\n"
        f"  Actual position:    {actual_pos:.6g} runtime joint coordinates\n"
        f"  Expected position:  {expected_pos:.6g} selected open target\n"
        f"  Error:              {error:.6g} runtime joint coordinates\n"
        f"  Tolerance:          {tolerance:.6g} runtime joint coordinates\n"
        "\n"
        f"Inspect {shape}_after_open_command.png and the joint motion history.\n"
        "Detection compares stepped live geometry at inset lower/upper probes\n"
        "and records achieved coordinates/apertures for each leader.\n"
        "Open is not universally the lower limit. GR.003 is the tube axis,\n"
        "not a declaration of jaw endpoints or their open/closed convention.\n"
        "Check that mapping, selected runtime variant, DOF names/order, imported\n"
        "limits, coupling/mimic constraints, contacts and actual drive commands\n"
        "before attributing the observation to an asset defect or controller.\n"
        "\n"
        "UNITS: runtime revolute coordinates use radians; prismatic/runtime\n"
        "coordinates require their resolved metadata and stage scale. Do not\n"
        "infer a joint type or unit from its name. Authored USD angular limits\n"
        "use DEGREES, and authored prismatic limits use stage length units.\n"
        "Do not copy a runtime coordinate into an authored limit without the\n"
        "appropriate conversion. The token physics:axis is X/Y/Z, not a value\n"
        "to negate. Do not swap limits, raise ratings or paste canned gains to\n"
        "force a pass; any justified repair or tuning is external to Evaluate.\n"
        "\n"
        "ILLUSTRATIVE ANGULAR FRAGMENT (degrees, not suggested travel ratings):\n"
        "    float physics:lowerLimit = 0.0  # degrees\n"
        "    float physics:upperLimit = 40.0 # degrees; use real mechanical travel\n"
        "\n"
        f"{_SPEC_REFERENCE}"
    )


def _fix_message_grasp_below_object(grasp_z: float, object_z: float) -> str:
    """Describe a trial-setup prerequisite, not a required authored rest pose."""
    return (
        "FET028 cannot run: the trial's grasp center is at or below the\n"
        "spawned test object.\n"
        f"  grasp_center world Z: {grasp_z:.4f} m\n"
        f"  object spawn  world Z: {object_z:.4f} m\n"
        "\n"
        "This test needs clearance for its descent phase. Its test-owned\n"
        "carrier/gantry setup is intended to accommodate the asset's original\n"
        "rest orientation and elevation; the source asset need not be authored\n"
        "pointing down or translated to a universal height.\n"
        "\n"
        "DIAGNOSE THE TRIAL SETUP: inspect the resolved TCP/grasp-site frame,\n"
        "composed transforms and scale, carrier pose/mount_height_m, test object\n"
        "size and placement, and runtime readbacks in the original evidence.\n"
        "Check a setup/classifier edge case before proposing an asset repair.\n"
        "Do not rotate or translate the source asset merely to fit the test rig.\n"
        "A confirmed test setup failure must be reported to the test owner.\n"
        "\n"
        f"{_SPEC_REFERENCE}"
    )


def _fix_message_failed_to_lift(
    tested_mass_kg: float,
    used_heuristic: bool,
    shapes_attempted: list,
    payload_mass_fraction: float,
) -> str:
    """Fix message when the gripper failed to grasp+lift any shape."""
    shapes_str = " AND ".join(shapes_attempted)
    payload_source = (
        "FET028 heuristic; custom:maxPayload was not authored"
        if used_heuristic
        else "resolved configured payload; inspect custom:maxPayload and any mass override"
    )
    return (
        "Gripper failed to grasp-and-lift the test object on every shape\n"
        f"({shapes_str}) at the configured {100.0 * payload_mass_fraction:.0f}% payload fraction.\n"
        f"  Tested object mass: {tested_mass_kg:.3f} kg ({payload_source})\n"
        "\n"
        "The configured simulated trial did not meet its grasp/lift criteria.\n"
        "This result alone does not establish an asset defect or its cause.\n"
        "A resolved topology does not validate test-object placement, grasp\n"
        "depth, reopening, carrier setup, payload suitability, or backend\n"
        "contact behavior. A heuristic payload is not a rated capability.\n"
        "\n"
        "INSPECT THE METRICS for this run in result.json:\n"
        "  - ``close_blocked_by_object_<shape>`` is the test's stall/\n"
        "    engagement proxy, not proof of measured contacts. False can\n"
        "    reflect an unengaged or incompletely reopened drive.\n"
        "  - ``grip_object_retained_<shape>`` compares object displacement\n"
        "    from spawn XY with the configured object-size tolerance.\n"
        "    ``object_lateral_drift_after_close_<shape>`` instead measures\n"
        "    displacement from the carrier axis; these are different bases.\n"
        "  - ``vertical_follow_dz_m_<shape>`` and lift/carrier motion show\n"
        "    whether the object followed the commanded lift.\n"
        "  - ``shake_max_relative_slip_m_<shape>`` (when present) records\n"
        "    the test's relative-slip check during perturbation.\n"
        "  - Missing contact-force observations are unmeasured, not zero.\n"
        "\n"
        "CHECKS BEFORE ATTRIBUTING A CAUSE:\n"
        "  1. Verify the effective payload and overrides against the real\n"
        "     mechanism. Do not change a declared rating to force a pass.\n"
        "  2. Inspect videos, stills and motion histories for object placement,\n"
        "     grasp depth, open/close targets and actual reopening, fingertip\n"
        "     resolution, carrier motion, and the backend/runtime setup.\n"
        "  3. Separate an unavailable contact readback or proxy edge case\n"
        "     from measured loss of the object. Reproduce a setup hypothesis\n"
        "     on a staged copy while preserving the original result.\n"
        "  4. Only after those checks, investigate authored collider/material\n"
        "     bindings, actual contact geometry, joint/mimic mapping and drive\n"
        "     parameters against the intended mechanical specification.\n"
        "     This result supplies no universal friction or gain prescription.\n"
        "\n"
        f"{_SPEC_REFERENCE}"
    )


def _closed_fraction(position, open_target, closed_target):
    """Diagnostic progress along a signed closing range, never a verdict.

    A held positioning DOF has no closing range; unavailable/non-finite
    inputs remain unmeasured. Do not clamp overshoot or reverse motion.
    """
    try:
        values = (position, open_target, closed_target)
        if any(value is None or isinstance(value, (bool, np.bool_)) for value in values):
            return None
        position, open_target, closed_target = (float(value) for value in values)
        if not all(math.isfinite(value) for value in (position, open_target, closed_target)):
            return None
        closing_range = closed_target - open_target
        if not math.isfinite(closing_range) or abs(closing_range) <= 1e-9:
            return None
        fraction = (position - open_target) / closing_range
        return fraction if math.isfinite(fraction) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _record_gripper_capture(path, motion, motion_joints):
    """Best-effort association with retained observations, without stepping.

    A marker means a successful capture followed an observation; it is not
    an exact rendered timestamp or encoded-video frame index.
    """
    if not path:
        return
    for observer in (motion, *motion_joints.values()):
        record = getattr(observer, "record_capture", None)
        if callable(record):
            try:
                record(path)
            except Exception:
                try:
                    observer._warn()
                except Exception:
                    pass


def get_defaults() -> dict[str, Any]:
    """Default config values for the FET028 gripper close-lift-shake-drop test.

    Every value here is generic across grippers -- nothing is keyed to
    a specific asset (no hard-coded joint names, prim paths, or
    geometric offsets that would tie this test to one model).

    The values that DO depend on the asset under test come from the
    asset's own USD authoring:
      - ``custom:maxOpening`` on the gripper site -> object size
      - ``custom:maxPayload`` on the gripper site -> tested mass
      - ``forward_axis`` and ``grip_line`` BasisCurves -> camera direction
      - The asset's own joint drive parameters (stiffness / maxForce)
        and physics materials -> grip force and friction
    """
    return {
        # ------------------------------------------------------------
        # Test object (synthetic sphere / cube spawned by the test).
        # ------------------------------------------------------------
        # Object diameter as a fraction of the gripper's max opening.
        # 0.7 is the "everyday stress" point for a position-drive
        # parallel-jaw gripper:
        #   - Holding torque = stiffness * (target - stalled), so a
        #     LARGER object means MORE position error and MORE grip
        #     force; 0.7 leaves the drive enough error to develop
        #     real holding torque (vs. the "easy" 0.6 where the
        #     fingers travel further into closure and the position
        #     error is smaller).
        #   - Stays clear of the geometric edge cases at 0.85+
        #     (finger-pad/object-corner alignment, contact
        #     resolution stability) where grippers can fail for
        #     reasons unrelated to grip strength.
        #   - Matches typical real-world operating conditions: most
        #     picked objects are 50-75% of the gripper's max
        #     opening; manufacturer maxPayload ratings implicitly
        #     assume an object in the gripper's intended operating
        #     range, not pinned at either extreme.
        "object_size_fraction": 0.7,
        # Physics material applied to the spawned test object. The
        # gripper's pads use whatever the asset authors -- we never
        # override that side; this is only the object side.
        "static_friction": 2.0,
        "dynamic_friction": 2.0,
        "restitution": 0.0,
        # Object mass = payload_mass_fraction * authored maxPayload.
        # 0.85 is the standard "85% of rated payload" stress test.
        "payload_mass_fraction": 0.85,
        # Optional debug override: set to a positive float to bypass
        # both the authored maxPayload calc and the heuristic. None =
        # off (production default). Useful for isolating mechanics
        # bugs from grip-strength bugs during local debug.
        "tested_mass_kg_override": None,
        # Explicit, bounded independently driven hand trial controls. Empty
        # preserves automatic mapping and the existing simultaneous close.
        "hand_trial_controls": {},
        # Optional contact evidence; it never changes grasp criteria.
        "diagnostic_native_contact_pairs": False,
        # Open the gripper FULLY (0 = drive to the exact open limit). The jam is
        # instead avoided by backing the gripper UP a little after it contacts
        # the object, before closing (refer to ``contact_backoff_m`` /
        # ``descent_contact_*`` below) -- so the gripper does not press the
        # object into the floor.
        "open_limit_backoff_frac": 0.0,
        # Contact-approach descent: descend in this many small chunks, holding
        # open, watching the object. When the object is nudged (z drops or it
        # shifts) past ``descent_contact_drop_m``, the gripper has made contact
        # -- stop descending.
        "descent_contact_chunks": 12,
        # Bound each approach increment as well as supplying a minimum chunk
        # count. A large backend-specific standoff must not turn twelve
        # nominally "small" chunks into centimetre-scale penetration steps.
        "descent_contact_max_step_m": 0.005,
        "descent_contact_drop_m": 0.003,
        # After contact, move the gripper UP by this much before closing, to
        # relieve the contact pressure so the fingers are free to close (they
        # jam if the gripper is still pressing the object into the floor).
        # None = 10% of the gripper's max opening.
        "contact_backoff_m": None,
        # Heuristic fallback when the asset doesn't author maxPayload.
        # Calibrated for industrial parallel-jaw grippers.
        "heuristic_payload_kg_per_m_opening": 50.0,
        "heuristic_payload_floor_kg": 0.1,
        "heuristic_payload_ceiling_kg": 50.0,
        # ------------------------------------------------------------
        # Spawn geometry
        # ------------------------------------------------------------
        # Gap between the object's bottom and the floor at spawn time
        # so it briefly free-falls onto the ground (lets PhysX settle
        # contact instead of starting in a penetrating state).
        "spawn_ground_clearance_m": 0.005,
        # Working height the rig mounts the gripper at before the grasp
        # (this is what an arm does: it presents the gripper above the
        # object). After the gantry attaches, the rig raises it by this
        # amount so the grasp center clears the floor and the object,
        # giving the descent room to bring the gripper down onto the
        # object resting on the ground. Independent of how the asset was
        # authored at rest -- we do NOT require the asset to be authored
        # pointing down with a pre-elevated grasp center.
        "mount_height_m": 0.30,
        # Standoff margin (m) ADDED to the object diameter to set how far
        # above the object the OPEN gripper starts before descending. The
        # gripper is positioned at object_center + object_size + this margin,
        # then descends exactly that far onto the object.
        "approach_extra_clearance_m": 0.03,
        # Physics steps used to drive the master DOF to each limit during
        # open/close detection (``_detect_open_closed_positions`` measures the
        # fingertip aperture at each limit; the wider one is OPEN). Enough steps
        # for the mimic chain to reach the limit and settle before measuring.
        "open_close_detect_steps": 120,
        # ------------------------------------------------------------
        # Open / close phases (master-DOF position-stall termination)
        # ------------------------------------------------------------
        # Hard cap on physics steps for each open/close drive loop
        # (early-exits on master-DOF position stall, see below).
        "open_steps_max": 600,
        "close_steps": 600,
        # Ramp the close target instead of applying a full-range step. The
        # existing 300-frame smoothstep limits abrupt linkage commands without
        # changing authored drives or the configured verdict thresholds.
        "close_ramp_steps": 300,
        # Master-DOF position-stall criterion: when the master mimic
        # DOF's position changes by less than ``close_position_stall_eps``
        # (rad for revolute, m for prismatic) over the last
        # ``close_stall_window`` physics steps, the loop exits. This
        # is robust to mimic-follower oscillation that broke the
        # earlier ``np.max(abs(velocity))`` check.
        "close_position_stall_eps": 1e-3,
        "close_stall_window": 8,
        # The close must move the master off its open position by at least this
        # much before a position-stall is accepted as a real stop. Guards
        # against a premature "stalled at open" exit when the drive's first-
        # frame response is delayed (determinism disabled in this build).
        "close_engage_eps": 2e-3,
        "close_log_every": 30,
        # If a parallel-jaw close reaches its hard limit without touching the
        # object, retry at slightly deeper object-sized approach levels.  This
        # handles runtimes that expose valid relative link motion but no usable
        # absolute link Z for distal-pad placement.  Backends with valid live
        # pad geometry (including PhysX) contact on the first close and never
        # enter this search.
        "grasp_depth_search_attempts": 4,
        "grasp_depth_search_step_radius_fraction": 0.5,
        # Required tolerance between commanded and observed open
        # position. 5x this is used as the actual open-reachability threshold.
        "open_position_tolerance": 0.005,
        # Settle time after the close drive exits, before reading
        # state for the lift.
        "close_settle_seconds": 0.3,
        # ------------------------------------------------------------
        # Lift (Z-axis gantry)
        # ------------------------------------------------------------
        "lift_delta_z": 0.20,
        "lift_duration_s": 1.0,
        # Drive-target write rate during lift. Matches physics_fps so
        # each iteration writes one target and runs one physics step.
        "lift_fps": 240,
        "hold_duration_s": 1.0,
        # ------------------------------------------------------------
        # Shake (sinusoidal perturbation)
        # ------------------------------------------------------------
        "enable_shake": True,
        "shake_amplitude_m": 0.02,
        "shake_frequency_hz": 2.0,
        "shake_duration_s": 2.0,
        # Pass criterion: object's lowest z during shake stays above
        # this threshold AND its slip relative to the gripper stays
        # below ``shake_max_relative_slip_m``.
        "shake_min_z_threshold_m": 0.02,
        "shake_max_relative_slip_m": 0.03,
        # ------------------------------------------------------------
        # Drop (release verification)
        # ------------------------------------------------------------
        "enable_drop": True,
        "drop_wait_s": 1.0,
        "drop_min_dz_m": 0.05,
        # ------------------------------------------------------------
        # Pass / fail thresholds (lift evaluation)
        # ------------------------------------------------------------
        "fall_min_delta_z": 0.05,
        "horizontal_drift_max": 0.05,
        "pre_load_max_dz": 0.01,
        "carrier_translate_tolerance_m": 0.01,
        # Minimum gantry lift (m) required to MEANINGFULLY evaluate the grasp.
        # The grasp verdict (vertical_follow_dz) is measured against the gantry's
        # ACTUAL lift, not the commanded one, so a partial lift is fine to judge
        # against -- we only need the rig to have lifted clearly more than
        # fall_min_delta_z. A heavier gripper + payload makes the gantry drive
        # lag the commanded lift_delta_z; that is not a grasp failure. Only fail
        # if the gantry barely moved (drive genuinely too weak / attach broken).
        "min_lift_for_eval_m": 0.10,
        # ------------------------------------------------------------
        # Camera framing (static side view)
        # ------------------------------------------------------------
        # Side-view direction is the gripper site's grip_line
        # direction, derived at runtime from the asset's authored
        # forward_axis + grip_line BasisCurves (FET028 spec). No
        # per-asset hard-coding.
        "camera_side_sign": 1.0,
        "camera_elevation": 0.2,
        "camera_margin_factor": 1.6,
        # ------------------------------------------------------------
        # Output
        # ------------------------------------------------------------
        # Video frame rate cap. At physics_fps=240 with cap=20 we
        # capture every 12 steps -- plenty for visualization, fast to
        # encode.
        "video_fps_max": 20.0,
        # ------------------------------------------------------------
        # Shape iteration
        # ------------------------------------------------------------
        "shapes": ["sphere", "cube"],
        # Independent-finger joint chains.
        "jik_max_iterations": 80,
        "jik_step_size": 0.05,
        "jik_position_tolerance": 0.005,
        "jik_rms_tolerance": 0.003,
        "jik_contact_force_threshold_n": 0.5,
        "max_close_frames": 1200,
    }


def compute_tested_mass(
    max_opening: float,
    max_payload_authored: float | None,
    config: dict[str, Any],
) -> tuple[float, bool, float]:
    """Resolve the test-object mass.

    Returns ``(tested_mass_kg, used_heuristic_payload, max_payload_used_kg)``.
    Resolution order:
      1. ``tested_mass_kg_override`` (debug knob): positive float bypasses
         everything else and uses that mass directly. ``max_payload_used``
         is reported as the override value so downstream consumers see a
         self-consistent triple.
      2. Authored ``custom:maxPayload`` * ``payload_mass_fraction`` when
         the asset declares a positive value.
      3. Linear ``50 * max_opening`` heuristic clamped to
         ``[floor, ceiling]`` * ``payload_mass_fraction``.
    """
    override = config.get("tested_mass_kg_override")
    if override is not None and float(override) > 0.0:
        m = float(override)
        return (m, False, m)
    fraction = float(config["payload_mass_fraction"])
    if max_payload_authored is not None and max_payload_authored > 0.0:
        return (fraction * max_payload_authored, False, float(max_payload_authored))
    raw = float(config["heuristic_payload_kg_per_m_opening"]) * float(max_opening)
    floor = float(config["heuristic_payload_floor_kg"])
    ceiling = float(config["heuristic_payload_ceiling_kg"])
    clamped = max(floor, min(ceiling, raw))
    return (fraction * clamped, True, clamped)


@dataclass
class PassCriterion:
    passed: bool
    vertical_follow_dz: float
    horizontal_drift: float
    pre_load_dz: float


def evaluate_pass_criterion(
    object_pre_close_xy: np.ndarray,
    object_pre_close_z: float,
    object_pre_lift_z: float,
    object_post_lift: np.ndarray,
    carrier_pre_lift_z: float,
    carrier_post_lift_z: float,
    config: dict[str, Any],
) -> PassCriterion:
    """Two-condition grasp-and-lift pass with a pre-load diagnostic:

    1. ``vertical_follow_dz < fall_min_delta_z`` — object followed the carrier upward
    2. ``horizontal_drift < horizontal_drift_max`` — object stayed in the grip XY-wise

    ``pre_load_dz`` records how far closure moved the object vertically before
    the carrier lift. It is diagnostic only: a hand may legitimately seat or
    lift an object while establishing contact, and the subsequent carrier-follow,
    shake, and release phases check retention under this test's conditions;
    they do not prove contact fidelity or unrestricted grasp capability.

    All distances in meters, world frame. Expected post-lift z is
    ``object_pre_lift_z + (carrier_post_lift_z - carrier_pre_lift_z)`` —
    the object should follow the carrier's translation exactly.
    """
    expected_object_z = object_pre_lift_z + (carrier_post_lift_z - carrier_pre_lift_z)
    vertical_follow_dz = abs(float(object_post_lift[2]) - expected_object_z)
    horizontal_drift = float(
        np.sqrt(
            (object_post_lift[0] - object_pre_close_xy[0]) ** 2 + (object_post_lift[1] - object_pre_close_xy[1]) ** 2
        )
    )
    pre_load_dz = abs(object_pre_lift_z - object_pre_close_z)

    passed = vertical_follow_dz < float(config["fall_min_delta_z"]) and horizontal_drift < float(
        config["horizontal_drift_max"]
    )
    return PassCriterion(
        passed=passed,
        vertical_follow_dz=vertical_follow_dz,
        horizontal_drift=horizontal_drift,
        pre_load_dz=pre_load_dz,
    )


def _rotated_grasp_center(stage, pivot_path, center_world, current_rotation, desired_rotation):
    """Predict the authored site center using the carrier's world rotation pivot."""
    from pxr import Gf, UsdGeom

    pivot = stage.GetPrimAtPath(pivot_path)
    if not pivot or not pivot.IsValid():
        raise RuntimeError("FET028 cannot predict the grasp center without a valid orientation pivot")
    anchor = UsdGeom.XformCache().GetLocalToWorldTransform(pivot).ExtractTranslation()
    delta = current_rotation.GetInverse() * desired_rotation
    center = Gf.Vec3d(*map(float, center_world))
    return np.asarray(anchor + delta.TransformDir(center - anchor), dtype=np.float64)


def _compute_approach_orientation(stage, gripper_base_path, site, approach_world, roll_deg=0.0, pivot_path=None):
    """Return (base_orient_wxyz, grasp_center_rotated, forward_in_base) to orient
    the gripper so its ``forward_axis`` points along ``approach_world`` (world -Z
    for a top-down grasp).

    ``base_orient`` (``rot``) is the gripper base's desired WORLD orientation: it
    must satisfy ``base_orient * forward_in_base_local == approach_world``, hence
    ``base_orient = rotation(forward_in_base_local -> approach_world)``. The grasp
    center uses the carrier's physical-root pivot when supplied; callers without
    a carrier retain the base-body pivot. Object spawn and descent then follow
    the same re-oriented authored site, including a site on an offset body.

    The carrier authors the desired pose and matching attachment frames before
    rebuilding physics. A reset default alone cannot override an attachment
    constraint; required live fixture checks establish the resulting pose.

    The returned quaternion is ``rot`` itself, scalar-first ``(w, x, y, z)``, as
    Isaac's ``set_default_state`` expects. It maps the resolved base-local
    forward direction onto the desired world approach using a minimal-arc
    rotation, followed by the optional roll around that approach. No particular
    axis angle follows from an asset name or an authored world-forward label.
    """
    import numpy as np
    from pxr import Gf, UsdGeom

    base_prim = stage.GetPrimAtPath(gripper_base_path)
    base_T = Gf.Transform(UsdGeom.XformCache().GetLocalToWorldTransform(base_prim))
    base_rot = base_T.GetRotation()

    fwd = Gf.Vec3d(*[float(x) for x in site.forward_axis_world]).GetNormalized()
    appr = Gf.Vec3d(float(approach_world[0]), float(approach_world[1]), float(approach_world[2]))
    fwd_in_base = base_rot.GetInverse().TransformDir(fwd)
    rot = Gf.Rotation(fwd_in_base, appr)  # base local-frame orientation -> forward maps to approach
    # ``Gf.Rotation(from, to)`` is the MINIMAL-arc rotation: it fixes the
    # forward axis along the approach but leaves the ROLL about that axis
    # arbitrary (for a hand this lands the palm in a random direction -- e.g.
    # palm-up instead of facing the object). ``roll_deg`` rolls the hand about
    # its OWN forward axis FIRST (in the base-local frame), then the
    # forward->approach mapping points the fingers at the object. Rolling about
    # the local forward axis spins the palm/grip around the finger axis while
    # keeping the fingers aligned with the approach. (The earlier attempt rolled
    # about the world ``appr`` vector in the pre-rotation frame -- the wrong
    # axis -- which just spun the whole hand without moving the palm.)
    if roll_deg:
        # Gf row-vector convention: (A * B) applies A first. Roll about the
        # local forward axis FIRST, then orient forward->approach.
        rot = Gf.Rotation(fwd_in_base, float(roll_deg)) * rot

    grasp_center_rotated = _rotated_grasp_center(
        stage, pivot_path or gripper_base_path, site.grasp_center_world_initial(), base_rot, rot
    )
    fwd_in_base_arr = np.array([fwd_in_base[0], fwd_in_base[1], fwd_in_base[2]], dtype=np.float64)
    # ``rot`` is the desired base WORLD orientation; return it scalar-first
    # (w, x, y, z) for ``set_default_state``. grasp_center_rotated uses rot.
    bq = rot.GetQuat()
    bi = bq.GetImaginary()
    base_orient_wxyz = np.array([bq.GetReal(), bi[0], bi[1], bi[2]], dtype=np.float64)
    return base_orient_wxyz, grasp_center_rotated, fwd_in_base_arr


def _authored_hand_frames(forward_in_base, grip_in_base, pitch_deg=None):
    """Build orthonormal local/target frames from authored site axes."""

    def _norm(vector):
        vector = np.asarray(vector, dtype=np.float64)
        length = float(np.linalg.norm(vector))
        return vector / length if length > 1e-12 else vector

    forward = _norm(forward_in_base)
    grip = _norm(grip_in_base)
    if float(np.linalg.norm(forward)) <= 1e-12:
        raise ValueError("forward_axis must have non-zero length")
    grip = _norm(grip - forward * float(np.dot(grip, forward)))
    if float(np.linalg.norm(grip)) <= 1e-12:
        raise ValueError("forward_axis and grip_line must define distinct directions")

    local_frame = np.array([forward, grip, np.cross(forward, grip)])
    forward_world = np.array([1.0, 0.0, 0.0])
    if pitch_deg is not None:
        pitch = normalize_hand_trial_controls({"approach_pitch_deg": pitch_deg})["approach_pitch_deg"]
        angle = math.radians(pitch)
        forward_world = np.array([math.cos(angle), 0.0, -math.sin(angle)])
    grip_world = np.array([0.0, -1.0, 0.0])
    world_frame = np.array([forward_world, grip_world, np.cross(forward_world, grip_world)])
    return local_frame, world_frame


def _authored_hand_orientation(stage, gripper_base_path, site, pivot_path=None, pitch_deg=None, center_base_m=None):
    """Orient an independent-finger hand from its authored site frame.

    The site's ``forward_axis`` is mapped to world +X and its ``grip_line`` to
    world -Y. Their cross product therefore points world -Z, placing the palm
    over the object without relying on an asset-specific palm axis. Returns the
    same triple and optional physical-root pivot as ``_compute_approach_orientation``.
    An explicit pitch tilts forward down from horizontal (0 through 90 degrees).
    An explicit center uses physical metres in the base's rotational frame; its
    world prediction still rotates about the carrier's resolved physical root.
    """
    from pxr import Gf, UsdGeom

    base_prim = stage.GetPrimAtPath(gripper_base_path)
    base_T = Gf.Transform(UsdGeom.XformCache().GetLocalToWorldTransform(base_prim))
    base_rot = base_T.GetRotation()

    fwd_world = np.asarray(site.forward_axis_world, dtype=np.float64)
    grip_world = np.asarray(site.grip_line_world[1] - site.grip_line_world[0], dtype=np.float64)
    fib = base_rot.GetInverse().TransformDir(Gf.Vec3d(*fwd_world.tolist()))
    gib = base_rot.GetInverse().TransformDir(Gf.Vec3d(*grip_world.tolist()))
    lframe, wframe = _authored_hand_frames([fib[0], fib[1], fib[2]], [gib[0], gib[1], gib[2]], pitch_deg)
    fa = lframe[0]

    rmat = wframe.T @ lframe  # base-local -> world rotation, R @ finger = finger-forward, R @ palm = down
    m = Gf.Matrix3d(*rmat.T.flatten().tolist())  # Gf row-vector: TransformDir(v) = v*M = R@v
    rot = m.ExtractRotation()
    bq = rot.GetQuat()
    bi = bq.GetImaginary()
    base_orient_wxyz = np.array([bq.GetReal(), bi[0], bi[1], bi[2]], dtype=np.float64)

    center_world = site.grasp_center_world_initial()
    if center_base_m is not None:
        center = normalize_hand_trial_controls({"grasp_center_base_m": center_base_m})["grasp_center_base_m"]
        scale = _hand_trial_length_scale(stage)
        center_stage = _required_trial_geometry([value / scale for value in center], 3, "base-local center conversion")
        center_world = base_T.GetTranslation() + base_rot.TransformDir(Gf.Vec3d(*center_stage))
        center_world = _required_trial_geometry(list(center_world), 3, "world grasp center")
    grasp_center_rotated = _rotated_grasp_center(stage, pivot_path or gripper_base_path, center_world, base_rot, rot)
    if center_base_m is not None or pitch_deg is not None:
        _required_trial_geometry(base_orient_wxyz, 4, "approach orientation")
        grasp_center_rotated = np.asarray(_required_trial_geometry(grasp_center_rotated, 3, "pivoted grasp center"))
    return base_orient_wxyz, grasp_center_rotated, fa


def _classify_hand_endpoint_motion(displacement, radial_change):
    """Return ``(role, target_endpoint)`` from authored-frame tip motion."""

    displacement = np.asarray(displacement, dtype=np.float64)
    motion = float(np.linalg.norm(displacement))
    if motion <= 1e-6:
        return ("unresolved", None)
    radial_tolerance = max(1e-5, motion * 0.02)
    if radial_change < -radial_tolerance:
        return ("closure", "upper")
    if radial_change > radial_tolerance:
        return ("closure", "lower")

    forward_component = abs(float(displacement[0]))
    grip_component = abs(float(displacement[1]))
    palm_component = abs(float(displacement[2]))
    if grip_component > max(forward_component, palm_component):
        return ("positioning", "upper")
    return ("positioning", "lower")


async def _infer_hand_grasp_specs(ctx, robot, fingertip_set, stage, config, grasp_center_world, base_path=None):
    """Infer independent-finger targets from stepped live geometry, not teleports."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        map_hand_endpoints,
    )

    return await map_hand_endpoints(
        ctx, robot, fingertip_set, stage, config, grasp_center_world, _classify_hand_endpoint_motion, base_path
    )


class _GripperSupportPause:
    """Temporarily disable only scene-owned support collision, without ticks.

    The free endpoint probe and existing standoff move must not be blocked by
    the synthetic pickup floor. Asset colliders, drive controls and visibility
    are untouched. Restore the exact edit-target collision opinions, including
    a previously absent authored default, before spawning the pickup object.
    """

    def __init__(self, ctx):
        from pxr import Sdf, Usd, UsdPhysics

        self.ctx = ctx
        self.stage = ctx.scene.stage
        self.edit_target = self.stage.GetEditTarget()
        self.pending = []
        roots = []
        room = getattr(ctx.scene, "_room_handle", None)
        room_path = getattr(room, "_room_path", None)
        if room_path:
            room_stage = getattr(room, "_stage", self.stage)
            if room_stage is not self.stage:
                raise RuntimeError("FET028 setup: room support belongs to a different stage")
            roots.append(str(room_path).rstrip("/") + "/Floor")
        ground_path = getattr(ctx.scene, "_ground_plane_path", None)
        if ground_path:
            roots.append(str(ground_path))

        asset = getattr(ctx.scene, "asset", None)
        asset_paths = {
            str(path)
            for path in (getattr(asset, "prim_path", None), getattr(ctx.scene, "_asset_root_path", None))
            if path
        }
        snapshots = []
        seen = set()
        layer = self.edit_target.GetLayer()
        for root in dict.fromkeys(roots):
            path = Sdf.Path(root)
            if not path.IsAbsolutePath() or not path.IsPrimPath() or path.GetParentPath() == Sdf.Path.absoluteRootPath:
                raise RuntimeError("FET028 setup: invalid scene-owned support path")
            if any(path.HasPrefix(Sdf.Path(item)) or Sdf.Path(item).HasPrefix(path) for item in asset_paths):
                raise RuntimeError("FET028 setup: scene-owned support overlaps the loaded asset subtree")
            prim = self.stage.GetPrimAtPath(path)
            if not prim or not prim.IsValid():
                raise RuntimeError("FET028 setup: declared scene-owned support is missing: %s" % path)
            for collider in Usd.PrimRange(prim):
                if not collider.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                attribute = UsdPhysics.CollisionAPI(collider).GetCollisionEnabledAttr()
                attribute_path = attribute.GetPath()
                if attribute_path in seen:
                    continue
                seen.add(attribute_path)
                enabled = attribute.Get()
                if not isinstance(enabled, bool) or attribute.GetNumTimeSamples():
                    raise RuntimeError("FET028 setup: support collision must have a static boolean state")
                spec = layer.GetAttributeAtPath(self.edit_target.MapToSpecPath(attribute_path))
                snapshots.append(
                    {
                        "attribute": attribute,
                        "enabled": enabled,
                        "had_spec": spec is not None,
                        "had_default": bool(spec is not None and spec.HasInfo("default")),
                        "default": spec.default if spec is not None and spec.HasInfo("default") else None,
                    }
                )
        try:
            for snapshot in snapshots:
                if snapshot["enabled"]:
                    self.pending.append(snapshot)
                    if not snapshot["attribute"].Set(False):
                        raise RuntimeError("FET028 setup: could not suspend scene-owned support collision")
        except BaseException as error:
            self.restore(error)
            raise
        try:
            ctx.add_metric(
                "test_support_collision_suspended",
                [str(snapshot["attribute"].GetPrim().GetPath()) for snapshot in self.pending],
            )
        except Exception:
            pass  # Optional diagnostics do not change the setup or its error.
        except BaseException as error:
            self.restore(error)
            raise

    def restore(self, original_error=None):
        from pxr import Usd

        errors, pending = [], []
        try:
            with Usd.EditContext(self.stage, self.edit_target):
                for snapshot in reversed(self.pending):
                    try:
                        attribute = snapshot["attribute"]
                        if snapshot["had_default"]:
                            restored = attribute.Set(snapshot["default"])
                        elif snapshot["had_spec"]:
                            restored = attribute.ClearDefault()
                        else:
                            restored = attribute.GetPrim().RemoveProperty(attribute.GetName())
                        if not restored or attribute.Get() != snapshot["enabled"]:
                            raise RuntimeError("collision opinion restoration did not restore the original state")
                    except BaseException as error:
                        errors.append(error)
                        pending.append(snapshot)
        except BaseException as error:
            # Enter/exit failures also leave the restoration context unqualified.
            # Retain all snapshots for guarded retry rather than claiming cleanup.
            errors.append(error)
            pending = list(self.pending)
        self.pending = pending
        if errors:
            error = _gripper_required_cleanup_error(
                errors[0], "FET028 setup: test-owned support collision restoration failed"
            )
            primary = original_error if original_error is not None else error
            _record_gripper_cleanup_failure(self.ctx, "Required FET028 support collision restoration failed.", primary)
            for secondary in errors:
                _gripper_cleanup_note(primary, secondary, "Support restoration")
            _gripper_cleanup_diagnostic(
                lambda: self.ctx.add_metric("test_support_restoration_incomplete", True), primary
            )
            _gripper_cleanup_diagnostic(
                lambda: self.ctx.warn(
                    "FET028 test-owned support collision restoration is incomplete; execution must stop."
                ),
                primary,
            )
            if original_error is None:
                raise error


def _prepare_gripper_ground(ctx):
    """Required collidable floor setup must not become an asset outcome."""
    room_handle = getattr(ctx.scene, "_room_handle", None)
    if room_handle is None:
        ctx.scene.enable_ground_plane()
        return
    # show_ground re-enables Floor collision; failures are setup errors.
    room_handle.show_ground(color=(0.3, 0.3, 0.3))
    stage = getattr(ctx.scene, "stage", None)
    room_path = getattr(room_handle, "_room_path", None)
    if stage is not None and room_path:
        from pxr import UsdPhysics

        floor = stage.GetPrimAtPath(str(room_path).rstrip("/") + "/Floor")
        if (
            not floor
            or not floor.IsValid()
            or not floor.HasAPI(UsdPhysics.CollisionAPI)
            or not UsdPhysics.CollisionAPI(floor).GetCollisionEnabledAttr().Get()
        ):
            raise RuntimeError("FET028 setup: the selected room Floor is missing or its collision is not enabled")
    try:
        room_handle.set_color(0.3, 0.3, 0.3)
    except Exception as exc:
        ctx.warn(f"FET028 cosmetic room color unavailable: {exc}")


async def _detach_trial_carrier(stage, carrier, ctx, original_error=None):
    """Fail closed on incomplete fixture cleanup without masking a trial error."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_carrier import (
        detach_carrier,
    )

    try:
        await detach_carrier(stage, carrier, ctx=ctx)
    except BaseException as error:
        failure = _gripper_required_cleanup_error(error, "FET028 setup: test-owned carrier restoration failed")
        primary = original_error if original_error is not None else failure
        _record_gripper_cleanup_failure(ctx, "Required FET028 carrier restoration failed.", primary)
        _gripper_cleanup_note(primary, error, "Carrier restoration")
        _gripper_cleanup_diagnostic(lambda: ctx.add_metric("test_carrier_restoration_incomplete", True), primary)
        _gripper_cleanup_diagnostic(
            lambda: ctx.warn("FET028 carrier restoration is incomplete; the first execution error is preserved."),
            primary,
        )
        if original_error is None:
            if failure is error:
                raise
            raise failure from error
        return False
    return True


def _gripper_cleanup_note(primary, secondary, operation):
    """Secondary diagnostics never replace the first error or interruption."""
    if primary is None or primary is secondary:
        return
    try:
        primary.add_note("%s also failed (%s)." % (operation, type(secondary).__name__))
    except BaseException:
        pass


def _gripper_cleanup_diagnostic(operation, primary):
    """Defer a new stop request, but ordinary optional sink errors stay optional."""
    try:
        operation()
    except BaseException as error:
        if primary is not None:
            _gripper_cleanup_note(primary, error, "Cleanup diagnostic")
        elif not isinstance(error, Exception):
            return error
    return primary


def _gripper_required_cleanup_error(error, message):
    if not isinstance(error, Exception):
        return error
    if isinstance(error, RuntimeError) and str(error).startswith("FET028 setup:"):
        return error
    failure = RuntimeError(message)
    failure.__cause__ = error
    return failure


def _record_gripper_cleanup_failure(ctx, reason, primary):
    """Latch native health when supported; a failed signal cannot hide its cause."""

    def record():
        adapter = getattr(ctx, "_engine_session", None)
        callback = getattr(adapter, "record_required_cleanup_failure", None)
        if callable(callback):
            callback(reason)

    _gripper_cleanup_diagnostic(record, primary)


def _remove_gripper_trial_object(stage, obj, edit_target):
    """Remove only the spawned physical object's own authored namespace."""
    from pxr import Usd

    if edit_target is None:
        raise RuntimeError("FET028 test-object cleanup has no captured authoring target")
    with Usd.EditContext(stage, edit_target):
        prim = stage.GetPrimAtPath(obj.root_path)
        if prim and prim.IsValid() and not stage.RemovePrim(obj.root_path):
            raise RuntimeError("FET028 test-object namespace removal was rejected")
    if stage.GetPrimAtPath(obj.root_path):
        raise RuntimeError("FET028 test-owned physical object remains composed after cleanup")


async def _cleanup_gripper_trial(
    ctx,
    stage,
    *,
    carrier,
    support_pause,
    obj,
    object_edit_target,
    contact_collector,
    contact_enabled,
    contact_metric,
    stop_reason,
    video_frames,
    video_fps,
    shape,
    original_error=None,
):
    """Finish independent required cleanup before propagating the first cause."""
    primary = original_error

    def defer(error, operation, required=False):
        nonlocal primary
        if required:
            failure = _gripper_required_cleanup_error(error, "FET028 setup: %s failed" % operation)
            if primary is None:
                primary = failure
            else:
                _gripper_cleanup_note(primary, error, operation)
            _record_gripper_cleanup_failure(ctx, "Required FET028 %s failed." % operation, primary)
        elif not isinstance(error, Exception):
            if primary is None:
                primary = error
            else:
                _gripper_cleanup_note(primary, error, operation)
        else:
            primary = _gripper_cleanup_diagnostic(
                lambda: ctx.log("Optional %s unavailable for %s (%s)." % (operation, shape, type(error).__name__)),
                primary,
            )

    if contact_enabled:
        try:
            _finish_gripper_contact_diagnostics(ctx, contact_collector, contact_metric, stop_reason)
        except BaseException as error:
            # The native collector owns its actual required-cleanup health;
            # serialization and evidence sinks remain diagnostic-only.
            defer(error, "native contact evidence")
    if support_pause is not None:
        try:
            support_pause.restore(primary)
        except BaseException as error:
            defer(error, "support collision restoration", required=True)
    carrier_restored = carrier is None
    if carrier is not None:
        try:
            carrier_restored = await _detach_trial_carrier(stage, carrier, ctx, primary) is True
        except BaseException as error:
            defer(error, "carrier restoration", required=True)
    if obj is not None:
        if carrier_restored:
            try:
                _remove_gripper_trial_object(stage, obj, object_edit_target)
            except BaseException as error:
                defer(error, "test-object removal", required=True)
        else:
            # A rejected/interrupted stop barrier withholds further topology
            # edits. Preserve the object for required scene teardown/retirement.
            defer(
                RuntimeError("Carrier cleanup was not confirmed; physical object was preserved"),
                "test-object removal withheld",
                required=True,
            )
            primary = _gripper_cleanup_diagnostic(lambda: ctx.add_metric("test_object_cleanup_deferred", True), primary)
    if video_frames:
        try:
            ctx.encode_video(video_frames, fps=int(round(video_fps)), label=f"{shape}_grasp_lift", role="summary")
        except BaseException as error:
            defer(error, "video encoding")
    if original_error is None and primary is not None:
        raise primary


async def run_gripper_close_lift(ctx, robot, scene_info, config):
    """Orchestrate FET028 close-and-lift on a single gripper site."""

    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    contact_diagnostics_enabled = config.get("diagnostic_native_contact_pairs", False)
    if type(contact_diagnostics_enabled) is not bool:
        raise ValueError("diagnostic_native_contact_pairs must be an explicit boolean")

    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        discover_fingertips,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_carrier import (
        _carrier_asset_root,
        _resolve_articulation_root_body,
        attach_carrier,
        carrier_world_position,
        linear_translate,
        shake_gantry_z,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        diagnose_missing_sites,
        discover_gripper_sites,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.object_spawning import (
        spawn_test_object,
    )

    hand_controls = normalize_hand_trial_controls(config.get("hand_trial_controls", {}))
    stage = ctx.scene.stage
    asset_handle = scene_info["asset_handle"]
    asset_prim = stage.GetPrimAtPath(asset_handle.prim_path)

    # 1. Site discovery. On miss, emit the actionable fix-instructions
    # message so the asset author sees exactly which prim to edit and
    # which fields/children to add. This message is the only signal the
    # author gets from CI when their asset is incomplete -- it MUST be
    # useful enough to fix the asset without round-tripping back to the
    # spec docs.
    sites = discover_gripper_sites(stage, asset_prim)
    if not sites:
        ctx.skip(diagnose_missing_sites(stage, asset_prim))
        return
    site = sites[0]
    if site.max_opening <= 0.0:
        ctx.precheck_failure(_fix_message_invalid_max_opening(site.prim_path, site.max_opening))
        return

    # 2. Payload + metrics
    tested_mass_kg, used_heuristic, max_payload_used = compute_tested_mass(
        max_opening=site.max_opening,
        max_payload_authored=site.max_payload,
        config=config,
    )
    if used_heuristic:
        ctx.warn(f"custom:maxPayload not authored; using heuristic {max_payload_used:.2f} kg")
    ctx.add_metric("gripper_max_opening_m", site.max_opening)
    ctx.add_metric("gripper_max_payload_kg", max_payload_used)
    ctx.add_metric("used_heuristic_payload", used_heuristic)
    ctx.add_metric("tested_object_mass_kg", tested_mass_kg)

    # 3. Topology
    fingertip_set = discover_fingertips(
        stage,
        robot,
        site,
    )
    if fingertip_set.kind == "unsupported":
        ctx.skip(_test_scope_skip_unsupported(site.prim_path, fingertip_set.reason))
        return
    if hand_controls and fingertip_set.kind != "independent_fingers":
        raise ValueError("hand_trial_controls require an independently driven hand")
    discovered_dof_names = _capture_gripper_dof_names(fingertip_set, robot.dof_names)
    discovered_fingertips = copy.deepcopy(fingertip_set)
    if fingertip_set.kind == "independent_fingers":
        # Hand topology discovered. Log it so the discovery can be verified
        # before the per-finger grasp (power/side + pinch/top) is implemented.
        try:
            chains = fingertip_set.finger_chains or []
            named = [[robot.dof_names[i] for i in chain] for chain in chains]
            ctx.log(
                "FET028 hand[%s]: %s | finger DOF groups=%s | fingertips=%s"
                % (
                    site.prim_path,
                    fingertip_set.reason,
                    named,
                    fingertip_set.tip_link_paths,
                )
            )
        except Exception as exc:
            ctx.log("FET028 hand topology log failed: %s" % exc)

    # 4. Resolve the gripper base body and the approach orientation up front --
    # before the camera and the spawn -- so both use the re-oriented grasp
    # center. The gripper base is the first RigidBodyAPI ancestor of the site.
    gripper_base_path = _resolve_gripper_base_path(stage, site.prim_path)
    if gripper_base_path is None:
        ctx.precheck_failure(_fix_message_no_rigidbody_ancestor(site.prim_path))
        return
    carrier_asset_root = _carrier_asset_root(stage, robot, gripper_base_path)
    carrier_pivot_path = _resolve_articulation_root_body(stage, robot.prim_path, carrier_asset_root)
    if not carrier_pivot_path:
        raise RuntimeError(f"FET028 cannot resolve an unambiguous articulation root body for {robot.prim_path}")
    # Orient the gripper so its forward_axis points along the approach vector
    # (world -Z, top-down) when welded under the gantry; the grasp center moves
    # with the rotation so the spawn + descent follow it. Parallel-jaw and
    # centric grippers approach top-down; independent-finger hands use the
    # complete authored site frame in the branch below.
    approach_base_orient = None
    approach_fwd_in_base = None
    grasp_center_for_test = np.asarray(site.grasp_center_world_initial(), dtype=np.float64)
    if fingertip_set.kind == "mimic_parallel_jaw":
        (
            approach_base_orient,
            grasp_center_for_test,
            approach_fwd_in_base,
        ) = _compute_approach_orientation(
            stage, gripper_base_path, site, (0.0, 0.0, -1.0), pivot_path=carrier_pivot_path
        )
        ctx.log(
            "FET028 orient: forward_axis -> world -Z; grasp center %s -> %s "
            "(base reset orientation set so the gripper points down)."
            % (
                np.round(site.grasp_center_world_initial(), 4),
                np.round(grasp_center_for_test, 4),
            )
        )
    elif fingertip_set.kind == "independent_fingers":
        # Map the complete authored site frame into the test frame. This places
        # the palm over the object without an asset-specific palm-axis override.
        try:
            (
                approach_base_orient,
                grasp_center_for_test,
                approach_fwd_in_base,
            ) = _authored_hand_orientation(
                stage,
                gripper_base_path,
                site,
                pivot_path=carrier_pivot_path,
                pitch_deg=hand_controls.get("approach_pitch_deg"),
                center_base_m=hand_controls.get("grasp_center_base_m"),
            )
        except ValueError as exc:
            ctx.precheck_failure(f"Invalid FET028 gripper site orientation at {site.prim_path}: {exc}.")
            return
        frame_description = "forward_axis -> world +X, grip_line -> world -Y, palm -> world -Z"
        if "approach_pitch_deg" in hand_controls:
            frame_description = (
                f"forward_axis tilted {hand_controls['approach_pitch_deg']:.3f} degrees down from world +X, "
                "grip_line -> world -Y"
            )
        ctx.log(
            f"FET028 hand orient [authored frame]: {frame_description}; grasp center "
            f"{np.round(site.grasp_center_world_initial(), 4)} -> {np.round(grasp_center_for_test, 4)}."
        )

    # Resolve explicit trial geometry before attachment changes native topology.
    # Empty controls retain the existing path and its ordinary placement math.
    hand_object_offset_stage = np.zeros(2)
    if hand_controls:
        hand_object_offset_stage = _validate_hand_trial_placement(
            stage, hand_controls, grasp_center_for_test, config, site.max_opening
        )

    # NOTE: we do NOT override the gripper's pad physics material.
    # The asset's authored materials apply. Close/retention proxies do not
    # measure friction or establish why a grasp failed; inspect setup and
    # authored materials separately before attributing a cause. We only set
    # the test-owned object's material in spawn_test_object.

    # Match FET005's room presentation: show the room's own Floor and
    # give the walls a visible color. ``setup_robot_test_scene`` hides
    # the floor for GRIPPER (because activate_ground_plane=False in the
    # gripper scene defaults), so without this the captures show no
    # floor at all and the un-colored walls blend with the dome light's
    # default grey IBL into one apparent "curved dome".
    #
    # We deliberately do NOT call ``ctx.scene.enable_ground_plane()``
    # (which v1 of this test did): that adds a *separate* physics
    # ground plane on top of the hidden room floor -- the cube ends up
    # sitting on the framework plane while the room walls go unrendered
    # (no color) and merge with the IBL. Reusing the room's Floor gives
    # us straight walls and one visible ground surface.
    # Keep the pickup floor inactive until free endpoint mapping and the
    # existing standoff positioning complete. Present it before object spawn.

    # Camera direction: look back along the gripper's grip_line axis
    # (the tube axis of the graspable region, per FET028 spec). The
    # three site axes are mutually orthogonal:
    #
    #   forward_axis  -- approach / descent direction (gripper moves
    #                    toward the object along this)
    #   grip_line     -- tube axis (PERPENDICULAR to closure motion;
    #                    the axis a held cylinder would lie along)
    #   closure       -- implied third axis = forward x grip_line,
    #                    direction fingers move when opening/closing
    #
    # Looking back along the grip_line means closure (the third axis)
    # ends up perpendicular to the camera's view direction -- so
    # closure motion shows as left-right in frame and forward/descent
    # shows as up-down. (Looking back along closure -- e.g.
    # ``cross(forward, grip_line)`` -- would put one finger in front
    # of the other and hide the closure motion entirely; that was
    # the previous bug.)
    #
    # Sign of grip_line p0->p1 is asset-author-determined; flip via
    # ``camera_side_sign`` if a specific asset's authoring convention
    # puts the camera on the wrong side.
    #
    # ``camera_elevation`` adds a +Z tilt to bias the sightline above
    # horizontal so a small object on the ground stays in frame.
    # ``setup_camera_follow`` is re-run with smooth_time=0 so the rig
    # snaps to this direction and tracks the descent without ~1s
    # smooth-damp lag.
    grip_dir = np.asarray(site.grip_line_world[1] - site.grip_line_world[0], dtype=np.float64).reshape(3)
    # Project the grip line onto the horizontal (XY) plane. Once the gripper is
    # rotated so its forward_axis points DOWN (-Z), the grip line can become
    # near-vertical; a grip-line-based sightline would then look straight down
    # and hide the object. A horizontal side view (with a small +Z elevation so
    # a low object stays in frame) shows the descent and closure cleanly.
    grip_horiz = np.array([float(grip_dir[0]), float(grip_dir[1]), 0.0])
    grip_norm = float(np.linalg.norm(grip_horiz))
    if grip_norm < 1e-6:
        grip_horiz = np.array([0.0, -1.0, 0.0])
    else:
        grip_horiz = grip_horiz / grip_norm
    side_sign = float(config.get("camera_side_sign", 1.0))
    elevation = float(config.get("camera_elevation", 0.2))
    side_dir = (
        float(grip_horiz[0]) * side_sign,
        float(grip_horiz[1]) * side_sign,
        elevation,
    )
    camera_margin = float(config.get("camera_margin_factor", 1.6))

    # Camera: use the proven camera-FOLLOW mechanism (identical to the other
    # articulation phases), NOT a one-shot ``set_camera``.
    # ``setup_robot_test_scene`` already set up a follow rig on /World/Camera;
    # the old ``set_camera`` repositioned that rig's child camera with a world
    # look-at, which composed against the rig's parent transform and rendered
    # BLANK frames (the saved PNGs were empty). Re-setup the follow with our
    # side-view direction, then ``update_camera_follow`` (in _capture /
    # _video_capture) advances it before each frame so the gripper + grasped
    # object stay in view through the descent and lift.
    _sd = np.array(side_dir, dtype=np.float64)
    _sn = float(np.linalg.norm(_sd))
    cam_direction = (0.0, -1.0, 0.3) if _sn < 1e-9 else tuple(_sd / _sn)
    try:
        ctx.scene.setup_camera_follow(
            {
                "camera_direction": (
                    float(cam_direction[0]),
                    float(cam_direction[1]),
                    float(cam_direction[2]),
                ),
                "camera_margin_factor": camera_margin,
            }
        )
        ctx.log(
            "FET028 camera-follow: direction=%s margin=%.2f"
            % (tuple(round(float(c), 3) for c in cam_direction), camera_margin)
        )
    except Exception as exc:
        ctx.log("FET028 camera-follow setup failed (ignored): %s" % exc)

    # Capture quality (anti-aliasing, samples-per-pixel, synchronous rendering)
    # is a CORE default applied when the engine starts -- not configured here.
    # If this test ever needs different quality, it would call
    # ``ctx.override_render_settings({...})`` (auto-restored after the test);
    # the core defaults are good for the gripper, so it does not override.

    # Discovery captures precede per-shape histories. Later captures annotate
    # only the current shape's retained observations, never earlier trials.
    motion = None
    motion_joints = {}

    async def _capture(label, stabilize_frames=2):
        """capture_frame wrapper. Advance the camera-follow rig first so the
        moving gripper + grasped object stay framed, then grab the frame."""
        if bool(config.get("disable_capture", False)):
            return None
        try:
            ctx.scene.update_camera_follow(update_history=True)
        except Exception:
            pass
        path = await ctx.capture_frame(label=label, stabilize_frames=stabilize_frames)
        _record_gripper_capture(path, motion, motion_joints)
        return path

    await _capture("discovery")
    if fingertip_set.kind == "independent_fingers":
        # Hand diagnostic keyframe: the hand as loaded, before reorientation.
        await _capture("hand_loaded")

    # 5. Per-shape grasp-and-lift
    # (``gripper_base_path`` and the approach orientation were resolved up
    # front, before the camera, so the framing follows the re-oriented grasp.)
    winning_shape = None
    object_size_m = float(config["object_size_fraction"]) * site.max_opening

    for trial_index, shape in enumerate(config["shapes"]):
        metric_suffix = "" if trial_index == 0 else f"_trial_{trial_index + 1:03d}"
        fingertip_set = _resolve_gripper_dof_names(discovered_fingertips, discovered_dof_names, robot.dof_names)
        carrier = None
        support_pause = None
        native_contact_collector = None
        probe_config = dict(config, _probe_trial_index=trial_index, _probe_trial_shape=str(shape))
        # Predeclared so the ``finally`` block can clean up even if
        # we hit an exception before these are assigned.
        obj = None
        object_edit_target = None
        # Video frames for THIS shape's run. Captured throughout the
        # action phases (open, descend, close, lift, hold) with
        # `stabilize_frames=1` (matches the FET005 grasp video; minimal
        # motion-during-accumulation smear since the timeline keeps running
        # through the stabilize ticks). `ctx.encode_video` consumes the PNGs
        # at the end of the shape iteration.
        video_frames = []
        video_label_prefix = f"{shape}_v"
        # Capture every Nth physics step. Physics runs at 240Hz; we
        # cap video at video_fps_max so the captures/ folder doesn't
        # explode and ffmpeg encoding stays fast. With physics at
        # 240Hz and video_fps_max=20, capture_every = 12 (one frame
        # every 50ms of physics time).
        physics_fps = float(config.get("physics_fps", 240.0))
        video_fps_max = float(config.get("video_fps_max", 20.0))
        video_capture_every = max(1, int(round(physics_fps / max(1.0, video_fps_max))))
        from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver

        motion_name, motion_trial_metadata = _gripper_motion_identity(shape, trial_index)
        motion = MotionObserver(
            ctx,
            motion_name,
            {
                "object_x": {"unit": "stage_length", "source": "existing runtime object pose accessor"},
                "object_y": {"unit": "stage_length", "source": "existing runtime object pose accessor"},
                "object_z": {"unit": "stage_length", "source": "existing runtime object pose accessor"},
                "carrier_x": {"unit": "stage_length", "source": "carrier runtime world position"},
                "carrier_y": {"unit": "stage_length", "source": "carrier runtime world position"},
                "carrier_z": {"unit": "stage_length", "source": "carrier runtime world position"},
                "relative_z": {
                    "unit": "stage_length",
                    "source": "object Z minus carrier Z; not baseline-corrected slip",
                },
                "finger_separation": {"unit": "stage_length", "source": "runtime fingertip link separation"},
            },
            metadata={
                **motion_trial_metadata,
                "clock_basis": "Kit timeline clock, not a solver execution clock",
                "encoded_video_fps": int(round(video_fps_max)),
                "capture_interval_steps": video_capture_every,
                "capture_time_basis": "successful capture after retained observation; not encoded frame time/index",
                "sample_stride": 4,
                "sampling_basis": "every fourth callback and phase transitions",
            },
            sample_stride=4,
        )
        motion_phase = "setup"
        motion_object_reader = None
        motion_joints = {}
        motion_last_targets = None
        joint_observation_incomplete = False

        def _joint_motion_failed(motion_joints=motion_joints):
            nonlocal joint_observation_incomplete
            joint_observation_incomplete = True
            # Mark all affected streams, including contact forces. Later-created
            # streams inherit this flag so a missing early sample is not hidden.
            for observer in motion_joints.values():
                try:
                    observer._warn()
                except Exception:
                    pass

        def _joint_motion(
            targets,
            positions,
            forces=None,
            motion=motion,
            motion_joints=motion_joints,
            shape=shape,
            metric_suffix=metric_suffix,
            trial_index=trial_index,
        ):
            # Called with the actual issued commands and the existing phase
            # readbacks. Contact force is a tip resultant, not actuator effort.
            if motion.history is None:
                return
            nonlocal motion_last_targets
            motion_last_targets = list(targets)
            from simready.foundation.tier_core.runtime_tests.motion_observer import joint_metadata

            for index, spec in enumerate(grasp_specs):
                if index not in motion_joints:
                    try:
                        identity = joint_metadata(
                            stage,
                            asset_prim,
                            str(robot.dof_names[int(spec["idx"])]),
                            root_path=getattr(robot, "prim_path", None),
                        )
                    except Exception:
                        identity = {"unit": "unknown_native", "dof_index": int(spec["idx"]), "identity_resolved": False}
                    joint_name, joint_trial_metadata = _gripper_motion_identity(shape, trial_index, "joint", index)
                    identity.update(joint_trial_metadata, sample_stride=4)
                    unit = identity["unit"]
                    motion_joints[index] = MotionObserver(
                        ctx,
                        joint_name,
                        {
                            "position": {"unit": unit, "source": "grasp phase articulation position readback"},
                            "target": {"unit": unit, "source": "actual sparse position command issued by test"},
                            "error": {"unit": unit, "source": "command minus position"},
                        },
                        metadata=identity,
                        sample_stride=4,
                    )
                position = positions[index] if positions is not None else None
                if joint_observation_incomplete:
                    motion_joints[index]._warn()
                target = float(targets[index])
                motion_joints[index].sample(
                    {
                        "position": position,
                        "target": target,
                        "error": target - position if position is not None else None,
                    },
                    phase=motion_phase,
                )
            if forces is not None and forces:
                if "forces" not in motion_joints:
                    force_name, force_trial_metadata = _gripper_motion_identity(shape, trial_index, "contacts")
                    motion_joints["forces"] = MotionObserver(
                        ctx,
                        force_name,
                        {
                            "tip_%03d"
                            % index: {
                                "unit": "N",
                                "source": "existing fingertip contact-force resultant readback",
                            }
                            for index in range(len(forces))
                        },
                        metadata={
                            **force_trial_metadata,
                            # Read the post-carrier mapping; callbacks are awaited within this trial.
                            "tip_link_paths": list(fingertip_set.tip_link_paths),  # noqa: B023
                            "force_basis": "tip resultant contact force, not actuator torque or force",
                            "sample_stride": 4,
                        },
                        sample_stride=4,
                    )
                motion_joints["forces"].sample(
                    {"tip_%03d" % index: value for index, value in enumerate(forces)}, phase=motion_phase
                )
                if joint_observation_incomplete:
                    motion_joints["forces"]._warn()

        async def _video_capture(
            _i,
            _total=None,
            motion=motion,
            motion_joints=motion_joints,
            video_capture_every=video_capture_every,
            video_label_prefix=video_label_prefix,
            video_frames=video_frames,
        ):
            # Observe independently of video enablement, before captures can
            # introduce extra rendering/timeline ticks. Never step physics here.
            if motion.history is not None:
                try:
                    values = {}
                    object_position = motion_object_reader() if motion_object_reader is not None else None
                    carrier_position = carrier_world_position(carrier) if carrier is not None else None
                    for axis, coordinate in enumerate(("x", "y", "z")):
                        values["object_" + coordinate] = (
                            float(object_position[axis]) if object_position is not None else None
                        )
                        values["carrier_" + coordinate] = (
                            float(carrier_position[axis]) if carrier_position is not None else None
                        )
                    values["relative_z"] = (
                        float(object_position[2] - carrier_position[2])
                        if object_position is not None and carrier_position is not None
                        else None
                    )
                    # This trial's mapping is replaced after carrier attachment, before callbacks run.
                    tip_paths = fingertip_set.tip_link_paths[:2]  # noqa: B023
                    tip_positions = robot.get_link_world_positions(tip_paths) if len(tip_paths) == 2 else {}
                    first = tip_positions.get(tip_paths[0]) if len(tip_paths) == 2 else None
                    second = tip_positions.get(tip_paths[1]) if len(tip_paths) == 2 else None
                    values["finger_separation"] = (
                        float(np.linalg.norm(first - second)) if first is not None and second is not None else None
                    )
                    motion.sample(values, phase=motion_phase)
                except Exception:
                    motion._warn()
                if motion_last_targets is not None and motion_phase in (
                    "preload",
                    "lift",
                    "hold",
                    "shake",
                    "release_wait",
                ):
                    try:
                        _joint_motion(motion_last_targets, _grasp_positions(robot, grasp_specs))
                    except Exception:
                        _joint_motion_failed()
            # `_total` is unused but accepted so the same callback works with
            # `linear_translate(on_substep=cb(i, n))` and `_drive_*(on_step=cb(i))`.
            #
            # Advance the camera-follow rig EVERY physics step (this is the key
            # difference from the other phases that the gripper test was missing
            # -- drive_gain/effort/etc. call update_camera_follow every frame).
            # Updating it only on capture frames let the follow camera jump ~12
            # steps between captures, so each captured frame was grabbed mid-
            # transition -> noise + occasional all-white frames. update_history
            # is advanced only on capture frames (matches drive_gain), so the
            # bbox window does not re-frame every step.
            if bool(config.get("disable_capture", False)):
                return
            is_capture = (_i % video_capture_every) == 0
            try:
                ctx.scene.update_camera_follow(update_history=is_capture)
            except Exception:
                pass
            if not is_capture:
                return
            try:
                # stabilize_frames=1 matches the FET005 grasp video. These
                # frames are captured DURING motion, and capture_frame cannot
                # pause the timeline during its stabilize ticks (pausing
                # crashes the PhysX tensor view), so physics keeps stepping
                # and the gripper moves IN-FRAME while RTX accumulates -- each
                # extra stabilize tick adds motion-during-accumulation =
                # ghosting/noise. 1 tick (FET005's value) converges enough with
                # the least motion smear; 2 (what we had) ghosted. Falsy path on
                # failure is skipped.
                p = await ctx.capture_frame(label=video_label_prefix, stabilize_frames=1)
                if p:
                    video_frames.append(p)
                    _record_gripper_capture(p, motion, motion_joints)
            except Exception:
                pass

        trial_error = None
        try:
            support_pause = _GripperSupportPause(ctx)
            await _reset_world(ctx)
            # Merge the test-owned prismatic rail into the articulation. This
            # is the PhysX path and gives the carrier an addressable DOF.
            _merge_rail = bool(config.get("carrier_merge_rail", True))
            # Capture the DOF name order BEFORE the carrier attaches. When the
            # rail MERGES into the articulation it adds a prismatic DOF, shifting
            # the indices the discovery computed (finger_chains / mimic_master).
            # We remap those by NAME to the post-merge order below so every
            # downstream index use (grasp_specs, open/close detection, grip
            # diagnostics) stays correct.
            _pre_dof_names = list(robot.dof_names)
            carrier = await attach_carrier(
                stage,
                scene_info,
                robot,
                gripper_base_path,
                base_orient_wxyz=(None if scene_info.get("fet028_preoriented") else approach_base_orient),
                ctx=ctx,
                merge_rail=_merge_rail,
            )
            _cur_dof_names = list(robot.dof_names)
            fingertip_set = _resolve_gripper_dof_names(discovered_fingertips, discovered_dof_names, _cur_dof_names)
            if _merge_rail and _pre_dof_names != _cur_dof_names:
                ctx.log(
                    "FET028: remapped grasp DOF indices by name after rail merge "
                    "(dof_count %d -> %d)." % (len(_pre_dof_names), len(_cur_dof_names))
                )
            # Record one readback after stepping in place (no carrier command).
            # This observation aids temporal comparison, but cannot isolate
            # instability, a carrier trigger, or an invalid physics-view cause.
            await _settle_for_seconds(ctx, 0.15, on_step=None)
            _jp_probe = robot.get_joint_positions()
            if _jp_probe is None:
                _st = "unavailable (None)"
            else:
                _arr = np.asarray(_jp_probe)
                _st = "finite(n=%d)" % _arr.size if np.isfinite(_arr).all() else "NON-FINITE/NaN"
            ctx.log(
                "FET028 post-attach in-place settle probe: joint_pos=%s "
                "(readback observation only; finite values do not prove stability "
                "or identify a later trigger. Unavailable/non-finite values can "
                "also indicate an invalid runtime view or setup; compare subsequent "
                "positioning and setup logs before attributing a cause)." % _st
            )
            if fingertip_set.kind == "independent_fingers":
                # Hand diagnostic keyframe: palm reoriented down, after attach.
                await _capture("hand_oriented")
            # Build the grasp actuation spec: the DOF(s) to drive and their
            # per-DOF open/closed joint targets. The open/close/hold drives and
            # the grip diagnostics all operate on this list, so the same code
            # path serves both a single-master parallel jaw and an N-flexor hand.
            #   parallel-jaw -> the single mimic master; the OPEN limit is
            #     detected by fingertip aperture (asset-agnostic) then backed off
            #     the hard limit (the asset's mimic is over-constrained AT the
            #     limit and can pin there).
            #   hand -> closure direction inferred from stepped fingertip
            #     geometry; positioning DOFs retain their original commands.
            grasp_specs = []
            if fingertip_set.kind == "mimic_parallel_jaw":
                open_master_pos, closed_master_pos = await _detect_open_closed_positions(
                    ctx, robot, fingertip_set, stage, probe_config, site.max_opening, gripper_base_path
                )
                _backoff_frac = float(config.get("open_limit_backoff_frac", 0.0))
                open_drive_pos = open_master_pos + (closed_master_pos - open_master_pos) * _backoff_frac
                if _backoff_frac:
                    ctx.log(
                        "FET028 open target backed off the limit: %.4f -> %.4f "
                        "(%.0f%% toward closed)." % (open_master_pos, open_drive_pos, 100.0 * _backoff_frac)
                    )
                _master_indices = list(fingertip_set.mimic_master_dofs or [int(fingertip_set.mimic_master_dof)])
                _lowers, _uppers = robot.get_joint_position_limits()
                for _mi in _master_indices:
                    _mi = int(_mi)
                    _lo = float(_lowers[_mi])
                    _up = float(_uppers[_mi])
                    if not np.isfinite(_lo) or not np.isfinite(_up):
                        raise RuntimeError(
                            "Parallel-jaw leader DOF idx=%d has no finite joint limits "
                            "(lower=%r, upper=%r)." % (_mi, _lo, _up)
                        )
                    _mapping = (fingertip_set.master_open_closed_positions or {}).get(_mi)
                    if _mapping is None:
                        raise RuntimeError("FET028 mapping: no measured endpoint polarity for leader DOF %d" % _mi)
                    _open, _closed = _mapping
                    _open_drive = _open + (_closed - _open) * _backoff_frac
                    grasp_specs.append(
                        {
                            "idx": _mi,
                            "open": float(_open_drive),
                            "closed": float(_closed),
                            "name": robot.dof_names[_mi],
                        }
                    )
                if len(grasp_specs) > 1:
                    ctx.log(
                        "FET028 parallel-jaw control: coordinating %d actuator-owned "
                        "leaders: %s." % (len(grasp_specs), ", ".join(str(spec["name"]) for spec in grasp_specs))
                    )
            else:  # independent_fingers (hand)
                # Runtime/mapping failures must propagate as setup errors,
                # not become asset FAIL based on unrelated static validation.
                grasp_specs, _hand_diagnostics = await _infer_hand_grasp_specs(
                    ctx, robot, fingertip_set, stage, probe_config, grasp_center_for_test, gripper_base_path
                )
                if config.get("hand_trial_controls") and normalize_hand_trial_controls(config["hand_trial_controls"]):
                    controls = normalize_hand_trial_controls(config["hand_trial_controls"])
                    eligible_indices = sorted(
                        {int(index) for chain in fingertip_set.finger_chains or [] for index in chain}
                    )
                    from simready.foundation.tier_core.runtime_tests.articulation_phases.hand_controls import (
                        MAX_HAND_JOINTS,
                    )

                    if len(eligible_indices) > MAX_HAND_JOINTS:
                        raise ValueError("hand trial has too many independently driven joints")
                    identities = _grasp_joint_identities(stage, asset_prim, robot, eligible_indices)
                    grasp_specs = resolve_hand_trial_specs(
                        grasp_specs, controls, identities, robot.get_joint_position_limits()
                    )
                    validate_close_delays(
                        controls, grasp_specs, config["close_steps"], config.get("close_ramp_steps", 300)
                    )
                _closure_indices = {
                    int(spec["idx"])
                    for spec in grasp_specs
                    if spec.get("contact_active", not np.isclose(spec["open"], spec["closed"]))
                }
                _unresolved_branches = [
                    list(chain)
                    for chain in fingertip_set.finger_chains or []
                    if not any(int(index) in _closure_indices for index in chain)
                ]
                if _unresolved_branches:
                    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
                        GripperMappingError,
                    )

                    raise GripperMappingError(
                        "FET028 mapping/setup limitation: no unambiguous closure motion "
                        f"for independent-finger branch DOFs {_unresolved_branches}."
                    )
                ctx.log(
                    "FET028 hand endpoint inference: %s"
                    % [
                        (
                            robot.dof_names[_idx],
                            _role,
                            _endpoint,
                            round(_radial, 6),
                            [round(_value, 6) for _value in _displacement],
                        )
                        for _idx, _role, _endpoint, _radial, _displacement in _hand_diagnostics
                    ]
                )
            if not grasp_specs:
                from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
                    GripperMappingError,
                )

                raise GripperMappingError(
                    f"FET028 mapping/setup limitation: no grasp targets resolved for {site.prim_path}."
                )

            try:
                identities = _grasp_joint_identities(
                    stage, asset_prim, robot, [int(spec["idx"]) for spec in grasp_specs]
                )
                effective_controls = effective_trial_controls(
                    shape,
                    hand_controls,
                    grasp_specs,
                    identities,
                    config,
                    object_size_m,
                    tested_mass_kg,
                    site.max_opening,
                    procedure_defaults=get_defaults(),
                )
                _record_gripper_trial_controls(ctx, effective_controls, trial_index)
            except Exception:
                _optional_contact_warning(
                    ctx, "Gripper trial control evidence unavailable; required controls and criteria are unchanged."
                )

            # 5a-prelude(0). FIRST poise the gripper at a size-based standoff
            # above where the object will be, THEN spawn the object on the floor
            # beneath it. Positioning the gantry before spawning keeps the order
            # unambiguous (the gripper is placed, then the pickup object appears
            # under it) and avoids any confusing raise-then-lower at the start.
            radius = object_size_m / 2.0
            ground_clearance = float(config.get("spawn_ground_clearance_m", 0.005))
            object_center_z = radius + ground_clearance

            # Standoff: how far above the object center the OPEN gripper starts
            # so its fingers clear the object before the descent. Sized from the
            # object (one diameter) plus a margin -- enough headroom for any
            # gripper of this opening class. The gripper descends exactly this
            # far to bring its grasp center to the object center.
            approach_clearance = object_size_m + float(config.get("approach_extra_clearance_m", 0.03))
            grasp_center_world = np.array(
                [
                    float(grasp_center_for_test[0]),
                    float(grasp_center_for_test[1]),
                    object_center_z + approach_clearance,
                ]
            )
            ctx.add_metric(f"grasp_center_initial_z_{shape}", float(grasp_center_world[2]))
            ctx.add_metric(f"approach_clearance_m_{shape}", approach_clearance)

            # SILENT positioning: raise the gantry so the grasp center reaches
            # the standoff height, WITHOUT video capture, so the recorded video
            # does not show a confusing up-move at the start. The recorded
            # action begins with the gripper already poised above the object.
            required_raise = float(grasp_center_world[2]) - float(grasp_center_for_test[2])
            if required_raise > 0.0:

                async def _hold_open_during_positioning(_i, _total=None, grasp_specs=grasp_specs):
                    _command_grasp_targets(robot, grasp_specs, "open")

                _command_grasp_targets(robot, grasp_specs, "open")
                await linear_translate(
                    ctx=ctx,
                    stage=stage,
                    handle=carrier,
                    delta_world=np.array([0.0, 0.0, required_raise]),
                    duration_s=0.6,
                    on_substep=_hold_open_during_positioning,
                )
                await _settle_for_seconds(
                    ctx,
                    0.2,
                    on_step=_hold_open_during_positioning,
                )

            # Restore every temporarily suspended support before enabling the
            # intended pickup floor. No object exists during the free probe.
            support_pause.restore()
            support_pause = None
            _prepare_gripper_ground(ctx)

            # Spawn directly below the authored grasp center. Runtime fingertip
            # measurements must not silently repair or offset site metadata.
            spawn_world = _authored_spawn_position(grasp_center_world, object_center_z)
            if "object_offset_world_xy_m" in hand_controls:
                spawn_world[:2] += hand_object_offset_stage
            if hand_controls:
                spawn_world = np.asarray(_required_trial_geometry(spawn_world, 3, "resolved object spawn"))
            spawn_pose = np.eye(4)
            spawn_pose[3, :3] = spawn_world
            object_edit_target = stage.GetEditTarget()
            obj = spawn_test_object(
                stage=stage,
                parent_path="/World",
                shape=shape,
                size_m=object_size_m,
                mass_kg=tested_mass_kg,
                static_friction=config["static_friction"],
                dynamic_friction=config["dynamic_friction"],
                restitution=config["restitution"],
                pose_world=spawn_pose,
                physics_engine="physx",
            )
            if contact_diagnostics_enabled:
                native_contact_collector = _begin_gripper_contact_diagnostics(
                    # The collector closes before the next trial changes this live phase.
                    ctx,
                    obj.prim_path,
                    fingertip_set.tip_link_paths,
                    lambda: motion_phase,  # noqa: B023
                )

            def _object_position_runtime(obj=obj):
                return _read_object_position(stage, obj.prim_path)

            def _object_xy_runtime():
                return _object_position_runtime()[:2]

            def _object_z_runtime():
                return float(_object_position_runtime()[2])

            motion_object_reader = _object_position_runtime

            ctx.add_metric(f"spawn_center_z_{shape}", float(spawn_world[2]))
            ctx.log(
                "FET028 position[%s]: gripper poised %.3f m above the object "
                "(grasp center z=%.4f, object center z=%.4f); object spawned "
                "beneath it; will descend %.3f m onto it."
                % (
                    shape,
                    approach_clearance,
                    float(grasp_center_world[2]),
                    object_center_z,
                    approach_clearance,
                )
            )

            # DIAGNOSTIC: measure the gripper base's ACTUAL world orientation
            # after the weld + raise. The orient math commands forward_axis ->
            # world -Z for jaws or +X for hands; this observation helps check
            # us whether the FixedJoint applied the commanded rotation, its
            # inverse, or was overridden (base ~ identity) by the articulation
            # root pose. Pure measurement -- no behavior change.
            if approach_base_orient is not None and approach_fwd_in_base is not None:
                from pxr import Gf as _Gf
                from pxr import UsdGeom as _UsdGeom

                _bt = _Gf.Transform(
                    _UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(gripper_base_path))
                )
                _brot = _bt.GetRotation()
                _fnow = _brot.TransformDir(
                    _Gf.Vec3d(
                        float(approach_fwd_in_base[0]),
                        float(approach_fwd_in_base[1]),
                        float(approach_fwd_in_base[2]),
                    )
                ).GetNormalized()
                _bq = _brot.GetQuat()
                _bi = _bq.GetImaginary()
                intended_forward = _intended_approach_direction(approach_base_orient, approach_fwd_in_base)
                ctx.log(
                    "FET028 weld-check[%s]: base world quat (w,x,y,z)="
                    "(%.3f, %.3f, %.3f, %.3f); forward_axis now points world "
                    "(%.3f, %.3f, %.3f) -- configured world direction %s."
                    % (
                        shape,
                        _bq.GetReal(),
                        _bi[0],
                        _bi[1],
                        _bi[2],
                        _fnow[0],
                        _fnow[1],
                        _fnow[2],
                        np.round(intended_forward, 6).tolist(),
                    )
                )

            # Keyframe: gripper poised above the object (start of the recorded
            # action). The positioning move above was silent, so this is the
            # first action frame -- no confusing up-move precedes it.
            await _capture(f"{shape}_positioned")

            # 5a. Open + mapped-target reachability check (early-exit on master-DOF
            # position stall, same robust signal as _drive_to_close).
            motion_phase = "open"
            await _drive_to_open(
                ctx,
                robot,
                grasp_specs,
                fingertip_set,
                config,
                on_step=_video_capture,
                on_motion=_joint_motion,
                on_motion_error=_joint_motion_failed,
            )
            # Capture the gripper state BEFORE the post-open check, so a
            # failure here (most common cause of FET028 setup issues:
            # open/close mapping inverted on a new asset) still produces
            # a frame the user can inspect to see what the gripper did.
            await _capture(f"{shape}_after_open_command")

            # Required live positions establish open-target reachability.
            # Missing, partial or non-finite selected state is a runtime/setup
            # error, never a successful reachability check or asset FAIL.
            # Live link-origin separation remains a diagnostic, not this gate.
            joint_positions = _required_grasp_positions(robot, grasp_specs, "post-open")
            # Per-DOF open check: every grasp DOF must have reached its OPEN
            # target. The worst-offending DOF (largest position error) drives
            # the pass/fail + diagnostic -- catches an unreached mapped target
            # or a stuck flexor on either a jaw (1 DOF) or a hand
            # (N flexors). Required positions come from physics; live link-origin
            # separation is recorded for diagnostics only.
            worst_err, worst_spec, worst_actual = -1.0, grasp_specs[0], 0.0
            for s, actual in zip(grasp_specs, joint_positions, strict=True):
                err = abs(actual - float(s["open"]))
                if err > worst_err:
                    worst_err, worst_spec, worst_actual = err, s, actual
            measured_sep = _measure_finger_separation(robot, fingertip_set)
            ctx.add_metric(f"open_joint_actual_{shape}", worst_actual)
            ctx.add_metric(f"open_joint_expected_{shape}", float(worst_spec["open"]))
            ctx.add_metric(f"open_joint_worst_error_{shape}", worst_err)
            ctx.add_metric(f"measured_separation_after_open_{shape}", measured_sep)

            # Tolerance: 5x the open_position_tolerance (which itself is
            # already conservative) gives a forgiving check that still
            # catches both unreached targets (joint at the opposite limit) and
            # stuck-joint cases (joint near its initial position).
            position_tolerance = 5.0 * float(config["open_position_tolerance"])
            if worst_err > position_tolerance:
                ctx.fail(
                    _fix_message_open_mapping_wrong(
                        joint_name=worst_spec["name"],
                        actual_pos=worst_actual,
                        expected_pos=float(worst_spec["open"]),
                        error=worst_err,
                        tolerance=position_tolerance,
                        shape=shape,
                    ),
                    details={
                        "joint_name": worst_spec["name"],
                        "joint_actual_position": worst_actual,
                        "joint_expected_open_position": float(worst_spec["open"]),
                        "joint_position_error": worst_err,
                        "joint_position_tolerance": position_tolerance,
                        "measured_separation": measured_sep,
                        "max_opening": site.max_opening,
                        "shape": shape,
                    },
                )
                return
            await _capture(f"{shape}_opened")

            async def _hold_open(_i, _total=None, grasp_specs=grasp_specs):
                # Keep commanding 'open' during the settle + descent so the
                # gripper APPROACHES the object open. _drive_to_open stops
                # applying the open action when it returns; re-applying it each
                # step holds the gripper open until it reaches grasp depth and
                # the close phase takes over.
                _command_grasp_targets(robot, grasp_specs, "open")
                await _video_capture(_i, _total)

            # Object was already spawned in the 5a-prelude above; by
            # this point gravity has had the open-phase duration to
            # settle it on the ground. One short settle pass to make
            # sure it's stationary before the descent reads its xy/z.
            await _settle_for_seconds(ctx, 0.2, on_step=_hold_open)
            await _capture(f"{shape}_spawned")

            # Object's SETTLED pose (read now, AFTER it has fallen onto the
            # floor). Use this as the baseline for both the descent target and
            # the contact test -- NOT the spawn pose, which sits a
            # ground-clearance gap higher (the object free-falls that gap on
            # spawn, and comparing against the spawn z made the settling itself
            # look like gripper contact, stopping the descent immediately above
            # the object).
            obj_ref_xy = np.asarray(_object_xy_runtime())
            obj_ref_z = float(_object_z_runtime())
            motion_phase = "descend"

            # 5c.5. Approach: OPEN, descend until the gripper CONTACTS the
            # object, then BACK OFF a little (move up) and close from there.
            # Backing off after contact stops the gripper from pressing the
            # object into the floor -- that press otherwise jams the fingers so
            # they cannot close. Descend in small chunks (holding open) and stop
            # as soon as the object is nudged (z drops or it shifts).
            # Descend so the live finger contact geometry reaches the authored
            # object reference. The site supplies the grasp frame and object
            # placement; the resolved fingertip geometry supplies approach depth.
            site_descent = float(grasp_center_world[2]) - obj_ref_z
            if fingertip_set.kind == "independent_fingers":
                # Bring the lowest open fingertip to the object's lower rim so
                # the independently driven branches surround it before curling.
                # This target comes from the test object's authored size and
                # floor clearance, not a hand- or asset-specific offset.
                rim_target_z = obj_ref_z - radius + ground_clearance
                _tips = _pad_world_tips(robot, stage, fingertip_set.tip_link_paths, (0.0, 0.0, -1.0))
                _tip_z = {p: float(v[2]) for p, v in _tips.items()}
                if _tip_z:
                    descent_max = _hand_cup_descent(min(_tip_z.values()), rim_target_z, 0.0)
                else:
                    descent_max = site_descent
                ctx.log(
                    "FET028 hand descent[%s]: depth=%.4f m (lowest open fingertip "
                    "z=%.4f -> target z=%.4f); site-aligned would be %.4f m."
                    % (shape, descent_max, min(_tip_z.values()) if _tip_z else float("nan"), rim_target_z, site_descent)
                )
            else:
                # A parallel jaw must surround the object before it closes.
                # Align the lowest live corner of the open pad geometry with
                # the object's lower rim.  A whole-link centroid is not the
                # contact end of a four-bar finger and can leave the pads well
                # above the object (the 2F-85 differs by several centimetres).
                # The same live-tip geometry is already used to infer the
                # open/closed endpoint, so this remains backend- and
                # asset-neutral.
                rim_target_z = obj_ref_z - radius
                _tips = _pad_world_tips(
                    robot,
                    stage,
                    fingertip_set.tip_link_paths,
                    (0.0, 0.0, -1.0),
                )
                _tip_z = [float(value[2]) for value in _tips.values()]
                if _tip_z and (min(_tip_z) - rim_target_z) > 1e-3:
                    descent_max = min(_tip_z) - rim_target_z
                else:
                    # Some backends expose link transforms in an
                    # articulation-local frame even though joint state and
                    # relative pad motion are valid.  In that case absolute
                    # tip Z cannot drive placement.  Use an object-sized
                    # conservative fallback: place the authored grasp frame at
                    # the lower rim, leaving the object's full diameter inside
                    # the closing span instead of stopping at its centre.
                    descent_max = float(grasp_center_world[2]) - rim_target_z
                ctx.log(
                    "FET028 descent[%s]: distal-pad depth=%.4f m (lowest open "
                    "pad z=%.4f -> object lower rim z=%.4f); site-aligned "
                    "would be %.4f m."
                    % (
                        shape,
                        descent_max,
                        min(_tip_z) if _tip_z else float("nan"),
                        rim_target_z,
                        site_descent,
                    )
                )
            if hand_controls.get("descent_reference") == "grasp_center":
                descent_max = max(0.0, site_descent)
            if descent_max <= 0.0 and fingertip_set.kind != "independent_fingers":
                ctx.fail(
                    _fix_message_grasp_below_object(
                        grasp_z=float(grasp_center_world[2]),
                        object_z=obj_ref_z,
                    ),
                    details={
                        "grasp_center_world_z": float(grasp_center_world[2]),
                        "object_settled_z": obj_ref_z,
                        "shape": shape,
                    },
                )
                return
            ctx.add_metric(f"descent_total_{shape}", descent_max)

            n_chunks = _descent_chunk_count(
                descent_max,
                int(config.get("descent_contact_chunks", 12)),
                float(config.get("descent_contact_max_step_m", 0.005)),
            )
            chunk = descent_max / n_chunks
            contact_drop = float(config.get("descent_contact_drop_m", 0.003))
            descended = 0.0
            contacted = False
            for _c in range(n_chunks):
                await linear_translate(
                    ctx=ctx,
                    stage=stage,
                    handle=carrier,
                    delta_world=np.array([0.0, 0.0, -chunk]),
                    duration_s=max(0.05, 0.6 / n_chunks),
                    on_substep=_hold_open,
                )
                descended += chunk
                obj_z_now = _object_z_runtime()
                obj_xy_now = np.asarray(_object_xy_runtime())
                xy_shift = float(np.linalg.norm(obj_xy_now - obj_ref_xy))
                motion_contact = obj_z_now < obj_ref_z - contact_drop or xy_shift > contact_drop
                if motion_contact:
                    contacted = True
                    ctx.log(
                        "FET028 descent object-motion proxy[%s] after %.4f m ("
                        "object z=%.4f, settled z=%.4f, xy_shift=%.4f) -- stopping descent."
                        % (shape, descended, obj_z_now, obj_ref_z, xy_shift)
                    )
                    break
            # Retain the established PhysX endpoint settle and capture timing.
            await _settle_for_seconds(ctx, 0.1, on_step=_hold_open)

            # Contact may occur during the endpoint settle rather than during
            # the ramp itself.  Re-read the object after the rail has converged
            # so that contact relief is based on the actual final pose.
            if not contacted:
                obj_z_now = _object_z_runtime()
                obj_xy_now = np.asarray(_object_xy_runtime())
                xy_shift = float(np.linalg.norm(obj_xy_now - obj_ref_xy))
                motion_contact = obj_z_now < obj_ref_z - contact_drop or xy_shift > contact_drop
                if motion_contact:
                    contacted = True
                    ctx.log(
                        "FET028 descent object-motion proxy[%s] during endpoint settle after "
                        "%.4f m (object z=%.4f, settled z=%.4f, "
                        "xy_shift=%.4f)." % (shape, descended, obj_z_now, obj_ref_z, xy_shift)
                    )
                else:
                    ctx.log(
                        "FET028 descent[%s] reached grasp depth (%.4f m) with no "
                        "object nudge detected; closing at that depth." % (shape, descended)
                    )

            if fingertip_set.kind == "independent_fingers":
                # Open cup positioned around the object with clearance (no
                # contact) -- diagnostic still before the fingers flex.
                await _capture("hand_cup_positioned")

            # Back off (UP) to relieve the contact before closing. The hand's cup
            # descent already stops a clearance gap short of the object (no
            # contact to relieve), and backing off would lift the open fingertips
            # off the equator, so the hand does not back off.
            if fingertip_set.kind == "independent_fingers" or not contacted:
                backoff_up = 0.0
            else:
                backoff_up = config.get("contact_backoff_m", None)
                backoff_up = 0.10 * float(site.max_opening) if backoff_up is None else float(backoff_up)
            if backoff_up > 0.0:
                await linear_translate(
                    ctx=ctx,
                    stage=stage,
                    handle=carrier,
                    delta_world=np.array([0.0, 0.0, backoff_up]),
                    duration_s=0.3,
                    on_substep=_hold_open,
                )
                await _settle_for_seconds(ctx, 0.1, on_step=_hold_open)
            ctx.add_metric(f"descent_contacted_{shape}", bool(contacted))
            ctx.add_metric(f"contact_backoff_m_{shape}", backoff_up)
            if backoff_up > 0.0:
                ctx.log(
                    "FET028 backed off %.4f m up after contact (gripper fully "
                    "open); now closing from there." % backoff_up
                )
            else:
                ctx.log("FET028 closing at the reached grasp depth without contact backoff.")
            # DIAGNOSTIC: grasp-DOF positions at the END of descent, right before
            # the close phase. Each DOF near its OPEN target means the hold
            # worked and the gripper arrived OPEN; near the CLOSED target means
            # it drifted closed during the approach despite the re-applied open
            # command.
            _pc = robot.get_joint_positions()
            if _pc is not None:
                ctx.log(
                    "FET028 pre-close[%s]: (dof, pos, open, closed)=%s -- want "
                    "pos ~open."
                    % (
                        shape,
                        [
                            (s["name"], round(float(_pc[int(s["idx"])]), 4), round(s["open"], 4), round(s["closed"], 4))
                            for s in grasp_specs
                        ],
                    )
                )
            object_pre_close_xy = _object_xy_runtime()
            object_pre_close_z = _object_z_runtime()
            await _capture(f"{shape}_engaged")

            # 5d. Close. Uses the asset's authored drive parameters
            # (stiffness, maxForce, damping) as-is -- no runtime
            # boost, no USD edits. The resolved payload can be authored or
            # heuristic; a failed grasp does not establish a rated capability
            # or identify drive tuning as its cause.
            # ``close_contact`` is the existing engagement/stall proxy: at least
            # one grasp DOF moved off open and remained short of its closed
            # target. Other obstructions/setup can produce the same observation,
            # so it does not identify a contacted body. It gates the lift.
            motion_phase = "close"
            close_contact = await _drive_to_close(
                ctx,
                robot,
                grasp_specs,
                fingertip_set,
                config,
                on_step=_video_capture,
                on_motion=_joint_motion,
                on_motion_error=_joint_motion_failed,
            )
            grasp_search_depth = 0.0
            if not close_contact and fingertip_set.kind != "independent_fingers":
                search_attempts = max(0, int(config.get("grasp_depth_search_attempts", 4)))
                search_step = radius * float(config.get("grasp_depth_search_step_radius_fraction", 0.5))
                for search_attempt in range(1, search_attempts + 1):
                    motion_phase = "retry_%d_open_descend" % search_attempt
                    ctx.log(
                        "FET028 grasp-depth search[%s]: close reached its limit "
                        "without satisfying the stall proxy; reopening and descending %.4f m "
                        "(attempt %d/%d)." % (shape, search_step, search_attempt, search_attempts)
                    )
                    await _drive_to_open(
                        ctx,
                        robot,
                        grasp_specs,
                        fingertip_set,
                        config,
                        on_step=_video_capture,
                        on_motion=_joint_motion,
                        on_motion_error=_joint_motion_failed,
                    )
                    await linear_translate(
                        ctx=ctx,
                        stage=stage,
                        handle=carrier,
                        delta_world=np.array([0.0, 0.0, -search_step]),
                        duration_s=0.3,
                        on_substep=_hold_open,
                    )
                    await _settle_for_seconds(
                        ctx,
                        0.1,
                        on_step=_hold_open,
                    )
                    grasp_search_depth += search_step
                    await _capture(f"{shape}_grasp_search_{search_attempt}")
                    motion_phase = "retry_%d_close" % search_attempt
                    close_contact = await _drive_to_close(
                        ctx,
                        robot,
                        grasp_specs,
                        fingertip_set,
                        config,
                        on_step=_video_capture,
                        on_motion=_joint_motion,
                        on_motion_error=_joint_motion_failed,
                    )
                    if close_contact:
                        ctx.log(
                            "FET028 grasp-depth search[%s]: stall/engagement proxy satisfied "
                            "after %.4f m additional descent." % (shape, grasp_search_depth)
                        )
                        break
            ctx.add_metric(f"grasp_depth_search_m_{shape}", grasp_search_depth)
            ctx.add_metric(f"close_blocked_by_object_{shape}", bool(close_contact))

            # Diagnose how the close actually ended, per DOF: a DOF near its
            # CLOSED target reached that target; a DOF stalled short may have
            # encountered an object, a constraint, or a setup limitation. This
            # diagnostic is not measured contact. Fraction = 0 at open, 1 at
            # closed, using the signed range. Held/unmeasured DOFs have no fraction.
            try:
                joint_positions = robot.get_joint_positions()
                if joint_positions is not None:
                    fractions = []
                    for s in grasp_specs:
                        raw_close = joint_positions[int(s["idx"])]
                        actual_close = float(raw_close) if raw_close is not None else None
                        if actual_close is not None and not math.isfinite(actual_close):
                            actual_close = None
                        frac = _closed_fraction(actual_close, s["open"], s["closed"])
                        fractions.append(frac)
                        ctx.add_metric(f"close_joint_actual_{shape}_{s['name']}", actual_close)
                    measured_fractions = [fraction for fraction in fractions if fraction is not None]
                    mean_frac = float(np.mean(measured_fractions)) if measured_fractions else None
                    ctx.add_metric(f"close_joint_fraction_{shape}", mean_frac)
                    ctx.log(
                        "Close ended: per-DOF closed-fraction=%s (mean %s; unmeasured/held=None) -- %s"
                        % (
                            [round(f, 2) if f is not None else None for f in fractions],
                            "%.0f%%" % (100.0 * mean_frac) if mean_frac is not None else "n/a",
                            (
                                "stall/engagement proxy satisfied (not measured contact)"
                                if close_contact
                                else "stall/engagement proxy not satisfied; inspect reopening and setup"
                            ),
                        )
                    )
            except Exception as exc:
                ctx.log("Close diagnostic skipped: %s" % exc)

            # Cube-vs-gripper diagnostic: did the close actually capture
            # the object, or did it knock it loose? After close, the
            # cube's xy should still be near the gripper's xy (cube
            # didn't slide out laterally), and the cube's z should be
            # close to the spawn z (didn't rocket up or fall through).
            try:
                object_pos = _object_position_runtime()
                grip_xy = carrier_world_position(carrier)
                object_lateral_drift = float(
                    np.linalg.norm(np.array([object_pos[0] - grip_xy[0], object_pos[1] - grip_xy[1]]))
                )
                object_z_drift_from_spawn = float(object_pos[2] - spawn_world[2])
                ctx.add_metric(f"object_lateral_drift_after_close_{shape}", object_lateral_drift)
                ctx.add_metric(f"object_z_drift_from_spawn_after_close_{shape}", object_z_drift_from_spawn)
                ctx.log(
                    "After close: object_world=(%.3f, %.3f, %.3f), "
                    "spawn_z=%.3f, lateral_drift_from_gripper_xy=%.3f, "
                    "z_drift_from_spawn=%.3f"
                    % (
                        object_pos[0],
                        object_pos[1],
                        object_pos[2],
                        spawn_world[2],
                        object_lateral_drift,
                        object_z_drift_from_spawn,
                    )
                )
                if object_lateral_drift > 3.0 * (object_size_m / 2.0):
                    ctx.warn(
                        "Object drifted laterally %.3f m from the "
                        "gripper's xy (more than 3x object radius) "
                        "during close. This carrier-axis drift alone does "
                        "not establish an asset defect or excessive drive "
                        "gain. Check placement, grasp depth, reopening, "
                        "resolved payload, contact proxies, and backend "
                        "setup before attributing a cause or changing gains." % object_lateral_drift
                    )
            except Exception as exc:
                ctx.log("Cube-position diagnostic skipped: %s" % exc)

            motion_phase = "preload"
            await _settle_for_seconds(
                ctx,
                config["close_settle_seconds"],
                on_step=_video_capture,
            )

            object_pre_lift_z = _object_z_runtime()
            carrier_pre_lift_z = _read_carrier_z(stage, carrier)
            await _capture(f"{shape}_closed")

            # 5d.5. Grip gate: only lift once the gripper has actually grasped
            # the object. Geometric + stall proxy for "all fingers in contact":
            #   - close_contact: the close stalled on the object (jammed below
            #     the joint's hard stop) rather than meeting in empty space;
            #   - object_retained: the object is still near its authored grasp
            #     location (within one object size of its spawn XY), i.e.
            #     the close did not knock it out.
            # If either fails the gripper is holding nothing, so lifting would
            # just raise an empty gripper -- fail honestly here instead of
            # "lifting" and reporting a slipped object.
            object_at_grip = _object_position_runtime()
            grip_lateral = _lateral_distance(object_at_grip, spawn_world)
            retain_tol = object_size_m
            object_retained = grip_lateral <= retain_tol
            ctx.add_metric(f"grip_confirmed_contact_{shape}", bool(close_contact))
            ctx.add_metric(f"grip_object_retained_{shape}", bool(object_retained))
            if not (close_contact and object_retained):
                ctx.fail(
                    "FET028 grasp not established on shape '%s' -- not lifting.\n"
                    "The configured grasp proxies did not establish a grasp.\n"
                    "These checks do not prove physical finger contacts:\n"
                    "  - close stall/engagement proxy: %s\n"
                    "  - object retained near spawn XY (lateral %.3f m <= "
                    "retain tolerance %.3f m): %s\n"
                    "This outcome alone does not establish an asset defect.\n"
                    "Inspect %s placement, grasp depth, actual reopening,\n"
                    "resolved payload, and the proxy/backend setup using the\n"
                    "%s_closed / %s_engaged captures and motion histories.\n"
                    "Missing contact-force readings are unmeasured, not zero."
                    % (
                        shape,
                        close_contact,
                        grip_lateral,
                        retain_tol,
                        object_retained,
                        shape,
                        shape,
                        shape,
                    ),
                    details={
                        "shape": shape,
                        "close_contact": bool(close_contact),
                        "object_retained": bool(object_retained),
                        "grip_lateral_m": grip_lateral,
                        "object_size_m": object_size_m,
                    },
                )
                return
            ctx.log(
                "FET028 grasp-proxies-satisfied[%s]: stall/engagement=%s, object retained "
                "(lateral %.3f m) -- starting lift." % (shape, close_contact, grip_lateral)
            )

            # 5e. Lift via the gantry's prismatic Z drive.
            motion_phase = "lift"
            #
            # ``linear_translate`` smoothly ramps the prismatic drive's
            # target position. PhysX integrates the motion (real
            # continuous velocity, not teleport) so held objects follow
            # via friction. The gripper base is rigidly attached to
            # gantry_z via the attach_joint FixedJoint, so the entire
            # gripper articulation rides along.
            lift_fps = int(config.get("lift_fps", 240))
            half_dt = float(config["lift_duration_s"]) * 0.5
            await linear_translate(
                ctx=ctx,
                stage=stage,
                handle=carrier,
                delta_world=np.array([0.0, 0.0, float(config["lift_delta_z"]) * 0.5]),
                duration_s=half_dt,
                fps=lift_fps,
                on_substep=_video_capture,
            )
            await _capture(f"{shape}_mid_lift")
            await linear_translate(
                ctx=ctx,
                stage=stage,
                handle=carrier,
                delta_world=np.array([0.0, 0.0, float(config["lift_delta_z"]) * 0.5]),
                duration_s=half_dt,
                fps=lift_fps,
                on_substep=_video_capture,
            )
            motion_phase = "hold"
            await _settle_for_seconds(
                ctx,
                config["hold_duration_s"],
                on_step=_video_capture,
            )
            await _capture(f"{shape}_lifted")

            carrier_post_lift_z = _read_carrier_z(stage, carrier)
            actual_translate = carrier_post_lift_z - carrier_pre_lift_z
            commanded_translate = float(config["lift_delta_z"])
            min_lift = float(config.get("min_lift_for_eval_m", 0.10))
            # The grasp verdict below is measured against the gantry's ACTUAL
            # lift, so a partial lift (a heavier gripper + payload makes the
            # gantry drive lag the commanded lift_delta_z) is fine to judge
            # against. Only fail if the gantry barely moved -- i.e. the rig
            # could not produce a meaningful lift to test holding against
            # gravity. The observation alone does not isolate a drive, carrier,
            # runtime-view or attachment cause.
            if not np.isfinite(actual_translate):
                raise RuntimeError("FET028 setup: test-owned gantry lift readback is unavailable/non-finite")
            if actual_translate < min_lift:
                raise RuntimeError(
                    "FET028 setup: test-owned gantry lifted only %.4f m (need at\n"
                    "least %.4f m to evaluate the grasp; commanded %.4f m). The\n"
                    "gantry is the test-owned prismatic Z-axis carrier authored\n"
                    "by ``attach_carrier()``, not the asset. A meaningful lift\n"
                    "was not produced; the grasp cannot be evaluated. Inspect\n"
                    "required readbacks, carrier targets, body mappings and\n"
                    "setup before attributing a cause or changing controls."
                    % (actual_translate, min_lift, commanded_translate)
                )
            if abs(actual_translate - commanded_translate) > float(config["carrier_translate_tolerance_m"]):
                # Partial lift: the carrier moved enough to evaluate against
                # its actual lift. Report the lag without attributing a cause.
                ctx.warn(
                    "FET028 gantry lift lagged the command (actual %.4f m vs "
                    "commanded %.4f m); grasp is evaluated against the actual "
                    "lift; this observation does not isolate a setup, drive "
                    "or payload cause." % (actual_translate, commanded_translate)
                )

            object_post_lift = _object_position_runtime()
            result = evaluate_pass_criterion(
                object_pre_close_xy=object_pre_close_xy,
                object_pre_close_z=object_pre_close_z,
                object_pre_lift_z=object_pre_lift_z,
                object_post_lift=object_post_lift,
                carrier_pre_lift_z=carrier_pre_lift_z,
                carrier_post_lift_z=carrier_post_lift_z,
                config=config,
            )

            ctx.add_metric(f"vertical_follow_dz_m_{shape}", result.vertical_follow_dz)
            ctx.add_metric(f"horizontal_drift_m_{shape}", result.horizontal_drift)
            ctx.add_metric(f"pre_load_dz_m_{shape}", result.pre_load_dz)
            pre_load_warn = float(config["pre_load_max_dz"])
            if result.pre_load_dz >= pre_load_warn:
                ctx.warn(
                    "FET028 closure moved the %s vertically by %.4f m before "
                    "the carrier lift (diagnostic threshold %.4f m). This is "
                    "not a failure by itself; carrier-follow, shake, and "
                    "release determine whether the grasp is valid." % (shape, result.pre_load_dz, pre_load_warn)
                )

            # 5f. Shake: oscillate the gantry Z to perturb the grip.
            motion_phase = "shake"
            # The object must stay in the gripper (object_min_z stays
            # above the threshold AND its relative slip vs the gripper
            # stays below ``shake_max_relative_slip_m``) for the test
            # to keep claiming a successful lift.
            shake_min_z = float(object_post_lift[2])
            shake_max_rel_slip = 0.0
            if bool(config.get("enable_shake", True)) and result.passed:
                shake_amp = float(config.get("shake_amplitude_m", 0.02))
                shake_freq = float(config.get("shake_frequency_hz", 2.0))
                shake_dur = float(config.get("shake_duration_s", 2.0))
                shake_min_z_thresh = float(config.get("shake_min_z_threshold_m", 0.02))
                shake_slip_thresh = float(config.get("shake_max_relative_slip_m", 0.03))
                ctx.log(
                    "Shake: amplitude=%.3fm freq=%.1fHz duration=%.1fs "
                    "(testing grip robustness)" % (shake_amp, shake_freq, shake_dur)
                )
                # Baseline gripper-to-object Z offset at the start of
                # shake. While shaking, both gripper and object move
                # together if the grip holds; if the object slips,
                # its z drifts down relative to the gripper.
                gripper_pre_shake_z = _read_carrier_z(stage, carrier)
                offset_pre_shake = float(object_post_lift[2]) - gripper_pre_shake_z

                async def _shake_video(_i, _total=None, carrier=carrier, offset_pre_shake=offset_pre_shake):
                    """Track object min z + relative slip vs gripper during shake."""
                    nonlocal shake_min_z, shake_max_rel_slip
                    # These readings determine retention, not optional plots.
                    # Missing/nonfinite state must stop evaluation, never retain
                    # the initial minimum and invented zero-slip as a false pass.
                    obj_z = _object_z_runtime()
                    gripper_z = _read_carrier_z(stage, carrier)
                    if obj_z < shake_min_z:
                        shake_min_z = obj_z
                    rel_slip = abs((obj_z - gripper_z) - offset_pre_shake)
                    if rel_slip > shake_max_rel_slip:
                        shake_max_rel_slip = rel_slip
                    await _video_capture(_i, _total)

                await shake_gantry_z(
                    ctx,
                    stage,
                    carrier,
                    amplitude=shake_amp,
                    frequency_hz=shake_freq,
                    duration_s=shake_dur,
                    on_step=_shake_video,
                )
                await _capture(f"{shape}_shaken")
                ctx.add_metric(f"shake_object_min_z_{shape}", shake_min_z)
                ctx.add_metric(f"shake_max_relative_slip_m_{shape}", shake_max_rel_slip)
                shake_held_above_floor = shake_min_z >= shake_min_z_thresh
                shake_no_slip = shake_max_rel_slip <= shake_slip_thresh
                shake_passed = shake_held_above_floor and shake_no_slip
                ctx.add_metric(f"shake_passed_{shape}", shake_passed)
                if shake_passed:
                    ctx.log(
                        "Shake: HELD through perturbation "
                        "(object_min_z=%.4f >= %.4f, "
                        "max_relative_slip=%.4f <= %.4f)"
                        % (
                            shake_min_z,
                            shake_min_z_thresh,
                            shake_max_rel_slip,
                            shake_slip_thresh,
                        )
                    )
                else:
                    reasons = []
                    if not shake_held_above_floor:
                        reasons.append("object reached floor (min_z=%.4f < %.4f)" % (shake_min_z, shake_min_z_thresh))
                    if not shake_no_slip:
                        reasons.append(
                            "object slipped %.4f m relative to gripper "
                            "(threshold %.4f m)" % (shake_max_rel_slip, shake_slip_thresh)
                        )
                    ctx.log("Shake: LOST THE OBJECT during perturbation -- %s" % "; ".join(reasons))
                    result = PassCriterion(
                        passed=False,
                        vertical_follow_dz=result.vertical_follow_dz,
                        horizontal_drift=result.horizontal_drift,
                        pre_load_dz=result.pre_load_dz,
                    )

            # 5g. Drop: open the gripper and verify the held object
            # actually falls when commanded to. This test is for the
            # asset's *release* capability -- if the gripper can't
            # open, the object stays in grip and ``drop_passed=False``.
            if bool(config.get("enable_drop", True)) and result.passed:
                motion_phase = "release"
                ctx.log("Drop: commanding gripper to open")
                pre_drop_z = _object_z_runtime()
                # Open via the same grasp_specs we used to close; this drives
                # every grasp DOF back to its open target to release the object.
                await _drive_to_open(
                    ctx,
                    robot,
                    grasp_specs,
                    fingertip_set,
                    config,
                    on_step=_video_capture,
                    on_motion=_joint_motion,
                    on_motion_error=_joint_motion_failed,
                )
                motion_phase = "release_wait"
                await _settle_for_seconds(
                    ctx,
                    float(config.get("drop_wait_s", 1.0)),
                    on_step=_video_capture,
                )
                await _capture(f"{shape}_dropped")
                post_drop_z = _object_z_runtime()
                drop_dz = pre_drop_z - post_drop_z
                drop_threshold = float(config.get("drop_min_dz_m", 0.05))
                drop_passed = drop_dz >= drop_threshold
                ctx.add_metric(f"drop_pre_z_{shape}", pre_drop_z)
                ctx.add_metric(f"drop_post_z_{shape}", post_drop_z)
                ctx.add_metric(f"drop_dz_{shape}", drop_dz)
                ctx.add_metric(f"drop_passed_{shape}", drop_passed)
                ctx.log(
                    "Drop result: object_z went %.4f -> %.4f (drop=%.4fm "
                    "vs threshold=%.4fm) -- %s"
                    % (
                        pre_drop_z,
                        post_drop_z,
                        drop_dz,
                        drop_threshold,
                        "RELEASED cleanly" if drop_passed else "did NOT release",
                    )
                )
                if not drop_passed:
                    result = PassCriterion(
                        passed=False,
                        vertical_follow_dz=result.vertical_follow_dz,
                        horizontal_drift=result.horizontal_drift,
                        pre_load_dz=result.pre_load_dz,
                    )

            motion.finish("shape_trial_completed")
            for joint_motion in motion_joints.values():
                joint_motion.finish("shape_trial_completed")
            if result.passed:
                winning_shape = shape
                break
            await _capture(f"{shape}_failed")

        except BaseException as error:
            trial_error = error
            raise
        finally:
            await _cleanup_gripper_trial(
                ctx,
                stage,
                carrier=carrier,
                support_pause=support_pause,
                obj=obj,
                object_edit_target=object_edit_target,
                contact_collector=native_contact_collector,
                contact_enabled=contact_diagnostics_enabled,
                contact_metric="native_contact_diagnostics" + metric_suffix,
                stop_reason=(
                    "cancelled"
                    if isinstance(trial_error, asyncio.CancelledError)
                    else "failed" if trial_error is not None or winning_shape != shape else "completed"
                ),
                video_frames=video_frames,
                video_fps=video_fps_max,
                shape=shape,
                original_error=trial_error,
            )

    if winning_shape is None:
        ctx.fail(
            _fix_message_failed_to_lift(
                tested_mass_kg=tested_mass_kg,
                used_heuristic=used_heuristic,
                shapes_attempted=list(config["shapes"]),
                payload_mass_fraction=float(config["payload_mass_fraction"]),
            ),
            details={
                "tested_object_mass_kg": tested_mass_kg,
                "used_heuristic_payload": used_heuristic,
                "shapes_attempted": list(config["shapes"]),
            },
        )
    else:
        ctx.add_metric("winning_shape", winning_shape)


async def _reset_world(ctx):
    """Clear FET028-managed prims between shape attempts and advance
    one physics step so the tensor backend re-syncs.

    KitEngineProxy does not expose a ``reset_world`` method (a future
    SceneHandle/EngineSession enhancement could add one); FET005's
    pattern of ``physics.stop(); physics.play()`` requires a
    PhysicsHandle that this test does not own. We instead remove the
    two FET028-owned root prims:

    * ``/World/_FET028`` -- carrier subtree (the previous iteration's
      ``finally`` block already detaches its carrier; this is belt-
      and-suspenders for crash paths).
    * ``/World/_FET028_Objects`` -- the legacy fixed object namespace.
      Current trials use unique namespaces and verified required per-trial
      cleanup. This legacy helper is not a replacement for that cleanup and
      does not remove current uniquely named objects.

    The trailing ``physics_step`` call flushes pending USD changes to
    the PhysX/tensor backend so subsequent state queries see the
    cleaned stage (project memory: tensor reads need one frame after
    world.reset before they are reliable).
    """
    import omni.usd
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_carrier import (
        _GANTRY_ROOT,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.object_spawning import (
        _OBJECTS_ROOT,
    )

    stage = omni.usd.get_context().get_stage()
    if stage is not None:
        for path in (_GANTRY_ROOT, _OBJECTS_ROOT):
            prim = stage.GetPrimAtPath(path)
            if prim and prim.IsValid():
                stage.RemovePrim(path)
    await ctx.step_one()


def _authored_spawn_position(grasp_center_world, object_center_z):
    """Object center directly below the authored grasp center, without repair."""
    center = np.asarray(grasp_center_world, dtype=np.float64)
    return np.array([float(center[0]), float(center[1]), float(object_center_z)], dtype=np.float64)


def _lateral_distance(first, second):
    """XY distance between two world positions."""
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    return float(np.linalg.norm(a[:2] - b[:2]))


def _resolve_gripper_base_path(stage, site_prim_path: str):
    """Return the prim path of the gripper's base body (the wrist/palm).

    The gripper site is conventionally authored under the wrist/palm body.
    Naive resolution -- "first RigidBodyAPI ancestor" -- works in the
    conventional case but fails when the site is authored under a finger
    pad (rare but possible): the carrier would attach to the finger and
    the gripper's palm would still float free.

    Strategy:
      1. Walk ancestors collecting every RigidBodyAPI hit.
      2. Prefer the closest ancestor that has at least one RigidBody
         descendant (other than itself) -- that body has fingers under it,
         so it's a base, not a tip.
      3. Fall back to the closest RigidBodyAPI ancestor if no candidate has
         body descendants (single-body assets, or tip-only authoring).
      4. Return None if no RigidBodyAPI ancestor exists at all.
    """
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(site_prim_path)
    if not prim or not prim.IsValid():
        return None

    rigid_ancestors = []
    walker = prim.GetParent()
    while walker and walker.IsValid() and walker.GetPath() != walker.GetPath().GetParentPath():
        if walker.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_ancestors.append(walker)
        walker = walker.GetParent()

    if not rigid_ancestors:
        return None

    # Prefer a body that has further articulated children (fingers).
    for body in rigid_ancestors:
        if _has_rigid_body_descendant(body):
            return str(body.GetPath())

    # No multi-body candidate found -- fall back to the closest body.
    return str(rigid_ancestors[0].GetPath())


def _has_rigid_body_descendant(body_prim) -> bool:
    """Return True if any descendant of ``body_prim`` has UsdPhysics.RigidBodyAPI.

    Used to distinguish "base" bodies (which have child links -- finger chains)
    from leaf bodies (finger pads). Walks via ``Usd.PrimRange`` and returns
    early on the first descendant hit.
    """
    from pxr import Usd, UsdPhysics

    for desc in Usd.PrimRange(body_prim):
        if desc == body_prim:
            continue
        if desc.HasAPI(UsdPhysics.RigidBodyAPI):
            return True
    return False


def _pad_world_tips(robot, stage, paths, approach_world):
    """Live distal geometry of resolved pads, excluding other bodies/guides."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        live_pad_tips,
    )

    return live_pad_tips(robot, stage, paths, approach_world)


def _hand_cup_descent(lowest_fingertip_z, object_center_z, clearance_m):
    """Descent so the lowest open fingertip reaches the object reference.

    ``clearance_m`` retains a generic caller-controlled separation. The result
    is never negative when the fingertip is already at or below the target.
    """
    return max(0.0, float(lowest_fingertip_z) - (float(object_center_z) + float(clearance_m)))


async def _detect_open_closed_positions(ctx, robot, fingertip_set, stage, config, max_opening, base_path=None):
    """Infer live geometry and a separate OPEN/CLOSED convention per leader.

    GR.003 defines a tube axis, never a jaw-endpoint pair. Rest targets and
    link names do not establish polarity. Sparse drive probes and restoration
    are owned by Core; ambiguity remains an explicit mapping/setup limitation.
    """
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        map_parallel_endpoints,
    )

    mappings, paths = await map_parallel_endpoints(ctx, robot, fingertip_set, stage, config, max_opening, base_path)
    fingertip_set.master_open_closed_positions = mappings
    fingertip_set.tip_link_paths = paths
    return mappings[int(fingertip_set.mimic_master_dof)]


def _command_grasp_targets(robot, grasp_specs, key, target_values=None):
    """Command only the selected grasp DOFs.

    PhysX receives sparse selected grasp commands. An
    explicit selection is essential for FET028: a full finger vector would
    also overwrite the independently commanded test-carrier actuator.
    """
    if target_values is None:
        target_values = [float(spec[key]) for spec in grasp_specs]
    if len(target_values) != len(grasp_specs):
        raise ValueError("target_values must match grasp_specs")
    from isaacsim.core.utils.types import ArticulationAction

    robot.apply_action(
        ArticulationAction(
            joint_positions=np.asarray(target_values, dtype=np.float32),
            joint_indices=np.asarray([int(spec["idx"]) for spec in grasp_specs], dtype=np.int32),
        )
    )


def _grasp_positions(robot, grasp_specs):
    """Current joint positions of the grasp DOFs (list, spec order), or None."""
    pos = robot.get_joint_positions()
    if pos is None:
        return None
    values = [float(pos[int(s["idx"])]) for s in grasp_specs]
    return values if np.isfinite(values).all() else None


def _required_grasp_positions(robot, grasp_specs, observation):
    """Finite selected live state for verdicts; failures are setup/runtime errors."""
    try:
        return validate_selected_native_positions(
            robot.get_joint_positions(), robot.dof_count, [spec["idx"] for spec in grasp_specs]
        )
    except (IndexError, KeyError, OverflowError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"FET028 setup: required {observation} joint readback is unavailable/invalid: {exc}"
        ) from exc


@dataclass(frozen=True)
class _GripperDofNames:
    """Immutable discovery identities, independent of changing native indices."""

    master: str | None
    masters: tuple[str, ...] | None
    follower: str | None
    chains: tuple[tuple[str, ...], ...] | None


def _capture_gripper_dof_names(fingertips, dof_names):
    names = tuple(dof_names)

    def _name(index):
        if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index < len(names):
            raise RuntimeError("FET028 setup: discovered gripper DOF index is invalid")
        name = names[index]
        if not isinstance(name, str) or not name or names.count(name) != 1:
            raise RuntimeError("FET028 setup: discovered gripper DOF name is missing/ambiguous")
        return name

    return _GripperDofNames(
        master=_name(fingertips.mimic_master_dof) if fingertips.mimic_master_dof is not None else None,
        masters=(
            tuple(_name(index) for index in fingertips.mimic_master_dofs)
            if fingertips.mimic_master_dofs is not None
            else None
        ),
        follower=_name(fingertips.mimic_follower_dof) if fingertips.mimic_follower_dof is not None else None,
        chains=(
            tuple(tuple(_name(index) for index in chain) for chain in fingertips.finger_chains)
            if fingertips.finger_chains is not None
            else None
        ),
    )


def _resolve_gripper_dof_names(template, identities, dof_names):
    """Fresh per-trial metadata; required identities never fall back to indices."""
    names = tuple(dof_names)

    def _index(name):
        if names.count(name) != 1:
            raise RuntimeError(f"FET028 setup: required gripper DOF name {name!r} is missing/ambiguous")
        return names.index(name)

    resolved = copy.deepcopy(template)
    resolved.mimic_master_dof = _index(identities.master) if identities.master is not None else None
    resolved.mimic_master_dofs = (
        [_index(name) for name in identities.masters] if identities.masters is not None else None
    )
    # A follower is diagnostic metadata, never a sparse command target. If a
    # rebuilt SDK hides it, preserve absence rather than an obsolete index.
    resolved.mimic_follower_dof = (
        names.index(identities.follower)
        if identities.follower is not None and names.count(identities.follower) == 1
        else None
    )
    resolved.finger_chains = (
        [[_index(name) for name in chain] for chain in identities.chains] if identities.chains is not None else None
    )
    return resolved


def _intended_approach_direction(base_orient_wxyz, forward_in_base):
    """Diagnostic target from the resolved approach, without another pose read."""
    from pxr import Gf

    w, x, y, z = (float(value) for value in base_orient_wxyz)
    rotation = Gf.Rotation(Gf.Quatd(w, Gf.Vec3d(x, y, z)))
    return np.asarray(rotation.TransformDir(Gf.Vec3d(*(float(value) for value in forward_in_base))))


def _gripper_motion_identity(shape, trial_index, kind="grasp", joint_index=None):
    """Preserve first history names; retain distinct later trials and attribution."""
    suffix = "" if trial_index == 0 else f"_trial_{trial_index + 1:03d}"
    name = "gripper_" + str(shape)
    if kind == "joint":
        name += f"_joint_{joint_index:03d}"
    elif kind == "contacts":
        name += "_contacts"
    elif kind != "grasp":
        raise ValueError("unknown gripper motion stream kind")
    return name + suffix, {"shape": str(shape), "trial_index": trial_index, "trial_number": trial_index + 1}


def _required_trial_geometry(values, count, description):
    """Reject unsafe resolved trial geometry without inventing physical stops."""
    try:
        return validate_selected_native_positions(values, count, list(range(count)))
    except (IndexError, OverflowError, TypeError, ValueError) as exc:
        raise RuntimeError(f"FET028 configured hand geometry setup: invalid {description}: {exc}") from exc


def _hand_trial_length_scale(stage):
    from pxr import UsdGeom

    scale = UsdGeom.GetStageMetersPerUnit(stage)
    if isinstance(scale, bool) or not isinstance(scale, Real) or not math.isfinite(float(scale)) or scale <= 0:
        raise RuntimeError(
            "FET028 configured hand geometry setup requires a finite positive numeric stage length scale"
        )
    return float(scale)


def _validate_hand_trial_placement(stage, controls, grasp_center, config, max_opening):
    """Validate planned stage coordinates before carrier/object authoring."""
    scale = _hand_trial_length_scale(stage)
    offset_stage = _required_trial_geometry(
        [value / scale for value in controls.get("object_offset_world_xy_m", [0.0, 0.0])],
        2,
        "world offset conversion",
    )
    center = _required_trial_geometry(grasp_center, 3, "predicted grasp center")
    try:
        size = float(config["object_size_fraction"]) * float(max_opening)
        object_z = size / 2.0 + float(config.get("spawn_ground_clearance_m", 0.005))
        standoff_z = object_z + size + float(config.get("approach_extra_clearance_m", 0.03))
    except (OverflowError, TypeError, ValueError) as exc:
        raise RuntimeError("FET028 configured hand geometry setup: invalid object/standoff coordinates") from exc
    _required_trial_geometry([center[0], center[1], standoff_z], 3, "planned standoff")
    _required_trial_geometry([standoff_z - center[2]], 1, "planned carrier translation")
    _required_trial_geometry(
        [center[0] + offset_stage[0], center[1] + offset_stage[1], object_z], 3, "planned object spawn"
    )
    return np.asarray(offset_stage)


def _record_gripper_trial_controls(ctx, values, trial_index):
    """Bound only optional evidence, with explicit transport omission counts."""
    try:
        record = _bounded_gripper_trial_controls(values)
        suffix = "" if trial_index == 0 else f"_trial_{trial_index + 1:03d}"
        ctx.add_metric("gripper_trial_controls" + suffix, record)
        if record["configured_trial"]:
            _optional_contact_warning(
                ctx,
                "Configured gripper trial controls are active; this result does not establish default FET028 qualification.",
            )
    except Exception:
        _optional_contact_warning(
            ctx, "Gripper trial control evidence unavailable; required controls and criteria are unchanged."
        )


def _bounded_gripper_trial_controls(values):
    """Detach and trim diagnostic records without touching controls used by motion."""
    # Serialization also detaches the record from the controls used by motion.
    record = json.loads(json.dumps(values, allow_nan=False))
    omissions = {"joints": 0, "hand_joint_controls": 0, "hand_close_delays": 0, "procedure_settings": 0}
    record["transport_omissions"] = omissions
    while len(json.dumps(record, allow_nan=False).encode("utf-8")) > 32768:
        if record["joints"]:
            record["joints"].pop()
            record["joints_omitted"] += 1
            omissions["joints"] += 1
        elif record["hand_controls"].get("joints"):
            record["hand_controls"]["joints"].popitem()
            omissions["hand_joint_controls"] += 1
        elif record["hand_controls"].get("close_delay_steps"):
            record["hand_controls"]["close_delay_steps"].popitem()
            omissions["hand_close_delays"] += 1
        elif record["procedure_settings"]:
            record["procedure_settings"].popitem()
            omissions["procedure_settings"] += 1
        else:
            raise ValueError("gripper trial evidence cannot fit its bounded transport")
    return record


def _optional_contact_warning(ctx, message):
    try:
        ctx.warn(message)
    except Exception:
        pass


def _begin_gripper_contact_diagnostics(ctx, object_path, hand_paths, phase_getter):
    """Optional provider imports/observations cannot alter required setup errors."""
    try:
        from simready.evaluate_engine_kit.contact_diagnostics import (
            begin_physx_contact_diagnostics,
        )

        return begin_physx_contact_diagnostics(
            ctx, object_paths=[object_path], hand_body_paths=list(hand_paths), phase_getter=phase_getter
        )
    except Exception:
        _optional_contact_warning(ctx, "Optional native contact diagnostics unavailable; grasp criteria are unchanged.")
        return None


def _finish_gripper_contact_diagnostics(ctx, collector, metric_name, reason):
    """Always close; compact nullable evidence remains separate from verdicts."""
    snapshot = {
        "schema_version": 1,
        "status": "unavailable",
        "cleanup_complete": True,
        "stop_reason": reason,
        "issues": ["provider_unavailable"],
        "summaries": [],
    }
    if collector is not None:
        cleanup_failed = False
        try:
            collector.close(reason=reason)
        except Exception:
            cleanup_failed = True
        try:
            observed = collector.snapshot()
            if not isinstance(observed, dict) or len(json.dumps(observed, allow_nan=False).encode("utf-8")) > 32768:
                raise ValueError("contact evidence exceeds the bounded metric transport")
            snapshot = observed
        except Exception:
            snapshot.update(cleanup_complete=None, issues=["snapshot_unavailable"])
        if cleanup_failed:
            snapshot = dict(snapshot, cleanup_complete=False)
        if snapshot.get("cleanup_complete") is not True:
            _optional_contact_warning(
                ctx,
                "Native contact cleanup could not be confirmed; inspect runtime health. "
                "Restart any retired Kit/Isaac process before another test.",
            )
    try:
        ctx.add_metric(metric_name, snapshot)
    except Exception:
        _optional_contact_warning(ctx, "Native contact diagnostic evidence could not be recorded.")


def _grasp_joint_identities(stage, asset_prim, robot, indices):
    """Resolve bounded identity evidence; optional metadata cannot break default motion."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.hand_controls import (
        MAX_HAND_JOINTS,
    )
    from simready.foundation.tier_core.runtime_tests.motion_observer import joint_metadata

    identities = {}
    for index in list(dict.fromkeys(indices))[:MAX_HAND_JOINTS]:
        name = robot.dof_names[index]
        if name in identities:
            identities[name] = {"idx": index, "unit": "unknown_native", "identity_resolved": False}
            continue
        try:
            identity = joint_metadata(stage, asset_prim, name, root_path=getattr(robot, "prim_path", None))
        except Exception:
            identity = {"unit": "unknown_native", "identity_resolved": False}
        identities[name] = dict(identity, idx=index)
    return identities


def _contact_active_specs(grasp_specs, tolerance=1e-9):
    """Specs that actually close; held positioning DOFs cannot imply contact."""
    return [
        spec
        for spec in grasp_specs
        if spec.get("contact_active", abs(float(spec["closed"]) - float(spec["open"])) > tolerance)
    ]


async def _drive_to_open(
    ctx, robot, grasp_specs, fingertip_set, config, on_step=None, on_motion=None, on_motion_error=None
):
    """Drive every grasp DOF toward its OPEN target; exit on aggregate stall.

    A single multi-DOF ArticulationAction sets all grasp DOFs to their 'open'
    targets each step (1 DOF for a parallel jaw, N flexors for a hand). Exits
    when ALL driven DOFs have stopped moving (max per-DOF position range over
    the sliding window < eps) or the step budget runs out.
    """
    stall_eps = float(config.get("close_position_stall_eps", 1e-3))
    stall_window = int(config.get("close_stall_window", 8))
    max_steps = int(config["open_steps_max"])

    histories = [[] for _ in grasp_specs]
    observation_warned = False

    for i in range(max_steps):
        _command_grasp_targets(robot, grasp_specs, "open")
        await ctx.step_one()
        if on_step is not None:
            _required_grasp_positions(robot, grasp_specs, "open before capture")
            await on_step(i)

        cur = _required_grasp_positions(robot, grasp_specs, "open")
        if on_motion is not None:
            try:
                on_motion([float(spec["open"]) for spec in grasp_specs], cur)
            except Exception:
                if on_motion_error is not None:
                    try:
                        on_motion_error()
                    except Exception:
                        pass
                if not observation_warned:
                    ctx.warn("Gripper joint motion observation unavailable; test criteria are unchanged.")
                    observation_warned = True
        for h, p in zip(histories, cur, strict=False):
            h.append(p)
            if len(h) > stall_window + 1:
                h.pop(0)

        if all(len(h) > stall_window for h in histories):
            max_range = max(max(h[-stall_window - 1 :]) - min(h[-stall_window - 1 :]) for h in histories)
            if max_range < stall_eps:
                return


async def _drive_to_close(
    ctx, robot, grasp_specs, fingertip_set, config, on_step=None, on_motion=None, on_motion_error=None
):
    """Drive every grasp DOF toward its CLOSED target; exit on joint stall.

    A single multi-DOF ArticulationAction sets all grasp DOFs to their 'closed'
    targets each step (1 DOF for a parallel jaw -- the mimic followers track via
    the PhysX mimic constraint -- or N flexors for a hand). Driving the DOFs
    DIRECTLY (vs ``ParallelGripper.forward('close')``, which intermittently
    PINNED the master at the open limit) is the SAME mechanism
    ``_detect_open_closed_positions`` uses and reliably moves the joints.

    Returns the existing close/engagement proxy: at least one DOF moved off open
    and the grasp stalled before all DOFs reached their closed target. This can
    also reflect another obstruction, so it does not establish object contact.
    Missing required live state is a runtime/setup error, not positive evidence.

    Available tip-force readings contribute an engagement proxy, but do not
    terminate the close.  The target must first finish its smooth ramp so a
    position drive can build holding force after first touch.

    After the target ramp completes, aggregate position stall terminates the
    close: ALL driven DOFs changed by
         < ``close_position_stall_eps`` over the last ``close_stall_window``
         frames. Position (not velocity) is the robust signal -- a stalled
         position drive oscillates through zero velocity but the position
         stays put.

    Per-DOF positions and contact-force readings are logged every
    ``close_log_every`` frames so the user can see the close progressing.
    """
    from simready.foundation.tier_core.runtime_tests.articulation_phases.force_utils import (
        read_contact_force_magnitude,
    )

    contact_threshold = float(config["jik_contact_force_threshold_n"])
    stall_eps = float(config.get("close_position_stall_eps", 1e-3))
    stall_window = int(config.get("close_stall_window", 8))
    log_every = int(config.get("close_log_every", 30))
    total_steps = int(config["close_steps"])
    ramp_steps = max(1, min(total_steps, int(config.get("close_ramp_steps", 300))))
    hand_controls = normalize_hand_trial_controls(config.get("hand_trial_controls", {}))
    close_delays = validate_close_delays(
        hand_controls, grasp_specs, config["close_steps"], config.get("close_ramp_steps", 300)
    )
    # Engage guard: do NOT honor a position-stall exit until SOME DOF has
    # actually STARTED closing (moved off its open position by
    # ``close_engage_eps``). The drive's first-frame response is not
    # deterministic in this build, so on some runs the DOFs have not begun
    # moving by the time the stall window first fills -- without this guard the
    # detector misreads "drive has not started yet" as "stalled at open / no
    # contact" and the close exits at step 8 having done nothing. Once a DOF has
    # engaged, a stall is an observed motion stop, not an isolated contact cause.
    engage_eps = float(config.get("close_engage_eps", 0.002))

    contact_specs = _contact_active_specs(grasp_specs)
    if not contact_specs:
        ctx.log("close aborted: no contact-active grasp DOFs")
        return False
    # Capture the open positions BEFORE the first close step (reading only after
    # step 0 misses a fast first-step jump that then stalls on the object).
    starts = _required_grasp_positions(robot, contact_specs, "initial close")
    all_starts = _required_grasp_positions(robot, grasp_specs, "initial close")
    histories = [[] for _ in contact_specs]
    has_engaged = False
    cur = starts
    observation_warned = False

    def _blocked():
        # Stalled short of a target is a blockage proxy, not proof of contact
        # with this object. Missing required state cannot satisfy that proxy.
        if cur is None:
            raise RuntimeError("FET028 setup: required final close joint readback is unavailable/invalid")
        return any(abs(cur[k] - contact_specs[k]["closed"]) > 5.0 * stall_eps for k in range(len(contact_specs)))

    for i in range(total_steps):
        if close_delays:
            targets = delayed_close_targets(all_starts, grasp_specs, i + 1, ramp_steps, close_delays)
        else:
            ramp_t = min(1.0, float(i + 1) / float(ramp_steps))
            eased = ramp_t * ramp_t * (3.0 - 2.0 * ramp_t)
            targets = [
                start + (float(spec["closed"]) - start) * eased
                for start, spec in zip(all_starts, grasp_specs, strict=False)
            ]
        _command_grasp_targets(robot, grasp_specs, "closed", target_values=targets)
        await ctx.step_one()
        if on_step is not None:
            _required_grasp_positions(robot, grasp_specs, "close before capture")
            await on_step(i)

        forces = [read_contact_force_magnitude(robot, tip) for tip in fingertip_set.tip_link_paths]
        all_above = forces and all(f is not None and f >= contact_threshold for f in forces)
        # Tip-force readings contribute an engagement proxy, but do not identify
        # the contacted body or provide a close-completion condition. A drive must keep
        # closing after first touch to build normal force.  In particular, a
        # sphere can report bilateral contact several frames before the pads
        # have developed enough force to retain it during lift.  Finish on the
        # joint-stall proxy below. A stall alone does not identify its cause.
        if all_above:
            has_engaged = True

        all_cur = _required_grasp_positions(robot, grasp_specs, "close")
        controlled_positions = {spec["idx"]: position for spec, position in zip(grasp_specs, all_cur, strict=True)}
        # Held joints remain required commanded state, while only moving
        # closure joints contribute to engagement and stall observations.
        cur = [controlled_positions[spec["idx"]] for spec in contact_specs]
        if on_motion is not None:
            try:
                on_motion(targets, _grasp_positions(robot, grasp_specs), forces)
            except Exception:
                if on_motion_error is not None:
                    try:
                        on_motion_error()
                    except Exception:
                        pass
                if not observation_warned:
                    ctx.warn("Gripper joint motion observation unavailable; test criteria are unchanged.")
                    observation_warned = True
        if any(abs(c - s) >= engage_eps for c, s in zip(cur, starts, strict=False)):
            has_engaged = True
        for h, p in zip(histories, cur, strict=False):
            h.append(p)
            if len(h) > stall_window + 1:
                h.pop(0)

        if (i % log_every) == 0:
            forces_str = ", ".join("%.2fN" % f if f is not None else "n/a" for f in forces)
            ctx.log(
                "close step %d/%d: dof_pos=%s contact=[%s]" % (i, total_steps, [round(c, 4) for c in cur], forces_str)
            )
        # Do not accept a stall while the close target is still ramping.  The
        # fingers naturally pause at first contact while the commanded target
        # is still close to the measured position.  Stopping there leaves very
        # little drive error (and therefore little normal force), which lets a
        # round object slip during lift.  Completing the ramp first preserves
        # the controlled approach while allowing the asset's authored drive to
        # develop its intended holding force.
        ramp_complete = (i + 1) >= ramp_steps + max(close_delays.values(), default=0)
        if ramp_complete and has_engaged and all(len(h) > stall_window for h in histories):
            max_range = max(max(h[-stall_window - 1 :]) - min(h[-stall_window - 1 :]) for h in histories)
            if max_range < stall_eps:
                blocked = _blocked()
                ctx.log(
                    "close early-exit at step %d: grasp DOFs stalled "
                    "(max position range %.5f < eps %.5f over last %d frames); "
                    "short_of_closed_target_proxy=%s" % (i, max_range, stall_eps, stall_window, blocked)
                )
                return blocked
    # Loop ran the full budget. If nothing engaged, the close drive never moved
    # the gripper off its open position -- flag it so the failure reads as
    # "close did not start" (a drive / constraint problem) rather than a silent
    # no-contact, and so the grip gate fails honestly.
    if not has_engaged:
        ctx.log(
            "close ran %d steps WITHOUT engaging: grasp DOFs never moved off "
            "the open position (starts=%s). Inspect issued commands, required "
            "readbacks, limits, constraints and setup before attributing a cause."
            % (total_steps, [round(s, 4) for s in (starts or [])])
        )
        return False
    return _blocked()


async def _settle_for_seconds(ctx, seconds: float, fps: int = 240, on_step=None):
    """Step a nominal ``seconds * fps`` physics-iteration budget.

    ``fps`` matches the default 240Hz physics rate and the close/lift loops.
    The callback may add capture/render timeline ticks, so this budget is not
    a measured solver duration or encoded-video duration. Motion histories
    report their observed clock basis separately. A mismatched rate changes
    the nominal budget, not just video playback.
    """
    n = max(1, int(round(seconds * fps)))
    for i in range(n):
        await ctx.step_one()
        if on_step is not None:
            await on_step(i)


def _measure_finger_separation(robot, fingertip_set):
    """Live world-space distance between the two identified finger-pad links.

    Reads live physics link poses via ``RobotHandle.get_link_world_positions``
    (NOT ``UsdGeom.XformCache``, which returns the static rest pose for
    articulation links -- every finger link would read the same base position).
    Missing, malformed or nonfinite diagnostic geometry remains unavailable.
    """
    try:
        paths = fingertip_set.tip_link_paths[:2]
        if len(paths) != 2:
            return None
        pos = robot.get_link_world_positions(paths)
        a = np.asarray(pos.get(paths[0]))
        b = np.asarray(pos.get(paths[1]))
        if a.dtype.kind not in "iuf" or b.dtype.kind not in "iuf":
            return None
        a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
        if a.shape != (3,) or b.shape != (3,) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
            return None
        with np.errstate(over="ignore", invalid="ignore"):
            distance = math.hypot(*(a - b))
        return distance if math.isfinite(distance) else None
    except Exception:
        return None


def _descent_chunk_count(distance_m, minimum_chunks, max_step_m):
    distance_m = max(0.0, float(distance_m))
    minimum_chunks = max(1, int(minimum_chunks))
    max_step_m = float(max_step_m)
    if max_step_m <= 0.0:
        return minimum_chunks
    return max(minimum_chunks, int(math.ceil(distance_m / max_step_m)))


def _read_object_position(stage, prim_path):
    """Required test-object pose; unavailable state cannot become an asset verdict."""
    from pxr import UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        raise RuntimeError("FET028 setup: required test-object prim is unavailable: %s" % prim_path)
    cache = UsdGeom.XformCache()
    position = np.array(cache.GetLocalToWorldTransform(prim)).reshape(4, 4)[3, :3]
    if not np.all(np.isfinite(position)):
        raise RuntimeError("FET028 setup: required test-object world position is nonfinite: %s" % prim_path)
    return position


def _read_carrier_z(stage, carrier):
    """Return the gripper's current world-frame Z.

    Reads from the articulation API (the new carrier IS the articulation
    root, see gripper_carrier.py) rather than from a separate Xform
    prim -- this gives the actual PhysX-side pose, not a USD-authored
    value that may lag simulation state.
    """
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_carrier import (
        carrier_world_position,
    )

    position = np.asarray(carrier_world_position(carrier), dtype=float)
    if position.shape != (3,) or not np.isfinite(position[2]):
        raise RuntimeError("FET028 setup: required carrier world Z is unavailable/non-finite")
    return float(position[2])

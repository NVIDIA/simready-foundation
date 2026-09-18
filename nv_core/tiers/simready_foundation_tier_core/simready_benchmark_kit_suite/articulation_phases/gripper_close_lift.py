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
pure-logic helpers (config defaults, heuristic, pass criterion, sign-flip
guard). The orchestrator requires Kit and is exercised by the manual
smoke test (Task H); the pure helpers are unit-tested in this task.
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

# ----------------------------------------------------------------------
# Shared spec/example reference block used in actionable fix messages.
# Kept in sync with the one in gripper_sites.py so an asset author who
# hits any FET028 message sees the same set of references (spec docs,
# canonical validator, working real-asset example).
# ----------------------------------------------------------------------
_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:      nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_grippers/requirements/\n"
    "  Validator: nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_grippers/validation.py\n"
    "  Example:   sample_content/common_assets/robots_general/Robotiq/"
    "2F-85/simready_isaac_usd/Robotiq_2F_85.usda\n"
    '             (search for: def Xform "gripper_01")'
)


# ---------------------------------------------------------------------------
# Test-scope skip messages for topologies with no resolvable position-driven
# finger branches. These skips must not push an author to fabricate a mimic
# relationship or drives that do not match the real mechanism.
# ---------------------------------------------------------------------------


def _test_scope_skip_unsupported(site_prim_path: str, reason: Optional[str] = None) -> str:
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
        "  Site that was discovered: {path}\n"
        "\n"
        "{reason}"
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
        "{ref}"
    ).format(path=site_prim_path, reason=reason_block, ref=_SPEC_REFERENCE)


def _fix_message_invalid_max_opening(site_prim_path: str, value: float) -> str:
    """Fix message for a gripper site whose ``gripper_maxOpening`` is <= 0."""
    return (
        "FET028 cannot run: gripper site has invalid maxOpening.\n"
        "  Site prim:           {path}\n"
        "  gripper_maxOpening:  {val!r} (must be a positive float in METERS)\n"
        "\n"
        "FIX: Author a positive ``gripper_maxOpening`` on the site prim --\n"
        "the maximum distance between the fingertip pads when the gripper\n"
        "is fully open, expressed in meters. Typical values are 0.05-0.15\n"
        "for industrial parallel-jaw grippers. Edit the prim at\n"
        "    {path}\n"
        "and set, for example:\n"
        "\n"
        "    custom float gripper_maxOpening = 0.085   # 85 mm, Robotiq 2F-85\n"
        "\n"
        "Per GR.004 (gripper-max-opening) this attribute is required and\n"
        "must be > 0; the static validator should normally catch this --\n"
        "if you are seeing this from FET028 the validator was bypassed.\n"
        "\n"
        "{ref}"
    ).format(path=site_prim_path, val=value, ref=_SPEC_REFERENCE)


def _fix_message_no_rigidbody_ancestor(site_prim_path: str) -> str:
    """Fix message when the gripper site has no RigidBodyAPI ancestor body."""
    return (
        "FET028 cannot run: no rigid-body ancestor found for gripper site.\n"
        "  Site prim:        {path}\n"
        "\n"
        "The gripper site must be authored UNDER a rigid-body link\n"
        "(the gripper base / wrist / palm) -- FET028 attaches its test\n"
        "carrier to that body, so the body must have ``UsdPhysics.RigidBodyAPI``\n"
        "applied. None of the ancestors of the site prim above carry\n"
        "RigidBodyAPI, which means either the site is mis-parented (e.g.\n"
        "placed under a pure Xform decorator outside the physics tree) or\n"
        "the gripper base link is missing its rigid-body schema.\n"
        "\n"
        "FIX: Reparent the gripper site Xform so it lives under the\n"
        "gripper base link (the wrist / palm body that the finger joints\n"
        "branch off of), and verify that body carries RigidBodyAPI:\n"
        "\n"
        '    def Xform "base_link" (\n'
        '        prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]\n'
        "    )\n"
        "    {{\n"
        "        # ... collision / mass / xform ops ...\n"
        "\n"
        '        def Xform "gripper_01" (\n'
        '            prepend apiSchemas = ["IsaacSiteAPI"]\n'
        "        )\n"
        "        {{\n"
        '            token simready:attachment:socketType = "Gripper"\n'
        "            custom float custom:maxOpening = 0.085\n"
        "            # ... forward_axis, grip_line BasisCurves ...\n"
        "        }}\n"
        "    }}\n"
        "\n"
        "The working Robotiq 2F-85 example places ``gripper_01`` directly\n"
        "under ``base_link``, which carries RigidBodyAPI via its Physics\n"
        "payload.\n"
        "\n"
        "{ref}"
    ).format(path=site_prim_path, ref=_SPEC_REFERENCE)


def _fix_message_open_mapping_wrong(
    *,
    joint_name: str,
    actual_pos: float,
    expected_pos: float,
    error: float,
    tolerance: float,
    shape: str,
) -> str:
    """Fix message when the master mimic joint did not reach its open limit."""
    return (
        "Open command did not drive the master mimic joint to its open\n"
        "position. The gripper either has its open/close convention\n"
        "reversed, has a broken drive, or has joint limits that don't\n"
        "match its actual range of motion.\n"
        "\n"
        "  Master mimic joint: {joint}\n"
        "  Actual position:    {actual:.4f} (rad for revolute, m for prismatic)\n"
        "  Expected position:  {expected:.4f}  (joint's authored LOWER limit)\n"
        "  Error:              {err:.4f}\n"
        "  Tolerance:          {tol:.4f}\n"
        "\n"
        "Inspect ``{shape}_after_open_command.png`` in the captures to see\n"
        "what the gripper actually did.\n"
        "\n"
        "FET028 convention: lowerLimit == OPEN, upperLimit == CLOSED.\n"
        "This matches typical industrial parallel-jaw grippers (Robotiq,\n"
        "Robotiq, etc.) where the closing motion drives the joint toward\n"
        "larger positive angles.\n"
        "\n"
        "ASSET-AUTHORING FIXES to inspect on the joint prim driving\n"
        "``{joint}``:\n"
        "\n"
        "  (a) Swapped open/close: if your asset uses upperLimit == open,\n"
        "      swap the two limits OR flip the joint axis (negate\n"
        "      ``physics:axis``) so the convention matches:\n"
        "\n"
        "          float physics:lowerLimit = 0.0    # open\n"
        "          float physics:upperLimit = 0.7    # closed (radians)\n"
        "\n"
        "  (b) Weak/missing drive: check the joint's drive parameters.\n"
        "      The drive's ``stiffness`` must be large enough to overcome\n"
        "      the gripper's own static friction; ``maxForce`` must be\n"
        "      finite and positive:\n"
        "\n"
        "          float drive:angular:physics:stiffness = 1000.0\n"
        "          float drive:angular:physics:damping   = 50.0\n"
        "          float drive:angular:physics:maxForce  = 100.0\n"
        "\n"
        "  (c) Joint limits don't match the modeled ROM: open the asset in\n"
        "      Kit, manually drag the gripper to its fully-open pose, read\n"
        "      back the joint angle, and use that as ``physics:lowerLimit``.\n"
        "\n"
        "{ref}"
    ).format(
        joint=joint_name,
        actual=actual_pos,
        expected=expected_pos,
        err=error,
        tol=tolerance,
        shape=shape,
        ref=_SPEC_REFERENCE,
    )


def _fix_message_grasp_below_object(grasp_z: float, object_z: float) -> str:
    """Fix message when the gripper is authored with the grasp center too low."""
    return (
        "FET028 cannot run: gripper grasp center is at or below the\n"
        "spawned test object.\n"
        "  grasp_center world Z: {gz:.4f} m\n"
        "  object spawn  world Z: {oz:.4f} m\n"
        "\n"
        "FET028 spawns the test object on the ground plane directly below\n"
        "the gripper's grasp center, then descends the gripper onto it. If\n"
        "the gripper's authored grasp center is already on or below the\n"
        "ground, there is no room for the descent phase.\n"
        "\n"
        "Two common authoring mistakes cause this:\n"
        "\n"
        "  (a) Gripper authored pointing UP (fingers above the wrist).\n"
        "      Rotate the asset root 180 deg around the X (or Y) axis so\n"
        "      the fingers point DOWN at rest, e.g. on your articulation\n"
        "      root Xform:\n"
        "\n"
        "          quatd xformOp:orient = (0, 1, 0, 0)  # 180 deg about X\n"
        "\n"
        "  (b) Asset translated to the floor with the wrist at Z=0.\n"
        "      Translate the asset root upward so the grasp center clears\n"
        "      both the ground plane and the test object radius (the test\n"
        "      object diameter is ``object_size_fraction * maxOpening``,\n"
        "      so add at least maxOpening * 0.5 + 0.05 m of headroom):\n"
        "\n"
        "          double3 xformOp:translate = (0, 0, 0.30)\n"
        "\n"
        "Verify by opening the asset in Kit: with the articulation at its\n"
        "rest pose, the gripper site's grasp center should sit roughly\n"
        "0.2-0.4 m above the world origin and the fingers should point\n"
        "down toward the floor.\n"
        "\n"
        "{ref}"
    ).format(gz=grasp_z, oz=object_z, ref=_SPEC_REFERENCE)


def _fix_message_failed_to_lift(
    tested_mass_kg: float,
    used_heuristic: bool,
    shapes_attempted: list,
    payload_mass_fraction: float,
) -> str:
    """Fix message when the gripper failed to grasp+lift any shape."""
    shapes_str = " AND ".join(shapes_attempted)
    payload_source = (
        "from the FET028 heuristic (asset did NOT author custom:maxPayload)"
        if used_heuristic
        else "from the asset's authored custom:maxPayload"
    )
    return (
        "Gripper failed to grasp-and-lift the test object on every shape\n"
        "({shapes}) at {payload_pct:.0f}% of its rated payload.\n"
        "  Tested object mass: {mass:.3f} kg ({src})\n"
        "\n"
        "This is the asset's grasp performance under FET028's standard\n"
        "stress test (object diameter = 70% of maxOpening, friction = 2.0,\n"
        "mass = {payload_pct:.0f}% of rated maxPayload). When the test reaches this\n"
        "point all the schema/topology checks above have already passed,\n"
        "so the failure is in the asset's *authored physics* -- the\n"
        "gripper closed and the lift was commanded, but the object\n"
        "either slipped out, was knocked away, or was never gripped\n"
        "firmly enough to follow the lift.\n"
        "\n"
        "INSPECT THE METRICS for this run in result.json:\n"
        "  - ``close_blocked_by_object_<shape>``  -- True means the\n"
        "    fingers stopped on the object (good); False means they\n"
        "    reached their upper limit with no contact (no grip).\n"
        "  - ``object_lateral_drift_after_close_<shape>`` -- large values\n"
        "    (> object_radius) mean the close knocked the object out.\n"
        "  - ``vertical_follow_dz_m_<shape>`` -- > fall_min_delta_z\n"
        "    means the object fell behind during the lift (slipped).\n"
        "  - ``shake_max_relative_slip_m_<shape>`` (if shake enabled)\n"
        "    -- > shake_max_relative_slip_m means the grip drifted under\n"
        "    perturbation.\n"
        "\n"
        "ASSET-AUTHORING LEVERS to investigate (in priority order):\n"
        "\n"
        "  1. Finger-pad friction. Inspect the PhysicsMaterial bound to\n"
        "     the finger pad collision meshes; static/dynamic friction\n"
        "     below ~0.8 will let any reasonable object slip. Industrial\n"
        "     pads typically author 1.0-2.0:\n"
        "         float physics:staticFriction  = 1.5\n"
        "         float physics:dynamicFriction = 1.5\n"
        "     (FET006 covers this independently.)\n"
        "\n"
        "  2. Master-mimic joint drive strength. The drive's\n"
        "     ``stiffness`` and ``maxForce`` together determine the\n"
        "     holding torque. As a starting point for a 5 kg payload\n"
        "     parallel-jaw gripper:\n"
        "         float drive:angular:physics:stiffness = 1000.0-5000.0\n"
        "         float drive:angular:physics:damping   =   50.0-200.0\n"
        "         float drive:angular:physics:maxForce  =  100.0-1000.0\n"
        "     Too LOW = weak grip / object slips out. Too HIGH = fingers\n"
        "     slam shut and knock the object away (look for large\n"
        "     ``object_lateral_drift_after_close_<shape>``).\n"
        "\n"
        "  3. ``custom:maxPayload`` honesty. If the heuristic was used\n"
        "     (``used_heuristic_payload=True`` in metrics), the test\n"
        "     guessed at the payload. Author a realistic value on the\n"
        "     gripper site so future runs test the spec'd capability:\n"
        "         custom float custom:maxPayload = 5.0   # kg\n"
        "\n"
        "  4. Mimic relationship. Verify the mimic joints are bound to\n"
        "     the master and their ratios make geometric sense -- a\n"
        "     mis-wired mimic (wrong sign / ratio) can leave one pad\n"
        "     out of contact while the master appears to close.\n"
        "\n"
        "{ref}"
    ).format(
        shapes=shapes_str,
        payload_pct=100.0 * payload_mass_fraction,
        mass=tested_mass_kg,
        src=payload_source,
        ref=_SPEC_REFERENCE,
    )


def get_defaults() -> Dict[str, Any]:
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
        # Ramp the close target instead of applying a full-range step. Newton's
        # closed-loop solver follows the same 300-frame smoothstep used by
        # FET022; an instantaneous 0 -> full-range request can lock the
        # over-constrained parallel linkage at its open endpoint.
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
        # position. 5x this is used as the actual sign-flip threshold.
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
    max_payload_authored: Optional[float],
    config: Dict[str, Any],
) -> Tuple[float, bool, float]:
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
    config: Dict[str, Any],
) -> PassCriterion:
    """Two-condition grasp-and-lift pass with a pre-load diagnostic:

    1. ``vertical_follow_dz < fall_min_delta_z`` — object followed the carrier upward
    2. ``horizontal_drift < horizontal_drift_max`` — object stayed in the grip XY-wise

    ``pre_load_dz`` records how far closure moved the object vertically before
    the carrier lift. It is diagnostic only: a hand may legitimately seat or
    lift an object while establishing contact, and the subsequent carrier-follow,
    shake, and release phases prove whether the grasp is real.

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


def _compute_approach_orientation(stage, gripper_base_path, site, approach_world, roll_deg=0.0):
    """Return (base_orient_wxyz, grasp_center_rotated, forward_in_base) to orient
    the gripper so its ``forward_axis`` points along ``approach_world`` (world -Z
    for a top-down grasp).

    ``base_orient`` (``rot``) is the gripper base's desired WORLD orientation: it
    must satisfy ``base_orient * forward_in_base_local == approach_world``, hence
    ``base_orient = rotation(forward_in_base_local -> approach_world)``. The grasp
    center rotates about the base position by ``rot``, so the object spawn /
    descent target follow the re-oriented gripper.

    The orientation is applied as the articulation's DEFAULT (reset) state -- NOT
    via the gantry weld. Measured on this Isaac build (weld-check log): the
    maximal-coordinate FixedJoint between the free gantry body and the
    articulation base enforces the base's POSITION but locks its ORIENTATION to
    the articulation reset pose, ignoring the joint's ``localRot0`` entirely
    (authoring ``rot`` and ``rot^-1`` produced an identical +Z base orientation).
    So the carrier sets ``robot.articulation.set_default_state(orientation=rot)``
    before ``world.reset_async()``; reset teleports the base to ``rot`` and the
    FixedJoint then cooks locking that down orientation.

    The returned quaternion is ``rot`` itself, scalar-first ``(w, x, y, z)``, as
    Isaac's ``set_default_state`` expects. For a centric gripper, forward
    (+Z) -> -Z makes ``rot`` a -90 degree rotation about X, and the grasp center
    moves from 0.13 m in front to 0.13 m below the base (the gripper descends
    straight onto the object instead of driving its body sideways into the floor).
    """
    import numpy as np
    from pxr import Gf, UsdGeom

    base_prim = stage.GetPrimAtPath(gripper_base_path)
    base_T = Gf.Transform(UsdGeom.XformCache().GetLocalToWorldTransform(base_prim))
    base_rot = base_T.GetRotation()
    base_pos = Gf.Vec3d(*[float(x) for x in base_T.GetTranslation()])

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

    gc = site.grasp_center_world_initial()
    gc_vec = Gf.Vec3d(float(gc[0]), float(gc[1]), float(gc[2]))
    gc_in_base = base_rot.GetInverse().TransformDir(gc_vec - base_pos)
    gc_rot = base_pos + rot.TransformDir(gc_in_base)
    grasp_center_rotated = np.array([gc_rot[0], gc_rot[1], gc_rot[2]], dtype=np.float64)
    fwd_in_base_arr = np.array([fwd_in_base[0], fwd_in_base[1], fwd_in_base[2]], dtype=np.float64)
    # ``rot`` is the desired base WORLD orientation; return it scalar-first
    # (w, x, y, z) for ``set_default_state``. grasp_center_rotated uses rot.
    bq = rot.GetQuat()
    bi = bq.GetImaginary()
    base_orient_wxyz = np.array([bq.GetReal(), bi[0], bi[1], bi[2]], dtype=np.float64)
    return base_orient_wxyz, grasp_center_rotated, fwd_in_base_arr


def _authored_hand_frames(forward_in_base, grip_in_base):
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
    grip_world = np.array([0.0, -1.0, 0.0])
    world_frame = np.array([forward_world, grip_world, np.cross(forward_world, grip_world)])
    return local_frame, world_frame


def _authored_hand_orientation(stage, gripper_base_path, site):
    """Orient an independent-finger hand from its authored site frame.

    The site's ``forward_axis`` is mapped to world +X and its ``grip_line`` to
    world -Y. Their cross product therefore points world -Z, placing the palm
    over the object without relying on an asset-specific palm axis. Returns the
    same triple as ``_compute_approach_orientation``.
    """
    from pxr import Gf, UsdGeom

    base_prim = stage.GetPrimAtPath(gripper_base_path)
    base_T = Gf.Transform(UsdGeom.XformCache().GetLocalToWorldTransform(base_prim))
    base_rot = base_T.GetRotation()
    base_pos = np.array([float(x) for x in base_T.GetTranslation()], dtype=np.float64)

    fwd_world = np.asarray(site.forward_axis_world, dtype=np.float64)
    grip_world = np.asarray(site.grip_line_world[1] - site.grip_line_world[0], dtype=np.float64)
    fib = base_rot.GetInverse().TransformDir(Gf.Vec3d(*fwd_world.tolist()))
    gib = base_rot.GetInverse().TransformDir(Gf.Vec3d(*grip_world.tolist()))
    lframe, wframe = _authored_hand_frames([fib[0], fib[1], fib[2]], [gib[0], gib[1], gib[2]])
    fa = lframe[0]

    rmat = wframe.T @ lframe  # base-local -> world rotation, R @ finger = finger-forward, R @ palm = down
    m = Gf.Matrix3d(*rmat.T.flatten().tolist())  # Gf row-vector: TransformDir(v) = v*M = R@v
    rot = m.ExtractRotation()
    bq = rot.GetQuat()
    bi = bq.GetImaginary()
    base_orient_wxyz = np.array([bq.GetReal(), bi[0], bi[1], bi[2]], dtype=np.float64)

    gc = np.asarray(site.grasp_center_world_initial(), dtype=np.float64)
    grasp_center_rotated = base_pos + rmat @ (gc - base_pos)
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

    forward_component = abs(float(displacement[0]))
    grip_component = abs(float(displacement[1]))
    palm_component = abs(float(displacement[2]))
    if grip_component > max(forward_component, palm_component):
        return ("positioning", "upper")
    return ("positioning", "lower")


def _infer_hand_grasp_specs(robot, fingertip_set, grasp_center_world):
    """Infer closure and positioning targets from kinematic fingertip motion."""

    original_positions = robot.get_joint_positions()
    original_velocities = robot.get_joint_velocities()
    lowers, uppers = robot.get_joint_position_limits()
    finite = np.isfinite(lowers) & np.isfinite(uppers)
    baseline = np.asarray(original_positions, dtype=np.float64).copy()
    tip_paths = list(fingertip_set.tip_link_paths)
    center = np.asarray(grasp_center_world, dtype=np.float64)
    candidate_indices = sorted({int(index) for chain in fingertip_set.finger_chains or [] for index in chain})
    for dof_index in candidate_indices:
        if finite[dof_index]:
            baseline[dof_index] = lowers[dof_index]
    specs = []
    diagnostics = []
    try:
        robot.set_joint_positions(baseline)
        base_tips = robot.get_link_world_positions(tip_paths)
        for dof_index in candidate_indices:
            if not finite[dof_index]:
                continue
            probe = baseline.copy()
            probe[dof_index] = uppers[dof_index]
            robot.set_joint_positions(probe)
            moved_tips = robot.get_link_world_positions(tip_paths)
            movements = []
            for tip_index, path in enumerate(tip_paths):
                before = base_tips.get(path)
                after = moved_tips.get(path)
                if before is None or after is None:
                    continue
                displacement = np.asarray(after - before, dtype=np.float64)
                if float(np.linalg.norm(displacement)) <= 1e-6:
                    continue
                radial_change = float(np.linalg.norm(after - center) - np.linalg.norm(before - center))
                movements.append((tip_index, displacement, radial_change))
            if not movements:
                diagnostics.append((dof_index, "unresolved", None, 0.0, []))
                continue
            primary = max(movements, key=lambda movement: float(np.linalg.norm(movement[1])))
            _, displacement, radial_change = primary
            role, endpoint = _classify_hand_endpoint_motion(displacement, radial_change)
            target = float(uppers[dof_index] if endpoint == "upper" else lowers[dof_index])
            specs.append(
                {
                    "idx": int(dof_index),
                    "open": float(lowers[dof_index]) if role == "closure" else target,
                    "closed": float(uppers[dof_index]) if role == "closure" else target,
                    "name": robot.dof_names[dof_index],
                }
            )
            diagnostics.append(
                (
                    dof_index,
                    role,
                    endpoint,
                    radial_change,
                    displacement.tolist(),
                )
            )
    finally:
        robot.set_joint_positions(original_positions)
        if np.isfinite(original_velocities).all():
            robot.set_joint_velocities(original_velocities)
    return specs, diagnostics


def sign_flip_detected(
    commanded_target: float,
    measured_separation: float,
    max_opening: float,
    config: Dict[str, Any],
) -> bool:
    """Return True if the open command appears reversed.

    After commanding open (target = max_opening), measure the actual
    fingertip separation. If it's substantially less than max_opening,
    the asset author likely has the open/close positions reversed —
    fail-fast with a clear message rather than silently testing closure
    when we asked for opening. Threshold: separation < 50% of max_opening.
    """
    tolerance = float(config["open_position_tolerance"])
    return measured_separation < max(0.5 * max_opening, tolerance * 10)


async def run_gripper_close_lift(ctx, robot, scene_info, config):
    """Orchestrate FET028 close-and-lift on a single gripper site."""

    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        discover_fingertips,
    )
    from simready_benchmark_kit_suite.articulation_phases.gripper_carrier import (
        attach_carrier,
        carrier_world_position,
        detach_carrier,
        linear_translate,
        shake_gantry_z,
    )
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        diagnose_missing_sites,
        discover_gripper_sites,
    )
    from simready_benchmark_kit_suite.articulation_phases.object_spawning import (
        spawn_test_object,
    )

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
        ctx.warn(f"custom:maxPayload not authored; using heuristic " f"{max_payload_used:.2f} kg")
    ctx.add_metric("gripper_max_opening_m", site.max_opening)
    ctx.add_metric("gripper_max_payload_kg", max_payload_used)
    ctx.add_metric("used_heuristic_payload", used_heuristic)
    ctx.add_metric("tested_object_mass_kg", tested_mass_kg)

    # Newton's native actuator/control buffers are not ready to accept their
    # first target immediately after the articulation view is created.  The
    # FET022 phases establish the proven lifecycle by stepping one second with
    # the authored rest targets before driving a joint.  Do the same here,
    # before endpoint discovery or any FET028 scene mutation.  Without this
    # warm-up the first target is silently ignored and the parallel-jaw master
    # remains at its authored rest position for the rest of the test.
    if scene_info.get("active_physics_engine") == "newton":
        warmup_seconds = float(config.get("newton_drive_warmup_seconds", 1.0))
        if warmup_seconds > 0.0:
            ctx.step("FET028: warming Newton actuators for %.2f s" % warmup_seconds)
            await _settle_for_seconds(ctx, warmup_seconds, on_step=None)

    # 3. Topology
    prebuilt_carrier = scene_info.get("prebuilt_gripper_carrier")
    fingertip_set = discover_fingertips(
        stage,
        robot,
        site,
        robot_prim_path=(prebuilt_carrier.get("asset_analysis_root_path") if prebuilt_carrier else None),
        ignored_joint_paths=(prebuilt_carrier.get("joint_z_path"),) if prebuilt_carrier else (),
    )
    if fingertip_set.kind == "unsupported":
        ctx.skip(_test_scope_skip_unsupported(site.prim_path, fingertip_set.reason))
        return
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
    # Orient the gripper so its forward_axis points along the approach vector
    # (world -Z, top-down) when welded under the gantry; the grasp center moves
    # with the rotation so the spawn + descent follow it. Parallel-jaw and
    # centric grippers approach top-down; independent-finger hands skipped above.
    approach_base_orient = None
    approach_fwd_in_base = None
    grasp_center_for_test = np.asarray(site.grasp_center_world_initial(), dtype=np.float64)
    if fingertip_set.kind == "mimic_parallel_jaw":
        (
            approach_base_orient,
            grasp_center_for_test,
            approach_fwd_in_base,
        ) = _compute_approach_orientation(stage, gripper_base_path, site, (0.0, 0.0, -1.0))
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
            ) = _authored_hand_orientation(stage, gripper_base_path, site)
        except ValueError as exc:
            ctx.precheck_failure(f"Invalid FET028 gripper site orientation at {site.prim_path}: {exc}.")
            return
        ctx.log(
            "FET028 hand orient [authored frame]: forward_axis -> world +X, "
            "grip_line -> world -Y, palm -> world -Z; grasp center %s -> %s."
            % (
                np.round(site.grasp_center_world_initial(), 4),
                np.round(grasp_center_for_test, 4),
            )
        )

    # NOTE: we do NOT override the gripper's pad physics material.
    # The asset's authored materials apply; if the asset doesn't
    # author friction on its finger pads, that's an asset-level
    # compliance issue (FET006 covers it) and the test will fail
    # cleanly here with low/missing friction -- which is the right
    # signal. We only set the test object's material (in
    # spawn_test_object) since that's owned by the test.

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
    try:
        room_handle = getattr(ctx.scene, "_room_handle", None)
        if room_handle is not None:
            room_handle.show_ground(color=(0.3, 0.3, 0.3))
            room_handle.set_color(0.3, 0.3, 0.3)
        else:
            # Fallback: framework didn't expose the room handle. Use the
            # ground plane API so the cube has *something* to sit on,
            # even if the walls remain blended with the IBL.
            ctx.scene.enable_ground_plane()
    except Exception as exc:
        ctx.log("Room/ground setup skipped: %s" % exc)

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

    async def _capture(label, stabilize_frames=2):
        """capture_frame wrapper. Advance the camera-follow rig first so the
        moving gripper + grasped object stay framed, then grab the frame."""
        if bool(config.get("disable_capture", False)):
            return None
        try:
            ctx.scene.update_camera_follow(update_history=True)
        except Exception:
            pass
        return await ctx.capture_frame(label=label, stabilize_frames=stabilize_frames)

    await _capture("discovery")
    if fingertip_set.kind == "independent_fingers":
        # Hand diagnostic keyframe: the hand as loaded, before reorientation.
        await _capture("hand_loaded")

    # 5. Per-shape grasp-and-lift
    # (``gripper_base_path`` and the approach orientation were resolved up
    # front, before the camera, so the framing follows the re-oriented grasp.)
    winning_shape = None
    object_size_m = float(config["object_size_fraction"]) * site.max_opening

    for shape in config["shapes"]:
        carrier = None
        # Predeclared so the ``finally`` block can clean up even if
        # we hit an exception before these are assigned.
        obj = None
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

        async def _video_capture(_i, _total=None):
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
            except Exception:
                pass

        try:
            await _reset_world(ctx)
            # Merge the test-owned prismatic rail into the articulation. This
            # is the proven PhysX path and gives the carrier an addressable DOF;
            # Newton receives the same merged topology before its first cook.
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
            stationary_load_test = bool(carrier.stationary)
            _cur_dof_names = list(robot.dof_names)
            if _merge_rail and _pre_dof_names != _cur_dof_names:

                def _remap_idx(_i):
                    _nm = _pre_dof_names[_i] if 0 <= _i < len(_pre_dof_names) else None
                    return _cur_dof_names.index(_nm) if _nm in _cur_dof_names else _i

                if fingertip_set.mimic_master_dof is not None:
                    fingertip_set.mimic_master_dof = _remap_idx(int(fingertip_set.mimic_master_dof))
                if fingertip_set.mimic_master_dofs:
                    fingertip_set.mimic_master_dofs = [
                        _remap_idx(int(_i)) for _i in fingertip_set.mimic_master_dofs
                    ]
                if fingertip_set.finger_chains:
                    fingertip_set.finger_chains = [
                        [_remap_idx(_i) for _i in _chain] for _chain in fingertip_set.finger_chains
                    ]
                ctx.log(
                    "FET028: remapped grasp DOF indices by name after rail merge "
                    "(dof_count %d -> %d)." % (len(_pre_dof_names), len(_cur_dof_names))
                )
            # ISOLATION: step physics IN PLACE (no gantry move) right after
            # attach, then probe joint validity. The attach itself leaves the
            # articulation finite (attach-probe[after reset_async]=finite); the
            # explosion happens during the subsequent gantry RAISE. This probe
            # distinguishes "free stepping alone destabilizes the mimic hand"
            # (non-finite here -> fundamental) from "only the gantry-driven
            # motion destabilizes it" (finite here -> motion/drive tuning).
            post_init_settle = 1.0 if scene_info.get("active_physics_engine") == "newton" else 0.15
            if post_init_settle > 0.15:
                ctx.log(
                    "FET028 Newton controller warm-up: stepping %.2f s before the first drive command."
                    % post_init_settle
                )
            await _settle_for_seconds(ctx, post_init_settle, on_step=None)
            _jp_probe = robot.get_joint_positions()
            if _jp_probe is None:
                _st = "None (view DEAD)"
            else:
                _arr = np.asarray(_jp_probe)
                _st = "finite(n=%d)" % _arr.size if np.isfinite(_arr).all() else "NON-FINITE/NaN"
            ctx.log(
                "FET028 post-attach in-place settle probe: joint_pos=%s "
                "(finite => free stepping is fine, the gantry RAISE is the "
                "trigger; dead => mimic hand is unstable even at rest)." % _st
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
            #   hand -> each finger FLEXOR (open = lower/extended limit,
            #     closed = upper/flexed limit); spread/opposition DOFs are
            #     positioning, left at their rest pose.
            grasp_specs = []
            if fingertip_set.kind == "mimic_parallel_jaw":
                open_master_pos, closed_master_pos = await _detect_open_closed_positions(
                    ctx, robot, fingertip_set, stage, config, site.max_opening
                )
                _backoff_frac = float(config.get("open_limit_backoff_frac", 0.0))
                open_drive_pos = open_master_pos + (closed_master_pos - open_master_pos) * _backoff_frac
                if _backoff_frac:
                    ctx.log(
                        "FET028 open target backed off the limit: %.4f -> %.4f "
                        "(%.0f%% toward closed)." % (open_master_pos, open_drive_pos, 100.0 * _backoff_frac)
                    )
                _master_indices = list(
                    fingertip_set.mimic_master_dofs or [int(fingertip_set.mimic_master_dof)]
                )
                _lowers, _uppers = robot.get_joint_position_limits()
                _primary_idx = int(fingertip_set.mimic_master_dof)
                _primary_lower = float(_lowers[_primary_idx])
                _primary_upper = float(_uppers[_primary_idx])
                _open_is_lower = abs(open_master_pos - _primary_lower) <= abs(
                    open_master_pos - _primary_upper
                )
                for _mi in _master_indices:
                    _mi = int(_mi)
                    _lo = float(_lowers[_mi])
                    _up = float(_uppers[_mi])
                    if not np.isfinite(_lo) or not np.isfinite(_up):
                        raise RuntimeError(
                            "Parallel-jaw leader DOF idx=%d has no finite joint limits "
                            "(lower=%r, upper=%r)." % (_mi, _lo, _up)
                        )
                    _open = _lo if _open_is_lower else _up
                    _closed = _up if _open_is_lower else _lo
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
                        "leaders: %s."
                        % (len(grasp_specs), ", ".join(str(spec["name"]) for spec in grasp_specs))
                    )
            else:  # independent_fingers (hand)
                try:
                    grasp_specs, _hand_diagnostics = _infer_hand_grasp_specs(
                        robot, fingertip_set, grasp_center_for_test
                    )
                except Exception as exc:
                    ctx.precheck_failure(
                        "FET028 could not infer independent-finger targets from fingertip motion: %s" % exc
                    )
                    return
                _closure_indices = {
                    int(spec["idx"]) for spec in grasp_specs if not np.isclose(spec["open"], spec["closed"])
                }
                _unresolved_branches = [
                    list(chain)
                    for chain in fingertip_set.finger_chains or []
                    if not any(int(index) in _closure_indices for index in chain)
                ]
                if _unresolved_branches:
                    ctx.precheck_failure(
                        "FET028 independent-finger target inference found no closure motion for branch DOFs %s."
                        % _unresolved_branches
                    )
                    return
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
                ctx.precheck_failure("FET028: no actuated grasp DOFs resolved for site %s." % site.prim_path)
                return

            # 5a-prelude(0). FIRST poise the gripper at a size-based standoff
            # above where the object will be, THEN spawn the object on the floor
            # beneath it. Positioning the gantry before spawning keeps the order
            # unambiguous (the gripper is placed, then the pickup object appears
            # under it) and avoids any confusing raise-then-lower at the start.
            radius = object_size_m / 2.0
            ground_clearance = float(config.get("spawn_ground_clearance_m", 0.005))
            object_center_z = float(grasp_center_for_test[2]) if stationary_load_test else radius + ground_clearance

            # Standoff: how far above the object center the OPEN gripper starts
            # so its fingers clear the object before the descent. Sized from the
            # object (one diameter) plus a margin -- enough headroom for any
            # gripper of this opening class. The gripper descends exactly this
            # far to bring its grasp center to the object center.
            approach_clearance = (
                0.0 if stationary_load_test else object_size_m + float(config.get("approach_extra_clearance_m", 0.03))
            )
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

                async def _hold_open_during_positioning(_i, _total=None):
                    _command_grasp_targets(robot, grasp_specs, "open")

                _command_grasp_targets(robot, grasp_specs, "open")
                positioning_duration = (
                    float(config.get("newton_carrier_position_duration_s", 2.0))
                    if scene_info.get("active_physics_engine") == "newton"
                    else 0.6
                )
                await linear_translate(
                    ctx=ctx,
                    stage=stage,
                    handle=carrier,
                    delta_world=np.array([0.0, 0.0, required_raise]),
                    duration_s=positioning_duration,
                    on_substep=_hold_open_during_positioning,
                )
                await _settle_for_seconds(
                    ctx,
                    0.5 if scene_info.get("active_physics_engine") == "newton" else 0.2,
                    on_step=_hold_open_during_positioning,
                )

            # Spawn directly below the authored grasp center. Runtime fingertip
            # measurements must not silently repair or offset site metadata.
            spawn_world = _authored_spawn_position(grasp_center_world, object_center_z)
            prebuilt_object = scene_info.get("prebuilt_fet028_test_object")
            object_body = None
            if prebuilt_object and prebuilt_object.get("shape") == shape:
                obj = prebuilt_object["object"]
                spawn_world = np.asarray(prebuilt_object["spawn_world"], dtype=np.float64)
                ctx.log("FET028: using the Newton test object authored before first physics cook.")
                # Newton requires the synthetic rigid body to exist before its
                # first scene cook.  Robot/carrier initialization advances the
                # simulation after that cook, however, so the prebuilt body may
                # have moved before this phase starts.  Updating the USD xform
                # alone does not teleport an already-compiled Newton body.
                # Reset the tensor-backed pose and velocity explicitly at the
                # point where the phase takes ownership of the object.
                from isaacsim.core.experimental.prims import RigidPrim

                object_body = RigidPrim(obj.prim_path)
                object_body.set_world_poses(
                    positions=np.asarray([spawn_world], dtype=np.float32),
                    orientations=np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
                )
                object_body.set_velocities(
                    linear_velocities=np.zeros((1, 3), dtype=np.float32),
                    angular_velocities=np.zeros((1, 3), dtype=np.float32),
                )
                ctx.log(
                    "FET028: reset the compiled Newton test body to "
                    "(%.4f, %.4f, %.4f) with zero velocity."
                    % (float(spawn_world[0]), float(spawn_world[1]), float(spawn_world[2]))
                )
            else:
                spawn_pose = np.eye(4)
                spawn_pose[3, :3] = spawn_world
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
                    physics_engine=scene_info.get("active_physics_engine"),
                )

            def _object_position_runtime():
                if object_body is not None:
                    positions, _orientations = object_body.get_world_poses()
                    return np.asarray(positions.numpy(), dtype=np.float64).reshape(-1, 3)[0]
                return _read_object_position(stage, obj.prim_path)

            def _object_xy_runtime():
                return _object_position_runtime()[:2]

            def _object_z_runtime():
                return float(_object_position_runtime()[2])

            def _newton_object_pad_contact():
                """Return True only for a force-bearing object-to-pad contact.

                Newton's ``rigid_contact_count`` contains broad-phase contact
                candidates whose force is exactly zero.  Treating shape-pair
                presence as contact stops the open-gripper descent while the
                pads are still centimetres above/beside the object.  Require a
                non-zero solver force; if this Newton solver does not publish
                contact forces, the distance-bounded descent remains the safe
                fallback.
                """
                if scene_info.get("active_physics_engine") != "newton":
                    return False
                try:
                    from isaacsim.physics.newton import acquire_stage  # type: ignore

                    newton_stage = acquire_stage()
                    model = getattr(newton_stage, "model", None)
                    contacts = getattr(newton_stage, "contacts", None)
                    if model is None or contacts is None:
                        return False
                    labels = [str(label) for label in (getattr(model, "shape_label", ()) or ())]
                    object_indices = _shape_indices_below_paths(labels, (obj.prim_path,))
                    pad_indices = _shape_indices_below_paths(labels, fingertip_set.tip_link_paths)
                    count_values = contacts.rigid_contact_count.numpy().reshape(-1)
                    count = int(count_values[0]) if len(count_values) else 0
                    shape0 = contacts.rigid_contact_shape0.numpy().reshape(-1)[:count]
                    shape1 = contacts.rigid_contact_shape1.numpy().reshape(-1)[:count]
                    forces = contacts.rigid_contact_force.numpy().reshape(-1, 3)[:count]
                    min_force = float(config.get("newton_descent_contact_force_min_n", 1.0e-6))
                    return any(
                        (
                            (int(a) in object_indices and int(b) in pad_indices)
                            or (int(b) in object_indices and int(a) in pad_indices)
                        )
                        and float(np.linalg.norm(force)) > min_force
                        for a, b, force in zip(shape0, shape1, forces)
                    )
                except Exception:
                    return False

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
            # world -Z; if the rendered gripper points the wrong way, this tells
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
                ctx.log(
                    "FET028 weld-check[%s]: base world quat (w,x,y,z)="
                    "(%.3f, %.3f, %.3f, %.3f); forward_axis now points world "
                    "(%.3f, %.3f, %.3f) -- want (0, 0, -1)."
                    % (
                        shape,
                        _bq.GetReal(),
                        _bi[0],
                        _bi[1],
                        _bi[2],
                        _fnow[0],
                        _fnow[1],
                        _fnow[2],
                    )
                )

            # Keyframe: gripper poised above the object (start of the recorded
            # action). The positioning move above was silent, so this is the
            # first action frame -- no confusing up-move precedes it.
            await _capture(f"{shape}_positioned")

            # 5a. Open + sign-flip guard (early-exit on master-DOF
            # position stall, same robust signal as _drive_to_close).
            await _drive_to_open(
                ctx,
                robot,
                grasp_specs,
                fingertip_set,
                config,
                on_step=_video_capture,
            )
            # Capture the gripper state BEFORE the post-open check, so a
            # failure here (most common cause of FET028 setup issues:
            # open/close mapping inverted on a new asset) still produces
            # a frame the user can inspect to see what the gripper did.
            await _capture(f"{shape}_after_open_command")

            # Verify the open command actually moved the master mimic
            # joint to its OPEN position. We check joint position rather
            # than fingertip-pad world separation because
            # _measure_finger_separation reads
            # UsdGeom.XformCache.GetLocalToWorldTransform() which returns
            # the USD-authored transform. Many production assets have
            # all-identity rest-pose transforms with the kinematic chain
            # established only at runtime by physics, so the USD-side
            # measurement is 0 even when the gripper is visibly open.
            # Joint position is read from the physics state and is
            # reliable.
            #
            # We also record measured_separation as a metric (still useful
            # for diagnostics where rest-pose transforms ARE authored) but
            # don't gate the test on it.
            joint_positions = robot.get_joint_positions()
            if joint_positions is None:
                ctx.fail(
                    "INTERNAL: articulation.get_joint_positions() returned\n"
                    "None after the open command on shape '%s'. The Isaac\n"
                    "physics view is not initialized for this articulation\n"
                    "-- FET028 has nothing to read post-open. This is a\n"
                    "test-framework bug or an articulation-initialization\n"
                    "race, not an asset-authoring issue: file a bug against\n"
                    "the core tier's FET028 runtime-test implementation with the\n"
                    "asset path so the harness can be hardened to ensure\n"
                    "the physics view is ready before _drive_to_open\n"
                    "returns." % shape,
                    details={"shape": shape},
                )
                return
            # Per-DOF open check: every grasp DOF must have reached its OPEN
            # target. The worst-offending DOF (largest position error) drives
            # the pass/fail + diagnostic -- catches a sign-flip (a flexor at its
            # closed limit) or a stuck flexor on either a jaw (1 DOF) or a hand
            # (N flexors). Joint position is read from physics (reliable);
            # USD-side fingertip separation is recorded for diagnostics only.
            worst_err, worst_spec, worst_actual = -1.0, grasp_specs[0], 0.0
            for s in grasp_specs:
                actual = float(joint_positions[int(s["idx"])])
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
            # catches both sign-flips (joint at the opposite limit) and
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

            async def _hold_open(_i, _total=None):
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
                _newton_pad_bounds = (
                    _newton_shape_world_bounds(fingertip_set.tip_link_paths)
                    if scene_info.get("active_physics_engine") == "newton"
                    else []
                )
                if _newton_pad_bounds:
                    # The Newton tensor state is authoritative after the first
                    # cook. Fabric/USD link transforms can lag the compiled
                    # articulation and previously produced a 0.323 m descent.
                    _tip_z = [float(bounds[0][2]) for bounds in _newton_pad_bounds]
                else:
                    _tips = _pad_world_tips(
                        robot,
                        stage,
                        fingertip_set.candidate_tip_paths or fingertip_set.tip_link_paths,
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
            if stationary_load_test:
                descent_max = 0.0
                ctx.log(
                    "FET028 Newton stationary-load mode[%s]: object authored at "
                    "the grasp center; preserving the asset's native fixed-base "
                    "articulation." % shape
                )
            if descent_max <= 0.0 and fingertip_set.kind != "independent_fingers" and not stationary_load_test:
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

            n_chunks = (
                1
                if stationary_load_test
                else _descent_chunk_count(
                    descent_max,
                    int(config.get("descent_contact_chunks", 12)),
                    float(config.get("descent_contact_max_step_m", 0.005)),
                )
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
                pad_contact = _newton_object_pad_contact()
                motion_contact = obj_z_now < obj_ref_z - contact_drop or xy_shift > contact_drop
                if pad_contact or (scene_info.get("active_physics_engine") != "newton" and motion_contact):
                    contacted = True
                    ctx.log(
                        "FET028 descent contact[%s] after %.4f m (pad_contact=%s, "
                        "object z=%.4f, settled z=%.4f, xy_shift=%.4f) -- stopping descent."
                        % (shape, descended, pad_contact, obj_z_now, obj_ref_z, xy_shift)
                    )
                    break
            # A Newton position actuator can still trail the final smoothstep
            # target after the ramp has ended.  Give it enough time to reach
            # the commanded grasp depth before deciding whether the open hand
            # touched the object.  PhysX settles within the existing short
            # window; retaining that value avoids changing its established
            # timing and baseline captures.
            descent_settle_s = 0.5 if scene_info.get("active_physics_engine") == "newton" else 0.1
            await _settle_for_seconds(ctx, descent_settle_s, on_step=_hold_open)

            # Contact may occur during the endpoint settle rather than during
            # the ramp itself.  Re-read the object after the rail has converged
            # so that contact relief is based on the actual final pose.
            if not contacted:
                obj_z_now = _object_z_runtime()
                obj_xy_now = np.asarray(_object_xy_runtime())
                xy_shift = float(np.linalg.norm(obj_xy_now - obj_ref_xy))
                pad_contact = _newton_object_pad_contact()
                motion_contact = obj_z_now < obj_ref_z - contact_drop or xy_shift > contact_drop
                if pad_contact or (scene_info.get("active_physics_engine") != "newton" and motion_contact):
                    contacted = True
                    ctx.log(
                        "FET028 descent contact[%s] during endpoint settle after "
                        "%.4f m (pad_contact=%s, object z=%.4f, settled z=%.4f, "
                        "xy_shift=%.4f)." % (shape, descended, pad_contact, obj_z_now, obj_ref_z, xy_shift)
                    )
                else:
                    ctx.log(
                        "FET028 descent[%s] reached grasp depth (%.4f m) with no "
                        "object nudge detected; closing at that depth." % (shape, descended)
                    )

            if stationary_load_test:
                backoff_up = 0.0
            elif fingertip_set.kind == "independent_fingers":
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
            # boost, no USD edits. If the gripper can't grip its
            # rated payload with its authored drive, that's a real
            # failure signal about the asset's drive tuning.
            # ``close_contact`` is the stall-based proxy for "the fingers met the
            # object": the close stalled BELOW its closed target on at least one
            # DOF, i.e. the chain jammed against the object rather than reaching
            # its hard stop in empty space. Returned by _drive_to_close; gates
            # the lift.
            close_contact = await _drive_to_close(
                ctx,
                robot,
                grasp_specs,
                fingertip_set,
                config,
                on_step=_video_capture,
            )
            grasp_search_depth = 0.0
            if not close_contact and fingertip_set.kind != "independent_fingers" and not stationary_load_test:
                search_attempts = max(0, int(config.get("grasp_depth_search_attempts", 4)))
                search_step = radius * float(config.get("grasp_depth_search_step_radius_fraction", 0.5))
                for search_attempt in range(1, search_attempts + 1):
                    ctx.log(
                        "FET028 grasp-depth search[%s]: close reached its limit "
                        "without contact; reopening and descending %.4f m "
                        "(attempt %d/%d)." % (shape, search_step, search_attempt, search_attempts)
                    )
                    await _drive_to_open(
                        ctx,
                        robot,
                        grasp_specs,
                        fingertip_set,
                        config,
                        on_step=_video_capture,
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
                        0.5 if scene_info.get("active_physics_engine") == "newton" else 0.1,
                        on_step=_hold_open,
                    )
                    grasp_search_depth += search_step
                    await _capture(f"{shape}_grasp_search_{search_attempt}")
                    close_contact = await _drive_to_close(
                        ctx,
                        robot,
                        grasp_specs,
                        fingertip_set,
                        config,
                        on_step=_video_capture,
                    )
                    if close_contact:
                        ctx.log(
                            "FET028 grasp-depth search[%s]: contact established "
                            "after %.4f m additional descent." % (shape, grasp_search_depth)
                        )
                        break
            ctx.add_metric(f"grasp_depth_search_m_{shape}", grasp_search_depth)
            ctx.add_metric(f"close_blocked_by_object_{shape}", bool(close_contact))

            # Diagnose how the close actually ended, per DOF: a DOF near its
            # CLOSED target reached its hard stop (no object blocking that
            # finger); a DOF stalled short is jammed against the object (good --
            # contact is real). Fraction = 0 at open, 1 at closed.
            try:
                joint_positions = robot.get_joint_positions()
                if joint_positions is not None:
                    fractions = []
                    for s in grasp_specs:
                        actual_close = float(joint_positions[int(s["idx"])])
                        frac = (actual_close - s["open"]) / max(1e-9, s["closed"] - s["open"])
                        fractions.append(frac)
                        ctx.add_metric(f"close_joint_actual_{shape}_{s['name']}", actual_close)
                    mean_frac = float(np.mean(fractions)) if fractions else 0.0
                    ctx.add_metric(f"close_joint_fraction_{shape}", mean_frac)
                    ctx.log(
                        "Close ended: per-DOF closed-fraction=%s (mean %.0f%%) -- %s"
                        % (
                            [round(f, 2) for f in fractions],
                            100.0 * mean_frac,
                            (
                                "BLOCKED on object (likely contact)"
                                if close_contact
                                else "REACHED limits (no contact / fingers met)"
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
                        "during close. The gripper's authored drive "
                        "is too aggressive for this object's mass: "
                        "the fingers slammed shut and bumped the "
                        "object out before contact stabilized. Asset "
                        "tuning issue (lower drive stiffness or "
                        "increase damping)." % object_lateral_drift
                    )
            except Exception as exc:
                ctx.log("Cube-position diagnostic skipped: %s" % exc)

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
                    "The lift only starts once the gripper has the object in a\n"
                    "real grasp (all fingers in contact). Geometric+stall proxy:\n"
                    "  - close stalled on the object (contact): %s\n"
                    "  - object still between the fingers (lateral %.3f m <= "
                    "retain tolerance %.3f m): %s\n"
                    "%s closed but did not capture the object: the fingers\n"
                    "either met in empty space (no contact) or knocked the\n"
                    "object out of the grasp during the close. Inspect the\n"
                    "%s_closed / %s_engaged captures and the close metrics."
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
                "FET028 grip-confirmed[%s]: contact=%s, object retained "
                "(lateral %.3f m) -- starting lift." % (shape, close_contact, grip_lateral)
            )

            # 5e. Lift via the gantry's prismatic Z drive.
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
            # gravity (drive genuinely too weak, or the attach_joint is broken).
            if actual_translate < min_lift:
                ctx.fail(
                    "INTERNAL: FET028 test gantry lifted only %.4f m (need at\n"
                    "least %.4f m to evaluate the grasp; commanded %.4f m). The\n"
                    "gantry is the test-owned prismatic Z-axis carrier authored\n"
                    "by ``attach_carrier()``, not the asset. Likely causes (all\n"
                    "in the test framework):\n"
                    "  - gantry drive stiffness / maxForce too low for the\n"
                    "    combined gripper + payload mass (tune gripper_carrier.py).\n"
                    "  - attach_joint FixedJoint between gantry and gripper base\n"
                    "    is broken / mis-bodied.\n"
                    "This is not an asset-authoring issue." % (actual_translate, min_lift, commanded_translate),
                    details={
                        "actual_translate": actual_translate,
                        "commanded_translate": commanded_translate,
                        "min_lift_for_eval_m": min_lift,
                        "shape": shape,
                    },
                )
                return
            if abs(actual_translate - commanded_translate) > float(config["carrier_translate_tolerance_m"]):
                # Partial lift: the gantry drive lagged the command but lifted
                # enough to evaluate. Note it (drive tuning), do not fail.
                ctx.warn(
                    "FET028 gantry lift lagged the command (actual %.4f m vs "
                    "commanded %.4f m); grasp is evaluated against the actual "
                    "lift. Heavier gripper + payload; the gantry drive in "
                    "gripper_carrier.py could be stiffened if needed." % (actual_translate, commanded_translate)
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
                gripper_pre_shake_z = float(carrier_world_position(carrier)[2])
                offset_pre_shake = float(object_post_lift[2]) - gripper_pre_shake_z

                async def _shake_video(_i, _total=None):
                    """Track object min z + relative slip vs gripper during shake."""
                    nonlocal shake_min_z, shake_max_rel_slip
                    try:
                        obj_z = _object_z_runtime()
                        gripper_z = float(carrier_world_position(carrier)[2])
                        if obj_z < shake_min_z:
                            shake_min_z = obj_z
                        rel_slip = abs((obj_z - gripper_z) - offset_pre_shake)
                        if rel_slip > shake_max_rel_slip:
                            shake_max_rel_slip = rel_slip
                    except Exception:
                        pass
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
                )
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

            if result.passed:
                winning_shape = shape
                break
            await _capture(f"{shape}_failed")

        finally:
            if carrier is not None:
                try:
                    await detach_carrier(stage, carrier, ctx=ctx)
                except Exception as exc:
                    ctx.log("detach_carrier failed (ignored): %s" % exc)
            # Remove only the unique object namespace created by this run.
            if obj is not None:
                try:
                    root_prim = stage.GetPrimAtPath(obj.root_path)
                    if root_prim and root_prim.IsValid():
                        stage.RemovePrim(obj.root_path)
                except Exception as exc:
                    ctx.log("Test-object cleanup skipped: %s" % exc)
            # Encode the per-shape video. ``encode_video`` deletes the
            # source PNGs by default to keep the captures/ directory
            # focused on the labeled story frames (discovery, opened,
            # spawned, engaged, closed, mid_lift, lifted, failed).
            if video_frames:
                try:
                    ctx.encode_video(
                        video_frames,
                        fps=int(round(video_fps_max)),
                        label=f"{shape}_grasp_lift",
                        role="summary",
                    )
                except Exception as exc:
                    ctx.log("Video encode skipped for %s: %s" % (shape, exc))

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
    * ``/World/_FET028_Objects`` -- spawned synthetic test objects.
      No per-iteration cleanup hook exists today, so without this the
      second-and-later shape attempts inherit the prior iteration's
      collider sitting in the grasp volume.

    The trailing ``physics_step`` call flushes pending USD changes to
    the PhysX/tensor backend so subsequent state queries see the
    cleaned stage (project memory: tensor reads need one frame after
    world.reset before they are reliable).
    """
    import omni.usd
    from simready_benchmark_kit_suite.articulation_phases.gripper_carrier import (
        _GANTRY_ROOT,
    )
    from simready_benchmark_kit_suite.articulation_phases.object_spawning import (
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


def _link_local_centroid(stage, path):
    """Geometry-bound midpoint of a link in its OWN body frame (pose-independent),
    or the origin (zeros) when the link has no computable bound."""
    from pxr import Usd, UsdGeom

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return np.zeros(3)
    try:
        bound = UsdGeom.Imageable(prim).ComputeUntransformedBound(
            Usd.TimeCode.Default(), UsdGeom.Tokens.default_, UsdGeom.Tokens.render
        )
        rng = bound.ComputeAlignedRange()
        if rng.IsEmpty():
            return np.zeros(3)
        c = rng.GetMidpoint()
        return np.array([float(c[0]), float(c[1]), float(c[2])], dtype=np.float64)
    except Exception:
        return np.zeros(3)


def _link_local_corners(stage, path):
    """The 8 corners of the link's local geometry bound (local units), or None."""
    from pxr import Usd, UsdGeom

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None
    try:
        bound = UsdGeom.Imageable(prim).ComputeUntransformedBound(
            Usd.TimeCode.Default(), UsdGeom.Tokens.default_, UsdGeom.Tokens.render
        )
        rng = bound.ComputeAlignedRange()
        if rng.IsEmpty():
            return None
        mn, mx = rng.GetMin(), rng.GetMax()
    except Exception:
        return None
    return np.array(
        [[x, y, z] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])],
        dtype=np.float64,
    )


def _pad_world_tips(robot, stage, paths, approach_world):
    """Live world position of each link's most-distal geometry corner along the
    approach direction (the finger TIP / contact end), ``{path: (3,)}``.

    The tip moves far more than the whole-link centroid as the jaw opens/closes,
    so it gives a robust open/close signal for a centric gripper whose link
    centroids barely move. Local corners are scaled by the link's world scale
    (mm-modelled assets) then rotated by the live link orientation.
    """
    from pxr import Gf

    appr = np.asarray(approach_world, dtype=np.float64)
    appr = appr / (float(np.linalg.norm(appr)) or 1.0)
    out = {}
    for path, (pos, quat_xyzw) in robot.get_link_world_transforms(paths).items():
        corners = _link_local_corners(stage, path)
        if corners is None:
            continue
        corners = corners * _link_world_scale(stage, path)
        rot = Gf.Rotation(Gf.Quatd(float(quat_xyzw[3]), float(quat_xyzw[0]), float(quat_xyzw[1]), float(quat_xyzw[2])))
        world = []
        for c in corners:
            r = rot.TransformDir(Gf.Vec3d(float(c[0]), float(c[1]), float(c[2])))
            world.append((float(r[0]) + pos[0], float(r[1]) + pos[1], float(r[2]) + pos[2]))
        world = np.array(world, dtype=np.float64)
        out[path] = world[int(np.argmax(world @ appr))]
    return out


def _link_world_scale(stage, path):
    """Accumulated world scale of a link (mean basis-vector length of its
    local-to-world transform). ~1.0 for unscaled assets, ~0.001 for a
    millimeter-modelled asset under a 0.001 root scale."""
    from pxr import UsdGeom

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return 1.0
    m = np.array(UsdGeom.XformCache().GetLocalToWorldTransform(prim)).reshape(4, 4)
    s = float(np.mean([np.linalg.norm(m[i, :3]) for i in range(3)]))
    return s if s > 1e-9 else 1.0


def _pad_world_centroids(robot, stage, paths):
    """Live world geometry centroids ``{path: (3,)}`` of the given links.

    ``centroid_world = link_pose_position + R(link_pose) * (local_centroid *
    world_scale)``. The centroid is distal (at the pad), so it tracks the actual
    contact surface -- unlike the proximal link ORIGIN, which on a 4-bar gripper
    moves opposite to the pad. The local geometry bound is in the link's LOCAL
    units, which are NOT world metres on a scaled asset, so it is multiplied by
    the link's accumulated world scale before being rotated into world. Poses are
    read from the physics tensor view (link poses are not in USD).
    """
    from pxr import Gf

    out = {}
    for path, (pos, quat_xyzw) in robot.get_link_world_transforms(paths).items():
        lc = _link_local_centroid(stage, path) * _link_world_scale(stage, path)
        rot = Gf.Rotation(Gf.Quatd(float(quat_xyzw[3]), float(quat_xyzw[0]), float(quat_xyzw[1]), float(quat_xyzw[2])))
        r = rot.TransformDir(Gf.Vec3d(float(lc[0]), float(lc[1]), float(lc[2])))
        out[path] = np.array([float(r[0]) + pos[0], float(r[1]) + pos[1], float(r[2]) + pos[2]], dtype=np.float64)
    return out


def _hand_cup_descent(lowest_fingertip_z, object_center_z, clearance_m):
    """Descent so the lowest open fingertip reaches the object reference.

    ``clearance_m`` retains a generic caller-controlled separation. The result
    is never negative when the fingertip is already at or below the target.
    """
    return max(0.0, float(lowest_fingertip_z) - (float(object_center_z) + float(clearance_m)))


def _authored_master_drive_target(stage, robot, master_idx):
    """Return the master joint's authored rest target in runtime units.

    USD angular drive targets are authored in degrees while articulation APIs
    expose angular positions in radians. Linear targets already use stage
    distance units. ``None`` means there is no unambiguous authored target.
    """
    from pxr import UsdPhysics

    dof_names = list(getattr(robot, "dof_names", ()) or ())
    if master_idx < 0 or master_idx >= len(dof_names):
        return None
    joint_name = str(dof_names[master_idx])
    matches = []
    # A precompiled Newton carrier owns the articulation view while the asset
    # joint remains under /World/AssetRoot/Asset, outside ``robot.prim_path``.
    # Search the test stage and accept the value only when every same-named
    # joint agrees, so a duplicated/conflicting joint cannot silently win.
    for prim in stage.Traverse():
        if prim.GetName() != joint_name:
            continue
        if prim.IsA(UsdPhysics.RevoluteJoint):
            drive = UsdPhysics.DriveAPI.Get(prim, "angular")
            value = drive.GetTargetPositionAttr().Get() if drive else None
            if value is not None:
                matches.append(math.radians(float(value)))
        elif prim.IsA(UsdPhysics.PrismaticJoint):
            drive = UsdPhysics.DriveAPI.Get(prim, "linear")
            value = drive.GetTargetPositionAttr().Get() if drive else None
            if value is not None:
                matches.append(float(value))
    if not matches:
        return None
    first = matches[0]
    if any(not math.isclose(first, value, rel_tol=1e-6, abs_tol=1e-8) for value in matches[1:]):
        return None
    return first


async def _detect_open_closed_positions(ctx, robot, fingertip_set, stage, config, max_opening):
    """Identify the finger-pad links AND which master-DOF limit is OPEN, purely
    from MOTION, and return ``(open_pos, closed_pos)``.

    Drives the master DOF to each joint limit and reads LIVE link world poses
    (finger links have no live USD pose -- ``UsdGeom.XformCache`` returns the
    static rest pose for every one of them, so a USD read cannot tell open from
    closed; see ``RobotHandle.get_link_world_positions``). Among all candidate
    tip bodies, the real jaw pads are the PAIR whose separation changes most
    between the two limits (internal 4-bar linkage bodies barely move relative to
    each other); OPEN is the limit at which that pair is widest.
    ``fingertip_set.tip_link_paths`` is updated in place to the identified pads so
    every downstream measurement uses the real contact pads.

    Asset-agnostic: no assumption about which limit is open (some grippers author
    lower=open while others author upper=open) and no reliance
    on static USD link xforms.
    """
    import itertools

    master_indices = list(fingertip_set.mimic_master_dofs or [int(fingertip_set.mimic_master_dof)])
    master_indices = [int(index) for index in master_indices]
    master_idx = int(fingertip_set.mimic_master_dof)
    lowers, uppers = robot.get_joint_position_limits()
    lo = float(lowers[master_idx])
    up = float(uppers[master_idx])
    if not np.isfinite(lo) or not np.isfinite(up):
        raise RuntimeError(
            "Master mimic DOF idx=%d has no finite joint limits (lower=%r, "
            "upper=%r). FET028 needs both limits to detect open/close; author "
            "<UsdPhysics:lowerLimit> and <UsdPhysics:upperLimit> on the joint." % (master_idx, lo, up)
        )
    for leader_idx in master_indices:
        leader_lo = float(lowers[leader_idx])
        leader_up = float(uppers[leader_idx])
        if not np.isfinite(leader_lo) or not np.isfinite(leader_up):
            raise RuntimeError(
                "Parallel-jaw leader DOF idx=%d has no finite joint limits "
                "(lower=%r, upper=%r)." % (leader_idx, leader_lo, leader_up)
            )

    if bool(getattr(fingertip_set, "tips_from_grip_line", False)):
        # FET028 defines the parallel-jaw convention explicitly: lowerLimit is
        # OPEN and upperLimit is CLOSED.  When the authored grip line already
        # identified the actual pad bodies, driving to both endpoints merely to
        # rediscover that convention is redundant.  More importantly, a tight
        # Newton four-bar can accumulate constraint error during a full
        # close->open probe and begin the real grasp in an asymmetric pose.
        ctx.add_metric("detect_used_authored_grip_line", True)
        ctx.log(
            "FET028 pad/open detect: grip-line endpoints resolved pads=(%s, %s); "
            "using contract convention OPEN=lower %.4f, CLOSED=upper %.4f "
            "without a destructive endpoint pre-sweep."
            % (
                fingertip_set.tip_link_paths[0].rsplit("/", 1)[-1],
                fingertip_set.tip_link_paths[1].rsplit("/", 1)[-1],
                lo,
                up,
            )
        )
        return lo, up

    candidates = list(fingertip_set.candidate_tip_paths or fingertip_set.tip_link_paths)
    drive_steps = int(config.get("open_close_detect_steps", 120))

    authored_rest = _authored_master_drive_target(stage, robot, master_idx)

    # Probe slightly INSIDE the limits, not at the exact stops. Some grippers
    # (e.g. the over-constrained ezu centric mimic) PIN at their exact joint stop
    # and refuse to move, so probing AT the limit reads no finger motion at all.
    # open/closed are still reported as the true limits below; only the probe
    # drive targets are inset.
    span = up - lo
    inset = float(config.get("detect_limit_inset_frac", 0.05)) * span
    lo_probe, up_probe = lo + inset, up - inset

    # Measure each candidate at its geometry CENTROID (distal, at the pad) -- NOT
    # at the link ORIGIN. On the 2F-85 4-bar linkage the inner-finger link origins
    # sit at the proximal pivots, which SPREAD as the jaws close (opposite to the
    # pad tips), so an origin-based aperture is inverted. The centroid tracks the
    # actual pad, so "widest = open" is correct.
    async def _ramp_master(target):
        start_positions = np.asarray(robot.get_joint_positions(), dtype=np.float64)
        if start_positions.ndim != 1 or start_positions.size != robot.dof_count:
            raise RuntimeError("FET028 open/close detection could not read the articulation state")
        starts = np.asarray([float(start_positions[index]) for index in master_indices], dtype=np.float64)
        primary_span = up - lo
        alpha = 0.0 if abs(primary_span) <= 1e-12 else (float(target) - lo) / primary_span
        targets = np.asarray(
            [
                float(lowers[index]) + alpha * (float(uppers[index]) - float(lowers[index]))
                for index in master_indices
            ],
            dtype=np.float64,
        )
        for step in range(drive_steps):
            t = float(step + 1) / float(drive_steps)
            eased = t * t * (3.0 - 2.0 * t)
            from isaacsim.core.utils.types import ArticulationAction

            commanded = starts + (targets - starts) * eased
            robot.apply_action(
                ArticulationAction(
                    joint_positions=np.asarray(commanded, dtype=np.float32),
                    joint_indices=np.asarray(master_indices, dtype=np.int32),
                )
            )
            await ctx.step_one()

    async def _drive_and_read(target):
        await _ramp_master(target)
        cen = _pad_world_centroids(robot, stage, candidates)
        # The first get_link_transforms() after (re)cook can return the ROOT pose
        # for every link (stale buffer -> all coincident). Retry a few steps until
        # the links actually spread.
        for _ in range(8):
            vals = list(cen.values())
            spread = 0.0
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    spread = max(spread, float(np.linalg.norm(vals[i] - vals[j])))
            if spread > 1e-3:
                break
            await ctx.step_one()
            cen = _pad_world_centroids(robot, stage, candidates)
        return cen

    async def _drive_and_read_tips(target):
        await _ramp_master(target)
        # The gripper is reoriented so its forward_axis points down (-Z), so
        # the distal finger tips are the lowest geometry corners.
        return _pad_world_tips(robot, stage, candidates, (0.0, 0.0, -1.0))

    pos_lo = await _drive_and_read(lo_probe)
    pos_up = await _drive_and_read(up_probe)

    if not pos_lo or not pos_up:
        raise RuntimeError(
            "FET028 open/close detection could not read live poses for any of "
            "the %d candidate tip bodies (RobotHandle.get_link_world_positions "
            "returned nothing -- the articulation physics view may not expose "
            "link transforms)." % len(candidates)
        )

    # The jaw pads are the candidate pair whose distal geometry has a lateral
    # separation matching the authored max jaw opening.  Use the geometry tip,
    # projected onto the plane perpendicular to the top-down grasp axis, rather
    # than body centroids or full 3-D distance.  A four-bar gripper's proximal
    # knuckles can be much farther apart in Z and can therefore dominate a 3-D
    # distance even though they are not contact pads.
    tips_lo = await _drive_and_read_tips(lo_probe)
    tips_up = await _drive_and_read_tips(up_probe)
    distal_z = {
        path: min(float(tips_lo[path][2]), float(tips_up[path][2]))
        for path in candidates
        if path in tips_lo and path in tips_up
    }
    most_distal_z = min(distal_z.values()) if distal_z else 0.0
    best = None  # (score, a, b, sep_lo, sep_up)
    preferred_paths = set(fingertip_set.tip_link_paths or ())
    preferred_best = None
    for a, b in itertools.combinations(candidates, 2):
        if a not in tips_lo or b not in tips_lo or a not in tips_up or b not in tips_up:
            continue
        delta_lo = tips_lo[a] - tips_lo[b]
        delta_up = tips_up[a] - tips_up[b]
        sep_lo = float(np.linalg.norm(delta_lo[:2]))
        sep_up = float(np.linalg.norm(delta_up[:2]))
        peak = max(sep_lo, sep_up)
        # Opposed pads terminate at approximately the same height *and* are the
        # most distal geometry along the grasp direction.  Equal-height alone
        # is insufficient: two proximal knuckles are also symmetric and can
        # accidentally have a separation close to maxOpening.
        z_mismatch = max(abs(float(delta_lo[2])), abs(float(delta_up[2])))
        distal_penalty = (distal_z[a] - most_distal_z) + (distal_z[b] - most_distal_z)
        score = abs(peak - float(max_opening)) + z_mismatch + 4.0 * distal_penalty
        ctx.log(
            "FET028 pad candidate (%s, %s): lateral @lo=%.4f @up=%.4f, "
            "z-mismatch=%.4f, distal-penalty=%.4f, score=%.4f."
            % (
                a.rsplit("/", 1)[-1],
                b.rsplit("/", 1)[-1],
                sep_lo,
                sep_up,
                z_mismatch,
                distal_penalty,
                score,
            )
        )
        if best is None or score < best[0]:
            best = (score, a, b, sep_lo, sep_up)
        if len(preferred_paths) == 2 and {a, b} == preferred_paths:
            preferred_best = (score, a, b, sep_lo, sep_up)

    # Fingertip discovery can resolve the pad bodies directly from the authored
    # gripper_grip_line endpoints.  Keep that semantic result authoritative;
    # the live probe determines direction/travel, not which two links the asset
    # declared as its contact pads.
    if preferred_best is not None:
        best = preferred_best
        ctx.log(
            "FET028 pad selection: using grip-line endpoint bodies (%s, %s)."
            % (best[1].rsplit("/", 1)[-1], best[2].rsplit("/", 1)[-1])
        )

    if best is None:
        # CENTRIC fallback: 3+ fingers converging on a
        # shared center have no opposed "pad pair" with a jaw-sized pairwise
        # excursion, so the parallel-jaw test above finds nothing. Measure the
        # group SPREAD instead -- the sum of each finger centroid's distance to
        # the group centroid -- which is large when the fingers are OPEN
        # (spread out) and small when CLOSED (converged). OPEN = wider spread.
        def _group_spread(tips):
            pts = np.array(list(tips.values()))
            if len(pts) < 2:
                return 0.0
            return float(np.sum(np.linalg.norm(pts - pts.mean(axis=0), axis=1)))

        spread_lo = _group_spread(tips_lo)
        spread_up = _group_spread(tips_up)
        if max(spread_lo, spread_up) <= 1e-4:
            raise RuntimeError(
                "FET028 open/close detection: no parallel-jaw pad pair and no "
                "centric finger-tip spread among %d candidates (spread lo=%.5f "
                "up=%.5f). Cannot determine open/close." % (len(candidates), spread_lo, spread_up)
            )
        spread_delta = abs(spread_up - spread_lo)
        ambiguity_tol = max(1e-5, 1e-3 * max(spread_lo, spread_up))
        if spread_delta <= ambiguity_tol:
            if authored_rest is None:
                raise RuntimeError(
                    "FET028 open/close detection is ambiguous: centric finger-tip "
                    "spread is unchanged between the lower and upper probes "
                    "(lo=%.5f, up=%.5f), and the master joint has no authored "
                    "drive target to identify its rest/open endpoint." % (spread_lo, spread_up)
                )
            if abs(authored_rest - lo) <= abs(authored_rest - up):
                open_pos, closed_pos, open_tips = lo, up, tips_lo
            else:
                open_pos, closed_pos, open_tips = up, lo, tips_up
            ctx.add_metric("detect_open_close_ambiguous", True)
            ctx.log(
                "FET028 open/close geometry was ambiguous (spread delta %.6f m); "
                "using authored master drive target %.4f to identify OPEN %.4f "
                "and CLOSED %.4f." % (spread_delta, authored_rest, open_pos, closed_pos)
            )
        elif spread_up > spread_lo:
            open_pos, closed_pos, open_tips = up, lo, tips_up
        else:
            open_pos, closed_pos, open_tips = lo, up, tips_lo
        # Downstream logic expects two "pad" links: use the two fingers whose
        # tips are furthest apart at the OPEN limit as representative opposed pads.
        pair = max(
            itertools.combinations(list(open_tips.keys()), 2),
            key=lambda ab: float(np.linalg.norm(open_tips[ab[0]] - open_tips[ab[1]])),
        )
        fingertip_set.tip_link_paths = list(pair)
        ctx.add_metric("detect_centric_spread_open_m", float(max(spread_lo, spread_up)))
        ctx.add_metric("detect_centric_spread_closed_m", float(min(spread_lo, spread_up)))
        ctx.log(
            "FET028 CENTRIC open/close detect: %d fingers, tip spread @lo=%.4f "
            "@up=%.4f -> OPEN master=%.4f, CLOSED master=%.4f; pads=(%s, %s)."
            % (
                len(candidates),
                spread_lo,
                spread_up,
                open_pos,
                closed_pos,
                pair[0].rsplit("/", 1)[-1],
                pair[1].rsplit("/", 1)[-1],
            )
        )
        return open_pos, closed_pos

    _score, pad_a, pad_b, sep_lo, sep_up = best
    delta = abs(sep_up - sep_lo)
    fingertip_set.tip_link_paths = [pad_a, pad_b]

    aperture_delta = abs(sep_up - sep_lo)
    ambiguity_tol = max(1e-4, 0.10 * float(max_opening))
    if aperture_delta <= ambiguity_tol and authored_rest is not None:
        # Bounding-box corners can move with the link while retaining almost
        # the same pairwise separation on a four-bar gripper.  In that case
        # geometry does not provide a trustworthy direction, while the
        # authored drive target is the asset's explicit rest/open state.
        if abs(authored_rest - lo) <= abs(authored_rest - up):
            open_pos, closed_pos, open_sep, closed_sep = lo, up, sep_lo, sep_up
        else:
            open_pos, closed_pos, open_sep, closed_sep = up, lo, sep_up, sep_lo
        ctx.add_metric("detect_open_close_ambiguous", True)
        ctx.log(
            "FET028 selected-pad aperture delta %.4f m is ambiguous; using "
            "authored master rest target %.4f to identify OPEN %.4f and CLOSED %.4f."
            % (aperture_delta, authored_rest, open_pos, closed_pos)
        )
    elif sep_up >= sep_lo:
        open_pos, closed_pos, open_sep, closed_sep = up, lo, sep_up, sep_lo
    else:
        open_pos, closed_pos, open_sep, closed_sep = lo, up, sep_lo, sep_up

    ctx.add_metric("detect_pad_open_aperture_m", float(open_sep))
    ctx.add_metric("detect_pad_closed_aperture_m", float(closed_sep))
    ctx.add_metric("detect_pad_aperture_delta_m", float(delta))
    ctx.log(
        "FET028 pad/open detect: pads=(%s, %s) aperture open=%.4f m "
        "closed=%.4f m (delta=%.4f) -> OPEN master=%.4f, CLOSED master=%.4f."
        % (
            pad_a.rsplit("/", 1)[-1],
            pad_b.rsplit("/", 1)[-1],
            open_sep,
            closed_sep,
            delta,
            open_pos,
            closed_pos,
        )
    )
    return open_pos, closed_pos


def _command_grasp_targets(robot, grasp_specs, key, target_values=None):
    """Command only the selected grasp DOFs.

    RobotHandle expands sparse commands for a standard Newton articulation and
    preserves them for mixed native-actuator/standard-drive articulations.  An
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


def _contact_active_specs(grasp_specs, tolerance=1e-9):
    """Specs that actually close; held positioning DOFs cannot imply contact."""
    return [
        spec
        for spec in grasp_specs
        if spec.get("contact_active", abs(float(spec["closed"]) - float(spec["open"])) > tolerance)
    ]


async def _drive_to_open(ctx, robot, grasp_specs, fingertip_set, config, on_step=None):
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

    for i in range(max_steps):
        _command_grasp_targets(robot, grasp_specs, "open")
        await ctx.step_one()
        if on_step is not None:
            await on_step(i)

        cur = _grasp_positions(robot, grasp_specs)
        if cur is None:
            continue
        for h, p in zip(histories, cur):
            h.append(p)
            if len(h) > stall_window + 1:
                h.pop(0)

        if all(len(h) > stall_window for h in histories):
            max_range = max(max(h[-stall_window - 1 :]) - min(h[-stall_window - 1 :]) for h in histories)
            if max_range < stall_eps:
                return


async def _drive_to_close(ctx, robot, grasp_specs, fingertip_set, config, on_step=None):
    """Drive every grasp DOF toward its CLOSED target; exit on joint stall.

    A single multi-DOF ArticulationAction sets all grasp DOFs to their 'closed'
    targets each step (1 DOF for a parallel jaw -- the mimic followers track via
    the PhysX mimic constraint -- or N flexors for a hand). Driving the DOFs
    DIRECTLY (vs ``ParallelGripper.forward('close')``, which intermittently
    PINNED the master at the open limit) is the SAME mechanism
    ``_detect_open_closed_positions`` uses and reliably moves the joints.

    Returns ``close_contact``: True if the close looks like it stalled ON THE
    OBJECT -- at least one DOF engaged (moved off open) and the grasp stalled
    before all DOFs reached their closed target. False if it never engaged (the
    drive could not move the DOFs) so the grip gate fails honestly.

    Contact readings confirm that the fingers engaged the object, but do not
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
    from simready_benchmark_kit_suite.articulation_phases.force_utils import (
        read_contact_force_magnitude,
    )

    contact_threshold = float(config["jik_contact_force_threshold_n"])
    stall_eps = float(config.get("close_position_stall_eps", 1e-3))
    stall_window = int(config.get("close_stall_window", 8))
    log_every = int(config.get("close_log_every", 30))
    total_steps = int(config["close_steps"])
    ramp_steps = max(1, min(total_steps, int(config.get("close_ramp_steps", 300))))
    # Engage guard: do NOT honor a position-stall exit until SOME DOF has
    # actually STARTED closing (moved off its open position by
    # ``close_engage_eps``). The drive's first-frame response is not
    # deterministic in this build, so on some runs the DOFs have not begun
    # moving by the time the stall window first fills -- without this guard the
    # detector misreads "drive has not started yet" as "stalled at open / no
    # contact" and the close exits at step 8 having done nothing. Once a DOF has
    # engaged, a stall is a real contact/limit stop.
    engage_eps = float(config.get("close_engage_eps", 0.002))

    contact_specs = _contact_active_specs(grasp_specs)
    if not contact_specs:
        ctx.log("close aborted: no contact-active grasp DOFs")
        return False
    # Capture the open positions BEFORE the first close step (reading only after
    # step 0 misses a fast first-step jump that then stalls on the object).
    starts = _grasp_positions(robot, contact_specs)
    all_starts = _grasp_positions(robot, grasp_specs)
    if all_starts is None:
        raise RuntimeError("Cannot close gripper: initial grasp joint positions are invalid")
    histories = [[] for _ in contact_specs]
    has_engaged = False
    cur = starts

    def _blocked():
        # Stalled SHORT of the closed target on at least one DOF -> blocked by
        # the object (real contact). Stalled AT the closed target -> the grasp
        # simply closed on empty air (no contact).
        if cur is None:
            return True
        return any(abs(cur[k] - contact_specs[k]["closed"]) > 5.0 * stall_eps for k in range(len(contact_specs)))

    for i in range(total_steps):
        ramp_t = min(1.0, float(i + 1) / float(ramp_steps))
        eased = ramp_t * ramp_t * (3.0 - 2.0 * ramp_t)
        targets = [start + (float(spec["closed"]) - start) * eased for start, spec in zip(all_starts, grasp_specs)]
        _command_grasp_targets(robot, grasp_specs, "closed", target_values=targets)
        await ctx.step_one()
        if on_step is not None:
            await on_step(i)

        forces = [read_contact_force_magnitude(robot, tip) for tip in fingertip_set.tip_link_paths]
        all_above = forces and all(f is not None and f >= contact_threshold for f in forces)
        # Contact confirms that the fingers engaged the object, but is not a
        # close-completion condition.  A position-controlled gripper must keep
        # closing after first touch to build normal force.  In particular, a
        # sphere can report bilateral contact several frames before the pads
        # have developed enough force to retain it during lift.  Finish on the
        # joint-stall condition below, which proves that the mechanism is
        # blocked by the object rather than merely touching it.
        if all_above:
            has_engaged = True

        cur = _grasp_positions(robot, contact_specs)
        if cur is not None:
            if starts is None:
                starts = cur
            if any(abs(c - s) >= engage_eps for c, s in zip(cur, starts)):
                has_engaged = True
            for h, p in zip(histories, cur):
                h.append(p)
                if len(h) > stall_window + 1:
                    h.pop(0)

        if (i % log_every) == 0 and cur is not None:
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
        ramp_complete = (i + 1) >= ramp_steps
        if ramp_complete and has_engaged and all(len(h) > stall_window for h in histories):
            max_range = max(max(h[-stall_window - 1 :]) - min(h[-stall_window - 1 :]) for h in histories)
            if max_range < stall_eps:
                blocked = _blocked()
                ctx.log(
                    "close early-exit at step %d: grasp DOFs stalled "
                    "(max position range %.5f < eps %.5f over last %d frames); "
                    "blocked_on_object=%s" % (i, max_range, stall_eps, stall_window, blocked)
                )
                return blocked
    # Loop ran the full budget. If nothing engaged, the close drive never moved
    # the gripper off its open position -- flag it so the failure reads as
    # "close did not start" (a drive / constraint problem) rather than a silent
    # no-contact, and so the grip gate fails honestly.
    if not has_engaged:
        ctx.log(
            "close ran %d steps WITHOUT engaging: grasp DOFs never moved off "
            "the open position (starts=%s). The drive could not move them -- "
            "likely the asset's mimic/limit constraint pinned a joint this run "
            "(marginal/non-deterministic), or the drive is too weak."
            % (total_steps, [round(s, 4) for s in (starts or [])])
        )
        return False
    return _blocked()


async def _settle_for_seconds(ctx, seconds: float, fps: int = 240, on_step=None):
    """Step physics for ``seconds`` of simulated time.

    ``fps`` matches the framework's default physics rate (240Hz) so
    that ``n = seconds * fps`` iterations advance physics by exactly
    ``seconds`` of simulated time AND so that the per-step
    ``on_step`` callback fires at the same rate as the close / lift
    drive loops. Mismatched rates (e.g. fps=60 with physics_fps=240)
    cause the assembled video to play at inconsistent speeds across
    phases and shorten the actual settle duration to a quarter of
    the requested ``seconds``.
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
    """
    paths = fingertip_set.tip_link_paths[:2]
    pos = robot.get_link_world_positions(paths)
    a = pos.get(paths[0])
    b = pos.get(paths[1])
    if a is None or b is None:
        return 0.0
    return float(np.linalg.norm(a - b))


def _midpoint_world(stage, fingertip_set):
    from pxr import UsdGeom

    cache = UsdGeom.XformCache()
    paths = fingertip_set.tip_link_paths
    a = np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(paths[0]))).reshape(4, 4)[3, :3]
    b = np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(paths[1]))).reshape(4, 4)[3, :3]
    return 0.5 * (a + b)


def _descent_chunk_count(distance_m, minimum_chunks, max_step_m):
    distance_m = max(0.0, float(distance_m))
    minimum_chunks = max(1, int(minimum_chunks))
    max_step_m = float(max_step_m)
    if max_step_m <= 0.0:
        return minimum_chunks
    return max(minimum_chunks, int(math.ceil(distance_m / max_step_m)))


def _rotate_vector_xyzw(vector, quaternion):
    vector = np.asarray(vector, dtype=np.float64)
    quaternion = np.asarray(quaternion, dtype=np.float64)
    xyz = quaternion[:3]
    w = float(quaternion[3])
    return vector + 2.0 * np.cross(xyz, np.cross(xyz, vector) + w * vector)


def _shape_indices_below_paths(labels, prim_paths):
    """Return shape indices whose USD labels are at or below exact prim paths.

    Newton shape labels are USD prim paths. Matching on path boundaries keeps
    this generic for arbitrary collider names while preventing a tip such as
    ``/Robot/finger`` from selecting ``/Robot/finger_aux``.
    """
    normalized_paths = tuple(str(path).replace("\\", "/").rstrip("/") for path in prim_paths if path)
    return {
        index
        for index, label in enumerate(labels)
        if any(
            (normalized_label := str(label).replace("\\", "/").rstrip("/")) == path
            or normalized_label.startswith(path + "/")
            for path in normalized_paths
        )
    }


def _newton_shape_world_bounds(prim_paths):
    """Return live Newton world AABBs for shapes below USD prim paths.

    Newton's tensor state is authoritative after the scene's first cook;
    Fabric/USD transforms may remain at their authored values. Bounds are
    reconstructed from each shape-local collision AABB, its body-local shape
    transform, and the live body transform.
    """
    try:
        from isaacsim.physics.newton import acquire_stage

        newton_stage = acquire_stage()
        model = getattr(newton_stage, "model", None)
        state = getattr(newton_stage, "state_0", None)
        if model is None or state is None:
            return []
        labels = list(getattr(model, "shape_label", ()) or ())
        shape_bodies = model.shape_body.numpy()
        shape_transforms = model.shape_transform.numpy()
        lowers = model.shape_collision_aabb_lower.numpy()
        uppers = model.shape_collision_aabb_upper.numpy()
        body_transforms = state.body_q.numpy()
    except Exception:
        return []

    selected_indices = _shape_indices_below_paths(labels, prim_paths)
    result = []
    for shape_index, label in enumerate(labels):
        if shape_index not in selected_indices:
            continue
        body_index = int(shape_bodies[shape_index])
        if body_index < 0 or body_index >= len(body_transforms):
            continue
        shape_transform = shape_transforms[shape_index]
        body_transform = body_transforms[body_index]
        corners = []
        for x in (lowers[shape_index][0], uppers[shape_index][0]):
            for y in (lowers[shape_index][1], uppers[shape_index][1]):
                for z in (lowers[shape_index][2], uppers[shape_index][2]):
                    point_body = shape_transform[:3] + _rotate_vector_xyzw((x, y, z), shape_transform[3:7])
                    point_world = body_transform[:3] + _rotate_vector_xyzw(point_body, body_transform[3:7])
                    corners.append(point_world)
        corners = np.asarray(corners, dtype=np.float64)
        result.append((corners.min(axis=0), corners.max(axis=0)))
    return result


def _read_object_position(stage, prim_path):
    from pxr import UsdGeom

    cache = UsdGeom.XformCache()
    return np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(prim_path))).reshape(4, 4)[3, :3]


def _read_object_xy(stage, prim_path):
    return _read_object_position(stage, prim_path)[:2]


def _read_object_z(stage, prim_path):
    return float(_read_object_position(stage, prim_path)[2])


def _read_carrier_z(stage, carrier):
    """Return the gripper's current world-frame Z.

    Reads from the articulation API (the new carrier IS the articulation
    root, see gripper_carrier.py) rather than from a separate Xform
    prim -- this gives the actual PhysX-side pose, not a USD-authored
    value that may lag simulation state.
    """
    from simready_benchmark_kit_suite.articulation_phases.gripper_carrier import (
        carrier_world_position,
    )

    return float(carrier_world_position(carrier)[2])

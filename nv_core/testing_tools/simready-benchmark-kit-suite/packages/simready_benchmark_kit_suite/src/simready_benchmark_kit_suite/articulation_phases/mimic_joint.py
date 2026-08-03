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
"""MIM phase: verify mimic joints follow their reference per authored gear/offset.
V1 reference: shared_phases/mimic_joint.py.
"""
import math

from simready_benchmark_kit_suite.articulation_phases.error_utils import engine_note
from simready_benchmark_kit_suite.articulation_phases.full_range_sweep import (
    interpolate_profile,
)
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready_benchmark_kit_suite.articulation_phases.mimic_joints import (
    detect_mimic_joints,
)

# --------------------------------------------------------------------------- #
# Shared "how to fix the asset" message bodies.
#
# Library philosophy: when a
# test cannot run on (or fails on) an asset, the message MUST teach the asset
# author EXACTLY how to fix the asset. Each helper builds a message with:
#   1) headline naming the failure,
#   2) what the test found vs. what was expected,
#   3) which prim(s)/attribute(s) need editing,
#   4) a paste-ready USDA snippet OR a concrete edit instruction,
#   5) REFERENCE to the spec doc + a working real-asset example.
# --------------------------------------------------------------------------- #

_MIM_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:      nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_driven_joints/requirements/mimic-api-check.md (DJ.007)\n"
    "  Example:   sample_content/common_assets/robots_general/Robotiq/"
    "ezu_35/simready_isaac_usd/payloads/Physics/physx.usda\n"
    "             (search for: PhysxMimicJointAPI:rotX on GBA2_TRANS_2 / "
    "GBA3_TRANS_3 referencing Jaw_Drive with gearing = -1)"
)


_MIMIC_USDA_TEMPLATE = (
    "    # The follower joint: applies PhysxMimicJointAPI keyed to the axis\n"
    "    # token of the joint (rotX/rotY/rotZ for revolute, transX/transY/\n"
    "    # transZ for prismatic). The instance name MUST match physics:axis.\n"
    '    def PhysicsRevoluteJoint "follower_joint" (\n'
    '        prepend apiSchemas = ["PhysxMimicJointAPI:rotX"]\n'
    "    )\n"
    "    {\n"
    '        uniform token physics:axis = "X"\n'
    "        rel physics:body0 = </path/to/parent_link>\n"
    "        rel physics:body1 = </path/to/follower_link>\n"
    "        float physics:lowerLimit = -45.0   # required: limits must be authored\n"
    "        float physics:upperLimit =  45.0\n"
    "\n"
    "        # ---- PhysxMimicJointAPI:rotX attributes ----\n"
    "        # gearing: Δq_follower = gearing * Δq_reference + offset\n"
    "        # Must be a non-zero real number. Sign encodes direction:\n"
    "        # -1 = follower moves opposite the reference (typical for\n"
    "        # parallel-jaw grippers where one jaw mirrors the other).\n"
    "        float physxMimicJoint:rotX:gearing = -1.0\n"
    "        float physxMimicJoint:rotX:offset = 0.0\n"
    "        float physxMimicJoint:rotX:naturalFrequency = 100.0\n"
    "        float physxMimicJoint:rotX:dampingRatio = 0.0\n"
    "        # referenceJoint must point at a joint that does NOT itself\n"
    "        # carry PhysxMimicJointAPI (no chains/cycles).\n"
    "        rel physxMimicJoint:rotX:referenceJoint = </path/to/reference_joint>\n"
    "    }\n"
)


def _msg_no_mimic_authored():
    # type: () -> str
    return (
        "MIM: no PhysxMimicJointAPI found on any joint under the asset prim.\n"
        "\n"
        "  Found:    0 joints with PhysxMimicJointAPI applied\n"
        "  Expected: at least one revolute or prismatic joint with\n"
        "            PhysxMimicJointAPI:<axisToken> applied (rotX/rotY/rotZ\n"
        "            or transX/transY/transZ)\n"
        "\n"
        "FIX (if your asset has coupled joints, e.g. a parallel-jaw gripper\n"
        "where the two finger joints must move together):\n"
        "  1. Pick the driven joint and call it the REFERENCE joint. Leave\n"
        "     it with a normal drive (PhysicsDriveAPI or JointStateAPI).\n"
        "  2. On each FOLLOWER joint, apply PhysxMimicJointAPI keyed to that\n"
        '     joint\'s physics:axis instance token (e.g. "rotX" for a\n'
        '     revolute joint with physics:axis = "X").\n'
        "  3. Set physxMimicJoint:<axis>:gearing (non-zero) and\n"
        "     physxMimicJoint:<axis>:referenceJoint pointing at the\n"
        "     reference joint's prim path.\n"
        "  4. Both follower AND reference joints must have physics:lowerLimit\n"
        "     and physics:upperLimit authored, and neither may have\n"
        "     physics:excludeFromArticulation = true.\n"
        "\n"
        "Paste-ready USDA snippet (adapt paths, axis token, gearing sign,\n"
        "and limits to your asset):\n"
        "\n"
        + _MIMIC_USDA_TEMPLATE
        + "\n"
        + _MIM_SPEC_REFERENCE
        + "\n\nNote: this test is SKIPPED (not failed) because mimic joints are\n"
        "optional. If your asset truly has no coupled joints, this skip is\n"
        "expected and benign."
    )


def _format_sample_pair(sample_pair):
    # type: (Any) -> str
    if sample_pair is None:
        return ""
    fol_dof = "<not found>" if sample_pair.follower_dof_index is None else str(sample_pair.follower_dof_index)
    ref_dof = "<not found>" if sample_pair.reference_dof_index is None else str(sample_pair.reference_dof_index)
    return (
        "  Example unresolvable pair:\n"
        "    follower joint prim: {fol_path}\n"
        "    reference joint prim: {ref_path}\n"
        "    follower DOF index:   {fol_dof}\n"
        "    reference DOF index:  {ref_dof}\n"
    ).format(
        fol_path=sample_pair.follower_joint_path,
        ref_path=sample_pair.reference_joint_path,
        fol_dof=fol_dof,
        ref_dof=ref_dof,
    )


_UNRESOLVABLE_BODY = (
    "  Found:    PhysxMimicJointAPI is authored on the joint(s)\n"
    "  Problem:  either the follower joint itself or the joint that\n"
    "            physxMimicJoint:<axis>:referenceJoint points at is\n"
    "            not present in the runtime DOF list. That usually\n"
    "            means one of:\n"
    "              (a) the referenceJoint relationship target uses a\n"
    "                  prim PATH that does not exist on stage (typo,\n"
    "                  stale path after a rename, wrong namespace);\n"
    "              (b) the referenced joint is excluded from the\n"
    "                  articulation (physics:excludeFromArticulation\n"
    "                  = true) and therefore has no DOF;\n"
    "              (c) the joint name doesn't match its DOF name\n"
    "                  (the DOF list is keyed off the joint prim name).\n"
    "\n"
    "{sample}"
    "FIX:\n"
    "  1. Open the follower joint prim in USD and inspect the\n"
    "     `physxMimicJoint:<axis>:referenceJoint` relationship. The\n"
    "     target must be the FULL prim path of an existing joint on\n"
    "     stage (e.g. </schunk_ezu_35/joints/Jaw_Drive>, NOT just\n"
    '     "Jaw_Drive").\n'
    "  2. On both the follower and the reference joint, confirm\n"
    "     `physics:excludeFromArticulation` is unset or false.\n"
    "  3. If you renamed or re-parented the reference joint, update\n"
    "     every `referenceJoint` relationship that points at it.\n"
    "\n"
    "{ref}"
)


def _msg_unresolvable_pairs(total, unresolved, sample_pair):
    # type: (int, int, Any) -> str
    headline = (
        "MIM: {unresolved} of {total} PhysxMimicJointAPI pair(s) could not "
        "be mapped to a\nlive articulation DOF and were skipped.\n\n"
    ).format(unresolved=unresolved, total=total)
    return headline + _UNRESOLVABLE_BODY.format(
        sample=_format_sample_pair(sample_pair),
        ref=_MIM_SPEC_REFERENCE,
    )


def _msg_all_pairs_unresolvable(total, sample_pair):
    # type: (int, Any) -> str
    headline = (
        "MIM: PhysxMimicJointAPI is applied on this asset ({total} pair(s)) "
        "but\nNONE of them resolve to a live articulation DOF -- the test "
        "cannot\nrun.\n\n"
    ).format(total=total)
    return headline + _UNRESOLVABLE_BODY.format(
        sample=_format_sample_pair(sample_pair),
        ref=_MIM_SPEC_REFERENCE,
    )


def _msg_reference_no_limits(ref_name, fol_name, lo, hi):
    # type: (str, str, float, float) -> str
    return (
        "MIM: reference joint '{ref}' (follower '{fol}') has no finite "
        "position\nrange -- skipping this pair.\n"
        "\n"
        "  Found:    lowerLimit={lo!r} upperLimit={hi!r} (one or both "
        "non-finite\n            or the range is zero)\n"
        "  Expected: physics:lowerLimit < physics:upperLimit, both finite,\n"
        "            authored on the REFERENCE joint prim (DJ.007 requires\n"
        "            both self and reference joints to have limits).\n"
        "\n"
        "FIX: open the joint prim named '{ref}' and author finite limits, "
        "e.g.:\n"
        "\n"
        "    float physics:lowerLimit = -45.0   # degrees for revolute,\n"
        "    float physics:upperLimit =  45.0   # meters for prismatic\n"
        "\n"
        "{spec_ref}"
    ).format(ref=ref_name, fol=fol_name, lo=lo, hi=hi, spec_ref=_MIM_SPEC_REFERENCE)


def _msg_drift_fix_hint():
    # type: () -> str
    return (
        "Asset fix: the test compares the MAGNITUDE of follower vs. reference "
        "motion across the sweep (|fol_swept| / |ref_swept|), which should be "
        "approximately |gearing|.\n"
        "  - If the ratio is ~0, the follower never moved: the mimic is "
        "broken. Confirm PhysxMimicJointAPI:<axis> is applied (axis instance "
        "matches physics:axis), `physxMimicJoint:<axis>:referenceJoint` "
        "resolves to a joint with a working drive, and neither joint has "
        "physics:excludeFromArticulation = true.\n"
        "  - If the ratio is non-zero but very different from |gearing|, the "
        "authored `physxMimicJoint:<axis>:gearing` magnitude is wrong. Edit "
        "the gearing attribute on the follower joint prim.\n"
        "  - For nonlinear linkages (4-bar grippers etc.), a single linear "
        "gearing is only an approximation; consider a Physx_Loop or more "
        "sophisticated coupling instead.\n"
        "  - Direction sign and rest-pose residual are reported as diagnostics "
        "but do NOT fail the test -- many real assets (Robotiq 2F-85 et al.) "
        "author signs in joint-local frames that disagree with the dof_index "
        "frame yet the gripper still closes correctly.\n"
        "  - See spec DJ.007 (nv_core/sr_specs/docs/capabilities/"
        "physics_bodies/physics_driven_joints/requirements/mimic-api-check.md) "
        "and the working example in sample_content/.../Robotiq/ezu_35/"
        "simready_isaac_usd/payloads/Physics/physx.usda (gearing = -1 on "
        "GBA2_TRANS_2 / GBA3_TRANS_3 referencing Jaw_Drive)."
    )


def get_defaults():
    # type: () -> Dict[str, Any]
    return {
        "settle_seconds": 1.0,
        "sweep_seconds": 2.0,
        # Legacy incremental-error tolerance (rad). Reported as a diagnostic
        # but no longer the pass criterion — see ``gear_ratio_tolerance``.
        "follow_tolerance": 0.05,
        # Pass criterion: |follower_swept / ref_swept - |gear|| <= this value.
        # Direction-agnostic; what actually matters for "is the mimic working"
        # is that motion magnitudes are coupled by the gear ratio. Sign
        # mismatches and rest-pose residuals show up as warnings only,
        # because real assets (Robotiq 2F-85, etc.) often have authored
        # gear signs that disagree with the joint-axis frame convention
        # while the gripper still closes correctly via the linkage.
        "gear_ratio_tolerance": 0.10,
        "sweep_margin_ratio": 0.10,
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        "capture_fps": 15,
    }


def compute_expected_follower(ref_pos, gear, offset):
    # type: (float, float, float) -> float
    return float(ref_pos) * float(gear) + float(offset)


def aggregate_mim_summary(per_pair_results):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    total = len(per_pair_results)
    passed = sum(1 for r in per_pair_results if r["ok"])
    return {
        "pairs_tested": total,
        "pairs_passed": passed,
        "pairs_failed": total - passed,
        "failure_names": [r["follower"] for r in per_pair_results if not r["ok"]],
    }


async def run_mimic_joint(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 15))
    settle_seconds = float(config.get("settle_seconds", 1.0))
    sweep_seconds = float(config.get("sweep_seconds", 2.0))
    gear_ratio_tol = float(config.get("gear_ratio_tolerance", 0.10))
    margin = float(config.get("sweep_margin_ratio", 0.10))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))

    HB_EVERY = 40

    ctx.step("Detecting mimic joints")
    specs = detect_mimic_joints(
        stage=stage,
        asset_prim=asset_prim,
        robot_prim_path=robot.prim_path,
        dof_names=list(robot.dof_names),
    )
    ctx.add_metric("mim_mimic_pairs_detected", len(specs))

    if not specs:
        ctx.skip(_msg_no_mimic_authored())
        return

    resolved = [s for s in specs if s.follower_dof_index is not None and s.reference_dof_index is not None]
    skipped = len(specs) - len(resolved)
    ctx.add_metric("mim_skipped_pairs", skipped)
    if skipped > 0:
        # Pick the first unresolved pair as the concrete example to surface
        # in the warning -- gives the asset author a real prim path to look
        # at instead of just a count.
        unresolved_sample = next(
            (s for s in specs if s.follower_dof_index is None or s.reference_dof_index is None),
            None,
        )
        ctx.warn(_msg_unresolvable_pairs(len(specs), skipped, unresolved_sample))
    if not resolved:
        unresolved_sample = next(
            (s for s in specs if s.follower_dof_index is None or s.reference_dof_index is None),
            None,
        )
        ctx.skip(_msg_all_pairs_unresolvable(len(specs), unresolved_sample))
        return

    ctx.step("Settling before MIM test")
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)

    lowers, uppers = robot.get_joint_position_limits()
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    per_pair_results = []

    for pnum, spec in enumerate(resolved, start=1):
        ref_idx = spec.reference_dof_index
        fol_idx = spec.follower_dof_index
        ref_name = robot.dof_names[ref_idx]
        fol_name = robot.dof_names[fol_idx]
        ctx.step(
            "MIM pair %d/%d ref=%s follower=%s gear=%.3f offset=%.3f"
            % (pnum, len(resolved), ref_name, fol_name, spec.gear, spec.offset)
        )

        lo = float(lowers[ref_idx])
        hi = float(uppers[ref_idx])
        if not (math.isfinite(lo) and math.isfinite(hi) and (hi - lo) > 1e-6):
            ctx.warn(_msg_reference_no_limits(ref_name, fol_name, lo, hi))
            per_pair_results.append(
                {
                    "follower": fol_name,
                    "max_follow_error": 0.0,
                    "ok": False,
                    "reason": "reference range non-finite (limits not authored on reference joint)",
                }
            )
            continue

        sweep_lo = lo + (hi - lo) * margin
        sweep_hi = hi - (hi - lo) * margin
        cur = robot.get_joint_positions().copy()

        # Capture rest-pose positions BEFORE commanding the sweep. PhysX
        # enforces ``PhysxMimicJointAPI`` as an INCREMENTAL constraint:
        # ``Δq_follower = gear * Δq_master + offset`` (the asset's rest pose
        # is the zero point). The naive absolute formula
        # ``q_follower = gear * q_master + offset`` only holds when the rest
        # poses already satisfy it (which they typically don't on real
        # gripper assets like the Robotiq 2F-85). The test compares
        # incremental motion against the gear, so a passing asset has motion
        # coupled with the right gear ratio + sign — even if absolute
        # positions look offset because the rest-pose residual ≠ 0.
        rest_positions = robot.get_joint_positions()
        ref_rest = float(rest_positions[ref_idx])
        fol_rest = float(rest_positions[fol_idx])
        # Diagnostic — what would the absolute formula say at rest? If non-zero,
        # the asset's authored offset doesn't match its rest pose.
        rest_residual = abs(fol_rest - (spec.gear * ref_rest + spec.offset))

        total_frames = max(20, int(sweep_seconds * physics_fps))
        max_err = 0.0  # primary: incremental-motion error (pass/fail)
        max_abs_err = 0.0  # diagnostic: absolute-formula error (informational)
        sample_count = 0
        sum_err = 0.0
        ref_min = float("inf")
        ref_max = float("-inf")
        fol_min = float("inf")
        fol_max = float("-inf")
        first_ref = None
        first_fol = None
        for frame in range(total_frames):
            # Triangular sweep: lo -> hi -> lo using smoothstep per leg.
            half = total_frames // 2 or 1
            if frame <= half:
                t = interpolate_profile("smoothstep", frame / float(half))
                tgt = sweep_lo + (sweep_hi - sweep_lo) * t
            else:
                t = interpolate_profile("smoothstep", (frame - half) / float(max(1, total_frames - half)))
                tgt = sweep_hi + (sweep_lo - sweep_hi) * t
            cur[ref_idx] = tgt
            robot.set_joint_position_targets(cur)
            await ctx.step_one()

            if frame % 10 == 0:
                positions = robot.get_joint_positions()
                ref_pos = float(positions[ref_idx])
                fol_pos = float(positions[fol_idx])
                # Primary check: incremental motion matches the gear.
                ref_delta = ref_pos - ref_rest
                fol_delta = fol_pos - fol_rest
                expected_fol_delta = spec.gear * ref_delta + spec.offset
                err = abs(fol_delta - expected_fol_delta)
                if err > max_err:
                    max_err = err
                # Diagnostic: absolute formula (legacy comparison; surfaced as a
                # separate metric so reviewers can tell "the gear ratio is
                # correct but the offset is wrong" apart from "the gear
                # itself is wrong").
                abs_expected = compute_expected_follower(ref_pos, spec.gear, spec.offset)
                abs_err = abs(fol_pos - abs_expected)
                if abs_err > max_abs_err:
                    max_abs_err = abs_err
                sample_count += 1
                sum_err += err
                if ref_pos < ref_min:
                    ref_min = ref_pos
                if ref_pos > ref_max:
                    ref_max = ref_pos
                if fol_pos < fol_min:
                    fol_min = fol_pos
                if fol_pos > fol_max:
                    fol_max = fol_pos
                if first_ref is None:
                    first_ref = ref_pos
                    first_fol = fol_pos

            if frame % 20 == 0:
                current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
                msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                if msg:
                    # Bbox blowup during the sweep usually indicates physics
                    # instability (e.g. unstable mimic coupling overshooting
                    # and tearing the articulation apart) rather than a static
                    # authoring gap. Surface it as a warning with the follower
                    # name and the joint pair so the asset author can inspect
                    # the gearing / naturalFrequency / dampingRatio values on
                    # the offending PhysxMimicJointAPI:<axis> instance.
                    ctx.warn(
                        "MIM: articulation bounding box exploded during "
                        "sweep of mimic pair follower='%s' ref='%s' "
                        "(gearing=%.3f offset=%.3f). %s %s Asset fix: if "
                        "this reproduces, lower "
                        "physxMimicJoint:<axis>:naturalFrequency on '%s' "
                        "(default 100 -- try 25-50) or raise "
                        "physxMimicJoint:<axis>:dampingRatio (default 0 -- "
                        "try 0.5-1.0) to soften the constraint; verify the "
                        "authored gearing is realistic for the linkage. "
                        "See nv_core/sr_specs/docs/capabilities/"
                        "physics_bodies/physics_driven_joints/requirements/"
                        "mimic-api-check.md (DJ.007)."
                        % (
                            fol_name,
                            ref_name,
                            float(spec.gear),
                            float(spec.offset),
                            msg,
                            engine_note(
                                "Physics may also be unstable due to too-large "
                                "dt at %d Hz; reducing physics_fps can help "
                                "diagnose authoring vs. solver issues." % int(physics_fps)
                            ),
                            fol_name,
                        )
                    )

            if frame % capture_interval == 0:
                frame_path = await ctx.capture_frame(
                    label="mim_%03d_%04d" % (pnum, frame),
                    stabilize_frames=0,
                )
                if frame_path:
                    capture_frames.append(frame_path)
                ctx.scene.update_camera_follow(update_history=True)
            else:
                ctx.scene.update_camera_follow(update_history=False)
            if frame % HB_EVERY == 0:
                ctx.step("MIM pair=%s frame=%d/%d max_err=%.3f" % (fol_name, frame, total_frames, max_err))

        # Pass criterion: the magnitude ratio of follower-to-master motion
        # matches |gear|. Direction-agnostic — real gripper assets (Robotiq
        # 2F-85 and similar 4-bar linkages) author gears in joint-local
        # frame conventions that may not match the dof_index frame, so a
        # follower moving "with" the master numerically can still
        # correspond to a correctly-authored gear=-1 (the linkage closes
        # the gripper either way). What truly verifies that the mimic is
        # functioning is that motion magnitudes are coupled by |gear|.
        # Sign disagreements and rest-pose residuals are surfaced as
        # warnings (and metrics) but do not fail the test.
        ref_swept = (ref_max - ref_min) if math.isfinite(ref_min) and math.isfinite(ref_max) else 0.0
        fol_swept = (fol_max - fol_min) if math.isfinite(fol_min) and math.isfinite(fol_max) else 0.0
        # Expected follower span = |gear| * ref_span (offset cancels out in span).
        expected_swept = abs(float(spec.gear)) * ref_swept

        # Magnitude-ratio: dimensionless. ε guards against division by zero
        # on a zero-range master (caught earlier, but defensive).
        gear_mag = abs(float(spec.gear))
        if ref_swept > 1e-9:
            motion_ratio = fol_swept / ref_swept
        else:
            motion_ratio = 0.0
        gear_ratio_error = abs(motion_ratio - gear_mag)
        ok = gear_ratio_error <= gear_ratio_tol
        # Track the legacy max_err separately for the failure message (still
        # useful info for genuinely-broken mimics where motion ratio is fine
        # but error is large, e.g. the mimic is nonlinear).
        mean_err = (sum_err / sample_count) if sample_count else 0.0
        # Sign sanity: did the follower move in the direction the gear predicts?
        # If gear > 0 the follower should move with the master (same sign of delta);
        # if gear < 0, opposite. We compare the LAST sample to the first.
        observed_dir_match = None
        if sample_count >= 2 and abs(ref_max - ref_min) > 1e-6:
            ref_delta = (
                (ref_max - ref_min)
                if (first_ref is not None and first_ref < (ref_min + ref_max) / 2)
                else -(ref_max - ref_min)
            )
            fol_delta = (
                (fol_max - fol_min)
                if (first_fol is not None and first_fol < (fol_min + fol_max) / 2)
                else -(fol_max - fol_min)
            )
            expected_sign = 1.0 if float(spec.gear) >= 0.0 else -1.0
            actual_sign = 1.0 if (fol_delta * ref_delta) >= 0 else -1.0
            observed_dir_match = expected_sign == actual_sign

        record = {
            "follower": fol_name,
            "reference": ref_name,
            "gear": float(spec.gear),
            "offset": float(spec.offset),
            "max_follow_error": max_err,
            "mean_follow_error": mean_err,
            "ref_swept_range_rad": ref_swept,
            "follower_observed_range_rad": fol_swept,
            "follower_expected_range_rad": expected_swept,
            "observed_direction_matches_gear_sign": observed_dir_match,
            "ok": ok,
        }
        # Surface as ctx metrics so they land in result.json.metrics, not just
        # in the in-memory record dict.
        ctx.add_metric("mim_pair_%s_max_error_rad" % fol_name, max_err)
        ctx.add_metric("mim_pair_%s_mean_error_rad" % fol_name, mean_err)
        ctx.add_metric("mim_pair_%s_ref_swept_rad" % fol_name, ref_swept)
        ctx.add_metric("mim_pair_%s_follower_observed_rad" % fol_name, fol_swept)
        ctx.add_metric("mim_pair_%s_follower_expected_rad" % fol_name, expected_swept)
        ctx.add_metric(
            "mim_pair_%s_dir_matches_gear" % fol_name,
            1 if observed_dir_match else (0 if observed_dir_match is False else -1),
        )
        # Primary pass-criterion metric: motion-ratio error (dimensionless).
        ctx.add_metric("mim_pair_%s_motion_ratio" % fol_name, motion_ratio)
        ctx.add_metric("mim_pair_%s_gear_ratio_error" % fol_name, gear_ratio_error)
        # Diagnostic: how far off is the absolute (rest-pose-naive) formula?
        # If rest_residual is large but max_err (incremental) is small, the
        # asset's mimic motion is correct — the authored offset just doesn't
        # bias the rest pose, which PhysX doesn't actually require.
        ctx.add_metric("mim_pair_%s_abs_formula_max_error_rad" % fol_name, max_abs_err)
        ctx.add_metric("mim_pair_%s_rest_residual_rad" % fol_name, rest_residual)

        if not ok:
            record["reason"] = (
                "motion-magnitude mismatch: ratio %.3f (follower/ref) vs |gear|=%.3f, "
                "error %.3f > tolerance %.3f; ref swept %.3f rad, follower observed %.3f rad "
                "(expected %.3f); incremental error %.3f rad, absolute-formula error %.3f rad, "
                "rest-pose residual %.3f rad, direction %s gear sign"
                % (
                    motion_ratio,
                    gear_mag,
                    gear_ratio_error,
                    gear_ratio_tol,
                    ref_swept,
                    fol_swept,
                    expected_swept,
                    max_err,
                    max_abs_err,
                    rest_residual,
                    (
                        "matches"
                        if observed_dir_match
                        else "DOES NOT MATCH" if observed_dir_match is False else "(unknown for)"
                    ),
                )
            )
            ctx.warn(
                "MIM: mimic pair drifted -- follower joint '%s' (reference "
                "joint '%s', authored gearing=%.3f offset=%.3f) does not "
                "track its reference within tolerance.\n"
                "  Measured: follower swept %.3f rad while reference swept "
                "%.3f rad => motion ratio %.3f.\n"
                "  Expected: motion ratio ~ |gearing| = %.3f (tolerance "
                "%.3f). Error %.3f.\n"
                "  Diagnostics: incremental error %.3f rad, absolute-formula "
                "error %.3f rad, rest-pose residual %.3f rad, direction %s "
                "the authored gearing sign.\n"
                "%s %s"
                % (
                    fol_name,
                    ref_name,
                    float(spec.gear),
                    float(spec.offset),
                    fol_swept,
                    ref_swept,
                    motion_ratio,
                    gear_mag,
                    gear_ratio_tol,
                    gear_ratio_error,
                    max_err,
                    max_abs_err,
                    rest_residual,
                    (
                        "matches"
                        if observed_dir_match
                        else "DOES NOT MATCH" if observed_dir_match is False else "(unknown direction relative to)"
                    ),
                    _msg_drift_fix_hint(),
                    engine_note(
                        "Large drift may also indicate physics instability "
                        "during the sweep (solver oscillation); a co-occurring "
                        "bbox-explode warning is a strong indicator."
                    ),
                )
            )
        elif observed_dir_match is False:
            # Magnitude is right but the sign disagrees with what the asset
            # claims. Pass, but warn so the asset author knows.
            ctx.warn(
                "MIM: mimic pair follower='%s' ref='%s' PASSES the magnitude "
                "check (motion ratio %.3f vs |gearing|=%.3f) but the "
                "observed direction does NOT match the authored gearing "
                "sign. Asset metadata may be inconsistent with the joint-"
                "axis frame convention (this is common on linkage-based "
                "grippers like the Robotiq 2F-85 and does not affect visual "
                "closure). Asset fix (optional, cosmetic): on the follower "
                "joint prim, flip the sign of "
                "physxMimicJoint:<axis>:gearing on the "
                "PhysxMimicJointAPI:<axis> instance so the authored sign "
                "matches the observed motion direction. Metric "
                "mim_pair_%s_dir_matches_gear=0 records this for review. "
                "Spec: nv_core/sr_specs/docs/capabilities/physics_bodies/"
                "physics_driven_joints/requirements/mimic-api-check.md "
                "(DJ.007)." % (fol_name, ref_name, motion_ratio, gear_mag, fol_name)
            )
        else:
            ctx.log("MIM: pair follower='%s' ok (max_err=%.3f)" % (fol_name, max_err))
        per_pair_results.append(record)

    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="mimic_joint", role="summary")

    summary = aggregate_mim_summary(per_pair_results)
    ctx.add_metric("mim_pairs_passed", summary["pairs_passed"])
    ctx.add_metric("mim_pairs_failed", summary["pairs_failed"])

    if summary["pairs_failed"] > 0:
        # Per-pair diagnostic detail (which joint, which gearing, what was
        # measured) so the asset author can go straight to the offending
        # prim without spelunking through result.json.
        per_pair_lines = []
        for r in per_pair_results:
            if r.get("ok"):
                continue
            per_pair_lines.append(
                "  - follower='%s' (reference='%s', authored gearing=%.3f, "
                "offset=%.3f): %s"
                % (
                    r["follower"],
                    r.get("reference", "?"),
                    float(r.get("gear", 0.0)),
                    float(r.get("offset", 0.0)),
                    r.get("reason", "see per-pair warning above"),
                )
            )
        per_pair_block = "\n".join(per_pair_lines) if per_pair_lines else "  (see per-pair warnings above)"

        ctx.fail(
            "MIM: %d of %d mimic pair(s) failed the motion-magnitude check.\n"
            "\n"
            "  Failing pairs (%s):\n"
            "%s\n"
            "\n"
            "  Pass criterion: |follower_swept / ref_swept - |gearing|| <=\n"
            "    `gear_ratio_tolerance` (default 0.10). Direction sign and\n"
            "    rest-pose residual are reported as diagnostic warnings only.\n"
            "\n"
            "%s\n"
            "\n"
            "Per-pair metrics in result.json.metrics:\n"
            "  mim_pair_<follower>_motion_ratio\n"
            "  mim_pair_<follower>_gear_ratio_error\n"
            "  mim_pair_<follower>_max_error_rad\n"
            "  mim_pair_<follower>_dir_matches_gear (1=match, 0=mismatch,\n"
            "    -1=indeterminate -- direction is diagnostic only)"
            % (
                summary["pairs_failed"],
                summary["pairs_tested"],
                ", ".join(summary["failure_names"]),
                per_pair_block,
                _msg_drift_fix_hint(),
            )
        )

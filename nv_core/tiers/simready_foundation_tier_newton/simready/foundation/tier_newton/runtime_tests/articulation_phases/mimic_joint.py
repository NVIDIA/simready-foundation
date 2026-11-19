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

"""Newton MIM: evaluate sampled follower/reference motion-magnitude ratios.
V1 reference: shared_phases/mimic_joint.py.

Backend-normalized direction and rest-pose residuals are diagnostics only;
the verdict does not certify the absolute gear/offset equation or its units.
"""

import math

from simready.foundation.tier_newton.runtime_tests.articulation_phases.error_utils import engine_note
from simready.foundation.tier_newton.runtime_tests._assessment import (
    _has_complete_asset_composition,
    not_applicable,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases._independent_dofs import (
    excluded_dof_indices,
    owned_articulation,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.config_validation import (
    validate_phase_config,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.full_range_sweep import (
    interpolate_profile,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_targets import (
    bounded_joint_range,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.mimic_joints import (
    detect_mimic_joints,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_history import (
    make_joint_observer,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
    settle_nominal,
)

# --------------------------------------------------------------------------- #
# Newton-owned diagnostic guidance. A failed observation does not establish
# whether the cause is the composed asset, importer, solver or test setup.
# Preserve the evidence and verify that cause before recommending an edit.
# --------------------------------------------------------------------------- #

_MIM_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec: nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/rules_and_reqs/physics_bodies/"
    "physics_driven_joints/requirements/newton-mimic-api.md (NEWTON.DJ.003).\n"
    "Inspect the composed runtime variant, not an unrelated solver payload."
)


def _msg_no_mimic_authored(backend="physx"):
    # type: () -> str
    return (
        "MIM: no active authored mimic follower was identified under the verified loaded asset.\n\n"
        "This optional response test is skipped, not failed. Disabled joints or "
        "disabled constraint opinions may retain authored API tokens; this is "
        "not a count of all raw APIs or proof that coupling is absent. If active coupling "
        "is intended, inspect the composed NewtonMimicAPI relationship "
        "newton:mimicJoint, enable state and coefficients, or the compatibility "
        "binding actually supported by the installed importer. Confirm the selected "
        "runtime variant and importer/solver support before attributing an asset defect. "
        "No response verdict was evaluated; do not add a mimic API solely to "
        "satisfy this skip.\n\n" + _MIM_SPEC_REFERENCE
    )


def _format_sample_pair(sample_pair):
    # type: (Any) -> str
    if sample_pair is None:
        return ""
    fol_dof = "<not found>" if sample_pair.follower_dof_index is None else str(sample_pair.follower_dof_index)
    ref_dof = "<not found>" if sample_pair.reference_dof_index is None else str(sample_pair.reference_dof_index)
    return (
        "  Example unresolvable pair:\n"
        f"    follower joint prim: {sample_pair.follower_joint_path}\n"
        f"    reference joint prim: {sample_pair.reference_joint_path}\n"
        f"    follower DOF index:   {fol_dof}\n"
        f"    reference DOF index:  {ref_dof}\n"
    )


_UNRESOLVABLE_BODY = (
    "  Found: mimic coupling metadata, but a follower or reference joint could "
    "not be mapped to a live articulation DOF.\n"
    "\n"
    "{sample}"
    "DIAGNOSE: inspect the composed NewtonMimicAPI newton:mimicJoint binding "
    "or the selected compatibility relationship, target prim paths, enable state, "
    "articulation membership and runtime DOF mapping. Check importer logs for "
    "collapsed, excluded or unsupported joints. No observation here establishes "
    "whether the cause is asset authoring, importer/solver support or test setup.\n"
    "\n"
    "{ref}"
)


def _msg_unresolvable_pairs(total, unresolved, sample_pair):
    # type: (int, int, Any) -> str
    headline = (
        f"MIM: {unresolved} of {total} detected mimic pair(s) could not "
        "be mapped to a\nlive articulation DOF and were skipped.\n\n"
    )
    return headline + _UNRESOLVABLE_BODY.format(
        sample=_format_sample_pair(sample_pair),
        ref=_MIM_SPEC_REFERENCE,
    )


def _msg_all_pairs_unresolvable(total, sample_pair):
    # type: (int, Any) -> str
    headline = (
        f"MIM: mimic coupling was detected on this asset ({total} pair(s)) "
        "but\nNONE of them resolve to a live articulation DOF -- the test "
        "cannot\nrun.\n\n"
    )
    return headline + _UNRESOLVABLE_BODY.format(
        sample=_format_sample_pair(sample_pair),
        ref=_MIM_SPEC_REFERENCE,
    )


def _msg_reference_no_limits(ref_name, fol_name, lo, hi):
    # type: (str, str, float, float) -> str
    return (
        f"MIM: reference joint '{ref_name}' (follower '{fol_name}') has no "
        "qualified finite runtime sweep interval; this pair cannot be exercised.\n"
        "\n"
        f"  Found:    lowerLimit={lo!r} upperLimit={hi!r} (one or both "
        "unavailable/unlimited or not wider than 1e-6 native units)\n"
        "  This procedure needs a finite runtime position range to construct its sweep. "
        "That test prerequisite is not itself a NEWTON.DJ.003 conformance rule.\n"
        "\n"
        "DIAGNOSE: compare the composed physics:lowerLimit/upperLimit with the "
        f"runtime values returned for '{ref_name}', including joint type, units and importer "
        "support. Authored USD limits are degrees for revolute joints and stage units "
        "for prismatic joints; runtime tensor units require their own qualified basis. "
        "Do not invent limits for an intentionally continuous joint merely to run this test.\n"
        "\n"
        f"{_MIM_SPEC_REFERENCE}"
    )


def _msg_drift_fix_hint():
    # type: () -> str
    return (
        "DIAGNOSE: the test compares the MAGNITUDE of follower vs. reference "
        "motion across the sweep (|fol_swept| / |ref_swept|), which should be "
        "approximately |gearing|.\n"
        "  - Inspect the composed NewtonMimicAPI binding, enable state, actual "
        "coefficients and DOF mapping, or the compatibility binding selected by the importer.\n"
        "  - Verify the installed importer/solver coupling support, controller response, "
        "joint-axis conventions and qualified runtime units. A zero response or ratio "
        "mismatch alone does not establish an asset defect or an incorrect coefficient.\n"
        "  - Direction sign and legacy formula/rest-pose residuals are diagnostics, "
        "not the verdict. Verify the backend coefficient convention before interpreting "
        "them; changing a coefficient sign changes physics and is not a cosmetic repair.\n"
        "Preserve the original evidence. Any justified asset repair or tuning is external "
        "to Evaluate; do not loosen the test tolerance merely to force a pass.\n\n" + _MIM_SPEC_REFERENCE
    )


def _msg_sweep_instability(follower, reference, gear, offset, bbox_message, physics_fps):
    """Describe the observed instability without selecting a repair or timestep."""
    return (
        "MIM: articulation bounding box exploded during sweep of mimic pair "
        "follower='%s' ref='%s' (gearing=%.3f offset=%.3f). %s %s "
        "Inspect the composed mimic binding, actual coefficients, joint units, "
        "importer/solver support and controller response before attributing a cause. "
        "Preserve the failing configuration for a controlled setup-versus-asset comparison."
        % (
            follower,
            reference,
            gear,
            offset,
            bbox_message,
            engine_note(
                "Configured physics_fps=%g Hz is nominal; dt=1/physics_fps, "
                "so lowering that rate increases the nominal step size. "
                "This observation does not identify a safe timestep or gain change." % physics_fps
            ),
        )
    )


def _msg_direction_mismatch(follower, reference, motion_ratio, gear_mag):
    """Keep legacy sign diagnostics separate from the magnitude verdict."""
    return (
        "MIM: mimic pair follower='%s' ref='%s' PASSES the magnitude check "
        "(motion ratio %.3f vs |gearing|=%.3f), but observed direction disagrees "
        "with the backend-normalized coefficient comparison. Inspect joint-axis conventions "
        "and the selected Newton importer coefficient conversion before interpreting "
        "this diagnostic. It is not proof of an asset defect; do not flip a coefficient "
        "sign to match this warning. That would change the physical coupling, not its appearance. "
        "Metric mim_pair_%s_dir_matches_gear=0 remains a diagnostic only.\n\n%s"
        % (follower, reference, motion_ratio, gear_mag, follower, _MIM_SPEC_REFERENCE)
    )


def get_defaults():
    # type: () -> dict[str, Any]
    return {
        "settle_seconds": 1.0,
        "sweep_seconds": 2.0,
        # Legacy incremental-error tolerance. Reported as a diagnostic
        # but no longer the pass criterion — see ``gear_ratio_tolerance``.
        "follow_tolerance": 0.05,
        # Pass criterion: |follower_swept / ref_swept - |gear|| <= this value.
        # Existing direction-agnostic verdict policy. Sign and rest-pose
        # residual diagnostics do not change it or certify physical correctness.
        "gear_ratio_tolerance": 0.10,
        "sweep_margin_ratio": 0.10,
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        "capture_fps": 15,
    }


def compute_expected_follower(ref_pos, gear, offset):
    # type: (float, float, float) -> float
    return float(ref_pos) * float(gear) + float(offset)


def _diagnostic_coefficients(spec):
    """Normalize only the evidence equation, retaining the raw authored spec.

    Native Newton uses follower = coef0 + coef1 * reference. PhysX uses
    follower + gearing * reference + offset = 0; Newton's compatibility
    importer makes the same sign conversion. Constant offsets cancel when
    subtracting measured rest positions. This does not change the ratio verdict.
    """
    if getattr(spec, "backend", "physx") == "newton":
        return float(spec.gear), float(spec.offset)
    return -float(spec.gear), -float(spec.offset)


def aggregate_mim_summary(per_pair_results):
    # type: (list[dict[str, Any]]) -> dict[str, Any]
    total = len(per_pair_results)
    passed = sum(1 for r in per_pair_results if r["ok"])
    return {
        "pairs_tested": total,
        "pairs_passed": passed,
        "pairs_failed": total - passed,
        "failure_names": [r["follower"] for r in per_pair_results if not r["ok"]],
    }


def _has_no_authored_active_mimic(stage, asset_prim, ctx):
    """Mapped-empty is not authored-empty when physical/native ownership is unresolved."""
    from simready.foundation.tier_newton.runtime_tests._assessment import _log_applicability_gap

    try:
        from pxr import Usd, UsdPhysics

        for prim in Usd.PrimRange(asset_prim, Usd.TraverseInstanceProxies(Usd.PrimIsActive)):
            raw = prim.GetMetadata("apiSchemas")
            schemas = set(prim.GetAppliedSchemas())
            if raw is not None:
                schemas.update(raw.ApplyOperations([]))
            newton = "NewtonMimicAPI" in schemas
            physx = any(name.startswith("PhysxMimicJointAPI:") for name in schemas)
            if not newton and not physx:
                continue
            if not prim.IsA(UsdPhysics.Joint):
                return _log_applicability_gap(ctx, "authored mimic sources have unqualified joint ownership")
            if UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is False:
                continue
            enabled = prim.GetAttribute("newton:mimicEnabled")
            if newton and enabled and enabled.HasAuthoredValue() and enabled.Get() is False:
                newton = False
            if newton or physx:
                return _log_applicability_gap(
                    ctx, "empty mapped candidates do not establish absence of authored active mimic sources"
                )
        return True
    except Exception:
        return _log_applicability_gap(ctx, "the raw authored mimic source inventory could not be queried")


async def run_mimic_joint(ctx, robot, scene_info, config):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

    validate_phase_config(config, "mimic_joint")
    nominal_settle_steps(config.get("settle_seconds", 1.0), config.get("physics_fps", 240.0))
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
        authored_followers = scene_info.get("mimic_follower_indices")
        if authored_followers is None and stage is not None and asset_prim is not None:
            from .mimic_joints import detect_mimic_follower_indices

            authored_followers = detect_mimic_follower_indices(stage, asset_prim, robot.prim_path, robot.dof_names)
        if authored_followers:
            raise RuntimeError(
                "MIM runtime error: authored mimic followers exist but no qualified "
                "response pair was resolved; schema SDK, axis, reference or runtime "
                "mapping prerequisites are unavailable. No mimic-response verdict "
                "was evaluated; this is not evidence that the asset lacks mimic APIs."
            )
        if authored_followers is None:
            raise RuntimeError(
                "MIM: No qualified response pair was resolved; authored mimic presence was not established."
            )
        else:
            backend = str(scene_info.get("active_physics_engine") or "physx").lower()
            reason = _msg_no_mimic_authored(backend)
            if _has_complete_asset_composition(stage, asset_prim, ctx=ctx) and _has_no_authored_active_mimic(
                stage, asset_prim, ctx
            ):
                ctx.add_metric("assessment_applicability", not_applicable("no_active_mimic_followers", reason))
            ctx.skip(reason)
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
        raise RuntimeError(_msg_all_pairs_unresolvable(len(specs), unresolved_sample))
        return

    followers = {spec.follower_dof_index for spec in specs if spec.follower_dof_index is not None}
    excluded = excluded_dof_indices(scene_info, len(robot.dof_names)) | followers
    if any(spec.reference_dof_index in excluded for spec in resolved):
        raise RuntimeError(
            "MIM runtime error: a resolved reference is a dependent/passive/loop DOF; "
            "independent driving of chained coupling is not qualified"
        )
    robot = owned_articulation(robot, scene_info, extra_excluded=followers)
    ctx.step("Settling before MIM test")
    await settle_nominal(ctx, settle_seconds, physics_fps, phase="MIM")
    baseline_bbox = freeze_bbox_reference(
        compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "mimic"
    )

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
        # MIM requires a finite bounded window; unlike MJC it does not invent a
        # local continuous-joint excursion. SDK float32-max is an unlimited
        # sentinel, not an enormous mechanical stop. Preserve finite-pair
        # metrics already collected before an unavailable later window.
        window = bounded_joint_range(lo, hi, 0.0, angular=False)
        if window is None or (hi - lo) <= 1e-6:
            raise RuntimeError("MIM runtime error: " + _msg_reference_no_limits(ref_name, fol_name, lo, hi))

        sweep_lo = lo + (hi - lo) * margin
        sweep_hi = hi - (hi - lo) * margin
        cur = _required_positions(robot, "MIM").copy()

        # Capture the measured rest pose before commands. Normalize the
        # backend's authored equation for diagnostic curves only; a constant
        # absolute offset cancels in displacement from this measured rest pose.
        # The existing verdict remains the direction-agnostic magnitude ratio.
        diagnostic_multiplier, diagnostic_offset = _diagnostic_coefficients(spec)
        rest_positions = _required_positions(robot, "MIM")
        ref_rest = float(rest_positions[ref_idx])
        fol_rest = float(rest_positions[fol_idx])
        motion_metadata = {
            "physics_fps": physics_fps,
            "encoded_video_fps": capture_fps,
            "capture_interval_steps": capture_interval,
            "reference_joint_name": str(ref_name),
            "follower_joint_name": str(fol_name),
            "gearing": float(spec.gear),
            "offset": float(spec.offset),
            "mimic_schema_backend": getattr(spec, "backend", "physx"),
            "diagnostic_multiplier": diagnostic_multiplier,
            "diagnostic_absolute_offset": diagnostic_offset,
            "absolute_equation_unit_basis": "raw numeric authored offset after backend sign normalization; angular offset conversion not qualified; residual diagnostic only",
            "coefficient_unit_caveat": "interpret scaling only with verified compatible reference/follower coordinate units; mixed joint types are not universally qualified",
            "formula_basis": "follower displacement = backend-normalized multiplier * measured reference displacement; constant absolute offset cancels; diagnostic only",
            "gear_ratio_tolerance": gear_ratio_tol,
            "observation_basis": "existing every-ten-step mimic readback; pair-local nominal step time excludes rendering ticks",
        }
        reference_motion = make_joint_observer(
            ctx,
            scene_info,
            str(ref_name),
            "mim_reference_%03d" % pnum,
            {
                "position": {"unit": "{joint}", "source": "RobotHandle articulation position readback"},
                "target": {"unit": "{joint}", "source": "position command issued by test"},
            },
            metadata=motion_metadata,
            sample_stride=1,
        )
        follower_motion = make_joint_observer(
            ctx,
            scene_info,
            str(fol_name),
            "mim_follower_%03d" % pnum,
            {
                "position": {"unit": "{joint}", "source": "RobotHandle articulation position readback"},
                "incremental_displacement": {
                    "unit": "{joint}",
                    "source": "measured follower position minus measured pair rest position",
                },
                "expected_displacement": {
                    "unit": "{joint}",
                    "source": "backend-normalized multiplier times measured reference displacement; constant offset cancels",
                },
                "incremental_error": {
                    "unit": "{joint}",
                    "source": "absolute incremental follower displacement error; not the magnitude-ratio verdict",
                },
            },
            metadata=motion_metadata,
            sample_stride=1,
        )
        # Legacy diagnostic only: absolute-equation residual at the measured
        # rest pose. A nonzero residual does not identify its authoring or runtime cause.
        rest_residual = abs(fol_rest - (diagnostic_multiplier * ref_rest + diagnostic_offset))

        total_frames = max(20, int(sweep_seconds * physics_fps))
        max_err = 0.0  # diagnostic: incremental-motion error, not the ratio verdict
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
                positions = _required_positions(robot, "MIM")
                ref_pos = float(positions[ref_idx])
                fol_pos = float(positions[fol_idx])
                # Diagnostic displacement comparison; absolute offset cancels.
                ref_delta = ref_pos - ref_rest
                fol_delta = fol_pos - fol_rest
                expected_fol_delta = diagnostic_multiplier * ref_delta
                err = abs(fol_delta - expected_fol_delta)
                observation_time = (frame + 1) / physics_fps
                phase = "outbound" if frame <= half else "return"
                reference_motion.sample(
                    {"position": ref_pos, "target": float(tgt)},
                    time_s=observation_time,
                    phase=phase,
                )
                follower_motion.sample(
                    {
                        "position": fol_pos,
                        "incremental_displacement": fol_delta,
                        "expected_displacement": expected_fol_delta,
                        "incremental_error": err,
                    },
                    time_s=observation_time,
                    phase=phase,
                )
                if err > max_err:
                    max_err = err
                # Separate absolute-equation diagnostic. Its residual alone
                # cannot attribute an asset, controller, importer or solver defect.
                abs_expected = compute_expected_follower(ref_pos, diagnostic_multiplier, diagnostic_offset)
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
                current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
                msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                if msg:
                    # Observed growth is a diagnostic, not an identified cause
                    # or authorization to tune the asset/controller.
                    ctx.warn(
                        _msg_sweep_instability(
                            fol_name,
                            ref_name,
                            float(spec.gear),
                            float(spec.offset),
                            msg,
                            physics_fps,
                        )
                    )

            if frame % capture_interval == 0:
                frame_path = await ctx.capture_frame(
                    label="mim_%03d_%04d" % (pnum, frame),
                    stabilize_frames=0,
                )
                if frame_path:
                    capture_frames.append(frame_path)
                    reference_motion.record_capture(frame_path)
                    follower_motion.record_capture(frame_path)
                ctx.scene.update_camera_follow(update_history=True)
            else:
                ctx.scene.update_camera_follow(update_history=False)
            if frame % HB_EVERY == 0:
                ctx.step("MIM pair=%s frame=%d/%d max_err=%.3f" % (fol_name, frame, total_frames, max_err))

        reference_motion.finish("mimic_pair_sweep_completed")
        follower_motion.finish("mimic_pair_sweep_completed")

        # Existing pass criterion: the sampled magnitude ratio matches |gear|.
        # This does not certify direction, absolute offset or every solver state.
        # Backend-normalized direction/residual diagnostics do not affect it.
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
        # Track diagnostic max_err separately; it does not establish causality.
        mean_err = (sum_err / sample_count) if sample_count else 0.0
        # Existing sampled-extrema direction heuristic, compared with the
        # backend-normalized multiplier. It is not a complete trajectory check.
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
            expected_sign = 1.0 if diagnostic_multiplier >= 0.0 else -1.0
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
        # Backend-normalized absolute residuals are independent diagnostics,
        # not proof that an offset is wrong or that coupling is fully correct.
        ctx.add_metric("mim_pair_%s_abs_formula_max_error_rad" % fol_name, max_abs_err)
        ctx.add_metric("mim_pair_%s_rest_residual_rad" % fol_name, rest_residual)

        if not ok:
            record["reason"] = (
                "motion-magnitude mismatch: ratio %.3f (follower/ref) vs |gear|=%.3f, "
                "error %.3f > tolerance %.3f; ref swept %.3f, follower observed %.3f "
                "(expected %.3f); incremental error %.3f in native coordinates; "
                "absolute-formula error %.3f, rest-pose residual %.3f "
                "(raw-offset numeric diagnostics; angular offset conversion unqualified), "
                "direction %s backend-normalized multiplier sign"
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
                "  Measured: follower swept %.3f while reference swept "
                "%.3f in native coordinates (see qualified/unknown motion unit metadata) => motion ratio %.3f.\n"
                "  Expected: motion ratio ~ |gearing| = %.3f (tolerance "
                "%.3f). Error %.3f.\n"
                "  Diagnostics: incremental error %.3f in native coordinates; absolute-formula "
                "error %.3f, rest-pose residual %.3f (raw-offset numeric diagnostics; "
                "angular offset conversion unqualified), direction %s "
                "the backend-normalized multiplier sign. Legacy *_rad metric keys "
                "do not establish the units of a prismatic readback.\n"
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
            # Preserve the magnitude verdict; direction is diagnostic only.
            ctx.warn(_msg_direction_mismatch(fol_name, ref_name, motion_ratio, gear_mag))
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
            "    -1=indeterminate -- direction is diagnostic only)\n"
            "Legacy *_rad metric names remain for compatibility; consult qualified "
            "motion metadata for each joint's actual or unknown runtime unit."
            % (
                summary["pairs_failed"],
                summary["pairs_tested"],
                ", ".join(summary["failure_names"]),
                per_pair_block,
                _msg_drift_fix_hint(),
            )
        )

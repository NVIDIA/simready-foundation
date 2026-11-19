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

"""VEL phase: compare an observed response with resolved ceilings.
V1 reference: shared_phases/velocity_limit.py.
"""

import math

import numpy as np
from simready.foundation.tier_core.runtime_tests._assessment import (
    _has_current_coordinate_exclusions,
    not_applicable,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
    owned_articulation,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    finite_number,
    validate_phase_config,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import engine_note
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_targets import (
    bounded_joint_range,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_utils import (
    merge_velocity_limits,
    resolve_usd_max_velocities,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    required_velocities as _required_velocities,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
    settle_nominal,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
    native_angular_dof_indices,
    usable_velocity,
)

# --------------------------------------------------------------------
# Fix-message helpers
# --------------------------------------------------------------------
#
# Describe the measured criterion separately from its cause. Resolve the
# selected variant, ceiling provenance, runtime units and test setup before
# assigning an asset defect; pasted ratings/gains are not a diagnosis.

_VEL_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:    nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_driven_joints/requirements/physics-joint-max-velocity.md\n"
    "           (DJ.005 -- physxJoint:maxJointVelocity > 0 required on\n"
    "            every revolute/prismatic PhysX driven joint)\n"
    "  Example: sample_content/common_assets/robots_general/Robotiq/"
    "2F-85/simready_usd/runnables/physics/physx.usda\n"
    "           (inspect physxJoint:maxJointVelocity on the selected variant)"
)


def _fix_message_no_velocity_limits():
    # type: () -> str
    """Report missing comparison evidence without prescribing joint ratings."""
    return (
        "VEL: No independently testable joint has both a meaningful positive finite comparison ceiling "
        "and finite increasing bounded travel.\n"
        "SDK unlimited sentinels are not ratings or physical stops; no substitute ceiling or excursion is invented.\n"
        "The test resolves runtime DOF ceilings and authored physxJoint:maxJointVelocity /\n"
        "physxDrivePerformanceEnvelope maxActuatorVelocity inputs. Passive, mimic-follower\n"
        "and closed-loop joints are excluded. Angular USD inputs are degrees/s and are\n"
        "converted to radians/s; linear inputs remain stage-distance/s, not necessarily m/s.\n"
        "Missing comparison evidence does not establish an asset defect. Check the selected\n"
        "variant, actual importer, returned DOF limits, schemas and units before changing\n"
        "authored data. If a rating is truly missing, use the mechanism's verified specification,\n"
        "not a pasted example value. Preserve the original asset and report runtime/test\n"
        "prerequisite limitations separately.\n\n" + _VEL_SPEC_REFERENCE
    )


def _fix_message_violations(failed_count, total, failed_names, failed_details):
    # type: (int, int, str, str) -> str
    """Report the evaluated response separately from an unproved cause."""
    return (
        "VEL: {n}/{total} joint(s) failed the configured velocity criterion or bounding-box guard: {names}.\n\n"
        "The test commands the opposite position-range target with a 5% margin and compares\n"
        "absolute observed velocity with the resolved ceiling plus tolerance. It excludes the\n"
        "first five startup observations when more than ten were collected and can stop\n"
        "after consecutive near-zero observations. Angular comparisons use radians/s;\n"
        "linear comparisons retain runtime native units/s (scale unqualified).\n"
        "This is a sampled response, not a proof\n"
        "of hard-cap enforcement for every possible command.\n\n"
        "Evaluated per-joint peaks:\n{details}\n\n"
        "Inspect per-joint warnings to distinguish a speed exceedance from a bounding-box\n"
        "growth failure. The measured failure does not establish a cause. First verify\n"
        "the selected variant, limit provenance, imported units, actuator controls, solver\n"
        "and test setup. Do not raise a rating to the observed peak, paste arbitrary gains,\n"
        "or loosen tolerance solely to make this run pass. Retuning, if justified by that\n"
        "diagnosis, belongs outside Evaluate; preserve the original run and source asset.\n\n" + _VEL_SPEC_REFERENCE
    ).format(n=failed_count, total=total, names=failed_names, details=failed_details)


def get_defaults():
    # type: () -> dict[str, Any]
    """Default config values for the VEL phase."""
    return {
        "settle_seconds": 1.0,
        "tolerance_percent": 0.05,
        "test_duration_seconds": 2.0,
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        # 15 fps matches FET003 / FET004 defaults.
        "capture_fps": 15,
        # Once |v| stays below ``settled_velocity_threshold`` for
        # ``capture_settled_grace_frames`` consecutive physics frames the
        # joint is treated as "at rest" and the observed window ends.
        # The peak-velocity criterion evaluates the collected window.
        # 0.05 rad/s ~= 3 deg/s; 24 frames at 240 Hz = 0.1 s grace.
        "settled_velocity_threshold": 0.05,
        "capture_settled_grace_frames": 24,
    }


# --------------------------------------------------------------------
# Pure helpers (unit-tested)
# --------------------------------------------------------------------


def compute_velocity_test_target(current_pos, lo, hi):
    # type: (float, float, float) -> float
    """Return the opposite end of the range with a 5% margin."""
    current_pos = finite_number(current_pos, "current position", minimum=-math.inf)
    lo = finite_number(lo, "lower position limit", minimum=-math.inf)
    hi = finite_number(hi, "upper position limit", minimum=-math.inf)
    bounds = bounded_joint_range(lo, hi, current_pos, angular=False)
    if bounds is None:
        raise ValueError("VEL requires finite increasing bounded position limits")
    lo, hi = bounds
    center = lo + (hi - lo) / 2.0
    margin = (hi - lo) * 0.05
    if current_pos <= center:
        return float(min(hi, max(lo, hi - margin)))
    return float(min(hi, max(lo, lo + margin)))


def _meaningful_velocities(values, native_angular_indices=()):
    """Keep VEL's ceiling policy local; unlimited SDK sentinels are absent."""
    if values is None:
        return None
    return np.array(
        [
            (
                velocity
                if (velocity := usable_velocity(value, native_angular=index in native_angular_indices)) is not None
                else math.nan
            )
            for index, value in enumerate(values)
        ],
        dtype=float,
    )


def find_joints_with_velocity_limits(robot, usd_vels=None, exclude_indices=None, omissions=None, scene_info=None):
    # type: (Any, Optional[np.ndarray], Optional[set]) -> list[dict[str, Any]]
    """Select meaningful finite ceilings and increasing bounded travel only.

    SDK unlimited sentinels are absent, not huge mechanical stops/ratings.
    Optional omissions record independent joints outside this test's coverage.

    robot must expose: dof_names, dof_count,
        get_joint_position_limits() -> (lower, upper),
        get_joint_velocity_limits() -> np.ndarray

    ``exclude_indices`` (optional): set of DOF indices to skip — typically the
    union of passive and mimic-follower joints, supplied by the phase runner
    so the velocity-limit test doesn't waste cycles commanding joints whose
    velocity is constrained by the master via ``PhysxMimicJointAPI`` or that
    have no drive at all.
    """
    excl = {int(i) for i in (exclude_indices or set())}
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    angular_indices = native_angular_dof_indices(robot, scene_info or {})
    dof_vels = _meaningful_velocities(robot.get_joint_velocity_limits(), angular_indices)
    usd_vels = _meaningful_velocities(usd_vels)
    merged = merge_velocity_limits(dof_vels, usd_vels, use_min_when_both=True)

    results = []
    for i, name in enumerate(dof_names):
        if i in excl:
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if bounded_joint_range(lo, hi, 0.0, angular=False) is None:
            if omissions is not None:
                omissions.append({"name": str(name)[:128], "reason": "no finite increasing bounded travel"})
            continue

        if merged is None or i >= len(merged):
            if omissions is not None:
                omissions.append({"name": str(name)[:128], "reason": "no meaningful comparison ceiling"})
            continue
        max_vel = float(merged[i])
        if not math.isfinite(max_vel) or max_vel <= 0:
            if omissions is not None:
                omissions.append({"name": str(name)[:128], "reason": "no meaningful comparison ceiling"})
            continue

        d_ok = (
            dof_vels is not None and i < len(dof_vels) and math.isfinite(float(dof_vels[i])) and float(dof_vels[i]) > 0
        )
        u_ok = (
            usd_vels is not None and i < len(usd_vels) and math.isfinite(float(usd_vels[i])) and float(usd_vels[i]) > 0
        )
        if d_ok and u_ok:
            source = "dof_or_usd_min"
        elif d_ok:
            source = "dof"
        elif u_ok:
            source = "usd"
        else:
            source = "none"

        results.append(
            {
                "index": i,
                "name": str(name),
                "lower": lo,
                "upper": hi,
                "max_velocity": max_vel,
                "max_velocity_source": source,
            }
        )
    return results


def analyze_velocity_results(velocities, max_velocity, tolerance_percent):
    # type: (list[float], float, float) -> tuple[list[tuple[int, float]], float]
    """Return (violations, peak_velocity). Drops the first 5 samples as startup."""
    tolerance_percent = finite_number(tolerance_percent, "tolerance_percent")
    max_velocity = finite_number(max_velocity, "max_velocity", positive=True)
    max_allowed = max_velocity * (1.0 + tolerance_percent)
    if not math.isfinite(max_allowed):
        raise ValueError("Velocity tolerance produces a nonfinite allowed ceiling")
    if not velocities:
        return ([], 0.0)
    filtered = velocities[5:] if len(velocities) > 10 else velocities
    if not filtered:
        filtered = velocities
    peak = float(max(filtered))
    violations = [(i, float(v)) for i, v in enumerate(filtered) if v > max_allowed]
    return (violations, peak)


# --------------------------------------------------------------------
# Async runner (native execution requires Kit; host regressions use adapters)
# --------------------------------------------------------------------


async def run_velocity_limit(ctx, robot, scene_info, config):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    """Run the VEL phase. Mutates ctx via skip / add_metric / warn / fail."""
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

    validate_phase_config(config, "velocity_limit")
    nominal_settle_steps(config.get("settle_seconds", 1.0), config.get("physics_fps", 240.0))
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 30))
    settle_seconds = float(config.get("settle_seconds", 1.0))
    test_duration = float(config.get("test_duration_seconds", 2.0))
    tolerance_percent = float(config.get("tolerance_percent", 0.05))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))
    settled_v_thresh = float(config.get("settled_velocity_threshold", 0.05))
    settled_grace = int(config.get("capture_settled_grace_frames", 24))

    # Precondition: find joints with velocity limits
    ctx.step("Scanning joints for authored velocity limits")
    usd_vels = resolve_usd_max_velocities(
        stage=stage,
        robot_prim_path=robot.prim_path,
        dof_names=list(robot.dof_names),
        asset_prim=asset_prim,
        robot_root_prim=robot_root_prim,
        reject_unlimited=True,
    )
    # Exclude passive joints (no drive) and mimic-followers (constrained by
    # reference via PhysxMimicJointAPI) — neither responds to a velocity
    # command independently. Surfaced from scene_info (computed once at
    # setup_robot_test_scene). For arms this set is empty.
    passive_indices = {int(i) for i in scene_info.get("passive_joint_indices") or []}
    follower_indices = {int(i) for i in scene_info.get("mimic_follower_indices") or []}
    loop_indices = {int(i) for i in scene_info.get("loop_joint_indices") or []}
    excluded = passive_indices | follower_indices | loop_indices
    if excluded:
        ctx.add_metric("vel_joints_skipped_passive", len(passive_indices))
        ctx.add_metric("vel_joints_skipped_mimic_follower", len(follower_indices))
        ctx.add_metric("vel_joints_skipped_loop", len(loop_indices))

    omissions = []
    joints = find_joints_with_velocity_limits(
        robot, usd_vels=usd_vels, exclude_indices=excluded, omissions=omissions, scene_info=scene_info
    )
    ctx.add_metric("vel_joints_with_limits", len(joints))
    ctx.add_metric("vel_joints_not_evaluated", len(omissions))
    if omissions:
        ctx.add_metric("vel_joint_eligibility_omissions", omissions[:64])
        ctx.add_metric("vel_joint_eligibility_omissions_truncated", max(0, len(omissions) - 64))
        ctx.warn(
            "VEL: %d independently selected joint(s) were not evaluated because meaningful velocity ceilings "
            "and finite increasing bounded travel are required. This result covers only %d eligible joint(s). "
            "Omitted: %s%s"
            % (
                len(omissions),
                len(joints),
                ", ".join(row["name"] + " (" + row["reason"] + ")" for row in omissions[:8]),
                "; additional omissions recorded by count" if len(omissions) > 8 else "",
            )
        )

    if not joints:
        reason = _fix_message_no_velocity_limits()
        if any(i not in excluded for i in range(len(robot.dof_names))):
            raise RuntimeError(reason)
        if _has_current_coordinate_exclusions(robot, scene_info, ctx=ctx):
            ctx.add_metric("assessment_applicability", not_applicable("no_independent_coordinates", reason))
        ctx.skip(reason)
        return

    robot = owned_articulation(robot, scene_info)
    # Record the helper's acknowledgement, not a claim of physical enforcement.
    merged_limits = np.array([float("nan")] * robot.dof_count, dtype=np.float64)
    for j in joints:
        merged_limits[j["index"]] = j["max_velocity"]
    application_result = robot.apply_velocity_limits_to_tensor_view(merged_limits)
    if application_result is True:
        application_status = "reported_success"
    elif application_result is False:
        application_status = "not_applied"
    else:
        application_status = "unknown"
    ctx.add_metric("vel_velocity_limit_application", application_status)
    ctx.add_metric("vel_velocity_limit_enforcement", "not_verified")
    if application_status != "reported_success":
        ctx.warn(
            "VEL: Runtime velocity-limit application is %s. The test compares the "
            "sampled response with the resolved ceiling; physical hard-cap enforcement "
            "is not verified." % application_status
        )

    # Settle
    ctx.step("Settling robot before velocity tests")
    await settle_nominal(ctx, settle_seconds, physics_fps, phase="VEL")

    baseline_bbox = freeze_bbox_reference(
        compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "vel"
    )

    # Per-joint test
    joints_passed = 0
    joints_failed = 0
    failed_names = []
    failed_details = []  # human-readable lines for the aggregate fail msg
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))

    # Keep healthy sweeps observable to the configured output-inactivity
    # watchdog. See the nominal-step cadence notes in full_range_sweep.py.
    HB_EVERY = 40

    for jnum, jinfo in enumerate(joints, start=1):
        ctx.step("VEL joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))

        from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_history import (
            make_joint_observer,
        )

        motion = make_joint_observer(
            ctx,
            scene_info,
            jinfo["name"],
            "vel_joint_%03d" % jnum,
            {
                "velocity": {"unit": "{joint}/s", "source": "RobotHandle articulation velocity readback"},
                "position_target": {"unit": "{joint}", "source": "position command issued by test"},
                "speed_limit": {
                    "unit": "{joint}/s",
                    "source": "resolved comparison ceiling; see limit_source/provenance",
                },
                "allowed_speed": {"unit": "{joint}/s", "source": "speed limit with configured verdict allowance"},
            },
            metadata={
                "physics_fps": physics_fps,
                "clock_basis": "nominal observed step count / configured physics fps; capture ticks excluded",
                "limit_source": jinfo["max_velocity_source"],
                "tolerance_percent": tolerance_percent,
                "vel_velocity_limit_application": application_status,
                "vel_velocity_limit_enforcement": "not_verified",
            },
        )

        current_positions = _required_positions(robot, "VEL")
        cur = float(current_positions[jinfo["index"]])
        target = compute_velocity_test_target(cur, jinfo["lower"], jinfo["upper"])

        targets = current_positions.astype(float, copy=True)
        targets[jinfo["index"]] = target
        robot.set_joint_position_targets(targets)

        test_frames = max(20, int(test_duration * physics_fps))
        velocities_observed = []
        joint_errors = []
        # Track consecutive near-zero velocity frames so we can BREAK out
        # of the loop once the joint is at rest. Earlier ports stopped only
        # capture and kept stepping physics for the full window, which made
        # VEL spend ~10x more wall time than needed (DGV / EFF had the same
        # bug). The peak velocity is already in velocities_observed; the
        # bbox check below catches any explosion that already happened.
        settled_consecutive = 0
        for frame in range(test_frames):
            await ctx.step_one()
            v = float(_required_velocities(robot, "VEL")[jinfo["index"]])
            velocities_observed.append(abs(v))
            motion.sample(
                {
                    "velocity": v,
                    "position_target": target,
                    "speed_limit": jinfo["max_velocity"],
                    "allowed_speed": jinfo["max_velocity"] * (1.0 + tolerance_percent),
                },
                (frame + 1) / physics_fps,
                "position_command_response",
            )

            if frame % 20 == 0:
                current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
                msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                if msg:
                    joint_errors.append("VEL: Joint '%s': %s" % (jinfo["name"], msg))

            if abs(v) < settled_v_thresh:
                settled_consecutive += 1
            else:
                settled_consecutive = 0

            if frame % capture_interval == 0:
                frame_path = await ctx.capture_frame(
                    label="velocity_limit_%03d_%04d" % (jnum, frame),
                    stabilize_frames=0,
                )
                if frame_path:
                    capture_frames.append(frame_path)
                    motion.record_capture(frame_path)
                ctx.scene.update_camera_follow(update_history=True)
            else:
                ctx.scene.update_camera_follow(update_history=False)

            if frame % HB_EVERY == 0:
                ctx.step("VEL j=%s frame=%d/%d |v|=%.3f" % (jinfo["name"], frame, test_frames, abs(v)))

            if settled_consecutive >= settled_grace:
                ctx.step(
                    "VEL j=%s settled (|v|<%.3f for %d frames) at frame "
                    "%d/%d -- exiting" % (jinfo["name"], settled_v_thresh, settled_grace, frame, test_frames)
                )
                break

        motion.finish("velocity_stop_condition" if settled_consecutive >= settled_grace else "step_budget_exhausted")

        violations, peak = analyze_velocity_results(
            velocities_observed,
            max_velocity=jinfo["max_velocity"],
            tolerance_percent=tolerance_percent,
        )

        if violations or joint_errors:
            joints_failed += 1
            failed_names.append(jinfo["name"])
            overshoot_pct = (peak / jinfo["max_velocity"] - 1.0) * 100
            failed_details.append(
                "    - %s: peak=%.3f, limit=%.3f (+%.1f%% over, "
                "limit-source=%s)"
                % (jinfo["name"], peak, jinfo["max_velocity"], overshoot_pct, jinfo["max_velocity_source"])
            )
            # Per-joint summary; the aggregate fail() below carries the
            # full how-to-fix instructions so we don't duplicate the
            # template on every joint warning.
            msg = (
                "VEL: Joint '%s' failed the velocity criterion or bounding-box guard: "
                "peak=%.3f, max=%.3f (+%.1f%% relative to ceiling, source=%s). "
                "%s %s"
                % (
                    jinfo["name"],
                    peak,
                    jinfo["max_velocity"],
                    overshoot_pct,
                    jinfo["max_velocity_source"],
                    engine_note(
                        "Check the selected variant, limit provenance, actuator controls "
                        "and typed motion history before assigning an asset defect. "
                        "Do not change ratings or gains solely to force a pass."
                    ),
                    engine_note(
                        "Preserve video, logs and the original configuration; distinguish "
                        "speed exceedance from bounding-box growth and runtime/test setup."
                    ),
                )
            )
            for err in joint_errors:
                ctx.warn(err)
            ctx.warn(msg)
        else:
            joints_passed += 1
            ctx.log(
                "VEL: Joint '%s' within comparison ceiling (peak=%.2f <= max=%.2f "
                "runtime joint units/s; see typed motion history)" % (jinfo["name"], peak, jinfo["max_velocity"])
            )

    # Encode video
    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="velocity_limit", role="summary")

    ctx.add_metric("vel_joints_passed", joints_passed)
    ctx.add_metric("vel_joints_failed", joints_failed)

    if joints_failed > 0:
        ctx.fail(
            _fix_message_violations(
                failed_count=joints_failed,
                total=len(joints),
                failed_names=", ".join(failed_names),
                failed_details="\n".join(failed_details) if failed_details else "    (no per-joint detail captured)",
            )
        )

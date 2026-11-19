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

"""STA phase: sampled position response against legal waypoint goals.
V1 reference: shared_phases/state_accuracy.py.

Algorithm retains the v1 observation policy with legal waypoint selection:
- Per joint, command [center, +step, center, -step, center], where zero-derived
  center is clamped inside the reported limits with a range-scaled margin.
  The step is min(15 deg, 10% of joint range) so heavy industrial arms with default
  drive gains receive bounded excursions inside the test window; this does
  not guarantee every drive reaches each waypoint.
- Position tolerance is 5 degrees by default (matches v1). Failing on a tighter rad
  tolerance with full-range targets caused Fanuc CR/CRX joints to fail STA on the
  first smoke run.
- Velocity-reporting consistency and reading consistency are LOGGED, not failed.
  Only position-tracking error past tolerance fails the joint.
"""

import math

from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
    owned_articulation,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    finite_number,
    validate_phase_config,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_utils import smoothstep
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

# ----------------------------------------------------------------------
# Failure-message helpers (asset-author-facing).
#
# Describe the measured criterion separately from its cause. Check the
# selected variant, runtime readbacks and test setup before assigning an
# asset defect; generic pasted gains/ratings are not a diagnosis.
# ----------------------------------------------------------------------

_SPEC_REFERENCE_STA = (
    "REFERENCE:\n"
    "  Spec:      nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_driven_joints/requirements/\n"
    "               drive-joint-value-reasonable.md\n"
    "               physics-drive-and-joint-state.md\n"
    "               joint-has-joint-state-api.md\n"
    "  Example:   sample_content/common_assets/robots_general/ur10/"
    "simready_usd/payloads/Physics/physics.usda\n"
    "             (search for: drive:angular:physics:stiffness)"
)


def _fix_message_no_testable_joints(n_passive, passive_names, n_mimic, mimic_names):
    # type: (int, list, int, list) -> str
    """Report missing prerequisites without prescribing actuator settings."""
    return (
        "STA cannot run: no testable joints after prerequisite filtering.\n"
        "  Passive joints: %d (%s).\n  Mimic followers: %d (%s).\n"
        "Check discovered joints, the selected variant, independently actuated drives,\n"
        "finite non-degenerate position limits and runtime state readbacks. A mimic\n"
        "follower is not independently commanded by this phase. Missing prerequisites\n"
        "are insufficient evidence, not an automatic asset failure. USD angular\n"
        "physics:lowerLimit/upperLimit and drive:angular:physics:targetPosition use\n"
        "degrees; runtime revolute coordinates use radians. USD linear values use\n"
        "stage-distance units, not necessarily meters; runtime linear scaling remains\n"
        "unqualified, so consult the typed history. Preserve the original asset;\n"
        "do not paste generic gains, unlimited force or example limits to force a run.\n%s"
    ) % (
        n_passive,
        ", ".join(passive_names) or "(none)",
        n_mimic,
        ", ".join(mimic_names) or "(none)",
        _SPEC_REFERENCE_STA,
    )


def _fix_message_joint_position_error(joint_name, max_err_deg, tol_deg, reason_summary):
    # type: (str, float, float, str) -> str
    """Report tracking error without asserting a cause or prescribing gains."""
    return (
        "STA: Joint '%s' failed the configured tracking criterion.\n"
        "  Legacy degree-labelled summary: max error %.2f; tolerance %.2f.\n"
        "  Details: %s.\n"
        "For revolute joints the summary converts runtime radians to degrees; for\n"
        "linear joints it is not a physical angle. Use the history's joint type/units\n"
        "and actual commands/readbacks to interpret the response. The cause is not\n"
        "established by this error. Check the selected variant, drive/state API and\n"
        "axis mappings, authored\n"
        "limits, mimic coupling, mass/inertia, test gravity and settling setup before\n"
        "assigning an asset defect. Preserve the original asset; any justified tuning\n"
        "is external, not a prescribed gain multiplier or tolerance relaxation.\n%s"
    ) % (joint_name, max_err_deg, tol_deg, reason_summary, _SPEC_REFERENCE_STA)


def _fix_message_phase_failure(joints_failed, joints_tested, failure_names):
    # type: (int, int, list) -> str
    """Summarize measured failures without changing the tracking criterion."""
    return (
        "STA: %d/%d joints failed the configured state-accuracy criterion.\n"
        "  Failing joints: %s.\n"
        "Inspect per-target warnings, the sta_max_position_error_deg legacy summary\n"
        "and typed motion histories. Confirm the actual issued command versus final\n"
        "goal, selected variant, drive/readback units and solver/test setup before\n"
        "assigning an asset defect. Degree-labelled summaries are not linear-joint\n"
        "angles. Do not multiply gains, rewrite ratings or relax tolerances simply\n"
        "to pass. Preserve the original run and asset while investigating.\n%s"
    ) % (joints_failed, joints_tested, ", ".join(failure_names), _SPEC_REFERENCE_STA)


# ----------------------------------------------------------------------
# Defaults (mirrors v1 shared_phases.state_accuracy.get_all_parameter_defaults)
# ----------------------------------------------------------------------


def get_defaults():
    # type: () -> dict[str, Any]
    return {
        "settle_seconds": 0.5,
        "position_tolerance_deg": 5.0,
        "velocity_tolerance_percent": 0.20,
        "test_duration_seconds": 3.0,
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        "capture_fps": 15,
        "max_step_deg": 15.0,
        "step_range_fraction": 0.10,
    }


# ----------------------------------------------------------------------
# Pure helpers (unit-tested)
# ----------------------------------------------------------------------


def compute_test_positions(lo, hi, max_step_deg=15.0, step_range_fraction=0.10):
    # type: (float, float, float, float) -> list[float]
    """Return [center, +step, center, -step, center] target sequence.

    Step is limited by the configured angular maximum and a range fraction.
    The center is zero clamped into the legal interior; its margin is the
    smaller of 0.05 native coordinates and ten percent of the valid range.
    A directional target can coincide with center when zero is outside limits.
    """
    max_step_deg = finite_number(max_step_deg, "max_step_deg", positive=True)
    step_range_fraction = finite_number(step_range_fraction, "step_range_fraction", positive=True, maximum=1.0)
    rng = float(hi) - float(lo)
    if not (math.isfinite(float(lo)) and math.isfinite(float(hi)) and rng > 0.0):
        raise ValueError("State accuracy requires finite ordered limits")
    margin = min(0.05, 0.10 * rng)
    safe_lo, safe_hi = float(lo) + margin, float(hi) - margin
    center = max(safe_lo, min(safe_hi, 0.0))
    step_size = min(math.radians(float(max_step_deg)), rng * float(step_range_fraction))
    pos_a = max(safe_lo, min(safe_hi, center + step_size))
    pos_b = max(safe_lo, min(safe_hi, center - step_size))
    return [center, pos_a, center, pos_b, center]


def classify_position_error(reported_pos, target, tolerance_rad):
    # type: (float, float, float) -> tuple[bool, Optional[str], float]
    """Pass = finite reading AND |target - reported| <= tolerance_rad.

    Returns (ok, reason_or_None, abs_error). Velocity/consistency are NOT
    checked here -- v1 logs those as warnings, not joint failures.
    """
    tolerance_rad = finite_number(tolerance_rad, "tolerance_rad")
    if not math.isfinite(reported_pos):
        return False, "reading not finite (pos=%r)" % reported_pos, float("inf")
    err = abs(float(target) - float(reported_pos))
    if err > tolerance_rad:
        return (
            False,
            "position error %.4f deg > tolerance %.4f deg" % (math.degrees(err), math.degrees(tolerance_rad)),
            err,
        )
    return True, None, err


def aggregate_sta_summary(per_joint_results):
    # type: (list[dict[str, Any]]) -> dict[str, Any]
    total = len(per_joint_results)
    passed = sum(1 for r in per_joint_results if r["ok"])
    failed = total - passed
    max_pos = max((r.get("max_position_error_rad", 0.0) for r in per_joint_results), default=0.0)
    failure_names = [r["name"] for r in per_joint_results if not r["ok"]]
    return {
        "joints_tested": total,
        "joints_passed": passed,
        "joints_failed": failed,
        "max_position_error_deg": math.degrees(max_pos),
        "failure_names": failure_names,
    }


def compute_motion_frames(test_duration, physics_fps, waypoint_count):
    # type: (float, float, int) -> int
    """Return a per-waypoint ramp budget without changing verdict policy."""
    settle_frames = max(30, int(0.5 * physics_fps))
    test_frames = max(20, int(test_duration * physics_fps))
    frames = max(30, (test_frames - waypoint_count * settle_frames) // waypoint_count)
    return frames


# ----------------------------------------------------------------------
# Async runner (native execution requires Kit; host regressions use adapters)
# ----------------------------------------------------------------------


async def _run_motion_to_target(
    ctx,
    robot,
    jinfo,
    target,
    motion_frames,
    capture_interval,
    capture_frames,
    baseline_bbox,
    bbox_ratio_limit,
    robot_root_prim,
    asset_prim,
    jnum,
    motion=None,
    motion_clock=None,
    motion_phase="waypoint",
):
    """Drive the joint toward target for motion_frames; capture frames.

    The commanded position is RAMPED from the joint's start value to the target
    over the motion window (smoothstep) -- a paced trajectory, not a single step
    command -- so an uncapped joint does not whip toward the target. Other
    independent joints retain starting hold targets; the phase-local facade
    leaves declared dependent/passive control buffers untouched.
    """
    HB_EVERY = 40
    start_positions = _required_positions(robot, "STA").copy()
    start_val = float(start_positions[jinfo["index"]])
    delta = float(target) - start_val
    ramp_frames = max(1, int(motion_frames))

    # Complete the bounded smoothstep command sequence before observing the
    # endpoint hold. Entering a coarse response band does not mean the final
    # goal was commanded; the following hold must not retain an intermediate
    # setpoint and fail an otherwise exact tracker at a tighter tolerance.
    bbox_msgs = []
    for frame in range(motion_frames):
        eased = smoothstep((frame + 1) / float(ramp_frames))
        command = start_positions.copy()
        command[jinfo["index"]] = target if frame + 1 == ramp_frames else start_val + delta * eased
        robot.set_joint_position_targets(command)
        await ctx.step_one()
        if motion_clock is not None:
            motion_clock["steps"] += 1
            motion_clock["issued_target"] = float(command[jinfo["index"]])
        if frame % 20 == 0:
            current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
            msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
            if msg:
                bbox_msgs.append(msg)
        if frame % capture_interval == 0:
            frame_path = await ctx.capture_frame(stabilize_frames=0, label="state_accuracy_%03d_%04d" % (jnum, frame))
            if frame_path:
                capture_frames.append(frame_path)
                if motion is not None:
                    # The retained observation precedes this capture. The
                    # existing verdict readbacks below remain after capture.
                    motion.record_capture(frame_path)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)
        if frame % HB_EVERY == 0:
            ctx.step("STA j=%s motion frame=%d/%d" % (jinfo["name"], frame, motion_frames))

        # Required response observations remain independent of optional hooks.
        pos = float(_required_positions(robot, "STA")[jinfo["index"]])
        vel = float(_required_velocities(robot, "STA")[jinfo["index"]])
        if motion is not None:
            issued = float(command[jinfo["index"]])
            motion.sample(
                {
                    "position": pos,
                    "velocity": vel,
                    "target": issued,
                    "final_goal": target,
                    "error": issued - pos,
                    "goal_error": target - pos,
                },
                motion_clock["steps"] / motion_clock["physics_fps"],
                motion_phase + "_ramp",
            )
    return bbox_msgs


async def _run_settle_to_target(
    ctx,
    robot,
    jinfo,
    target,
    settle_frames,
    capture_interval,
    capture_frames,
    jnum,
    base_frame_label,
    motion=None,
    motion_clock=None,
    motion_phase="waypoint",
):
    """Settle for up to settle_frames; early-exit when joint is at target."""
    HB_EVERY = 40
    pos_tol = 0.005
    vel_tol = 0.01
    consecutive_settled = 0
    min_settle_count = 3
    min_settle_frames = min(10, settle_frames)
    for frame in range(settle_frames):
        await ctx.step_one()
        pos = float(_required_positions(robot, "STA")[jinfo["index"]])
        vel = float(_required_velocities(robot, "STA")[jinfo["index"]])
        if motion is not None:
            motion_clock["steps"] += 1
            # Keep recording the actual final ramp command; observation does
            # not issue or relabel a command on behalf of the controller.
            issued = motion_clock["issued_target"]
            motion.sample(
                {
                    "position": pos,
                    "velocity": vel,
                    "target": issued,
                    "final_goal": target,
                    "error": issued - pos if issued is not None else None,
                    "goal_error": target - pos,
                },
                motion_clock["steps"] / motion_clock["physics_fps"],
                motion_phase + "_settle",
            )
        if abs(pos - target) <= pos_tol and abs(vel) <= vel_tol:
            consecutive_settled += 1
        else:
            consecutive_settled = 0
        if frame % capture_interval == 0:
            frame_path = await ctx.capture_frame(stabilize_frames=0, label="%s_settle_%04d" % (base_frame_label, frame))
            if frame_path:
                capture_frames.append(frame_path)
                if motion is not None:
                    motion.record_capture(frame_path)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)
        if frame % HB_EVERY == 0:
            ctx.step(
                "STA j=%s settle frame=%d/%d |pos-tgt|=%.4f" % (jinfo["name"], frame, settle_frames, abs(pos - target))
            )
        if frame >= min_settle_frames and consecutive_settled >= min_settle_count:
            break


async def run_state_accuracy(ctx, robot, scene_info, config):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    """Run the STA phase. Mutates ctx via skip / add_metric / warn / fail."""
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

    validate_phase_config(config, "state_accuracy")
    nominal_settle_steps(config.get("settle_seconds", 0.5), config.get("physics_fps", 240.0))
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 15))
    settle_seconds = float(config.get("settle_seconds", 0.5))
    test_duration = float(config.get("test_duration_seconds", 3.0))
    pos_tol_deg = float(config.get("position_tolerance_deg", 5.0))
    pos_tol_rad = math.radians(pos_tol_deg)
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))
    max_step_deg = float(config.get("max_step_deg", 15.0))
    step_range_fraction = float(config.get("step_range_fraction", 0.10))

    ctx.step("Scanning joints for finite limits (STA)")
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()

    # Skip joints whose motion is constrained by a mimic relationship — the
    # follower's position is determined by the reference (master) via
    # PhysxMimicJointAPI, so commanding it directly is futile. Without this
    # filter, every mimic-follower joint fails STA with a "position error 15
    # deg" warning that has nothing to do with state-reporting accuracy.
    follower_dof_indices = {int(i) for i in scene_info.get("mimic_follower_indices") or []}
    passive_indices = {int(i) for i in scene_info.get("passive_joint_indices") or []}
    loop_indices = {int(i) for i in scene_info.get("loop_joint_indices") or []}

    joints = []
    skipped_passive = []
    skipped_mimic = []
    skipped_loop = []
    for i, name in enumerate(dof_names):
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if not (math.isfinite(lo) and math.isfinite(hi) and (hi - lo) >= 0.01):
            continue
        if i in passive_indices:
            skipped_passive.append(str(name))
            continue
        if i in follower_dof_indices:
            skipped_mimic.append(str(name))
            continue
        if i in loop_indices:
            skipped_loop.append(str(name))
            continue
        joints.append({"index": i, "name": str(name), "lower": lo, "upper": hi})

    if skipped_loop:
        ctx.step(
            "STA: skipping %d closed-loop / parallel-linkage joint(s) "
            "(constrained by the loop; cannot be driven to an independent "
            "target): %s" % (len(skipped_loop), ", ".join(skipped_loop))
        )

    ctx.add_metric("sta_joints_with_limits", len(joints))
    ctx.add_metric("sta_joints_skipped_passive", len(skipped_passive))
    ctx.add_metric("sta_joints_skipped_mimic_follower", len(skipped_mimic))
    ctx.add_metric("sta_joints_skipped_loop", len(skipped_loop))
    if skipped_mimic:
        ctx.step(
            "STA: skipping %d mimic-follower joint(s) (constrained by reference "
            "via PhysxMimicJointAPI; cannot be tested independently): %s"
            % (len(skipped_mimic), ", ".join(skipped_mimic))
        )
    if skipped_passive:
        ctx.step("STA: skipping %d passive joint(s): %s" % (len(skipped_passive), ", ".join(skipped_passive)))
    if not joints:
        ctx.skip(
            _fix_message_no_testable_joints(
                n_passive=len(skipped_passive),
                passive_names=skipped_passive,
                n_mimic=len(skipped_mimic),
                mimic_names=skipped_mimic,
            )
        )
        return

    robot = owned_articulation(robot, scene_info)
    ctx.step("Settling robot before STA")
    await settle_nominal(ctx, settle_seconds, physics_fps, phase="STA")
    baseline_bbox = freeze_bbox_reference(
        compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "sta"
    )

    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    per_joint_results = []

    for jnum, jinfo in enumerate(joints, start=1):
        ctx.step("STA joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))

        from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_history import (
            make_joint_observer,
        )

        motion = make_joint_observer(
            ctx,
            scene_info,
            jinfo["name"],
            "sta_joint_%03d" % jnum,
            {
                "position": {"unit": "{joint}", "source": "RobotHandle articulation position readback"},
                "velocity": {"unit": "{joint}/s", "source": "RobotHandle articulation velocity readback"},
                "target": {"unit": "{joint}", "source": "position command issued by test"},
                "final_goal": {"unit": "{joint}", "source": "waypoint destination; not necessarily the issued command"},
                "error": {"unit": "{joint}", "source": "command minus measured position"},
                "goal_error": {"unit": "{joint}", "source": "waypoint destination minus position"},
            },
            metadata={
                "physics_fps": physics_fps,
                "clock_basis": "cumulative observed step count / configured physics fps; capture ticks excluded",
                "position_tolerance_rad": pos_tol_rad,
                "tolerance_basis": "existing angular verdict configuration; not inferred for linear joints",
            },
        )
        motion_clock = {"steps": 0, "physics_fps": physics_fps, "issued_target": None}

        positions = compute_test_positions(
            jinfo["lower"],
            jinfo["upper"],
            max_step_deg=max_step_deg,
            step_range_fraction=step_range_fraction,
        )

        settle_frames_per_target = max(30, int(0.5 * physics_fps))
        motion_frames_per_target = compute_motion_frames(
            test_duration,
            physics_fps,
            len(positions),
        )

        max_err_rad = 0.0
        per_target_errors = []
        all_bbox_msgs = []
        for tnum, target in enumerate(positions, start=1):
            ctx.log(
                "STA: j=%s target %d/%d = %.4f rad (%.2f deg)"
                % (jinfo["name"], tnum, len(positions), target, math.degrees(target))
            )
            bbox_msgs = await _run_motion_to_target(
                ctx,
                robot,
                jinfo,
                target,
                motion_frames_per_target,
                capture_interval,
                capture_frames,
                baseline_bbox,
                bbox_ratio_limit,
                robot_root_prim,
                asset_prim,
                jnum,
                motion=motion,
                motion_clock=motion_clock,
                motion_phase="waypoint_%03d" % tnum,
            )
            all_bbox_msgs.extend(bbox_msgs)
            await _run_settle_to_target(
                ctx,
                robot,
                jinfo,
                target,
                settle_frames_per_target,
                capture_interval,
                capture_frames,
                jnum,
                "state_accuracy_%03d_t%d" % (jnum, tnum),
                motion=motion,
                motion_clock=motion_clock,
                motion_phase="waypoint_%03d" % tnum,
            )
            final_pos = float(_required_positions(robot, "STA")[jinfo["index"]])
            ok_target, reason_target, err = classify_position_error(
                final_pos,
                target,
                pos_tol_rad,
            )
            per_target_errors.append(
                {
                    "target": target,
                    "reported": final_pos,
                    "ok": ok_target,
                    "reason": reason_target,
                    "abs_error": err,
                }
            )
            if err > max_err_rad and math.isfinite(err):
                max_err_rad = err

        motion.finish("waypoint_sequence_completed")

        joint_ok = all(t["ok"] for t in per_target_errors) and not all_bbox_msgs
        record = {
            "name": jinfo["name"],
            "ok": joint_ok,
            "max_position_error_rad": max_err_rad,
            "per_target": per_target_errors,
            "bbox_msgs": all_bbox_msgs,
        }
        if not joint_ok:
            failed_targets = [t for t in per_target_errors if not t["ok"]]
            reason_summary = "; ".join(t["reason"] for t in failed_targets if t["reason"])
            if all_bbox_msgs:
                reason_summary = (reason_summary + "; " if reason_summary else "") + "bbox: " + "; ".join(all_bbox_msgs)
            if not reason_summary:
                reason_summary = "(no per-target reason captured -- check " "result.json `sta_max_position_error_deg`)"
            ctx.warn(
                _fix_message_joint_position_error(
                    joint_name=jinfo["name"],
                    max_err_deg=math.degrees(max_err_rad),
                    tol_deg=pos_tol_deg,
                    reason_summary=reason_summary,
                )
            )
        else:
            ctx.log(
                "STA: Joint '%s' ok (max_err=%.3f deg <= tol %.2f deg)"
                % (jinfo["name"], math.degrees(max_err_rad), pos_tol_deg)
            )
        per_joint_results.append(record)

    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="state_accuracy", role="summary")

    summary = aggregate_sta_summary(per_joint_results)
    ctx.add_metric("sta_joints_tested", summary["joints_tested"])
    ctx.add_metric("sta_joints_passed", summary["joints_passed"])
    ctx.add_metric("sta_joints_failed", summary["joints_failed"])
    ctx.add_metric("sta_max_position_error_deg", summary["max_position_error_deg"])

    if summary["joints_failed"] > 0:
        ctx.fail(
            _fix_message_phase_failure(
                joints_failed=summary["joints_failed"],
                joints_tested=summary["joints_tested"],
                failure_names=summary["failure_names"],
            )
        )

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
"""DGV phase: step-response quality (overshoot / settling / oscillations).
V1 reference: shared_phases/drive_gain_validation.py.
"""
import math

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready_benchmark_kit_suite.articulation_phases.passive_joints import (
    detect_passive_joints,
)
from simready_benchmark_kit_suite.articulation_phases.robot_state import (
    reset_to_default,
)

# ----------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------


def get_defaults():
    # type: () -> Dict[str, Any]
    # Defaults match v1 shared_phases.drive_gain_validation (post-Fanuc smoke
    # 2026-04-24): a constant 30 deg step (NOT a fraction of joint range), 5 s
    # settling window, 50%% overshoot allowed, and 20 oscillations max. The
    # earlier 0.3-fraction step + 2 s + 20%% + 3 osc combination was 3-7x
    # tighter than v1 and failed industrial arms with stock drive gains.
    return {
        "settle_seconds": 1.0,
        "step_magnitude_deg": 30.0,
        "test_duration_seconds": 5.0,
        "max_overshoot_pct": 50.0,
        "max_settling_seconds": 5.0,
        "max_oscillations": 20,
        "settling_tolerance": 0.05,
        "step_fatal": False,
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        "capture_fps": 15,
        "settled_velocity_threshold": 0.05,
        "capture_settled_grace_frames": 24,
    }


# ----------------------------------------------------------------------
# Pure helpers (unit-tested)
# ----------------------------------------------------------------------


def compute_overshoot(positions, step_start, step_target):
    # type: (np.ndarray, float, float) -> float
    """Return overshoot as a fraction of step magnitude (0.0 = none)."""
    step_mag = float(step_target - step_start)
    if abs(step_mag) < 1e-9:
        return 0.0
    peak = float(np.max(np.asarray(positions, dtype=np.float64)))
    if step_mag > 0:
        excursion = peak - step_target
    else:
        trough = float(np.min(np.asarray(positions, dtype=np.float64)))
        excursion = step_target - trough
    if excursion <= 0:
        return 0.0
    return float(excursion / abs(step_mag))


def compute_settling_time(positions, times, step_target, settle_band):
    # type: (np.ndarray, np.ndarray, float, float) -> Optional[float]
    """First time the position enters [target-band, target+band] AND stays there."""
    pos = np.asarray(positions, dtype=np.float64)
    t = np.asarray(times, dtype=np.float64)
    within = np.abs(pos - step_target) <= settle_band
    if not within.any():
        return None
    # Find longest trailing stretch of True; if it extends to the last frame,
    # settling time = first frame of that stretch.
    n = len(within)
    idx = n - 1
    if not within[idx]:
        return None
    while idx > 0 and within[idx - 1]:
        idx -= 1
    return float(t[idx])


def count_oscillations(velocities):
    # type: (np.ndarray) -> int
    """Count sign changes of velocity (zero-crossings). 0 for monotonic motion."""
    v = np.asarray(velocities, dtype=np.float64)
    if v.size < 2:
        return 0
    signs = np.sign(v)
    # Treat zero as same sign as the previous sample to avoid double-counting grazes.
    for i in range(1, signs.size):
        if signs[i] == 0:
            signs[i] = signs[i - 1]
    diffs = np.diff(signs)
    return int(np.count_nonzero(diffs))


def aggregate_dgv_summary(per_joint_results):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    total = len(per_joint_results)
    passed = sum(1 for r in per_joint_results if r["ok"])
    failed = total - passed
    return {
        "joints_tested": total,
        "joints_passed": passed,
        "joints_failed": failed,
        "failure_names": [r["name"] for r in per_joint_results if not r["ok"]],
    }


# ----------------------------------------------------------------------
# Async runner (Kit-only, not unit-tested)
# ----------------------------------------------------------------------


async def run_drive_gain_validation(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run DGV phase. Mutates ctx via skip / add_metric / warn / fail."""
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    default_state = scene_info.get("default_state")

    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 15))
    settle_seconds = float(config.get("settle_seconds", 1.0))
    test_duration = float(config.get("test_duration_seconds", 5.0))
    step_magnitude_rad = math.radians(float(config.get("step_magnitude_deg", 30.0)))
    max_overshoot_pct = float(config.get("max_overshoot_pct", 50.0))
    max_settling = float(config.get("max_settling_seconds", 5.0))
    max_oscillations = int(config.get("max_oscillations", 20))
    settling_tolerance = float(config.get("settling_tolerance", 0.05))
    step_fatal = bool(config.get("step_fatal", False))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))
    settled_v_thresh = float(config.get("settled_velocity_threshold", 0.05))
    settled_grace = int(config.get("capture_settled_grace_frames", 24))

    HB_EVERY = 40

    # ---- joint selection: actively driven AND not a mimic follower.
    # Passives have no DriveAPI / no positive stiffness — commanding them
    # produces no response. Mimic followers' positions are determined by the
    # reference (master) via PhysxMimicJointAPI — driving them independently
    # is futile. Both sets come from scene_info (computed once at setup); for
    # arms with no mimic, the follower set is empty so behavior is unchanged.
    ctx.step("Scanning for actively-driven joints (excluding passive + mimic followers)")
    passive_idxs = set(int(i) for i in scene_info.get("passive_joint_indices") or [])
    follower_idxs = set(int(i) for i in scene_info.get("mimic_follower_indices") or [])
    loop_idxs = set(int(i) for i in scene_info.get("loop_joint_indices") or [])
    # Fallback if scene_info is missing the keys (older callers): re-detect passives.
    if not scene_info.get("passive_joint_indices") and "passive_joint_indices" not in scene_info:
        passive_pair = detect_passive_joints(stage, robot.prim_path, list(robot.dof_names))
        passive_idxs = set(int(i) for i in (passive_pair[0] or []))
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    joints = []
    for i, name in enumerate(dof_names):
        if i in passive_idxs:
            continue
        if i in follower_idxs:
            continue
        if i in loop_idxs:
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if not (math.isfinite(lo) and math.isfinite(hi) and (hi - lo) > 1e-6):
            continue
        joints.append({"index": i, "name": str(name), "lower": lo, "upper": hi})

    ctx.add_metric("dgv_joints_tested", len(joints))
    ctx.add_metric("dgv_passive_joints_skipped", len(passive_idxs))
    ctx.add_metric("dgv_mimic_follower_joints_skipped", len(follower_idxs))
    if not joints:
        ctx.skip(
            _fix_message_no_drivable_joints(
                asset_path=str(asset_prim.GetPath()) if asset_prim is not None else "<unknown>",
                dof_count=len(dof_names),
                passive_count=len(passive_idxs),
                follower_count=len(follower_idxs),
            )
        )
        return

    ctx.step("Settling robot before DGV")
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)

    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    per_joint_results = []

    for jnum, jinfo in enumerate(joints, start=1):
        ctx.step("DGV joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))

        # Per-joint reset to default state for isolation.
        if default_state is not None:
            await reset_to_default(ctx, robot, default_state, settle_seconds=0.2)

        current_positions = robot.get_joint_positions()
        cur = float(current_positions[jinfo["index"]])
        # v1 parity: use a constant step magnitude (default 30 deg) instead of a
        # fraction of joint range. Pick the direction that keeps the step inside
        # the joint's authored limits.
        candidate_up = cur + step_magnitude_rad
        candidate_down = cur - step_magnitude_rad
        if candidate_up <= jinfo["upper"] - 1e-6:
            step_target = candidate_up
        elif candidate_down >= jinfo["lower"] + 1e-6:
            step_target = candidate_down
        else:
            # Joint range smaller than step: use whichever clamp leaves the
            # largest distance from current.
            step_target = jinfo["upper"] if (jinfo["upper"] - cur) >= (cur - jinfo["lower"]) else jinfo["lower"]
        step_target = max(jinfo["lower"], min(jinfo["upper"], step_target))
        if abs(step_target - cur) < 1e-6:
            per_joint_results.append(
                {
                    "name": jinfo["name"],
                    "ok": True,
                    "overshoot_pct": 0.0,
                    "settling_time": 0.0,
                    "oscillations": 0,
                    "reason": "step smaller than epsilon -- skipping",
                }
            )
            continue

        targets = current_positions.copy()
        targets[jinfo["index"]] = step_target
        robot.set_joint_position_targets(targets)

        test_frames = max(20, int(test_duration * physics_fps))
        positions_buf = np.zeros(test_frames, dtype=np.float64)
        velocities_buf = np.zeros(test_frames, dtype=np.float64)
        times_buf = np.zeros(test_frames, dtype=np.float64)
        joint_errors = []
        settled_consecutive = 0
        actual_frames = 0

        for frame in range(test_frames):
            await ctx.step_one()
            pos_v = robot.get_joint_positions()[jinfo["index"]]
            vel_v = robot.get_joint_velocities()[jinfo["index"]]
            positions_buf[frame] = float(pos_v)
            velocities_buf[frame] = float(vel_v)
            times_buf[frame] = float(frame) / physics_fps
            actual_frames = frame + 1

            if frame % 20 == 0:
                current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
                msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                if msg:
                    joint_errors.append("DGV: Joint '%s': %s" % (jinfo["name"], msg))

            if abs(float(vel_v)) < settled_v_thresh:
                settled_consecutive += 1
            else:
                settled_consecutive = 0

            if frame % capture_interval == 0:
                frame_path = await ctx.capture_frame(
                    label="dgv_%03d_%04d" % (jnum, frame),
                    stabilize_frames=0,
                )
                if frame_path:
                    capture_frames.append(frame_path)
                ctx.scene.update_camera_follow(update_history=True)
            else:
                ctx.scene.update_camera_follow(update_history=False)
            if frame % HB_EVERY == 0:
                ctx.step("DGV j=%s frame=%d/%d |v|=%.3f" % (jinfo["name"], frame, test_frames, abs(float(vel_v))))

            # Settled-exit BREAKS the loop (not just capture). Once the joint
            # is at rest under the step input we have all the data needed for
            # overshoot/settling-time/oscillation analysis -- continuing to
            # step physics produces no new information and dominated wall time.
            if settled_consecutive >= settled_grace:
                ctx.step("DGV j=%s settled at frame %d/%d -- exiting" % (jinfo["name"], frame, test_frames))
                break

        pos_slice = positions_buf[:actual_frames]
        vel_slice = velocities_buf[:actual_frames]
        time_slice = times_buf[:actual_frames]
        overshoot_frac = compute_overshoot(pos_slice, step_start=cur, step_target=step_target)
        overshoot_pct = overshoot_frac * 100.0
        settling_time = compute_settling_time(
            pos_slice,
            time_slice,
            step_target=step_target,
            settle_band=settling_tolerance * abs(step_target - cur),
        )
        oscillations = count_oscillations(vel_slice)

        ok = (
            overshoot_pct <= max_overshoot_pct
            and (settling_time is not None and settling_time <= max_settling)
            and oscillations <= max_oscillations
        )
        reason = None
        if not ok:
            reason = "overshoot=%.1f%% (max %.1f%%), settle=%s s (max %.1f), osc=%d (max %d)" % (
                overshoot_pct,
                max_overshoot_pct,
                "None" if settling_time is None else ("%.2f" % settling_time),
                max_settling,
                oscillations,
                max_oscillations,
            )

        record = {
            "name": jinfo["name"],
            "ok": ok,
            "overshoot_pct": overshoot_pct,
            "settling_time": settling_time if settling_time is not None else float("inf"),
            "oscillations": oscillations,
        }
        if reason:
            record["reason"] = reason
            msg = _fix_message_joint_step_response(
                joint_name=jinfo["name"],
                overshoot_pct=overshoot_pct,
                max_overshoot_pct=max_overshoot_pct,
                settling_time=settling_time,
                max_settling=max_settling,
                oscillations=oscillations,
                max_oscillations=max_oscillations,
                step_target=step_target,
                step_start=cur,
            )
            ctx.warn(msg)
        else:
            ctx.log(
                "DGV: Joint '%s' ok (overshoot=%.1f%%, settle=%.2f s, osc=%d)"
                % (jinfo["name"], overshoot_pct, record["settling_time"], oscillations)
            )
        for err in joint_errors:
            ctx.warn(err)
        per_joint_results.append(record)

    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="drive_gain_validation", role="summary")

    summary = aggregate_dgv_summary(per_joint_results)
    ctx.add_metric("dgv_joints_passed", summary["joints_passed"])
    ctx.add_metric("dgv_joints_failed", summary["joints_failed"])

    if summary["joints_failed"] > 0 and step_fatal:
        ctx.fail(
            _fix_message_dgv_summary_failure(
                joints_failed=summary["joints_failed"],
                joints_tested=summary["joints_tested"],
                failure_names=summary["failure_names"],
                max_overshoot_pct=max_overshoot_pct,
                max_settling=max_settling,
                max_oscillations=max_oscillations,
            )
        )


# ----------------------------------------------------------------------
# Actionable failure messages
#
# Philosophy: when a test
# cannot run on -- or fails on -- an asset, the message returned to the
# author must teach them EXACTLY how to fix the asset, not just say what
# went wrong. These string-builders are kept module-private and unit-test
# friendly so they can grow without bloating the runner above.
# ----------------------------------------------------------------------

_DGV_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:     nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_driven_joints/requirements/drive-joint-value-reasonable.md\n"
    "            (DJ.006: stiffness ~100-10000, damping ~1-100 as a\n"
    "             starting envelope; heavier links typically need higher\n"
    "             stiffness and proportionally higher damping.)\n"
    "  Schema:   UsdPhysicsDriveAPI on each actuated joint\n"
    "            (drive:angular:* for revolute, drive:linear:* for prismatic)\n"
    "  Example:  sample_content/common_assets/robots_general/ur10/"
    "simready_isaac_usd/payloads/Physics/physics.usda\n"
    "            (per-joint drive:angular:physics:stiffness / :damping /\n"
    "             :maxForce authored on each PhysicsRevoluteJoint)"
)


def _fix_message_no_drivable_joints(asset_path, dof_count, passive_count, follower_count):
    # type: (str, int, int, int) -> str
    """Asset has no joints DGV can drive — author the missing DriveAPI authoring.

    Reached when the active-joint scan (after excluding passive joints and
    mimic followers, and filtering to finite, non-zero joint limits) yields
    an empty set. The asset is either (a) entirely passive / mimic, (b)
    missing PhysicsDriveAPI on every joint, or (c) authoring joint limits
    of zero range. All three are asset-authoring gaps.
    """
    return (
        "DGV: no actively-driven joints found under {root}.\n"
        "  DOFs discovered:           {dofs}\n"
        "  Excluded as passive:       {passive} (no DriveAPI / stiffness <= 0)\n"
        "  Excluded as mimic follower:{followers} (driven by PhysxMimicJointAPI)\n"
        "  Drivable after filter:     0\n"
        "\n"
        "DGV runs a per-joint step input and measures overshoot, settling\n"
        "time, and oscillation count. It needs at least one joint that has\n"
        "BOTH (i) UsdPhysicsDriveAPI applied with positive stiffness, and\n"
        "(ii) authored joint limits with non-zero range. Without that, the\n"
        "controller has nothing to drive.\n"
        "\n"
        "FIX (most common cause: missing PhysicsDriveAPI). On each actuated\n"
        "revolute joint, apply DriveAPI and author stiffness / damping /\n"
        "maxForce. Edit the prim in your USD file:\n"
        "\n"
        '    def PhysicsRevoluteJoint "shoulder_pan_joint" (\n'
        '        prepend apiSchemas = ["PhysicsDriveAPI:angular"]\n'
        "    )\n"
        "    {{\n"
        "        rel physics:body0 = </Base>\n"
        "        rel physics:body1 = </ShoulderLink>\n"
        '        uniform token physics:axis = "Z"\n'
        "\n"
        "        # Joint limits (REQUIRED -- DGV skips joints with zero range)\n"
        "        float physics:lowerLimit = -180.0\n"
        "        float physics:upperLimit =  180.0\n"
        "\n"
        "        # Drive gains. Tune per-joint -- heavier proximal links\n"
        "        # need higher stiffness/damping than distal wrists.\n"
        "        # Starting envelope (DJ.006): stiffness ~100-10000,\n"
        "        # damping ~1-100; the UR10 reference asset uses values\n"
        "        # from ~7 (wrist 3) up to ~360000 (shoulder lift).\n"
        "        float drive:angular:physics:stiffness = 1000.0\n"
        "        float drive:angular:physics:damping   = 50.0\n"
        "        float drive:angular:physics:maxForce  = 1000.0\n"
        "        float drive:angular:physics:targetPosition = 0.0\n"
        "    }}\n"
        "\n"
        "For PRISMATIC joints use drive:linear:* (same scheme). For mimic\n"
        "followers leave drive stiffness/damping at 0.0 -- they get their\n"
        "position from the reference joint via PhysxMimicJointAPI and are\n"
        "EXPECTED to be excluded from DGV.\n"
        "\n"
        "{ref}"
    ).format(
        root=asset_path,
        dofs=dof_count,
        passive=passive_count,
        followers=follower_count,
        ref=_DGV_SPEC_REFERENCE,
    )


def _fix_message_joint_step_response(
    joint_name,
    overshoot_pct,
    max_overshoot_pct,
    settling_time,
    max_settling,
    oscillations,
    max_oscillations,
    step_target,
    step_start,
):
    # type: (str, float, float, Any, float, int, int, float, float) -> str
    """Per-joint behavior failure -- name the symptom and the gain to tune.

    The author needs to know (a) which joint, (b) which metric failed,
    (c) which authored drive value to inspect, and (d) a reasonable target
    range. Each failing metric maps cleanly to a specific gain.
    """
    settle_str = "never settled" if settling_time is None else ("%.2f s" % settling_time)

    symptoms = []
    if overshoot_pct > max_overshoot_pct:
        symptoms.append(
            "  - OVERSHOOT %.1f%% > max %.1f%%\n"
            "      Drive is underdamped relative to its stiffness. RAISE\n"
            "      `drive:*:physics:damping` (try +50%% to start), or LOWER\n"
            "      `drive:*:physics:stiffness` ~20%%. Aim for a critically-\n"
            "      damped / slightly underdamped response.\n"
            "      Typical ratio: damping ~= 2 * sqrt(stiffness * effective_inertia)."
            % (overshoot_pct, max_overshoot_pct)
        )
    if settling_time is None or settling_time > max_settling:
        symptoms.append(
            "  - SETTLING %s > max %.1f s\n"
            "      Either the PD controller is too soft (raise stiffness;\n"
            "      values <100 are usually too low for a multi-kg link), or\n"
            "      `drive:*:physics:maxForce` is saturating before the joint\n"
            "      can reach the target. If settling_time is None, the joint\n"
            "      did NOT enter the +/-%.0f%% target band at all -- check\n"
            "      maxForce, friction, and that no downstream passive joint\n"
            "      is dragging on this link." % (settle_str, max_settling, 5.0)
        )
    if oscillations > max_oscillations:
        symptoms.append(
            "  - OSCILLATIONS %d zero-crossings > max %d\n"
            "      Velocity is reversing too often -- classic underdamped\n"
            "      PD. RAISE damping. Heavy base/shoulder joints often look\n"
            "      more underdamped in sim than on hardware; review the\n"
            "      captured DGV video before retuning aggressively." % (oscillations, max_oscillations)
        )

    return (
        "DGV: joint '{name}' step-response outside thresholds.\n"
        "  Step:        {start_rad:.3f} rad -> {target_rad:.3f} rad\n"
        "  Overshoot:   {ov:.1f}% (limit {ov_max:.1f}%)\n"
        "  Settle:      {settle} (limit {settle_max:.1f} s)\n"
        "  Oscillations:{osc} (limit {osc_max})\n"
        "\n"
        "Failing metrics and the specific drive values to tune:\n"
        "{symptoms}\n"
        "\n"
        "FIX: locate the PhysicsRevoluteJoint / PhysicsPrismaticJoint prim\n"
        "for DOF '{name}' in your USD file and adjust its DriveAPI:\n"
        "\n"
        "    float drive:angular:physics:stiffness = <value>   # raise/lower per above\n"
        "    float drive:angular:physics:damping   = <value>   # raise to kill overshoot/osc\n"
        "    float drive:angular:physics:maxForce  = <value>   # raise if settling is None\n"
        "\n"
        "(Prismatic joints: use drive:linear:* instead of drive:angular:*.)\n"
        "This is a WARNING by default. To make it fatal for CI, set\n"
        "`step_fatal: true` in the DGV phase config.\n"
        "\n"
        "{ref}"
    ).format(
        name=joint_name,
        start_rad=step_start,
        target_rad=step_target,
        ov=overshoot_pct,
        ov_max=max_overshoot_pct,
        settle=settle_str,
        settle_max=max_settling,
        osc=oscillations,
        osc_max=max_oscillations,
        symptoms="\n".join(symptoms) if symptoms else "  (none -- joint passed)",
        ref=_DGV_SPEC_REFERENCE,
    )


def _fix_message_dgv_summary_failure(
    joints_failed,
    joints_tested,
    failure_names,
    max_overshoot_pct,
    max_settling,
    max_oscillations,
):
    # type: (int, int, list, float, float, int) -> str
    """Aggregate failure (step_fatal mode) -- per-joint detail is in warnings.

    The per-joint ctx.warn() calls above already carry concrete tuning
    instructions for each individual failure. This aggregate message
    summarizes the run and points back at those warnings, plus repeats
    the failure-mode -> drive-value mapping so the asset author can plan
    their tuning pass without scrolling.
    """
    return (
        "DGV: {failed}/{tested} joints failed step-response: {names}\n"
        "\n"
        "Each failing joint has a detailed warning above with its specific\n"
        "metrics and the exact DriveAPI attribute to tune. Failure modes\n"
        "and their fixes (DJ.006 reasonable ranges in brackets):\n"
        "\n"
        "- Overshoot > {ov_max:.0f}%:\n"
        "      RAISE `drive:*:physics:damping` (envelope ~1-100), or\n"
        "      LOWER `drive:*:physics:stiffness` (envelope ~100-10000).\n"
        "      Heavy distal joints in simulation often look more\n"
        "      underdamped than on real hardware -- the captured DGV\n"
        "      video shows the actual trajectory; review it before\n"
        "      aggressive retuning.\n"
        "\n"
        "- Settling > {settle_max:.1f} s:\n"
        "      RAISE `drive:*:physics:stiffness` so the joint reaches the\n"
        "      target band faster -- but expect new overshoot, and raise\n"
        "      damping in proportion.\n"
        "\n"
        "- Oscillations > {osc_max} zero-crossings:\n"
        "      Drive is underdamped. RAISE `drive:*:physics:damping`.\n"
        "\n"
        "- Settling time = inf (never settled):\n"
        "      The PD controller could not hold the step target. Verify\n"
        "      `drive:*:physics:maxForce` is large enough (saturation\n"
        "      caps the achievable acceleration) and that no passive\n"
        "      downstream joint is dragging on the chain.\n"
        "\n"
        "For heavy base/shoulder joints that look underdamped only in\n"
        "sim, run with `step_fatal: false` (the default) and treat as\n"
        "warnings; the captured trajectory is recorded for manual review.\n"
        "\n"
        "{ref}"
    ).format(
        failed=joints_failed,
        tested=joints_tested,
        names=", ".join(failure_names) if failure_names else "(none reported)",
        ov_max=max_overshoot_pct,
        settle_max=max_settling,
        osc_max=max_oscillations,
        ref=_DGV_SPEC_REFERENCE,
    )

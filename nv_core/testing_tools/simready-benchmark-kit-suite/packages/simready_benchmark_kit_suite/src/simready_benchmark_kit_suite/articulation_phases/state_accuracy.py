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
"""STA phase: per-joint commanded-position accuracy + state-reporting sanity.
V1 reference: shared_phases/state_accuracy.py.

Algorithm matches v1 (post-Fanuc smoke run 2026-04-24):
- Per joint, command a 5-step sequence around 0: [center, +step, center, -step, center].
  The step is min(15 deg, 10% of joint range) so heavy industrial arms with default
  drive gains can reach each waypoint inside the test window.
- Position tolerance is 5 degrees by default (matches v1). Failing on a tighter rad
  tolerance with full-range targets caused Fanuc CR/CRX joints to fail STA on the
  first smoke run.
- Velocity-reporting consistency and reading consistency are LOGGED, not failed.
  Only position-tracking error past tolerance fails the joint.
"""
import math

from simready_benchmark_kit_suite.articulation_phases.error_utils import (
    asset_fix,
    engine_note,
)
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready_benchmark_kit_suite.articulation_phases.motion_utils import smoothstep

# ----------------------------------------------------------------------
# Failure-message helpers (asset-author-facing).
#
# Library philosophy: when
# STA cannot run, or a joint fails state-accuracy, the message that lands
# in result.json / the HTML report is the only signal the asset author
# sees. Each message names the failure, says what was found vs. expected,
# points at the prim(s)/attribute(s) to edit, gives a paste-ready USDA
# snippet or concrete edit with example values, and links to the spec +
# a working real-asset example.
# ----------------------------------------------------------------------

_SPEC_REFERENCE_STA = (
    "REFERENCE:\n"
    "  Spec:      nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_driven_joints/requirements/\n"
    "               drive-joint-value-reasonable.md\n"
    "               physics-drive-and-joint-state.md\n"
    "               joint-has-joint-state-api.md\n"
    "  Example:   sample_content/common_assets/robots_general/ur10/"
    "simready_isaac_usd/payloads/Physics/physx.usda\n"
    "             (search for: drive:angular:physics:stiffness)"
)


def _fix_message_no_testable_joints(n_passive, passive_names, n_mimic, mimic_names):
    # type: (int, list, int, list) -> str
    """Mode: every articulated DOF was filtered out before STA could run.

    Either every joint is passive (no drive authored) or every articulated
    joint is a mimic follower constrained by PhysxMimicJointAPI, or its
    authored position limits are degenerate (|hi - lo| < 0.01 rad). STA
    needs at least one joint it can command independently.
    """
    passive_list = ", ".join(passive_names) if passive_names else "(none)"
    mimic_list = ", ".join(mimic_names) if mimic_names else "(none)"
    return (
        "STA cannot run: no testable joints after filtering.\n"
        "\n"
        "WHAT WE FOUND:\n"
        "  - passive joints (no UsdPhysics:DriveAPI authored): %d\n"
        "      %s\n"
        "  - mimic-follower joints (PhysxMimicJointAPI -> reference): %d\n"
        "      %s\n"
        "  - articulated joints with finite, non-degenerate limits and a\n"
        "    drive authored: 0\n"
        "\n"
        "WHAT WE EXPECTED:\n"
        "  At least one revolute or prismatic joint with:\n"
        "    1. finite lower/upper position limits where |hi - lo| >= 0.01 rad,\n"
        "    2. UsdPhysics:DriveAPI applied (angular for revolute,\n"
        "       linear for prismatic), and\n"
        "    3. no PhysxMimicJointAPI making it a follower of another joint.\n"
        "\n"
        "FIX: Apply DriveAPI on the joint(s) that should be actuated, with\n"
        "non-zero stiffness and a reasonable target (typically 0 rad at\n"
        "rest pose). On the joint prim in your USD, paste:\n"
        "\n"
        '    over "<joint_prim_name>" (\n'
        '        prepend apiSchemas = ["PhysicsDriveAPI:angular",\n'
        '                              "PhysicsJointStateAPI:angular"]\n'
        "    )\n"
        "    {\n"
        "        # Position-control drive. Stiffness in N-m/rad for angular,\n"
        "        # N/m for linear. UR10 uses ~5,729,578 (1e8 deg/rad-ish);\n"
        "        # most arms want 1e4 to 1e6 N-m/rad.\n"
        "        float drive:angular:physics:stiffness = 100000.0\n"
        "        float drive:angular:physics:damping   = 10000.0\n"
        "        float drive:angular:physics:maxForce  = inf\n"
        "        float drive:angular:physics:targetPosition = 0.0\n"
        "\n"
        "        # Position limits in RADIANS for revolute, METERS for\n"
        "        # prismatic. Must be finite and span the test waypoints\n"
        "        # (default test commands +/-15 deg around 0).\n"
        "        float physics:lowerLimit = -3.14159\n"
        "        float physics:upperLimit =  3.14159\n"
        "\n"
        "        # JointStateAPI -- required for STA to read back the\n"
        "        # commanded position during the test.\n"
        "        float state:angular:physics:position = 0.0\n"
        "        float state:angular:physics:velocity = 0.0\n"
        "    }\n"
        "\n"
        "If a joint is INTENTIONALLY passive (e.g. a free-spinning caster),\n"
        "tag it with `simready:joint:passive = true` so STA skips it without\n"
        "counting it against the asset. If the asset is a pure-mimic\n"
        "gripper (every DOF is a follower), STA does not apply -- mark the\n"
        "reference joint with DriveAPI as above and let the followers be\n"
        "driven by mimic.\n"
        "\n"
        "%s"
    ) % (n_passive, passive_list, n_mimic, mimic_list, _SPEC_REFERENCE_STA)


def _fix_message_joint_position_error(joint_name, max_err_deg, tol_deg, reason_summary):
    # type: (str, float, float, str) -> str
    """Mode: one joint missed its commanded position by more than tolerance.

    This is a physics/behavior failure: the drive cannot hold the joint at
    the commanded waypoint within `position_tolerance_deg`. Almost always
    fixable by raising authored drive stiffness/damping, or by re-checking
    distal link mass/inertia. We name the joint, the measured error vs.
    tolerance, the per-target detail, and the exact attributes to edit.
    """
    return (
        "STA: Joint '%s' failed state-accuracy (max position error "
        "%.2f deg > tolerance %.2f deg).\n"
        "\n"
        "WHAT WE FOUND:\n"
        "  %s\n"
        "\n"
        "WHAT WE EXPECTED:\n"
        "  After commanding the joint through [center, +step, center,\n"
        "  -step, center], the reported position at each settle point\n"
        "  should be within %.2f deg of the commanded target. The drive\n"
        "  did not hold the joint at the commanded position.\n"
        "\n"
        "FIX (in priority order):\n"
        "  1. Raise drive stiffness on this joint. On the joint prim, edit:\n"
        "         float drive:angular:physics:stiffness  # for revolute\n"
        "         float drive:linear:physics:stiffness   # for prismatic\n"
        "     Typical values: 1e4 to 1e6 N-m/rad for ARM/SCARA revolute\n"
        "     joints. If you currently have <1000, raise by 10x first.\n"
        "  2. If the joint oscillates around the target instead of\n"
        "     settling on it, raise drive damping by 2-5x:\n"
        "         float drive:angular:physics:damping = <current * 3>\n"
        "  3. Check distal link mass/inertia. A heavy distal link makes\n"
        "     upstream joints undershoot under fixed gains. Inspect:\n"
        "         float physxRigidBody:mass\n"
        "         float3 physxRigidBody:diagonalInertia\n"
        "     on every link downstream of this joint.\n"
        "  4. Verify position limits cover the test waypoints. The test\n"
        "     commands +/-step around 0; if 0 (or +/-15 deg) is outside\n"
        "     your authored limits, the joint cannot reach the target:\n"
        "         float physics:lowerLimit\n"
        "         float physics:upperLimit\n"
        "  5. %s\n"
        "  6. %s\n"
        "\n"
        "%s"
    ) % (
        joint_name,
        max_err_deg,
        tol_deg,
        reason_summary,
        tol_deg,
        asset_fix(
            "Raise authored drive stiffness/damping on this joint until\n"
            "     it can hold the commanded position; check downstream\n"
            "     link mass and inertia if upstream joints undershoot."
        ),
        engine_note(
            "If tuning the asset does not help, capture video + logs\n"
            "     and attach the simulation parameters used (physics_fps,\n"
            "     settle_seconds, test_duration_seconds)."
        ),
        _SPEC_REFERENCE_STA,
    )


def _fix_message_phase_failure(joints_failed, joints_tested, failure_names):
    # type: (int, int, list) -> str
    """Mode: phase-level summary -- at least one joint failed STA.

    The per-joint detail already landed via ctx.warn during the run; this
    message lists the failing joints and gives the asset author the single
    most actionable next step: edit drive stiffness/damping on those
    joints, and verify gravity-disable on horizontal-axis joints didn't
    fall through.
    """
    return (
        "STA: %d/%d joints failed state accuracy.\n"
        "\n"
        "FAILING JOINTS: %s\n"
        "\n"
        "WHAT WE FOUND:\n"
        "  At least one joint could not hold its commanded position within\n"
        "  the tolerance during the 5-waypoint test. Per-joint detail (max\n"
        "  position error in degrees, failed targets) is in the warnings\n"
        "  above and recorded as `sta_max_position_error_deg` in\n"
        "  result.json.\n"
        "\n"
        "FIX (in priority order):\n"
        "  1. Raise drive stiffness/damping on the failing joint(s). On\n"
        "     each joint prim, edit:\n"
        "         float drive:angular:physics:stiffness = <larger value>\n"
        "         float drive:angular:physics:damping   = <larger value>\n"
        "     For ARM/SCARA robots FET022 disables robot gravity per-body\n"
        "     during STA, so the drive only needs to overcome link inertia;\n"
        "     a few hundred N-m/rad is usually enough. If you see large\n"
        "     steady-state errors specifically on horizontal-axis joints,\n"
        "     the per-body gravity disable may have failed -- check the\n"
        "     `articulation.disable_gravity()` and `per-body\n"
        "     disable_gravity` events from RobotHandle.initialize in the\n"
        "     log.\n"
        "  2. If the joint oscillates instead of settling, raise damping\n"
        "     by 2-5x before raising stiffness further.\n"
        "  3. Verify authored position limits include the test waypoints.\n"
        "     The test commands joints to small +/-step targets around 0\n"
        "     by default; if 0 is outside your authored range, the test\n"
        "     cannot reach it. Edit `physics:lowerLimit` /\n"
        "     `physics:upperLimit` on the joint prim.\n"
        "  4. Inspect downstream mass. A heavy distal link causes upstream\n"
        "     joints to undershoot under default gains. Re-check\n"
        "     `physxRigidBody:mass` and `physxRigidBody:diagonalInertia`\n"
        "     on each downstream link.\n"
        "  5. Increase `test_duration_seconds` (default 3.0) only if the\n"
        "     joint is slow but does reach the target eventually.\n"
        "  6. Loosen `position_tolerance_deg` (default 5.0) only when\n"
        "     intentional steady-state error is acceptable for the asset.\n"
        "\n"
        "%s"
    ) % (joints_failed, joints_tested, ", ".join(failure_names), _SPEC_REFERENCE_STA)


# ----------------------------------------------------------------------
# Defaults (mirrors v1 shared_phases.state_accuracy.get_all_parameter_defaults)
# ----------------------------------------------------------------------


def get_defaults():
    # type: () -> Dict[str, Any]
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
    # type: (float, float, float, float) -> List[float]
    """Return [center, +step, center, -step, center] target sequence.

    step = min(max_step_deg, range * step_range_fraction); clamped inside limits
    with a 0.05 rad (~2.86 deg) safety margin from each end (matches v1).
    """
    center = 0.0
    rng = float(hi) - float(lo)
    step_size = min(math.radians(float(max_step_deg)), rng * float(step_range_fraction))
    pos_a = max(lo + 0.05, min(hi - 0.05, center + step_size))
    pos_b = max(lo + 0.05, min(hi - 0.05, center - step_size))
    return [center, pos_a, center, pos_b, center]


def classify_position_error(reported_pos, target, tolerance_rad):
    # type: (float, float, float) -> Tuple[bool, Optional[str], float]
    """Pass = finite reading AND |target - reported| <= tolerance_rad.

    Returns (ok, reason_or_None, abs_error). Velocity/consistency are NOT
    checked here -- v1 logs those as warnings, not joint failures.
    """
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
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
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


# ----------------------------------------------------------------------
# Async runner (Kit-only, not unit-tested)
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
):
    """Drive the joint toward target for motion_frames; capture frames.

    The commanded position is RAMPED from the joint's start value to the target
    over the motion window (smoothstep) -- a paced trajectory, not a single step
    command -- so an uncapped joint does not whip toward the target. Other joints
    are held at their start pose. (FRS / JIK drive the robot the same way.)
    """
    HB_EVERY = 40
    start_positions = robot.get_joint_positions().copy()
    start_val = float(start_positions[jinfo["index"]])
    delta = float(target) - start_val
    ramp_frames = max(1, int(motion_frames))

    # Early-exit thresholds: once the joint is within a coarse-grained
    # band of the target AND nearly at rest, the settle phase will tidy
    # up the rest. Keeps the motion phase from spending its full budget
    # idling after the joint has clearly arrived.
    motion_pos_tol = 0.05  # rad (~ 2.86 deg)
    motion_vel_tol = 0.05  # rad/s
    bbox_msgs = []
    for frame in range(motion_frames):
        eased = smoothstep((frame + 1) / float(ramp_frames))
        command = start_positions.copy()
        command[jinfo["index"]] = start_val + delta * eased
        robot.set_joint_position_targets(command)
        await ctx.step_one()
        if frame % 20 == 0:
            current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
            msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
            if msg:
                bbox_msgs.append(msg)
        if frame % capture_interval == 0:
            frame_path = await ctx.capture_frame(stabilize_frames=0, label="state_accuracy_%03d_%04d" % (jnum, frame))
            if frame_path:
                capture_frames.append(frame_path)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)
        if frame % HB_EVERY == 0:
            ctx.step("STA j=%s motion frame=%d/%d" % (jinfo["name"], frame, motion_frames))

        # Once the joint is roughly at target and slow, exit motion phase
        # early -- the settle phase that follows can finish convergence.
        pos = float(robot.get_joint_positions()[jinfo["index"]])
        vel = float(robot.get_joint_velocities()[jinfo["index"]])
        if abs(pos - target) < motion_pos_tol and abs(vel) < motion_vel_tol:
            break
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
        pos = float(robot.get_joint_positions()[jinfo["index"]])
        vel = float(robot.get_joint_velocities()[jinfo["index"]])
        if abs(pos - target) <= pos_tol and abs(vel) <= vel_tol:
            consecutive_settled += 1
        else:
            consecutive_settled = 0
        if frame % capture_interval == 0:
            frame_path = await ctx.capture_frame(stabilize_frames=0, label="%s_settle_%04d" % (base_frame_label, frame))
            if frame_path:
                capture_frames.append(frame_path)
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
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run the STA phase. Mutates ctx via skip / add_metric / warn / fail."""
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

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
    follower_dof_indices = set(int(i) for i in scene_info.get("mimic_follower_indices") or [])
    passive_indices = set(int(i) for i in scene_info.get("passive_joint_indices") or [])
    loop_indices = set(int(i) for i in scene_info.get("loop_joint_indices") or [])

    joints = []
    skipped_passive = []
    skipped_mimic = []
    skipped_loop = []
    for i, name in enumerate(dof_names):
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if not (math.isfinite(lo) and math.isfinite(hi) and abs(hi - lo) >= 0.01):
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

    ctx.step("Settling robot before STA")
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)

    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    per_joint_results = []

    for jnum, jinfo in enumerate(joints, start=1):
        ctx.step("STA joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))

        positions = compute_test_positions(
            jinfo["lower"],
            jinfo["upper"],
            max_step_deg=max_step_deg,
            step_range_fraction=step_range_fraction,
        )

        test_frames = max(20, int(test_duration * physics_fps))
        settle_frames_per_target = max(30, int(0.5 * physics_fps))
        motion_frames_per_target = max(30, (test_frames - len(positions) * settle_frames_per_target) // len(positions))

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
            )
            final_pos = float(robot.get_joint_positions()[jinfo["index"]])
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

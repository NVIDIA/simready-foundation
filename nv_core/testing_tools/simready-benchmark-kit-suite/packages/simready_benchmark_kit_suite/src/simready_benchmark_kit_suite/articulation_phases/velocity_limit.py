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
"""VEL phase: verify joints respect authored max velocities.
V1 reference: shared_phases/velocity_limit.py.
"""
import math

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.error_utils import (
    asset_fix,
    engine_note,
)
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready_benchmark_kit_suite.articulation_phases.motion_utils import (
    merge_velocity_limits,
    resolve_usd_max_velocities,
)

# --------------------------------------------------------------------
# Fix-message helpers
# --------------------------------------------------------------------
#
# Library philosophy: when
# a test cannot run, or fails, the message landing in result.json must
# teach the asset author EXACTLY how to fix the asset -- the headline,
# what we found vs. expected, which prim/attribute to edit, a paste-ready
# USDA snippet, and references to the spec + a working real example.

_VEL_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:    nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_driven_joints/requirements/physics-joint-max-velocity.md\n"
    "           (DJ.005 -- physxJoint:maxJointVelocity > 0 required on\n"
    "            every revolute/prismatic PhysX driven joint)\n"
    "  Example: sample_content/common_assets/robots_general/ur10/"
    "simready_isaac_usd/payloads/Physics/physx.usda\n"
    "           (search for: float physxJoint:maxJointVelocity = 120)"
)


def _fix_message_no_velocity_limits():
    # type: () -> str
    """Skip-time message for assets with no authored joint velocity limits."""
    return (
        "VEL: No joints carry an authored velocity limit; the velocity-"
        "limit test cannot run.\n"
        "\n"
        "What the test looked for (EITHER authoring form is accepted):\n"
        "  - `physxJoint:maxJointVelocity` on a PhysxJointAPI, OR\n"
        "  - `physxDrivePerformanceEnvelope:angular:maxActuatorVelocity`\n"
        "    (or `:linear:`) on a PhysxDrivePerformanceEnvelopeAPI,\n"
        "  set to a positive finite value on each driven (revolute /\n"
        "  prismatic) joint.\n"
        "  - At least one such joint that is NOT a passive or mimic-\n"
        "    follower joint (those are excluded -- their velocity is not\n"
        "    independently commandable).\n"
        "\n"
        "  UNITS: USD authors these in DEGREES/second for revolute joints\n"
        "  and distance/second for prismatic joints. (PhysX consumes\n"
        "  radians/second internally; the test converts deg->rad for you.)\n"
        "\n"
        "What was found:\n"
        "  - No joint carried either authored velocity limit, or every\n"
        "    joint that did is passive / mimic-followed.\n"
        "\n"
        "FIX: On every driven revolute/prismatic joint, author a positive\n"
        "finite velocity limit matching the mechanism's datasheet rated\n"
        "speed, in DEGREES/second (revolute) or distance/second\n"
        "(prismatic).\n"
        "\n"
        "Paste-ready USDA -- adjust the value to your joint's datasheet:\n"
        "\n"
        '    def PhysicsRevoluteJoint "shoulder_pan_joint" (\n'
        '        prepend apiSchemas = ["PhysicsDriveAPI:angular",\n'
        '                              "PhysxJointAPI"]\n'
        "    )\n"
        "    {\n"
        "        rel physics:body0 = </base_link>\n"
        "        rel physics:body1 = </shoulder_link>\n"
        '        uniform token physics:axis = "Z"\n'
        "        # Rated max speed in DEGREES/s (UR10 shoulder = 120 deg/s\n"
        "        # = ~2.09 rad/s).\n"
        "        float physxJoint:maxJointVelocity = 120\n"
        "    }\n"
        "\n"
        '    def PhysicsPrismaticJoint "slide_joint" (\n'
        '        prepend apiSchemas = ["PhysicsDriveAPI:linear",\n'
        '                              "PhysxJointAPI"]\n'
        "    )\n"
        "    {\n"
        "        rel physics:body0 = </base_link>\n"
        "        rel physics:body1 = </slide_link>\n"
        '        uniform token physics:axis = "X"\n'
        "        # Rated max speed, distance/s.\n"
        "        float physxJoint:maxJointVelocity = 1.0\n"
        "    }\n"
        "\n"
        "Notes:\n"
        "  - The same limit can also (or instead) be authored on the\n"
        "    actuator side as\n"
        "    `physxDrivePerformanceEnvelope:angular:maxActuatorVelocity`\n"
        "    (or `:linear:`), also in DEGREES/second for revolute; the\n"
        "    test takes the MIN of the two when both are present, so\n"
        "    author both consistently.\n"
        "  - If every joint in the articulation is passive or a mimic\n"
        "    follower, this phase has nothing to test -- add a velocity\n"
        "    limit on the master joint that drives the followers.\n"
        "\n" + _VEL_SPEC_REFERENCE
    )


def _fix_message_violations(failed_count, total, failed_names, failed_details):
    # type: (int, int, str, str) -> str
    """Fail-time message for joints that exceeded their authored limit."""
    return (
        "VEL: {n}/{total} joint(s) exceeded their authored velocity "
        "limit: {names}.\n"
        "\n"
        "What the test did:\n"
        "  - Commanded each joint to the opposite end of its position\n"
        "    range (with a 5% margin) and stepped physics for\n"
        "    `test_duration_seconds` (default 2s) at "
        "`physics_fps` (default 240).\n"
        "  - Compared the per-frame |joint velocity| (rad/s) against the\n"
        "    authored velocity limit, converted from its USD units\n"
        "    (degrees/s for revolute, distance/s for prismatic) to rad/s,\n"
        "    allowing a `tolerance_percent` overshoot (default 5%).\n"
        "\n"
        "Per-joint peaks:\n"
        "{details}\n"
        "\n"
        "FIX -- decide which side is wrong and edit the asset:\n"
        "\n"
        "(a) If the joint legitimately needs to move that fast, raise\n"
        "    the authored limit on the joint prim to match the\n"
        "    datasheet rated speed:\n"
        "\n"
        "        over </Robot/joints/{first_name}>:\n"
        "        {{\n"
        "            # New value >= observed peak, authored in DEGREES/s\n"
        "            # (revolute) or distance/s (prismatic). The peak\n"
        "            # reported above is rad/s -- multiply by 180/pi to\n"
        "            # get deg/s. Keep within physical limits.\n"
        "            float physxJoint:maxJointVelocity = <new_value>\n"
        "        }}\n"
        "\n"
        "(b) If the limit is correct and the drive is overshooting,\n"
        "    retune the PD controller on the joint's drive so it\n"
        "    cannot accelerate past the cap when chasing the target:\n"
        "      - LOWER `drive:angular:physics:stiffness` (or\n"
        "        `drive:linear:physics:stiffness`).\n"
        "      - RAISE `drive:*:physics:damping`.\n"
        "      - LOWER `drive:*:physics:maxForce` -- excess available\n"
        "        torque is what lets the joint blow past the cap.\n"
        "    A reasonable starting point: damping ~= 2 * sqrt(stiffness\n"
        "    * effective_inertia); then iterate.\n"
        "\n"
        "(c) If both the limit and the drive are correct and PhysX is\n"
        "    still overshooting by a small margin, bump\n"
        "    `tolerance_percent` in the test config -- but only as a\n"
        "    last resort; (a) and (b) are the right fix.\n"
        "\n"
        "Per-joint peak velocities are also recorded as warnings above\n"
        "and counted in `vel_joints_failed` in result.json.\n"
        "\n" + _VEL_SPEC_REFERENCE
    ).format(
        n=failed_count,
        total=total,
        names=failed_names,
        details=failed_details,
        first_name=(failed_names.split(",")[0].strip() or "joint_name"),
    )


# --------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------


def get_defaults():
    # type: () -> Dict[str, Any]
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
        # joint is treated as "at rest" and capture_frame is skipped for
        # the remaining test frames. Physics stepping continues so the
        # bbox-explode check and peak-velocity measurement stay intact.
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
    center = (lo + hi) / 2.0
    margin = (hi - lo) * 0.05
    if current_pos <= center:
        return float(hi - margin)
    return float(lo + margin)


def find_joints_with_velocity_limits(robot, usd_vels=None, exclude_indices=None):
    # type: (Any, Optional[np.ndarray], Optional[set]) -> List[Dict[str, Any]]
    """Return per-joint records for joints with a positive finite velocity limit.

    robot must expose: dof_names, dof_count,
        get_joint_position_limits() -> (lower, upper),
        get_joint_velocity_limits() -> np.ndarray

    ``exclude_indices`` (optional): set of DOF indices to skip — typically the
    union of passive and mimic-follower joints, supplied by the phase runner
    so the velocity-limit test doesn't waste cycles commanding joints whose
    velocity is constrained by the master via ``PhysxMimicJointAPI`` or that
    have no drive at all.
    """
    excl = set(int(i) for i in (exclude_indices or set()))
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    dof_vels = robot.get_joint_velocity_limits()
    merged = merge_velocity_limits(dof_vels, usd_vels, use_min_when_both=True)

    results = []
    for i, name in enumerate(dof_names):
        if i in excl:
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if not (math.isfinite(lo) and math.isfinite(hi)):
            continue

        if merged is None or i >= len(merged):
            continue
        max_vel = float(merged[i])
        if not math.isfinite(max_vel) or max_vel <= 0:
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
    # type: (List[float], float, float) -> Tuple[List[Tuple[int, float]], float]
    """Return (violations, peak_velocity). Drops the first 5 samples as startup."""
    if not velocities:
        return ([], 0.0)
    filtered = velocities[5:] if len(velocities) > 10 else velocities
    if not filtered:
        filtered = velocities
    peak = float(max(filtered))
    max_allowed = max_velocity * (1.0 + tolerance_percent)
    violations = [(i, float(v)) for i, v in enumerate(filtered) if v > max_allowed]
    return (violations, peak)


# --------------------------------------------------------------------
# Async runner (Kit-only, not unit-tested)
# --------------------------------------------------------------------


async def run_velocity_limit(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run the VEL phase. Mutates ctx via skip / add_metric / warn / fail."""
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

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
    )
    # Exclude passive joints (no drive) and mimic-followers (constrained by
    # reference via PhysxMimicJointAPI) — neither responds to a velocity
    # command independently. Surfaced from scene_info (computed once at
    # setup_robot_test_scene). For arms this set is empty.
    passive_indices = set(int(i) for i in scene_info.get("passive_joint_indices") or [])
    follower_indices = set(int(i) for i in scene_info.get("mimic_follower_indices") or [])
    loop_indices = set(int(i) for i in scene_info.get("loop_joint_indices") or [])
    excluded = passive_indices | follower_indices | loop_indices
    if excluded:
        ctx.add_metric("vel_joints_skipped_passive", len(passive_indices))
        ctx.add_metric("vel_joints_skipped_mimic_follower", len(follower_indices))
        ctx.add_metric("vel_joints_skipped_loop", len(loop_indices))

    joints = find_joints_with_velocity_limits(robot, usd_vels=usd_vels, exclude_indices=excluded)
    ctx.add_metric("vel_joints_with_limits", len(joints))

    if not joints:
        ctx.skip(_fix_message_no_velocity_limits())
        return

    # Push USD limits into tensor view
    merged_limits = np.array([float("nan")] * robot.dof_count, dtype=np.float64)
    for j in joints:
        merged_limits[j["index"]] = j["max_velocity"]
    robot.apply_velocity_limits_to_tensor_view(merged_limits)

    # Settle
    ctx.step("Settling robot before velocity tests")
    await ctx.physics_steps(int(settle_seconds * physics_fps))

    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)

    # Per-joint test
    joints_passed = 0
    joints_failed = 0
    failed_names = []
    failed_details = []  # human-readable lines for the aggregate fail msg
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))

    # Heartbeat cadence to avoid the 60s watchdog SIGKILL on silent but
    # healthy sweeps. See parallel comment in full_range_sweep.py.
    HB_EVERY = 40

    for jnum, jinfo in enumerate(joints, start=1):
        ctx.step("VEL joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))

        current_positions = robot.get_joint_positions()
        cur = float(current_positions[jinfo["index"]])
        target = compute_velocity_test_target(cur, jinfo["lower"], jinfo["upper"])

        targets = current_positions.copy()
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
            v = float(robot.get_joint_velocities()[jinfo["index"]])
            velocities_observed.append(abs(v))

            if frame % 20 == 0:
                current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
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
                "VEL: Joint '%s' exceeded velocity limit: "
                "peak=%.3f > max=%.3f (+%.1f%% overshoot, source=%s). "
                "%s %s"
                % (
                    jinfo["name"],
                    peak,
                    jinfo["max_velocity"],
                    overshoot_pct,
                    jinfo["max_velocity_source"],
                    asset_fix(
                        "Raise physxJoint:maxJointVelocity on this joint "
                        "if the speed is legitimate, or lower drive "
                        "stiffness / raise damping / lower maxForce so "
                        "the PD controller stops overshooting the cap."
                    ),
                    engine_note(
                        "If the limit and drive look correct, capture " "video + logs and check `tolerance_percent`."
                    ),
                )
            )
            for err in joint_errors:
                ctx.warn(err)
            ctx.warn(msg)
        else:
            joints_passed += 1
            ctx.log(
                "VEL: Joint '%s' within limit (peak=%.2f <= max=%.2f rad/s)"
                % (jinfo["name"], peak, jinfo["max_velocity"])
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

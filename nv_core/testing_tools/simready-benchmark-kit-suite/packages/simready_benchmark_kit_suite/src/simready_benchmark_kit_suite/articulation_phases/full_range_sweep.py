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
"""FRS phase: drive every joint through max -> min -> zero.
V1 reference: shared_phases/full_range_sweep.py.
"""
import math

from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)

# --------------------------------------------------------------------
# Fix-message helpers
# --------------------------------------------------------------------
#
# Library philosophy: when
# a test cannot run, or fails on an asset, the message landing in
# result.json / the HTML report must teach the asset author EXACTLY how
# to fix the asset -- a headline, what we found vs. expected, which
# prim/attribute to edit, a paste-ready USDA snippet, and references to
# the spec + a working real-asset example.

_FRS_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Feature:   nv_core/sr_specs/docs/features/FET_022-driven_joints.md\n"
    "  Drive:     nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_driven_joints/requirements/\n"
    "             physics-drive-and-joint-state.md (DJ.001 -- maxForce > 0)\n"
    "             drive-joint-value-reasonable.md  (DJ.006 -- stiffness/"
    "damping ranges)\n"
    "             physics-joint-max-velocity.md    (DJ.005 -- maxJointVelocity"
    " > 0)\n"
    "  Joints:    nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_joints/requirements/\n"
    "             joint-body-target-exists.md\n"
    "  Example:   sample_content/common_assets/robots_general/Franka/"
    "FrankaResearch3/\n"
    "             simready_isaac_usd/FrankaResearch3.usda\n"
    "             (search for: physics:lowerLimit, physics:upperLimit,\n"
    "              drive:angular:physics:stiffness)"
)


def _fix_message_no_joints_with_limits(passive_count, total_dof):
    # type: (int, int) -> str
    return (
        "FRS: No joints have valid position limits; the full-range sweep"
        " test cannot run.\n"
        "  Total DOF on articulation:      {total}\n"
        "  Passive joints excluded:        {passive}\n"
        "\n"
        "WHAT THE TEST NEEDS: at least one active (non-passive) revolute or"
        " prismatic\n"
        "joint that declares finite, distinct position limits with"
        " (upper - lower) > 1e-3.\n"
        "Joints with missing, infinite, equal, or zero-width limits are"
        " silently skipped --\n"
        "if EVERY joint is in that state, FRS has nothing to sweep.\n"
        "\n"
        "FIX: open each driven joint prim under the articulation and author"
        " physics:lowerLimit\n"
        "and physics:upperLimit (radians for revolute, meters for"
        " prismatic). Units must\n"
        "match the joint type. Example -- paste/edit on a revolute joint:\n"
        "\n"
        '    def PhysicsRevoluteJoint "joint_1" (\n'
        '        prepend apiSchemas = ["PhysxJointAPI",'
        ' "PhysicsDriveAPI:angular", "PhysicsJointStateAPI:angular"]\n'
        "    )\n"
        "    {{\n"
        "        rel physics:body0 = </link_0>\n"
        "        rel physics:body1 = </link_1>\n"
        '        uniform token physics:axis = "Y"\n'
        "\n"
        "        # Required for FRS: finite, distinct limits with"
        " (upper - lower) > 1e-3.\n"
        "        # Typical revolute arm joints (radians): +/- 2.9 rad"
        " (~+/- 165 deg)\n"
        "        # Typical prismatic gripper finger (meters): 0.0 .. 0.04\n"
        "        float physics:lowerLimit = -2.8973\n"
        "        float physics:upperLimit =  2.8973\n"
        "\n"
        "        # FRS only sweeps joints with a working drive (so the"
        " commanded\n"
        "        # target actually moves the link). Author drive gains too:\n"
        "        float drive:angular:physics:stiffness = 1000.0\n"
        "        float drive:angular:physics:damping   = 100.0\n"
        "        float drive:angular:physics:maxForce  = 87.0\n"
        "        float physxJoint:maxJointVelocity     = 2.6\n"
        "    }}\n"
        "\n"
        "If every joint on this articulation is genuinely passive (e.g., a"
        " static fixture\n"
        "or a passive mimic-follower chain), FRS is not applicable -- exclude"
        " the asset from\n"
        "the FRS profile in your test plan.\n"
        "\n"
        "{ref}"
    ).format(total=total_dof, passive=passive_count, ref=_FRS_SPEC_REFERENCE)


def _fix_message_bbox_explode(joint_name, seg_name, bbox_msg):
    # type: (str, str, str) -> str
    return (
        "FRS: Joint '{name}' (segment {seg}): bounding-box explode while"
        " sweeping.\n"
        "  Engine observation: {bbox}\n"
        "\n"
        "WHAT THIS MEANS: while FRS commanded joint '{name}' through its"
        " authored range,\n"
        "the articulation's world-aligned bounding box grew past the safety"
        " ratio -- a sign\n"
        "that a link flew off, the integrator diverged, or a constraint"
        " released.\n"
        "\n"
        "WHAT TO INSPECT (in priority order):\n"
        "  1. physxRigidBody:mass and physxRigidBody:diagonalInertia on the"
        " links downstream\n"
        "     of joint '{name}'. Mass < 1e-3 kg or near-zero inertia diagonals"
        " amplify drive\n"
        "     impulses and produce runaway motion. Typical arm-link mass:"
        " 0.1 - 10 kg.\n"
        "  2. drive:<linear|angular>:physics:stiffness on '{name}' -- a value"
        " above ~50000\n"
        "     against a low-mass link blows the integrator at 240 Hz."
        " DJ.006 recommends\n"
        "     stiffness in 100 - 10000, damping in 1 - 100.\n"
        "  3. physxJoint:maxJointVelocity on '{name}'. Unbounded (missing)"
        " or huge values\n"
        "     let one frame's overshoot become catastrophic. DJ.005 requires"
        " a positive,\n"
        "     datasheet-grounded value (radians/s for revolute, m/s for"
        " prismatic).\n"
        "  4. physics:lowerLimit / physics:upperLimit. If the authored range"
        " is huge (e.g.\n"
        "     +/- 10 rad on a wrist that physically rotates +/- 2 rad),"
        " links collide with\n"
        "     each other or pull free of the chain. Clamp to the real"
        " mechanical envelope.\n"
        "  5. Articulation root pin. If the base is unpinned and gravity is"
        " on (or the\n"
        "     per-body gravity disable failed), the whole chain accelerates"
        " on the first\n"
        "     drive impulse. Check that the root link carries the expected"
        " PhysicsFixedJoint\n"
        "     to /World or that FET022 gravity-disable applied.\n"
        "\n"
        "{ref}"
    ).format(name=joint_name, seg=seg_name, bbox=bbox_msg, ref=_FRS_SPEC_REFERENCE)


def _fix_message_rest_violation(joint_name, seg_name, seg_end, violations, total):
    # type: (str, str, float, int, int) -> str
    return (
        "FRS: Joint '{name}' failed rest check at segment '{seg}' (commanded"
        " target = {tgt:.3f}).\n"
        "  Rest-frame violations: {viol}/{total} (more than half of the"
        " pause window had\n"
        "  position error > rest_tolerance from the commanded target).\n"
        "\n"
        "WHAT THIS MEANS: after FRS drove joint '{name}' to {tgt:.3f}, the"
        " drive could not\n"
        "hold the link steady at that target during the pause window -- the"
        " link is\n"
        "oscillating, sagging, or drifting under residual torques.\n"
        "\n"
        "WHAT TO INSPECT (in priority order):\n"
        "  1. drive:<linear|angular>:physics:stiffness on the joint prim for"
        " '{name}'.\n"
        "     Too low -> the link sags away from the commanded target."
        " Typical good range:\n"
        "     1000 - 10000 (DJ.006). Bump it up and re-run.\n"
        "  2. drive:<linear|angular>:physics:damping on the same joint."
        " Under-damped drives\n"
        "     ring at the commanded position. Typical good range: 10 - 100"
        " (DJ.006). Aim\n"
        "     for damping ~= 2 * sqrt(stiffness * effective_inertia) for"
        " critical damping.\n"
        "  3. drive:<linear|angular>:physics:maxForce. If the holding torque"
        " is below the\n"
        "     gravitational + inertial load on the link, no amount of"
        " stiffness will hold\n"
        "     position. Typical revolute arm joints: 50 - 300 N*m"
        " (shoulder > elbow > wrist).\n"
        "  4. Whether '{name}' should be a mimic-follower (its motion is"
        " coupled to another\n"
        "     joint via PhysicsMimicJointAPI rather than independently"
        " driven). Mimic-followed\n"
        "     joints have stiffness = damping = 0 and never hold their own"
        " target; if FRS\n"
        "     is sweeping them, scene_info['mimic_follower_indices'] is wrong"
        " (passive_joints\n"
        "     detector did not see the mimic APIs).\n"
        "  5. Config knob: increase 'pause_at_limits_seconds' in the FRS"
        " config if the\n"
        "     joint is settling correctly but the rest window is too short"
        " to observe it.\n"
        "  6. Config knob: set 'rest_check_fatal' = False (the default) if"
        " minor oscillation\n"
        "     at extremes is acceptable for this asset. Only set True when"
        " strict steady-\n"
        "     state hold is a real requirement.\n"
        "\n"
        "{ref}"
    ).format(
        name=joint_name,
        seg=seg_name,
        tgt=seg_end,
        viol=violations,
        total=total,
        ref=_FRS_SPEC_REFERENCE,
    )


def _fix_message_zero_return(joint_name, observed, target, tolerance):
    # type: (str, float, float, float) -> str
    return (
        "FRS: Joint '{name}' failed zero-return: end-of-sweep position"
        " {obs:.4f} differs\n"
        "from the commanded zero target {tgt:.4f} by more than the"
        " configured tolerance\n"
        "({tol:.4f}).\n"
        "\n"
        "WHAT THIS MEANS: after the to_max -> to_min -> to_zero sweep, the"
        " drive could not\n"
        "return joint '{name}' to its zero (rest) position within tolerance."
        " Either the\n"
        "drive is too weak to settle, the joint is overshooting and never"
        " resting, or the\n"
        "joint mechanically cannot reach zero (e.g. zero falls outside the"
        " authored limits).\n"
        "\n"
        "WHAT TO INSPECT (in priority order):\n"
        "  1. drive:<linear|angular>:physics:stiffness and damping on the"
        " joint prim for\n"
        "     '{name}'. Under-stiff drives leave a steady-state offset"
        " under gravity or\n"
        "     residual load; under-damped drives ring past zero. DJ.006"
        " recommends\n"
        "     stiffness in 100 - 10000 and damping in 1 - 100. Aim for"
        " damping ~=\n"
        "     2 * sqrt(stiffness * effective_inertia) (critical damping).\n"
        "  2. drive:<linear|angular>:physics:maxForce. If the holding"
        " torque is below the\n"
        "     gravitational load at zero, the drive saturates and leaves a"
        " bias. Typical\n"
        "     revolute arm joints: 50 - 300 N*m.\n"
        "  3. physics:lowerLimit / physics:upperLimit on '{name}'. FRS"
        " commands zero only\n"
        "     when 0.0 lies inside [lower, upper]; otherwise it commands the"
        " nearest in-range\n"
        "     target. If the authored limits do not bracket the joint's"
        " natural rest pose,\n"
        "     re-author them to match the mechanism (radians for revolute,"
        " meters for\n"
        "     prismatic).\n"
        "  4. Joint type vs. axis sign convention. If the asset axes were"
        " flipped between\n"
        "     authoring and simulation, the commanded 'zero' is a non-rest"
        " configuration.\n"
        "     Verify physics:axis and the body0/body1 ordering against the"
        " mechanism CAD.\n"
        "  5. Config knob: relax 'zero_return_tolerance' in the FRS config"
        " ONLY if the\n"
        "     joint's natural deadband is wider than {tol:.4f} (e.g. a"
        " backlash-heavy\n"
        "     mechanism). Default 0.01 is appropriate for tuned drives.\n"
        "\n"
        "{ref}"
    ).format(
        name=joint_name,
        obs=observed,
        tgt=target,
        tol=tolerance,
        ref=_FRS_SPEC_REFERENCE,
    )


def _fix_message_aggregate(failed, total, failure_names):
    # type: (int, int, list) -> str
    return (
        "FRS: {failed}/{total} joints failed the full-range sweep.\n"
        "  Failing joints: {names}\n"
        "\n"
        "Each failing joint has one or more per-joint warnings above with"
        " its specific\n"
        "failure mode (bbox explode, rest violation at a commanded target,"
        " or zero-return\n"
        "error) and a four-to-six-item inspection checklist for the drive"
        " gains, drive\n"
        "maxForce, joint limits, and mimic-status of that joint. Walk those"
        " first.\n"
        "\n"
        "QUICK TRIAGE:\n"
        "  - If most or all joints fail with rest-violation or zero-return"
        " errors: the\n"
        "    asset-wide drive tuning is off. Most likely cause is uniformly"
        " low stiffness\n"
        "    or damping authored across all driven joints, or a"
        " configuration mistake\n"
        "    (e.g. drive:linear gains on a revolute joint, or vice versa)."
        " Spot-check\n"
        "    drive:<axis>:physics:stiffness / damping / maxForce on every"
        " driven joint\n"
        "    prim. DJ.006 ranges: stiffness 100-10000, damping 1-100.\n"
        "  - If exactly one or two joints fail: those joints' drive gains"
        " or limits are\n"
        "    the most likely culprit. Edit the joint prims in USD against"
        " the per-joint\n"
        "    warnings above.\n"
        "  - If failures cite bbox explode: the test detected runaway"
        " motion, not a tuning\n"
        "    issue alone. Check link mass / inertia, articulation root"
        " pinning, and that\n"
        "    FET022 per-body gravity disable applied (look for"
        " 'articulation.disable_gravity'\n"
        "    in RobotHandle.initialize logs).\n"
        "  - If failures cite zero-return only (no rest, no bbox): drives"
        " are likely under-\n"
        "    stiff or under-damped. Bump stiffness/damping by 2x and re-run"
        " before chasing\n"
        "    deeper authoring issues.\n"
        "\n"
        "Configuration overrides (in the FRS phase config) when failures"
        " reflect test\n"
        "policy rather than authoring:\n"
        "  - 'pause_at_limits_seconds' (default 0.15): widen the rest"
        " window for slow-\n"
        "    settling drives.\n"
        "  - 'rest_check_fatal' (default False): if rest-check warnings are"
        " acceptable, they\n"
        "    will not contribute to fail count; only oscillation set fatal"
        " counts here.\n"
        "  - 'zero_return_tolerance' (default 0.01): relax only for"
        " backlash-heavy hardware.\n"
        "\n"
        "{ref}"
    ).format(
        failed=failed,
        total=total,
        names=", ".join(failure_names),
        ref=_FRS_SPEC_REFERENCE,
    )


# --------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------


def get_defaults():
    # type: () -> Dict[str, Any]
    return {
        "settle_seconds": 1.0,
        "sweep_margin_ratio": 0.10,
        "interpolation_profile": "smoothstep",
        # sweep_speed_scale sets simulation-seconds-per-segment as
        # 1.0/speed_scale. v1.6 used 0.5 (2 s per segment); timing
        # analysis showed 3 segments x 6 joints x ~2 s sim time = the
        # dominant share of FRS wall-clock. 0.8 cuts that to 1.25 s per
        # segment (~1.6x faster) without changing what the test checks;
        # the smoothstep-driven PD target simply steps faster.
        "sweep_speed_scale": 0.8,
        # pause_at_limits was 0.5s; dropped to 0.15s after timing analysis
        # showed the three per-joint pauses (x6 joints) produced dead
        # time with no movement to observe.
        "pause_at_limits_seconds": 0.15,
        "zero_return_tolerance": 0.01,
        "limit_tolerance": 0.02,
        "bbox_explode_ratio": 10.0,
        "rest_check_enabled": True,
        "rest_tolerance": 0.1,
        "rest_check_fatal": False,
        "max_sweep_range": 2 * 3.14159,
        "physics_fps": 240.0,
        # 8 fps still produces a smooth-enough video and halves capture
        # wall time vs 15 fps. FRS's per-segment sweep is 1.25 s at the
        # tuned speed_scale; 8 fps yields ~10 frames/segment, plenty for
        # visual review. Earlier 15 fps default was the dominant cost.
        "capture_fps": 8,
    }


# --------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------


def interpolate_profile(profile, t):
    # type: (str, float) -> float
    """Evaluate the named interpolation profile at t in [0, 1]."""
    t = max(0.0, min(1.0, float(t)))
    name = str(profile).lower()
    if name == "smoothstep":
        return t * t * (3.0 - 2.0 * t)
    if name == "smootherstep":
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    if name == "trapezoidal":
        if t < 0.25:
            return t * 2.0
        if t < 0.75:
            return 0.5
        return 0.5 + (t - 0.75) * 2.0
    return t


def select_all_joints_with_limits(robot, excluded_indices):
    # type: (Any, FrozenSet[int]) -> List[Tuple[int, str]]
    """Return [(dof_idx, name), ...] for joints with finite range > 1e-3.

    ``excluded_indices`` holds joints that cannot be swept independently:
    passive joints, mimic-followers, and closed-loop / parallel-linkage joints.
    """
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    out = []
    for i, name in enumerate(dof_names):
        if i in excluded_indices:
            continue
        if i >= len(lowers) or i >= len(uppers):
            continue
        lo = float(lowers[i])
        hi = float(uppers[i])
        if not (math.isfinite(lo) and math.isfinite(hi)):
            continue
        if (hi - lo) <= 1e-3:
            continue
        out.append((i, str(name)))
    return out


def compute_sweep_parameters(
    lo,
    hi,
    margin_ratio,
    max_sweep_range,
    speed_scale,
    pause_seconds,
    physics_fps,
    joint_name,
):
    # type: (float, float, float, float, float, float, float, str) -> Dict[str, Any]
    """Compute sweep targets and frame counts for one joint."""
    effective_lo = lo
    effective_hi = hi
    full_range = hi - lo
    if max_sweep_range > 0 and full_range > max_sweep_range:
        center = 0.0
        if center < lo:
            center = lo + max_sweep_range / 2.0
        elif center > hi:
            center = hi - max_sweep_range / 2.0
        effective_lo = center - max_sweep_range / 2.0
        effective_hi = center + max_sweep_range / 2.0

    margin = abs(effective_hi - effective_lo) * margin_ratio
    min_target = effective_lo + margin
    max_target = effective_hi - margin
    zero_target = 0.0
    if zero_target < lo:
        zero_target = lo + margin
    elif zero_target > hi:
        zero_target = hi - margin

    base_segment_seconds = 1.0 / max(0.1, speed_scale)
    seg_frames = max(2, int(base_segment_seconds * physics_fps))
    pause_frames = max(1, int(pause_seconds * physics_fps))

    return {
        "min_target": min_target,
        "max_target": max_target,
        "zero_target": zero_target,
        "seg_frames": seg_frames,
        "pause_frames": pause_frames,
    }


def build_sweep_segments(q_start, params):
    # type: (float, Dict[str, Any]) -> List[Tuple[float, float, str]]
    """Return [(start, end, name), ...] for the 3-phase sweep."""
    return [
        (q_start, params["max_target"], "to_max"),
        (params["max_target"], params["min_target"], "to_min"),
        (params["min_target"], params["zero_target"], "to_zero"),
    ]


# --------------------------------------------------------------------
# Async runner (Kit-only)
# --------------------------------------------------------------------


async def run_full_range_sweep(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run the FRS phase. Mutates ctx."""
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    passive_joint_indices = scene_info.get("passive_joint_indices", frozenset())
    passive_dof_names = scene_info.get("passive_dof_names", [])
    follower_indices = scene_info.get("mimic_follower_indices") or []
    loop_indices = scene_info.get("loop_joint_indices") or []
    loop_dof_names = scene_info.get("loop_joint_names") or []
    excluded_indices = frozenset(
        int(i) for i in list(passive_joint_indices) + list(follower_indices) + list(loop_indices)
    )

    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 8))
    settle_seconds = float(config.get("settle_seconds", 1.0))
    margin_ratio = float(config.get("sweep_margin_ratio", 0.10))
    profile = str(config.get("interpolation_profile", "smoothstep"))
    speed_scale = float(config.get("sweep_speed_scale", 0.5))
    pause_seconds = float(config.get("pause_at_limits_seconds", 0.5))
    zero_tolerance = float(config.get("zero_return_tolerance", 0.01))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))
    rest_enabled = bool(config.get("rest_check_enabled", True))
    rest_tolerance = float(config.get("rest_tolerance", 0.1))
    rest_fatal = bool(config.get("rest_check_fatal", False))
    max_sweep_range = float(config.get("max_sweep_range", 2 * 3.14159))

    joints = select_all_joints_with_limits(robot, excluded_indices)
    ctx.add_metric("frs_total_dofs", robot.dof_count)
    ctx.add_metric("frs_joints_tested", len(joints))
    ctx.add_metric("frs_passive_joints_skipped", len(passive_joint_indices))
    ctx.add_metric("frs_loop_joints_skipped", len(loop_indices))
    if passive_dof_names:
        ctx.log("FRS: Skipping passive joints: %s" % ", ".join(passive_dof_names))
    if loop_dof_names:
        ctx.log("FRS: Skipping closed-loop / parallel-linkage joints: %s" % ", ".join(loop_dof_names))

    if not joints:
        ctx.skip(
            _fix_message_no_joints_with_limits(
                passive_count=len(passive_joint_indices),
                total_dof=robot.dof_count,
            )
        )
        return

    # Heartbeat cadence: emit a ctx.step every HB_EVERY physics frames
    # inside the inner loops so we never cross the 60s runner watchdog
    # (session.py:OUTPUT_INACTIVITY_TIMEOUT -> runner.py:_force_kill_process_tree)
    # on a genuinely healthy sweep. At 240 Hz physics this is ~0.2s per
    # heartbeat. Without it, physics_step/advance emit nothing and the
    # gap between the 10th capture progress and the next joint message
    # could exceed 60s when render frames are slow.
    HB_EVERY = 40

    # Overlays still disabled (# OVERLAY-DISABLED). They are visual-only
    # and were on the suspect list before we pinned the real cause to the
    # runner watchdog; re-enable one at a time after captures confirm green.
    # show_overlay(stage, camera_path, "FRS FULL RANGE SWEEP\nSETTLING")
    ctx.step("FRS: initial settle %ds (%d frames)" % (int(settle_seconds), int(settle_seconds * physics_fps)))
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    # update_overlay_transform(stage, camera_path)  # OVERLAY-DISABLED

    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
    ctx.add_metric("frs_bbox_baseline_volume", baseline_bbox.volume)

    joints_passed = 0
    joints_failed = 0
    failed_names = []
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    frame_counter = 0

    for jnum, (joint_idx, joint_name) in enumerate(joints, start=1):
        ctx.step("FRS joint %d/%d: %s" % (jnum, len(joints), joint_name))
        # show_overlay(...)  # OVERLAY-DISABLED

        lowers, uppers = robot.get_joint_position_limits()
        lo = float(lowers[joint_idx])
        hi = float(uppers[joint_idx])

        params = compute_sweep_parameters(
            lo,
            hi,
            margin_ratio=margin_ratio,
            max_sweep_range=max_sweep_range,
            speed_scale=speed_scale,
            pause_seconds=pause_seconds,
            physics_fps=physics_fps,
            joint_name=joint_name,
        )

        start_positions = robot.get_joint_positions()
        q_start = float(start_positions[joint_idx])
        segments = build_sweep_segments(q_start, params)
        joint_errors = []

        for seg_start, seg_end, seg_name in segments:
            ctx.step("FRS j=%s seg=%s begin (%d frames)" % (joint_name, seg_name, params["seg_frames"]))
            for frame in range(params["seg_frames"]):
                t = (frame + 1) / float(params["seg_frames"])
                eased = interpolate_profile(profile, t)
                target = seg_start + (seg_end - seg_start) * eased
                positions = robot.get_joint_positions()
                positions[joint_idx] = target
                robot.set_joint_position_targets(positions)
                await ctx.step_one()

                if frame % 20 == 0:
                    current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
                    msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                    if msg:
                        joint_errors.append(_fix_message_bbox_explode(joint_name, seg_name, msg))

                if frame_counter % capture_interval == 0:
                    fp = await ctx.capture_frame(
                        label="full_range_sweep_%03d_%s_%04d" % (jnum, seg_name, frame),
                        stabilize_frames=0,
                    )
                    if fp:
                        capture_frames.append(fp)
                    ctx.scene.update_camera_follow(update_history=True)
                else:
                    ctx.scene.update_camera_follow(update_history=False)

                if frame % HB_EVERY == 0:
                    ctx.step(
                        "FRS j=%s seg=%s frame=%d/%d pos=%.3f"
                        % (joint_name, seg_name, frame, params["seg_frames"], target)
                    )
                frame_counter += 1

            if rest_enabled:
                rest_violations = 0
                for pframe in range(params["pause_frames"]):
                    await ctx.step_one()
                    positions = robot.get_joint_positions()
                    if abs(float(positions[joint_idx]) - float(seg_end)) > rest_tolerance:
                        rest_violations += 1
                    frame_counter += 1
                    if pframe % HB_EVERY == 0:
                        ctx.step("FRS j=%s seg=%s rest %d/%d" % (joint_name, seg_name, pframe, params["pause_frames"]))
                if rest_violations > params["pause_frames"] // 2:
                    rest_msg = _fix_message_rest_violation(
                        joint_name=joint_name,
                        seg_name=seg_name,
                        seg_end=float(seg_end),
                        violations=rest_violations,
                        total=params["pause_frames"],
                    )
                    if rest_fatal:
                        joint_errors.append(rest_msg)
                    else:
                        ctx.warn(rest_msg)
            else:
                for pframe in range(params["pause_frames"]):
                    await ctx.step_one()
                    frame_counter += 1
                    if pframe % HB_EVERY == 0:
                        ctx.step("FRS j=%s seg=%s pause %d/%d" % (joint_name, seg_name, pframe, params["pause_frames"]))

        final_positions = robot.get_joint_positions()
        observed_zero = float(final_positions[joint_idx])
        err_to_zero = abs(observed_zero - params["zero_target"])
        if err_to_zero > zero_tolerance:
            joint_errors.append(
                _fix_message_zero_return(
                    joint_name=joint_name,
                    observed=observed_zero,
                    target=float(params["zero_target"]),
                    tolerance=zero_tolerance,
                )
            )

        if joint_errors:
            joints_failed += 1
            failed_names.append(joint_name)
            for msg in joint_errors:
                ctx.warn(msg)
        else:
            joints_passed += 1
            ctx.log("FRS: Joint '%s' passed full-range sweep" % joint_name)

    # hide_overlay(stage)         # OVERLAY-DISABLED
    # cleanup_overlay(stage)      # OVERLAY-DISABLED
    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="full_range_sweep", role="summary")

    ctx.add_metric("frs_joints_passed", joints_passed)
    ctx.add_metric("frs_joints_failed", joints_failed)

    if joints_failed > 0:
        ctx.fail(
            _fix_message_aggregate(
                failed=joints_failed,
                total=len(joints),
                failure_names=failed_names,
            )
        )

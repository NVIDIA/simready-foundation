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
"""MJC phase: simultaneous multi-joint convergence.
V1 reference: shared_phases/multi_joint_coordination.py.

Targets are mid-range positions scaled by a per-iteration factor (default
[0.3, 0.6, 0.5]); commanding all joints to opposite extremes simultaneously
caused self-collisions and PD saturation that looked like flickering on
Fanuc smoke runs (2026-04-24).
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

# ---------------------------------------------------------------------------
# Actionable failure messages.
#
# Library philosophy: when MJC
# cannot run on an asset (skip) or fails on it (fail), the message must
# teach the asset author exactly how to fix the asset -- not just say
# "didn't converge". These helpers return the strings that land in
# ``result.json`` and on the HTML report, and are the only signal an
# asset author gets back from CI.
# ---------------------------------------------------------------------------


_SPEC_REFERENCE_MJC = (
    "REFERENCE:\n"
    "  Spec (driven joints):  nv_core/sr_specs/docs/features/"
    "FET_022-driven_joints.md\n"
    "  Spec (articulation):   nv_core/sr_specs/docs/features/"
    "FET_024-base_articulation.md\n"
    "  Example: sample_content/common_assets/robots_general/Robotiq/"
    "2F-85/simready_isaac_usd/Robotiq_2F_85.usda\n"
    '           (search for: prepend apiSchemas = ["PhysicsDriveAPI:angular"])'
)


def _build_skip_message_no_movable_joints(total_dof, finite_count):
    # type: (int, int) -> str
    """Build the message for skipping MJC because fewer than 2 joints have finite limits.

    This is an ASSET-AUTHORING gap: MJC drives multiple joints to mid-range
    targets simultaneously, so it needs at least two joints with both a
    finite lower AND finite upper limit. Continuous (infinite-range) revolute
    joints and unconstrained prismatic joints are useless here because there
    is no well-defined mid-range to aim at.
    """
    return (
        "MJC skipped: asset has only {finite}/{total} joints with finite "
        "position limits; MJC needs at least 2.\n"
        "\n"
        "WHAT THE TEST FOUND:\n"
        "  - Articulation DOFs reported by Isaac: {total}\n"
        "  - DOFs with finite (lower, upper) and upper-lower > 1e-6: {finite}\n"
        "  - Required by MJC: >= 2 (each driven independently to a mid-range\n"
        "    target chosen by target_factors x [lower+margin, upper-margin]).\n"
        "\n"
        "WHY IT MATTERS:\n"
        "  MJC validates simultaneous multi-joint convergence under the PD\n"
        "  drive controller. A revolute joint authored without limits (or\n"
        "  with type='none', or as a continuous joint) has no mid-range\n"
        "  target the test can pick, so it cannot participate.\n"
        "\n"
        "FIX: On every joint you intend MJC to exercise, author finite\n"
        "position limits on the matching axis. For PhysicsRevoluteJoint use\n"
        "lowerLimit/upperLimit in DEGREES; for PhysicsPrismaticJoint use\n"
        "lowerLimit/upperLimit in the stage's linear unit (typically meters).\n"
        "Both must be finite and upperLimit > lowerLimit.\n"
        "\n"
        "TEMPLATE -- paste/edit on each joint prim. Pick limits that match\n"
        "the real mechanical travel of the joint; do NOT use +-inf:\n"
        "\n"
        '    def PhysicsRevoluteJoint "joint_1"\n'
        "    {{\n"
        '        uniform token physics:axis = "Z"\n'
        "        float physics:lowerLimit = -170.0   # degrees\n"
        "        float physics:upperLimit =  170.0   # degrees\n"
        "        # ... body0 / body1 / localPos0 / localPos1 ...\n"
        "    }}\n"
        "\n"
        '    def PhysicsPrismaticJoint "slider_1"\n'
        "    {{\n"
        '        uniform token physics:axis = "X"\n'
        "        float physics:lowerLimit = 0.0      # meters\n"
        "        float physics:upperLimit = 0.085    # meters\n"
        "        # ... body0 / body1 / localPos0 / localPos1 ...\n"
        "    }}\n"
        "\n"
        "CHECKLIST per joint you expect MJC to drive:\n"
        "  - physics:axis is set (X / Y / Z).\n"
        "  - physics:lowerLimit and physics:upperLimit are BOTH finite.\n"
        "  - physics:upperLimit - physics:lowerLimit > 1e-6 (non-degenerate).\n"
        "  - Joint is reachable from the articulation root (otherwise Isaac\n"
        "    will not expose it as a DOF; see FET_024 for articulation\n"
        "    topology requirements).\n"
        "\n"
        "If the joint is intentionally free-running (e.g. a passive wheel),\n"
        "exclude it from your articulation rather than leaving it limit-less.\n"
        "\n"
        "{ref}"
    ).format(total=total_dof, finite=finite_count, ref=_SPEC_REFERENCE_MJC)


def _format_joint_list(valid_joints, limit=8):
    # type: (List[Dict[str, Any]], int) -> str
    """Render the list of MJC-driven joints as a copyable bullet list."""
    if not valid_joints:
        return "    (no joints captured)"
    lines = []
    for j in valid_joints[:limit]:
        lo_deg = math.degrees(float(j["lower"]))
        hi_deg = math.degrees(float(j["upper"]))
        lines.append(
            "    - {name} (DOF index {idx}): limits [{lo:.2f}, {hi:.2f}] deg "
            "(or stage-linear units for prismatic)".format(
                name=j["name"],
                idx=j["index"],
                lo=lo_deg,
                hi=hi_deg,
            )
        )
    if len(valid_joints) > limit:
        lines.append("    - ... ({n} more not listed)".format(n=len(valid_joints) - limit))
    return "\n".join(lines)


def _build_fail_message_iterations(
    iters_failed, total_iters, failed_iter_indices, valid_joints, pos_tol_deg, max_settling_seconds
):
    # type: (int, int, List[int], List[Dict[str, Any]], float, float) -> str
    """Build the message for MJC failing one or more iterations.

    This is a PHYSICS/BEHAVIOR failure: at least one joint did not enter
    the convergence band within ``max_settling_seconds``. The author needs
    to know which joints to inspect (we list all candidates), the typical
    drive-authoring fixes, and the paste-ready DriveAPI snippet.
    """
    iters_str = ", ".join(str(i) for i in failed_iter_indices) or "(none)"
    return (
        "MJC: {failed}/{total} iterations did not converge "
        "(failed iterations: {iters}).\n"
        "\n"
        "WHAT THE TEST FOUND:\n"
        "  - At least one joint did not reach its target within "
        "{tol:.2f} deg\n"
        "    of the commanded mid-range position within "
        "{tmax:.1f}s of physics.\n"
        "  - Joints under MJC control on this asset:\n"
        "{joints}\n"
        "\n"
        "WHICH PRIMS TO INSPECT:\n"
        "  Open each joint listed above in usdview / Kit and confirm it\n"
        "  carries a PhysicsDriveAPI on the matching axis (PhysicsRevoluteJoint\n"
        "  -> 'angular'; PhysicsPrismaticJoint -> 'linear'), with non-zero\n"
        "  stiffness and damping, and a maxForce large enough for the link\n"
        "  inertia it has to move.\n"
        "\n"
        "TYPICAL FIXES (in priority order):\n"
        "  1. Missing or zero drive stiffness on a driven joint. Add\n"
        "     PhysicsDriveAPI on the right axis. Paste-ready USDA:\n"
        "\n"
        '       def PhysicsRevoluteJoint "joint_1" (\n'
        '           prepend apiSchemas = ["PhysicsDriveAPI:angular"]\n'
        "       )\n"
        "       {{\n"
        '           uniform token physics:axis = "Z"\n'
        "           float physics:lowerLimit = -170.0\n"
        "           float physics:upperLimit =  170.0\n"
        "           float drive:angular:physics:stiffness = 1.0e6\n"
        "           float drive:angular:physics:damping   = 1.0e5\n"
        "           float drive:angular:physics:maxForce  = 1.0e7\n"
        '           uniform token drive:angular:physics:type = "force"\n'
        "       }}\n"
        "\n"
        "     For a prismatic joint, use 'PhysicsDriveAPI:linear' and the\n"
        "     'drive:linear:*' attribute namespace.\n"
        "\n"
        "  2. Under-tuned drive (joint lags behind). Increase\n"
        "     drive:*:physics:stiffness; if the joint then oscillates,\n"
        "     increase damping in proportion (rule of thumb: damping ~ 0.1 *\n"
        "     stiffness for force-type drives, but tune against your asset).\n"
        "\n"
        "  3. Over-tuned drive (oscillation / overshoot). Reduce stiffness or\n"
        "     raise damping. The MJC video capture is the fastest way to spot\n"
        "     this -- look for ring-out at the end of each iteration.\n"
        "\n"
        "  4. Self-collision stalling a subset of joints. Inspect the captured\n"
        "     video at iteration {first_failed}; if links visibly jam against\n"
        "     each other before converging, the asset needs collision-mesh or\n"
        "     limit adjustments so the commanded mid-range targets are\n"
        "     geometrically reachable simultaneously.\n"
        "\n"
        "  5. Passive joints in the articulation. MJC does NOT auto-skip\n"
        "     passive joints (only FRS does). Either author drive stiffness\n"
        "     on them, or expect them to fail MJC; remove them from the\n"
        "     articulation if they are meant to be free-running.\n"
        "\n"
        "TEST-SIDE KNOBS (only if the asset is correct):\n"
        "  - Increase max_settling_seconds for genuinely slow but converging\n"
        "    assets (long arms with high inertia commonly need 8-12s).\n"
        "  - Loosen position_tolerance_deg (default 1.0) only when minor\n"
        "    steady-state error is acceptable for the asset.\n"
        "\n"
        "{ref}"
    ).format(
        failed=iters_failed,
        total=total_iters,
        iters=iters_str,
        tol=pos_tol_deg,
        tmax=max_settling_seconds,
        joints=_format_joint_list(valid_joints),
        first_failed=(failed_iter_indices[0] if failed_iter_indices else 0),
        ref=_SPEC_REFERENCE_MJC,
    )


def get_defaults():
    # type: () -> Dict[str, Any]
    return {
        "settle_seconds": 1.0,
        "num_iterations": 3,
        "max_settling_seconds": 8.0,
        "position_tolerance_deg": 1.0,
        "target_margin_ratio": 0.10,
        "target_factors": [0.3, 0.6, 0.5],
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        "capture_fps": 15,
        # Seconds to ramp the commanded targets from start to goal (paced
        # trajectory) instead of a single far-target step command. Matches the
        # way FRS / JIK drive the robot; keeps uncapped joints from whipping.
        "motion_seconds": 2.0,
    }


def compute_factor_target(lo, hi, margin_ratio, factor):
    # type: (float, float, float, float) -> float
    """Pick a target inside [lo+margin, hi-margin] interpolated by factor in [0,1]."""
    margin = (hi - lo) * float(margin_ratio)
    span = (hi - lo) - 2.0 * margin
    if span <= 0.0:
        return float((lo + hi) * 0.5)
    return float(lo + margin + span * float(factor))


def aggregate_mjc_summary(per_iter_results):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    """Roll up per-iteration results to phase-level metrics."""
    iters_passed = sum(1 for r in per_iter_results if r["ok"])
    iters_failed = len(per_iter_results) - iters_passed
    return {
        "iterations_passed": iters_passed,
        "iterations_failed": iters_failed,
        "failed_iterations": [r["iteration"] for r in per_iter_results if not r["ok"]],
    }


async def _run_iteration(
    ctx,
    robot,
    scene_info,
    valid_joints,
    factor,
    iteration_idx,
    pos_tol_rad,
    max_frames,
    capture_interval,
    capture_frames,
    baseline_bbox,
    bbox_ratio_limit,
    margin_ratio,
    physics_fps,
    motion_frames,
):
    """Run a single coordination iteration. Returns (ok, settled_joint_names).
    Captures frames into the shared list.

    The commanded joint targets are RAMPED from the start pose to the goal over
    ``motion_frames`` (smoothstep), i.e. the robot is driven like a real
    trajectory -- a stream of intermediate setpoints -- rather than handed a
    single far target in one step. A step command makes the PD drive accelerate
    hard toward the goal; on a joint with no enforced velocity limit that whips
    the joint and can diverge the solver (invalid PhysX transforms). Ramping
    keeps the motion physical and stable. After the ramp the final target is
    held while convergence is measured. (FRS and JIK drive the robot the same
    way.)
    """
    HB_EVERY = 40
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

    start_positions = robot.get_joint_positions().copy()
    targets = start_positions.copy()
    target_pairs = []
    for j in valid_joints:
        tgt = compute_factor_target(j["lower"], j["upper"], margin_ratio, factor)
        targets[j["index"]] = tgt
        target_pairs.append((j["index"], j["name"], tgt))
    delta = targets - start_positions
    ramp_frames = max(1, int(motion_frames))

    converged_names = set()
    iteration_errors = []
    for frame in range(max_frames):
        # Paced command: ramp start -> goal over ramp_frames, then hold goal.
        eased = smoothstep((frame + 1) / float(ramp_frames))
        robot.set_joint_position_targets(start_positions + delta * eased)
        await ctx.step_one()
        positions = robot.get_joint_positions()
        for idx, name, tgt in target_pairs:
            err = abs(float(positions[idx]) - tgt)
            if err <= pos_tol_rad:
                converged_names.add(name)

        if frame % 20 == 0:
            current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
            msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
            if msg:
                iteration_errors.append(msg)
                break

        if frame % capture_interval == 0:
            frame_path = await ctx.capture_frame(
                label="mjc_iter%d_%04d" % (iteration_idx, frame),
                stabilize_frames=0,
            )
            if frame_path:
                capture_frames.append(frame_path)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)

        if frame % HB_EVERY == 0:
            ctx.step(
                "MJC iter=%d frame=%d/%d converged=%d/%d"
                % (iteration_idx, frame, max_frames, len(converged_names), len(target_pairs))
            )

        if len(converged_names) >= len(target_pairs):
            break

    ok = len(converged_names) >= len(target_pairs) and not iteration_errors
    return ok, converged_names, iteration_errors


async def run_multi_joint_coordination(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run the MJC phase. Mutates ctx via skip / add_metric / warn / fail."""
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 15))
    settle_seconds = float(config.get("settle_seconds", 1.0))
    num_iterations = int(config.get("num_iterations", 3))
    max_settling_seconds = float(config.get("max_settling_seconds", 8.0))
    pos_tol_deg = float(config.get("position_tolerance_deg", 1.0))
    pos_tol_rad = math.radians(pos_tol_deg)
    margin_ratio = float(config.get("target_margin_ratio", 0.10))
    target_factors = list(config.get("target_factors", [0.3, 0.6, 0.5]))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))

    ctx.step("Scanning joints for finite ranges (MJC)")
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    passive_indices = set(int(i) for i in scene_info.get("passive_joint_indices") or [])
    follower_indices = set(int(i) for i in scene_info.get("mimic_follower_indices") or [])
    loop_indices = set(int(i) for i in scene_info.get("loop_joint_indices") or [])
    excluded = passive_indices | follower_indices | loop_indices
    valid_joints = []
    skipped_loop = []
    for i, name in enumerate(dof_names):
        if i in excluded:
            if i in loop_indices:
                skipped_loop.append(str(name))
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if math.isfinite(lo) and math.isfinite(hi) and (hi - lo) > 1e-6:
            valid_joints.append(
                {
                    "index": i,
                    "name": str(name),
                    "lower": lo,
                    "upper": hi,
                }
            )
    if skipped_loop:
        ctx.step(
            "MJC: skipping %d closed-loop / parallel-linkage joint(s) "
            "(constrained by the loop; cannot be driven to independent "
            "targets): %s" % (len(skipped_loop), ", ".join(skipped_loop))
        )
    ctx.add_metric("mjc_total_joints", len(dof_names))
    ctx.add_metric("mjc_valid_joints", len(valid_joints))
    ctx.add_metric("mjc_loop_joints_skipped", len(skipped_loop))
    if len(valid_joints) < 2:
        ctx.skip(
            _build_skip_message_no_movable_joints(
                total_dof=len(dof_names),
                finite_count=len(valid_joints),
            )
        )
        return

    ctx.step("Settling robot before MJC")
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)

    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    max_frames = max(60, int(max_settling_seconds * physics_fps))
    motion_frames = max(1, int(float(config.get("motion_seconds", 2.0)) * physics_fps))
    per_iter_results = []

    for it in range(num_iterations):
        factor = float(target_factors[it % len(target_factors)]) if target_factors else 0.5
        ctx.step("MJC iteration %d/%d (factor=%.2f)" % (it + 1, num_iterations, factor))
        ok, converged_names, iter_errs = await _run_iteration(
            ctx=ctx,
            robot=robot,
            scene_info=scene_info,
            valid_joints=valid_joints,
            factor=factor,
            iteration_idx=it,
            pos_tol_rad=pos_tol_rad,
            max_frames=max_frames,
            capture_interval=capture_interval,
            capture_frames=capture_frames,
            baseline_bbox=baseline_bbox,
            bbox_ratio_limit=bbox_ratio_limit,
            margin_ratio=margin_ratio,
            physics_fps=physics_fps,
            motion_frames=motion_frames,
        )
        per_iter_results.append(
            {
                "iteration": it,
                "ok": ok,
                "converged_count": len(converged_names),
                "errors": iter_errs,
            }
        )
        if iter_errs:
            for err in iter_errs:
                ctx.warn("MJC iter %d: %s" % (it, err))
        if not ok:
            ctx.warn(
                "MJC: iteration %d did not converge (%d/%d joints settled). %s %s"
                % (
                    it,
                    len(converged_names),
                    len(valid_joints),
                    asset_fix("Tune drive gains or relax target_margin_ratio."),
                    engine_note("PD controller may need tuning per asset."),
                )
            )

    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="multi_joint_coordination", role="summary")

    summary = aggregate_mjc_summary(per_iter_results)
    ctx.add_metric("mjc_iterations_passed", summary["iterations_passed"])
    ctx.add_metric("mjc_iterations_failed", summary["iterations_failed"])

    if summary["iterations_failed"] > 0:
        ctx.fail(
            _build_fail_message_iterations(
                iters_failed=summary["iterations_failed"],
                total_iters=len(per_iter_results),
                failed_iter_indices=summary["failed_iterations"],
                valid_joints=valid_joints,
                pos_tol_deg=pos_tol_deg,
                max_settling_seconds=max_settling_seconds,
            )
        )

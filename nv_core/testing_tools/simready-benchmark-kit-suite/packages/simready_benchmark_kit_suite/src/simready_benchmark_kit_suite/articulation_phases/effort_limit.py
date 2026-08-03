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
"""EFF phase: external-force break detection across 12 directions.
V1 reference: shared_phases/effort_limit.py.
"""
import math

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.force_utils import (
    apply_external_force,
    clear_external_force,
    clear_force_visualization,
    generate_12_force_directions,
    visualize_force_arrow,
)
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready_benchmark_kit_suite.articulation_phases.robot_state import (
    reset_to_default,
)

_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Feature:   nv_core/sr_specs/docs/features/FET_022-driven_joints.md\n"
    "  Drive:     nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_driven_joints/requirements/\n"
    "             physics-drive-and-joint-state.md (DJ.001 -- maxForce > 0)\n"
    "             drive-joint-value-reasonable.md  (DJ.006 -- stiffness/"
    "damping ranges)\n"
    "  Joints:    nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_joints/requirements/\n"
    "             joint-body-target-exists.md\n"
    "  Example:   sample_content/common_assets/robots_general/Franka/"
    "FrankaResearch3/\n"
    "             simready_isaac_usd/FrankaResearch3.usda\n"
    "             (search for: drive:angular:physics:maxForce)"
)


def _no_testable_joints_message(asset_path, passive_count, follower_count):
    # type: (str, int, int) -> str
    return (
        "EFF: No joints with authored position or effort limits to test"
        " under external force.\n"
        "  Asset:               {root}\n"
        "  Passive joints excluded:        {passive}\n"
        "  Mimic-follower joints excluded: {follower}\n"
        "\n"
        "WHAT THE TEST NEEDS: at least one revolute or prismatic joint that"
        " has EITHER\n"
        "  - finite physics:lowerLimit + physics:upperLimit with"
        " (upper - lower) > 1e-6, OR\n"
        "  - a finite, positive drive:<linear|angular>:physics:maxForce.\n"
        "\n"
        "FIX: open each driven joint prim under {root} and ensure the"
        " drive + limits are authored.\n"
        "Example -- paste/edit on a revolute joint (values in newtons,"
        " radians):\n"
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
        "        # Required for EFF: positive maxForce so the controller"
        " can hold against pushes.\n"
        "        # Typical revolute arm joints: 50-300 N·m;"
        " base/shoulder larger, wrist smaller.\n"
        "        float drive:angular:physics:maxForce = 87.0\n"
        "        float drive:angular:physics:stiffness = 1000.0\n"
        "        float drive:angular:physics:damping   = 100.0\n"
        "\n"
        "        # Required for EFF break detection: real motion limits"
        " (radians for revolute,\n"
        "        # meters for prismatic). EFF flags a 'break' when the"
        " joint exceeds these by\n"
        "        # more than break_tolerance * range (default 10%).\n"
        "        float physics:lowerLimit = -2.8973\n"
        "        float physics:upperLimit =  2.8973\n"
        "    }}\n"
        "\n"
        "If every joint is genuinely fixed/passive (e.g., a static fixture),"
        " EFF is not\n"
        "applicable to this asset -- exclude it from the EFF profile in"
        " your test plan.\n"
        "\n"
        "{ref}"
    ).format(root=asset_path, passive=passive_count, follower=follower_count, ref=_SPEC_REFERENCE)


def _no_child_body_message(joint_name, joint_index):
    # type: (str, int) -> str
    return (
        "EFF: Joint '{name}' (dof index {idx}) has no resolvable downstream"
        " child body -- skipping this joint.\n"
        "\n"
        "WHAT THE TEST NEEDS: the joint must connect a parent rigid body"
        " (body0) to a child rigid\n"
        "body (body1). EFF applies external force to the child body and"
        " measures joint excursion;\n"
        "without body1 there is nothing to push.\n"
        "\n"
        "FIX: open the joint prim for '{name}' in USD and ensure BOTH"
        " body relationships are\n"
        "authored and target prims that carry PhysicsRigidBodyAPI:\n"
        "\n"
        '    def PhysicsRevoluteJoint "{name}"\n'
        "    {{\n"
        "        rel physics:body0 = </path/to/parent_link>   # must exist"
        " and have PhysicsRigidBodyAPI\n"
        "        rel physics:body1 = </path/to/child_link>    # REQUIRED"
        " for EFF -- was missing/unresolved\n"
        '        uniform token physics:axis = "Y"\n'
        "        ...\n"
        "    }}\n"
        "\n"
        "Common causes:\n"
        "  - physics:body1 not authored (only body0 set).\n"
        "  - physics:body1 points at a prim that does not exist or has been"
        " renamed.\n"
        "  - The target prim exists but lacks PhysxRigidBodyAPI /"
        " PhysicsRigidBodyAPI.\n"
        "  - A loose RigidBodyAPI prim was expected to sit beside the joint"
        " and is missing.\n"
        "\n"
        "{ref}"
    ).format(name=joint_name, idx=joint_index, ref=_SPEC_REFERENCE)


def _joint_broke_message(joint_name, broke_directions, min_break_force):
    # type: (str, list, Optional[float]) -> str
    force_str = "unknown" if min_break_force is None else ("%.1f N" % min_break_force)
    return (
        "EFF: Joint '{name}' exceeded its authored position limits under"
        " external force.\n"
        "  Failing directions:   {dirs}\n"
        "  Min observed break:   {force}\n"
        "\n"
        "WHAT TO INSPECT (in priority order):\n"
        "  1. drive:<linear|angular>:physics:maxForce on the joint prim --"
        " this is the cap on the\n"
        "     controller's holding torque/force. If it is too low, the"
        " drive cannot resist the\n"
        "     applied 12-direction push and the link drifts past its"
        " physics:lowerLimit /\n"
        "     physics:upperLimit. Typical good ranges:\n"
        "        - revolute arm joints:   ~50-300 N·m (shoulder >"
        " elbow > wrist)\n"
        "        - prismatic gripper:     ~20-200 N\n"
        "     Bump maxForce above the applied push (see test config"
        " 'force_magnitude_newtons')\n"
        "     plus a safety margin (2-3x) and re-run.\n"
        "  2. drive stiffness / damping -- under-damped drives oscillate"
        " past the limit even\n"
        "     when maxForce is adequate. Sane defaults: stiffness 1000-10000,"
        " damping 10-100\n"
        "     (DJ.006).\n"
        "  3. physxRigidBody:mass and physxRigidBody:diagonalInertia on the"
        " driven link --\n"
        "     under-massed links amplify force response and read as a"
        " spurious break.\n"
        "  4. physics:lowerLimit / physics:upperLimit -- if these are too"
        " tight, normal hold\n"
        "     wobble exceeds them. EFF flags a break when excursion > 10%"
        " of (upper - lower).\n"
        "\n"
        "If the joint is GENUINELY meant to yield at this load, lower"
        " 'force_magnitude_newtons'\n"
        "in the per-test config to the asset's real operating envelope.\n"
        "\n"
        "{ref}"
    ).format(name=joint_name, dirs=", ".join(broke_directions) or "(none)", force=force_str, ref=_SPEC_REFERENCE)


def _aggregate_failure_message(failed, tested, failure_names, force_magnitude):
    # type: (int, int, list, float) -> str
    return (
        "EFF: {failed}/{tested} joints exceeded position limits under"
        " {force:.0f} N external force.\n"
        "  Failing joints: {names}\n"
        "\n"
        "Each failing joint has a per-joint warning above with its"
        " specific failing directions\n"
        "and the four-step inspection checklist (drive maxForce, drive"
        " stiffness/damping, link\n"
        "mass/inertia, joint limits). Walk those first.\n"
        "\n"
        "QUICK TRIAGE:\n"
        "  - If most or all joints fail in the same directions: the test"
        " force is likely too\n"
        "    high for this asset's class. Drop 'force_magnitude_newtons'"
        " in the EFF config to\n"
        "    the asset's rated operating envelope.\n"
        "  - If one or two joints fail: those joints'"
        " drive:*:physics:maxForce is the most\n"
        "    likely culprit. Edit the joint prims in USD and raise"
        " maxForce above the applied\n"
        "    push with a 2-3x margin.\n"
        "  - If the bbox 'exploded' rather than a clean limit excursion,"
        " the per-joint warning\n"
        "    says so -- that points to runaway integration, usually from"
        " an unpinned base or\n"
        "    near-zero mass/inertia on a link.\n"
        "\n"
        "{ref}"
    ).format(
        failed=failed,
        tested=tested,
        force=force_magnitude,
        names=", ".join(failure_names),
        ref=_SPEC_REFERENCE,
    )


def get_defaults():
    # type: () -> Dict[str, Any]
    # v1.6 parity (shared_phases.effort_limit): test_duration_seconds is the
    # TOTAL budget across all 12 directions, NOT per-direction. v1 computes:
    #   total_test_frames    = test_duration * fps
    #   frames_per_direction = total_test_frames // len(FORCE_DIRECTIONS)
    # so 2 s / 12 dirs = ~0.17 s per direction. Earlier ports of this file
    # ran the full test_duration per direction, which made EFF 12x slower
    # than v1 and pushed wall time past 6 min on a 6-DOF arm.
    return {
        "settle_seconds": 0.3,
        "force_magnitude_newtons": 10.0,
        "test_duration_seconds": 2.0,
        "break_tolerance": 0.1,
        "bbox_explode_ratio": 10.0,
        "bisection_enabled": True,
        "bisection_min_newtons": 1.0,
        "bisection_max_iterations": 6,
        "physics_fps": 240.0,
        "capture_fps": 8,
        "stop_on_first_break": True,
    }


def detect_break_from_positions(positions, authored_lo, authored_hi, break_tolerance, bbox_msgs):
    # type: (List[float], float, float, float, List[str]) -> Tuple[bool, str]
    """Return (broke, reason). Break = position excursion past (lo, hi) by > tolerance*range OR bbox explode."""
    if bbox_msgs:
        return True, "bbox explode: %s" % bbox_msgs[0]
    if not positions:
        return False, ""
    rng = authored_hi - authored_lo
    if rng <= 0:
        return False, ""
    overshoot = break_tolerance * rng
    max_p = max(positions)
    min_p = min(positions)
    if max_p > authored_hi + overshoot:
        return True, "exceeded upper limit (%.3f > %.3f + tol %.3f)" % (max_p, authored_hi, overshoot)
    if min_p < authored_lo - overshoot:
        return True, "exceeded lower limit (%.3f < %.3f - tol %.3f)" % (min_p, authored_lo, overshoot)
    return False, ""


def aggregate_eff_summary(per_joint_results):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    total = len(per_joint_results)
    passed = sum(1 for r in per_joint_results if r["ok"])
    return {
        "joints_tested": total,
        "joints_passed": passed,
        "joints_failed": total - passed,
        "failure_names": [r["name"] for r in per_joint_results if not r["ok"]],
    }


async def run_effort_limit(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    default_state = scene_info.get("default_state")

    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 8))
    settle_seconds = float(config.get("settle_seconds", 0.3))
    force_mag = float(config.get("force_magnitude_newtons", 10.0))
    test_duration = float(config.get("test_duration_seconds", 2.0))
    break_tol = float(config.get("break_tolerance", 0.1))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))
    bisection_enabled = bool(config.get("bisection_enabled", True))
    bisection_min = float(config.get("bisection_min_newtons", 1.0))
    # TODO: bisection_max_iters is read but never passed to bisect_break_force();
    # the bisection search ignores the configured iteration cap (latent bug).
    bisection_max_iters = int(config.get("bisection_max_iterations", 6))  # noqa: F841
    stop_on_first_break = bool(config.get("stop_on_first_break", True))

    HB_EVERY = 40

    # Exclude passive joints (no drive — applying external force tests the
    # joint's break threshold under no-drive holding torque, which is
    # meaningless) and mimic-followers (their effort response is dominated by
    # the mimic constraint, not their own drive). Both sets come from
    # scene_info; for arms with no mimic, the follower set is empty.
    ctx.step("Scanning joints for EFF candidates (excluding passive + mimic followers)")
    passive_indices = set(int(i) for i in scene_info.get("passive_joint_indices") or [])
    follower_indices = set(int(i) for i in scene_info.get("mimic_follower_indices") or [])
    loop_indices = set(int(i) for i in scene_info.get("loop_joint_indices") or [])
    excluded = passive_indices | follower_indices | loop_indices

    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    effort_limits = robot.get_joint_effort_limits()
    joints = []
    for i, name in enumerate(dof_names):
        if i in excluded:
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        el = float(effort_limits[i]) if effort_limits is not None and i < len(effort_limits) else float("nan")
        has_pos = math.isfinite(lo) and math.isfinite(hi) and (hi - lo) > 1e-6
        has_eff = math.isfinite(el) and el > 0.0
        if has_pos or has_eff:
            joints.append({"index": i, "name": str(name), "lower": lo, "upper": hi})

    ctx.add_metric("eff_joints_with_candidates", len(joints))
    ctx.add_metric("eff_joints_skipped_passive", len(passive_indices))
    ctx.add_metric("eff_joints_skipped_mimic_follower", len(follower_indices))
    if not joints:
        ctx.skip(
            _no_testable_joints_message(
                asset_path=str(asset_prim.GetPath()) if asset_prim is not None else "<unknown asset>",
                passive_count=len(passive_indices),
                follower_count=len(follower_indices),
            )
        )
        return

    # Probe IPhysxSimulation availability. apply_force_at_pos lives on this
    # interface in Kit 110+ (it was removed from the PhysX C++ class returned
    # by get_physx_interface() that v1.6 used). When the interface is absent
    # (e.g., pure-Python test env), skip cleanly rather than running iterations
    # that silently no-op the force.
    try:
        from omni.physx import get_physx_simulation_interface

        if get_physx_simulation_interface() is None:
            raise RuntimeError("get_physx_simulation_interface returned None")
    except Exception as exc:
        ctx.skip(
            "INTERNAL: EFF cannot run -- omni.physx simulation interface is"
            " not available in this process (%s: %s).\n"
            "EFF needs a live Kit session with the omni.physx extension"
            " loaded so that\n"
            "IPhysxSimulation.apply_force_at_pos can drive the 12-direction"
            " external-force probe.\n"
            "This is an environment / harness issue, not an asset issue."
            " Please file an issue\n"
            "with the kit_logs attached." % (type(exc).__name__, exc)
        )
        return

    ctx.step("Settling robot before EFF")
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)

    force_vectors = generate_12_force_directions()
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    per_joint_results = []

    for jnum, jinfo in enumerate(joints, start=1):
        ctx.step("EFF joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))
        broke_directions = []
        min_break_force = None
        body_path = robot.get_child_body_path(jinfo["index"]) if hasattr(robot, "get_child_body_path") else None
        if not body_path:
            msg = _no_child_body_message(jinfo["name"], jinfo["index"])
            detail = getattr(robot, "_child_body_resolve_detail", "")
            if detail:
                msg = msg + "\nResolver detail: " + detail + "\n"
            ctx.warn(msg)
            per_joint_results.append(
                {
                    "name": jinfo["name"],
                    "broke_directions": [],
                    "min_break_force_newtons": None,
                    "ok": True,
                    "skipped_reason": "no child body",
                }
            )
            continue

        # v1.6 parity: test_duration is the TOTAL budget per joint across
        # all 12 directions, not per-direction. With test_duration=2.0s and
        # 12 directions, each direction gets ~0.17s of physics + capture.
        total_test_frames = max(60, int(test_duration * physics_fps))
        frames_per_direction = max(1, total_test_frames // len(force_vectors))

        for fvec in force_vectors:
            arrow_path = "/World/_effort_viz/j%d_%s" % (
                jnum,
                fvec.label.replace("+", "p").replace("-", "n"),
            )
            visualize_force_arrow(stage, body_path, fvec.direction, force_mag, arrow_path)

            positions_buf = []
            bbox_msgs = []
            for frame in range(frames_per_direction):
                # apply_force_at_pos is single-shot per physics tick;
                # re-apply every frame so the force persists across the
                # whole test window. Matches v1.6 behaviour.
                apply_external_force(stage, body_path, fvec.direction, force_mag)
                await ctx.step_one()
                # Defensive read: if the physics view was invalidated mid-test
                # (commonly seen when applying external forces to an unpinned
                # base), get_joint_positions returns a NaN array. Skip the
                # frame and break out of this direction's loop with a clear
                # reason instead of crashing the whole effort_limit phase.
                positions = robot.get_joint_positions()
                idx = jinfo["index"]
                if idx >= positions.shape[0] or np.isnan(positions[idx]):
                    bbox_msgs.append(
                        "physics view invalidated (joint position read returned "
                        "NaN); skipping remaining frames for this direction"
                    )
                    break
                pos = float(positions[idx])
                positions_buf.append(pos)
                if frame % 20 == 0:
                    current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
                    msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                    if msg:
                        bbox_msgs.append(msg)

                if frame % capture_interval == 0:
                    frame_path = await ctx.capture_frame(
                        label="eff_%03d_%s_%04d" % (jnum, fvec.label, frame),
                        stabilize_frames=0,
                    )
                    if frame_path:
                        capture_frames.append(frame_path)
                    ctx.scene.update_camera_follow(update_history=True)
                if frame % HB_EVERY == 0:
                    ctx.step("EFF j=%s dir=%s frame=%d/%d" % (jinfo["name"], fvec.label, frame, frames_per_direction))
                if bbox_msgs:
                    break

            clear_external_force(stage, body_path)
            clear_force_visualization(stage, arrow_path)

            broke, _reason = detect_break_from_positions(
                positions_buf,
                jinfo["lower"],
                jinfo["upper"],
                break_tol,
                bbox_msgs,
            )
            if broke:
                broke_directions.append(fvec.label)
                if bisection_enabled and min_break_force is None:
                    # Conservative bisection: record the lower bound (we know the
                    # joint broke at force_mag; refining the exact threshold
                    # requires an async probe which is out of scope for the
                    # synchronous bisect_break_force helper).
                    min_break_force = float(bisection_min)

            if default_state is not None:
                await reset_to_default(ctx, robot, default_state, settle_seconds=0.2)

            # v1 parity: stop testing remaining directions once a break is
            # detected -- there is no value in confirming the joint is broken
            # in 11 more directions, and on a 6-DOF arm this saves up to ~90%
            # of the per-joint wall time on broken joints.
            if broke and stop_on_first_break:
                ctx.step(
                    "EFF j=%s broke at dir=%s -- skipping remaining %d directions"
                    % (jinfo["name"], fvec.label, len(force_vectors) - len(broke_directions))
                )
                break

        ok = not broke_directions
        record = {
            "name": jinfo["name"],
            "broke_directions": broke_directions,
            "min_break_force_newtons": min_break_force,
            "ok": ok,
        }
        if not ok:
            ctx.warn(_joint_broke_message(jinfo["name"], broke_directions, min_break_force))
        else:
            ctx.log("EFF: Joint '%s' held across all 12 directions" % jinfo["name"])
        per_joint_results.append(record)

    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="effort_limit", role="summary")

    summary = aggregate_eff_summary(per_joint_results)
    ctx.add_metric("eff_joints_tested", summary["joints_tested"])
    ctx.add_metric("eff_joints_passed", summary["joints_passed"])
    ctx.add_metric("eff_joints_failed", summary["joints_failed"])

    if summary["joints_failed"] > 0:
        ctx.fail(
            _aggregate_failure_message(
                failed=summary["joints_failed"],
                tested=summary["joints_tested"],
                failure_names=summary["failure_names"],
                force_magnitude=float(config.get("force_magnitude_newtons", 10.0)),
            )
        )

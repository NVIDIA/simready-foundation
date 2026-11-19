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
from simready.foundation.tier_core.runtime_tests.articulation_phases.coordination_timing import (
    MAX_TIMING_ITERATIONS,
    CoordinationBudget,
    CoordinationTiming,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    engine_note,
    note_secondary_error,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.kinematic_bounds import (
    articulation_span_reference,
    check_articulation_span,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_history import (
    make_joint_observer,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_utils import smoothstep
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
    resolve_velocity_hints,
    usable_velocity,
)

# ---------------------------------------------------------------------------
# Evidence-based failure messages distinguish unavailable prerequisites,
# evaluated goal-band misses and possible setup/importer/asset causes. They
# preserve the governing references without treating every miss as an asset
# defect or prescribing unproved gain changes. Results, logs and motion evidence
# provide complementary context for the owning provider or asset author.
# ---------------------------------------------------------------------------


_SPEC_REFERENCE_MJC = (
    "REFERENCE:\n"
    "  Driven joints: nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/"
    "FET022_DrivenJoints.PhysX.md\n"
    "  Articulation: nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/"
    "physics_bodies/base_articulation/requirements/has-articulation-root.md\n"
    "  Example: sample_content/common_assets/robots_general/Robotiq/"
    "2F-85/simready_usd/runnables/physics/physx.usda\n"
    "           (inspect the selected variant's authored drives and joint limits)"
)


def _build_skip_message_no_movable_joints(total_dof, finite_count):
    # type: (int, int) -> str
    """Describe fewer than two qualified bounded excursions without inventing limits.

    The historical finite_count parameter includes supported local angular
    excursions; it is not a count of finite authored/imported limit pairs.
    """
    return (
        f"MJC: asset has only {finite_count}/{total_dof} joints with qualified bounded excursions; "
        "MJC needs at least 2.\n"
        "\n"
        "WHAT THE TEST FOUND:\n"
        f"  - Articulation DOFs reported by the runtime: {total_dof}\n"
        f"  - Eligible DOFs with a safe excursion wider than 1e-6: {finite_count}\n"
        "  - Required by MJC: >= 2 (each driven independently to a mid-range\n"
        "    target chosen by target_factors x [lower+margin, upper-margin]).\n"
        "\n"
        "WHY IT MATTERS:\n"
        "  MJC commands multiple eligible DOFs and checks whether each enters\n"
        "  its target tolerance band. Finite native ranges retain their stops.\n"
        "  A uniquely identified unbounded revolute joint can use a local +/-pi\n"
        "  excursion around its measured start, retaining any finite one-sided\n"
        "  stop. Signed infinities and float32-max SDK sentinels identify\n"
        "  unbounded limits; no units are guessed for prismatic/unknown DOFs.\n"
        "  Unsupported ranges and passive/mimic/loop exclusions do not count.\n"
        "\n"
        "INSPECT: compare the composed and imported position limits first.\n"
        "If legitimate mechanical limits are missing, author the real values.\n"
        "For PhysicsRevoluteJoint use\n"
        "lowerLimit/upperLimit in DEGREES; for PhysicsPrismaticJoint use\n"
        "lowerLimit/upperLimit in stage units, not automatically meters.\n"
        "Any authored mechanical stops must describe the real increasing range.\n"
        "\n"
        "ILLUSTRATIVE TEMPLATE -- these are not suggested ratings. Pick limits\n"
        "that describe real bounded mechanical travel; continuous revolute joints\n"
        "can retain valid signed infinite endpoints and qualify a local excursion:\n"
        "\n"
        '    def PhysicsRevoluteJoint "joint_1"\n'
        "    {\n"
        '        uniform token physics:axis = "Z"\n'
        "        float physics:lowerLimit = -170.0   # degrees\n"
        "        float physics:upperLimit =  170.0   # degrees\n"
        "        # ... body0 / body1 / localPos0 / localPos1 ...\n"
        "    }\n"
        "\n"
        '    def PhysicsPrismaticJoint "slider_1"\n'
        "    {\n"
        '        uniform token physics:axis = "X"\n'
        "        float physics:lowerLimit = 0.0      # illustrative stage units\n"
        "        float physics:upperLimit = 0.085    # use real mechanical travel\n"
        "        # ... body0 / body1 / localPos0 / localPos1 ...\n"
        "    }\n"
        "\n"
        "CHECKLIST per joint you expect MJC to drive:\n"
        "  - physics:axis is set (X / Y / Z).\n"
        "  - A finite increasing native range, or a uniquely identified\n"
        "    unbounded revolute joint with a safe local angular excursion.\n"
        "  - Qualified excursion width > 1e-6 (non-degenerate).\n"
        "  - Joint is reachable from the articulation root (otherwise the runtime\n"
        "    will not expose it as a DOF; inspect the articulation-root and joint\n"
        "    topology requirements).\n"
        "\n"
        "Intentionally free-running or continuous joints may be valid; identified\n"
        "revolute joints can qualify without invented stops. Unbounded prismatic\n"
        "or unidentified DOFs remain outside the safe-excursion scope.\n"
        "Do not remove them from the articulation\n"
        "or invent limits merely to make the test run.\n"
        "\n"
        f"{_SPEC_REFERENCE_MJC}"
    )


def _format_joint_list(valid_joints, limit=8):
    # type: (list[dict[str, Any]], int) -> str
    """Render native runtime limits without assuming angular joint types."""
    if not valid_joints:
        return "    (no joints captured)"
    lines = []
    for j in valid_joints[:limit]:
        lines.append(
            "    - {name} (DOF index {idx}): limits [{lo:.6g}, {hi:.6g}] "
            "runtime joint coordinates; consult motion metadata for units".format(
                name=j["name"],
                idx=j["index"],
                lo=float(j["lower"]),
                hi=float(j["upper"]),
            )
        )
    if len(valid_joints) > limit:
        lines.append(f"    - ... ({len(valid_joints) - limit} more not listed)")
    return "\n".join(lines)


def _build_fail_message_iterations(
    iters_failed, total_iters, failed_iter_indices, valid_joints, pos_tol_deg, max_settling_seconds, timing_records=None
):
    # type: (int, int, list[int], list[dict[str, Any]], float, float) -> str
    """Describe failed convergence without guessing gains or changing policy."""
    iters_str = ", ".join(str(i) for i in failed_iter_indices) or "(none)"
    timing_text = (
        "  - Planned nominal ramp/hold/observation windows (seconds):\n"
        + "\n".join(
            "    iteration %d: %.3g / %.3g / %.3g"
            % (row["iteration"], row["ramp_seconds"], row["hold_seconds"], row["observation_seconds"])
            for row in timing_records
        )
        + "\n  - See mjc_timing_iterations for hint provenance and omitted diagnostic rows.\n"
        if timing_records is not None
        else f"  - Configured base observation window: {max_settling_seconds:.1f}s of nominal physics.\n"
    )
    return (
        f"MJC: {iters_failed}/{total_iters} iterations did not converge "
        f"(failed iterations: {iters_str}).\n"
        "\n"
        "WHAT THE TEST FOUND:\n"
        "  - At least one joint did not reach its target with configured "
        f"position_tolerance_deg={pos_tol_deg:.2f}\n"
        "    of the commanded mid-range position within its planned nominal window.\n"
        f"{timing_text}"
        "  - Joints under MJC control on this asset:\n"
        f"{_format_joint_list(valid_joints)}\n"
        "\n"
        "DIAGNOSE BEFORE REPAIR:\n"
        "  Inspect the composed joints, selected runtime variant, actual commands,\n"
        "  imported actuator settings, passive/mimic/equality classification, units,\n"
        "  returned limits, collisions, gravity/base setup and PhysX runtime support.\n"
        "  A convergence failure or sampled bounding-box growth does not isolate\n"
        "  an asset defect, wrong gains, importer limitation or test setup issue.\n"
        "  The existing tolerance is radians-derived; for a prismatic joint the\n"
        "  legacy configuration label is not a physical angle. Consult motion metadata.\n"
        "  Preserve the original plan, trajectory and video for controlled comparisons.\n"
        "  Do not paste canned gains, relax target margins/tolerances, raise ratings\n"
        "  or remove passive joints merely to force a pass. Any justified repair or\n"
        "  tuning is external to Evaluate.\n"
        "\n"
        f"{_SPEC_REFERENCE_MJC}"
    )


def get_defaults():
    # type: () -> dict[str, Any]
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
        "coordination_speed_scale": 0.8,
        "coordination_settling_allowance_seconds": 0.25,
        "max_coordination_ramp_seconds": 60.0,
        "max_coordination_simulation_seconds": 600.0,
        "max_coordination_wall_seconds": 3360.0,
    }


def compute_factor_target(lo, hi, margin_ratio, factor, center=0.0, angular=False):
    # type: (float, float, float, float) -> float
    """Pick a target inside [lo+margin, hi-margin] interpolated by factor in [0,1]."""
    from .joint_targets import bounded_joint_range

    bounds = bounded_joint_range(lo, hi, center, angular=angular)
    if bounds is None:
        raise ValueError("MJC joint has no safe target range")
    lo, hi = bounds
    margin_ratio = finite_number(margin_ratio, "target_margin_ratio", maximum=0.5)
    factor = finite_number(factor, "target factor", maximum=1.0)
    margin = (hi - lo) * float(margin_ratio)
    span = (hi - lo) - 2.0 * margin
    if span <= 0.0:
        return float(min(hi, max(lo, lo + (hi - lo) * 0.5)))
    return float(min(hi, max(lo, lo + margin + span * float(factor))))


def aggregate_mjc_summary(per_iter_results):
    # type: (list[dict[str, Any]]) -> dict[str, Any]
    """Roll up per-iteration results to phase-level metrics."""
    iters_passed = sum(1 for r in per_iter_results if r["ok"])
    iters_failed = len(per_iter_results) - iters_passed
    return {
        "iterations_passed": iters_passed,
        "iterations_failed": iters_failed,
        "failed_iterations": [r["iteration"] for r in per_iter_results if not r["ok"]],
    }


def _record_guard_metric(ctx, name, value, primary=None):
    """Optional spatial context must not replace an actual guard interruption."""
    try:
        ctx.add_metric(name, value)
    except BaseException as diagnostic_error:
        if primary is None and not isinstance(diagnostic_error, Exception):
            raise
        if primary is not None:
            note_secondary_error(
                primary,
                lambda diagnostic_error=diagnostic_error: f"MJC {name} diagnostics unavailable: {diagnostic_error}",
            )
        else:
            try:
                ctx.warn(f"MJC {name} diagnostics unavailable; the spatial guard remains active.")
            except Exception:
                pass


def _publish_timing(ctx, records, attempted_iterations, budget=None):
    """Retain bounded diagnostic snapshots without masking a required error."""
    try:
        ctx.add_metric(
            "mjc_timing_iterations",
            [{**row, "joints": [dict(joint) for joint in row["joints"]]} for row in records],
        )
        ctx.add_metric("mjc_timing_iterations_omitted", max(0, attempted_iterations - len(records)))
        if budget is not None:
            ctx.add_metric("mjc_completed_nominal_ticks", budget.ticks)
    except Exception:
        try:
            ctx.warn("MJC timing diagnostics unavailable; the original control and execution outcome are unchanged.")
        except Exception:
            pass


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
    motion_observers=None,
    motion_clock=None,
    timing=None,
    budget=None,
    velocity_hints=None,
    timing_records=None,
    kinematic_span=None,
):
    """Run one iteration; return (ok, converged_names, iteration_errors).
    Captures frames into the shared list.

    The commanded joint targets are RAMPED from the start pose to the goal over
    ``motion_frames`` (smoothstep), i.e. the robot is driven like a real
    stream of intermediate setpoints rather than a single far target. Qualified
    speed hints pace the commanded profile; this is not proof of physical
    speed/acceleration enforcement or solver stability. After the ramp the
    final target is held while the existing band-entry check continues.
    """
    HB_EVERY = 40
    robot = owned_articulation(robot, scene_info)
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")

    from .joint_targets import bounded_joint_range

    # Required readback validation preserves SDK dtype. Use floating commands
    # so integer state vectors do not truncate goals and float32 assignment does
    # not round a bounded float64 command past the imported stop.
    start_positions = _required_positions(robot, "MJC").astype(float, copy=True)
    targets = start_positions.copy()
    target_pairs = []
    target_bounds = {}
    for j in valid_joints:
        bounds = bounded_joint_range(
            j["lower"],
            j["upper"],
            float(start_positions[j["index"]]),
            angular=j.get("angular", False),
        )
        if bounds is None:
            raise ValueError("MJC joint has no safe target range")
        tgt = compute_factor_target(
            j["lower"],
            j["upper"],
            margin_ratio,
            factor,
            center=float(start_positions[j["index"]]),
            angular=j.get("angular", False),
        )
        targets[j["index"]] = tgt
        target_pairs.append((j["index"], j["name"], tgt))
        target_bounds[j["index"]] = bounds
    delta = targets - start_positions
    ramp_frames = max(1, int(motion_frames))
    timing_record = None
    if timing is not None:
        timing_record = timing.plan_iteration(start_positions, targets, valid_joints, velocity_hints or [])
        ramp_frames = timing_record["ramp_frames"]
        max_frames = timing_record["total_frames"]
        timing_record["iteration"] = iteration_idx
        timing_record["clock_basis"] = "completed nominal simulation ticks; render/capture ticks excluded"
        timing_record["coordinate_basis"] = "same native runtime joint coordinates for displacement and speed"
        timing_record["completed_iteration_ticks"] = 0
        if timing_records is not None and len(timing_records) < MAX_TIMING_ITERATIONS:
            timing_records.append(timing_record)
        # Preserve legal clipping, but qualify the actual first setpoint against
        # the live start: clipping an out-of-range pose can introduce a jump
        # absent from the ideal smoothstep peak estimate.
        rows_by_index = {row["index"]: row for row in timing_record["joints"]}
        first_eased = smoothstep(1.0 / ramp_frames)
        try:
            for joint in valid_joints:
                index = joint["index"]
                lower, upper = target_bounds[index]
                raw = float(start_positions[index] + delta[index] * first_eased)
                first_command = min(upper, max(lower, raw))
                first_speed = abs(first_command - float(start_positions[index])) * physics_fps
                if not math.isfinite(first_speed):
                    raise RuntimeError(
                        "MJC initial legal command step has an invalid speed; runtime/setup timing mismatch"
                    )
                row = rows_by_index.get(index)
                if row is not None:
                    row["initial_command_clipped"] = first_command != raw
                    row["estimated_initial_command_step_speed"] = first_speed
                velocity = usable_velocity(velocity_hints[index][0]) if index < len(velocity_hints or []) else None
                if velocity is not None:
                    allowance = velocity * timing.scale
                    if first_speed > allowance and not math.isclose(first_speed, allowance, rel_tol=1e-12, abs_tol=0.0):
                        raise RuntimeError(
                            "MJC first legal command for joint %s exceeds its qualified speed allowance; "
                            "the initial live state and test timing cannot fit this window, a runtime/setup error "
                            "not an evaluated asset failure" % str(joint["name"])[:128]
                        )
        finally:
            _publish_timing(
                ctx, timing_records if timing_records is not None else [timing_record], iteration_idx + 1, budget
            )
    if budget is not None:
        budget.reserve(max_frames)

    converged_names = set()
    iteration_errors = []
    positions = start_positions
    for frame in range(max_frames):
        # Paced command: ramp start -> goal over ramp_frames, then hold goal.
        eased = smoothstep((frame + 1) / float(ramp_frames))
        # Clip only exercised coordinates, including endpoint roundoff.
        # Unselected coordinates remain the measured start exactly, not the
        # result of full-vector arithmetic or a guessed bounds policy.
        command = start_positions.copy()
        for idx, (lower, upper) in target_bounds.items():
            command[idx] = min(
                upper,
                max(lower, float(start_positions[idx] + delta[idx] * eased)),
            )
        robot.set_joint_position_targets(command)
        if budget is None:
            await ctx.step_one()
        else:
            await budget.step_one(ctx)
        positions = _required_positions(robot, "MJC")
        if motion_clock is not None:
            motion_clock["steps"] += 1
            for idx, observer in (motion_observers or {}).items():
                observer.sample(
                    {
                        "position": float(positions[idx]),
                        "target": float(command[idx]),
                        "final_target": float(targets[idx]),
                        "target_error": abs(float(positions[idx]) - float(targets[idx])),
                    },
                    time_s=motion_clock["steps"] / physics_fps,
                    phase="iteration_%d_%s" % (iteration_idx, "ramp" if frame < ramp_frames else "hold"),
                )
        for idx, name, tgt in target_pairs:
            err = abs(float(positions[idx]) - tgt)
            if err <= pos_tol_rad:
                converged_names.add(name)

        if frame % 20 == 0:
            current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
            msg = (
                check_articulation_span(current_bbox, kinematic_span, bbox_ratio_limit)
                if kinematic_span is not None
                else check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
            )
            if msg:
                if timing_record is not None:
                    timing_record["completed_iteration_ticks"] = frame + 1
                    timing_record["stop_reason"] = "spatial_guard_abort"
                interruption = RuntimeError(
                    f"MJC observation interrupted by spatial safety guard: {msg}; "
                    f"iteration {iteration_idx} completed {frame + 1}/{max_frames} planned ticks. "
                    "The convergence observation did not complete; this is not a measured non-convergence or an asset-defect diagnosis."
                )
                _record_guard_metric(
                    ctx,
                    "mjc_guard_abort",
                    {
                        "iteration": iteration_idx,
                        "reason": msg,
                        "completed_ticks": frame + 1,
                        "planned_ticks": max_frames,
                        "kinematic_span": kinematic_span,
                        "basis": "kinematic_span" if kinematic_span is not None else "unqualified_initial_volume_proxy",
                    },
                    primary=interruption,
                )
                raise interruption

        if frame % capture_interval == 0:
            frame_path = await ctx.capture_frame(
                label="mjc_iter%d_%04d" % (iteration_idx, frame),
                stabilize_frames=0,
            )
            if frame_path:
                capture_frames.append(frame_path)
                for observer in (motion_observers or {}).values():
                    observer.record_capture(frame_path)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)

        if budget is not None:
            budget.check_wall()

        if frame % HB_EVERY == 0:
            ctx.step(
                "MJC iter=%d frame=%d/%d converged=%d/%d"
                % (iteration_idx, frame, max_frames, len(converged_names), len(target_pairs))
            )

        if len(converged_names) >= len(target_pairs):
            break

    ok = len(converged_names) >= len(target_pairs) and not iteration_errors
    ctx.add_metric(
        f"mjc_iteration_{iteration_idx:d}_joints",
        [
            {
                "name": name,
                "target": float(tgt),
                "final_position": float(positions[idx]),
                "final_error": abs(float(positions[idx]) - tgt),
                "entered_tolerance": name in converged_names,
            }
            for idx, name, tgt in target_pairs
        ],
    )
    missing = [name for _, name, _ in target_pairs if name not in converged_names]
    if missing:
        ctx.warn(f"MJC iter={iteration_idx:d} joints never entered tolerance: {', '.join(missing)}")
    if timing_record is not None:
        timing_record["completed_iteration_ticks"] = frame + 1
    return ok, converged_names, iteration_errors


async def run_multi_joint_coordination(ctx, robot, scene_info, config, *, started_at=None, budget=None):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    """Run the MJC phase. Mutates ctx via skip / add_metric / warn / fail."""
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    validate_phase_config(config, "multi_joint_coordination")
    nominal_settle_steps(config.get("settle_seconds", 1.0), config.get("physics_fps", 240.0))
    timing = CoordinationTiming(config)
    budget = CoordinationBudget(config, started_at=started_at) if budget is None else budget
    budget.reserve(timing.minimum_total_frames)
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 15))
    num_iterations = int(config.get("num_iterations", 3))
    max_settling_seconds = float(config.get("max_settling_seconds", 8.0))
    pos_tol_deg = float(config.get("position_tolerance_deg", 1.0))
    pos_tol_rad = math.radians(pos_tol_deg)
    margin_ratio = float(config.get("target_margin_ratio", 0.10))
    target_factors = list(config.get("target_factors", [0.3, 0.6, 0.5]))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))

    from .joint_targets import bounded_joint_range, joint_is_angular

    ctx.step("Scanning joints for bounded target ranges (MJC)")
    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    passive_indices = {int(i) for i in scene_info.get("passive_joint_indices") or []}
    follower_indices = {int(i) for i in scene_info.get("mimic_follower_indices") or []}
    loop_indices = {int(i) for i in scene_info.get("loop_joint_indices") or []}
    excluded = passive_indices | follower_indices | loop_indices
    valid_joints = []
    independent_motion_count = 0
    skipped_loop = []
    skipped_ranges = []
    for i, name in enumerate(dof_names):
        if i in excluded:
            if i in loop_indices:
                skipped_loop.append(str(name))
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        if not (math.isfinite(lo) and math.isfinite(hi) and lo == hi):
            independent_motion_count += 1
        angular = joint_is_angular(scene_info, name)
        # Applicability does not need a live read. Each actual iteration derives
        # its local angular excursion from its required measured start pose.
        bounds = bounded_joint_range(lo, hi, 0.0, angular=angular)
        if bounds is not None and (bounds[1] - bounds[0]) > 1e-6:
            valid_joints.append(
                {
                    "index": i,
                    "name": str(name),
                    "lower": lo,
                    "upper": hi,
                    "angular": angular,
                }
            )
        else:
            skipped_ranges.append(str(name))
    if skipped_ranges:
        ctx.warn(f"MJC: no safe bounded excursion for joint(s): {', '.join(skipped_ranges)}")
    ctx.add_metric("mjc_joints_without_safe_range", skipped_ranges)
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
        reason = _build_skip_message_no_movable_joints(
            total_dof=len(dof_names),
            finite_count=len(valid_joints),
        )
        if independent_motion_count >= 2:
            raise RuntimeError(reason)
        if _has_current_coordinate_exclusions(robot, scene_info, ctx=ctx):
            ctx.add_metric("assessment_applicability", not_applicable("fewer_than_two_independent_coordinates", reason))
        ctx.skip(reason)
        return

    robot = owned_articulation(robot, scene_info)
    velocity_hints = resolve_velocity_hints(robot, scene_info)
    fallback_count = sum(velocity_hints[joint["index"]][0] is None for joint in valid_joints)
    ctx.add_metric("mjc_velocity_hint_fallback_joints", fallback_count)
    if fallback_count:
        ctx.warn(
            "MJC: %d eligible joints have no qualified speed hint; using the configured motion floor." % fallback_count
        )

    ctx.step("Settling robot before MJC")
    for index in range(timing.settle_frames):
        await budget.step_one(ctx)
        completed = index + 1
        if completed % 40 == 0 or completed == timing.settle_frames:
            ctx.step("MJC: nominal settle %d/%d ticks" % (completed, timing.settle_frames))
    baseline_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
    kinematic_span = articulation_span_reference(asset_prim or robot_root_prim)
    _record_guard_metric(
        ctx,
        "mjc_guard_reference",
        {
            "kinematic_span_stage_units": kinematic_span,
            "qualified": kinematic_span is not None,
            "basis": "kinematic_span" if kinematic_span is not None else "unqualified_initial_volume_proxy",
            "reference_source": (
                "authored body geometry, joint anchor offsets and bounded prismatic travel; frozen setup reference"
                if kinematic_span is not None
                else "initial live world-aligned bounding-box volume; topology reference could not be qualified"
            ),
        },
    )

    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    max_frames = timing.base_ramp_frames + timing.hold_frames
    motion_frames = timing.base_ramp_frames
    per_iter_results = []
    timing_records = []
    motion_observers = {
        joint["index"]: make_joint_observer(
            ctx,
            scene_info,
            joint["name"],
            "mjc_joint_%03d" % joint["index"],
            {
                "position": {"unit": "{joint}", "source": "RobotHandle articulation position readback"},
                "target": {"unit": "{joint}", "source": "position command issued by test"},
                "final_target": {
                    "unit": "{joint}",
                    "source": "iteration goal position used by the existing convergence check",
                },
                "target_error": {"unit": "{joint}", "source": "absolute measured joint position minus iteration goal"},
            },
            metadata={
                "physics_fps": physics_fps,
                "encoded_video_fps": capture_fps,
                "capture_interval_steps": capture_interval,
                "iterations": num_iterations,
                "observation_basis": "cumulative nominal steps across coordination iterations; initial settle and render ticks excluded",
                "position_tolerance_config_deg": pos_tol_deg,
                "applied_native_position_tolerance": pos_tol_rad,
                "tolerance_basis": "existing radians-derived tolerance; does not change linear-joint verdict policy",
                "convergence_basis": "existing check records whether each joint entered the goal band at any observation; plot does not assert simultaneous final convergence",
            },
        )
        for joint in valid_joints
    }
    motion_clock = {"steps": 0}

    for it in range(num_iterations):
        factor = float(target_factors[it % len(target_factors)]) if target_factors else 0.5
        ctx.step("MJC iteration %d/%d (factor=%.2f)" % (it + 1, num_iterations, factor))
        iteration_started_ticks = budget.ticks
        try:
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
                motion_observers=motion_observers,
                motion_clock=motion_clock,
                timing=timing,
                budget=budget,
                velocity_hints=velocity_hints,
                timing_records=timing_records,
                kinematic_span=kinematic_span,
            )
        except BaseException as primary_error:
            # Preserve observed media and partial histories without changing
            # the original interruption/cancellation into a behavioral verdict.
            for observer in motion_observers.values():
                try:
                    observer._warn()
                    observer.finish("coordination_interrupted")
                except Exception as diagnostic_error:
                    note_secondary_error(
                        primary_error,
                        lambda secondary=diagnostic_error: f"MJC partial motion evidence unavailable: {secondary}",
                    )
            if capture_frames:
                try:
                    ctx.encode_video(capture_frames, fps=capture_fps, label="multi_joint_coordination", role="summary")
                except Exception as diagnostic_error:
                    note_secondary_error(
                        primary_error,
                        lambda diagnostic_error=diagnostic_error: f"MJC partial video unavailable: {diagnostic_error}",
                    )
            raise
        finally:
            # A completed tick followed by a wall-guard error still counts;
            # failed ticks and render/capture work do not advance this clock.
            if timing_records and timing_records[-1]["iteration"] == it:
                timing_records[-1]["completed_iteration_ticks"] = budget.ticks - iteration_started_ticks
            _publish_timing(ctx, timing_records, it + 1, budget)
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
                    "Inspect actual commands, imported controls, coupling and unit basis; no cause is established.",
                    engine_note("Compare the selected variant, solver support and test setup before asset repair."),
                )
            )

    for observer in motion_observers.values():
        observer.finish("coordination_iterations_completed")

    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="multi_joint_coordination", role="summary")

    budget.check_wall()
    _publish_timing(ctx, timing_records, num_iterations, budget)

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
                timing_records=timing_records,
            )
        )

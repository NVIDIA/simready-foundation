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

"""Newton FRS: evaluate eligible joints at legal inset targets and zero/rest.
V1 reference: shared_phases/full_range_sweep.py.
"""

import math
from numbers import Real

from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.sweep_diagnostics import (
    SweepDiagnostics,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.sweep_timing import (
    SweepBudget,
    resolve_velocity_hints,
    segment_frames,
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

_FRS_SPEC_REFERENCE = "REFERENCE: simready/foundation/tier_newton/runtime_tests/docs/runtime-tests.md; selected plan and Newton importer/actuator configuration.\n"


def _fix_message_no_joints_with_limits(passive_count, total_dof):
    return (
        "FRS cannot run: no active joints with finite, distinct position limits.\n"
        "  Total articulation DOF: %d; passive joints excluded: %d.\n"
        "Check joint discovery, selected variant, actuator mapping and imported limits first.\n"
        "USD physics:lowerLimit / physics:upperLimit use degrees for revolute joints\n"
        "and stage-distance units for prismatic joints. Runtime revolute readbacks use radians;\n"
        "do not paste their values into authored USD limits without conversion.\n"
        "If verified authoring is incomplete, an illustrative angular-limit fragment is:\n"
        "    float physics:lowerLimit = -165.0\n"
        "    float physics:upperLimit = 165.0\n"
        "These are degrees, not suggested ratings; use the mechanism's real limits.\n"
        "No PhysX schema or gains should be added merely to make Newton pass.\n%s"
    ) % (total_dof, passive_count, _FRS_SPEC_REFERENCE)


def _fix_message_bbox_explode(joint_name, seg_name, bbox_msg):
    return (
        "FRS: Joint '%s' (segment %s): sampled bounding-box explosion: %s.\n"
        "This reports growth beyond the configured safety ratio, not its cause.\n"
        "Check imported body mass/inertia, actuator controls, joint/axis mapping,\n"
        "base pinning, test gravity setup and solver support before classifying an asset defect.\n"
        "UsdPhysics mass/inertia properties are physics:mass / physics:diagonalInertia;\n"
        "inspect the values actually imported by Newton rather than prescribing PhysX schemas.\n"
        "Author angular position limits in degrees and linear limits in stage-distance units.\n"
        "Capture the original asset, plan, video, diagnostics and installed engine versions.\n%s"
    ) % (joint_name, seg_name, bbox_msg, _FRS_SPEC_REFERENCE)


def _fix_message_rest_violation(joint_name, seg_name, seg_end, violations, total):
    return (
        "FRS: Joint '%s' failed hold check at segment '%s' (target %.3f).\n"
        "  Observations outside rest_tolerance: %d/%d (more than half the hold window).\n"
        "This is a sampled tracking criterion, not continuous stability proof. Targets\n"
        "are configured inset/capped destinations, not necessarily authored endpoints.\n"
        "Check the actual commands, imported actuator settings, units, mimic coupling,\n"
        "mass/inertia, base setup and Newton backend support before diagnosing the asset.\n"
        "Inspect pause_at_limits_seconds, rest_tolerance and rest_check_fatal in the saved plan;\n"
        "do not loosen policy or rewrite gains just to force a pass. Runtime angular targets\n"
        "are radians; authored USD angular limits are degrees.\n%s"
    ) % (joint_name, seg_name, seg_end, violations, total, _FRS_SPEC_REFERENCE)


def _fix_message_zero_return(joint_name, observed, target, tolerance):
    return (
        "FRS: Joint '%s' failed zero/rest-return: observed %.4f, commanded target %.4f,\n"
        "tolerance %.4f. Zero is clamped to the feasible in-range rest destination.\n"
        "These values are runtime joint coordinates, not authored USD angular limits.\n"
        "Inspect the preceding command/readback history, imported limits and actuator controls,\n"
        "mimic coupling and test settling window before assigning a cause. USD angular\n"
        "limits use degrees; runtime revolute positions use radians. Linear limits use\n"
        "stage-distance units. Any justified repair/tuning belongs outside Evaluate;\n"
        "preserve the original asset and evidence.\n%s"
    ) % (joint_name, observed, target, tolerance, _FRS_SPEC_REFERENCE)


def _fix_message_aggregate(failed, total, failure_names):
    return (
        "FRS: %d/%d joints failed the configured sweep criterion.\n"
        "  Failing joints: %s.\n"
        "Review each joint's bbox, hold-window and zero/rest-return evidence. A failure\n"
        "does not establish wrong gains or an asset defect. Check the selected backend,\n"
        "imported controls/units, prerequisites and saved test configuration first.\n"
        "Do not add PhysX schemas, raise ratings or loosen tolerance to force a pass.\n%s"
    ) % (failed, total, ", ".join(failure_names), _FRS_SPEC_REFERENCE)


# --------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------


def get_defaults():
    # type: () -> dict[str, Any]
    return {
        "settle_seconds": 1.0,
        "sweep_margin_ratio": 0.10,
        "interpolation_profile": "smoothstep",
        # Retain 1/speed_scale as the fallback floor; known speed hints also
        # pace the interpolation profile's peak below min(1, speed_scale).
        "sweep_speed_scale": 0.8,
        "sweep_settling_allowance_seconds": 0.25,
        "max_sweep_segment_seconds": 60.0,
        "max_sweep_simulation_seconds": 600.0,
        "max_sweep_wall_seconds": 3360.0,
        # pause_at_limits was 0.5s; dropped to 0.15s after timing analysis
        # showed the three per-joint pauses (x6 joints) produced dead
        # time with no movement to observe.
        "pause_at_limits_seconds": 0.15,
        # Newton can still be ringing after the final full-range reversal even
        # when it tracked the ramp correctly. Keep commanding the authored home
        # target until it remains inside the unchanged verdict tolerance for a
        # short window, bounded by this timeout.
        "newton_zero_max_settling_seconds": 2.0,
        "newton_zero_consecutive_frames": 8,
        "zero_return_tolerance": 0.01,
        "limit_tolerance": 0.02,
        "bbox_explode_ratio": 10.0,
        "rest_check_enabled": True,
        "rest_tolerance": 0.1,
        # A full-range pass must mean the joint reached and held both commanded
        # extremes. The previous False default allowed a joint with every rest
        # frame outside tolerance to pass, producing visibly false-positive
        # Newton results.
        "rest_check_fatal": True,
        "max_sweep_range": math.tau,
        "physics_fps": 240.0,
        # Video cadence does not set simulation time or ramp duration.
        "capture_fps": 8,
    }


# --------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------


def _finite_config_number(value, name):
    """Reject coercions and non-finite values before they can disable a verdict."""
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError("FRS %s must be a finite real number" % name)
    return float(value)


def _verdict_threshold(value, name, *, positive=False):
    value = _finite_config_number(value, name)
    if value < 0 or (positive and value == 0):
        raise ValueError("FRS %s must be %s" % (name, "positive" if positive else "non-negative"))
    return value


def _boolean_config_value(value, name):
    """Keep explicit diagnostic policies distinct from malformed falsey values."""
    if type(value) is not bool:
        raise ValueError("FRS %s must be a boolean" % name)
    return value


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
    # type: (Any, FrozenSet[int]) -> list[tuple[int, str]]
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
    # type: (float, float, float, float, float, float, float, str) -> dict[str, Any]
    """Compute legal inset targets and frame counts for one joint.

    A genuinely capped interval prefers a zero-centered window, shifted as
    needed to fit entirely within the runtime limits. A relative tolerance of
    one part per million treats float32 imports and the legacy ``2 * 3.14159``
    cap as equal to a full turn, rather than changing the sweep interval.
    """
    if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
        raise ValueError("FRS joint '%s' requires finite ordered position limits" % joint_name)
    if not (math.isfinite(margin_ratio) and 0.0 <= margin_ratio < 0.5):
        raise ValueError("FRS sweep_margin_ratio must be finite and in [0, 0.5)")
    if not math.isfinite(max_sweep_range):
        raise ValueError("FRS max_sweep_range must be finite; use a non-positive value for no cap")
    effective_lo = lo
    effective_hi = hi
    full_range = hi - lo
    if not math.isfinite(full_range):
        raise ValueError("FRS joint '%s' position range must be finite" % joint_name)
    if (
        max_sweep_range > 0
        and full_range > max_sweep_range
        and not math.isclose(full_range, max_sweep_range, rel_tol=1e-6, abs_tol=0.0)
    ):
        half_range = max_sweep_range / 2.0
        center = min(max(0.0, lo + half_range), hi - half_range)
        effective_lo = max(lo, center - half_range)
        effective_hi = min(hi, center + half_range)

    margin = abs(effective_hi - effective_lo) * margin_ratio
    min_target = min(hi, max(lo, effective_lo + margin))
    max_target = min(hi, max(lo, effective_hi - margin))
    zero_target = 0.0
    if zero_target < lo:
        zero_target = lo + margin
    elif zero_target > hi:
        zero_target = hi - margin
    zero_target = min(hi, max(lo, zero_target))

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


def interpolate_sweep_target(seg_start, seg_end, eased, lo, hi):
    # type: (float, float, float, float, float) -> float
    """Bound the ramp command, including endpoint floating-point roundoff."""
    return min(hi, max(lo, seg_start + (seg_end - seg_start) * eased))


def build_sweep_segments(q_start, params):
    # type: (float, dict[str, Any]) -> list[tuple[float, float, str]]
    """Return [(start, end, name), ...] for the 3-phase sweep."""
    return [
        (q_start, params["max_target"], "to_max"),
        (params["max_target"], params["min_target"], "to_min"),
        (params["min_target"], params["zero_target"], "to_zero"),
    ]


def rest_window_failed(violations, total_frames):
    # type: (int, int) -> bool
    """Return whether most endpoint-hold frames missed the target tolerance."""
    total_frames = int(total_frames)
    return total_frames > 0 and int(violations) > total_frames // 2


def update_convergence_count(error, tolerance, consecutive_count):
    # type: (float, float, int) -> int
    """Count consecutive in-tolerance samples, resetting on ringing."""
    if math.isfinite(error) and error <= tolerance:
        return int(consecutive_count) + 1
    return 0


def command_single_joint_position(robot, joint_idx, target):
    # type: (Any, int, float) -> None
    """Command one joint while preserving the other articulation targets.

    Newton's native actuator bridge consumes the current control input every
    simulation step; unlike a persistent USD DriveAPI target, a previously
    submitted ``ArticulationAction`` is not guaranteed to remain active during
    an endpoint hold. Reissuing the endpoint is therefore required for the rest
    window to measure holding behavior rather than an absent command.
    """
    sparse_command = getattr(robot, "set_joint_position_target", None)
    if sparse_command is not None:
        sparse_command(joint_idx, target)
        return

    # Compatibility for lightweight third-party/test handles that implement
    # only the original full-array API.
    positions = _required_positions(robot, "FRS")
    positions[joint_idx] = target
    robot.set_joint_position_targets(positions)


# --------------------------------------------------------------------
# Async runner (Kit-only)
# --------------------------------------------------------------------


async def run_full_range_sweep(ctx, robot, scene_info, config, started_at=None):
    """Keep partial timing evidence without masking an original failure/cancellation."""
    diagnostics = SweepDiagnostics(ctx)
    try:
        await _run_full_range_sweep(ctx, robot, scene_info, config, started_at, diagnostics)
    except BaseException as error:
        try:
            diagnostics.finish(error)
        except BaseException:
            # Optional recording during unwinding must never replace the
            # original required error, cancellation, or system exit.
            pass
        raise
    else:
        diagnostics.finish()


async def _run_full_range_sweep(ctx, robot, scene_info, config, started_at, diagnostics):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
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
    margin_ratio = _finite_config_number(config.get("sweep_margin_ratio", 0.10), "sweep_margin_ratio")
    if not 0.0 <= margin_ratio < 0.5:
        raise ValueError("FRS sweep_margin_ratio must be in [0, 0.5)")
    profile = str(config.get("interpolation_profile", "smoothstep"))
    speed_scale = float(config.get("sweep_speed_scale", 0.8))
    pause_seconds = float(config.get("pause_at_limits_seconds", 0.15))
    zero_tolerance = _verdict_threshold(config.get("zero_return_tolerance", 0.01), "zero_return_tolerance")
    bbox_ratio_limit = _verdict_threshold(config.get("bbox_explode_ratio", 10.0), "bbox_explode_ratio", positive=True)
    rest_enabled = _boolean_config_value(config.get("rest_check_enabled", True), "rest_check_enabled")
    rest_tolerance = _verdict_threshold(config.get("rest_tolerance", 0.1), "rest_tolerance")
    rest_fatal = _boolean_config_value(config.get("rest_check_fatal", True), "rest_check_fatal")
    max_sweep_range = _finite_config_number(config.get("max_sweep_range", math.tau), "max_sweep_range")
    active_engine = str(scene_info.get("active_physics_engine") or "").lower()
    newton_zero_max_settling_seconds = _verdict_threshold(
        config.get("newton_zero_max_settling_seconds", 2.0), "newton_zero_max_settling_seconds"
    )
    newton_zero_consecutive_frames = _finite_config_number(
        config.get("newton_zero_consecutive_frames", 8), "newton_zero_consecutive_frames"
    )
    if newton_zero_consecutive_frames <= 0 or not newton_zero_consecutive_frames.is_integer():
        raise ValueError("FRS newton_zero_consecutive_frames must be a positive integer")
    newton_zero_consecutive_frames = int(newton_zero_consecutive_frames)

    budget = SweepBudget(config, started_at=started_at)
    diagnostics.attach(budget)
    diagnostics.position(None, "initial_settle")
    diagnostics.publish()
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

    # Emit progress every HB_EVERY requested physics steps so a healthy sweep
    # remains observable to the engine's configured output-inactivity watchdog.
    # This cadence is nominal simulation-step spacing, not a wall-time guarantee:
    # slow rendering or native steps can lengthen the gap between messages.
    HB_EVERY = 40

    # Overlays still disabled (# OVERLAY-DISABLED). They are visual-only
    # and were on the suspect list before we pinned the real cause to the
    # runner watchdog; re-enable one at a time after captures confirm green.
    # show_overlay(stage, camera_path, "FRS FULL RANGE SWEEP\nSETTLING")
    ctx.step("FRS: initial settle %ds (%d frames)" % (int(settle_seconds), int(settle_seconds * physics_fps)))
    velocity_hints = resolve_velocity_hints(robot, scene_info)
    settle_frames = math.ceil(settle_seconds * physics_fps)
    budget.reserve(settle_frames)
    for settle_frame in range(settle_frames):
        await budget.step_one(ctx)
        if settle_frame % HB_EVERY == 0:
            ctx.step("FRS initial settle %d/%d" % (settle_frame + 1, settle_frames))
    # update_overlay_transform(stage, camera_path)  # OVERLAY-DISABLED

    with diagnostics.measure("bounds"):
        baseline_bbox = freeze_bbox_reference(
            compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "frs"
        )
    ctx.add_metric("frs_bbox_baseline_volume", baseline_bbox.volume)

    joints_passed = 0
    joints_failed = 0
    failed_names = []
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    frame_counter = 0
    timing_records = []
    ctx.add_metric("frs_segment_timing", timing_records)

    for jnum, (joint_idx, joint_name) in enumerate(joints, start=1):
        diagnostics.position(joint_name, "planning")
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

        start_positions = _required_positions(robot, "FRS")
        if jnum == 1:
            diagnostics.estimate_plan(
                joints,
                lowers,
                uppers,
                start_positions,
                velocity_hints,
                config,
                compute_sweep_parameters,
                build_sweep_segments,
                segment_frames,
                newton_convergence_seconds=newton_zero_max_settling_seconds if active_engine == "newton" else 0.0,
            )
            diagnostics.publish()
        q_start = float(start_positions[joint_idx])
        segments = build_sweep_segments(q_start, params)
        velocity_hint, velocity_source = velocity_hints[joint_idx]
        joint_errors = []

        from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_history import (
            make_joint_observer,
        )

        motion = make_joint_observer(
            ctx,
            scene_info,
            joint_name,
            "frs_joint_%03d" % jnum,
            {
                "position": {"unit": "{joint}", "source": "RobotHandle articulation position readback"},
                "target": {"unit": "{joint}", "source": "position command issued by test"},
                "final_goal": {"unit": "{joint}", "source": "current sweep segment destination"},
                "error": {"unit": "{joint}", "source": "command minus measured position"},
            },
            metadata={
                "physics_fps": physics_fps,
                "clock_basis": "cumulative observed step count / configured physics fps; capture ticks excluded",
                "runtime_lower": lo,
                "runtime_upper": hi,
                "runtime_limit_source": "RobotHandle.get_joint_position_limits(); native articulation limit readback, not raw USD authored limits",
                "rest_tolerance": rest_tolerance,
                "velocity_hint_native_per_second": velocity_hint,
                "velocity_hint_source": velocity_source,
                "timing_basis": "profile peak * native distance / scaled speed hint, bounded by configured simulation and wall budgets",
                "zero_return_tolerance": zero_tolerance,
                "tolerance_basis": "existing native joint-position verdict thresholds",
            },
        )
        motion_steps = 0

        def _sample_motion(issued_target, final_goal, phase, position=None):
            with diagnostics.measure("optional_motion"):
                _sample_motion_impl(issued_target, final_goal, phase, position)

        def _sample_motion_impl(issued_target, final_goal, phase, position=None, motion=motion, joint_idx=joint_idx):
            nonlocal motion_steps
            motion_steps += 1
            if motion.history is None:
                return
            if position is None:
                # This read is diagnostic-only. The original required endpoint
                # and heartbeat readbacks below keep their exception behavior.
                try:
                    position = float(robot.get_joint_positions()[joint_idx])
                except Exception:
                    motion._warn()
            motion.sample(
                {
                    "position": position,
                    "target": issued_target,
                    "final_goal": final_goal,
                    "error": issued_target - position if position is not None else None,
                },
                motion_steps / physics_fps,
                phase,
            )

        for seg_start, seg_end, seg_name in segments:
            diagnostics.position(joint_name, seg_name)
            # Each segment starts at the *measured* position. A preceding
            # endpoint can be missed while its hold still records an asset
            # failure; ramping from that requested endpoint would turn the
            # next segment's first command into an unpaced setpoint jump.
            observed_start = q_start if seg_name == "to_max" else float(_required_positions(robot, "FRS")[joint_idx])
            seg_frames = segment_frames(seg_start, seg_end, observed_start, velocity_hint, config, params["seg_frames"])
            budget.reserve(seg_frames + params["pause_frames"])
            diagnostics.publish()
            first_eased = interpolate_profile(profile, 1.0 / seg_frames)
            first_raw = observed_start + (seg_end - observed_start) * first_eased
            if not math.isfinite(first_raw):
                raise RuntimeError("FRS initial command is non-finite; runtime/setup state is invalid")
            first_command = interpolate_sweep_target(observed_start, seg_end, first_eased, lo, hi)
            first_speed = abs(first_command - observed_start) * physics_fps
            if not math.isfinite(first_speed):
                raise RuntimeError(
                    "FRS initial legal command step has an invalid speed; runtime/setup state is invalid"
                )
            if len(timing_records) < 192:
                timing_records.append(
                    {
                        "joint": joint_name,
                        "segment": seg_name,
                        "requested_start": seg_start,
                        "observed_start": observed_start,
                        "ramp_seconds": seg_frames / physics_fps,
                        "velocity_hint_native_per_second": velocity_hint,
                        "velocity_hint_source": velocity_source,
                        "initial_command_clipped": first_command != first_raw,
                        "estimated_initial_command_step_speed": first_speed,
                    }
                )
                ctx.add_metric("frs_segment_timing", timing_records)
            if velocity_hint is not None:
                allowance = velocity_hint * min(1.0, speed_scale)
                if first_speed > allowance and not math.isclose(first_speed, allowance, rel_tol=1e-12):
                    raise RuntimeError(
                        "FRS first legal command for joint %s exceeds its qualified speed allowance; "
                        "the live start and test timing cannot fit this window, a runtime/setup error "
                        "not an evaluated asset failure" % str(joint_name)[:128]
                    )
            ctx.step(
                "FRS j=%s seg=%s begin (%d ticks, %.3fs simulation, speed hint=%s, source=%s)"
                % (joint_name, seg_name, seg_frames, seg_frames / physics_fps, velocity_hint, velocity_source)
            )
            for frame in range(seg_frames):
                t = (frame + 1) / float(seg_frames)
                eased = interpolate_profile(profile, t)
                target = interpolate_sweep_target(observed_start, seg_end, eased, lo, hi)
                with diagnostics.measure("commands"):
                    command_single_joint_position(robot, joint_idx, target)
                await budget.step_one(ctx)
                _sample_motion(target, seg_end, seg_name)

                if frame % 20 == 0:
                    with diagnostics.measure("bounds"):
                        current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
                        msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                    if msg:
                        joint_errors.append(_fix_message_bbox_explode(joint_name, seg_name, msg))

                if frame_counter % capture_interval == 0:
                    with diagnostics.measure("camera"):
                        ctx.scene.update_camera_follow(update_history=True)
                    with diagnostics.measure("captures"):
                        fp = await ctx.capture_frame(
                            label="full_range_sweep_%03d_%s_%04d" % (jnum, seg_name, frame),
                            stabilize_frames=0,
                        )
                    budget.check_wall()
                    if fp:
                        capture_frames.append(fp)
                        with diagnostics.measure("optional_motion"):
                            motion.record_capture(fp)
                else:
                    with diagnostics.measure("camera"):
                        ctx.scene.update_camera_follow(update_history=False)

                if frame % HB_EVERY == 0:
                    observed = _required_positions(robot, "FRS")
                    observed_position = float(observed[joint_idx])
                    follower_trace = ", ".join(
                        "%s=%.3f" % (robot.dof_names[int(index)], float(observed[int(index)]))
                        for index in follower_indices
                        if int(index) < len(observed)
                    )
                    ctx.step(
                        "FRS j=%s seg=%s frame=%d/%d target=%.3f observed=%.3f followers=[%s]"
                        % (
                            joint_name,
                            seg_name,
                            frame,
                            seg_frames,
                            target,
                            observed_position,
                            follower_trace,
                        )
                    )
                frame_counter += 1

            if rest_enabled:
                diagnostics.position(joint_name, seg_name + "_hold")
                rest_violations = 0
                for pframe in range(params["pause_frames"]):
                    with diagnostics.measure("commands"):
                        command_single_joint_position(robot, joint_idx, seg_end)
                    await budget.step_one(ctx)
                    positions = _required_positions(robot, "FRS")
                    _sample_motion(seg_end, seg_end, seg_name + "_hold", float(positions[joint_idx]))
                    if abs(float(positions[joint_idx]) - float(seg_end)) > rest_tolerance:
                        rest_violations += 1
                    frame_counter += 1
                    if pframe % 12 == 0 or pframe == params["pause_frames"] - 1:
                        ctx.step(
                            "FRS j=%s seg=%s rest=%d/%d target=%.3f observed=%.3f"
                            % (
                                joint_name,
                                seg_name,
                                pframe,
                                params["pause_frames"],
                                seg_end,
                                float(positions[joint_idx]),
                            )
                        )
                if rest_window_failed(rest_violations, params["pause_frames"]):
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
                diagnostics.position(joint_name, seg_name + "_pause")
                for pframe in range(params["pause_frames"]):
                    await budget.step_one(ctx)
                    _sample_motion(seg_end, seg_end, seg_name + "_pause")
                    frame_counter += 1
                    if pframe % HB_EVERY == 0:
                        ctx.step("FRS j=%s seg=%s pause %d/%d" % (joint_name, seg_name, pframe, params["pause_frames"]))

        if active_engine == "newton" and newton_zero_max_settling_seconds > 0.0:
            diagnostics.position(joint_name, "zero_convergence")
            stabilization_frames = max(1, int(newton_zero_max_settling_seconds * physics_fps))
            ctx.step(
                "FRS j=%s: Newton zero convergence (up to %d frames, %d consecutive required)"
                % (joint_name, stabilization_frames, newton_zero_consecutive_frames)
            )
            consecutive = 0
            for settle_frame in range(stabilization_frames):
                with diagnostics.measure("commands"):
                    command_single_joint_position(robot, joint_idx, params["zero_target"])
                await budget.step_one(ctx)
                observed = float(_required_positions(robot, "FRS")[joint_idx])
                _sample_motion(params["zero_target"], params["zero_target"], "zero_convergence", observed)
                error = abs(observed - params["zero_target"])
                consecutive = update_convergence_count(error, zero_tolerance, consecutive)
                if settle_frame % HB_EVERY == 0:
                    ctx.step(
                        "FRS j=%s zero settle=%d/%d observed=%.4f error=%.4f stable=%d/%d"
                        % (
                            joint_name,
                            settle_frame,
                            stabilization_frames,
                            observed,
                            error,
                            consecutive,
                            newton_zero_consecutive_frames,
                        )
                    )
                if consecutive >= newton_zero_consecutive_frames:
                    break

        final_positions = _required_positions(robot, "FRS")
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

        with diagnostics.measure("optional_motion"):
            motion.finish("sweep_sequence_completed")

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
        diagnostics.position(None, "encoding")
        with diagnostics.measure("encoding"):
            ctx.encode_video(capture_frames, fps=capture_fps, label="full_range_sweep", role="summary")
    budget.check_wall()
    ctx.add_metric("frs_completed_nominal_simulation_seconds", budget.ticks / physics_fps)
    ctx.add_metric("frs_segment_timing_omitted", max(0, len(joints) * 3 - len(timing_records)))

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

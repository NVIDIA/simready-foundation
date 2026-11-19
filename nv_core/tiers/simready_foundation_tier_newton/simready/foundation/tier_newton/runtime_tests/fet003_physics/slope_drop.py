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

"""FET003 Slope Drop test (RB.COL.001 -- collider capability).

WHAT: Place the asset above a 45-degree slope. A valid result requires
      the AABB proximity indication, signed downhill movement and the
      configured overlap/separation checks. A valid downhill exit can
      leave the finite ramp; an uphill launch does not disable separation
      checks. These observations are geometry proxies, not contact points.

HOW:  1. Load asset in room with collision ground + slope.
      2. Place asset at the top of the slope.
      3. Run pre-simulation safeguards (world-anchor, rigid body checks).
      4. Simulate at 240fps with camera follow.
      5. Watch the AABB's signed distance interval from the ramp plane.
         Recognize proximity while its centre is above the finite ramp.
         Watch the bbox centre Y each frame. When downhill displacement
         from the start position exceeds
         ``horizontal_movement_threshold`` (default 0.01m), the asset is
         sliding.
      6. After proximity, require consecutive excessive-separation samples
         before failing; only a qualified downhill exit is exempt. Once
         downhill movement is detected, keep simulating for
         ``post_horiz_seconds`` (default 3s) and watch z_min. If it
         ever drops below floor_level - floor_margin during that window,
         that is a penetration failure.
      7. After a clean window, stop: the sampled motion and configured
         overlap/separation proxies passed. This is not collider-fidelity
         or continuous-contact proof.
      8. If no horizontal movement within ``simulation_seconds``, FAIL.

WHY:  RB.COL.001 requires collider capability.  The slope introduces
      lateral forces that stress the collision mesh differently than a
      vertical drop.  Sliding along a surface exposes gaps and thin-
      geometry tunneling that a straight drop may miss.  Horizontal
      movement is the direct signal that the asset is sliding, so
      detecting signed downhill displacement and evaluating the configured
      ramp/floor proxies provides this procedure's sampled evidence.

FALSE POSITIVE AVOIDANCE:
  - horizontal_movement_threshold (0.01m) ignores micro-jitter from solver.
  - Cumulative downhill displacement from the initial centre (not per-frame)
    works at high fps where per-frame deltas are tiny.
  - floor_margin (default 0.1 stage units) is an allowed AABB floor-overlap
    proxy, not a measured contact offset or floating-point error estimate.
  - The default 3s post-downhill window observes floor overlap; a threshold
    breach fails immediately. Ramp separation requires its own consecutive
    confirmation window (default 0.1 nominal simulation seconds).
  - World-anchor detection skips test for anchored assets.
  - RigidBody pre-check catches assets with no physics setup.
  - Newton initialization is checked before evaluated motion.
  - Required bounds follow complete live body geometry, not stale USD poses.
  - RoomHandle.add_slope authors the generated ramp's physics material and
    binding; those test-fixture properties are distinct from the asset's.
"""

import math
from typing import Any

from simready.evaluate.core.decorator import test
from simready.evaluate.core.output_layout import UnsafeEvidencePathError
from simready.foundation.tier_newton.runtime_tests.placement_compat import place_with_minimum_clearance
from simready.foundation.tier_newton.runtime_tests._assessment import (
    _has_complete_scene_asset,
    not_applicable,
)


def _apply_ground_friction():
    """Require the same locally owned, qualified floor fixture as ground drop."""
    from simready.foundation.tier_newton.runtime_tests.fet003_physics._ground_trial import (
        apply_ground_physics_material,
    )

    apply_ground_physics_material("/World/GroundPlane")


def _slope_plane_distance_interval(
    bounds: Any,
    slope_center_z: float,
    slope_tangent: float,
) -> tuple[float, float]:
    """Return the world AABB's signed-distance interval from the ramp plane.

    The ramp plane is ``z + y * slope_tangent - slope_center_z = 0``.
    Projecting all eight AABB corners onto its unit normal accounts for the
    incline and avoids treating ``bbox.min.z`` at the centre Y as a contact
    distance. The latter produces false gaps for curved bodies such as a
    sphere tangent to a 45-degree ramp.
    """
    min_y = float(bounds.min[1])
    max_y = float(bounds.max[1])
    min_z = float(bounds.min[2])
    max_z = float(bounds.max[2])
    tangent = float(slope_tangent)
    normal_length = math.sqrt(1.0 + tangent * tangent)
    min_support_y = min_y if tangent >= 0.0 else max_y
    max_support_y = max_y if tangent >= 0.0 else min_y
    minimum_distance = (min_z + min_support_y * tangent - float(slope_center_z)) / normal_length
    maximum_distance = (max_z + max_support_y * tangent - float(slope_center_z)) / normal_length
    return minimum_distance, maximum_distance


def _report_result(ctx: Any, state: dict, physics_fps: int, sim_seconds: float) -> None:
    """Emit metrics and pass/fail for the slope drop test."""
    contact_detected = state["contact_detected"]
    horiz_detected = state["horiz_detected"]
    horiz_frame = state["horiz_frame"]
    penetrated = state["penetrated"]
    slope_penetrated = state["slope_penetrated"]
    excessive_separation = state["excessive_separation"]
    uphill_motion = state["uphill_motion"]
    motion_passed = (
        contact_detected and horiz_detected and not penetrated and not slope_penetrated and not excessive_separation
    )
    post_slide_completed = state["post_slide_completed"]
    passed = motion_passed and post_slide_completed

    ctx.add_metric("slope_drop_contact_detected", 1 if contact_detected else 0)
    ctx.add_metric("slope_drop_horiz_detected", 1 if horiz_detected else 0)
    ctx.add_metric("slope_drop_penetrated", 1 if penetrated else 0)
    ctx.add_metric("slope_drop_slope_penetrated", 1 if slope_penetrated else 0)
    ctx.add_metric("slope_drop_excessive_separation", 1 if excessive_separation else 0)
    ctx.add_metric("slope_drop_uphill_motion", 1 if uphill_motion else 0)
    ctx.add_metric("slope_drop_passed", 1 if passed else 0)
    ctx.add_metric("slope_drop_post_slide_completed", 1 if post_slide_completed else 0)
    ctx.add_metric("slope_drop_post_slide_observed_frames", state["post_slide_observed_frames"])
    ctx.add_metric("slope_drop_post_slide_required_frames", state["post_slide_required_frames"])
    ctx.add_metric("slope_drop_max_clearance", round(state["max_clearance"], 4), unit="stage_length")
    ctx.add_metric("slope_drop_separation_frames", state["separation_frames"])
    if state["separation_frame"] >= 0:
        ctx.add_metric("slope_drop_separation_frame", state["separation_frame"])
    if state["left_slope_frame"] >= 0:
        ctx.add_metric("slope_drop_left_slope_frame", state["left_slope_frame"])
    if horiz_frame >= 0:
        ctx.add_metric("slope_drop_horiz_time", round(horiz_frame / float(physics_fps), 3))

    if motion_passed and not post_slide_completed:
        raise RuntimeError(
            "Slope drop observation incomplete: observed %d of %d required post-travel steps before the "
            "nominal simulation budget ended. This is incomplete test execution, not an asset-response failure."
            % (state["post_slide_observed_frames"], state["post_slide_required_frames"])
        )

    if not passed:
        diagnostic_guidance = (
            "\n\nThe cause has not been established; it may involve the collider or the simulation/test setup. "
            "This result does not establish an asset-authoring defect. "
            "Report this failure to the test owner with the result JSON, video, motion history (when available), "
            "and engine log. The test owner should investigate the setup and physics backend; "
            "you do not need to configure the backend or change the asset to diagnose this result."
        )
        if slope_penetrated:
            ctx.fail(
                "Slope drop FAILED: The entire bounding box fell below the ramp plane beyond the configured allowance. "
                "This is a bounding-box proxy, not measured collider penetration." + diagnostic_guidance
            )
        elif not contact_detected:
            ctx.fail(
                "Slope drop FAILED: The ramp proximity proxy was not detected before moving or timing out. "
                "This proxy does not measure physical contact." + diagnostic_guidance
            )
        elif excessive_separation:
            ctx.fail(
                "Slope drop FAILED: The asset remained too far from the ramp after contact "
                "for %d consecutive observed step(s); peak bounding-box clearance %.4f stage units at step %d. "
                "The ramp contact indication is a proximity proxy, not a measured collision."
                % (
                    state["separation_frames"],
                    state["max_clearance"],
                    state["separation_frame"],
                )
                + diagnostic_guidance,
                details={
                    "maximum_clearance_stage_length": round(state["max_clearance"], 6),
                    "separation_frame": state["separation_frame"],
                    "consecutive_separation_frames": state["separation_frames"],
                },
            )
        elif not horiz_detected:
            observation = (
                "Upward-slope displacement was observed instead of the required downhill travel. "
                if uphill_motion
                else "The required downhill displacement threshold was not reached. "
            )
            ctx.fail(
                "Slope drop FAILED: Required downhill displacement was not detected within "
                "%.0f nominal step seconds. " % sim_seconds + observation + diagnostic_guidance
            )
        else:
            ctx.fail(
                "Slope drop FAILED: Bounding-box floor overlap exceeded the configured allowance after "
                "movement; this is not measured collider penetration." + diagnostic_guidance
            )
        return

    ctx.log(
        "Slope drop PASSED: downhill displacement at %.2fs nominal step time; overlap proxies within allowance"
        % (horiz_frame / float(physics_fps))
    )


async def _run_simulation(ctx, cfg):
    # type: (object, dict) -> tuple
    """Run the physics simulation loop. Returns (frames, state dict).

    Flow:
      - Require ramp-proximity detection followed by sufficient signed +Y
        displacement from the initial center. This is a downhill-motion proxy,
        not proof of physical sliding contact.
      - After sliding is detected, keep simulating for
        ``post_horiz_frames`` frames watching for penetration.
      - Stop as soon as the post-horizontal window has elapsed without
        penetration.  Anything beyond that is wasted sim + capture time.
    """
    from simready.foundation.tier_newton.runtime_tests.fet003_physics._drop_config import (
        validate_slope_observation_config,
    )

    validate_slope_observation_config(cfg)
    frames = []
    initial_y = None
    contact_detected = False
    horiz_detected = False
    post_slide_completed = False
    horiz_frame = -1
    penetrated = False
    slope_penetrated = False
    excessive_separation = False
    separation_frames = 0
    separation_frame = -1
    left_slope_frame = -1
    max_clearance = 0.0
    uphill_motion = False
    observed_frames = 0
    from simready.foundation.tier_newton.runtime_tests.motion_observer import (
        MotionObserver,
        drop_metadata,
    )

    motion = MotionObserver(
        ctx,
        "slope_drop",
        {
            "center_y": {"unit": "stage_length", "source": "runtime world-aligned bounding box center"},
            "minimum_z": {"unit": "stage_length", "source": "runtime world-aligned bounding box minimum"},
            "clearance": {"unit": "stage_length", "source": "AABB minimum signed ramp-plane distance"},
            "maximum_plane_distance": {"unit": "stage_length", "source": "AABB maximum signed ramp-plane distance"},
            "downhill_displacement": {"unit": "stage_length", "source": "AABB center Y minus initial center Y"},
            "contact_tolerance": {"unit": "stage_length", "source": "test contact proxy threshold"},
        },
        metadata={
            **drop_metadata(ctx, cfg.get("physics_fps"), getattr(ctx, "config", {}).get("capture_fps")),
            "clock_basis": "nominal observed step index / configured physics fps; capture ticks are not counted",
            "contact_basis": "AABB ramp-plane distance, not measured contact force",
            "slope_overlap_allowance_stage_length": cfg["slope_penetration_tolerance"],
            "ramp_proximity_tolerance_stage_length": cfg["contact_tolerance"],
            "floor_overlap_limit_stage_length": cfg["pen_threshold"],
            "finite_ramp_exit_allowed": True,
            "ramp_separation_exit_policy": (
                "exempt only beyond downhill edge with positive downhill displacement; uphill exits remain checked"
            ),
        },
    )

    async def capture_terminal_observation():
        """Record a near-terminal render when a measured guard ends early."""
        try:
            capture = await ctx.capture_frame(label="slope_drop")
        except UnsafeEvidencePathError:
            raise
        except Exception as exc:
            # Optional terminal media cannot replace an already measured
            # physics result. Cancellation and interrupts still propagate.
            try:
                ctx.warn(f"Terminal slope capture unavailable; measured result retained: {exc}")
            except UnsafeEvidencePathError:
                raise
            except Exception:
                pass
            return
        if capture is None:
            return
        frames.append(capture)
        motion.record_capture(capture)

    for frame in range(cfg["total_frames"]):
        await ctx.physics_step()
        ctx.scene.update_camera_follow()
        bounds = ctx.get_asset_bounds()
        observed_frames += 1
        z_min = bounds.min[2]
        min_y = bounds.min[1]
        max_y = bounds.max[1]
        cy = (min_y + max_y) / 2.0

        if initial_y is None:
            initial_y = cy

        on_slope = cfg["slope_min_y"] <= cy <= cfg["slope_max_y"]
        # Whole-box-below-ramp checking requires the complete footprint to
        # remain over the finite ramp. Post-proximity separation is checked
        # more broadly and exempted only by the qualified downhill-exit guard.
        fully_on_slope = cfg["slope_min_y"] <= min_y and max_y <= cfg["slope_max_y"]
        # Project the complete AABB onto the ramp normal. This measures a
        # geometry-aware separation interval in stage units and handles
        # curved bodies whose minimum Z is not below the plane at centre Y.
        clearance, maximum_plane_distance = _slope_plane_distance_interval(
            bounds,
            cfg["slope_center_z"],
            cfg["slope_tangent"],
        )
        below_ramp = maximum_plane_distance < -cfg["slope_penetration_tolerance"]
        motion.sample(
            {
                "center_y": float(cy),
                "minimum_z": float(z_min),
                "clearance": float(clearance),
                "maximum_plane_distance": float(maximum_plane_distance),
                "downhill_displacement": float(cy - initial_y),
                "contact_tolerance": float(cfg["contact_tolerance"]),
            },
            (frame + 1) / float(cfg.get("physics_fps", 240)),
            "on_ramp" if fully_on_slope else "edge_or_airborne",
        )
        if fully_on_slope and below_ramp:
            slope_penetrated = True
            ctx.step("Slope penetration at frame %d (maximum signed distance=%.4fm)" % (frame, maximum_plane_distance))
            await capture_terminal_observation()
            break
        if on_slope and not below_ramp and clearance <= cfg["contact_tolerance"]:
            contact_detected = True

        # The ramp descends toward +Y. Require signed downhill motion so a
        # sideways launch or Newton contact impulse cannot count as sliding.
        downhill_disp = cy - initial_y
        if contact_detected and downhill_disp <= -cfg["horiz_threshold"]:
            uphill_motion = True
            # A small first-impact rebound is valid. Record it for diagnostics,
            # but do not count it as sliding and keep watching for downhill
            # motion or an excessive launch away from the ramp.
        if contact_detected and not horiz_detected and downhill_disp >= cfg["horiz_threshold"]:
            horiz_detected = True
            horiz_frame = frame
            ctx.step("Downhill movement at frame %d (%.4fm)" % (frame, downhill_disp))

        # A single AABB sample can spike while a tumbling body rotates. Require
        # sustained separation before calling it a launch. Only a downhill
        # exit can exempt the finite ramp: crossing the uphill edge during a
        # launch must not disable the check or turn an earlier slide into a pass.
        downhill_exit = max_y > cfg["slope_max_y"] and downhill_disp >= cfg["horiz_threshold"]
        if contact_detected and not fully_on_slope and left_slope_frame < 0:
            left_slope_frame = frame
        if contact_detected and not downhill_exit:
            max_clearance = max(max_clearance, clearance)
            if clearance > cfg["max_slope_separation"]:
                separation_frames += 1
                if separation_frames >= cfg["separation_confirmation_frames"]:
                    excessive_separation = True
                    separation_frame = frame
                    ctx.step(
                        "Excessive slope separation confirmed at frame %d "
                        "after %d consecutive frame(s) (%.4fm)" % (frame, separation_frames, clearance)
                    )
                    await capture_terminal_observation()
                    break
            else:
                separation_frames = 0
        else:
            separation_frames = 0

        # Penetration is a hard fail any time after we start checking.
        # (We only start checking after horiz is detected so mid-fall
        # below-floor glitches don't fail assets that correctly recover.)
        if horiz_detected and not penetrated and z_min < cfg["pen_threshold"]:
            penetrated = True
            ctx.step("Penetration at frame %d (z=%.3f)" % (frame, z_min))
            await capture_terminal_observation()
            break  # stop after a near-terminal illustrative render

        if frame % cfg["capture_interval"] == 0:
            capture = await ctx.capture_frame(label="slope_drop")
            frames.append(capture)
            motion.record_capture(capture)

        # Stop once the post-horizontal window has been watched clean.
        if horiz_detected and not penetrated and frame - horiz_frame >= cfg["post_horiz_frames"]:
            post_slide_completed = True
            break

        await ctx.physics_advance()

    motion.finish(
        "slope_penetration"
        if slope_penetrated
        else (
            "excessive_separation"
            if excessive_separation
            else (
                "floor_penetration"
                if penetrated
                else "post_slide_window" if post_slide_completed else "step_budget_exhausted"
            )
        )
    )
    state = {
        "horiz_detected": horiz_detected,
        "post_slide_completed": post_slide_completed,
        "post_slide_observed_frames": max(0, observed_frames - 1 - horiz_frame) if horiz_detected else 0,
        "post_slide_required_frames": cfg["post_horiz_frames"],
        "horiz_frame": horiz_frame,
        "penetrated": penetrated,
        "slope_penetrated": slope_penetrated,
        "contact_detected": contact_detected,
        "excessive_separation": excessive_separation,
        "uphill_motion": uphill_motion,
        "max_clearance": max_clearance,
        "separation_frames": separation_frames,
        "separation_frame": separation_frame,
        "left_slope_frame": left_slope_frame,
    }
    return frames, state


# Newton-owned test policy and decorator metadata.
SLOPE_DROP_KWARGS = {
    "description": (
        "Places the asset on a 45° inclined plane with collision; runs "
        "physics; checks downhill displacement and configured bounding-box "
        "ramp-plane and floor overlap/separation proxies over the full configured "
        "post-travel observation window. Leaving the finite "
        "ramp through a qualified downhill exit is allowed; an uphill exit "
        "remains subject to separation checks. Distances are stage units; these observations do "
        "not measure collision contact points or prove collider fidelity."
    ),
    "expected_video": (
        "The asset placed on a tilted ramp. It begins to slide down the "
        "slope under gravity, possibly tumbling and leaving the finite ramp. "
        "The camera follows the object. Compare phases and proxy thresholds "
        "with the footage; apparent mesh overlap is not measured collider "
        "penetration and the clip may end at a failure or observation deadline."
    ),
    "version": "3.3.6",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "max_duration": 600,
    "config_defaults": {
        # simulation_seconds is a hard cap; the loop exits as soon as the
        # post-horizontal window completes.
        "simulation_seconds": 10.0,
        "physics_fps": 240,
        "capture_fps": 15,
        "settle_frames": 5,
        "asset_load_timeout": 30,
        "slope_angle_deg": 45.0,
        "slope_friction": 0.5,
        # Preserve a useful fall for very short assets while the room helper
        # also accounts for the full bbox footprint over the inclined plane.
        "minimum_slope_clearance": 0.1,
        "floor_level": 0.0,
        "floor_margin": 0.1,
        # Minimum signed downhill displacement from the start position
        # (metres) to count as "sliding on the slope".
        "horizontal_movement_threshold": 0.01,
        # Maximum bbox-to-ramp gap used to recognize initial contact, and the
        # maximum allowed separation after contact before declaring a launch.
        "slope_contact_tolerance": 0.02,
        # Excessive overlap requires the whole AABB to lie below the analytic
        # ramp plane beyond this allowance while its footprint is on the ramp.
        # This geometry proxy is not a measured collision penetration depth.
        "slope_penetration_tolerance": 0.02,
        "maximum_slope_separation": 0.05,
        # Require consecutive AABB separation samples after proximity. Only a
        # qualified downhill exit disables this check; uphill exits do not.
        "separation_confirmation_seconds": 0.1,
        # After horizontal movement is detected, keep simulating this
        # long while watching for a penetration event.  No penetration
        # during the window -> PASS. Also sets how much of the slide the
        # video captures, so keep it long enough to show the asset sliding
        # (not just the first instant of motion).
        "post_horiz_seconds": 3.0,
    },
}


@test(
    features=[
        {"id": "FET003_RigidBody.Newton.0-1-0", "version": "*"},
    ],
    name="slope_drop_newton",
    **SLOPE_DROP_KWARGS,
)
async def test_slope_drop_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_slope_drop(ctx)


async def run_slope_drop(ctx):
    """Evaluate signed downhill motion and the configured AABB ramp/floor proxies."""
    from simready.foundation.tier_newton.runtime_tests.fet003_physics._drop_config import (
        validate_drop_config,
    )

    validate_drop_config(ctx.config, slope=True)
    # --- Config ---
    sim_seconds = float(ctx.config["simulation_seconds"])
    physics_fps = int(ctx.config["physics_fps"])
    capture_fps = int(ctx.config["capture_fps"])
    floor_level = float(ctx.config["floor_level"])
    floor_margin = float(ctx.config["floor_margin"])
    post_horiz_secs = float(ctx.config["post_horiz_seconds"])

    sim_cfg = {
        "total_frames": int(sim_seconds * physics_fps),
        "physics_fps": physics_fps,
        "capture_interval": max(1, physics_fps // capture_fps),
        "pen_threshold": floor_level - floor_margin,
        "horiz_threshold": float(ctx.config["horizontal_movement_threshold"]),
        "post_horiz_frames": int(post_horiz_secs * physics_fps),
        "separation_confirmation_frames": max(
            1, int(float(ctx.config["separation_confirmation_seconds"]) * physics_fps)
        ),
    }

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)  # saturated blue walls
    room.show_ground(color=(0.25, 0.35, 0.6))  # darker blue ground
    room.add_slope(angle=ctx.config["slope_angle_deg"], friction=ctx.config["slope_friction"])
    sim_cfg.update(
        {
            "slope_min_y": -room._slope_high_end_y,
            "slope_max_y": room._slope_high_end_y,
            "slope_center_z": room._slope_half_len * math.sin(room._slope_angle_rad) - room._slope_sink,
            "slope_tangent": math.tan(room._slope_angle_rad),
            "contact_tolerance": float(ctx.config["slope_contact_tolerance"]),
            "slope_penetration_tolerance": float(ctx.config["slope_penetration_tolerance"]),
            "max_slope_separation": float(ctx.config["maximum_slope_separation"]),
        }
    )
    clearance_supported = place_with_minimum_clearance(
        room.place_asset_on_slope,
        ctx.config["minimum_slope_clearance"],
    )
    if not clearance_supported:
        ctx.log(
            "The installed simready.evaluate.engine-kit does not support bbox-safe slope clearance; "
            "using legacy slope placement. Upgrade the Benchmark wheels to 2026.8.0rc3 or newer "
            "to enable size-safe placement."
        )

    # --- Pre-simulation safeguards ---
    from simready.foundation.tier_newton.runtime_tests.fet003_physics.physics_checks import (
        has_active_owned_world_anchor,
        run_pre_checks,
    )

    pre_result = run_pre_checks(ctx)
    if pre_result is not None:
        if pre_result.startswith("NA:"):
            reason = pre_result[3:].strip()
            if _has_complete_scene_asset(
                ctx, inspection_includes_instance_proxies=True
            ) and has_active_owned_world_anchor(ctx):
                ctx.add_metric("assessment_applicability", not_applicable("world_anchored", reason))
            ctx.skip(reason)
            ctx.add_metric("slope_drop_skipped", 1)
        elif pre_result.startswith("SKIP:"):
            ctx.precheck_failure(pre_result[5:].strip())
            ctx.add_metric("slope_drop_passed", 0)
        else:
            ctx.fail(pre_result)
            ctx.add_metric("slope_drop_passed", 0)
        return

    # --- Lighting + Physics + camera ---
    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=9.81, fps=float(physics_fps))
    ctx.scene.enable_ground_plane(friction=0.5)
    _apply_ground_friction()
    # V1 pattern: camera from -X side, looking in +X. The slope motion is
    # along Y so the object slides left-to-right in frame.
    ctx.scene.setup_camera_follow(
        {
            "camera_direction": (-1.0, 0.0, 0.2),
        }
    )
    await ctx.settle(count=3)

    # Cook dynamic mesh colliders (and author missing mass) OFF the timeline
    # path, time-boxed, BEFORE play() -- a cold SDF cook triggered by play()
    # can freeze the run. Reports a clean failure if a collider cannot cook.
    from simready.evaluate_engine_kit.physics_utils import cook_skip_message
    from simready.foundation.tier_newton.runtime_tests.engine_guard import (
        NEWTON_SCENE_ERROR,
        NewtonSceneInitializationError,
        articulationize_loose_joints,
        newton_scene_initialized,
    )

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        ctx.add_metric("slope_drop_passed", 0)
        return

    # Under Newton, wrap the asset's loose (maximal-coordinate) joints into a
    # runtime articulation so Newton can build the scene (it aborts on loose
    # joints). The asset's USD on disk is unchanged; PhysX is untouched.
    import omni.usd

    articulationize_loose_joints(ctx, omni.usd.get_context().get_stage())
    await ctx.settle(count=1)

    # Newton scene-init guard (Newton only; PhysX untouched). Report an error
    # when Newton aborts scene init instead of stepping the un-built simulation
    # or counting the requested coverage as a non-blocking skip.
    physics.play()
    await ctx.settle(count=3)
    newton_ready = newton_scene_initialized()
    physics.stop()
    if not newton_ready:
        raise NewtonSceneInitializationError(NEWTON_SCENE_ERROR)

    physics.play()

    # --- Log initial position for physics validation ---
    init_bounds = ctx.get_asset_bounds(authored=True)  # pre-pump placement/setup context, not runtime evidence
    init_cx = (init_bounds.min[0] + init_bounds.max[0]) / 2.0
    init_cy = (init_bounds.min[1] + init_bounds.max[1]) / 2.0
    init_z_min = init_bounds.min[2]
    bbox_height = init_bounds.max[2] - init_bounds.min[2]
    ctx.add_metric("slope_drop_initial_cx", round(init_cx, 4))
    ctx.add_metric("slope_drop_initial_cy", round(init_cy, 4))
    ctx.add_metric("slope_drop_initial_z_min", round(init_z_min, 4))
    ctx.add_metric("slope_drop_bbox_height", round(bbox_height, 4))
    ctx.step("Initial: cx=%.4f, cy=%.4f, z_min=%.4f, bbox_h=%.4f" % (init_cx, init_cy, init_z_min, bbox_height))

    # --- Simulation ---
    ctx.step("Simulating slope drop")
    frames, state = await _run_simulation(ctx, sim_cfg)

    # --- Video + results ---
    if frames:
        ctx.encode_video(frames, fps=capture_fps, label="slope_drop", role="summary")
    _report_result(ctx, state, physics_fps, sim_seconds)

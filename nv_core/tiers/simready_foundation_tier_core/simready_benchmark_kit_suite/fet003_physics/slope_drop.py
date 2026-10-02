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

WHAT: Place the asset on a 45-degree slope.  A valid result requires the
      asset to contact the ramp, move downhill, and remain close to the
      ramp after contact.  This rejects airborne motion and solver
      impulses that previously looked like a successful slide.

HOW:  1. Load asset in room with collision ground + slope.
      2. Place asset at the top of the slope.
      3. Run pre-simulation safeguards (world-anchor, rigid body checks).
      4. Simulate at 240fps with camera follow.
      5. Watch the bbox centre Y each frame.  When downhill displacement
         from the start position exceeds
         ``horizontal_movement_threshold`` (default 0.01m), the asset is
         sliding.
      6. Once sliding is detected, keep simulating for
         ``post_horiz_seconds`` (default 0.5s) and watch z_min.  If it
         ever drops below floor_level - floor_margin during that window,
         that is a penetration failure.
      7. After the clean window, stop -- we have proven "slides" + "no
         penetration" so nothing more needs to be simulated or captured.
      8. If no horizontal movement within ``simulation_seconds``, FAIL.

WHY:  RB.COL.001 requires collider capability.  The slope introduces
      lateral forces that stress the collision mesh differently than a
      vertical drop.  Sliding along a surface exposes gaps and thin-
      geometry tunneling that a straight drop may miss.  Horizontal
      movement is the direct signal that the asset is sliding, so
      detecting it (and then verifying the slope-to-floor transition
      does not produce a penetration) is the cheapest correct check.

FALSE POSITIVE AVOIDANCE:
  - horizontal_movement_threshold (0.01m) ignores micro-jitter from solver.
  - Cumulative downhill displacement from the initial centre (not per-frame)
    works at high fps where per-frame deltas are tiny.
  - floor_margin (0.1m) tolerance for floating-point collision resolution.
  - 0.5s post-horizontal window catches transient vs sustained penetration.
  - World-anchor detection skips test for anchored assets.
  - RigidBody pre-check catches assets with no physics setup.
  - Mesh cooking safeguards in load_asset() prevent PhysX hangs.
  - ctx.get_asset_bounds() tracks actual physics body, not root xform.
  - Ground collision plane has physics material with friction applied.
"""

import math
from typing import Any

from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.placement_compat import place_with_minimum_clearance


def _apply_ground_friction():
    # type: () -> None
    """Apply physics material with friction to the collision ground plane.

    enable_ground_plane() creates collision geometry but does not attach a
    physics material, so friction defaults to PhysX's built-in value.
    This applies a material explicitly for deterministic behavior.
    """
    ground_path = "/World/GroundPlane"
    try:
        import omni.usd
        from pxr import UsdPhysics, UsdShade

        stage = omni.usd.get_context().get_stage()
        gp_prim = stage.GetPrimAtPath(ground_path + "/CollisionMesh")
        if gp_prim.IsValid():
            mat_path = ground_path + "/PhysMaterial"
            mat_prim = stage.DefinePrim(mat_path)
            phys_mat = UsdPhysics.MaterialAPI.Apply(mat_prim)
            phys_mat.CreateStaticFrictionAttr(0.5)
            phys_mat.CreateDynamicFrictionAttr(0.4)
            phys_mat.CreateRestitutionAttr(0.0)
            UsdShade.MaterialBindingAPI.Apply(gp_prim).Bind(
                UsdShade.Material(mat_prim),
                UsdShade.Tokens.weakerThanDescendants,
                "physics",
            )
    except Exception:
        pass


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
    passed = (
        contact_detected and horiz_detected and not penetrated and not slope_penetrated and not excessive_separation
    )

    ctx.add_metric("slope_drop_contact_detected", 1 if contact_detected else 0)
    ctx.add_metric("slope_drop_horiz_detected", 1 if horiz_detected else 0)
    ctx.add_metric("slope_drop_penetrated", 1 if penetrated else 0)
    ctx.add_metric("slope_drop_slope_penetrated", 1 if slope_penetrated else 0)
    ctx.add_metric("slope_drop_excessive_separation", 1 if excessive_separation else 0)
    ctx.add_metric("slope_drop_uphill_motion", 1 if uphill_motion else 0)
    ctx.add_metric("slope_drop_passed", 1 if passed else 0)
    ctx.add_metric("slope_drop_max_clearance", round(state["max_clearance"], 4), unit="m")
    ctx.add_metric("slope_drop_separation_frames", state["separation_frames"])
    if state["separation_frame"] >= 0:
        ctx.add_metric("slope_drop_separation_frame", state["separation_frame"])
    if state["left_slope_frame"] >= 0:
        ctx.add_metric("slope_drop_left_slope_frame", state["left_slope_frame"])
    if horiz_frame >= 0:
        ctx.add_metric("slope_drop_horiz_time", round(horiz_frame / float(physics_fps), 3))

    if not passed:
        if slope_penetrated:
            ctx.fail(
                "Slope drop FAILED: The asset penetrated through the ramp surface. "
                "Review its collider approximation, contact offsets, and the captured video."
            )
        elif not contact_detected:
            ctx.fail(
                "Slope drop FAILED: The asset never contacted the slope before moving or timing out. "
                "Check the collision mesh and the generated ramp contact configuration."
            )
        elif excessive_separation:
            ctx.fail(
                "Slope drop FAILED: The asset remained too far from the ramp after contact "
                "for %d consecutive frame(s); peak clearance %.4fm at frame %d. "
                "Review collision contact gaps, restitution, and the video for an upward launch."
                % (
                    state["separation_frames"],
                    state["max_clearance"],
                    state["separation_frame"],
                ),
                details={
                    "maximum_clearance_m": round(state["max_clearance"], 6),
                    "separation_frame": state["separation_frame"],
                    "consecutive_separation_frames": state["separation_frames"],
                },
            )
        elif not horiz_detected:
            ctx.fail(
                "Slope drop FAILED: No horizontal movement detected within "
                "%.0f seconds (asset did not slide on the slope).\n"
                "\n"
                "How to fix:\n"
                "- Verify UsdPhysics.RigidBodyAPI is applied to the root "
                "prim.\n"
                "- Check collision mesh makes contact with the slope "
                "surface.\n"
                "- Check friction values -- very high friction may prevent "
                "sliding.\n"
                "- Check for FixedJoint anchoring the asset to the world." % sim_seconds
            )
        else:
            ctx.fail(
                "Slope drop FAILED: Object penetrated the ground after "
                "sliding.\n"
                "\n"
                "How to fix:\n"
                "- Check collision mesh approximation (convexHull "
                "recommended).\n"
                "- The slope-floor transition is a stress point -- check "
                "for thin geometry or gaps in collision mesh.\n"
                "- Review the video to see where penetration occurs."
            )
        return

    ctx.log("Slope drop PASSED: sliding at %.2fs, no penetration" % (horiz_frame / float(physics_fps)))


async def _run_simulation(ctx, cfg):
    # type: (object, dict) -> tuple
    """Run the physics simulation loop. Returns (frames, state dict).

    Flow:
      - Watch for horizontal movement (cumulative XY displacement from
        start).  That confirms the asset is sliding on the slope.
      - After sliding is detected, keep simulating for
        ``post_horiz_frames`` frames watching for penetration.
      - Stop as soon as the post-horizontal window has elapsed without
        penetration.  Anything beyond that is wasted sim + capture time.
    """
    frames = []
    initial_y = None
    contact_detected = False
    horiz_detected = False
    horiz_frame = -1
    penetrated = False
    slope_penetrated = False
    excessive_separation = False
    separation_frames = 0
    separation_frame = -1
    left_slope_frame = -1
    max_clearance = 0.0
    uphill_motion = False
    for frame in range(cfg["total_frames"]):
        await ctx.physics_step()
        ctx.scene.update_camera_follow()
        bounds = ctx.get_asset_bounds()
        z_min = bounds.min[2]
        min_y = bounds.min[1]
        max_y = bounds.max[1]
        cy = (min_y + max_y) / 2.0

        if initial_y is None:
            initial_y = cy

        on_slope = cfg["slope_min_y"] <= cy <= cfg["slope_max_y"]
        # The separation heuristic is meaningful only while the complete bbox
        # footprint remains over the finite ramp. Near the downhill edge an
        # object can be visibly sliding correctly while its centre is still on
        # the ramp and its leading edge is already falling toward the floor.
        fully_on_slope = cfg["slope_min_y"] <= min_y and max_y <= cfg["slope_max_y"]
        # Project the complete AABB onto the ramp normal. This measures a
        # geometry-aware separation interval in metres and correctly handles
        # curved bodies whose minimum Z is not below the plane at centre Y.
        clearance, maximum_plane_distance = _slope_plane_distance_interval(
            bounds,
            cfg["slope_center_z"],
            cfg["slope_tangent"],
        )
        below_ramp = maximum_plane_distance < -cfg["slope_penetration_tolerance"]
        if fully_on_slope and below_ramp:
            slope_penetrated = True
            ctx.step("Slope penetration at frame %d (maximum signed distance=%.4fm)" % (frame, maximum_plane_distance))
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
        # sustained separation before calling it a launch, and stop evaluating
        # this signal as soon as any part of the bbox leaves the finite ramp.
        if contact_detected and fully_on_slope:
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
                    break
            else:
                separation_frames = 0
        else:
            separation_frames = 0
            if contact_detected and not fully_on_slope and left_slope_frame < 0:
                left_slope_frame = frame

        # Penetration is a hard fail any time after we start checking.
        # (We only start checking after horiz is detected so mid-fall
        # below-floor glitches don't fail assets that correctly recover.)
        if horiz_detected and not penetrated and z_min < cfg["pen_threshold"]:
            penetrated = True
            ctx.step("Penetration at frame %d (z=%.3f)" % (frame, z_min))
            break  # stop immediately; no need to capture past the fail

        if frame % cfg["capture_interval"] == 0:
            frames.append(await ctx.capture_frame(label="slope_drop"))

        # Stop once the post-horizontal window has been watched clean.
        if horiz_detected and not penetrated and frame - horiz_frame >= cfg["post_horiz_frames"]:
            break

        await ctx.physics_advance()

    state = {
        "horiz_detected": horiz_detected,
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


@test(
    features=[
        {"id": "FET_003_STANDARD", "version": ">=0.1.0"},
        {"id": "FET_003_PHYSX", "version": ">=0.1.0"},
        {"id": "FET_003_NEWTON", "version": ">=0.1.0"},
    ],
    name="slope_drop",
    description=(
        "Places the asset on a 45° inclined plane with collision; runs "
        "physics; verifies the asset slides downhill (positive horizontal "
        "velocity over time) and does not tunnel through the slope's "
        "collision surface. Sliding is the positive signal that the asset's "
        "collider is registering contacts; tunneling proves it isn't."
    ),
    expected_video=(
        "The asset placed on a tilted ramp. It begins to slide down the "
        "slope under gravity, possibly tumbling. It stays on top of the "
        "slope surface for the entire clip. An asset that drops straight "
        "through the ramp (tunnels) or that floats above it (collision "
        "in the wrong place) indicates a broken collision shape."
    ),
    version="3.3.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    max_duration=300,
    config_defaults={
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
        # Bbox bottom may sit slightly below the analytic lowest ramp height
        # because of solver/contact tolerance. Larger negative clearance is
        # treated as tunnelling through the ramp.
        "slope_penetration_tolerance": 0.02,
        "maximum_slope_separation": 0.05,
        # Ignore isolated AABB spikes from tumbling bodies. Separation must
        # persist for this duration while the complete bbox footprint remains
        # over the finite ramp before it is classified as an upward launch.
        "separation_confirmation_seconds": 0.1,
        # After horizontal movement is detected, keep simulating this
        # long while watching for a penetration event.  No penetration
        # during the window -> PASS. Also sets how much of the slide the
        # video captures, so keep it long enough to show the asset sliding
        # (not just the first instant of motion).
        "post_horiz_seconds": 3.0,
    },
)
async def test_slope_drop(ctx):
    """Slope drop -- asset must slide on the slope and not penetrate the ground."""
    # --- Config ---
    sim_seconds = float(ctx.config["simulation_seconds"])
    physics_fps = int(ctx.config["physics_fps"])
    capture_fps = int(ctx.config["capture_fps"])
    floor_level = float(ctx.config["floor_level"])
    floor_margin = float(ctx.config["floor_margin"])
    post_horiz_secs = float(ctx.config["post_horiz_seconds"])

    sim_cfg = {
        "total_frames": int(sim_seconds * physics_fps),
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
            "The installed simready-benchmark-engine-kit does not support bbox-safe slope clearance; "
            "using legacy slope placement. Upgrade the Benchmark wheels to 2026.8.0rc3 or newer "
            "to enable size-safe placement."
        )

    # --- Pre-simulation safeguards ---
    from simready_benchmark_kit_suite.fet003_physics.physics_checks import (
        run_pre_checks,
    )

    pre_result = run_pre_checks(ctx)
    if pre_result is not None:
        if pre_result.startswith("NA:"):
            ctx.skip(pre_result[3:].strip())
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
    from simready_benchmark_engine_kit.physics_utils import (
        active_physics_engine,
        cook_skip_message,
    )
    from simready_benchmark_kit_suite.engine_guard import (
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
    if active_physics_engine() != "physx":
        import omni.usd

        articulationize_loose_joints(ctx, omni.usd.get_context().get_stage())
        await ctx.settle(count=1)

    # Newton scene-init guard (Newton only; PhysX untouched). Report an error
    # when Newton aborts scene init instead of stepping the un-built simulation
    # or counting the requested coverage as a non-blocking skip.
    if active_physics_engine() != "physx":
        physics.play()
        await ctx.settle(count=3)
        newton_ready = newton_scene_initialized()
        physics.stop()
        if not newton_ready:
            raise NewtonSceneInitializationError(NEWTON_SCENE_ERROR)

    physics.play()

    # --- Log initial position for physics validation ---
    init_bounds = ctx.get_asset_bounds()
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

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

WHAT: Place the asset on a 45-degree slope.  The defining signal that
      the collider works on a slope is *horizontal* movement -- the
      asset has to actually slide.  Once we observe sliding, we only
      need to confirm the asset does not tunnel through the floor.

HOW:  1. Load asset in room with collision ground + slope.
      2. Place asset at the top of the slope.
      3. Run pre-simulation safeguards (world-anchor, rigid body checks).
      4. Simulate at 240fps with camera follow.
      5. Watch the bbox centre XY each frame.  When cumulative XY
         displacement from the start position exceeds
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
  - Cumulative displacement from the initial XY centre (not per-frame)
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
import time

from simready_benchmark.core.decorator import test


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
                UsdShade.Material(mat_prim), UsdShade.Tokens.weakerThanDescendants, "physics"
            )
    except Exception:
        pass


def _report_result(ctx, horiz_detected, penetrated, horiz_frame, physics_fps, sim_seconds):
    # type: (object, bool, bool, int, int, float) -> None
    """Emit metrics and pass/fail for the slope drop test."""
    passed = horiz_detected and not penetrated

    ctx.add_metric("slope_drop_horiz_detected", 1 if horiz_detected else 0)
    ctx.add_metric("slope_drop_penetrated", 1 if penetrated else 0)
    ctx.add_metric("slope_drop_passed", 1 if passed else 0)
    if horiz_frame >= 0:
        ctx.add_metric("slope_drop_horiz_time", round(horiz_frame / float(physics_fps), 3))

    if not passed:
        if not horiz_detected:
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
    initial_x = None
    initial_y = None
    horiz_detected = False
    horiz_frame = -1
    penetrated = False
    deadline = time.monotonic() + 120.0  # 120 second watchdog

    for frame in range(cfg["total_frames"]):
        await ctx.physics_step()
        if time.monotonic() > deadline:
            ctx.fail(
                "Physics simulation hung (exceeded 120s watchdog).\n"
                "\n"
                "How to fix:\n"
                "- Asset likely has unstable physics: check for self-penetrating geometry, "
                "missing or zero-volume colliders, and overlapping rigid bodies.\n"
                "- Inspect `physxRigidBody:mass` and `physxRigidBody:diagonalInertia` -- "
                "NaN, zero, or extreme values can stall PhysX cooking and stepping.\n"
                "- Verify every dynamic mesh has a valid `UsdPhysics.CollisionAPI` + "
                "`UsdPhysics.MeshCollisionAPI` with a non-empty approximation.\n"
                "- Open the asset in Kit standalone and step physics manually; the engine "
                "log will surface the specific PhysX error that the watchdog is hiding here."
            )
            break
        ctx.scene.update_camera_follow()
        bounds = ctx.get_asset_bounds()
        z_min = bounds.min[2]
        cx = (bounds.min[0] + bounds.max[0]) / 2.0
        cy = (bounds.min[1] + bounds.max[1]) / 2.0

        if initial_x is None:
            initial_x = cx
            initial_y = cy

        # Detect sliding via cumulative XY displacement from start.
        if not horiz_detected:
            disp = math.sqrt((cx - initial_x) ** 2 + (cy - initial_y) ** 2)
            if disp >= cfg["horiz_threshold"]:
                horiz_detected = True
                horiz_frame = frame
                ctx.step("Horizontal movement at frame %d (%.4fm)" % (frame, disp))

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
    }
    return frames, state


@test(
    features=[{"id": "FET003_BASE_PHYSX", "version": ">=0.1.0"}],
    name="slope_drop",
    description=(
        "Places the asset on a 45° inclined plane with collision; runs "
        "physics; verifies the asset slides downhill (positive horizontal "
        "velocity over time) and does not tunnel through the slope's "
        "collision mesh. Sliding is the positive signal that the asset's "
        "collider is registering contacts; tunneling proves it isn't."
    ),
    expected_video=(
        "The asset placed on a tilted ramp. It begins to slide down the "
        "slope under gravity, possibly tumbling. It stays on top of the "
        "slope surface for the entire clip. An asset that drops straight "
        "through the ramp (tunnels) or that floats above it (collision "
        "in the wrong place) indicates a broken collision shape."
    ),
    version="3.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
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
        "floor_level": 0.0,
        "floor_margin": 0.1,
        # Minimum cumulative XY displacement from the start position
        # (metres) to count as "sliding on the slope".
        "horizontal_movement_threshold": 0.01,
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
    }

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)  # saturated blue walls
    room.show_ground(color=(0.25, 0.35, 0.6))  # darker blue ground
    room.add_slope(angle=ctx.config["slope_angle_deg"], friction=ctx.config["slope_friction"])
    room.place_asset_on_slope()

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
    from simready_benchmark_engine_kit.physics_utils import cook_skip_message

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        ctx.add_metric("slope_drop_passed", 0)
        return

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
    _report_result(ctx, state["horiz_detected"], state["penetrated"], state["horiz_frame"], physics_fps, sim_seconds)

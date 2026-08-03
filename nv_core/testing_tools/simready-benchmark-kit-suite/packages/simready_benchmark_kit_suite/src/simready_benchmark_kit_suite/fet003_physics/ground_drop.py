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
"""FET003 Ground Drop + Stability test (RB.001 / RB.007).

WHAT: Drop the asset from N x its height onto a flat ground plane, verify
      it touches the ground, does not penetrate, and comes to rest.  Combines
      the former ground_drop (RB.001) and ground_stability (RB.007) tests
      into one simulation to avoid paying the setup + boot cost twice.

HOW:  1. Load asset in blue room with collision ground.
      2. Place asset at drop_height_factor * bbox_height above ground.
      3. Run pre-simulation safeguards (world-anchor, rigid body checks).
      4. Simulate at 240 fps with camera follow.
      5. Each frame:
         - Check ground touch (bbox z_min crossing floor + floor_margin).
         - Check penetration (bbox z_min below floor - floor_margin).
         - After the post-touch penetration window, begin rest detection:
           track bbox centre + corners over a sliding hold window and
           declare rest when both stay within tolerance.
      6. Early-exit: stop simulating as soon as rest is detected (+ short
         tail for the video).  This is the main win over running a fixed
         simulation_seconds every time.

PASS/FAIL:
  - PASS: touched + no penetration + rest detected within
          rest_detection_max_seconds after the first ground touch.
  - FAIL: never touched, or penetrated after touch, or oscillated without
          settling within the rest deadline.

FALSE POSITIVE AVOIDANCE:
  - floor_margin (0.1m) tolerance for floating-point collision resolution.
  - 1-second penetration window catches transient vs sustained penetration.
  - World-anchor detection skips test for anchored assets.
  - RigidBody pre-check catches assets with no physics setup.
  - Mesh cooking safeguards in load_asset() prevent PhysX hangs.
  - ctx.get_asset_bounds() tracks actual physics body, not root xform.
  - Rest uses bbox min + max corners so rotation without translation is
    still detected (a spinning object is not at rest).
"""
import time

from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.fet003_physics.stability import (
    bounds_to_history_entry,
    check_bbox_corners_stable,
    check_position_stable,
    check_rest_window,
)


def _apply_ground_physics_material(ground_path="/World/GroundPlane"):
    # type: (str) -> None
    """Apply physics material to ground plane (enable_ground_plane ignores friction)."""
    try:
        import omni.usd
        from pxr import UsdPhysics, UsdShade

        _stage = omni.usd.get_context().get_stage()
        gp_prim = _stage.GetPrimAtPath(ground_path + "/CollisionMesh")
        if gp_prim.IsValid():
            _mat_path = ground_path + "/PhysMaterial"
            _mat_prim = _stage.DefinePrim(_mat_path)
            _phys_mat = UsdPhysics.MaterialAPI.Apply(_mat_prim)
            _phys_mat.CreateStaticFrictionAttr(0.5)
            _phys_mat.CreateDynamicFrictionAttr(0.4)
            _phys_mat.CreateRestitutionAttr(0.0)
            UsdShade.MaterialBindingAPI.Apply(gp_prim).Bind(
                UsdShade.Material(_mat_prim), UsdShade.Tokens.weakerThanDescendants, "physics"
            )
    except Exception:
        pass


def _diagnose_instability(history, hold_frames, pos_tol, corner_tol):
    # type: (list, int, float, float) -> str
    """Return a diagnostic string about which axis is unstable."""
    if len(history) < hold_frames:
        return ""
    pos_stable = check_position_stable(history, hold_frames, pos_tol)
    rot_stable = check_bbox_corners_stable(history, hold_frames, corner_tol)
    if pos_stable and not rot_stable:
        return "\nDiagnostic: position is stable but rotation is not.\n" "The object may be spinning in place.\n"
    if not pos_stable and rot_stable:
        return "\nDiagnostic: rotation is stable but position is not.\n" "The object may be sliding or bouncing.\n"
    return ""


def _report_result(
    ctx,
    touched,
    penetrated,
    rest_detected,
    touch_frame,
    rest_frame,
    physics_fps,
    sim_seconds,
    max_rest_seconds,
    history,
    hold_frames,
    rest_tol,
    bbox_corner_tol,
):
    # type: (object, bool, bool, bool, int, int, int, float, float, list, int, float, float) -> None
    """Emit metrics and pass/fail for the combined ground drop + stability test."""
    passed = touched and not penetrated and rest_detected

    ctx.add_metric("ground_drop_touched", 1 if touched else 0)
    ctx.add_metric("ground_drop_penetrated", 1 if penetrated else 0)
    ctx.add_metric("ground_drop_stable", 1 if rest_detected else 0)
    ctx.add_metric("ground_drop_passed", 1 if passed else 0)
    if touch_frame >= 0:
        ctx.add_metric("ground_drop_touch_time", round(touch_frame / float(physics_fps), 3))
    if rest_frame >= 0:
        ctx.add_metric("ground_drop_rest_time", round(rest_frame / float(physics_fps), 3))

    if passed:
        ctx.log(
            "Ground drop + stability PASSED: touched at %.2fs, settled at %.2fs"
            % (touch_frame / float(physics_fps), rest_frame / float(physics_fps))
        )
        return

    if not touched:
        ctx.fail(
            "Ground drop FAILED: Object never touched the ground within "
            "%.0f seconds.\n"
            "\n"
            "How to fix:\n"
            "- Verify UsdPhysics.RigidBodyAPI is applied to the root prim.\n"
            "- Check that at least one mesh has UsdPhysics.CollisionAPI.\n"
            "- Check for FixedJoint anchoring the asset to the world.\n"
            "- Check mass -- mass=0 makes the body kinematic (won't fall)." % sim_seconds
        )
        return

    if penetrated:
        ctx.fail(
            "Ground drop FAILED: Object penetrated the ground plane "
            "after contact.\n"
            "\n"
            "How to fix:\n"
            "- Check collision mesh approximation (convexHull recommended).\n"
            "- Verify collision mesh normals point outward.\n"
            "- Check for very thin geometry (< 1cm) that may tunnel.\n"
            "- Review the video to see where penetration occurs."
        )
        return

    # Touched + no penetration + never stabilized: this is the ex-ground_stability failure.
    detail = _diagnose_instability(history, hold_frames, rest_tol, bbox_corner_tol)
    ctx.fail(
        "Ground drop FAILED: Object touched the ground but never came to "
        "rest within %.1f seconds after touch. Object is oscillating, "
        "sliding, or spinning indefinitely.%s\n"
        "\n"
        "How to fix:\n"
        "- Check mass properties. Unrealistic mass causes excessive "
        "bouncing; set mass proportional to real-world equivalent.\n"
        "- Check center of mass. If outside the collision mesh, the object "
        "wobbles indefinitely.\n"
        "- Check for rounded base geometry. Perfectly round bottoms may "
        "never fully rest; consider flattening the base collision mesh.\n"
        "- Check for overlapping collision meshes causing perpetual forces.\n"
        "- Review the video. Jittering often indicates solver instability "
        "-- try simplifying collision mesh to convexHull." % (max_rest_seconds, detail)
    )


@test(
    features=[
        {"id": "FET003_BASE_PHYSX", "version": ">=0.1.0"},
    ],
    name="ground_drop",
    description=(
        "Loads the asset above a collision-enabled ground plane (default "
        "drop height = 8 × asset height), enables physics, and verifies "
        "three things: the asset eventually contacts the ground, never "
        "penetrates more than a configurable margin, and comes to rest "
        "(linear + angular velocity below threshold) within "
        "max_settle_seconds. Validates the collision shape is correctly "
        "authored and the asset's mass/inertia are physically reasonable."
    ),
    expected_video=(
        "The asset starts in mid-air above a flat blue floor. It falls "
        "under gravity, hits the ground, may bounce or tumble, and comes "
        "to rest. The video shows the entire fall + settle. An asset that "
        "tunnels through the floor or never settles indicates broken "
        "collision or unrealistic mass parameters."
    ),
    version="3.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        # simulation_seconds is now a hard upper cap; the loop exits as
        # soon as rest is detected so typical runs finish much sooner.
        "simulation_seconds": 10.0,
        "physics_fps": 240,
        "capture_fps": 15,
        "settle_frames": 5,
        "asset_load_timeout": 30,
        "drop_height_factor": 8.0,
        "floor_level": 0.0,
        "floor_margin": 0.1,
        "penetration_check_seconds": 1.0,
        # Rest detection (merged from the former ground_stability test).
        # Tolerance is intentionally loose (2 cm) to accept small rocking
        # that never fully damps out -- e.g. cylindrical-rim objects like
        # coffee cups.  Tighten if you need stricter settling behaviour.
        "rest_tolerance": 0.02,
        "rest_detection_hold_seconds": 2.0,
        # Fail if the object does not reach rest within this many seconds
        # after the first ground touch.  Rockers (round-rim objects) need
        # the wider 8s budget; simple boxes typically settle in <3s.
        "rest_detection_max_seconds": 8.0,
        "simulate_after_result_seconds": 0.5,
    },
)
async def test_ground_drop(ctx):
    """Ground drop + stability -- asset must fall, not penetrate, and settle."""
    # --- Config ---
    sim_seconds = float(ctx.config["simulation_seconds"])
    physics_fps = int(ctx.config["physics_fps"])
    capture_fps = int(ctx.config["capture_fps"])
    floor_level = float(ctx.config["floor_level"])
    floor_margin = float(ctx.config["floor_margin"])
    pen_check_secs = float(ctx.config["penetration_check_seconds"])
    after_result_secs = float(ctx.config["simulate_after_result_seconds"])
    rest_tol = float(ctx.config["rest_tolerance"])
    bbox_corner_tol = rest_tol  # same tolerance applied to bbox min/max
    hold_seconds = float(ctx.config["rest_detection_hold_seconds"])
    max_rest_seconds = float(ctx.config["rest_detection_max_seconds"])

    touch_threshold = floor_level + floor_margin
    pen_threshold = floor_level - floor_margin
    pen_check_frames = int(pen_check_secs * physics_fps)
    hold_frames = int(hold_seconds * physics_fps)
    max_rest_frames = int(max_rest_seconds * physics_fps)
    after_result_frames = int(after_result_secs * physics_fps)
    capture_interval = max(1, physics_fps // capture_fps)
    total_frames = int(sim_seconds * physics_fps)

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)  # saturated blue walls
    room.show_ground(color=(0.25, 0.35, 0.6))  # darker blue ground
    room.place_asset_above_ground(height_factor=ctx.config["drop_height_factor"])

    # --- Pre-simulation safeguards ---
    from simready_benchmark_kit_suite.fet003_physics.physics_checks import (
        run_pre_checks,
    )

    pre_result = run_pre_checks(ctx)
    if pre_result is not None:
        if pre_result.startswith("NA:"):
            ctx.skip(pre_result[3:].strip())
            ctx.add_metric("ground_drop_skipped", 1)
        elif pre_result.startswith("SKIP:"):
            ctx.precheck_failure(pre_result[5:].strip())
            ctx.add_metric("ground_drop_passed", 0)
        else:
            ctx.fail(pre_result)
            ctx.add_metric("ground_drop_passed", 0)
        return

    # --- Lighting + Physics + camera ---
    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=9.81, fps=float(physics_fps))
    ctx.scene.enable_ground_plane(friction=0.5)
    _apply_ground_physics_material()
    ctx.scene.setup_camera_follow()
    await ctx.settle(count=3)

    # Cook the dynamic mesh colliders (and author any missing mass) OFF the
    # timeline path, bounded by a timeout, BEFORE play(). A cold SDF cook
    # triggered synchronously by play() can freeze the run; doing it here as a
    # pumped, time-boxed step keeps the run alive and reports a clean failure
    # if a collider is too expensive to cook in this environment.
    from simready_benchmark_engine_kit.physics_utils import cook_skip_message

    cook_status = await ctx.scene.prepare_physics()
    cook_skip = cook_skip_message(cook_status)
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        ctx.add_metric("ground_drop_passed", 0)
        return

    physics.play()

    # --- Log initial position for physics validation ---
    init_bounds = ctx.get_asset_bounds()
    init_z_min = init_bounds.min[2]
    bbox_height = init_bounds.max[2] - init_bounds.min[2]
    effective_fall = init_z_min - touch_threshold
    ctx.add_metric("ground_drop_initial_z_min", round(init_z_min, 4))
    ctx.add_metric("ground_drop_bbox_height", round(bbox_height, 4))
    ctx.add_metric("ground_drop_effective_fall", round(effective_fall, 4))
    ctx.step(
        "Initial: z_min=%.4f, bbox_h=%.4f, effective_fall=%.4f, "
        "touch=%.2f, pen=%.2f" % (init_z_min, bbox_height, effective_fall, touch_threshold, pen_threshold)
    )

    # --- Simulation loop ---
    ctx.step("Simulating ground drop + stability")
    frames = []
    history = []  # (cx, cy, cz, min_x..z, max_x..z) per frame
    touched = False
    touch_frame = -1
    penetrated = False
    rest_detected = False
    rest_frame = -1
    result_frame = -1
    prev_z_min = None
    deadline = time.monotonic() + 120.0  # 120 second watchdog

    for frame in range(total_frames):
        # 1. Process physics (next_update_async, pauses after first call)
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

        # 2. Read current state
        bounds = ctx.get_asset_bounds()
        z_min = bounds.min[2]
        history.append(bounds_to_history_entry(bounds))

        # Debug: log z_min for first 10 frames, then every 60 frames
        if frame < 10 or frame % 60 == 0:
            ctx.step("frame %d: z_min=%.4f (touch=%.2f, pen=%.2f)" % (frame, z_min, touch_threshold, pen_threshold))

        # 3. Check ground touch / penetration
        if not touched and prev_z_min is not None:
            if prev_z_min > touch_threshold and z_min <= touch_threshold:
                touched = True
                touch_frame = frame
                ctx.step("Ground touch at frame %d (z=%.3f)" % (frame, z_min))

        if touched and not penetrated and z_min < pen_threshold:
            penetrated = True
            ctx.step("Penetration at frame %d (z=%.3f)" % (frame, z_min))
            # Penetration is a hard fail; lock the result so we tail the video
            # briefly and exit without waiting on rest detection.
            if result_frame < 0:
                result_frame = frame

        # 4. Rest detection (only after the post-touch penetration window
        # so we don't confuse mid-air stillness with settled rest).
        if touched and not rest_detected and not penetrated and frame - touch_frame >= pen_check_frames:
            frames_since_touch = frame - touch_frame
            if check_rest_window(history, hold_frames, rest_tol, bbox_corner_tol):
                rest_detected = True
                rest_frame = frame
                ctx.step(
                    "Rest detected at frame %d (%.2fs after touch)" % (frame, frames_since_touch / float(physics_fps))
                )
                if result_frame < 0:
                    result_frame = frame
            elif frames_since_touch >= max_rest_frames:
                # Object touched but failed to settle within the rest deadline.
                # Lock the failure here and tail briefly for the video.
                if result_frame < 0:
                    result_frame = frame

        should_stop = result_frame >= 0 and frame - result_frame >= after_result_frames

        # 5. Camera follow
        ctx.scene.update_camera_follow()

        # 6. Capture (only at capture interval)
        prev_z_min = z_min
        if frame % capture_interval == 0:
            frames.append(await ctx.capture_frame(label="ground_drop"))

        if should_stop:
            break

        # 7. Advance timeline (V1 pattern: at END, after captures)
        await ctx.physics_advance()

    # --- Video + results ---
    if frames:
        ctx.encode_video(frames, fps=capture_fps, label="ground_drop", role="summary")
    _report_result(
        ctx,
        touched,
        penetrated,
        rest_detected,
        touch_frame,
        rest_frame,
        physics_fps,
        sim_seconds,
        max_rest_seconds,
        history,
        hold_frames,
        rest_tol,
        bbox_corner_tol,
    )

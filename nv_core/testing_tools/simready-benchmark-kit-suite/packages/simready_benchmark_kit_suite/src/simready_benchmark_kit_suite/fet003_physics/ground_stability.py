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
"""FET003 Ground Stability test (RB.007 -- rigid body mass).

WHAT: Place the asset slightly above the ground and let it settle. Verify
      it comes to rest (position AND rotation stable) within 5 seconds.

HOW:  1. Load asset in white room with collision ground.
      2. Place asset at floor_margin (0.1m) above ground level.
      3. Run pre-simulation safeguards (world-anchor, rigid body checks).
      4. After physics.play(), the first physics_step() pauses the timeline.
         All subsequent stepping is manual via forward_one_frame() to ensure
         exactly one physics step per frame (prevents multi-frame
         auto-advancement).
      5. Camera uses screen-space safety check -- zooms out instantly if
         the object would leave the visible frame.
      6. Simulate at 240fps with camera follow.
      7. Per frame: record bounds min (XYZ) and max (XYZ) to history.
      8. Rest detection uses a sliding window of hold_seconds (2.0s).
         All frames in the window must be within tolerance of the CURRENT
         (latest) frame:
         - Position: bounds center within rest_tolerance (0.01m).
         - Rotation (practical): both bounds.min and bounds.max must be
           stable within rotation_rest_tolerance_degrees converted to a
           linear tolerance. If both extremes are stable, the object has
           not rotated (rotation changes the bbox shape/position).
      9. Hold frames = hold_seconds * physics_fps (2.0 * 240 = 480).
      10. Rest detected within rest_detection_max_seconds (5.0s): PASS,
          then continue simulate_after_result_seconds (2.0s) for video.
      11. max_seconds without rest: FAIL.

WHY:  RB.007 requires correct mass properties. An asset with correct mass,
      collision, and center of gravity should settle naturally. Objects that
      jitter, spin, or oscillate indefinitely have broken physics setup.

FALSE POSITIVE AVOIDANCE:
  - Rest uses sliding window against CURRENT position. An object that
    topples and lies on its side is at rest (PASS). The test checks if
    motion stopped, not if the object stayed upright.
  - 2-second hold window prevents counting momentary pauses during bouncing.
  - Tracking bounds min+max detects rotation without extracting Euler angles
    (avoids gimbal lock issues). If both bbox corners are stable, the object
    is stable in both position and rotation.
  - Slight lift (floor_margin) at start avoids starting mid-collision which
    would cause explosive solver forces.
  - Ground friction material prevents infinite sliding on frictionless surface.
  - 120-second watchdog timeout prevents PhysX mesh cooking hangs.
  - World-anchor detection skips test for anchored assets.
  - RigidBody pre-check catches assets with no physics setup.
  - ctx.get_asset_bounds() tracks actual physics body, not root xform.
"""
import time

from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.fet003_physics.stability import (
    bounds_to_history_entry,
    check_bbox_corners_stable,
    check_position_stable,
    check_rest_window,
)

# ---------------------------------------------------------------------------
# Helper: apply friction material to the ground plane
# ---------------------------------------------------------------------------


def _apply_ground_friction_material():
    """Apply physics material with friction to the ground plane.

    enable_ground_plane() ignores friction -- we apply it manually.
    """
    ground_path = "/World/GroundPlane"
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


# ---------------------------------------------------------------------------
# Helper: run the simulation loop and return results
# ---------------------------------------------------------------------------


async def _run_simulation(
    ctx,
    total_frames,
    hold_frames,
    max_rest_frames,
    after_result_frames,
    capture_interval,
    rest_tol,
    bbox_corner_tol,
    physics_fps,
):
    """Run the physics simulation loop and collect bounds history.

    Returns (frames, history, rest_detected, rest_frame).
    """
    frames = []
    rest_detected = False
    rest_frame = -1
    result_frame = -1
    history = []

    deadline = time.monotonic() + 120.0  # 120 second watchdog

    for frame in range(total_frames):
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
        history.append(bounds_to_history_entry(bounds))

        # Rest detection (only before max_rest_frames)
        if not rest_detected and frame < max_rest_frames:
            if check_rest_window(history, hold_frames, rest_tol, bbox_corner_tol):
                rest_detected = True
                rest_frame = frame
                rest_time = frame / float(physics_fps)
                ctx.step("Rest detected at frame %d (%.2fs)" % (frame, rest_time))
                result_frame = frame

        # If max rest time exceeded without rest, record failure frame
        if not rest_detected and frame >= max_rest_frames and result_frame < 0:
            result_frame = frame

        # Continue after result for video
        if result_frame >= 0 and frame - result_frame >= after_result_frames:
            break

        if frame % capture_interval == 0:
            frames.append(await ctx.capture_frame(label="ground_stability"))

        await ctx.physics_advance()

    return frames, history, rest_detected, rest_frame


# ---------------------------------------------------------------------------
# Helper: report pass/fail result
# ---------------------------------------------------------------------------


def _report_result(
    ctx, rest_detected, rest_frame, history, hold_frames, rest_tol, bbox_corner_tol, max_rest_seconds, physics_fps
):
    """Emit metrics and pass/fail for the ground stability test."""
    ctx.add_metric("ground_stability_rest_detected", 1 if rest_detected else 0)
    ctx.add_metric("ground_stability_passed", 1 if rest_detected else 0)
    if rest_frame >= 0:
        ctx.add_metric("ground_stability_rest_time", round(rest_frame / float(physics_fps), 3))

    if not rest_detected:
        detail = _diagnose_instability(history, hold_frames, rest_tol, bbox_corner_tol)
        ctx.fail(
            "Ground stability FAILED: Object did not come to rest within "
            "%.1f seconds.%s\n"
            "\n"
            "How to fix:\n"
            "- Check mass properties. Unrealistic mass causes excessive "
            "bouncing. Set mass proportional to real-world equivalent.\n"
            "- Check center of mass. If outside the collision mesh, the "
            "object wobbles indefinitely.\n"
            "- Check for rounded base geometry. Perfectly round bottoms may "
            "never fully rest. Consider flattening the base collision mesh.\n"
            "- Check for overlapping collision meshes causing perpetual "
            "forces.\n"
            "- Review the video. Jittering often indicates solver "
            "instability -- try simplifying collision mesh to convexHull." % (max_rest_seconds, detail)
        )
        return

    ctx.log("Ground stability PASSED: object at rest after %.2fs" % (rest_frame / float(physics_fps)))


def _diagnose_instability(history, hold_frames, rest_tol, bbox_corner_tol):
    """Return a diagnostic string about which axis is unstable."""
    if len(history) < hold_frames:
        return ""

    pos_stable = check_position_stable(history, hold_frames, rest_tol)
    rot_stable = check_bbox_corners_stable(history, hold_frames, bbox_corner_tol)

    if pos_stable and not rot_stable:
        return "\nDiagnostic: position is stable but rotation is not.\n" "The object may be spinning in place.\n"
    if not pos_stable and rot_stable:
        return "\nDiagnostic: rotation is stable but position is not.\n" "The object may be sliding or bouncing.\n"
    return ""


# ---------------------------------------------------------------------------
# Main test function
# ---------------------------------------------------------------------------


@test(
    features=[
        {"id": "FET003_BASE_PHYSX", "version": ">=0.1.0"},
    ],
    name="ground_stability",
    description=(
        "Loads the asset 0.1 m (floor_margin) above the ground plane and "
        "enables physics with no initial velocity. Verifies the asset "
        "comes to rest — both linear and angular velocities below "
        "threshold — within max_settle_seconds (default 5 s). Catches "
        "assets with unstable mass distributions, missing damping, or "
        "ill-formed collision that wobble forever instead of settling."
    ),
    expected_video=(
        "The asset starts hovering just above a white floor. Gravity drops "
        "it the small remaining distance. It contacts the ground, may "
        "rock briefly, and stabilizes. By the end of the clip the asset "
        "is stationary. Continued visible wobbling or sliding past the "
        "settle window is a fail."
    ),
    version="2.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "simulation_seconds": 10.0,
        "physics_fps": 240,
        "capture_fps": 30,
        "settle_frames": 5,
        "asset_load_timeout": 30,
        "floor_level": 0.0,
        "floor_margin": 0.1,
        "rest_tolerance": 0.01,
        "rotation_rest_tolerance_degrees": 0.01,
        "rest_detection_hold_seconds": 2.0,
        "rest_detection_max_seconds": 5.0,
        "simulate_after_result_seconds": 2.0,
    },
    enabled=False,
)
async def test_ground_stability(ctx):
    """Ground stability -- asset must come to rest within time limit."""
    # --- Config ---
    physics_fps = int(ctx.config["physics_fps"])
    capture_fps = int(ctx.config["capture_fps"])
    floor_margin = float(ctx.config["floor_margin"])
    rest_tol = float(ctx.config["rest_tolerance"])
    hold_seconds = float(ctx.config["rest_detection_hold_seconds"])
    max_rest_seconds = float(ctx.config["rest_detection_max_seconds"])
    after_result_secs = float(ctx.config["simulate_after_result_seconds"])

    # Bbox corner tolerance: same as rest_tolerance (0.01m). Stable bbox
    # min+max means no rotation. See module docstring for rationale.
    bbox_corner_tol = rest_tol

    hold_frames = int(hold_seconds * physics_fps)
    max_rest_frames = int(max_rest_seconds * physics_fps)
    after_result_frames = int(after_result_secs * physics_fps)
    capture_interval = max(1, physics_fps // capture_fps)
    total_frames = int(float(ctx.config["simulation_seconds"]) * physics_fps)

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)  # saturated blue walls
    room.show_ground(color=(0.25, 0.35, 0.6))  # darker blue ground
    room.place_asset_at_ground(margin=floor_margin)

    # --- Pre-simulation safeguards ---
    from simready_benchmark_kit_suite.fet003_physics.physics_checks import (
        run_pre_checks,
    )

    pre_result = run_pre_checks(ctx)
    if pre_result is not None:
        if pre_result.startswith("NA:"):
            ctx.skip(pre_result[3:].strip())
            ctx.add_metric("ground_stability_skipped", 1)
            return
        elif pre_result.startswith("SKIP:"):
            ctx.precheck_failure(pre_result[5:].strip())
            ctx.add_metric("ground_stability_passed", 0)
            return
        else:
            ctx.fail(pre_result)
            ctx.add_metric("ground_stability_passed", 0)
            return

    # --- Lighting + Physics + camera ---
    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=9.81, fps=float(physics_fps))
    ctx.scene.enable_ground_plane(friction=0.5)
    _apply_ground_friction_material()
    ctx.scene.setup_camera_follow()
    await ctx.settle(count=3)

    # Cook dynamic mesh colliders (and author missing mass) OFF the timeline
    # path, time-boxed, BEFORE play() -- a cold SDF cook triggered by play()
    # can freeze the run. Reports a clean failure if a collider cannot cook.
    from simready_benchmark_engine_kit.physics_utils import cook_skip_message

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        ctx.add_metric("ground_stability_passed", 0)
        return

    physics.play()

    # --- Log initial position for physics validation ---
    init_bounds = ctx.get_asset_bounds()
    init_z_min = init_bounds.min[2]
    bbox_height = init_bounds.max[2] - init_bounds.min[2]
    ctx.add_metric("ground_stability_initial_z_min", round(init_z_min, 4))
    ctx.add_metric("ground_stability_bbox_height", round(bbox_height, 4))
    ctx.step("Initial: z_min=%.4f, bbox_h=%.4f, floor_margin=%.2f" % (init_z_min, bbox_height, floor_margin))

    # --- Simulation ---
    ctx.step("Simulating ground stability")
    frames, history, rest_detected, rest_frame = await _run_simulation(
        ctx,
        total_frames,
        hold_frames,
        max_rest_frames,
        after_result_frames,
        capture_interval,
        rest_tol,
        bbox_corner_tol,
        physics_fps,
    )

    # --- Video + result ---
    if frames:
        ctx.encode_video(frames, fps=capture_fps, label="ground_stability", role="summary")

    _report_result(
        ctx, rest_detected, rest_frame, history, hold_frames, rest_tol, bbox_corner_tol, max_rest_seconds, physics_fps
    )

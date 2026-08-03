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
"""FET005 Grasp-and-Lift test.

Validates whether a SimReady asset can be grasped, lifted, held, shaken,
and released by a standardized parallel-jaw gripper at each declared
grasp point (grasp_identifier_* prims).

Skips if no grasp identifiers are found on the asset.
Stops at the first failed phase per identifier.
Fresh scene per identifier for PhysX safety.
"""
from simready_benchmark.core.decorator import test


@test(
    features=[
        {"id": "FET005_BASE_NEUTRAL", "version": ">=0.1.0"},
    ],
    name="grasp_and_lift",
    description=(
        "Iterates each grasp_identifier_* prim authored on the asset. At "
        "each, positions a synthetic gantry parallel-jaw gripper at the "
        "identifier's pose, closes it onto the asset, lifts the gripper "
        "by a configurable height, holds, optionally shakes. Verifies the "
        "asset stays grasped — doesn't slip out of the jaws or separate "
        "vertically by more than fall_min_delta_z. Validates that each "
        "declared grasp is physically achievable in PhysX. Depends on "
        "FET003_BASE_PHYSX: the asset is skipped, not failed, when its PhysX "
        "physics setup is not validated, since grasp behavior is only "
        "meaningful once that setup is confirmed."
    ),
    expected_video=(
        "For each grasp_identifier on the asset: a parallel-jaw gripper "
        "moves to the identifier's pose, closes around the asset, lifts "
        "it cleanly off the floor, holds it in mid-air, optionally shakes "
        "side-to-side, then opens to drop. The asset should follow the "
        "gripper's lift motion without sliding out. An asset that slips "
        "during lift or shake fails that grasp."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "physics_fps": 240,
        "capture_fps": 15,
        "simulation_seconds": 12.0,
        "close_duration": 0.5,
        # After the close ramp ends, keep holding the close command for
        # this long so PD-driven gripper joints can physically converge
        # onto the object before Lifting starts.  Without this the
        # gripper is still moving when lift commands rise, and small /
        # tightly-fitted objects slip out.
        "close_settle_seconds": 0.3,
        "lift_duration": 1.0,
        "open_duration": 0.5,
        "lift_height_multiplier": 2.0,
        "lift_min_delta_z": 0.02,
        # Slip threshold during shake: object must drop more than this
        # (metres) from its position at shake start to count as a drop.
        # 2cm was too tight for assets that slip slightly while still
        # firmly held; 5cm catches real drops without false-failing on
        # small jitters. Also used by phase_dropping as the floor of
        # `required fall = max(fall_min_delta_z, bbox_height)`.
        "fall_min_delta_z": 0.05,
        # Hold-phase drop tolerance (separate from fall_min_delta_z so
        # phase_dropping's "did it actually fall when released?" check
        # stays strict). Long thin objects -- dishwand-style tools,
        # handles -- can shift 5-10cm in centre-of-mass z while firmly
        # gripped near one end: the bbox tip rotates in the gripper
        # which drags the centre down without the object falling out.
        # 10cm catches real in-grip drops while tolerating swing.
        "hold_drop_tolerance": 0.10,
        "hold_seconds": 1.0,
        "shake_duration_seconds": 1.5,
        "shake_amplitude": 0.01,
        "shake_frequency_hz": 2.0,
        "enable_shake_test": True,
        "stability_max_seconds": 3.0,
        "rest_tolerance": 0.002,
        "rest_detection_hold_seconds": 1.0,
        "pad_touching_tolerance": 0.002,
        "floor_level": 0.0,
        # Floor-contact tolerance for shake/hold phases. NEGATIVE values
        # allow the object's bbox-bottom to dip below the floor by this
        # much during a shake without failing the test. Slim assets
        # swinging in the gripper can pass 1-2cm below ground while the
        # object remains firmly held (visible in failing-asset videos:
        # the gripper retains the asset but reports a 6mm bbox dip).
        # -2cm leaves headroom for normal in-grip motion while still
        # catching genuine ground contact when the object truly falls.
        "floor_margin": -0.02,
        "release_check_seconds": 0.5,
        "drop_check_seconds": 3.0,
        "post_drop_max_seconds": 1.0,
        "post_ground_contact_seconds": 0.0,
        "asset_load_timeout": 30,
        "settle_frames": 5,
        "show_gripper": True,
    },
    max_duration=600,
)
async def test_grasp_and_lift(ctx):
    """Test grasp-and-lift for each grasp_identifier on the asset."""
    # FET005 depends on FET003 PhysX. The grasp-and-lift sequence (close,
    # lift, shake, release) only behaves correctly when the asset carries the
    # validated PhysX physics setup -- PhysX colliders, mass, and a physics
    # scene -- that FET003_BASE_PHYSX certifies. Running it against an asset
    # that has not validated FET003_BASE_PHYSX would exercise physics that is
    # not guaranteed and report a misleading failure, so we skip FET005
    # instead of testing it. asset_validated_features is None for external or
    # forced (--features) runs that carry no workspace validation record; in
    # that case the dependency cannot be checked, so we proceed and run.
    required_feature = "FET003_BASE_PHYSX"
    validated = ctx.asset_validated_features
    if validated is not None and required_feature not in validated:
        ctx.skip(
            "Requires %s to be validated first: grasp-and-lift depends on the "
            "PhysX physics setup, and %s is not in this asset's validated "
            "features." % (required_feature, required_feature)
        )
        return

    # Lazy imports: Kit/USD modules are not available in pure-Python test env
    from simready_benchmark_kit_suite.fet005_grasp.grasp_checks import run_pre_checks

    cfg = ctx.config

    # --- Load asset + room (before pre-checks, same as FET003/FET004) ---
    ctx.set_settle_frames(cfg["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=cfg["asset_load_timeout"])

    import omni.usd

    stage = omni.usd.get_context().get_stage()
    asset_prim_path = ctx.scene.asset.prim_path

    # --- Pre-checks ---
    ctx.step("Discovering grasp identifiers")
    result_str, identifiers = run_pre_checks(stage, asset_prim_path)
    if result_str is not None:
        msg = result_str.replace("SKIP: ", "")
        if result_str.startswith("SKIP: no grasp_identifier"):
            # No identifiers at all -> structural, skip regardless of validation.
            ctx.skip(msg)
        else:
            ctx.precheck_failure(msg)
        return

    ctx.step("Found %d grasp identifier(s)" % len(identifiers))

    # --- Per-identifier loop ---
    num_failed = 0
    failures = []

    for idx, id_path in enumerate(identifiers):
        id_name = id_path.rsplit("/", 1)[-1]
        safe_name = "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in id_name).strip("_") or "grasp"

        ctx.step("Testing identifier %d/%d: %s" % (idx + 1, len(identifiers), id_name))

        # Fresh scene per identifier
        try:
            scene_result = await _test_one_identifier(ctx, cfg, id_path, safe_name, asset_prim_path)
        except Exception as exc:
            scene_result = {
                "phase_name": "Exception",
                "message": str(exc),
                "failed": True,
            }

        passed = not scene_result.get("failed", False)
        ctx.add_metric("grasp_%s_passed" % safe_name, 1 if passed else 0)

        if not passed:
            num_failed += 1
            failures.append((id_path, scene_result.get("message", "unknown")))
            ctx.log("FAILED: %s -- %s" % (id_path, scene_result["message"]))
        else:
            ctx.log("PASSED: %s" % id_path)

    # --- Overall result ---
    total = len(identifiers)
    num_passed = total - num_failed
    ctx.add_metric("grasp_total", total)
    ctx.add_metric("grasp_passed", num_passed)
    ctx.add_metric("grasp_failed", num_failed)

    # Pass if at least one identifier passed; fail only when every
    # identifier failed. Per-identifier failures are still logged above
    # and captured in metrics.
    if num_passed == 0:
        lines = ["All %d grasp identifier(s) failed." % total]
        for path, reason in failures:
            lines.append("  %s: %s" % (path, reason))
        lines.append("")
        lines.append("How to fix:")
        lines.append(
            "- The per-identifier reason above identifies which grasp phase failed "
            "(gripper-positioning, grasping, lifting, hold, dropping, shake, "
            "stability, opening). Treat each phase failure independently."
        )
        lines.append(
            "- Verify `physxRigidBody:mass` and `physxRigidBody:diagonalInertia` on "
            "the asset -- objects with zero or NaN mass cannot be grasped."
        )
        lines.append(
            "- Check `physxMaterial:dynamicFriction` / `staticFriction` on the asset "
            "-- low friction prevents the gripper from holding under gravity."
        )
        lines.append(
            "- Confirm the grasp identifier (USD prim path/name) actually points at a "
            "graspable surface; missing or mis-targeted identifiers fail across all "
            "phases consistently."
        )
        lines.append(
            "- Inspect the captured video for each identifier; common visual cues: "
            "gripper passes through asset (collider missing), asset slips out of "
            "fingers (friction too low), asset shoots away on contact (penetration "
            "depth misconfigured)."
        )
        lines.append(
            "- If the asset is intentionally not graspable for some identifiers, "
            "remove those identifiers from the asset's grasp metadata rather than "
            "tuning physics to make them pass."
        )
        ctx.fail("\n".join(lines))
    elif num_failed > 0:
        summary = "Grasp passed on %d of %d identifier(s); %d failed." % (num_passed, total, num_failed)
        ctx.log(summary)
        for path, reason in failures:
            ctx.warn("%s: %s" % (path, reason))


async def _test_one_identifier(ctx, cfg, identifier_path, safe_name, asset_prim_path):
    # type: (...) -> dict
    """Run the full 9-phase test for a single grasp identifier.

    Builds the gripper, runs simulation, encodes video.
    Returns the final result dict.
    """
    import omni.usd
    from simready_benchmark_engine_kit.physics_utils import (
        configure_physx_determinism,
    )
    from simready_benchmark_kit_suite.fet005_grasp.grasp_scene import GraspScene

    stage = omni.usd.get_context().get_stage()

    # Setup room -- place asset so bbox bottom sits just above ground.
    # This compensates for pivots below the mesh (V1 approach: let gravity
    # settle the object during the stability phase).
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.3, 0.3)
    room.show_ground()
    _place_asset_on_ground(stage, asset_prim_path, margin=0.01)

    ctx.scene.lighting.add_dome(intensity=1000.0)

    physics = ctx.scene.add_physics(gravity=9.81, fps=float(cfg["physics_fps"]))

    configure_physx_determinism(stage, float(cfg["physics_fps"]))
    # No fix_mesh_approximations here: run the asset's collision AS AUTHORED,
    # exactly like Isaac. PhysX performs its own runtime convexHull fallback
    # for dynamic triangle-mesh colliders and emits the diagnostic, which the
    # KitLogMonitor captures into kit_logs (instead of us pre-converting and
    # hiding both the error and Isaac's real collision behaviour).

    # DON'T build gripper before physics. Let the object settle
    # naturally without interference (like FET003). The gripper
    # will be built after stability in the rebuild step.
    grasp_scene = GraspScene(ctx, identifier_path, asset_prim_path)
    grasp_scene.init_tracking()

    # Camera + settle + start physics (no gripper on stage yet)
    ctx.scene.setup_camera_follow()
    await ctx.settle(count=3)

    # Cook dynamic mesh colliders (and author missing mass) OFF the timeline
    # path, time-boxed, BEFORE play() -- a cold SDF cook triggered by play()
    # can freeze the run. Reports a clean failure if a collider cannot cook.
    from simready_benchmark_engine_kit.physics_utils import cook_skip_message

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        return

    physics.stop()
    physics.play()

    ctx.step("Running 9-phase grasp simulation")
    result = await grasp_scene.run_simulation(cfg, safe_name, physics)

    physics.stop()

    return result


def _place_asset_on_ground(stage, asset_prim_path, margin=0.01):
    # type: (Any, str, float) -> None
    """Move asset so its bounding-box bottom is *margin* above Z=0.

    Compensates for pivots that are below the mesh bottom. Without this,
    objects whose local origin is inside/below the mesh would start
    partially underground.
    """
    from pxr import Gf, Usd, UsdGeom

    prim = stage.GetPrimAtPath(asset_prim_path)
    if not prim or not prim.IsValid():
        return
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    bbox = bbox_cache.ComputeWorldBound(prim)
    aligned = bbox.ComputeAlignedBox()
    bbox_min_z = float(aligned.GetMin()[2])

    # Offset so bbox bottom = margin above ground
    z_offset = -bbox_min_z + margin

    # Apply to the asset root (parent of the asset prim)
    root_path = asset_prim_path.rsplit("/", 1)[0]
    root_prim = stage.GetPrimAtPath(root_path)
    if not root_prim or not root_prim.IsValid():
        root_prim = prim
    xformable = UsdGeom.Xformable(root_prim)
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, z_offset))

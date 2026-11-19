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

Evaluates configured lift, hold, shake, and release-motion proxies with a
standardized parallel-jaw gripper at each grasp_identifier_* prim. At least
one completed identifier must pass; this is not a contact-force measurement
or certification that every grasp identifier works.

Skips if no grasp identifiers are found on the asset.
Stops at the first failed phase per identifier.
Fresh scene per identifier for PhysX safety.
"""

import os
from collections import Counter

from simready.evaluate.core.decorator import test
from simready.foundation.contracts import CapabilityId, ContractError, FeatureId
from simready.foundation.tier_core.runtime_tests._assessment import not_applicable

#: Rigid-body contract per runtime, without its version segment. MuJoCo's
#: variant carries no runtime tests, so it is a capability rather than a feature.
_RUNTIME_PHYSICS_FEATURES = {
    "newton": "FET003_RigidBody.Newton",
    "mujoco": "CAP003_RigidBody.MuJoCo",
    "physx": "FET003_RigidBody.PhysX",
}


def _required_physics_feature(runtime):
    # type: (str) -> str | None
    """Return the rigid-body feature/capability family for a recognized runtime."""
    return _RUNTIME_PHYSICS_FEATURES.get(runtime.strip().lower())


def _is_validated(contract, validated):
    # type: (str, object) -> bool
    """Whether any version of ``contract`` is among the validated contract IDs."""
    legacy_contracts = {
        "FET003_RigidBody.Newton": "FET_003_NEWTON",
        "FET003_RigidBody.PhysX": "FET_003_PHYSX",
        "CAP003_RigidBody.MuJoCo": "FET_003_MUJOCO",
    }
    legacy_id = legacy_contracts.get(contract)
    for item in validated:
        if legacy_id is not None and item == legacy_id:
            return True
        try:
            identity = (CapabilityId if contract.startswith("CAP") else FeatureId).parse(item)
        except ContractError:
            continue
        if f"{identity.name}.{identity.runtime}" == contract:
            return True
    return False


def _all_identifiers_failed_message(total: int, failures: list[tuple[str, str, str]]) -> str:
    """Build remediation that matches the phase that actually failed."""
    lines = ["All %d grasp identifier(s) failed." % total]
    for path, _phase, reason in failures:
        lines.append("  %s: %s" % (path, reason))
    lines.extend(("", "How to investigate:"))

    setup_phases = {"FixtureSetup", "Exception"}
    if failures and all(phase in setup_phases for _path, phase, _reason in failures):
        lines.extend(
            (
                "- The test stopped during fixture setup, before grasp behavior was evaluated. "
                "Use the per-identifier exception above as the primary cause.",
                "- For an import or backend exception, repair the Isaac/Kit environment; "
                "asset mass and friction cannot fix a suite dependency failure.",
                "- For body-resolution or bound errors, confirm the grasp segment crosses "
                "one intended rigid body with finite default/render/proxy geometry. A separate "
                "grasp annotation scope is valid and does not need to be reparented.",
            )
        )
        return "\n".join(lines)

    lines.extend(
        (
            "- The per-identifier reason above identifies which grasp phase failed "
            "(gripper-positioning, grasping, lifting, hold, dropping, shake, "
            "stability, opening). Treat each phase failure independently.",
            "- A phase failure is an observation, not proof of its cause or an asset "
            "contract violation. Inspect fixture placement, issued commands, required "
            "live readbacks, cooking and effective contact configuration first.",
            "- Compare the authored grasp segment with the selected rigid body and "
            "its active runtime colliders. Pads meeting can follow missing contact, "
            "misplacement or object ejection; video alone does not distinguish them.",
            "- For a release/drop failure, verify generated-pad opening and release "
            "authoring separately from native contact application before blaming the asset.",
            "- Preserve the original asset and declared identifiers. Propose an asset "
            "change only after proving a violation of the selected contract; do not "
            "remove identifiers or retune ratings merely to obtain a pass.",
        )
    )
    if any(phase in {"Lifting", "HoldBeforeShake", "HoldAfterShake", "Shake"} for _path, phase, _reason in failures):
        lines.append(
            "- When load/contact evidence is relevant, inspect the composed UsdPhysics "
            "`physics:mass` / `physics:diagonalInertia` and the resolved physics-purpose "
            "material `physics:staticFriction` / `physics:dynamicFriction`, including "
            "the generated fixture and runtime import. Their presence alone does not "
            "establish the cause of a sampled grip loss."
        )
    return "\n".join(lines)


def _identifier_output_aliases(identifiers):
    """Keep unique legacy labels; disambiguate collisions on Windows and Linux."""
    bases = [
        "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in path.rsplit("/", 1)[-1]).strip("_") or "grasp"
        for path in identifiers
    ]
    counts = Counter(base.casefold() for base in bases)
    # Reserve every legacy name before allocating suffixes, including unique
    # names that occur later. New aliases must never overwrite those labels.
    reserved = set(counts)
    aliases = []
    for index, base in enumerate(bases, 1):
        if counts[base.casefold()] == 1:
            alias = base
        else:
            stem = "%s_identifier_%03d" % (base, index)
            alias = stem
            suffix = 2
            while alias.casefold() in reserved:
                alias = "%s_%d" % (stem, suffix)
                suffix += 1
            reserved.add(alias.casefold())
        aliases.append(alias)
    return aliases


@test(
    features=[
        {"id": "FET005_Grasp.0-1-0", "version": "*"},
    ],
    name="grasp_and_lift",
    description=(
        "Iterates each grasp_identifier_* prim authored on the asset. At "
        "each, positions a synthetic gantry parallel-jaw gripper at the "
        "identifier's pose, closes it onto the asset, lifts the gripper "
        "by a configurable height, holds, optionally applies a circular horizontal "
        "orbit shake, and releases it. Records each identifier's measured phase "
        "outcome and passes when at least one identifier completes the procedure. "
        "Unexpected setup, required-readback or cleanup errors remain incomplete "
        "execution, even after an earlier identifier passed. Checks the active "
        "runtime's validated rigid-body feature/capability family: a validation "
        "record missing that prerequisite causes a skip, while a forced/external "
        "run without a validation record can proceed without that qualification. "
        "Motion proxies do not directly measure contact or holding force."
    ),
    expected_video=(
        "For each grasp_identifier on the asset: a parallel-jaw gripper "
        "moves to the identifier's pose, closes around the asset, lifts "
        "it cleanly off the floor, holds it in mid-air, optionally shakes "
        "through a circular horizontal orbit, then opens to drop. The asset should follow the "
        "gripper's lift motion. Configured lift, hold, shake and fall proxies "
        "determine the result, not every visible shift; a failed clip can end "
        "before later phases. This footage is not a native contact measurement."
    ),
    version="1.3.5",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "physics_fps": 240,
        "capture_fps": 15,
        "simulation_seconds": 15.0,
        # Preserve the terminal verdict immediately, then keep stepping and
        # recording so the video shows why the object was lost.
        "post_failure_observation_seconds": 1.0,
        "close_duration": 0.5,
        "close_ramp_speed_m_s": 0.04,
        # Lower bound for the bounded settling budget, combined with
        # close_max_settle_seconds. The actual continuous dwell is controlled
        # by post_grasp_stability_seconds, including convergence during ramp.
        "close_settle_seconds": 0.3,
        # Do not begin Lifting while the fingers are still moving or rebounding
        # from an initial encounter. Require a bounded stable-position window;
        # this observation is a motion proxy, not native contact detection.
        "close_convergence_hold_seconds": 0.1,
        # Preserve the squeeze that produced a stable bilateral grasp and
        # observe it for another 0.3 seconds before beginning the lift.
        "post_grasp_stability_seconds": 0.3,
        "close_convergence_tolerance": 0.0005,
        "close_object_settle_tolerance": 0.0005,
        "close_contact_travel_tolerance": 0.002,
        "grasp_contact_compression": 0.005,
        "close_max_settle_seconds": 2.0,
        "lift_duration": 1.0,
        "open_duration": 0.5,
        "lift_height_multiplier": 2.0,
        "lift_min_delta_z": 0.02,
        "lift_min_height": 0.3,
        "lift_max_height": 0.5,
        # Minimum release fall used by Dropping. The required distance is the
        # larger of this value and the grasped body's bounding-box height.
        "fall_min_delta_z": 0.05,
        # Hold-phase drop tolerance (separate from fall_min_delta_z so
        # phase_dropping's "did it actually fall when released?" check
        # stays strict). Long thin objects -- dishwand-style tools,
        # handles -- can shift 5-10cm in bounding-box-centre z while firmly
        # gripped near one end: the bbox tip rotates in the gripper
        # which drags the centre down without the object falling out.
        # 10cm is the configured centre-drop proxy allowance.
        "hold_drop_tolerance": 0.10,
        "hold_seconds": 1.0,
        "shake_duration_seconds": 1.5,
        "shake_amplitude": 0.01,
        "shake_frequency_hz": 2.0,
        # Ease the gantry into and out of the circular orbit. Starting the
        # cosine component at full amplitude creates a one-frame position
        # discontinuity and an artificial contact impulse.
        "shake_ramp_seconds": 0.25,
        "shake_grip_separation_tolerance": 0.05,
        "enable_shake_test": True,
        "stability_max_seconds": 3.0,
        "rest_tolerance": 0.002,
        "rest_detection_hold_seconds": 1.0,
        "pad_touching_tolerance": 0.002,
        "floor_level": 0.0,
        # Raise the generated gripper when necessary so the complete oriented
        # pad boxes remain above the room floor.
        "pad_ground_clearance": 0.002,
        # Geometric floor proxies, not collision-contact measurements.
        # Shake checks bbox minimum Z <= floor_level + floor_margin;
        # Hold checks bbox centre Z < floor_level - floor_margin. Thus this
        # negative margin allows a 0.02 below-floor box dip in Shake, while
        # Hold's centre-height threshold is 0.02 above the default floor.
        "floor_margin": -0.02,
        "release_check_seconds": 0.5,
        "drop_check_seconds": 3.0,
        "post_drop_observation_seconds": 1.0,
        "asset_load_timeout": 30,
        "settle_frames": 5,
        "show_gripper": True,
    },
    max_duration=1200,
)
async def test_grasp_and_lift(ctx):
    """Test grasp-and-lift for each grasp_identifier on the asset."""
    # FET005 depends on the active runtime's FET003 physics contract. Running
    # it against an asset that has not validated that contract would exercise
    # physics that is not guaranteed and report a misleading failure, so skip
    # FET005 instead of testing it. asset_validated_features is None for external or
    # forced (--features) runs that carry no workspace validation record; in
    # that case the dependency cannot be checked, so we proceed and run.
    runtime = os.environ.get("SIMREADY_PHYSICS_RUNTIME", "PhysX")
    required_feature = _required_physics_feature(runtime)
    if required_feature is None:
        ctx.skip(
            "Unsupported SIMREADY_PHYSICS_RUNTIME value %r. Expected one of: "
            "%s. FET005 was not run because its runtime-specific FET003 "
            "dependency cannot be determined." % (runtime, ", ".join(sorted(_RUNTIME_PHYSICS_FEATURES)))
        )
        return

    validated = ctx.asset_validated_features
    if validated is not None and not _is_validated(required_feature, validated):
        ctx.skip(
            "Requires %s to be validated first: grasp-and-lift depends on the "
            "active runtime physics setup, and %s is not in this asset's validated "
            "features." % (required_feature, required_feature)
        )
        return

    # Lazy imports: Kit/USD modules are not available in pure-Python test env
    from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_checks import run_pre_checks

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
            # A complete asset with no identifiers has no grasp behavior to exercise.
            ctx.add_metric("assessment_applicability", not_applicable("no_grasp_identifiers", msg))
            ctx.skip(msg)
        elif result_str.startswith("SKIP: grasp_identifier prims exist"):
            ctx.skip(msg)
        else:
            ctx.precheck_failure(msg)
        return

    ctx.step("Found %d grasp identifier(s)" % len(identifiers))

    # --- Per-identifier loop ---
    num_failed = 0
    failures = []

    aliases = _identifier_output_aliases(identifiers)
    for idx, id_path in enumerate(identifiers):
        id_name = id_path.rsplit("/", 1)[-1]
        safe_name = aliases[idx]
        ctx.add_metric("grasp_%s_identifier_path" % safe_name, id_path)

        ctx.step("Testing identifier %d/%d: %s" % (idx + 1, len(identifiers), id_name))

        if idx:
            # Each identifier starts from the same source revision, not the
            # preceding trial's released pose, runtime overrides or contacts.
            try:
                if ctx.scene.clear() is False:
                    raise RuntimeError("Required FET005 scene reset was rejected")
            except BaseException as error:
                _record_identifier_cleanup_failure(ctx, "scene reset", error)
                raise
            ctx.scene.load_asset(ctx.asset_path, timeout=cfg["asset_load_timeout"])
            stage = omni.usd.get_context().get_stage()
            asset_prim_path = ctx.scene.asset.prim_path

        # Fresh scene per identifier
        # Only an actually evaluated phase may return a behavioral failure.
        # Setup, command, readback and cleanup exceptions keep their original
        # cause for the runner's incomplete execution outcome.
        scene_result = await _test_one_identifier(ctx, cfg, id_path, safe_name, asset_prim_path)

        # Asset-wide early exits apply equally to every grasp identifier. The
        # helper returns a signal dict so this caller can set the whole-test
        # verdict once and stop without treating None as a phase result.
        if scene_result.get("skip"):
            ctx.skip(scene_result["skip"])
            return
        if scene_result.get("precheck"):
            ctx.precheck_failure(scene_result["precheck"])
            return

        passed = not scene_result.get("failed", False)
        ctx.add_metric("grasp_%s_passed" % safe_name, 1 if passed else 0)

        if not passed:
            num_failed += 1
            failures.append(
                (
                    id_path,
                    scene_result.get("phase_name", "Unknown"),
                    scene_result.get("message", "unknown"),
                )
            )
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
        ctx.fail(_all_identifiers_failed_message(total, failures))
    elif num_failed > 0:
        summary = "Grasp passed on %d of %d identifier(s); %d failed." % (num_passed, total, num_failed)
        ctx.log(summary)
        for path, _phase, reason in failures:
            ctx.warn("%s: %s" % (path, reason))


async def _test_one_identifier(ctx, cfg, identifier_path, safe_name, asset_prim_path):
    # type: (...) -> dict
    """Run the full 9-phase test for a single grasp identifier.

    Builds the gripper, runs simulation, encodes video.
    Returns the final result dict.
    """
    try:
        import omni.usd
        from isaacsim.core.utils.stage import update_stage_async
        from simready.evaluate_engine_kit.physics_utils import (
            active_physics_engine,
            configure_physx_determinism,
        )
        from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_scene import GraspScene
        from simready.foundation.tier_core.runtime_tests.fet005_grasp.newton_articulation import (
            apply_temporary_newton_articulations,
            remove_temporary_newton_articulations,
        )
    except Exception as exc:
        # Binary ABI conflicts can raise ValueError while Python is importing a
        # C extension. Normalize every exception raised inside this import-only
        # boundary so the engine reports a suite/environment error instead of
        # an asset grasp failure with physics remediation advice.
        raise ImportError("FET_005 runtime dependency import failed (%s): %s" % (type(exc).__name__, exc)) from exc

    stage = omni.usd.get_context().get_stage()
    temporary_articulations = []
    physics = None
    grasp_scene = None
    original_error = None
    owned_fixture_paths = []
    for fixture_path in ("/World/grasp_robot", "/World/GripperMaterial"):
        if stage.GetPrimAtPath(fixture_path).IsValid():
            raise RuntimeError("FET005 fixture namespace already exists: " + fixture_path)
        owned_fixture_paths.append(fixture_path)

    try:
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

        if active_physics_engine() == "newton":
            temporary_articulations = apply_temporary_newton_articulations(stage, asset_prim_path)
            if temporary_articulations:
                ctx.log(
                    "[newton-articulation] temporary roots: "
                    + ", ".join(mutation.path for mutation in temporary_articulations)
                )

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
        from simready.evaluate_engine_kit.physics_utils import cook_skip_message

        cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
        if cook_skip is not None:
            return {"precheck": cook_skip[5:].strip()}

        if physics.stop() is False:
            raise RuntimeError("Required FET005 initial physics stop was rejected")
        if physics.play() is False:
            raise RuntimeError("Required FET005 physics start was rejected")

        if active_physics_engine() == "newton":
            # Newton builds its simulation asynchronously from the composed
            # stage. Pump updates before querying the sim view, then skip
            # unsupported loose/cyclic joint topologies without stepping a
            # broken simulation.
            await ctx.settle(count=3)
            from simready.foundation.tier_core.runtime_tests.engine_guard import (
                NEWTON_SCENE_ERROR,
                NewtonSceneInitializationError,
                newton_scene_initialized,
            )

            if not newton_scene_initialized():
                raise NewtonSceneInitializationError(NEWTON_SCENE_ERROR)

        ctx.step("Running 9-phase grasp simulation")
        return await grasp_scene.run_simulation(cfg, safe_name, physics)
    except BaseException as exc:
        original_error = exc
        raise
    finally:
        robot = getattr(grasp_scene, "robot", None) if grasp_scene is not None else None
        await _cleanup_identifier_scene(
            ctx,
            physics,
            robot,
            stage,
            temporary_articulations,
            remove_temporary_newton_articulations,
            update_stage_async,
            original_error,
            owned_fixture_paths=owned_fixture_paths,
        )


def _record_identifier_cleanup_failure(ctx, operation, primary):
    """Best-effort native health reporting never replaces its required cause."""
    try:
        adapter = getattr(ctx, "_engine_session", None)
        callback = getattr(adapter, "record_required_cleanup_failure", None)
        if callable(callback):
            callback("Required FET005 %s failed." % operation)
    except BaseException as diagnostic_error:
        try:
            primary.add_note("Cleanup health reporting also failed (%s)." % type(diagnostic_error).__name__)
        except BaseException:
            pass


async def _cleanup_identifier_scene(
    ctx,
    physics,
    robot,
    stage,
    temporary_articulations,
    restore_articulations,
    update_stage,
    original_error=None,
    *,
    owned_fixture_paths=(),
):
    """Stop before restoring topology and preserve the original execution cause."""
    primary = original_error

    def defer(error, operation):
        nonlocal primary
        if primary is None:
            primary = error
        elif primary is not error:
            try:
                primary.add_note("Required FET005 %s also failed (%s)." % (operation, type(error).__name__))
            except BaseException:
                pass
        _record_identifier_cleanup_failure(ctx, operation, primary)

    if original_error is not None and getattr(original_error, "_fet005_required_cleanup_failed", False) is True:
        defer(original_error, "temporary articulation rollback")
    stopped = physics is None
    if physics is not None:
        try:
            if physics.stop() is False:
                raise RuntimeError("Required FET005 physics stop was rejected")
            stopped = True
        except BaseException as error:
            defer(error, "physics stop")
    controller_closed = robot is None
    if robot is not None and stopped:
        try:
            if robot.teardown() is False:
                raise RuntimeError("Required FET005 generated controller teardown was rejected")
            controller_closed = True
        except BaseException as error:
            defer(error, "generated controller teardown")
    topology_safe = stopped and controller_closed
    if temporary_articulations and topology_safe:
        try:
            restore_articulations(stage, temporary_articulations)
            await update_stage()
        except BaseException as error:
            defer(error, "temporary articulation restoration")
    if owned_fixture_paths and topology_safe:
        try:
            from simready.evaluate_engine_kit.stage_cleanup import remove_scene_prim
        except BaseException as error:
            defer(error, "generated fixture cleanup import")
        else:
            for fixture_path in owned_fixture_paths:
                try:
                    remove_scene_prim(stage, fixture_path)
                except BaseException as error:
                    defer(error, "generated fixture removal")
            try:
                await update_stage()
            except BaseException as error:
                defer(error, "generated fixture removal update")
    if original_error is None and primary is not None:
        raise primary


def _place_asset_on_ground(stage, asset_prim_path, margin=0.01):
    # type: (Any, str, float) -> None
    """Move asset so its bounding-box bottom is *margin* above Z=0.

    Compensates for pivots that are below the mesh bottom. Without this,
    objects whose local origin is inside/below the mesh would start
    partially underground.
    """
    from pxr import Gf, Usd, UsdGeom
    from simready.evaluate_engine_kit.fabric_utils import validated_bounds
    from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_utils import (
        _required_real_observation,
    )

    margin = _required_real_observation(margin, "Ground placement margin")
    prim = stage.GetPrimAtPath(asset_prim_path)
    if not prim or not prim.IsValid():
        raise RuntimeError("Required FET005 ground-placement asset is missing: " + str(asset_prim_path))
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    bbox = bbox_cache.ComputeWorldBound(prim)
    aligned = bbox.ComputeAlignedBox()
    if aligned.IsEmpty():
        raise RuntimeError("Required FET005 ground-placement asset bounds are empty")
    minimum, _maximum = validated_bounds(aligned.GetMin(), aligned.GetMax())
    bbox_min_z = minimum[2]

    # Offset so bbox bottom = margin above ground
    z_offset = _required_real_observation(-bbox_min_z + margin, "Ground placement offset")

    # Apply to the asset root (parent of the asset prim)
    root_path = asset_prim_path.rsplit("/", 1)[0]
    root_prim = stage.GetPrimAtPath(root_path)
    if not root_prim or not root_prim.IsValid():
        root_prim = prim
    xformable = UsdGeom.Xformable(root_prim)
    if not xformable:
        raise RuntimeError("Required FET005 ground-placement root is not transformable")
    if xformable.ClearXformOpOrder() is not True or xformable.GetOrderedXformOps():
        raise RuntimeError("Required FET005 ground-placement transform order could not be cleared")
    translation = (0.0, 0.0, z_offset)
    operation = xformable.AddTranslateOp()
    if operation.Set(Gf.Vec3d(*translation)) is not True:
        raise RuntimeError("Required FET005 ground-placement translation was rejected")
    authored_translation = operation.Get()
    observed, _ = validated_bounds(authored_translation, authored_translation)
    ordered = xformable.GetOrderedXformOps()
    if observed != translation or len(ordered) != 1 or ordered[0].GetOpName() != operation.GetOpName():
        raise RuntimeError("Required FET005 ground-placement translation was not authored as requested")

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


"""Newton-owned flat-ground fixture and qualified sampled observations.

Drop and stability have independent verdicts but keep the same placement,
proximity/overlap allowances and rest/deadline observation schedule. Nothing
here measures collision contacts, velocities or continuous stability.
"""

import math
from numbers import Real

from simready.foundation.tier_newton.runtime_tests.placement_compat import place_with_minimum_clearance
from simready.foundation.tier_newton.runtime_tests._assessment import (
    _has_complete_scene_asset,
    not_applicable,
)
from simready.foundation.tier_newton.runtime_tests.fet003_physics._drop_config import (
    validate_drop_config,
)
from simready.foundation.tier_newton.runtime_tests.fet003_physics.stability import (
    bounds_to_history_entry,
    check_rest_window,
)
from simready.foundation.tier_newton.runtime_tests.motion_observer import (
    MotionObserver,
    drop_metadata,
)


def validate_ground_config(config, *, require_rest):
    """Qualify gate inputs before scene changes, retaining drop's zero policy."""
    validate_drop_config(config)
    derived = (
        config["floor_level"] + config["floor_margin"],
        config["floor_level"] - config["floor_margin"],
        config["floor_level"] + config["floor_margin"] + config["minimum_drop_distance"],
        config["penetration_check_seconds"] * config["physics_fps"],
        config["rest_detection_hold_seconds"] * config["physics_fps"],
        config["rest_detection_max_seconds"] * config["physics_fps"],
        config["simulation_seconds"] * config["physics_fps"],
        config["simulate_after_result_seconds"] * config["physics_fps"],
        config["rest_tolerance"] * config["rest_tolerance"],
    )
    try:
        finite = all(math.isfinite(value) for value in derived)
    except (OverflowError, TypeError, ValueError):
        finite = False
    if not finite:
        raise RuntimeError("Ground observation requires finite derived thresholds and step budgets")
    if require_rest:
        hold_samples = math.ceil(config["rest_detection_hold_seconds"] * config["physics_fps"]) + 1
        if hold_samples < 2:
            raise RuntimeError("Ground stability requires rest_detection_hold_seconds covering at least two samples")
        minimum_elapsed = max(hold_samples - 1, math.ceil(config["penetration_check_seconds"] * config["physics_fps"]))
        deadline_steps = int(config["rest_detection_max_seconds"] * config["physics_fps"])
        total_steps = int(config["simulation_seconds"] * config["physics_fps"])
        if deadline_steps < minimum_elapsed:
            raise RuntimeError("Ground stability rest_detection_max_seconds cannot contain its full rest window")
        if total_steps < minimum_elapsed + 1:
            raise RuntimeError("Ground stability simulation_seconds cannot contain its full post-proximity rest window")


def qualified_bounds(bounds):
    """Reject malformed required geometry instead of manufacturing a criterion."""
    try:
        minimum, maximum = tuple(bounds.min), tuple(bounds.max)
        if len(minimum) != 3 or len(maximum) != 3:
            raise ValueError("bounds must have three coordinates per corner")
        for value in minimum + maximum:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError("bounds coordinates must be finite real numbers")
        if any(high < low for low, high in zip(minimum, maximum, strict=True)):
            raise ValueError("bounds corners are inverted")
        if not any(high > low for low, high in zip(minimum, maximum, strict=True)):
            raise ValueError("bounds contain no measurable geometry")
        entry = bounds_to_history_entry(bounds)
        if not all(math.isfinite(value) for value in entry):
            raise ValueError("bounds produce a nonfinite required center")
        return entry
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        raise RuntimeError("Ground observation requires finite, ordered, nonempty asset bounds") from error


def apply_ground_physics_material(ground_path="/World/GroundPlane"):
    """Require the generated collision ground and verified typed physics material."""
    import omni.usd
    from pxr import UsdPhysics, UsdShade

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Ground fixture stage is unavailable")
    ground = stage.GetPrimAtPath(ground_path + "/CollisionMesh")
    if not ground or not ground.IsValid() or not ground.HasAPI(UsdPhysics.CollisionAPI):
        raise RuntimeError("Ground fixture requires collision-enabled CollisionMesh geometry")
    if UsdPhysics.CollisionAPI(ground).GetCollisionEnabledAttr().Get() is not True:
        raise RuntimeError("Ground fixture CollisionMesh collision is disabled or unqualified")
    material = UsdShade.Material.Define(stage, ground_path + "/PhysMaterial")
    physics_material = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    if not material or not physics_material:
        raise RuntimeError("Ground fixture physics material could not be defined")
    for create, expected in (
        (physics_material.CreateStaticFrictionAttr, 0.5),
        (physics_material.CreateDynamicFrictionAttr, 0.4),
        (physics_material.CreateRestitutionAttr, 0.0),
    ):
        attribute = create()
        if not attribute or not attribute.Set(expected):
            raise RuntimeError("Ground fixture physics material property could not be authored")
        observed = attribute.Get()
        if (
            isinstance(observed, bool)
            or not isinstance(observed, Real)
            or not math.isclose(observed, expected, rel_tol=1e-6, abs_tol=1e-7)
        ):
            raise RuntimeError("Ground fixture physics material property readback disagrees with its control")
    binding = UsdShade.MaterialBindingAPI.Apply(ground)
    if not binding or binding.Bind(material, UsdShade.Tokens.strongerThanDescendants, "physics") is False:
        raise RuntimeError("Ground fixture physics material binding was rejected")
    bound, _ = binding.ComputeBoundMaterial(materialPurpose="physics")
    if not bound or bound.GetPath() != material.GetPath():
        raise RuntimeError("Ground fixture effective physics material binding is unqualified")


def stop_physics(physics, ctx, primary=None):
    """Required cleanup preserves the first execution error or cancellation."""
    try:
        if physics.stop() is False:
            raise RuntimeError("Ground fixture physics stop was rejected")
    except BaseException as cleanup_error:
        from simready.foundation.tier_newton.runtime_tests.articulation_phases._diagnostic_notes import (
            note_secondary_error,
            record_required_cleanup_failure,
        )

        record_required_cleanup_failure(ctx, "Ground fixture physics stop failed", primary)
        if primary is None:
            raise
        note_secondary_error(
            primary, lambda cleanup_error=cleanup_error: f"Required ground physics cleanup also failed: {cleanup_error}"
        )


def _optional_observer_call(observer, method, *args):
    """Diagnostic recording errors never replace qualified test observations."""
    if observer is not None:
        try:
            getattr(observer, method)(*args)
        except Exception:
            pass


def _sampled_variation(history, hold_frames):
    """Derive graph evidence from the already-qualified complete hold window."""
    if len(history) < hold_frames:
        return None, None
    try:
        latest = history[-1]
        window = history[-hold_frames:]
        center = max(math.sqrt(sum((row[i] - latest[i]) ** 2 for i in range(3))) for row in window)
        corners = max(abs(row[i] - latest[i]) for row in window for i in range(3, 9))
        return center, corners
    except Exception:
        return None, None


async def observe_ground(ctx, config, initial_bounds, label):
    """Observe the unchanged flat-ground window using required live bounds."""
    physics_fps = int(config["physics_fps"])
    capture_fps = int(config["capture_fps"])
    touch_threshold = float(config["floor_level"] + config["floor_margin"])
    pen_threshold = float(config["floor_level"] - config["floor_margin"])
    stability = label == "ground_stability"
    pen_check_frames = (
        math.ceil(config["penetration_check_seconds"] * physics_fps)
        if stability
        else int(config["penetration_check_seconds"] * physics_fps)
    )
    # N observations contain N-1 intervals. Standalone stability requires the
    # entire elapsed hold; drop retains its established diagnostic schedule.
    hold_frames = (
        math.ceil(config["rest_detection_hold_seconds"] * physics_fps) + 1
        if stability
        else max(1, int(config["rest_detection_hold_seconds"] * physics_fps))
    )
    max_rest_frames = int(config["rest_detection_max_seconds"] * physics_fps)
    after_result_frames = int(config["simulate_after_result_seconds"] * physics_fps)
    total_frames = int(config["simulation_seconds"] * physics_fps)
    capture_interval = max(1, physics_fps // capture_fps)
    rest_tol = float(config["rest_tolerance"])
    initial = qualified_bounds(initial_bounds)
    if initial[5] <= touch_threshold:
        raise RuntimeError("Ground fixture initial bounds must start above the proximity threshold")
    state = {
        "touched": False,
        "penetrated": False,
        "rest_detected": False,
        "touch_frame": -1,
        "rest_frame": -1,
        "last_frame": -1,
        "history": [],
        "post_touch_history": [],
        "frames": [],
        "overlap_window_complete": False,
        "deadline_completed": False,
    }
    previous_z = initial[5]
    result_frame = -1
    channels = {
        "center_x": {"unit": "stage_length", "source": "runtime world-aligned bounding box center"},
        "center_y": {"unit": "stage_length", "source": "runtime world-aligned bounding box center"},
        "center_z": {"unit": "stage_length", "source": "runtime world-aligned bounding box center"},
        "minimum_z": {"unit": "stage_length", "source": "runtime world-aligned bounding box minimum"},
        "touch_threshold": {"unit": "stage_length", "source": "test bounding-box proximity threshold"},
        "penetration_threshold": {"unit": "stage_length", "source": "test bounding-box overlap threshold"},
    }
    if label == "ground_stability":
        channels.update(
            {
                "center_window_max_distance": {
                    "unit": "stage_length",
                    "source": "maximum sampled window center distance to latest center",
                },
                "corner_window_max_variation": {
                    "unit": "stage_length",
                    "source": "maximum sampled window AABB corner-coordinate variation to latest corners",
                },
                "rest_tolerance": {"unit": "stage_length", "source": "configured sampled rest tolerance"},
            }
        )
    try:
        measurement_context = drop_metadata(ctx, physics_fps, capture_fps)
    except Exception:
        measurement_context = {"context_partial": True}
    try:
        motion = MotionObserver(
            ctx,
            label,
            channels,
            metadata={
                **measurement_context,
                "clock_basis": "nominal observed step index / configured physics fps; capture ticks are not counted",
                "contact_basis": "AABB threshold crossing, not measured contact force",
                "rest_tolerance": rest_tol,
                "rest_window_samples": hold_frames,
                "rest_window_basis": "entirely post-proximity observed samples",
                "rest_floor_proximity_required": stability,
                "rest_floor_proximity_basis": (
                    "every retained rest-window minimum Z within configured overlap/proximity thresholds"
                    if stability
                    else "legacy drop diagnostic rest; does not certify sustained floor proximity"
                ),
                "rest_acceptance_deadline_seconds": float(config["rest_detection_max_seconds"]),
                "ground_static_friction": 0.5,
                "ground_dynamic_friction": 0.4,
                "ground_restitution": 0.0,
                "floor_level_stage_length": float(config["floor_level"]),
                "proximity_allowance_stage_length": float(config["floor_margin"]),
                "overlap_allowance_stage_length": float(config["floor_margin"]),
                "stability_basis": "post-proximity sampled AABB center and min/max corner variation; not velocity thresholds or continuous stability proof",
            },
        )
    except Exception:
        motion = None
    for frame in range(total_frames):
        await ctx.physics_step()
        bounds = ctx.get_asset_bounds()
        entry = qualified_bounds(bounds)
        z_min = entry[5]
        state["last_frame"] = frame
        state["history"].append(entry)
        if not state["touched"] and previous_z > touch_threshold and z_min <= touch_threshold:
            state["touched"] = True
            state["touch_frame"] = frame
            ctx.step("Ground proximity at sample %d (z=%.4f)" % (frame, z_min))
        if state["touched"]:
            state["post_touch_history"].append(entry)
            since_touch = frame - state["touch_frame"]
            state["overlap_window_complete"] = since_touch >= pen_check_frames
            state["deadline_completed"] = since_touch >= max_rest_frames
            if z_min < pen_threshold:
                state["penetrated"] = True
                if result_frame < 0:
                    result_frame = frame
            # A complete window must follow proximity; midair observations and
            # post-deadline video-tail observations cannot certify stability.
            if (
                not state["rest_detected"]
                and not state["penetrated"]
                and state["overlap_window_complete"]
                and since_touch <= max_rest_frames
                and (
                    not stability
                    or all(
                        pen_threshold <= sample[5] <= touch_threshold
                        for sample in state["post_touch_history"][-hold_frames:]
                    )
                )
                and check_rest_window(state["post_touch_history"], hold_frames, rest_tol, rest_tol)
            ):
                state["rest_detected"] = True
                state["rest_frame"] = frame
                if result_frame < 0:
                    result_frame = frame
            if not state["rest_detected"] and state["deadline_completed"] and result_frame < 0:
                result_frame = frame
        sample = {
            "center_x": entry[0],
            "center_y": entry[1],
            "center_z": entry[2],
            "minimum_z": z_min,
            "touch_threshold": touch_threshold,
            "penetration_threshold": pen_threshold,
        }
        if label == "ground_stability":
            center, corners = _sampled_variation(state["post_touch_history"], hold_frames)
            sample.update(
                center_window_max_distance=center, corner_window_max_variation=corners, rest_tolerance=rest_tol
            )
        _optional_observer_call(
            motion,
            "sample",
            sample,
            (frame + 1) / float(physics_fps),
            (
                "penetration"
                if state["penetrated"]
                else "rest_detected" if state["rest_detected"] else "after_touch" if state["touched"] else "fall"
            ),
        )
        ctx.scene.update_camera_follow()
        previous_z = z_min
        if frame % capture_interval == 0:
            capture = await ctx.capture_frame(label=label)
            if capture:
                state["frames"].append(capture)
                _optional_observer_call(motion, "record_capture", capture)
        if result_frame >= 0 and frame - result_frame >= after_result_frames:
            break
        await ctx.physics_advance()
    _optional_observer_call(
        motion,
        "finish",
        (
            "penetration"
            if state["penetrated"]
            else (
                "rest_detected"
                if state["rest_detected"]
                else "rest_deadline" if state["deadline_completed"] else "step_budget_exhausted"
            )
        ),
    )
    return state


async def run_ground_trial(ctx, *, label, require_rest):
    """Build the Newton-local fixture, observe and always stop required physics."""
    validate_ground_config(ctx.config, require_rest=require_rest)
    config = ctx.config
    ctx.set_settle_frames(config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=config["asset_load_timeout"])
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)
    room.show_ground(color=(0.25, 0.35, 0.6))
    threshold = float(config["floor_level"] + config["floor_margin"])
    if not place_with_minimum_clearance(
        room.place_asset_above_ground,
        threshold + float(config["minimum_drop_distance"]),
        height_factor=config["drop_height_factor"],
    ):
        ctx.log(
            "The installed Kit provider does not support minimum drop clearance; using legacy height-based placement."
        )
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
            ctx.add_metric(label + "_skipped", 1)
        elif pre_result.startswith("SKIP:"):
            ctx.precheck_failure(pre_result[5:].strip())
            ctx.add_metric(label + "_passed", 0)
        else:
            ctx.fail(pre_result)
            ctx.add_metric(label + "_passed", 0)
        return None
    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=9.81, fps=float(config["physics_fps"]))
    primary = None
    try:
        ground_path = ctx.scene.enable_ground_plane(friction=0.5, position=(0.0, 0.0, float(config["floor_level"])))
        apply_ground_physics_material(ground_path)
        ctx.scene.setup_camera_follow()
        await ctx.settle(count=3)
        import omni.usd
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
            ctx.add_metric(label + "_passed", 0)
            return None
        articulationize_loose_joints(ctx, omni.usd.get_context().get_stage())
        await ctx.settle(count=1)
        physics.play()
        await ctx.settle(count=3)
        newton_ready = newton_scene_initialized()
        stop_physics(physics, ctx)
        if not newton_ready:
            raise NewtonSceneInitializationError(NEWTON_SCENE_ERROR)
        # Authored setup bounds describe placement, never evaluated motion.
        init_bounds = ctx.get_asset_bounds(authored=True)
        initial = qualified_bounds(init_bounds)
        ctx.add_metric(label + "_initial_z_min", initial[5], unit="stage_length")
        ctx.add_metric(label + "_bbox_height", initial[8] - initial[5], unit="stage_length")
        ctx.add_metric(label + "_effective_fall", initial[5] - threshold, unit="stage_length")
        physics.play()
        ctx.step("Observing ground proximity, overlap and sampled rest")
        return await observe_ground(ctx, config, init_bounds, label)
    except BaseException as error:
        primary = error
        raise
    finally:
        stop_physics(physics, ctx, primary)


def report_ground_result(ctx, state, *, label, require_rest):
    """Only measured conditions fail; incomplete windows remain execution errors."""
    if state is None:
        return
    touched, penetrated, rest = state["touched"], state["penetrated"], state["rest_detected"]
    if touched and not penetrated and not state["overlap_window_complete"]:
        raise RuntimeError("Ground observation budget ended before the required post-proximity overlap window")
    if require_rest and touched and not penetrated and not rest and not state["deadline_completed"]:
        raise RuntimeError("Ground stability observation budget ended before its post-proximity rest deadline")
    passed = touched and not penetrated and (rest if require_rest else True)
    ctx.add_metric(label + "_touched", int(touched))
    ctx.add_metric(label + "_penetrated", int(penetrated))
    ctx.add_metric(label + "_stable", int(rest))
    ctx.add_metric(label + "_passed", int(passed))
    ctx.add_metric(label + "_overlap_window_complete", int(state["overlap_window_complete"]))
    ctx.add_metric(label + "_rest_deadline_complete", int(state["deadline_completed"]))
    if require_rest:
        ctx.add_metric(label + "_rest_detected", int(rest))
    for key in ("touch", "rest"):
        if state[key + "_frame"] >= 0:
            ctx.add_metric(
                label + "_" + key + "_time", (state[key + "_frame"] + 1) / float(ctx.config["physics_fps"]), unit="s"
            )
    title = "Ground stability" if require_rest else "Ground drop"
    if passed:
        ctx.log(
            title
            + " PASSED: qualified proximity and allowed-overlap proxies"
            + (
                " with a complete post-proximity sampled-rest window."
                if require_rest
                else "; settling is assessed separately by ground_stability_newton."
            )
        )
        return
    if not touched:
        reason = "The bounding-box proximity threshold was not crossed within the observed step budget."
    elif penetrated:
        reason = "Bounding-box floor overlap exceeded the configured allowance after proximity. This is not measured collider penetration."
    else:
        reason = "No complete post-proximity rest window stayed in the configured floor-proximity/allowed-overlap band while center and box-corner variation met their tolerance before the deadline."
    ctx.fail(
        title
        + " FAILED: "
        + reason
        + " Review the native result, motion history, fixture configuration and engine log; this observation alone does not establish an asset-authoring defect."
    )


def encode_ground_video(ctx, state, label):
    """Summary media is optional; cancellation and required causes stay distinct."""
    if state is not None and state["frames"]:
        try:
            ctx.encode_video(state["frames"], fps=int(ctx.config["capture_fps"]), label=label, role="summary")
        except Exception:
            try:
                ctx.warn("Ground summary video could not be encoded; test criteria are unchanged.")
            except Exception:
                pass

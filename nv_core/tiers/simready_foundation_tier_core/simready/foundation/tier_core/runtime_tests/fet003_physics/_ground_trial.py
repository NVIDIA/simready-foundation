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


"""Core-owned PhysX ground trial; public drop/rest verdicts remain independent."""

import math
from numbers import Real

from simready.foundation.tier_core.runtime_tests._assessment import (
    _has_complete_scene_asset,
    not_applicable,
)
from simready.foundation.tier_core.runtime_tests.fet003_physics._drop_config import (
    validate_drop_config,
)
from simready.foundation.tier_core.runtime_tests.fet003_physics.stability import (
    bounds_to_history_entry,
    check_bbox_corners_stable,
    check_position_stable,
    check_rest_window,
)
from simready.foundation.tier_core.runtime_tests.placement_compat import place_with_minimum_clearance


def qualified_bounds_entry(bounds):
    """Require finite ordered live bounds, never default missing observations."""
    try:
        minimum, maximum = bounds.min, bounds.max
        if len(minimum) != 3 or len(maximum) != 3:
            raise ValueError("expected three coordinates per corner")
        values = tuple(minimum) + tuple(maximum)
        if any(isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) for value in values):
            raise ValueError("coordinates must be finite real numbers")
        if any(minimum[i] > maximum[i] for i in range(3)):
            raise ValueError("minimum exceeds maximum")
        if not any(minimum[i] < maximum[i] for i in range(3)):
            raise ValueError("empty bounding box")
        entry = tuple(float(value) for value in bounds_to_history_entry(bounds))
        if not all(math.isfinite(value) for value in entry):
            raise ValueError("derived center or corner coordinates are not finite")
        return entry
    except (AttributeError, TypeError, ValueError, OverflowError, IndexError) as error:
        raise RuntimeError("FET003 required live bounding-box observation is invalid: " + str(error)) from error


def apply_ground_physics_material(ground_path, stage=None):
    """Require the fixture's typed material, coefficients and effective binding."""
    if stage is None:
        import omni.usd

        stage = omni.usd.get_context().get_stage()
    from pxr import UsdPhysics, UsdShade

    if stage is None:
        raise RuntimeError("FET003 ground material setup requires a live stage")
    collider = stage.GetPrimAtPath(ground_path + "/CollisionMesh")
    if not collider or not collider.IsValid() or not collider.HasAPI(UsdPhysics.CollisionAPI):
        raise RuntimeError("FET003 ground fixture collision mesh/API is unavailable")
    if UsdPhysics.CollisionAPI(collider).GetCollisionEnabledAttr().Get() is not True:
        raise RuntimeError("FET003 ground fixture collision mesh is not enabled")
    material = UsdShade.Material.Define(stage, ground_path + "/PhysMaterial")
    if not material:
        raise RuntimeError("FET003 ground fixture material could not be defined")
    physics_material = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    if not physics_material:
        raise RuntimeError("FET003 ground fixture physics material API could not be applied")
    for create, expected in (
        (physics_material.CreateStaticFrictionAttr, 0.5),
        (physics_material.CreateDynamicFrictionAttr, 0.4),
        (physics_material.CreateRestitutionAttr, 0.0),
    ):
        attribute = create()
        if attribute.Set(expected) is False:
            raise RuntimeError("FET003 ground material coefficient write was rejected")
        value = attribute.Get()
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise RuntimeError("FET003 ground material coefficient readback is unavailable")
        if not math.isclose(float(value), expected, rel_tol=0.0, abs_tol=1e-6):
            raise RuntimeError("FET003 ground material coefficient readback differs from the configured fixture")
    binding = UsdShade.MaterialBindingAPI.Apply(collider)
    if not binding or binding.Bind(material, UsdShade.Tokens.strongerThanDescendants, "physics") is False:
        raise RuntimeError("FET003 ground fixture physics material binding was rejected")
    effective, _ = binding.ComputeBoundMaterial("physics")
    if not effective or effective.GetPath() != material.GetPath():
        raise RuntimeError("FET003 ground fixture physics material binding could not be verified")


def validate_ground_trial_config(config, *, stability=False):
    """Validate before scene mutations; retain drop's diagnostic zero policies."""
    validate_drop_config(config)
    derived = {
        "floor_level + floor_margin proximity threshold": config["floor_level"] + config["floor_margin"],
        "floor_level - floor_margin overlap threshold": config["floor_level"] - config["floor_margin"],
        "minimum_drop_distance placement clearance": (
            config["floor_level"] + config["floor_margin"] + config["minimum_drop_distance"]
        ),
        "rest_tolerance squared distance comparison": config["rest_tolerance"] * config["rest_tolerance"],
    }
    for name in (
        "simulation_seconds",
        "penetration_check_seconds",
        "rest_detection_hold_seconds",
        "rest_detection_max_seconds",
        "simulate_after_result_seconds",
    ):
        derived[name + " frame budget"] = config[name] * config["physics_fps"]
    for name, value in derived.items():
        try:
            finite = math.isfinite(value)
        except (OverflowError, TypeError, ValueError):
            finite = False
        if not finite:
            raise RuntimeError("FET003 invalid configuration: nonfinite derived " + name)
    if not stability:
        return
    fps = int(config["physics_fps"])
    hold_intervals = math.ceil(float(config["rest_detection_hold_seconds"]) * fps)
    hold_frames = hold_intervals + 1
    delay_frames = math.ceil(float(config["penetration_check_seconds"]) * fps)
    deadline_frames = int(float(config["rest_detection_max_seconds"]) * fps)
    total_frames = int(float(config["simulation_seconds"]) * fps)
    if hold_intervals < 1:
        raise RuntimeError("FET003 invalid configuration: stability rest_detection_hold_seconds requires >=2 samples")
    minimum_elapsed = max(hold_frames - 1, delay_frames)
    if deadline_frames < minimum_elapsed:
        raise RuntimeError("FET003 invalid configuration: rest_detection_max_seconds cannot contain the rest window")
    if total_frames < minimum_elapsed + 1:
        raise RuntimeError(
            "FET003 invalid configuration: simulation_seconds cannot contain a post-proximity rest window"
        )


class GroundTrial:
    """Qualified observations and frozen deadline acceptance, independent of recording."""

    def __init__(self, config, initial, *, stability=False):
        self.config = config
        self.require_floor_rest = stability
        self.physics_fps = int(config["physics_fps"])
        self.touch_threshold = float(config["floor_level"]) + float(config["floor_margin"])
        self.pen_threshold = float(config["floor_level"]) - float(config["floor_margin"])
        self.pen_frames = (
            math.ceil(float(config["penetration_check_seconds"]) * self.physics_fps)
            if stability
            else int(float(config["penetration_check_seconds"]) * self.physics_fps)
        )
        self.hold_frames = (
            math.ceil(float(config["rest_detection_hold_seconds"]) * self.physics_fps) + 1
            if stability
            else max(1, int(float(config["rest_detection_hold_seconds"]) * self.physics_fps))
        )
        self.max_rest_frames = int(float(config["rest_detection_max_seconds"]) * self.physics_fps)
        self.after_result_frames = int(float(config["simulate_after_result_seconds"]) * self.physics_fps)
        self.rest_tol = float(config["rest_tolerance"])
        self.history = []
        self.contact_history = []
        self.touched = False
        self.penetrated = False
        self.rest_detected = False
        self.touch_frame = -1
        self.rest_frame = -1
        self.result_frame = -1
        self.last_frame = -1
        self.previous_z = initial[5]
        if self.previous_z <= self.touch_threshold:
            raise RuntimeError("FET003 ground placement did not provide required initial proximity clearance")

    def observe(self, frame, entry):
        self.last_frame = frame
        self.history.append(entry)
        z_min = entry[5]
        if not self.touched and self.previous_z > self.touch_threshold and z_min <= self.touch_threshold:
            self.touched = True
            self.touch_frame = frame
        self.previous_z = z_min
        if not self.touched:
            return
        self.contact_history.append(entry)
        if z_min < self.pen_threshold:
            self.penetrated = True
            if self.result_frame < 0:
                self.result_frame = frame
        elapsed = frame - self.touch_frame
        if not self.penetrated and not self.rest_detected and self.pen_frames <= elapsed <= self.max_rest_frames:
            floor_window = not self.require_floor_rest or (
                len(self.contact_history) >= self.hold_frames
                and all(
                    self.pen_threshold <= sample[5] <= self.touch_threshold
                    for sample in self.contact_history[-self.hold_frames :]
                )
            )
            if floor_window and check_rest_window(self.contact_history, self.hold_frames, self.rest_tol, self.rest_tol):
                self.rest_detected = True
                self.rest_frame = frame
                if self.result_frame < 0:
                    self.result_frame = frame
        if not self.rest_detected and elapsed >= self.max_rest_frames and self.result_frame < 0:
            self.result_frame = frame

    @property
    def overlap_window_complete(self):
        return self.touched and self.last_frame - self.touch_frame >= self.pen_frames

    @property
    def rest_deadline_complete(self):
        return self.touched and self.last_frame - self.touch_frame >= self.max_rest_frames

    @property
    def should_stop(self):
        return self.result_frame >= 0 and self.last_frame - self.result_frame >= self.after_result_frames

    @property
    def stop_reason(self):
        if self.penetrated:
            return "penetration"
        if self.rest_detected:
            return "rest_detected"
        return "rest_deadline" if self.rest_deadline_complete else "step_budget_exhausted"


def _diagnostic_warning(ctx, message):
    """A best-effort diagnostic must never replace a verdict or first exception."""
    try:
        ctx.warn(message)
    except Exception:
        pass


def _motion_call(ctx, motion, method, *args):
    if motion is not None:
        try:
            getattr(motion, method)(*args)
        except Exception:
            _diagnostic_warning(ctx, "Ground motion evidence is incomplete; test criteria are unchanged.")


def _window_measurements(result):
    """Optional plotting values from existing qualified post-proximity samples."""
    if len(result.contact_history) < result.hold_frames:
        return None, None
    latest = result.contact_history[-1]
    window = result.contact_history[-result.hold_frames :]
    center = max(math.dist(entry[:3], latest[:3]) for entry in window)
    corners = max(abs(entry[i] - latest[i]) for entry in window for i in range(3, 9))
    return center, corners


def _begin_motion(ctx, evidence_name, result):
    from simready.foundation.tier_core.runtime_tests.motion_observer import (
        MotionObserver,
        drop_metadata,
    )

    try:
        return MotionObserver(
            ctx,
            evidence_name,
            {
                **{
                    name: {"unit": "stage_length", "source": source}
                    for name, source in (
                        ("center_x", "runtime world-aligned bounding box center"),
                        ("center_y", "runtime world-aligned bounding box center"),
                        ("center_z", "runtime world-aligned bounding box center"),
                        ("minimum_z", "runtime world-aligned bounding box minimum"),
                        ("touch_threshold", "test bounding-box contact proxy threshold"),
                        ("penetration_threshold", "test bounding-box penetration threshold"),
                        ("center_window_max_distance", "maximum sampled window center distance to latest center"),
                        (
                            "corner_window_max_variation",
                            "maximum sampled window AABB corner-coordinate variation to latest corners",
                        ),
                        ("rest_tolerance", "configured sampled rest tolerance"),
                    )
                },
            },
            metadata={
                **drop_metadata(ctx, result.physics_fps, int(ctx.config["capture_fps"])),
                "clock_basis": "nominal observed step index / configured physics fps; capture ticks are not counted",
                "contact_basis": "AABB threshold crossing, not measured contact force",
                "rest_tolerance": result.rest_tol,
                "rest_window_samples": result.hold_frames,
                "rest_window_basis": "entirely post-proximity observed samples",
                "rest_floor_proximity_required": result.require_floor_rest,
                "rest_floor_proximity_basis": (
                    "every retained rest-window minimum Z within configured overlap/proximity thresholds"
                    if result.require_floor_rest
                    else "legacy drop diagnostic rest; does not certify sustained floor proximity"
                ),
                "rest_acceptance_deadline_seconds": float(ctx.config["rest_detection_max_seconds"]),
                "floor_level_stage_length": float(ctx.config["floor_level"]),
                "proximity_allowance_stage_length": float(ctx.config["floor_margin"]),
                "overlap_allowance_stage_length": float(ctx.config["floor_margin"]),
                "stability_basis": "sampled AABB center distance and min/max corner coordinate variation; not velocity thresholds or continuous stability proof",
                "ground_static_friction": 0.5,
                "ground_dynamic_friction": 0.4,
                "ground_restitution": 0.0,
            },
        )
    except Exception:
        _diagnostic_warning(ctx, "Ground motion evidence is unavailable; test criteria are unchanged.")
        return None


async def run_ground_trial(ctx, evidence_name, *, stability=False):
    """Run the owned impact fixture, preserving overlap coverage and required cleanup."""
    validate_ground_trial_config(ctx.config, stability=stability)
    config = ctx.config
    fps = int(config["physics_fps"])
    ctx.set_settle_frames(config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=config["asset_load_timeout"])
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)
    room.show_ground(color=(0.25, 0.35, 0.6))
    minimum_clearance = (
        float(config["floor_level"]) + float(config["floor_margin"]) + float(config["minimum_drop_distance"])
    )
    if not place_with_minimum_clearance(
        room.place_asset_above_ground, minimum_clearance, height_factor=config["drop_height_factor"]
    ):
        ctx.log("Legacy height-based placement is in use; required initial proximity clearance will be checked.")

    from simready.foundation.tier_core.runtime_tests.fet003_physics.physics_checks import (
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
            ctx.add_metric(evidence_name + "_skipped", 1)
        elif pre_result.startswith("SKIP:"):
            ctx.precheck_failure(pre_result[5:].strip())
            ctx.add_metric(evidence_name + "_passed", 0)
        else:
            ctx.fail(pre_result)
            ctx.add_metric(evidence_name + "_passed", 0)
        return None

    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=9.81, fps=float(fps))
    original_error = None
    try:
        ground_path = ctx.scene.enable_ground_plane(friction=0.5, position=(0.0, 0.0, float(config["floor_level"])))
        apply_ground_physics_material(ground_path)
        ctx.scene.setup_camera_follow()
        await ctx.settle(count=3)
        from simready.evaluate_engine_kit.physics_utils import cook_skip_message

        cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
        if cook_skip is not None:
            ctx.precheck_failure(cook_skip[5:].strip())
            ctx.add_metric(evidence_name + "_passed", 0)
            return None
        # Placement is authored setup, not a solver observation. Do not request
        # live Fabric bounds until the first required pumped physics step.
        initial = qualified_bounds_entry(ctx.get_asset_bounds(authored=True))
        result = GroundTrial(config, initial, stability=stability)
        ctx.add_metric(evidence_name + "_initial_z_min", round(initial[5], 4), unit="stage_length")
        ctx.add_metric(evidence_name + "_bbox_height", round(initial[8] - initial[5], 4), unit="stage_length")
        ctx.add_metric(evidence_name + "_effective_fall", round(initial[5] - result.touch_threshold, 4), unit="stage_length")
        ctx.step("Simulating ground drop with independently qualified sampled stability")
        motion = _begin_motion(ctx, evidence_name, result)
        physics.play()
        frames = []
        capture_interval = max(1, fps // int(config["capture_fps"]))
        for frame in range(int(float(config["simulation_seconds"]) * fps)):
            await ctx.physics_step()
            entry = qualified_bounds_entry(ctx.get_asset_bounds())
            result.observe(frame, entry)
            if frame < 10 or frame % 60 == 0:
                ctx.step(
                    "frame %d: z_min=%.4f (proximity=%.2f, overlap=%.2f)"
                    % (frame, entry[5], result.touch_threshold, result.pen_threshold)
                )
            try:
                center_variation, corner_variation = _window_measurements(result)
            except Exception:
                center_variation, corner_variation = None, None
                _diagnostic_warning(ctx, "Ground rest-window plot values are unavailable; test criteria are unchanged.")
            _motion_call(
                ctx,
                motion,
                "sample",
                {
                    "center_x": entry[0],
                    "center_y": entry[1],
                    "center_z": entry[2],
                    "minimum_z": entry[5],
                    "touch_threshold": result.touch_threshold,
                    "penetration_threshold": result.pen_threshold,
                    "center_window_max_distance": center_variation,
                    "corner_window_max_variation": corner_variation,
                    "rest_tolerance": result.rest_tol,
                },
                (frame + 1) / float(fps),
                (
                    "penetration"
                    if result.penetrated
                    else "rest_detected" if result.rest_detected else "after_touch" if result.touched else "fall"
                ),
            )
            ctx.scene.update_camera_follow()
            if frame % capture_interval == 0:
                capture = await ctx.capture_frame(label=evidence_name)
                if capture:
                    frames.append(capture)
                    _motion_call(ctx, motion, "record_capture", capture)
            if result.should_stop:
                break
            await ctx.physics_advance()
        _motion_call(ctx, motion, "finish", result.stop_reason)
        if frames:
            try:
                ctx.encode_video(frames, fps=int(config["capture_fps"]), label=evidence_name, role="summary")
            except Exception:
                _diagnostic_warning(ctx, "Ground summary video could not be encoded; test criteria are unchanged.")
        return result
    except BaseException as error:
        original_error = error
        raise
    finally:
        try:
            if physics.stop() is False:
                raise RuntimeError("FET003 required physics stop was rejected")
        except BaseException as cleanup_error:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
                note_secondary_error,
                record_required_cleanup_failure,
            )

            record_required_cleanup_failure(ctx, "FET003 required ground physics cleanup failed", original_error)
            if original_error is None:
                raise
            note_secondary_error(
                original_error,
                lambda cleanup_error=cleanup_error: (
                    "Required ground physics cleanup also failed: " + str(cleanup_error)
                ),
            )


def _metrics(ctx, result, prefix):
    ctx.add_metric(prefix + "_touched", int(result.touched))
    ctx.add_metric(prefix + "_penetrated", int(result.penetrated))
    ctx.add_metric(prefix + "_stable", int(result.rest_detected))
    ctx.add_metric(prefix + "_overlap_window_complete", int(result.overlap_window_complete))
    ctx.add_metric(prefix + "_rest_deadline_complete", int(result.rest_deadline_complete))
    if result.touch_frame >= 0:
        ctx.add_metric(prefix + "_touch_time", round((result.touch_frame + 1) / float(result.physics_fps), 3), unit="s")
    if result.rest_frame >= 0:
        ctx.add_metric(prefix + "_rest_time", round((result.rest_frame + 1) / float(result.physics_fps), 3), unit="s")


def _report_prerequisites(ctx, result, prefix):
    if not result.touched:
        ctx.fail(
            prefix.replace("_", " ").capitalize()
            + " FAILED: Bounding-box proximity threshold was not crossed within the observation budget. Review placement, enabled body, constraints and recorded motion; this is not proof of a missing collider or mass defect."
        )
        return False
    if result.penetrated:
        ctx.fail(
            prefix.replace("_", " ").capitalize()
            + " FAILED: Sampled bounding-box overlap exceeded the configured floor allowance. This is not measured collider penetration. Review the measured box, scale, allowance, collider approximation/contact offsets and video before attributing an asset defect."
        )
        return False
    if not result.overlap_window_complete:
        raise RuntimeError(
            "FET003 required post-proximity overlap observation window was not completed before the simulation cap"
        )
    return True


def report_ground_drop(ctx, result):
    _metrics(ctx, result, "ground_drop")
    if not _report_prerequisites(ctx, result, "ground_drop"):
        ctx.add_metric("ground_drop_passed", 0)
        return
    ctx.add_metric("ground_drop_passed", 1)
    ctx.log(
        "Ground drop PASSED: proximity observed and sampled overlap stayed within the allowance. Sampled rest is diagnostic only; consult ground_stability for its independent verdict."
    )


def report_ground_stability(ctx, result):
    _metrics(ctx, result, "ground_stability")
    ctx.add_metric("ground_stability_rest_detected", int(result.rest_detected))
    if not _report_prerequisites(ctx, result, "ground_stability"):
        ctx.add_metric("ground_stability_passed", 0)
        return
    if result.rest_detected:
        ctx.add_metric("ground_stability_passed", 1)
        ctx.log(
            "Ground stability PASSED: qualified post-proximity sampled rest at %.2fs nominal step time. This is not a velocity or mass/inertia measurement."
            % ((result.rest_frame + 1) / float(result.physics_fps))
        )
        return
    if not result.rest_deadline_complete:
        raise RuntimeError(
            "FET003 required post-proximity stability deadline was not observed before the simulation cap"
        )
    ctx.add_metric("ground_stability_passed", 0)
    detail = ""
    if len(result.contact_history) >= result.hold_frames:
        pos = check_position_stable(result.contact_history, result.hold_frames, result.rest_tol)
        corners = check_bbox_corners_stable(result.contact_history, result.hold_frames, result.rest_tol)
        if pos and not corners:
            detail = " The sampled centre is stable but box corners vary."
        elif corners and not pos:
            detail = " Box corners meet their tolerance but centre distance does not."
    ctx.fail(
        "Ground stability FAILED: No complete post-proximity rest window stayed within the configured floor-proximity/allowed-overlap band while centre and box-corner variation met their tolerance within %.1f nominal seconds after proximity.%s Review video, sampled variation, floor-proximity evidence, scale and tolerances; these observations do not establish a mass, friction or geometry defect. Do not alter the asset solely to obtain a pass."
        % (float(result.config["rest_detection_max_seconds"]), detail)
    )

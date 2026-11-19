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
"""Phase 4: Lifting -- raise gripper and verify object lifts."""

from pxr import Usd, UsdGeom
from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    finite_number,
)
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_geometry import (
    bounded_lift_height,
    smoothstep_progress,
)
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_utils import detect_object_lifted


class LiftingPhase:
    """Raise the gripper and verify the object moves upward."""

    def __init__(self, cfg):
        # type: (dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._lift_duration = float(cfg.get("lift_duration", 1.5))
        self._lift_frames = int(self._lift_duration * self._fps)
        self._min_delta_z = float(cfg.get("lift_min_delta_z", 0.02))
        self._height_mult = finite_number(cfg.get("lift_height_multiplier", 2.0), "lift_height_multiplier")
        self._minimum_lift_height = finite_number(cfg.get("lift_min_height", 0.3), "lift_min_height", positive=True)
        self._maximum_lift_height = finite_number(
            cfg.get("lift_max_height", 0.5), "lift_max_height", minimum=self._minimum_lift_height
        )
        self._start_frame = None  # type: Optional[int]
        self._start_time = None  # type: Optional[float]
        self._lift_height = None  # type: Optional[float]
        self._base_z = 0.0  # gantry Z at lift start (relative lift)
        self._done = False

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[dict[str, Any]]
        if self._done:
            return None

        robot = scene.robot

        if self._start_frame is None:
            self._start_frame = frame
            self._start_time = time
            self._lift_height = self._compute_lift_height(scene)
            # Capture current Z so lift is relative to current position
            jx, jy, self._base_z = robot.get_joint_targets()
            # Record object Z at lift start for diagnostics
            self._obj_start_z = None
            if tracker.center_history:
                self._obj_start_z = tracker.center_history[-1][2]

        elapsed = frame - self._start_frame

        # Smooth lift ramp (relative to base_z)
        if elapsed < self._lift_frames:
            progress = elapsed / self._lift_frames
            # Avoid an instantaneous upward velocity at first contact.  The
            # impulse can peel an eccentric object (such as a hammer) out of
            # an otherwise stable grasp.
            progress = smoothstep_progress(progress)
            robot.lift(self._base_z + self._lift_height * progress)
            return None

        # Lift complete -- check if object lifted
        self._done = True
        obj_end_z = None
        if tracker.center_history:
            obj_end_z = tracker.center_history[-1][2]
        actual_dz = tracker.delta_z_between(self._start_time, time)
        _, _, jz_end = robot.get_joint_targets()

        if detect_object_lifted(tracker, self._start_time, time, self._min_delta_z):
            return {
                "phase_name": "Lifting",
                "frame": frame,
                "time": time,
                "message": (
                    "Object lifted at frame %d (dz=%.4f, "
                    "obj_z=%.4f->%.4f, gantry_z=%.4f->%.4f, "
                    "target_height=%.3f)"
                    % (
                        frame,
                        actual_dz,
                        self._obj_start_z or 0,
                        obj_end_z or 0,
                        self._base_z,
                        jz_end,
                        self._lift_height,
                    )
                ),
                "failed": False,
                "lift_height": self._lift_height,
                "lift_success_frame": frame,
            }
        return {
            "phase_name": "Lifting",
            "frame": frame,
            "time": time,
            "message": (
                "Lifting failed: object did not rise %.3fm "
                "(actual_dz=%.4f, obj_z=%.4f->%.4f, "
                "gantry_z=%.4f->%.4f, target_height=%.3f)"
                % (
                    self._min_delta_z,
                    actual_dz,
                    self._obj_start_z or 0,
                    obj_end_z or 0,
                    self._base_z,
                    jz_end,
                    self._lift_height,
                )
            ),
            "failed": True,
        }

    def _compute_lift_height(self, scene):
        # type: (Any) -> float
        """Size the existing lift formula from required selected-body geometry."""
        from simready.evaluate_engine_kit.fabric_utils import (
            is_rigid_body,
            live_world_aabb,
            validated_bounds,
        )
        from simready.evaluate_engine_kit.physics_utils import active_physics_engine

        try:
            properties = scene.scene_properties
            asset_path = properties.get("tracked_body_path") or properties.get("target_asset_path")
            if not asset_path:
                raise ValueError("Tracked grasp body path is unavailable")
            stage = scene.stage
            prim = stage.GetPrimAtPath(asset_path)
            if not prim or not prim.IsValid():
                raise ValueError("Tracked grasp body is unavailable: " + str(asset_path))
            if active_physics_engine() == "physx":
                bbox_cache = UsdGeom.BBoxCache(
                    Usd.TimeCode.Default(),
                    [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
                )
                aligned = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
                if aligned.IsEmpty():
                    raise ValueError("Required grasp-body bound is empty")
                minimum, maximum = validated_bounds(aligned.GetMin(), aligned.GetMax())
            else:
                bounds = live_world_aabb(stage, asset_path, is_rigid_body, require_complete=True)
                if bounds is None:
                    raise ValueError("Required live grasp-body bounds are unavailable: " + str(asset_path))
                minimum, maximum = validated_bounds(*bounds)
            max_dim = max(high - low for low, high in zip(minimum, maximum, strict=True))
            return bounded_lift_height(
                max_dim,
                self._height_mult,
                self._minimum_lift_height,
                self._maximum_lift_height,
            )
        except Exception as exc:
            raise RuntimeError("Required grasp-body bounds could not determine the generated lift height") from exc

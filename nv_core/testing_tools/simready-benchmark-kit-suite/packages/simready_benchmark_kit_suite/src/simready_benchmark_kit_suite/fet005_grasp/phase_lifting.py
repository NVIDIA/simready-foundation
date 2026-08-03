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
from simready_benchmark_kit_suite.fet005_grasp.grasp_utils import (
    detect_object_lifted,
)


class LiftingPhase:
    """Raise the gripper and verify the object moves upward."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._lift_duration = float(cfg.get("lift_duration", 1.5))
        self._lift_frames = int(self._lift_duration * self._fps)
        self._min_delta_z = float(cfg.get("lift_min_delta_z", 0.02))
        self._height_mult = float(cfg.get("lift_height_multiplier", 2.0))
        self._start_frame = None  # type: Optional[int]
        self._start_time = None  # type: Optional[float]
        self._lift_height = None  # type: Optional[float]
        self._base_z = 0.0  # gantry Z at lift start (relative lift)
        self._done = False

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
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
        try:
            asset_path = scene.scene_properties["target_asset_path"]
            stage = scene.stage
            prim = stage.GetPrimAtPath(asset_path)
            bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"])
            aligned = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
            size = aligned.GetSize()
            max_dim = max(float(size[0]), float(size[1]), float(size[2]))
            return max(0.3, max_dim * self._height_mult)
        except Exception:
            return 0.3

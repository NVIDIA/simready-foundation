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
"""Phase 6: Shake -- oscillatory perturbation to test grip robustness.

A slipped-but-still-held object is not a grasp failure here -- the test
only fails if the object physically reaches the floor during the shake.
This prevents false negatives on assets that wobble or rotate slightly
in grip without actually dropping.
"""
import math

from simready_benchmark_kit_suite.fet005_grasp.grasp_utils import (
    detect_object_hit_floor,
)


class ShakePhase:
    """Apply sinusoidal oscillation to the gripper gantry."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._enabled = bool(cfg.get("enable_shake_test", True))
        self._duration = float(cfg.get("shake_duration_seconds", 2.0))
        self._duration_frames = int(self._duration * self._fps)
        self._amplitude = float(cfg.get("shake_amplitude", 0.01))
        self._freq = float(cfg.get("shake_frequency_hz", 2.0))
        # Floor threshold: object's bbox min_z dipping at or below this
        # during the shake counts as a dropped object.
        self._floor_level = float(cfg.get("floor_level", 0.0))
        self._floor_margin = float(cfg.get("floor_margin", 0.0))
        self._floor_threshold = self._floor_level + self._floor_margin
        self._start_frame = None  # type: Optional[int]
        self._start_time = None  # type: Optional[float]
        self._base_x = 0.0
        self._base_y = 0.0
        self._base_z = 0.0
        self._done = False

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        if not self._enabled:
            self._done = True
            return {
                "phase_name": "Shake",
                "frame": frame,
                "time": time,
                "message": "Shake disabled -- skipping",
                "failed": False,
                "shake_enabled": False,
            }

        robot = scene.robot

        if self._start_frame is None:
            self._start_frame = frame
            self._start_time = time
            self._base_x, self._base_y, self._base_z = robot.get_joint_targets()

        elapsed_frames = frame - self._start_frame
        elapsed_time = time - self._start_time

        if elapsed_frames <= self._duration_frames:
            omega = 2.0 * math.pi * self._freq
            offset_x = self._amplitude * math.sin(omega * elapsed_time)
            offset_y = self._amplitude * math.sin(omega * elapsed_time + math.pi / 2.0)
            robot.update_joint_target_positions(
                self._base_x + offset_x,
                self._base_y + offset_y,
                self._base_z,
            )

            if detect_object_hit_floor(tracker, self._floor_threshold):
                self._done = True
                obj_min_z = tracker.min_z_history[-1] if tracker.min_z_history else 0.0
                return {
                    "phase_name": "Shake",
                    "frame": frame,
                    "time": time,
                    "message": (
                        "Shake failed: object reached floor during shaking "
                        "(min_z=%.4f <= floor+margin=%.4f)" % (obj_min_z, self._floor_threshold)
                    ),
                    "failed": True,
                }

        if elapsed_frames >= self._duration_frames:
            # Restore baseline
            robot.update_joint_target_positions(self._base_x, self._base_y, self._base_z)
            self._done = True
            return {
                "phase_name": "Shake",
                "frame": frame,
                "time": time,
                "message": "Shake succeeded: object stayed in grip",
                "failed": False,
                "shake_enabled": True,
            }
        return None

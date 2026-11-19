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
"""Phase 2: Gripper Positioning -- wait for gantry to reach grasp line.

After stability, the snap boosts drive stiffness and sets targets.
This phase waits until the gantry has physically converged to the
grasp midpoint (within tolerance) before allowing grasping to start.
"""

import numpy as np
from simready.evaluate_engine_kit.fabric_utils import validated_bounds


class GripperPositioningPhase:
    """Wait for the gantry to physically reach the grasp position."""

    # Converge when gantry_x is within this distance of grasp midpoint
    _TOLERANCE = 0.005  # 5mm
    _MAX_SECONDS = 2.0  # give up after 2s

    def __init__(self, cfg):
        # type: (dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._max_frames = int(self._MAX_SECONDS * self._fps)
        self._start_frame = None  # type: Optional[int]
        self._done = False

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[dict[str, Any]]
        if self._done:
            return None

        robot = getattr(scene, "robot", None)
        if robot is None:
            raise RuntimeError("Required generated gripper robot is unavailable for positioning")

        pts = scene.get_current_world_grasp_points()
        if pts is None:
            raise RuntimeError("Required live grasp points are unavailable for positioning")

        if self._start_frame is None:
            self._start_frame = frame

        elapsed = frame - self._start_frame

        # Check if gantry_x has converged to the grasp midpoint
        try:
            gp1, gp2 = pts
            gp1, _ = validated_bounds(gp1, gp1)
            gp2, _ = validated_bounds(gp2, gp2)
            desired_mid = 0.5 * (np.array(gp1) + np.array(gp2))
            offset = scene.scene_properties.get("pad_ground_offset_z", 0.0)
            offset_vector, _ = validated_bounds((0.0, 0.0, offset), (0.0, 0.0, offset))
            desired_mid[2] += offset_vector[2]
        except Exception as exc:
            raise RuntimeError("Required positioning target is invalid") from exc

        from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_robot import GraspRobot

        gx_xf = scene._body_world_matrix(GraspRobot.GANTRY_X)
        try:
            gx_pos = gx_xf.ExtractTranslation()
            actual, _ = validated_bounds(gx_pos, gx_pos)
            distance = float(np.linalg.norm(np.array(actual) - desired_mid))
            if not np.isfinite(distance):
                raise ValueError("Positioning distance is not finite")
        except Exception as exc:
            raise RuntimeError("Required live gantry position is invalid") from exc

        if distance <= self._TOLERANCE:
            self._done = True
            return {
                "phase_name": "GripperPositioning",
                "frame": frame,
                "time": time,
                "message": ("Gripper converged at frame %d (dist=%.4fm)" % (frame, distance)),
                "failed": False,
                "gripper_positioned_frame": frame,
            }

        # Timeout
        if elapsed >= self._max_frames:
            self._done = True
            return {
                "phase_name": "GripperPositioning",
                "frame": frame,
                "time": time,
                "message": ("Gripper positioning timeout (%.1fs)" % self._MAX_SECONDS),
                "failed": True,
            }

        return None  # Keep waiting

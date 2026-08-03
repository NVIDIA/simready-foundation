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
"""Phase 8: Opening -- open gripper and detect object release."""


class OpeningPhase:
    """Open the gripper smoothly and detect object release."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._open_duration = float(cfg.get("open_duration", 1.0))
        self._open_frames = int(self._open_duration * self._fps)
        self._check_frames = int(float(cfg.get("release_check_seconds", 1.0)) * self._fps)
        self._start_frame = None  # type: Optional[int]
        self._open_start_target = None  # type: Optional[float]
        self._released = False
        self._done = False
        self._drop_start_z = None  # type: Optional[float]

    @property
    def drop_start_z(self):
        # type: () -> Optional[float]
        """Z position at the moment of opening (used by DroppingPhase)."""
        return self._drop_start_z

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        robot = scene.robot

        if self._start_frame is None:
            self._start_frame = frame
            self._open_start_target = robot.get_gripper_joint_position()
            if tracker.center_history:
                self._drop_start_z = tracker.center_history[-1][2]

        elapsed = frame - self._start_frame

        # Smooth open ramp
        if elapsed < self._open_frames and self._open_frames > 0:
            progress = elapsed / self._open_frames
            target = (self._open_start_target or 0.0) * (1.0 - progress)
            robot.close(target)
        elif elapsed == self._open_frames:
            robot.open()

        # Detect release (position change)
        if not self._released and elapsed >= 5 and len(tracker.center_history) >= 2:
            cur = tracker.center_history[-1]
            prev = tracker.center_history[-2]
            dx = cur[0] - prev[0]
            dy = cur[1] - prev[1]
            dz = cur[2] - prev[2]
            movement = (dx * dx + dy * dy + dz * dz) ** 0.5
            if movement > 0.001 or dz < -0.001:
                self._released = True

        if elapsed >= self._check_frames:
            self._done = True
            return {
                "phase_name": "Opening",
                "frame": frame,
                "time": time,
                "message": "Gripper opened%s"
                % (" -- object released" if self._released else " -- release not clearly detected"),
                "failed": False,
                "object_released": self._released,
                "object_release_frame": frame if self._released else None,
            }
        return None

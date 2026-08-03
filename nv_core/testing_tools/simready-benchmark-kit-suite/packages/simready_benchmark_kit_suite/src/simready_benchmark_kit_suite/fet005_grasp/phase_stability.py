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
"""Phase 1: Stability -- wait for object to reach rest.

Non-blocking: proceeds after timeout even if not stable.
"""


class StabilityPhase:
    """Wait for the asset to settle before positioning the gripper."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._max_seconds = float(cfg.get("stability_max_seconds", 5.0))
        self._max_frames = int(self._max_seconds * self._fps)
        self._tolerance = float(cfg.get("rest_tolerance", 0.002))
        self._hold_seconds = float(cfg.get("rest_detection_hold_seconds", 2.0))
        self._done = False

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        # Early exit if rest detected
        rest = tracker.find_first_rest_window(0.0, time, self._hold_seconds, self._tolerance)
        if rest is not None:
            self._done = True
            return {
                "phase_name": "Stability",
                "frame": frame,
                "time": time,
                "message": "Object at rest at frame %d" % frame,
                "failed": False,
                "stability_detected": True,
                "stability_frame": frame,
            }

        # Timeout -- proceed anyway
        if frame >= self._max_frames:
            self._done = True
            return {
                "phase_name": "Stability",
                "frame": frame,
                "time": time,
                "message": ("Stability timeout (%.1fs) -- proceeding anyway" % self._max_seconds),
                "failed": False,
                "stability_detected": False,
            }
        return None

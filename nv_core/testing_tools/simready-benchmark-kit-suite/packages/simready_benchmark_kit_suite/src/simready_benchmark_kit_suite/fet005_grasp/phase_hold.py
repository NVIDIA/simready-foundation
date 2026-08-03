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
"""Phase 5/7: Hold -- verify object stays in grip without dropping.

Reusable with a label parameter for HoldBeforeShake / HoldAfterShake.
"""

from simready_benchmark_kit_suite.fet005_grasp.grasp_utils import (
    detect_object_falling,
)


class HoldPhase:
    """Hold the object for a duration and detect drops or ground contact."""

    def __init__(self, cfg, label="Hold"):
        # type: (Dict[str, Any], str) -> None
        self._label = label
        self._fps = int(cfg["physics_fps"])
        self._hold_seconds = float(cfg.get("hold_seconds", 2.0))
        default_drop = float(cfg.get("fall_min_delta_z", 0.02))
        self._drop_tol = float(cfg.get("hold_drop_tolerance", default_drop))
        self._floor_level = float(cfg.get("floor_level", 0.0))
        self._floor_margin = float(cfg.get("floor_margin", 0.0))
        self._start_frame = None  # type: Optional[int]
        self._start_time = None  # type: Optional[float]
        self._done = False

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        if self._start_frame is None:
            self._start_frame = frame
            self._start_time = time

        # Fail if object fell
        if detect_object_falling(tracker, self._start_time, time, self._drop_tol):
            self._done = True
            return {
                "phase_name": self._label,
                "frame": frame,
                "time": time,
                "message": "%s failed: object dropped" % self._label,
                "failed": True,
            }

        # Fail if ground contact
        if tracker.center_history:
            z = tracker.center_history[-1][2]
            if z < self._floor_level - self._floor_margin:
                self._done = True
                return {
                    "phase_name": self._label,
                    "frame": frame,
                    "time": time,
                    "message": ("%s failed: object touched ground (z=%.4f)" % (self._label, z)),
                    "failed": True,
                }

        # Success after hold duration
        elapsed = time - self._start_time
        if elapsed >= self._hold_seconds:
            self._done = True
            return {
                "phase_name": self._label,
                "frame": frame,
                "time": time,
                "message": ("%s succeeded: held %.1fs without drop" % (self._label, elapsed)),
                "failed": False,
                "hold_duration": elapsed,
            }
        return None

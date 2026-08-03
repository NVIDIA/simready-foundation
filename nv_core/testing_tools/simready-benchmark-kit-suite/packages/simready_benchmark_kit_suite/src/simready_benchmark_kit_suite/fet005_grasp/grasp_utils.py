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
"""Pose tracker and detection helpers for grasp-and-lift tests.

Tracks per-frame object position and gripper joint state. Provides
helper functions used by phase checks: rest detection, lift/fall
detection, pad-touching detection.
"""

from pxr import Usd, UsdGeom


class AssetPoseTracker:
    """Track object centre position and gripper state each physics frame."""

    def __init__(self, timeline_fps):
        # type: (int) -> None
        self.timeline_fps = timeline_fps
        self.center_history = []  # type: List[Tuple[float, float, float]]
        # min_z per frame so phases can check whether the object has
        # physically reached the floor (not just drifted downward).
        self.min_z_history = []  # type: List[float]
        self.times = []  # type: List[float]
        self.joint_positions = []  # type: List[float]

    def record_frame(self, asset_prim, current_time):
        # type: (Any, float) -> None
        """Record bbox centre + min_z and time for one frame."""
        try:
            bbox_cache = UsdGeom.BBoxCache(
                Usd.TimeCode.Default(),
                ["default"],
            )
            world_bound = bbox_cache.ComputeWorldBound(asset_prim)
            aligned = world_bound.ComputeAlignedBox()
            centre = aligned.GetMidpoint()
            min_corner = aligned.GetMin()
            self.center_history.append((float(centre[0]), float(centre[1]), float(centre[2])))
            self.min_z_history.append(float(min_corner[2]))
        except Exception:
            if self.center_history:
                self.center_history.append(self.center_history[-1])
                last_min_z = self.min_z_history[-1] if self.min_z_history else 0.0
                self.min_z_history.append(last_min_z)
            else:
                self.center_history.append((0.0, 0.0, 0.0))
                self.min_z_history.append(0.0)
        self.times.append(current_time)

    def record_joint_position(self, position):
        # type: (float) -> None
        """Record gripper finger joint position."""
        self.joint_positions.append(float(position))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def delta_z_between(self, t1, t2):
        # type: (float, float) -> float
        """Return Z displacement between two times."""
        idx1 = self._nearest_index(t1)
        idx2 = self._nearest_index(t2)
        if idx1 is None or idx2 is None:
            return 0.0
        return self.center_history[idx2][2] - self.center_history[idx1][2]

    def find_first_rest_window(self, start_time, end_time, window_duration, tolerance):
        # type: (float, float, float, float) -> Optional[float]
        """Find first time where object is at rest for *window_duration*.

        Returns the start-time of the rest window, or None.
        """
        if len(self.center_history) < 2:
            return None
        window_frames = int(window_duration * self.timeline_fps)
        if window_frames < 1:
            window_frames = 1
        start_idx = self._nearest_index(start_time) or 0
        end_idx = self._nearest_index(end_time) or (len(self.times) - 1)
        for i in range(start_idx, end_idx - window_frames + 1):
            ref = self.center_history[i]
            stable = True
            for j in range(i + 1, i + window_frames):
                dx = abs(self.center_history[j][0] - ref[0])
                dy = abs(self.center_history[j][1] - ref[1])
                dz = abs(self.center_history[j][2] - ref[2])
                if dx > tolerance or dy > tolerance or dz > tolerance:
                    stable = False
                    break
            if stable:
                return self.times[i]
        return None

    def get_most_closed_joint_position(self):
        # type: () -> float
        """Return the most-negative (most closed) finger joint position."""
        if not self.joint_positions:
            return 0.0
        return min(self.joint_positions)

    def _nearest_index(self, t):
        # type: (float) -> Optional[int]
        if not self.times:
            return None
        best = 0
        best_dist = abs(self.times[0] - t)
        for i in range(1, len(self.times)):
            d = abs(self.times[i] - t)
            if d < best_dist:
                best = i
                best_dist = d
        return best


# ------------------------------------------------------------------
# Detection helpers (used by phase checks)
# ------------------------------------------------------------------


def detect_object_lifted(tracker, start_time, current_time, min_height):
    # type: (AssetPoseTracker, float, float, float) -> bool
    """True if object moved upward by at least *min_height* metres."""
    if len(tracker.times) < 2:
        return False
    dz = tracker.delta_z_between(start_time, current_time)
    return dz >= min_height


def detect_object_falling(tracker, start_time, current_time, min_distance):
    # type: (AssetPoseTracker, float, float, float) -> bool
    """True if object moved downward by at least *min_distance* metres."""
    if len(tracker.times) < 2:
        return False
    dz = tracker.delta_z_between(start_time, current_time)
    return dz <= -min_distance


def detect_object_hit_floor(tracker, floor_threshold):
    # type: (AssetPoseTracker, float) -> bool
    """True if the object's bbox min_z has reached or dipped below floor_threshold.

    Use this when you want to know whether the object has physically
    touched the ground -- not whether it merely drifted downward from
    its starting position.  The delta-z check (``detect_object_falling``)
    is too strict during phases like Shake where the object can wobble
    or rotate in grip without ever leaving the gripper.
    """
    if not tracker.min_z_history:
        return False
    return tracker.min_z_history[-1] <= floor_threshold


def detect_pads_touching(tracker, scene_props, pad_touching_tolerance):
    # type: (AssetPoseTracker, Dict[str, Any], float) -> bool
    """True if gripper pads closed enough to be touching (no object)."""
    try:
        grasp_distance = scene_props["gripper_position_info"]["grasp_distance"]
        pad_scale = scene_props["gripper_pad_properties"]["scale"]
        most_closed = tracker.get_most_closed_joint_position()
        max_close_without_touching = -(grasp_distance / 2.0) + (pad_scale / 2.0)
        threshold = max_close_without_touching + pad_touching_tolerance
        return most_closed <= threshold
    except (KeyError, ValueError, AttributeError):
        return False

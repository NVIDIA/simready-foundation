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

Tracks per-observation world-aligned bounding-box centre/minimum Z and
gripper joint state. Provides sampled rest, lift/fall, floor-height, and
bilateral aperture proxies; these are not native contact measurements.
"""

import math
from numbers import Real

from pxr import Usd, UsdGeom


def _required_real_observation(value, label):
    """Accept measured real scalars without coercing unsupported native values."""
    kind = getattr(getattr(value, "dtype", None), "kind", None)
    if (
        (kind is not None and kind not in ("i", "u", "f"))
        or isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
    ):
        raise ValueError("%s must be a finite real observation" % label)
    return float(value)


class AssetPoseTracker:
    """Track world-aligned box centre and gripper state per observation."""

    def __init__(self, timeline_fps):
        # type: (int) -> None
        self.timeline_fps = timeline_fps
        self.center_history = []  # type: list[tuple[float, float, float]]
        # Minimum box Z supports a floor-height proxy, not a native contact
        # query. Centre displacement is tracked separately for lift/fall.
        self.min_z_history = []  # type: list[float]
        self.times = []  # type: list[float]
        self.joint_positions = []  # type: list[float]
        self.finger_positions = []  # type: list[tuple[float, float]]
        self.finger_times = []  # type: list[float]
        self.pose_source = "usd"

    def record_frame(self, asset_prim, current_time):
        # type: (Any, float) -> None
        """Record bbox centre + min_z and time for one frame."""
        from simready.evaluate_engine_kit import fabric_utils
        from simready.evaluate_engine_kit.physics_utils import active_physics_engine

        timestamp = _required_real_observation(current_time, "Observation time")
        if asset_prim is None or not asset_prim or not asset_prim.IsValid():
            raise fabric_utils.LiveBoundsReadError("Required grasp body is unavailable")
        if active_physics_engine() != "physx":
            live_bound = fabric_utils.live_world_aabb(
                asset_prim.GetStage(),
                str(asset_prim.GetPath()),
                fabric_utils.is_rigid_body,
                require_complete=True,
            )
            if live_bound is None:
                raise fabric_utils.LiveBoundsReadError("Required grasp-body live bounds are unavailable")
            minimum, maximum = fabric_utils.validated_bounds(*live_bound)
            source = "fabric"
        else:
            bbox_cache = UsdGeom.BBoxCache(
                Usd.TimeCode.Default(),
                ["default", "render", "proxy"],
            )
            world_bound = bbox_cache.ComputeWorldBound(asset_prim)
            aligned = world_bound.ComputeAlignedBox()
            if aligned.IsEmpty():
                raise fabric_utils.LiveBoundsReadError("Required grasp-body bound is empty")
            minimum, maximum = fabric_utils.validated_bounds(aligned.GetMin(), aligned.GetMax())
            source = "usd"

        # Append only complete validated observations. Failed reads must not
        # manufacture a stationary object, a zero height or nominal progress.
        centre = tuple(minimum[index] * 0.5 + maximum[index] * 0.5 for index in range(3))
        if not all(math.isfinite(value) for value in centre):
            raise fabric_utils.LiveBoundsReadError("Required grasp-body center is non-finite")
        self.center_history.append(centre)
        self.min_z_history.append(minimum[2])
        self.pose_source = source
        self.times.append(timestamp)

    def record_joint_position(self, position):
        # type: (float) -> None
        """Record gripper finger joint position."""
        self.joint_positions.append(_required_real_observation(position, "Finger joint position"))

    def record_finger_positions(self, positions, current_time=None):
        """Retain both jaws from one required snapshot, never mixed-time minima."""
        kind = getattr(getattr(positions, "dtype", None), "kind", None)
        if kind is not None and kind not in ("i", "u", "f"):
            raise ValueError("Finger joint pair must have a real numeric dtype")
        if positions is None or len(positions) != 2:
            raise ValueError("Finger joint pair requires exactly two observations")
        left = _required_real_observation(positions[0], "Left finger joint position")
        right = _required_real_observation(positions[1], "Right finger joint position")
        if not self.times:
            raise RuntimeError("Finger joint pair requires a current object observation")
        observation_time = _required_real_observation(self.times[-1], "Object observation time")
        timestamp = (
            observation_time if current_time is None else _required_real_observation(current_time, "Finger time")
        )
        if timestamp != observation_time:
            raise RuntimeError("Finger joint pair must match the current object observation")
        self.finger_positions.append((left, right))
        self.finger_times.append(timestamp)
        self.joint_positions.append(left)

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
            raise RuntimeError("Required finger joint history is unavailable")
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
    """True if tracked box centre rose by at least *min_height* stage units."""
    if len(tracker.times) < 2:
        return False
    dz = tracker.delta_z_between(start_time, current_time)
    return dz >= min_height


def detect_object_falling(tracker, start_time, current_time, min_distance):
    # type: (AssetPoseTracker, float, float, float) -> bool
    """True if tracked box centre fell by at least *min_distance* stage units."""
    if len(tracker.times) < 2:
        return False
    dz = tracker.delta_z_between(start_time, current_time)
    return dz <= -min_distance


def detect_object_hit_floor(tracker, floor_threshold):
    # type: (AssetPoseTracker, float) -> bool
    """True if the object's bbox min_z has reached or dipped below floor_threshold.

    This is a sampled world-aligned bounding-box floor-height proxy, not
    proof of physical contact. Unlike ``detect_object_falling``, it checks
    an absolute minimum-Z threshold rather than centre displacement.
    """
    if not tracker.min_z_history:
        return False
    return tracker.min_z_history[-1] <= floor_threshold


def detect_pads_touching(tracker, scene_props, pad_touching_tolerance):
    # type: (AssetPoseTracker, dict[str, Any], float) -> bool
    """True if same-sample bilateral aperture meets the empty-grasp proxy."""
    grasp_distance = _required_real_observation(
        scene_props["gripper_position_info"]["grasp_distance"], "Grasp distance"
    )
    pad_scale = _required_real_observation(scene_props["gripper_pad_properties"]["scale"], "Pad scale")
    tolerance = _required_real_observation(pad_touching_tolerance, "Pad touching tolerance")
    if grasp_distance <= 0.0 or pad_scale <= 0.0 or tolerance < 0.0:
        raise ValueError("Pad aperture requires positive dimensions and a nonnegative tolerance")
    if not tracker.finger_positions or len(tracker.finger_positions) != len(tracker.finger_times):
        raise RuntimeError("Required bilateral finger history is unavailable")
    # Total aperture is grasp_distance - pad_scale + left + right. Express
    # its 2*tolerance comparison in per-jaw units to retain the established
    # symmetric floating-point boundary. Each mean uses ONE measured pair.
    most_closed_pair = min(left * 0.5 + right * 0.5 for left, right in tracker.finger_positions)
    threshold = -(grasp_distance / 2.0) + (pad_scale / 2.0) + tolerance
    return most_closed_pair <= threshold

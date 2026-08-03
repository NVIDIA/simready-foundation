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
"""Phase 9: Dropping -- verify the object fell when the gripper opened.

The only signal we want from this phase is: did the object actually drop
once the gripper released it? A successful fall (>= bbox height or
``fall_min_delta_z``, whichever is larger) is sufficient proof that the
release worked. Ground penetration is intentionally NOT checked here --
small objects naturally settle with their centroid close to (or, for
PhysX contact-tolerance reasons, slightly below) the floor, and that's
not a failure of the grasp test. Penetration concerns belong to FET003
ground-drop, not here.
"""

from pxr import Usd, UsdGeom


class DroppingPhase:
    """Monitor the object after release: must fall by at least its bbox height."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._fall_min = float(cfg.get("fall_min_delta_z", 0.02))
        self._check_seconds = float(cfg.get("drop_check_seconds", 3.0))
        self._check_frames = int(self._check_seconds * self._fps)

        self._start_frame = None  # type: Optional[int]
        self._drop_start_z = None  # type: Optional[float]
        self._min_z = None  # type: Optional[float]
        self._required_fall = None  # type: Optional[float]
        self._done = False

    def set_drop_start_z(self, z):
        # type: (Optional[float]) -> None
        """Set reference Z from the Opening phase."""
        self._drop_start_z = z

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        if self._start_frame is None:
            self._start_frame = frame
            if self._drop_start_z is None and tracker.center_history:
                self._drop_start_z = tracker.center_history[-1][2]
            self._min_z = self._drop_start_z
            # Required fall = max(fall_min, bbox height)
            self._required_fall = self._compute_required_fall(scene)

        elapsed = frame - self._start_frame

        # Track drop distance based on the lowest Z the object's centroid
        # has reached since release. We deliberately do not fail on ground
        # penetration here -- see module docstring.
        cur_z = None
        if tracker.center_history:
            cur_z = tracker.center_history[-1][2]
        drop_distance = 0.0
        if cur_z is not None:
            if self._min_z is None or cur_z < self._min_z:
                self._min_z = cur_z
            if self._drop_start_z is not None and self._min_z is not None:
                drop_distance = self._drop_start_z - self._min_z

        # Done as soon as object fell enough (>= bbox height)
        if drop_distance >= self._required_fall:
            self._done = True
            return {
                "phase_name": "Dropping",
                "frame": frame,
                "time": time,
                "message": ("Dropping complete: fell %.4fm (required %.4fm)" % (drop_distance, self._required_fall)),
                "failed": False,
                "drop_distance": drop_distance,
            }

        # Timeout: object never fell enough
        if elapsed >= self._check_frames:
            self._done = True
            return {
                "phase_name": "Dropping",
                "frame": frame,
                "time": time,
                "message": ("Dropping failed: fell %.4fm, needed %.4fm" % (drop_distance, self._required_fall)),
                "failed": True,
                "drop_distance": drop_distance,
            }
        return None

    def _compute_required_fall(self, scene):
        # type: (Any) -> float
        """Required fall = max(fall_min_delta_z, asset bbox height)."""
        try:
            asset_path = scene.scene_properties["target_asset_path"]
            stage = scene.stage
            prim = stage.GetPrimAtPath(asset_path)
            bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"])
            aligned = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
            bbox_height = float(aligned.GetSize()[2])
            return max(self._fall_min, bbox_height)
        except Exception:
            return self._fall_min

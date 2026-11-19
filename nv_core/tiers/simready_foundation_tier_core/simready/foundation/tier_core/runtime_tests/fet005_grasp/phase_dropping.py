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

"""Phase 9: Dropping -- check observed box-centre fall after the release request.

A fall of at least the larger of the required body-box height and
``fall_min_delta_z`` meets the configured release-motion criterion. The
reference height comes from Opening's first observation, not a native
contact-release timestamp. Required Newton compiled-pad flag readback is
checked separately on the first existing Dropping tick; neither those flags
nor centre motion proves effective collision response or zero contacts.
This phase does not check floor overlap. FET003 ground-drop owns its
separate bounding-box overlap proxy, not exact collision penetration.
"""

import math

from pxr import Usd, UsdGeom


class DroppingPhase:
    """Require box-centre fall of max(body-box height, configured minimum)."""

    def __init__(self, cfg):
        # type: (dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._fall_min = float(cfg.get("fall_min_delta_z", 0.02))
        self._check_seconds = float(cfg.get("drop_check_seconds", 3.0))
        self._check_frames = int(self._check_seconds * self._fps)
        self._observation_seconds = float(cfg.get("post_drop_observation_seconds", 1.0))
        self._observation_frames = max(0, int(self._observation_seconds * self._fps))

        self._start_frame = None  # type: Optional[int]
        self._drop_start_z = None  # type: Optional[float]
        self._min_z = None  # type: Optional[float]
        self._required_fall = None  # type: Optional[float]
        self._detected_frame = None  # type: Optional[int]
        self._done = False

    def set_drop_start_z(self, z):
        # type: (Optional[float]) -> None
        """Set reference Z from the Opening phase."""
        self._drop_start_z = z

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[dict[str, Any]]
        if self._done:
            return None

        if self._start_frame is None:
            # Opening authored release on the previous phase's tick. The loop's
            # existing advance has now allowed backend application; USD readback
            # alone cannot qualify a Newton free-fall verdict.
            scene.verify_gripper_collision_disabled()
            self._start_frame = frame
            if self._drop_start_z is None and tracker.center_history:
                self._drop_start_z = tracker.center_history[-1][2]
            self._min_z = self._drop_start_z
            # Required fall = max(fall_min, bbox height)
            self._required_fall = self._compute_required_fall(scene)

        elapsed = frame - self._start_frame

        # Track the lowest observed box-centre Z against Opening's reference.
        # Ground overlap is not this phase's criterion; see module docstring.
        cur_z = None
        if tracker.center_history:
            cur_z = tracker.center_history[-1][2]
        drop_distance = 0.0
        if cur_z is not None:
            if self._min_z is None or cur_z < self._min_z:
                self._min_z = cur_z
            if self._drop_start_z is not None and self._min_z is not None:
                drop_distance = self._drop_start_z - self._min_z

        # Detect a complete drop, then keep simulating for a fixed observation
        # tail so the video shows the object's post-release behavior.
        if drop_distance >= self._required_fall and self._detected_frame is None:
            self._detected_frame = frame

        if self._detected_frame is not None and frame - self._detected_frame >= self._observation_frames:
            self._done = True
            return {
                "phase_name": "Dropping",
                "frame": frame,
                "time": time,
                "message": (
                    "Dropping complete: fell %.4fm (required %.4fm); "
                    "observed %.1fs after detection" % (drop_distance, self._required_fall, self._observation_seconds)
                ),
                "failed": False,
                "drop_distance": drop_distance,
                "drop_detection_frame": self._detected_frame,
                "drop_observation_seconds": self._observation_seconds,
            }

        # Timeout: object never fell enough
        if self._detected_frame is None and elapsed >= self._check_frames:
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
        """Required fall = max(fall_min_delta_z, required live body bbox height)."""
        from simready.evaluate_engine_kit.fabric_utils import (
            is_rigid_body,
            live_world_aabb,
            validated_bounds,
        )
        from simready.evaluate_engine_kit.physics_utils import active_physics_engine

        try:
            asset_path = scene.scene_properties.get("tracked_body_path") or scene.scene_properties.get(
                "target_asset_path"
            )
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
                minimum, maximum = validated_bounds(aligned.GetMin(), aligned.GetMax())
            else:
                bounds = live_world_aabb(stage, asset_path, is_rigid_body, require_complete=True)
                if bounds is None:
                    raise ValueError("Required live grasp-body bounds are unavailable: " + str(asset_path))
                minimum, maximum = validated_bounds(*bounds)
            bbox_height = maximum[2] - minimum[2]
            if not math.isfinite(bbox_height) or bbox_height <= 0.0:
                raise ValueError("Required live grasp-body height is non-finite or degenerate")
            return max(self._fall_min, bbox_height)
        except Exception as exc:
            raise RuntimeError("Required grasp-body bounds could not determine the release/drop criterion") from exc

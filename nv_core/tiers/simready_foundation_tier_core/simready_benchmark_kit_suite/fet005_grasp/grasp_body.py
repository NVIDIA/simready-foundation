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

import math
from typing import Optional, Tuple

from pxr import Gf, Usd, UsdGeom, UsdPhysics


def _segment_box_overlap(
    start: Gf.Vec3d,
    end: Gf.Vec3d,
    bounds: Gf.Range3d,
) -> Optional[Tuple[float, float]]:
    """Return the normalized segment interval inside an axis-aligned box."""
    if bounds.IsEmpty():
        return None
    minimum = bounds.GetMin()
    maximum = bounds.GetMax()
    t_min = 0.0
    t_max = 1.0
    for axis in range(3):
        origin = float(start[axis])
        direction = float(end[axis]) - origin
        low = float(minimum[axis])
        high = float(maximum[axis])
        if not all(math.isfinite(value) for value in (origin, direction, low, high)):
            return None
        if abs(direction) <= 1e-12:
            if origin < low or origin > high:
                return None
            continue
        entry = (low - origin) / direction
        exit_ = (high - origin) / direction
        if entry > exit_:
            entry, exit_ = exit_, entry
        t_min = max(t_min, entry)
        t_max = min(t_max, exit_)
        if t_min > t_max:
            return None
    return (t_min, t_max)


def _nearest_rigid_body_ancestor(prim: Usd.Prim, stop_prim: Usd.Prim) -> Optional[Usd.Prim]:
    current = prim.GetParent()
    while current and current.IsValid():
        if current.HasAPI(UsdPhysics.RigidBodyAPI):
            return current
        if current == stop_prim:
            break
        current = current.GetParent()
    return None


def resolve_grasp_body(
    stage: Usd.Stage,
    identifier_path: str,
    asset_root_path: str,
    world_start: Gf.Vec3d,
    world_end: Gf.Vec3d,
) -> str:
    """Resolve the rigid body owned by a grasp identifier.

    Authored identifiers may be children of the rigid body or live in a
    sibling annotation scope. In the latter case, select the body whose world
    bound contains the largest portion of the authored grasp segment.
    """
    identifier = stage.GetPrimAtPath(identifier_path)
    asset_root = stage.GetPrimAtPath(asset_root_path)
    if not identifier or not identifier.IsValid():
        raise ValueError("grasp identifier is missing: " + str(identifier_path))
    if not asset_root or not asset_root.IsValid():
        raise ValueError("mounted asset root is missing: " + str(asset_root_path))

    ancestor = _nearest_rigid_body_ancestor(identifier, asset_root)
    if ancestor is not None:
        return str(ancestor.GetPath())

    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    segment_midpoint = 0.5 * (Gf.Vec3d(world_start) + Gf.Vec3d(world_end))
    candidates = []
    for prim in Usd.PrimRange(
        asset_root,
        Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate),
    ):
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        bounds = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
        overlap = _segment_box_overlap(world_start, world_end, bounds)
        if overlap is None:
            continue
        overlap_size = overlap[1] - overlap[0]
        center_distance = (bounds.GetMidpoint() - segment_midpoint).GetLength() ** 2
        candidates.append((overlap_size, -center_distance, str(prim.GetPath())))

    if candidates:
        return max(candidates)[2]
    return str(asset_root.GetPath())

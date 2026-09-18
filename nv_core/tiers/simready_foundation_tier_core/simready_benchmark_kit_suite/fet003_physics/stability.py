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
"""Rest-detection helpers shared by ground_drop and ground_stability.

A body is "at rest" when its bounding box does not change beyond a small
tolerance over a hold window.  Rotation and translation are both covered
by tracking the bbox centre and the bbox min/max corners -- if both
corners stay put, neither the position nor the orientation changed.

History entries are 9-tuples of floats::

    (cx, cy, cz,            # bbox centre
     min_x, min_y, min_z,   # bbox min corner
     max_x, max_y, max_z)   # bbox max corner

Callers build the history list themselves (one entry per physics frame)
and call ``check_rest_window`` each frame after they have enough history.
"""
from typing import Tuple

HistoryEntry = Tuple[float, float, float, float, float, float, float, float, float]


def check_rest_window(history, hold_frames, pos_tol, corner_tol):
    # type: (List[HistoryEntry], int, float, float) -> bool
    """Return True if the last ``hold_frames`` entries are all close to the latest.

    Requires BOTH bounds centre stability and bbox-corner stability.
    Returns False if the history is shorter than ``hold_frames``.
    """
    if len(history) < hold_frames:
        return False
    return check_position_stable(history, hold_frames, pos_tol) and check_bbox_corners_stable(
        history, hold_frames, corner_tol
    )


def check_position_stable(history, hold_frames, tol):
    # type: (List[HistoryEntry], int, float) -> bool
    """Return True if the bounds centre stays within ``tol`` over the window.

    Euclidean distance between each frame's centre and the latest centre
    must be <= tol for every frame in the window.
    """
    current = history[-1]
    cur_cx, cur_cy, cur_cz = current[0], current[1], current[2]
    window_start = len(history) - hold_frames
    tol_sq = tol * tol
    for i in range(window_start, len(history)):
        h = history[i]
        dx = h[0] - cur_cx
        dy = h[1] - cur_cy
        dz = h[2] - cur_cz
        if dx * dx + dy * dy + dz * dz > tol_sq:
            return False
    return True


def check_bbox_corners_stable(history, hold_frames, tol):
    # type: (List[HistoryEntry], int, float) -> bool
    """Return True if both bbox corners stay within ``tol`` over the window.

    If both bbox min and bbox max are stable, the body has not rotated
    (rotation changes the axis-aligned bbox shape/position).  This avoids
    extracting Euler angles (gimbal lock) and catches all rotation cases.
    """
    current = history[-1]
    window_start = len(history) - hold_frames
    for i in range(window_start, len(history)):
        h = history[i]
        # indices 3..5 = min corner, 6..8 = max corner
        for j in range(3, 9):
            if abs(h[j] - current[j]) > tol:
                return False
    return True


def bounds_to_history_entry(bounds):
    """Convert a RawAssetBounds-like object to a 9-tuple history entry.

    ``bounds`` must expose ``.min`` and ``.max`` as length-3 indexables
    (matches ``ctx.get_asset_bounds()`` return type).
    """
    mn = bounds.min
    mx = bounds.max
    return (
        (mn[0] + mx[0]) / 2.0,
        (mn[1] + mx[1]) / 2.0,
        (mn[2] + mx[2]) / 2.0,
        mn[0],
        mn[1],
        mn[2],
        mx[0],
        mx[1],
        mx[2],
    )

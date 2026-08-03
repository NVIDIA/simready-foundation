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
"""Robot default-state capture and reset.

Ported from v1 test_infra/reset_helpers.py.
"""
from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class RobotDefaultState:
    """Snapshot of a robot's joint state and root pose for reset."""

    joint_positions: np.ndarray
    joint_velocities: np.ndarray
    root_position: Tuple[float, float, float]
    root_orientation: Tuple[float, float, float, float]  # quaternion (w, x, y, z)


def capture_default_state(robot):
    # type: (Any) -> RobotDefaultState
    """Snapshot joint state. Root pose defaults to identity when unavailable."""
    positions = np.array(robot.get_joint_positions(), dtype=np.float64)
    velocities = np.array(robot.get_joint_velocities(), dtype=np.float64)

    root_position = (0.0, 0.0, 0.0)
    root_orientation = (1.0, 0.0, 0.0, 0.0)
    art = getattr(robot, "articulation", None)
    if art is not None:
        try:
            pos, orient = art.get_world_pose()
            root_position = (float(pos[0]), float(pos[1]), float(pos[2]))
            root_orientation = (
                float(orient[0]),
                float(orient[1]),
                float(orient[2]),
                float(orient[3]),
            )
        except Exception:
            pass

    return RobotDefaultState(
        joint_positions=positions,
        joint_velocities=velocities,
        root_position=root_position,
        root_orientation=root_orientation,
    )


async def reset_to_default(ctx, robot, state, settle_seconds=0.5):
    # type: (Any, Any, RobotDefaultState, float) -> None
    """Zero velocities, restore positions + root pose, settle."""
    if getattr(robot, "dof_count", 0) > 0:
        robot.set_joint_velocities(np.zeros_like(state.joint_velocities))
        robot.set_joint_positions(state.joint_positions)

    art = getattr(robot, "articulation", None)
    if art is not None:
        try:
            art.set_world_pose(
                position=np.array(state.root_position, dtype=np.float64),
                orientation=np.array(state.root_orientation, dtype=np.float64),
            )
        except Exception:
            pass

    count = max(1, int(round(settle_seconds * 10)))
    await ctx.settle(count=count)

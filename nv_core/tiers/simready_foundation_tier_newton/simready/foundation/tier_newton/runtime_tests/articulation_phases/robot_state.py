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

import numpy as np
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
    require_vector,
    required_positions,
    required_velocities,
)


@dataclass
class RobotDefaultState:
    """Snapshot of a robot's joint state and root pose for reset."""

    joint_positions: np.ndarray
    joint_velocities: np.ndarray
    root_position: tuple[float, float, float]
    root_orientation: tuple[float, float, float, float]  # quaternion (w, x, y, z)
    root_pose_observed: bool = False


def _validated_root_pose(position, orientation):
    position = require_vector(position, "robot default state", "root position", 3)
    orientation = require_vector(orientation, "robot default state", "root quaternion", 4)
    norm = float(np.linalg.norm(orientation))
    if not np.isfinite(norm) or norm <= 0.0:
        raise RequiredReadbackError("robot default state: root quaternion must have a positive finite norm")
    return tuple(float(value) for value in position), tuple(float(value) for value in orientation)


def capture_default_state(robot):
    # type: (Any) -> RobotDefaultState
    """Save required joint and articulation root state for later reset.

    Root values are unused identity placeholders only when no articulation
    exists. They are labelled unobserved, never substituted for a failed view.
    """
    positions = np.array(required_positions(robot, "robot default state"), dtype=np.float64)
    velocities = np.array(required_velocities(robot, "robot default state"), dtype=np.float64)

    root_position = (0.0, 0.0, 0.0)
    root_orientation = (1.0, 0.0, 0.0, 0.0)
    root_pose_observed = False
    art = getattr(robot, "articulation", None)
    if art is not None:
        try:
            get_root_pose = getattr(robot, "get_world_pose", None)
            pos, orient = get_root_pose() if callable(get_root_pose) else art.get_world_pose()
            root_position, root_orientation = _validated_root_pose(pos, orient)
            root_pose_observed = True
        except RequiredReadbackError:
            raise
        except Exception as exc:
            raise RequiredReadbackError(
                "robot default state: required articulation root pose unavailable: %s" % exc
            ) from exc

    return RobotDefaultState(
        joint_positions=positions,
        joint_velocities=velocities,
        root_position=root_position,
        root_orientation=root_orientation,
        root_pose_observed=root_pose_observed,
    )


async def reset_to_default(ctx, robot, state, settle_seconds=0.5):
    # type: (Any, Any, RobotDefaultState, float) -> None
    """Zero velocities, restore positions + root pose, settle."""
    art = getattr(robot, "articulation", None)
    if art is not None:
        if not state.root_pose_observed:
            raise RequiredReadbackError("robot reset: saved articulation root pose was not observed")
        root_position, root_orientation = _validated_root_pose(state.root_position, state.root_orientation)
    if getattr(robot, "dof_count", 0) > 0:
        positions = require_vector(state.joint_positions, "robot reset", "saved joint position", robot.dof_count)
        velocities = require_vector(state.joint_velocities, "robot reset", "saved joint velocity", robot.dof_count)
        robot.set_joint_velocities(np.zeros_like(velocities))
        robot.set_joint_positions(positions)

    if art is not None:
        try:
            art.set_world_pose(
                position=np.array(root_position, dtype=np.float64),
                orientation=np.array(root_orientation, dtype=np.float64),
            )
        except Exception as exc:
            raise RequiredReadbackError("robot reset: required articulation root restore failed: %s" % exc) from exc

    count = max(1, int(round(settle_seconds * 10)))
    await ctx.settle(count=count)

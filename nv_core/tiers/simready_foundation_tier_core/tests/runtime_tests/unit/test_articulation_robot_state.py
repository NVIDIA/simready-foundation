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
"""Tests for articulation_phases.robot_state (uses fake RobotHandle stub)."""
import numpy as np
import pytest
from simready_benchmark_kit_suite.articulation_phases.robot_state import (
    RobotDefaultState,
    capture_default_state,
    reset_to_default,
)


class FakeRobot:
    def __init__(self):
        self.dof_count = 3
        self._positions = np.array([0.1, 0.2, 0.3])
        self._velocities = np.array([0.0, 0.0, 0.0])
        self._set_positions = None
        self._set_velocities = None

    def get_joint_positions(self):
        return self._positions.copy()

    def get_joint_velocities(self):
        return self._velocities.copy()

    def set_joint_positions(self, p):
        self._set_positions = np.array(p, dtype=np.float64)
        self._positions = np.array(p, dtype=np.float64)

    def set_joint_velocities(self, v):
        self._set_velocities = np.array(v, dtype=np.float64)
        self._velocities = np.array(v, dtype=np.float64)


class FakeCtx:
    def __init__(self):
        self.settle_calls = []

    async def settle(self, count=1):
        self.settle_calls.append(count)


def test_capture_default_state_snapshots_positions_and_velocities():
    robot = FakeRobot()
    state = capture_default_state(robot)
    assert isinstance(state, RobotDefaultState)
    assert list(state.joint_positions) == [0.1, 0.2, 0.3]
    assert list(state.joint_velocities) == [0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_reset_to_default_zeroes_velocities_and_sets_positions():
    robot = FakeRobot()
    robot._positions = np.array([5.0, 5.0, 5.0])
    state = RobotDefaultState(
        joint_positions=np.array([0.1, 0.2, 0.3]),
        joint_velocities=np.array([0.0, 0.0, 0.0]),
        root_position=(0.0, 0.0, 0.0),
        root_orientation=(1.0, 0.0, 0.0, 0.0),
    )
    ctx = FakeCtx()
    await reset_to_default(ctx, robot, state, settle_seconds=0.5)
    assert robot._set_velocities is not None
    assert list(robot._set_velocities) == [0.0, 0.0, 0.0]
    assert robot._set_positions is not None
    assert list(robot._set_positions) == [0.1, 0.2, 0.3]
    assert ctx.settle_calls


@pytest.mark.asyncio
async def test_reset_to_default_handles_zero_dof_count_gracefully():
    class EmptyRobot:
        dof_count = 0

        def get_joint_positions(self):
            return np.array([])

        def get_joint_velocities(self):
            return np.array([])

        def set_joint_positions(self, p):
            pass

        def set_joint_velocities(self, v):
            pass

    robot = EmptyRobot()
    state = RobotDefaultState(
        joint_positions=np.array([]),
        joint_velocities=np.array([]),
        root_position=(0.0, 0.0, 0.0),
        root_orientation=(1.0, 0.0, 0.0, 0.0),
    )
    ctx = FakeCtx()
    await reset_to_default(ctx, robot, state)

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
"""Generic nonlinear and bounded-failure regressions for the production solver."""

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.jik_solver import JacobianIKSolver


class CubicRobot:
    dof_names = ["joint"]

    def __init__(self):
        self.q = np.array([0.001])
        self.commands = []

    def get_joint_positions(self):
        return self.q.copy()

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def set_joint_positions(self, q):
        self.q = q.copy()
        self.commands.append(q.copy())

    def set_joint_position_targets(self, q):
        pass

    def set_joint_velocities(self, velocity):
        pass

    def get_link_world_transforms(self, paths):
        return {paths[0]: (np.array([self.q[0] ** 3, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))}


@pytest.mark.asyncio
async def test_backtracking_reduces_nonlinear_overshoot_without_target_or_limit_changes():
    robot = CubicRobot()
    solver = JacobianIKSolver(robot, "/tool", damping_lambda=0.0, finite_difference_epsilon=1e-5)
    ticks = []

    async def step():
        ticks.append(1)

    result = await solver.solve(
        np.array([0.02**3, 0.0, 0.0]), [1.0, 0.0, 0.0, 0.0], step, max_iterations=50, pos_tol=1e-9
    )
    assert result.success
    assert abs(robot.q[0] - 0.02) < 1e-5
    assert all(-1.0 <= command[0] <= 1.0 for command in robot.commands)
    assert result.final_pos_error < 1e-9
    assert len(ticks) <= 50 * (8 + 6) + 1


@pytest.mark.asyncio
async def test_unreachable_target_is_not_fabricated_by_best_iterate_restoration():
    robot = CubicRobot()
    solver = JacobianIKSolver(robot, "/tool", damping_lambda=0.05)

    async def step():
        return None

    result = await solver.solve(np.array([10.0, 0.0, 0.0]), [1.0, 0.0, 0.0, 0.0], step, max_iterations=10, pos_tol=0.01)
    assert not result.success
    assert result.final_pos_error == pytest.approx(abs(10.0 - robot.q[0] ** 3))
    assert np.array_equal(result.converged_joints, robot.q)

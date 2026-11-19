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
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import state_accuracy as phase
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)


class ExactTracker:
    dof_names = ["joint"]
    dof_count = 1

    def __init__(self):
        self.positions = np.array([0.0])
        self.commands = []
        self.track = True
        self.invalid_position = False
        self.invalid_velocity = False
        self.command_error = None

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def get_joint_positions(self):
        return np.array([math.nan]) if self.invalid_position else self.positions.copy()

    def get_joint_velocities(self):
        return np.array([math.nan]) if self.invalid_velocity else np.array([0.0])

    def set_joint_position_targets(self, command):
        if self.command_error is not None and len(self.commands) == 2:
            raise self.command_error
        self.commands.append(command.copy())
        if self.track:
            self.positions = command.copy()


@pytest.fixture
def trial(monkeypatch):
    robot = ExactTracker()
    state = SimpleNamespace(ticks=0, failures=[], metrics={}, tick_error=None, tick_hook=None)

    async def step():
        state.ticks += 1
        if state.tick_hook is not None:
            state.tick_hook()
        if state.tick_error is not None and state.ticks == 3:
            raise state.tick_error

    async def capture(*args, **kwargs):
        return None

    ctx = SimpleNamespace(
        step_one=step,
        capture_frame=capture,
        scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None),
        step=lambda *args: None,
        log=lambda *args: None,
        warn=lambda *args: None,
        fail=lambda message: state.failures.append(message),
        skip=lambda message: pytest.fail(message),
        add_metric=lambda key, value: state.metrics.__setitem__(key, value),
    )
    monkeypatch.setattr(phase, "compute_world_aligned_bbox", lambda *args: None)
    monkeypatch.setattr(phase, "check_bbox_explode", lambda *args: None)
    return robot, ctx, state


async def _run_ramp(robot, ctx, target):
    await phase._run_motion_to_target(
        ctx, robot, {"index": 0, "name": "joint"}, target, 100, 10, [], None, 10.0, None, None, 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [0.001, 0.2, -0.2])
async def test_exact_tracker_completes_every_smoothstep_command_before_hold(trial, target):
    robot, ctx, state = trial
    await _run_ramp(robot, ctx, target)
    expected = [target * phase.smoothstep((index + 1) / 100.0) for index in range(100)]
    assert len(robot.commands) == state.ticks == 100
    assert [float(command[0]) for command in robot.commands] == pytest.approx(expected)
    assert robot.commands[-1][0] == target
    await phase._run_settle_to_target(ctx, robot, {"index": 0, "name": "joint"}, target, 120, 10, [], 1, "test")
    assert phase.classify_position_error(robot.positions[0], target, math.radians(1.0))[0]
    assert len(robot.commands) == 100  # Holding does not add a teleport/endpoint jump.


@pytest.mark.asyncio
@pytest.mark.parametrize("tolerance_deg", [0.0, 1.0, 5.0])
async def test_official_phase_perfect_tracking_passes_tight_and_default_tolerance(trial, tolerance_deg):
    robot, ctx, state = trial
    config = dict(phase.get_defaults(), settle_seconds=0.0, position_tolerance_deg=tolerance_deg)
    await phase.run_state_accuracy(ctx, robot, {}, config)
    frames = phase.compute_motion_frames(config["test_duration_seconds"], config["physics_fps"], 5)
    assert len(robot.commands) == 5 * frames
    goals = phase.compute_test_positions(-1.0, 1.0)
    assert [float(robot.commands[(index + 1) * frames - 1][0]) for index in range(5)] == pytest.approx(goals)
    assert not state.failures
    assert state.metrics["sta_joints_passed"] == 1
    assert state.metrics["sta_max_position_error_deg"] == pytest.approx(0.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("start,target", [(2.0, 0.05), (-2.0, -0.05), (1e12, 0.05)])
async def test_last_ramp_command_is_exact_goal_despite_cancellation_roundoff(trial, start, target):
    robot, ctx, state = trial
    robot.positions = np.array([start])
    await _run_ramp(robot, ctx, target)
    assert len(robot.commands) == state.ticks == 100
    assert robot.commands[-1][0] == target
    assert phase.classify_position_error(robot.positions[0], target, 0.0)[0]


@pytest.mark.asyncio
async def test_completed_commands_do_not_relax_measured_nontracking_failure(trial):
    robot, ctx, state = trial
    robot.track = False
    await phase.run_state_accuracy(
        ctx, robot, {}, dict(phase.get_defaults(), settle_seconds=0.0, position_tolerance_deg=1.0)
    )
    assert state.failures and state.metrics["sta_joints_failed"] == 1
    assert state.metrics["sta_max_position_error_deg"] > 1.0


@pytest.mark.asyncio
async def test_transient_goal_readback_does_not_truncate_remaining_paced_commands(trial):
    robot, ctx, state = trial

    def briefly_cross_goal():
        if state.ticks == 3:
            robot.positions = np.array([0.2])

    state.tick_hook = briefly_cross_goal
    await _run_ramp(robot, ctx, 0.2)
    assert len(robot.commands) == state.ticks == 100
    assert [float(command[0]) for command in robot.commands] == pytest.approx(
        [0.2 * phase.smoothstep((index + 1) / 100.0) for index in range(100)]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["position", "velocity", "command", "step"])
async def test_required_runtime_failure_stops_ramp_without_completing_commands(trial, kind):
    robot, ctx, state = trial
    original = RuntimeError("original required operation failed")
    if kind == "command":
        robot.command_error = original
    elif kind == "step":
        state.tick_error = original
    else:

        def fail_readback():
            if state.ticks == 3:
                setattr(robot, "invalid_" + kind, True)

        state.tick_hook = fail_readback
    expected = RequiredReadbackError if kind in ("position", "velocity") else RuntimeError
    with pytest.raises(expected) as caught:
        await _run_ramp(robot, ctx, 0.2)
    if kind in ("command", "step"):
        assert caught.value is original
    assert 0 < len(robot.commands) <= 3
    assert state.ticks <= 3
    assert not state.failures

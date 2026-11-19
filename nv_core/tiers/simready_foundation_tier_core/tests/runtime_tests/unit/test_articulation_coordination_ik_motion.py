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

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach,
    jacobian_ik,
    mimic_joint,
    motion_history,
    multi_joint_coordination,
)


class _History:
    def __init__(self, channels, metadata):
        self.channels = channels
        self.metadata = metadata
        self.samples = []
        self.captures = []
        self.partial = []
        self.reason = None

    def sample(self, time_s, values, **kwargs):
        assert not self.samples or time_s > self.samples[-1][0]
        self.samples.append((time_s, dict(values), kwargs))

    def record_capture(self, time_s):
        self.captures.append(time_s)

    def mark_partial(self, reason):
        self.partial.append(reason)

    def finish(self, reason):
        self.reason = reason


class _Robot:
    def __init__(self, count=2, coupled=False):
        self.dof_names = ["joint_%d" % index for index in range(count)]
        self.prim_path = "/Robot"
        self.positions = np.zeros(count)
        self.target = self.positions.copy()
        self.commands = []
        self.coupled = coupled
        self.fail_next_read = False

    def get_joint_positions(self):
        if self.fail_next_read:
            self.fail_next_read = False
            raise RuntimeError("joint readback unavailable")
        return self.positions.copy()

    def get_joint_position_limits(self):
        return np.zeros(len(self.positions)), np.ones(len(self.positions))

    def set_joint_position_targets(self, command):
        self.target = np.asarray(command).copy()
        self.commands.append(self.target.copy())

    def set_joint_position_targets_indexed(self, values, indices):
        assert list(indices) == [0]
        self.target[indices] = values
        self.commands.append(self.target.copy())

    def set_joint_positions_indexed(self, values, indices):
        self.positions[indices] = values

    def set_joint_velocities_indexed(self, values, indices):
        raise AssertionError("MIM does not write velocities")


class _Context:
    def __init__(self, robot, recording=True, capture=True):
        self.robot = robot
        self.histories = {}
        self.warnings = []
        self.steps = 0
        self.failed = False
        self.capture = capture
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)
        if not recording:
            self.begin_motion_history = None

    def begin_motion_history(self, name, channels, metadata=None):
        assert name not in self.histories
        self.histories[name] = _History(channels, metadata)
        return self.histories[name]

    async def step_one(self):
        self.steps += 1
        self.robot.positions = self.robot.target.copy()
        if self.robot.coupled:
            self.robot.positions[1] = self.robot.positions[0]

    async def physics_steps(self, count):
        for _ in range(count):
            await self.step_one()

    async def capture_frame(self, **kwargs):
        return "capture_%d.png" % self.steps if self.capture else None

    def encode_video(self, *args, **kwargs):
        pass

    def step(self, *args, **kwargs):
        pass

    def log(self, *args):
        pass

    def add_metric(self, *args):
        pass

    def warn(self, message):
        self.warnings.append(message)

    def fail(self, message):
        self.failed = True


@pytest.fixture
def joint_units(monkeypatch):
    monkeypatch.setattr(
        motion_history,
        "joint_metadata",
        lambda stage, root, name, root_path=None: {
            "joint_name": name,
            "unit": "rad",
            "identity_resolved": True,
            "meters_per_unit": 1.0,
        },
    )


@pytest.mark.asyncio
async def test_mimic_histories_use_existing_pair_readbacks_and_actual_commands(monkeypatch, joint_units):
    pair = SimpleNamespace(reference_dof_index=0, follower_dof_index=1, gear=-1.0, offset=0.0, backend="physx")
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **kwargs: [pair])
    monkeypatch.setattr(mimic_joint, "compute_world_aligned_bbox", lambda prim: object())
    monkeypatch.setattr(mimic_joint, "check_bbox_explode", lambda *args: None)
    robot = _Robot(coupled=True)
    ctx = _Context(robot)
    await mimic_joint.run_mimic_joint(
        ctx, robot, {"stage": None}, {"physics_fps": 10, "settle_seconds": 0, "sweep_seconds": 4, "capture_fps": 10}
    )
    reference = ctx.histories["mim_reference_001"]
    follower = ctx.histories["mim_follower_001"]
    assert len(reference.samples) == 4
    assert reference.samples[0][0] == pytest.approx(0.1)
    assert [row[2]["phase"] for row in follower.samples] == ["outbound", "outbound", "outbound", "return"]
    for time_s, values, kwargs in reference.samples:
        index = round(time_s * 10) - 1
        assert values["target"] == robot.commands[index][0]
        assert kwargs["clock_source"] == "estimated"
    assert follower.samples[-1][1]["incremental_error"] == pytest.approx(0)
    assert reference.reason == follower.reason == "mimic_pair_sweep_completed"
    assert reference.captures and follower.captures
    assert ctx.steps == len(robot.commands) == 40
    assert not ctx.failed


@pytest.mark.asyncio
async def test_coordination_histories_keep_monotonic_clock_across_iterations(monkeypatch, joint_units):
    monkeypatch.setattr(multi_joint_coordination, "compute_world_aligned_bbox", lambda prim: object())
    monkeypatch.setattr(multi_joint_coordination, "check_bbox_explode", lambda *args: None)
    robot = _Robot()
    ctx = _Context(robot, capture=False)
    await multi_joint_coordination.run_multi_joint_coordination(
        ctx,
        robot,
        {},
        {"physics_fps": 10, "settle_seconds": 0, "num_iterations": 2, "motion_seconds": 0.1, "capture_fps": 10},
    )
    assert ctx.steps == len(robot.commands) == 2
    history = ctx.histories["mjc_joint_000"]
    assert [row[0] for row in history.samples] == pytest.approx([0.1, 0.2])
    assert [row[2]["phase"] for row in history.samples] == ["iteration_0_ramp", "iteration_1_ramp"]
    assert history.reason == "coordination_iterations_completed"
    assert not history.captures
    assert history.channels["position"]["unit"] == "rad"
    assert not ctx.failed


def _playback_observer(ctx):
    return {
        0: motion_history.make_joint_observer(
            ctx,
            {},
            "joint_0",
            "playback_joint_0",
            {
                "position": {"unit": "{joint}", "source": "measured articulation position"},
                "target": {"unit": "{joint}", "source": "issued command"},
                "error": {"unit": "{joint}", "source": "command minus position"},
            },
        )
    }


@pytest.mark.asyncio
async def test_lula_playback_hooks_preserve_commands_ticks_and_result(monkeypatch, joint_units):
    monkeypatch.setattr(ik_target_reach, "_compute_target_error", lambda *args: 1.0)
    runs = []
    for recording in (False, True):
        robot = _Robot(count=1)
        ctx = _Context(robot, recording=recording)
        observers = _playback_observer(ctx)
        result = await ik_target_reach._interpolate_ik_motion(
            ctx,
            robot,
            object(),
            object(),
            np.array([1.0]),
            1,
            [],
            8,
            0.02,
            None,
            None,
            10.0,
            "target_0",
            observers,
            {"steps": 0, "command": None},
            10.0,
        )
        runs.append((result, ctx.steps, np.asarray(robot.commands)))
        if recording:
            history = ctx.histories["playback_joint_0"]
            assert history.samples and history.captures
            assert all(row[1]["target"] == robot.commands[round(row[0] * 10) - 1][0] for row in history.samples)
        else:
            assert not ctx.histories
    assert runs[0][:2] == runs[1][:2] == ((False, 1.0), 8)
    np.testing.assert_array_equal(runs[0][2], runs[1][2])


@pytest.mark.asyncio
async def test_jacobian_optional_readback_failure_is_partial_not_verdict_failure(joint_units):
    robot = _Robot(count=1)
    ctx = _Context(robot, capture=False)
    observers = _playback_observer(ctx)
    robot.fail_next_read = True
    errors = await jacobian_ik._interpolate_to_solution(
        ctx,
        robot,
        {},
        np.array([0.0]),
        np.array([1.0]),
        0.8,
        10.0,
        1,
        [],
        "trial",
        "smoothstep",
        None,
        10.0,
        "target_0",
        motion_observers=observers,
        motion_clock={"steps": 0},
    )
    history = ctx.histories["playback_joint_0"]
    assert not errors and not ctx.failed
    assert ctx.steps == len(robot.commands) == 8
    assert history.samples[0][1]["position"] is None
    assert history.samples[0][1]["error"] is None
    assert history.partial and len(ctx.warnings) == 1
    assert history.samples[-1][1]["position"] is not None
    assert not history.captures


@pytest.mark.asyncio
async def test_coordination_required_readback_error_still_propagates(monkeypatch):
    monkeypatch.setattr(multi_joint_coordination, "compute_world_aligned_bbox", lambda prim: object())
    robot = _Robot()
    ctx = _Context(robot, recording=False)
    robot.fail_next_read = True
    with pytest.raises(RuntimeError, match="joint readback unavailable"):
        await multi_joint_coordination._run_iteration(
            ctx,
            robot,
            {},
            [{"index": 0, "name": "joint_0", "lower": 0, "upper": 1}],
            0.5,
            0,
            0.01,
            2,
            1,
            [],
            object(),
            10,
            0.1,
            10,
            1,
        )


@pytest.mark.asyncio
async def test_lula_hold_dispatch_failure_prevents_stale_target_pass(joint_units):
    robot = _Robot(count=1)
    robot.target[:] = 0.25
    ctx = _Context(robot, capture=False)
    observers = _playback_observer(ctx)

    def rejected_command(command):
        raise RuntimeError("dispatch unavailable")

    robot.set_joint_position_targets = rejected_command
    with pytest.raises(ik_target_reach.RequiredReadbackError, match="hold command failed") as raised:
        await ik_target_reach._hold_after_reach(
            ctx,
            robot,
            np.array([1.0]),
            3,
            1,
            [],
            1,
            "target_0",
            motion_observers=observers,
            motion_clock={"steps": 1, "command": np.array([0.25])},
            physics_fps=10,
        )
    history = ctx.histories["playback_joint_0"]
    assert str(raised.value.__cause__) == "dispatch unavailable"
    assert ctx.steps == 0
    assert history.samples == []
    np.testing.assert_array_equal(robot.target, [0.25])
    assert not ctx.failed


@pytest.mark.asyncio
async def test_jacobian_locked_joint_plot_omits_unissued_command_and_requested_goal(joint_units):
    robot = _Robot(count=1)
    ctx = _Context(robot)
    observers = _playback_observer(ctx)
    await jacobian_ik._interpolate_to_solution(
        ctx,
        robot,
        {},
        np.array([0.0]),
        np.array([1.0]),
        0.8,
        10.0,
        1,
        [],
        "trial",
        "smoothstep",
        None,
        10.0,
        "target_0",
        locked_indices={0},
        motion_observers=observers,
        motion_clock={"steps": 0},
    )
    history = ctx.histories["playback_joint_0"]
    assert ctx.steps == 8 and robot.commands == []
    assert all(set(row[1]) == {"position"} for row in history.samples)
    assert history.captures

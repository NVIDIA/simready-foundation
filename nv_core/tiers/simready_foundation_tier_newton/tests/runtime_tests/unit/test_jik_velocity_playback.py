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
from simready.foundation.tier_newton.runtime_tests.articulation_phases import jacobian_ik as phase
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.sweep_timing import (
    SweepBudgetExceeded,
)


@pytest.mark.parametrize(
    "profile,peak", [("linear", 1.0), ("smoothstep", 1.5), ("smootherstep", 1.875), ("trapezoidal", 2.0)]
)
def test_playback_paces_slowest_independent_coordinate(profile, peak):
    cfg = {"physics_fps": 240, "interpolation_profile": profile}
    frames = phase._playback_frames(
        [0, 0, 0], [1, 2, 100], [(0.25, "native"), (2.0, "native"), (1e-12, "native")], {2}, cfg, 1.25
    )
    assert frames == int(np.ceil((peak / (0.25 * 0.8) + 0.25) * 240))


def test_minimum_missing_hint_and_exact_rounding():
    cfg = {"physics_fps": 240}
    assert phase._playback_frames([0], [1], [(None, "fallback")], set(), cfg, 1.25) == int(np.ceil(1.25 * 240))
    assert phase._playback_frames([0], [0], [(100.0, "native")], set(), cfg, 1.25) == int(np.ceil(1.25 * 240))
    assert phase._playback_frames([0], [1], [(None, "fallback")], set(), {"physics_fps": 7}, 0.9) == 7


def test_named_policy_overrides_are_used_and_budget_is_phase_accurate():
    cfg = {
        "physics_fps": 10,
        "sweep_speed_scale": 0.5,
        "sweep_settling_allowance_seconds": 0.4,
        "max_sweep_segment_seconds": 4,
    }
    assert phase._playback_frames([0], [1], [(1.0, "native")], set(), cfg, 1.25) == 34
    with pytest.raises(SweepBudgetExceeded, match="JIK.*incomplete|JIK.*insufficient") as exc:
        phase._playback_frames([0], [1], [(0.001, "native")], set(), cfg, 1.25)
    assert exc.value.reason == "segment_budget"


@pytest.mark.parametrize(
    "start,end,hints", [([0, 1], [1], [(1.0, "native")]), ([0], [float("nan")], [(1.0, "native")]), ([0], [1], [])]
)
def test_invalid_required_dimensions_are_not_zero_or_truncated(start, end, hints):
    with pytest.raises((RequiredReadbackError, ValueError)):
        phase._playback_frames(start, end, hints, set(), {"physics_fps": 240}, 1.25)


class Robot:
    dof_names = ["active", "held"]
    prim_path = "/Robot"

    def __init__(self):
        self.positions = np.zeros(2)
        self.target = self.positions.copy()
        self.commands = []
        self.hints = [0.25, 1e-12]

    def set_joint_positions_indexed(self, values, indices):
        raise AssertionError("playback must not teleport")

    def set_joint_velocities_indexed(self, values, indices):
        raise AssertionError("playback must not set velocities")

    def get_joint_positions(self):
        return self.positions.copy()

    def get_joint_velocity_limits(self):
        return self.hints

    def set_joint_position_targets_indexed(self, values, indices):
        assert list(indices) == [0]
        self.target[indices] = values
        self.commands.append((values.copy(), indices.copy()))


class Context:
    def __init__(self, robot):
        self.robot = robot
        self.steps = 0
        self.metrics = {}
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)

    async def step_one(self):
        self.steps += 1
        self.robot.positions = self.robot.target.copy()

    async def physics_steps(self, count):
        for _ in range(count):
            await self.step_one()

    async def capture_frame(self, **kwargs):
        return None

    def step(self, *args, **kwargs):
        pass

    def log(self, *args, **kwargs):
        pass

    def warn(self, *args, **kwargs):
        pass

    def add_metric(self, name, value):
        self.metrics[name] = value


def solution(index, value):
    return {
        "target": SimpleNamespace(index=index, is_reachable=True, position=np.zeros(3)),
        "solver_success": True,
        "pos_err": 0.0,
        "orient_err_deg": 0.0,
        "solution": np.array([value, 100.0]),
        "iterations": 1,
    }


@pytest.mark.asyncio
async def test_actual_playback_preserves_sparse_commands_minimum_hold_and_scheduled_evidence(monkeypatch):
    robot = Robot()
    ctx = Context(robot)
    monkeypatch.setattr(phase, "check_bbox_explode", lambda *args: None)
    solver = SimpleNamespace(get_ee_pose=lambda: (np.zeros(3), [1, 0, 0, 0]))
    cfg = phase.get_defaults()
    result = await phase._run_motion_for_solutions(
        ctx, robot, solver, {}, [solution(0, 1.0)], np.zeros(2), cfg, [], 10000, None, locked_indices={1}
    )
    assert result[0]["passed"]
    assert result[0]["scheduled_interpolation_frames"] == 1860
    assert result[0]["scheduled_interpolation_seconds"] == 7.75
    assert ctx.steps == 1860 + int(1.0 * 240)
    assert robot.positions.tolist() == [1.0, 0.0]


@pytest.mark.asyncio
async def test_budget_keeps_completed_targets_without_fabricating_current_verdict(monkeypatch):
    robot = Robot()
    ctx = Context(robot)
    monkeypatch.setattr(phase, "check_bbox_explode", lambda *args: None)
    solver = SimpleNamespace(get_ee_pose=lambda: (np.zeros(3), [1, 0, 0, 0]))
    with pytest.raises(SweepBudgetExceeded, match="JIK"):
        await phase._run_motion_for_solutions(
            ctx,
            robot,
            solver,
            {},
            [solution(0, 0.0), solution(1, 100.0)],
            np.zeros(2),
            phase.get_defaults(),
            [],
            10000,
            None,
            locked_indices={1},
        )
    assert len(ctx.metrics["jik_per_target"]) == 1
    assert ctx.metrics["jik_per_target"][0]["passed"]
    assert ctx.metrics["jik_playback_completion"] == "incomplete"
    assert ctx.metrics["jik_interrupted_target_index"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["initial", "command", "tick", "subsequent", "hold", "ee", "cancel"])
@pytest.mark.parametrize("optional_failure", [False, True])
async def test_entire_required_playback_keeps_prior_target_and_first_cause(monkeypatch, failure, optional_failure):
    import asyncio

    robot = Robot()
    robot.hints = [None, None]
    ctx = Context(robot)
    primary = asyncio.CancelledError() if failure == "cancel" else RuntimeError("required " + failure)
    read = robot.get_joint_positions
    command = robot.set_joint_position_targets_indexed
    tick = ctx.step_one
    reads = 0

    def positions():
        nonlocal reads
        reads += 1
        if (
            (failure == "initial" and reads == 1)
            or (failure == "subsequent" and reads == 3)
            or (failure == "hold" and ctx.steps == 2)
        ):
            raise primary
        return read()

    def issue(values, indices):
        if failure == "command":
            raise primary
        return command(values, indices)

    async def step():
        if failure in ("tick", "cancel"):
            raise primary
        await tick()

    def ee():
        if failure == "ee":
            raise primary
        return np.zeros(3), [1, 0, 0, 0]

    async def capture(**kwargs):
        # Recoverable media absence is producer-owned; camera/observer sinks
        # below provide the independent ordinary optional failure control.
        return None

    robot.get_joint_positions = positions
    robot.set_joint_position_targets_indexed = issue
    ctx.step_one = step
    ctx.capture_frame = capture
    if optional_failure:

        def cleanup(*args, **kwargs):
            raise OSError("optional observer unavailable")

        monkeypatch.setattr(phase, "finish_joint_observers", cleanup)
        ctx.scene.update_camera_follow = cleanup
    cfg = phase.get_defaults()
    cfg.update(physics_fps=2, interpolation_seconds=1.0, hold_after_reach_seconds=1.0)
    rejected = solution(0, 0)
    rejected.update(solver_success=False, solution=None)
    rejected["target"].is_reachable = False
    with pytest.raises(BaseException) as caught:
        await phase._run_motion_for_solutions(
            ctx,
            robot,
            SimpleNamespace(get_ee_pose=ee),
            {},
            [rejected, solution(1, 0)],
            np.zeros(2),
            cfg,
            [],
            1,
            None,
            locked_indices={1},
        )
    cause = caught.value
    while cause is not primary and cause.__cause__ is not None:
        cause = cause.__cause__
    assert cause is primary
    assert [row["index"] for row in ctx.metrics["jik_per_target"]] == [0]
    assert ctx.metrics["jik_per_target"][0]["passed"] is True
    assert ctx.metrics["jik_interrupted_target_index"] == 1
    assert ctx.metrics["jik_playback_completion"] == "incomplete"


@pytest.mark.asyncio
async def test_failed_optional_metric_sink_preserves_primary_and_independent_publication(monkeypatch):
    robot = Robot()
    ctx = Context(robot)
    primary = RuntimeError("required initial positions")

    def positions():
        raise primary

    robot.get_joint_positions = positions
    original = ctx.add_metric

    def metric(name, value):
        if name == "jik_per_target":
            raise OSError("storage unavailable")
        original(name, value)

    ctx.add_metric = metric
    with pytest.raises(BaseException) as caught:
        await phase._run_motion_for_solutions(
            ctx, robot, None, {}, [solution(1, 0)], np.zeros(2), phase.get_defaults(), [], 1, None
        )
    assert caught.value is primary or caught.value.__cause__ is primary
    assert ctx.metrics["jik_interrupted_target_index"] == 1
    assert "jik_per_target" not in ctx.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera", "capture"])
@pytest.mark.parametrize("kind", ["ordinary", "cancel", "exit", "keyboard", "unsafe"])
async def test_optional_playback_preserves_control_flow_and_capture_contract(monkeypatch, operation, kind):
    import asyncio

    from simready.evaluate.core.output_layout import UnsafeEvidencePathError

    primary = {
        "ordinary": OSError("sink or capture failed"),
        "cancel": asyncio.CancelledError("stop"),
        "exit": SystemExit("stop"),
        "keyboard": KeyboardInterrupt("stop"),
        "unsafe": UnsafeEvidencePathError("unsafe evidence"),
    }[kind]
    robot = Robot()
    robot.hints = [None, None]
    ctx = Context(robot)

    def fail(*args, **kwargs):
        raise primary

    async def capture(**kwargs):
        raise primary

    if operation == "camera":
        ctx.scene.update_camera_follow = fail
    else:
        ctx.capture_frame = capture
    monkeypatch.setattr(phase, "check_bbox_explode", lambda *args: None)
    cfg = phase.get_defaults()
    cfg.update(physics_fps=2, interpolation_seconds=1.0, hold_after_reach_seconds=1.0)
    rejected = solution(0, 0)
    rejected.update(solver_success=False, solution=None)
    rejected["target"].is_reachable = False
    call = phase._run_motion_for_solutions(
        ctx,
        robot,
        SimpleNamespace(get_ee_pose=lambda: (np.zeros(3), [1, 0, 0, 0])),
        {},
        [rejected, solution(1, 0)],
        np.zeros(2),
        cfg,
        [],
        1,
        None,
        locked_indices={1},
    )
    if operation == "camera" and kind == "ordinary":
        result = await call
        assert len(result) == 2 and all(row["passed"] for row in result)
    else:
        with pytest.raises(type(primary)) as caught:
            await call
        assert caught.value is primary
        assert [row["index"] for row in ctx.metrics["jik_per_target"]] == [0]
        assert ctx.metrics["jik_interrupted_target_index"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("passed", [False, True])
@pytest.mark.parametrize("encoder_error", [False, True])
async def test_actual_jik_finalization_keeps_gate_under_metric_sink_failure(monkeypatch, passed, encoder_error):
    from pxr import Usd

    robot = Robot()
    robot.get_joint_position_limits = lambda: (np.zeros(2), np.ones(2))
    ctx = Context(robot)
    failures = []
    ctx.fail = failures.append
    ctx.skip = lambda message: pytest.fail("unexpected skip: " + message)
    primary = OSError("required encoder session error")

    def encode(*args, **kwargs):
        if encoder_error:
            raise primary
        return None

    ctx.encode_video = encode
    original = ctx.add_metric

    def metric(name, value):
        if name == "jik_targets_generated":
            raise OSError("optional final metric sink")
        original(name, value)

    ctx.add_metric = metric
    monkeypatch.setattr(phase, "is_standalone_gripper", lambda *args: False)
    monkeypatch.setattr(phase, "discover_end_effector_link", lambda **kwargs: "/Robot/tip")
    monkeypatch.setattr(phase, "resolve_live_end_effector_link", lambda *args: "/Robot/tip")

    async def home(*args):
        return np.zeros(2)

    monkeypatch.setattr(phase, "_settle_and_snapshot", home)
    monkeypatch.setattr(phase, "JacobianIKSolver", lambda **kwargs: object())
    monkeypatch.setattr(phase, "_capture_home_orientation", lambda *args: [1, 0, 0, 0])
    monkeypatch.setattr(phase, "estimate_robot_reach", lambda *args: 1.0)

    async def targets(**kwargs):
        return [SimpleNamespace(is_reachable=True, position=np.zeros(3))], 1.0

    monkeypatch.setattr(phase, "_generate_fk_targets", targets)

    async def solutions(**kwargs):
        return [object()]

    monkeypatch.setattr(phase, "_precompute_solutions", solutions)

    async def playback(**kwargs):
        kwargs["capture_frames"].append("frame.png")
        return [{"index": 0, "name": "target", "is_reachable": True, "passed": passed, "solver_success": True}]

    monkeypatch.setattr(phase, "_run_motion_for_solutions", playback)
    call = phase.run_jacobian_ik(
        ctx,
        robot,
        {"stage": Usd.Stage.CreateInMemory()},
        {"num_targets": 1, "out_of_reach_count": 0, "show_target_spheres": False},
    )
    if encoder_error:
        with pytest.raises(OSError) as caught:
            await call
        assert caught.value is primary
    else:
        await call
        assert bool(failures) is (not passed)
        assert ctx.metrics["jik_pass_rate"] == (1.0 if passed else 0.0)
        assert ctx.metrics["jik_ee_link"] == "/Robot/tip"


@pytest.mark.parametrize("sink", ["metric", "warning"])
def test_seed_diagnostics_do_not_swallow_unsafe_evidence(sink):
    from simready.evaluate.core.output_layout import UnsafeEvidencePathError

    primary = UnsafeEvidencePathError("unsafe seed diagnostics")

    def metric(*args):
        raise primary if sink == "metric" else OSError("ordinary sink")

    def warning(*args):
        raise primary

    ctx = SimpleNamespace(add_metric=metric, warn=warning)
    with pytest.raises(UnsafeEvidencePathError) as caught:
        phase._record_seed_attempts(ctx, [], 0)
    assert caught.value is primary

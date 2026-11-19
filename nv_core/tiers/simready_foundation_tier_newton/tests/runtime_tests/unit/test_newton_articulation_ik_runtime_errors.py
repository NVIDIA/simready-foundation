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

"""Native IK execution failures must not become geometric rejection evidence."""

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import ik_target_reach as phase


class _RuntimeRobot:
    def __init__(self):
        self.dof_names = ["a", "b", "c"]
        self.dof_count = 3
        self.positions = np.array([0.4, 0.5, 0.6])
        self.writes = []
        self.commands = []
        self.restore_failure = None

    def get_joint_positions(self):
        return self.positions.copy()

    def get_joint_velocities(self):
        return np.zeros(3)

    def set_joint_positions(self, value):
        self.writes.append(np.asarray(value).copy())
        if self.restore_failure is not None and len(self.writes) > 1:
            raise self.restore_failure
        self.positions = np.asarray(value).copy()

    def set_joint_position_targets(self, value):
        self.commands.append(np.asarray(value).copy())

    def set_joint_velocities(self, value):
        pass


class _RuntimeContext:
    def __init__(self):
        self.metrics = {}
        self.warnings = []
        self.failed = False
        self.ticks = 0
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)

    def step(self, *args):
        pass

    async def step_one(self):
        self.ticks += 1

    async def capture_frame(self, **kwargs):
        return None

    def log(self, *args):
        pass

    def warn(self, message):
        self.warnings.append(message)

    def add_metric(self, name, value):
        self.metrics[name] = value

    def fail(self, message):
        self.failed = True

    def skip(self, message):
        pytest.fail("Execution failures must not be skipped: " + message)


def _native_case(stage=None, success=True):
    robot = _RuntimeRobot()
    context = _RuntimeContext()
    fault = RuntimeError("native solver crashed: " + str(stage))
    target = SimpleNamespace(index=1, is_reachable=False, position=np.ones(3))
    action_calls = []

    def maybe_fail(point, value):
        if stage == point:
            raise fault
        return value

    def make_action(values, velocities):
        action_calls.append(values)
        return maybe_fail(
            "action",
            None if stage == "missing_action" else SimpleNamespace(joint_positions=values, joint_indices=None),
        )

    subset = SimpleNamespace(
        get_joint_positions=lambda: maybe_fail("warm_start", robot.get_joint_positions()),
        make_articulation_action=make_action,
    )

    def inverse(*args):
        return maybe_fail("solve", (np.array([0.1, 0.2, 0.3]), success))

    kinematics = SimpleNamespace(
        compute_inverse_kinematics=inverse,
        compute_forward_kinematics=lambda *args, **kwargs: maybe_fail(
            "pose", (np.ones(3), np.array([1.0, 0.0, 0.0, 0.0]))
        ),
    )
    articulation = SimpleNamespace(
        get_joints_subset=lambda: maybe_fail("subset", subset),
        get_kinematics_solver=lambda: maybe_fail("solver", kinematics),
        get_end_effector_frame=lambda: maybe_fail("frame", "tip"),
    )
    return context, robot, articulation, target, fault, action_calls


async def _run_phase_with_native_helper(monkeypatch, context, robot, articulation, target):
    async def setup(*args):
        return {"art_ik": articulation, "targets": [target]}

    async def inputs(*args):
        return {}

    # Only native environment discovery is substituted. Precompute, warm start,
    # solver invocation, action construction, restoration and phase runner are real.
    monkeypatch.setattr(phase, "_setup_ik_phase", setup)
    monkeypatch.setattr(phase, "_gather_motion_inputs", inputs)
    await phase.run_ik_target_reach(context, robot, {}, {"show_target_spheres": False})


@pytest.mark.asyncio
@pytest.mark.parametrize("reachable", [False, True])
@pytest.mark.parametrize("stage", ["subset", "warm_start", "solver", "frame", "solve", "action", "pose"])
@pytest.mark.parametrize("boundary", ["precompute", "runner"])
async def test_native_ik_execution_error_never_counts_as_target_rejection(monkeypatch, reachable, stage, boundary):
    context, robot, articulation, target, fault, _ = _native_case(stage)
    target.is_reachable = reachable
    reference = robot.positions.copy()

    with pytest.raises(phase.RequiredReadbackError, match="IK runtime error") as raised:
        if boundary == "precompute":
            await phase._precompute_ik_solutions(context, robot, articulation, [target], 0.01, 0.1, reference)
        else:
            await _run_phase_with_native_helper(monkeypatch, context, robot, articulation, target)

    assert raised.value.__cause__ is fault
    np.testing.assert_array_equal(robot.writes[-1], reference)
    np.testing.assert_array_equal(robot.positions, reference)
    assert "ik_out_of_reach_correctly_failed" not in context.metrics
    assert not any("correctly rejected" in message for message in context.warnings)


@pytest.mark.asyncio
@pytest.mark.parametrize("reachable", [False, True])
@pytest.mark.parametrize("success", [False, np.bool_(False)])
async def test_explicit_native_false_preserves_geometric_rejection_and_restores_reference(reachable, success):
    context, robot, articulation, target, _, action_calls = _native_case(success=success)
    target.is_reachable = reachable
    reference = robot.positions.copy()

    solutions, metrics = await phase._precompute_ik_solutions(
        context, robot, articulation, [target], 0.01, 0.1, reference
    )
    result = await phase._execute_one_target(context, robot, articulation, solutions[0], [], 1, {}, {}, {})

    assert result["ok"] is (not reachable)
    assert result["message"] == "ik_failed"
    assert not result["solved"] and not result["reached"]
    assert metrics["out_of_reach_correctly_failed"] == (0 if reachable else 1)
    assert metrics["solve_failed_reachable"] == (1 if reachable else 0)
    assert action_calls == []
    np.testing.assert_array_equal(robot.positions, reference)
    np.testing.assert_array_equal(robot.writes[-1], reference)


@pytest.mark.asyncio
@pytest.mark.parametrize("reachable", [False, True])
@pytest.mark.parametrize("success", [False, np.bool_(False)])
async def test_runner_preserves_explicit_native_false_without_action_construction(monkeypatch, reachable, success):
    context, robot, articulation, target, _, action_calls = _native_case(success=success)
    target.is_reachable = reachable
    reference = robot.positions.copy()

    await _run_phase_with_native_helper(monkeypatch, context, robot, articulation, target)

    assert context.failed is reachable
    assert context.metrics["ik_out_of_reach_correctly_failed"] == (0 if reachable else 1)
    assert context.metrics["ik_solve_failed_reachable"] == (1 if reachable else 0)
    assert action_calls == []
    np.testing.assert_array_equal(robot.positions, reference)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "success", [None, 0, 1, 0.0, float("nan"), float("inf"), "False", "True", [], np.array([False]), np.array(False)]
)
@pytest.mark.parametrize("reachable", [False, True])
async def test_invalid_solver_success_status_is_not_geometric_rejection(monkeypatch, success, reachable):
    context, robot, articulation, target, _, action_calls = _native_case(success=success)
    target.is_reachable = reachable
    reference = robot.positions.copy()

    with pytest.raises(phase.RequiredReadbackError, match="success status must be a boolean"):
        await _run_phase_with_native_helper(monkeypatch, context, robot, articulation, target)

    assert action_calls == []
    np.testing.assert_array_equal(robot.positions, reference)
    assert "ik_out_of_reach_correctly_failed" not in context.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("reachable", [False, True])
async def test_successful_native_solver_requires_an_articulation_action(reachable):
    context, robot, articulation, target, _, _ = _native_case("missing_action")
    target.is_reachable = reachable
    reference = robot.positions.copy()
    with pytest.raises(phase.RequiredReadbackError, match="no articulation action"):
        await phase._precompute_ik_solutions(context, robot, articulation, [target], 0.01, 0.1, reference)
    np.testing.assert_array_equal(robot.positions, reference)


@pytest.mark.asyncio
async def test_unexpected_precompute_helper_exception_propagates_with_reference_restoration(monkeypatch):
    context, robot, articulation, target, fault, _ = _native_case()
    reference = robot.positions.copy()

    def crash(*args):
        raise fault

    monkeypatch.setattr(phase, "_compute_inverse_kinematics_host", crash)
    with pytest.raises(phase.RequiredReadbackError, match="solver execution failed") as raised:
        await phase._precompute_ik_solutions(context, robot, articulation, [target], 0.01, 0.1, reference)
    assert raised.value.__cause__ is fault
    np.testing.assert_array_equal(robot.positions, reference)


@pytest.mark.asyncio
async def test_native_failure_remains_primary_when_reference_restoration_also_fails():
    context, robot, articulation, target, fault, _ = _native_case("solve")
    robot.restore_failure = RuntimeError("reference restoration unavailable")
    with pytest.raises(phase.RequiredReadbackError) as raised:
        await phase._precompute_ik_solutions(context, robot, articulation, [target], 0.01, 0.1, robot.positions.copy())
    assert raised.value.__cause__ is fault
    assert any("restoration also failed" in note for note in raised.value.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["playback", "post_hold"])
async def test_unexpected_position_error_exception_is_not_timeout_or_stale_pass(monkeypatch, boundary):
    context, robot, articulation, target, fault, _ = _native_case()

    def crash(*args):
        raise fault

    monkeypatch.setattr(phase, "_compute_target_error", crash)
    with pytest.raises(phase.RequiredReadbackError, match="position error failed") as raised:
        if boundary == "playback":
            await phase._interpolate_ik_motion(
                context, robot, articulation, target, np.ones(3), 1, [], 1, 0.01, None, None, 10.0, "target_1"
            )
        else:
            await phase._resolve_actual_error(
                context,
                robot,
                articulation,
                target,
                np.ones(3),
                "target_1",
                True,
                0.0,
                1,
                [],
                1,
                {"motion_timeouts": 0},
                {"hold_frames": 1, "update_interval_frames": 1, "physics_fps": 240.0},
            )
    assert raised.value.__cause__ is fault


@pytest.mark.parametrize("position", [[1.0, float("nan"), 1.0], [1.0, float("inf"), 1.0], ["1", "1", "1"], [True] * 3])
def test_invalid_target_error_evidence_is_runtime_failure(position):
    _, _, articulation, target, _, _ = _native_case()
    target.position = position
    with pytest.raises(phase.RequiredReadbackError):
        phase._compute_target_error(articulation, target)


def test_large_finite_position_error_avoids_square_overflow():
    _, _, articulation, target, _, _ = _native_case()
    target.position = np.array([1e200, 1.0, 1.0])
    assert phase._compute_target_error(articulation, target) == pytest.approx(1e200)

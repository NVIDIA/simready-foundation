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

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import jacobian_ik as phase
from simready.foundation.tier_newton.runtime_tests.articulation_phases.ik_targets import IKTarget
from simready.foundation.tier_newton.runtime_tests.fet022_driven_joints import (
    jacobian_ik as registration,
)


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


class Context:
    def __init__(self, clock, tick_seconds=0.0):
        self.clock, self.tick_seconds = clock, tick_seconds
        self.ticks, self.metrics, self.messages = 0, {}, []

    async def step_one(self):
        self.ticks += 1
        self.clock.value += self.tick_seconds

    def step(self, message):
        self.messages.append(message)

    log = warn = step

    def add_metric(self, name, value):
        self.metrics[name] = value


class Robot:
    dof_names = ["arm"]
    dof_count = 1

    def __init__(self):
        self.positions = np.array([0.0])
        self.commands = []

    def get_joint_positions(self):
        return self.positions.copy()

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def set_joint_positions(self, values):
        self.positions[:] = values
        self.commands.append(self.positions.copy())

    def set_joint_position_targets(self, values):
        pass

    def set_joint_velocities(self, values):
        pass

    def get_link_world_transforms(self, paths):
        return {paths[0]: (np.array([self.positions[0], 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))}


def target(index=0, reachable=True):
    return IKTarget(np.array([0.4, 0.0, 0.0]), reachable, index, np.array([1.0, 0.0, 0.0, 0.0]))


def failed_result():
    return SimpleNamespace(
        success=False,
        iterations=1,
        converged_joints=np.array([0.3]),
        final_position=np.zeros(3),
        final_orientation=np.array([1.0, 0.0, 0.0, 0.0]),
        final_pos_error=0.4,
        final_orient_error_deg=0.0,
    )


INVALID_BUDGETS = [
    True,
    False,
    np.bool_(True),
    "900",
    None,
    {},
    [],
    0,
    -1,
    float("nan"),
    float("inf"),
    -float("inf"),
    1800.01,
]


@pytest.mark.parametrize("value", INVALID_BUDGETS)
@pytest.mark.asyncio
async def test_invalid_budget_rejected_before_phase_scene_access(monkeypatch, value):
    async def forbidden(*args):
        pytest.fail("invalid search configuration must not inspect or step the scene")

    monkeypatch.setattr(phase, "_run_jacobian_ik_impl", forbidden)
    with pytest.raises(ValueError, match="max_search_wall_seconds"):
        await phase.run_jacobian_ik(object(), object(), {}, {"max_search_wall_seconds": value})


@pytest.mark.parametrize("value", INVALID_BUDGETS)
@pytest.mark.asyncio
async def test_registration_rejects_invalid_budget_before_engine_or_setup(value):
    with pytest.raises(ValueError, match="max_search_wall_seconds"):
        await registration.run_jacobian_ik(SimpleNamespace(config={"max_search_wall_seconds": value}))


def test_declared_allowances_and_response_criteria_are_exact():
    defaults, metadata = phase.get_defaults(), registration.JACOBIAN_IK_KWARGS
    assert defaults["max_search_wall_seconds"] == 1800.0
    assert phase.validate_search_budget({}) == 1800.0
    assert phase.validate_search_budget({"max_search_wall_seconds": 0.01}) == 0.01
    assert metadata["max_duration"] == 2400
    assert metadata["version"] == "1.4.12"
    assert (defaults["num_targets"], defaults["out_of_reach_count"], defaults["max_solver_iterations"]) == (5, 2, 150)
    assert (defaults["position_tolerance"], defaults["orientation_tolerance_deg"], defaults["min_pass_rate"]) == (
        0.05,
        10.0,
        0.40,
    )


@pytest.mark.asyncio
async def test_elapsed_guard_refuses_new_tick():
    clock = Clock()
    ctx, search = Context(clock), None
    search = phase._JIKSearchContext(ctx, 1.0, clock)
    clock.value = 1.0
    with pytest.raises(phase.JIKSearchBudgetExceeded):
        await search.step_one()
    assert ctx.ticks == search.ticks_requested == search.ticks_completed == 0


@pytest.mark.asyncio
async def test_completed_existing_tick_is_counted_before_late_budget_error():
    clock = Clock()
    ctx = Context(clock, 1.1)
    search = phase._JIKSearchContext(ctx, 1.0, clock)
    with pytest.raises(phase.JIKSearchBudgetExceeded):
        await search.step_one()
    assert ctx.ticks == search.ticks_requested == search.ticks_completed == 1


@pytest.mark.parametrize(
    "primary", [OSError("physics failed"), asyncio.CancelledError(), KeyboardInterrupt(), SystemExit(2)]
)
@pytest.mark.asyncio
async def test_actual_tick_failure_or_interrupt_beats_late_clock(primary):
    clock = Clock()
    ctx = Context(clock)

    async def fail():
        clock.value = 2.0
        raise primary

    ctx.step_one = fail
    search = phase._JIKSearchContext(ctx, 1.0, clock)
    with pytest.raises(type(primary)) as caught:
        await search.step_one()
    assert caught.value is primary
    assert search.ticks_requested == 1 and search.ticks_completed == 0


@pytest.mark.asyncio
async def test_target_boundary_budget_error_restores_home_without_new_ticks():
    clock, robot = Clock(), Robot()
    ctx = Context(clock)
    search = phase._JIKSearchContext(ctx, 1.0, clock)
    robot.positions[:] = 0.7
    clock.value = 1.1
    with pytest.raises(phase.JIKSearchBudgetExceeded, match="last progress: JIK precompute"):
        await phase._precompute_solutions(
            search, robot, SimpleNamespace(_locked=set()), [target()], np.zeros(1), None, 0.05, 0.1, 150
        )
    assert ctx.ticks == 0 and robot.positions.tolist() == [0.0]
    assert search.solver_attempts_started == 0


@pytest.mark.asyncio
async def test_seed_boundary_expiry_does_not_start_another_attempt(monkeypatch):
    clock, robot = Clock(), Robot()
    ctx = Context(clock)
    original_step = ctx.step

    def expire_seed(message):
        original_step(message)
        if message.startswith("JIK target_"):
            clock.value = 1.1

    ctx.step = expire_seed
    search = phase._JIKSearchContext(ctx, 1.0, clock)

    async def forbidden(*args):
        pytest.fail("expired seed must not start solver execution")

    monkeypatch.setattr(phase, "_solve_target", forbidden)
    with pytest.raises(phase.JIKSearchBudgetExceeded, match="seed=previous_success"):
        await phase._precompute_solutions(
            search, robot, SimpleNamespace(_locked=set()), [target()], np.zeros(1), None, 0.05, 0.1, 150
        )
    assert ctx.ticks == 3 and search.solver_attempts_started == 0
    assert robot.positions.tolist() == [0.0]


@pytest.mark.asyncio
async def test_actual_solver_deadline_is_not_wrapped_as_rejected_negative_target():
    clock, robot = Clock(), Robot()
    ctx = Context(clock, 0.2)
    search = phase._JIKSearchContext(ctx, 0.75, clock)
    solver = phase.JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(phase.JIKSearchBudgetExceeded) as caught:
        await phase._precompute_solutions(
            search, robot, solver, [target(reachable=False)], np.zeros(1), None, 0.05, 0.1, 150
        )
    assert "coverage is incomplete" in str(caught.value)
    assert search.solver_attempts_started == 1 and search.solver_attempts_completed == 0
    assert robot.positions.tolist() == [0.0]
    assert not any("correctly rejected" in row for row in ctx.messages)


@pytest.mark.asyncio
async def test_all_positive_and_negative_targets_retain_search_and_iteration_cap(monkeypatch):
    clock, robot = Clock(), Robot()
    ctx, calls = Context(clock), []
    search = phase._JIKSearchContext(ctx, 1.0, clock)

    async def solve(ctx, solver, goal, home_orientation, pos_tol, orient_tol_rad, max_iterations):
        calls.append((goal.index, goal.is_reachable, pos_tol, orient_tol_rad, max_iterations))
        return failed_result()

    monkeypatch.setattr(phase, "_solve_target", solve)
    records = await phase._precompute_solutions(
        search, robot, SimpleNamespace(_locked=set()), [target(), target(1, False)], np.zeros(1), None, 0.05, 0.1, 150
    )
    assert [row["target"].is_reachable for row in records] == [True, False]
    assert {row[0] for row in calls} == {0, 1}
    assert any(row[1] is False for row in calls)
    assert all(row[2:] == (0.05, 0.1, 150) for row in calls)
    assert all(sum(row[0] == index for row in calls) <= 4 for index in (0, 1))
    assert search.solver_attempts_completed == len(calls)
    assert search.solver_iterations_completed == len(calls)


@pytest.mark.asyncio
async def test_native_typed_readback_cause_is_not_rewrapped_by_probe_propagation():
    primary = phase.RequiredReadbackError("original required native state failed")
    solver = phase.JacobianIKSolver(Robot(), "/Robot/tool")

    async def failed_step():
        raise primary

    with pytest.raises(phase.RequiredReadbackError) as caught:
        await solver._propagate_probe(failed_step)
    assert caught.value is primary


@pytest.mark.asyncio
async def test_timing_is_observational_and_playback_does_not_consume_search_budget():
    clock = Clock()
    ctx = Context(clock, 0.2)
    search = phase._JIKSearchContext(ctx, 1.0, clock)
    search.step("target_0 seed=home")
    await search.step_one()
    search.begin_solver()
    search.finish_solver(failed_result())
    search.finish("search_completed")
    clock.value = 100.0
    await search.step_one()
    phase._record_search_timing(ctx, search)
    row = ctx.metrics["jik_search_timing"]
    assert ctx.ticks == 2 and row["search_ticks_completed"] == 1
    assert row["wall_elapsed_seconds"] == pytest.approx(0.2)
    assert row["wall_allowance_seconds"] == 1.0 and row["whole_test_ceiling_seconds"] == 2400
    assert row["solver_attempts_started"] == row["solver_attempts_completed"] == row["solver_iterations_completed"] == 1
    assert row["stop_reason"] == "search_completed"
    assert row["last_progress"] == "target_0 seed=home"


@pytest.mark.asyncio
@pytest.mark.parametrize("primary", [None, OSError("solver failed"), asyncio.CancelledError()])
async def test_optional_timing_sink_failure_preserves_phase_outcome(monkeypatch, primary):
    clock = Clock()
    ctx = Context(clock)

    def unavailable(*args):
        raise OSError("metric sink unavailable")

    ctx.add_metric = unavailable

    async def implementation(search, *args):
        if primary is not None:
            raise primary
        search.finish("search_completed")

    monkeypatch.setattr(phase, "_run_jacobian_ik_impl", implementation)
    if primary is None:
        await phase.run_jacobian_ik(ctx, object(), {}, {})
    else:
        with pytest.raises(type(primary)) as caught:
            await phase.run_jacobian_ik(ctx, object(), {}, {})
        assert caught.value is primary
    assert any("execution outcome unchanged" in row for row in ctx.messages)


def test_optional_interrupt_does_not_replace_an_existing_primary_failure():
    clock = Clock()
    primary = OSError("original solver cause")

    def interrupted(*args):
        raise KeyboardInterrupt()

    ctx = SimpleNamespace(add_metric=interrupted, warn=interrupted)
    search = phase._JIKSearchContext(ctx, 1.0, clock)
    phase._record_search_timing(ctx, search, primary)
    assert any("search timing unavailable" in note for note in primary.__notes__)

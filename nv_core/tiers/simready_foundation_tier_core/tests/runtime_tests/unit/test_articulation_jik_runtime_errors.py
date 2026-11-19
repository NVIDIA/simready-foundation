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
"""JIK runtime failures cannot become evidence of correctly rejected targets."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import jacobian_ik as phase
from simready.foundation.tier_core.runtime_tests.articulation_phases import jik_solver
from simready.foundation.tier_core.runtime_tests.articulation_phases.ik_targets import IKTarget
from simready.foundation.tier_core.runtime_tests.articulation_phases.jik_solver import JacobianIKSolver
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)


class _Robot:
    dof_names = ["joint"]
    dof_count = 1

    def __init__(self):
        self.positions = np.array([0.2])
        self.commands = []

    def get_joint_positions(self):
        return self.positions.copy()

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def set_joint_positions(self, values):
        self.positions[:] = values
        self.commands.append(np.asarray(values).copy())

    def set_joint_position_targets(self, values):
        pass

    def set_joint_velocities(self, values):
        pass

    def get_link_world_transforms(self, paths):
        return {paths[0]: (np.array([self.positions[0], 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))}


class _Context:
    def __init__(self):
        self.ticks = 0
        self.messages = []
        self.metrics = {}

    async def step_one(self):
        self.ticks += 1

    def step(self, message):
        self.messages.append(message)

    log = step
    warn = step

    def add_metric(self, name, value):
        self.metrics[name] = value


def _target():
    return IKTarget(
        position=np.array([10.0, 0.0, 0.0]), is_reachable=False, index=0, orientation=np.array([1.0, 0.0, 0.0, 0.0])
    )


def _result(success=False):
    return SimpleNamespace(
        success=success,
        iterations=1,
        final_position=np.array([0.2, 0.0, 0.0]),
        final_orientation=np.array([1.0, 0.0, 0.0, 0.0]),
        final_pos_error=9.8,
        final_orient_error_deg=0.0,
        converged_joints=np.array([0.2]),
    )


def _solver_with_result(result):
    async def solve(**kwargs):
        return result

    return SimpleNamespace(dof_count=1, solve=solve)


async def _precompute(ctx, robot, solver):
    return await phase._precompute_solutions(
        ctx, robot, solver, [_target()], np.array([0.2]), np.array([1.0, 0.0, 0.0, 0.0]), 0.02, 0.1, 2
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception", [OSError("backend unavailable"), ValueError("bad computation"), OverflowError("DLS")]
)
async def test_solver_exception_cannot_be_correctly_rejected_out_of_reach_target(exception):
    robot = _Robot()
    ctx = _Context()

    async def solve(**kwargs):
        robot.set_joint_positions([0.8])
        raise exception

    with pytest.raises(RequiredReadbackError, match="required solver execution") as caught:
        await _precompute(ctx, robot, SimpleNamespace(dof_count=1, solve=solve))
    assert caught.value.__cause__ is exception
    assert np.array_equal(robot.positions, [0.2])
    assert ctx.ticks == 3
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_actual_solver_finite_damping_overflow_is_runtime_error_not_nonconvergence():
    robot, ctx = _Robot(), _Context()
    solver = JacobianIKSolver(robot, "/Robot/tool", damping_lambda=1.0e308)
    with pytest.raises(RequiredReadbackError, match="required solver execution") as caught:
        await _precompute(ctx, robot, solver)
    assert isinstance(caught.value.__cause__, OverflowError)
    assert np.array_equal(robot.positions, [0.2])
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_actual_solver_failed_linear_solve_and_pseudoinverse_are_runtime_error(monkeypatch):
    robot, ctx = _Robot(), _Context()
    primary = np.linalg.LinAlgError("SVD did not converge")

    def fail(*args, **kwargs):
        raise primary

    monkeypatch.setattr(np.linalg, "solve", fail)
    monkeypatch.setattr(np.linalg, "pinv", fail)
    solver = JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(RequiredReadbackError, match="required solver execution") as caught:
        await _precompute(ctx, robot, solver)
    assert caught.value.__cause__ is primary
    assert np.array_equal(robot.positions, [0.2])
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_actual_solver_singular_solve_with_numeric_pseudoinverse_retains_valid_response(monkeypatch):
    robot, ctx = _Robot(), _Context()
    original_pinv = np.linalg.pinv
    fallback_calls = []

    def singular(*args, **kwargs):
        raise np.linalg.LinAlgError("Singular matrix")

    def numeric_pinv(matrix):
        fallback_calls.append(matrix.copy())
        return original_pinv(matrix)

    monkeypatch.setattr(np.linalg, "solve", singular)
    monkeypatch.setattr(np.linalg, "pinv", numeric_pinv)
    solver = JacobianIKSolver(robot, "/Robot/tool")
    records = await _precompute(ctx, robot, solver)
    assert fallback_calls
    assert records[0]["solver_success"] is False
    assert np.isfinite(records[0]["pos_err"])
    assert np.isfinite(records[0]["solution"]).all()
    outcomes = await phase._run_motion_for_solutions(
        ctx, robot, solver, {}, records, np.array([0.2]), phase.get_defaults(), [], 1, None
    )
    assert outcomes[0]["passed"] is True
    assert np.array_equal(robot.positions, [0.2])


@pytest.mark.asyncio
async def test_actual_solver_nonfinite_pseudoinverse_step_is_not_clamped_into_rejection(monkeypatch):
    robot, ctx = _Robot(), _Context()
    monkeypatch.setattr(
        robot,
        "get_link_world_transforms",
        lambda paths: {paths[0]: (np.array([robot.positions[0] * 1.0e-308, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))},
    )
    solver = JacobianIKSolver(robot, "/Robot/tool", damping_lambda=0.0)
    # A finite, tiny Jacobian makes the numeric pseudoinverse overflow when
    # multiplied by the target error. Clamping its infinite step to a legal
    # joint stop must not turn this computation failure into nonconvergence.
    with pytest.raises(RequiredReadbackError, match="required solver execution") as caught:
        await _precompute(ctx, robot, solver)
    assert isinstance(caught.value.__cause__, FloatingPointError)
    assert np.array_equal(robot.positions, [0.2])
    assert all(np.isfinite(command).all() for command in robot.commands)
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_actual_solver_finite_large_jacobian_intermediate_overflow_is_runtime_error(monkeypatch):
    robot, ctx = _Robot(), _Context()
    monkeypatch.setattr(
        robot,
        "get_link_world_transforms",
        lambda paths: {
            paths[0]: (np.array([(robot.positions[0] - 0.2) * 1.0e200, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))
        },
    )
    solver = JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(RequiredReadbackError, match="required solver execution") as caught:
        await _precompute(ctx, robot, solver)
    assert isinstance(caught.value.__cause__, FloatingPointError)
    assert np.array_equal(robot.positions, [0.2])
    assert all(np.isfinite(command).all() for command in robot.commands)
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_actual_solver_finite_joint_and_step_sum_overflow_cannot_be_clamped(monkeypatch):
    robot, ctx = _Robot(), _Context()
    home = np.array([1.0e308])
    robot.positions[:] = home
    monkeypatch.setattr(robot, "get_joint_position_limits", lambda: (np.array([-1.0e308]), np.array([1.0e308])))
    monkeypatch.setattr(
        robot,
        "get_link_world_transforms",
        lambda paths: {paths[0]: (np.array([0.2, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))},
    )
    monkeypatch.setattr(jik_solver, "_compute_dls_step", lambda *args: np.array([1.0e308]))
    solver = JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(RequiredReadbackError, match="required solver execution") as caught:
        await phase._precompute_solutions(ctx, robot, solver, [_target()], home, None, 0.02, 0.1, 2)
    assert isinstance(caught.value.__cause__, FloatingPointError)
    assert np.array_equal(robot.positions, home)
    assert all(np.isfinite(command).all() for command in robot.commands)
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_actual_solver_large_finite_step_still_clamps_to_legal_joint_limits(monkeypatch):
    robot, ctx = _Robot(), _Context()
    monkeypatch.setattr(jik_solver, "_compute_dls_step", lambda *args: np.array([100.0]))
    solver = JacobianIKSolver(robot, "/Robot/tool")
    records = await _precompute(ctx, robot, solver)
    assert records[0]["solver_success"] is False
    assert np.isfinite(records[0]["pos_err"])
    assert all(np.isfinite(command).all() for command in robot.commands)
    assert all(-1.0 <= command[0] <= 1.0 for command in robot.commands)
    assert any(command[0] == 1.0 for command in robot.commands)
    assert np.array_equal(robot.positions, [0.2])


@pytest.mark.parametrize("rows", [2, 3, 6])
def test_dls_helper_keeps_generic_numeric_matrix_shape(rows):
    jacobian = np.eye(rows, 2)
    delta = jik_solver._compute_dls_step(jacobian, np.ones(rows), 0.05)
    assert delta.shape == (2,)
    assert np.isfinite(delta).all()


@pytest.mark.parametrize(
    ("jacobian", "error", "damping"),
    [
        ([[1.0], [np.nan]], [1.0, 0.0], 0.05),
        ([[1.0], [True]], [1.0, 0.0], 0.05),
        ([[complex(1.0, 1.0)]], [1.0], 0.05),
        ([[1.0]], [np.inf], 0.05),
        ([[1.0]], [False], 0.05),
        ([[1.0]], [1.0, 0.0], 0.05),
        ([[1.0]], [1.0], True),
        ([[1.0]], [1.0], -0.1),
        ([[1.0]], [1.0], np.inf),
    ],
)
def test_dls_helper_requires_finite_real_inputs(jacobian, error, damping):
    with pytest.raises((ValueError, RequiredReadbackError)):
        jik_solver._compute_dls_step(jacobian, error, damping)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_tick", [1, 4])
async def test_actual_solver_or_initial_probe_step_failure_preserves_cause_and_home(failure_tick):
    robot, ctx = _Robot(), _Context()
    primary = OSError("physics step failed")

    async def step():
        ctx.ticks += 1
        if ctx.ticks == failure_tick:
            raise primary

    ctx.step_one = step
    solver = JacobianIKSolver(robot, "/Robot/tool")
    with pytest.raises(RequiredReadbackError, match="probe.*propagation") as caught:
        await _precompute(ctx, robot, solver)
    assert caught.value.__cause__ is primary
    assert np.array_equal(robot.positions, [0.2])
    assert ctx.ticks == failure_tick


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [False, np.bool_(False)])
async def test_only_well_formed_explicit_false_can_correctly_reject_target(success):
    robot, ctx = _Robot(), _Context()
    solver = _solver_with_result(_result(success))
    records = await _precompute(ctx, robot, solver)
    outcomes = await phase._run_motion_for_solutions(
        ctx, robot, solver, {}, records, np.array([0.2]), phase.get_defaults(), [], 1, None
    )
    assert outcomes[0]["passed"] is True
    assert outcomes[0]["solver_success"] is False
    assert outcomes[0]["pos_err"] == pytest.approx(9.8)
    assert np.array_equal(robot.positions, [0.2])


@pytest.mark.asyncio
async def test_actual_solver_well_formed_nonconvergence_remains_correct_rejection():
    robot, ctx = _Robot(), _Context()
    solver = JacobianIKSolver(robot, "/Robot/tool")
    records = await _precompute(ctx, robot, solver)
    assert records[0]["solver_success"] is False
    assert np.isfinite(records[0]["pos_err"])
    outcomes = await phase._run_motion_for_solutions(
        ctx, robot, solver, {}, records, np.array([0.2]), phase.get_defaults(), [], 1, None
    )
    assert outcomes[0]["passed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [True, np.bool_(True)])
async def test_well_formed_explicit_success_is_preserved(success):
    result = _result(success)
    returned = await phase._solve_target(_Context(), _solver_with_result(result), _target(), None, 0.02, 0.1, 2)
    assert returned is result


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [None, 0, 1, "False", np.int64(0), np.array([False])])
async def test_untyped_success_flag_is_not_rejection_evidence(success):
    with pytest.raises(RequiredReadbackError, match="solver result"):
        await _precompute(_Context(), _Robot(), _solver_with_result(_result(success)))


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [None, SimpleNamespace(success=False)])
async def test_missing_solver_result_is_not_rejection_evidence(result):
    with pytest.raises(RequiredReadbackError, match="solver result"):
        await _precompute(_Context(), _Robot(), _solver_with_result(result))


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [False, True])
@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("converged_joints", None),
        ("converged_joints", []),
        ("converged_joints", [0.2, 0.3]),
        ("converged_joints", [True]),
        ("converged_joints", [np.nan]),
        ("converged_joints", [complex(0.2, 1.0)]),
        ("final_position", [0.0, 0.0]),
        ("final_position", [0.0, np.inf, 0.0]),
        ("final_position", [0.0, False, 0.0]),
        ("final_orientation", [0.0, 0.0, 0.0, 0.0]),
        ("final_orientation", [1.0, 0.0, np.nan, 0.0]),
        ("final_orientation", [1.0, 0.0, False, 0.0]),
        ("final_orientation", [1.0, 0.0, 0.0]),
        ("iterations", True),
        ("iterations", -1),
        ("iterations", 1.5),
        ("iterations", 3),
        ("final_pos_error", np.nan),
        ("final_pos_error", np.inf),
        ("final_pos_error", -0.1),
        ("final_pos_error", True),
        ("final_pos_error", "0.1"),
        ("final_orient_error_deg", np.nan),
        ("final_orient_error_deg", np.inf),
        ("final_orient_error_deg", -1.0),
        ("final_orient_error_deg", np.bool_(False)),
    ],
)
async def test_malformed_solver_solution_pose_or_error_cannot_create_target_verdict(success, field, invalid):
    result = _result(success)
    setattr(result, field, invalid)
    robot, ctx = _Robot(), _Context()
    with pytest.raises(RequiredReadbackError):
        await _precompute(ctx, robot, _solver_with_result(result))
    assert np.array_equal(robot.positions, [0.2])
    assert not any("correctly rejected" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_solver_cancellation_remains_cancellation_and_restores_home_without_extra_ticks():
    robot, ctx = _Robot(), _Context()
    primary = asyncio.CancelledError()

    async def solve(**kwargs):
        robot.set_joint_positions([0.8])
        raise primary

    with pytest.raises(asyncio.CancelledError) as caught:
        await _precompute(ctx, robot, SimpleNamespace(dof_count=1, solve=solve))
    assert caught.value is primary
    assert np.array_equal(robot.positions, [0.2])
    assert ctx.ticks == 3


@pytest.mark.asyncio
async def test_home_restoration_failure_does_not_replace_solver_error(monkeypatch):
    robot, ctx = _Robot(), _Context()
    primary = OSError("solver backend failed")

    async def solve(**kwargs):
        def fail(values):
            raise ValueError("home restoration failed")

        monkeypatch.setattr(robot, "set_joint_positions", fail)
        raise primary

    with pytest.raises(RequiredReadbackError) as caught:
        await _precompute(ctx, robot, SimpleNamespace(dof_count=1, solve=solve))
    assert caught.value.__cause__ is primary
    assert any("restoration" in note for note in caught.value.__notes__)

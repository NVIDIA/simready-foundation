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
"""Newton-owned cleanup paths retain their first failure on older runtimes."""

from types import SimpleNamespace

import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    _diagnostic_notes,
    _kinematic_bounds,
    ik_target_reach,
    jacobian_ik,
    jik_solver,
)
from simready.foundation.tier_newton.runtime_tests.fet004_multibody import joint_movement


def _primary(mode):
    class PrimaryError(RuntimeError):
        if mode == "absent":
            add_note = None
        elif mode == "lookup":

            @property
            def add_note(self):
                raise RuntimeError("diagnostic attribute lookup failed")

        else:

            def add_note(self, message):
                raise KeyboardInterrupt("diagnostic note interrupted")

    return PrimaryError("original native readback failure")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
async def test_actual_scalar_trial_preserves_primary_and_stop_barrier(monkeypatch, mode):
    original = _primary(mode)
    calls = []

    def stop():
        calls.append("stop")
        if len(calls) > 1:
            raise RuntimeError("required cleanup stop failed")

    def restore(*args):
        calls.append("restore")
        raise RuntimeError("required drive restoration failed")

    async def trial(*args):
        raise original

    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "activate_newton_position_drives", lambda *args, **kwargs: {})
    monkeypatch.setattr(joint_movement, "restore_newton_position_drives", restore)
    monkeypatch.setattr(joint_movement, "_run_newton_drive_sim_impl", trial)
    with pytest.raises(type(original)) as caught:
        await joint_movement._run_newton_drive_sim(
            None, None, "asset", [], {}, SimpleNamespace(stop=stop), {}, 1, 1, False, 1
        )
    assert caught.value is original and calls == ["stop", "stop"]


@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
@pytest.mark.parametrize("owner", [_kinematic_bounds, jacobian_ik])
def test_newton_optional_guard_and_search_timing_cannot_replace_primary(owner, mode):
    original = _primary(mode)

    def metric(*args):
        raise RuntimeError("optional metric unavailable")

    ctx = SimpleNamespace(add_metric=metric, warn=lambda *args: None)
    if owner is _kinematic_bounds:
        owner._guard_metric(ctx, "guard_abort", {}, primary=original)
    else:
        owner._record_search_timing(ctx, SimpleNamespace(timing_record=lambda: {}), primary=original)
    assert str(original) == "original native readback failure"


def test_newton_note_helper_does_not_need_new_core_api():
    original = RuntimeError("original")
    _diagnostic_notes.note_secondary_error(original, "local secondary")
    assert original.__notes__ == ["local secondary"]


@pytest.mark.parametrize("owner", [_kinematic_bounds, jacobian_ik])
def test_newton_lazy_note_binds_secondary_after_handler_returns(monkeypatch, owner):
    pending = []
    monkeypatch.setattr(owner, "note_secondary_error", lambda primary, message: pending.append(message))

    def metric(*args):
        raise RuntimeError("specific secondary metric error")

    ctx = SimpleNamespace(add_metric=metric, warn=lambda *args: None)
    primary = RuntimeError("original")
    if owner is _kinematic_bounds:
        owner._guard_metric(ctx, "guard_abort", {}, primary=primary)
    else:
        owner._record_search_timing(ctx, SimpleNamespace(timing_record=lambda: {}), primary=primary)
    assert len(pending) == 1 and "specific secondary metric error" in pending[0]()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
async def test_actual_newton_solver_restoration_preserves_original(monkeypatch, mode):
    primary = _primary(mode)
    solver = object.__new__(jik_solver.JacobianIKSolver)
    solver.dof_count = 1

    async def probe(*args):
        raise primary

    def restore(*args):
        raise RuntimeError("native pose restoration failed")

    async def step():
        return None

    monkeypatch.setattr(solver, "_compute_jacobian", probe)
    monkeypatch.setattr(solver, "_write_joint_pose", restore)
    with pytest.raises(type(primary)) as caught:
        await solver.compute_jacobian([0.0], step)
    assert caught.value is primary


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
async def test_actual_newton_ik_reference_restoration_preserves_original(monkeypatch, mode):
    primary = _primary(mode)

    async def trial(*args, **kwargs):
        raise primary

    async def restore(*args, **kwargs):
        raise RuntimeError("native reference restoration failed")

    monkeypatch.setattr(ik_target_reach, "_precompute_ik_solutions_impl", trial)
    monkeypatch.setattr(ik_target_reach, "_teleport_to_joints", restore)
    with pytest.raises(type(primary)) as caught:
        await ik_target_reach._precompute_ik_solutions(None, None, None, [], 0.1, 0.1, [0.0])
    assert caught.value is primary


@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
def test_newton_jik_pose_restore_never_replaces_primary(monkeypatch, mode):
    primary = _primary(mode)

    def restore(*args, **kwargs):
        raise RuntimeError("native pose restoration failed")

    monkeypatch.setattr(jacobian_ik, "write_probe_state", restore)
    jacobian_ik._restore_pose_after_error(SimpleNamespace(dof_count=1), [0.0], primary)
    assert str(primary) == "original native readback failure"

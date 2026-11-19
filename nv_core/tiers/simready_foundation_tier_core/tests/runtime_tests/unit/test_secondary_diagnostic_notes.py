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
"""Optional diagnostic notes preserve required errors at actual owner helpers."""

from types import SimpleNamespace

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    error_utils,
    ik_target_reach,
    jacobian_ik,
    jik_solver,
    kinematic_bounds,
    multi_joint_coordination,
)


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

    return PrimaryError("original required readback failure")


@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
def test_secondary_note_method_or_lookup_cannot_mask_primary(mode):
    original = _primary(mode)
    error_utils.note_secondary_error(original, "secondary cleanup failed")
    assert str(original) == "original required readback failure"


def test_secondary_note_formatting_is_inside_the_fail_soft_boundary():
    class SecondaryError(RuntimeError):
        def __str__(self):
            raise RuntimeError("secondary formatting failed")

    original = RuntimeError("original")
    error_utils.note_secondary_error(original, lambda: f"secondary: {SecondaryError()}")
    assert str(original) == "original"


@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
@pytest.mark.parametrize("owner", [kinematic_bounds, multi_joint_coordination, jacobian_ik])
def test_production_optional_guard_and_timing_paths_preserve_primary(owner, mode):
    original = _primary(mode)

    def metric(*args):
        raise RuntimeError("optional metric unavailable")

    ctx = SimpleNamespace(add_metric=metric, warn=lambda *args: None)
    if owner is kinematic_bounds:
        owner._guard_metric(ctx, "guard_abort", {}, primary=original)
    elif owner is multi_joint_coordination:
        owner._record_guard_metric(ctx, "guard_abort", {}, primary=original)
    else:
        owner._record_search_timing(ctx, SimpleNamespace(timing_record=lambda: {}), primary=original)
    assert str(original) == "original required readback failure"


def test_secondary_note_is_bounded_without_altering_the_primary():
    original = RuntimeError("original")
    error_utils.note_secondary_error(original, "x" * 10000)
    assert len(original.__notes__[0]) == 4096


@pytest.mark.parametrize("owner", [kinematic_bounds, multi_joint_coordination, jacobian_ik])
def test_lazy_secondary_message_remains_valid_after_except_scope_exits(monkeypatch, owner):
    pending = []
    monkeypatch.setattr(owner, "note_secondary_error", lambda primary, message: pending.append(message))

    def metric(*args):
        raise RuntimeError("specific secondary metric error")

    ctx = SimpleNamespace(add_metric=metric, warn=lambda *args: None)
    primary = RuntimeError("original")
    if owner is kinematic_bounds:
        owner._guard_metric(ctx, "guard_abort", {}, primary=primary)
    elif owner is multi_joint_coordination:
        owner._record_guard_metric(ctx, "guard_abort", {}, primary=primary)
    else:
        owner._record_search_timing(ctx, SimpleNamespace(timing_record=lambda: {}), primary=primary)
    assert len(pending) == 1 and "specific secondary metric error" in pending[0]()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
async def test_actual_solver_probe_restoration_preserves_original(monkeypatch, mode):
    primary = _primary(mode)
    solver = object.__new__(jik_solver.JacobianIKSolver)
    solver.dof_count = 1
    solver._jacobian_propagation_steps = 1

    async def probe(*args):
        raise primary

    def restore(*args):
        raise RuntimeError("native pose restoration failed")

    async def step():
        return None

    monkeypatch.setattr(solver, "_compute_jacobian_impl", probe)
    monkeypatch.setattr(solver, "_set_probe_pose", restore)
    with pytest.raises(type(primary)) as caught:
        await solver.compute_jacobian([0.0], step)
    assert caught.value is primary


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["absent", "lookup", "interrupted"])
@pytest.mark.parametrize("path", ["ik_reference", "jik_fk_home", "jik_search_home"])
async def test_actual_phase_reference_restoration_preserves_original(monkeypatch, mode, path):
    primary = _primary(mode)

    async def trial(*args, **kwargs):
        raise primary

    async def restore_async(*args, **kwargs):
        raise RuntimeError("native reference restoration failed")

    def restore_sync(*args, **kwargs):
        raise RuntimeError("native reference restoration failed")

    with pytest.raises(type(primary)) as caught:
        if path == "ik_reference":
            monkeypatch.setattr(ik_target_reach, "_precompute_ik_solutions_impl", trial)
            monkeypatch.setattr(ik_target_reach, "_teleport_to_joints", restore_async)
            await ik_target_reach._precompute_ik_solutions(None, None, None, [], 0.1, 0.1, [0.0])
        elif path == "jik_fk_home":
            monkeypatch.setattr(jacobian_ik, "_generate_fk_targets_impl", trial)
            monkeypatch.setattr(jacobian_ik, "_teleport_to_joints", restore_async)
            await jacobian_ik._generate_fk_targets(None, None, None, [0.0], None, None, None, (), 1, 1)
        else:
            monkeypatch.setattr(jacobian_ik, "_precompute_solutions_impl", trial)
            monkeypatch.setattr(jacobian_ik, "write_probe_state", restore_sync)
            await jacobian_ik._precompute_solutions(
                None, SimpleNamespace(dof_names=["joint"]), None, [], [0.0], None, 0.1, 0.1, 1
            )
    assert caught.value is primary

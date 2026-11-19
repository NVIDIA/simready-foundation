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

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_mapping as mapping
from simready.foundation.tier_core.runtime_tests.articulation_phases import kinematic_bounds as guard
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    multi_joint_coordination,
)
from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver


def _raise(error):
    raise error


def _probe(ctx):
    probe = object.__new__(mapping.GripperProbe)
    probe.ctx = ctx
    probe.moved = False
    probe.indices = (0, 1)
    probe.pending_restore = set()
    probe.observers = {}
    probe.targets = {0: 0.2, 1: 0.3}
    probe.diagnostic_suffix = ""
    probe.steps = 2
    probe.approach = (0, 0, -1)
    probe.meters_per_unit = 1
    probe.robot = SimpleNamespace(
        dof_count=1,
        get_joint_positions=lambda: [0.0],
        set_joint_position_target=lambda *args: None,
    )
    evidence = {"ramps": []}
    probe._evidence = lambda index: evidence
    return probe


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_type", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
async def test_actual_ramp_final_metric_never_replaces_required_step_failure(primary_type, secondary_type):
    primary = primary_type("original required endpoint step failed")
    secondary = secondary_type("optional metric interrupted")

    async def step():
        raise primary

    ctx = SimpleNamespace(step_one=step, add_metric=lambda *args: _raise(secondary))
    probe = _probe(ctx)
    with pytest.raises(primary_type) as caught:
        await probe._ramp(0, 1.0)
    assert caught.value is primary


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_type", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
async def test_actual_probe_exit_and_motion_observer_preserve_body_error(primary_type, secondary_type):
    primary = primary_type("original required native endpoint readback failed")
    secondary = secondary_type("optional history finalization interrupted")
    commands = []
    ctx = SimpleNamespace(log=lambda message: None, add_metric=lambda *args: None, warn=lambda message: None)
    probe = _probe(ctx)
    probe.moved = True
    probe.robot.set_joint_position_target = lambda index, value: commands.append((index, value))
    observer = object.__new__(MotionObserver)
    observer.ctx, observer.warned = ctx, False
    observer.history = SimpleNamespace(mark_partial=lambda reason: None, finish=lambda reason: _raise(secondary))
    probe.observers = {0: observer}
    with pytest.raises(primary_type) as caught:
        async with probe:
            raise primary
    assert caught.value is primary and commands == [(0, 0.2), (1, 0.3)]


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
async def test_restoration_diagnostics_cannot_replace_required_restore_error(secondary_type):
    primary = RuntimeError("original native return command failed")
    secondary = secondary_type("optional restoration explanation interrupted")
    ctx = SimpleNamespace(log=lambda message: _raise(secondary), add_metric=lambda *args: _raise(secondary))
    probe = _probe(ctx)
    probe.moved = True
    probe.pending_restore = {0}

    async def restore(index):
        raise primary

    probe.restore_pose = restore
    with pytest.raises(mapping.GripperMappingError) as caught:
        await probe.__aexit__(None, None, None)
    assert caught.value.__cause__ is primary


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
async def test_actual_mapping_comparison_preserves_primary_before_final_metric(monkeypatch, secondary_type):
    primary = RuntimeError("required aperture comparison failed")
    secondary = secondary_type("optional evidence publication interrupted")
    ctx = SimpleNamespace(add_metric=lambda *args: _raise(secondary))
    probe = _probe(ctx)

    async def endpoints(index):
        return (None, None), (None, None)

    probe.endpoints = endpoints
    monkeypatch.setattr(mapping, "GripperProbe", lambda *args, **kwargs: probe)
    monkeypatch.setattr(mapping, "_aperture_mapping", lambda *args: _raise(primary))
    fingers = SimpleNamespace(mimic_master_dofs=(0,), candidate_tip_paths=["/tip"], tip_link_paths=["/tip"])
    with pytest.raises(RuntimeError) as caught:
        await mapping.map_parallel_endpoints(ctx, None, fingers, None, {}, 0.1)
    assert caught.value is primary


@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_no_primary_probe_metric_retains_first_cancellation(secondary_type):
    first = secondary_type("first execution cancellation")
    probe = _probe(SimpleNamespace(add_metric=lambda *args: _raise(first)))
    with pytest.raises(secondary_type) as caught:
        probe._publish(0)
    assert caught.value is first


@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_actual_guard_trip_cannot_be_replaced_by_optional_metric(secondary_type):
    secondary = secondary_type("optional guard explanation interrupted")
    ctx = SimpleNamespace(add_metric=lambda *args: _raise(secondary))
    snapshot = SimpleNamespace(min_point=(0, 0, 0), max_point=(1, 1, 1), volume=1)
    current = SimpleNamespace(min_point=(0, 0, 0), max_point=(20, 20, 20), volume=8000)
    reference = guard.SpatialGuardReference(snapshot, 1.0, ctx, "frs")
    with pytest.raises(guard.SpatialGuardInterruption, match="spatial safety guard"):
        guard.check_guard_reference(current, reference, 8.0)


@pytest.mark.parametrize("owner", [guard, multi_joint_coordination])
@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_guard_metrics_without_primary_retain_first_cancellation(owner, secondary_type):
    first = secondary_type("first execution cancellation")
    ctx = SimpleNamespace(add_metric=lambda *args: _raise(first))
    metric = owner._guard_metric if owner is guard else owner._record_guard_metric
    with pytest.raises(secondary_type) as caught:
        metric(ctx, "reference", {}, primary=None)
    assert caught.value is first


@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_mjc_optional_metric_preserves_selected_required_guard(secondary_type):
    primary = guard.SpatialGuardInterruption("original safety interruption")
    secondary = secondary_type("optional guard explanation interrupted")
    ctx = SimpleNamespace(add_metric=lambda *args: _raise(secondary))
    multi_joint_coordination._record_guard_metric(ctx, "guard_abort", {}, primary)
    assert str(primary) == "original safety interruption"

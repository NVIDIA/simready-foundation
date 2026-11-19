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
"""Velocity omission requests must never become nonfinite native writes."""

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


def _handle(current=(8.0, 9.0, 0.0, 6.0), *, legacy=False, getter=True):
    caps = np.asarray([current], dtype=np.float32)
    writes = []

    def write(values, *indices):
        assert np.isfinite(values).all(), "nonfinite native velocity write"
        caps[:] = values
        writes.append(np.asarray(values).copy())

    view = SimpleNamespace()
    owner = view
    if legacy:
        view._physics_view = owner = SimpleNamespace()
    setattr(owner, "set_dof_max_velocities" if legacy else "set_max_joint_velocities", write)
    if getter:
        setattr(owner, "get_dof_max_velocities" if legacy else "get_joint_max_velocities", lambda: caps.copy())
    robot = RobotHandle(None, "/Robot", None, None)
    robot._articulation = SimpleNamespace(dof_names=list("abcd"), _articulation_view=view)
    return robot, caps, writes, owner


@pytest.mark.parametrize("legacy", [False, True])
def test_omissions_preserve_complete_raw_native_caps_including_zero_and_sdk_default(legacy):
    robot, caps, writes, _ = _handle(current=(8.0, 9.0, 0.0, np.finfo(np.float32).max), legacy=legacy)
    # A filtered rating API is deliberately unsuitable for preserving native state.
    robot.get_joint_velocity_limits = lambda: np.full(4, np.nan)
    request = np.asarray([1.5, 2.0, np.nan, np.nan])
    assert robot.apply_velocity_limits_to_tensor_view(request) is True
    np.testing.assert_array_equal(caps[0, :3], [1.5, 2.0, 0.0])
    assert caps[0, 3] == np.finfo(np.float32).max
    assert len(writes) == 1 and np.isnan(request[2:]).all()


@pytest.mark.parametrize(
    "limits",
    [
        [1.0, 2.0, np.inf, 4.0],
        [1.0, 2.0, -1.0, 4.0],
        [1.0, 2.0, 0.0, 4.0],
        [1.0, 2.0, 1e100, 4.0],
        [1.0, 2.0, 1e-100, 4.0],
        [True, 2.0, 3.0, 4.0],
        ["1", "2", "3", "4"],
        [[1.0, 2.0], [3.0, 4.0]],
        [1.0, 2.0],
        [1.0, 2.0, 3.0, 4.0, 5.0],
    ],
)
def test_invalid_request_fails_before_native_write(limits):
    robot, _, writes, _ = _handle()
    with pytest.raises((ValueError, RuntimeError)):
        robot.apply_velocity_limits_to_tensor_view(limits)
    assert not writes


@pytest.mark.parametrize("current", [(8.0, 9.0, np.nan, 6.0), (8.0, 9.0, np.inf, 6.0), (8.0, 9.0, -1.0, 6.0)])
def test_unpreservable_omitted_native_cap_fails_before_write(current):
    robot, _, writes, _ = _handle(current)
    with pytest.raises((ValueError, RuntimeError)):
        robot.apply_velocity_limits_to_tensor_view([1.5, 2.0, np.nan, np.nan])
    assert not writes


def test_absent_raw_getter_cannot_preserve_omissions():
    robot, _, writes, _ = _handle(getter=False)
    with pytest.raises((ValueError, RuntimeError)):
        robot.apply_velocity_limits_to_tensor_view([1.5, 2.0, np.nan, np.nan])
    assert not writes


@pytest.mark.parametrize("corruption", [np.nan, 0.05])
def test_omitted_readback_corruption_is_not_success(corruption):
    robot, caps, writes, owner = _handle()
    reads = 0

    def getter():
        nonlocal reads
        reads += 1
        result = caps.copy()
        if writes:
            result[0, 2] = corruption
        return result

    owner.get_joint_max_velocities = getter
    assert robot.apply_velocity_limits_to_tensor_view([1.5, 2.0, np.nan, np.nan]) is False
    assert reads >= 2 and len(writes) == 1


def test_all_omissions_is_noop_without_getter_or_native_write():
    robot, _, writes, _ = _handle(getter=False)
    assert robot.apply_velocity_limits_to_tensor_view([np.nan] * 4) is False
    assert not writes


@pytest.mark.parametrize("returned", [0.0, 0.09, 0.0011])
def test_unapplied_tiny_cap_cannot_pass_readback_with_absolute_or_percent_slack(returned):
    robot, _, writes, owner = _handle(current=(returned, 2.0, 5.0, 6.0))
    owner.set_max_joint_velocities = lambda values: writes.append(np.asarray(values).copy())
    assert robot.apply_velocity_limits_to_tensor_view([0.001, 2.0, 5.0, 6.0]) is False
    assert len(writes) == 1


def test_native_float32_roundtrip_matches_float64_request_after_qualified_conversion():
    robot, _, writes, _ = _handle()
    limits = np.asarray([0.001, 2.0, 5.0, 6.0], dtype=np.float64)
    assert robot.apply_velocity_limits_to_tensor_view(limits) is True
    assert writes[0][0, 0] == np.float32(0.001)
    assert limits[0] == 0.001


@pytest.mark.parametrize(
    "value",
    [
        5.939047e36,
        float(np.finfo(np.float32).max) * np.pi / 180.0,
        float(np.float32(float(np.finfo(np.float32).max) * np.pi / 180.0)),
    ],
)
def test_converted_sdk_sentinel_requires_native_angular_provenance(value):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
        usable_velocity,
    )

    assert usable_velocity(value, native_angular=True) is None
    # An authored rating, linear coordinate, or unqualified source keeps its value.
    assert usable_velocity(value) == value
    assert usable_velocity(1e30, native_angular=True) == 1e30


def _mixed_joint_scene():
    from pxr import UsdPhysics
    from test_selected_joint_metadata import physical_asset

    stage, selected = physical_asset()
    UsdPhysics.PrismaticJoint.Define(stage, "/Asset/Constraints/leader")
    for name in ("follower", "leader"):
        stage.GetPrimAtPath("/Asset/Constraints/" + name).RemoveProperty(
            "physxDrivePerformanceEnvelope:angular:maxActuatorVelocity"
        )
    value = 5.939047e36
    robot = SimpleNamespace(
        dof_names=selected.dof_names,
        dof_count=2,
        prim_path=selected.prim_path,
        get_joint_position_limits=lambda: (np.asarray([-1.0, -1.0]), np.asarray([1.0, 1.0])),
        get_joint_velocity_limits=lambda: np.asarray([value, value]),
    )
    return robot, {"stage": stage, "asset_prim": selected.asset_prim, "robot_root_prim": selected.asset_prim}


def test_vel_filters_only_qualified_native_angular_default_and_keeps_authored_fallback():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.velocity_limit import (
        find_joints_with_velocity_limits,
    )

    robot, scene = _mixed_joint_scene()
    joints = find_joints_with_velocity_limits(robot, scene_info=scene)
    assert [joint["index"] for joint in joints] == [1]
    joints = find_joints_with_velocity_limits(robot, usd_vels=np.asarray([5.939047e36, np.nan]), scene_info=scene)
    assert [joint["index"] for joint in joints] == [0, 1]
    assert joints[0]["max_velocity_source"] == "usd"


def test_sweep_timing_ignores_converted_native_angular_default_without_dropping_linear_value():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
        resolve_velocity_hints,
    )

    robot, scene = _mixed_joint_scene()
    hints = resolve_velocity_hints(robot, scene)
    assert hints[0][0] is None
    assert hints[1] == (5.939047e36, "runtime joint velocity ceiling")


@pytest.mark.parametrize("target", [np.nan, np.inf, 1e100])
def test_sparse_newton_expansion_rejects_nonfinite_final_native_target_before_action(monkeypatch, target):
    import sys

    writes = []
    monkeypatch.setitem(
        sys.modules,
        "isaacsim.core.utils.types",
        SimpleNamespace(ArticulationAction=lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    robot = RobotHandle(None, "/Robot", None, None)
    robot._is_newton = True
    robot._articulation = SimpleNamespace(
        dof_names=list("abcd"),
        get_joint_position_targets=lambda: np.asarray([1.0, 2.0, 3.0, 4.0]),
        apply_action=lambda action: writes.append(action),
    )
    with pytest.raises((ValueError, RuntimeError)):
        robot.set_joint_position_target(0, target)
    assert not writes


@pytest.mark.asyncio
async def test_actual_velocity_phase_preserves_ineligible_slots_at_handle_write(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import velocity_limit

    robot, caps, writes, _ = _handle(current=(8.0, 9.0, 5.0, 6.0))
    robot.get_joint_position_limits = lambda: (np.asarray([-1.0, -1.0, -np.inf, -np.inf]), np.ones(4))
    monkeypatch.setattr(velocity_limit, "resolve_usd_max_velocities", lambda **kwargs: None)
    metrics = {}

    class StopBeforeSettle(Exception):
        pass

    def step(message):
        if message == "Settling robot before velocity tests":
            raise StopBeforeSettle()

    ctx = SimpleNamespace(
        step=step, warn=lambda message: None, add_metric=lambda name, value: metrics.update({name: value})
    )
    with pytest.raises(StopBeforeSettle):
        await velocity_limit.run_velocity_limit(
            ctx,
            robot,
            {},
            {
                "physics_fps": 4,
                "capture_fps": 4,
                "settle_seconds": 1.0,
                "test_duration_seconds": 2.0,
            },
        )
    np.testing.assert_array_equal(caps, [[8.0, 9.0, 5.0, 6.0]])
    assert len(writes) == 1
    assert metrics["vel_velocity_limit_application"] == "reported_success"
    assert metrics["vel_velocity_limit_enforcement"] == "not_verified"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_current", [False, True])
async def test_core_initialize_preserves_native_caps_or_fails_without_invented_fallback(monkeypatch, invalid_current):
    import sys

    from test_robot_handle_authored_scale import _fake_isaac
    from test_selected_joint_metadata import physical_asset

    stage, selected = physical_asset()
    # Only follower has an authored limit; leader's live limit must be retained.
    stage.GetPrimAtPath("/Asset/Constraints/leader").RemoveProperty(
        "physxDrivePerformanceEnvelope:angular:maxActuatorVelocity"
    )
    _fake_isaac(monkeypatch, stage)
    caps = np.asarray([[8.0, np.nan if invalid_current else 9.0]], dtype=np.float32)
    writes = []

    def write(values):
        writes.append(np.asarray(values).copy())
        caps[:] = values

    art = SimpleNamespace(
        dof_names=selected.dof_names, get_max_joint_velocities=lambda: caps.copy(), set_max_joint_velocities=write
    )
    monkeypatch.setattr(sys.modules["isaacsim.core.prims"], "SingleArticulation", lambda **kwargs: art)
    robot = RobotHandle(stage, selected.prim_path, selected.asset_prim, None)
    messages = []
    ctx = SimpleNamespace(step=messages.append, warn=lambda message: None)
    if invalid_current:
        with pytest.raises(RuntimeError, match="preserve omitted"):
            await robot.initialize(ctx)
        assert not writes and not robot._initialized
    else:
        await robot.initialize(ctx)
        assert robot._initialized and len(writes) == 1
        assert caps[0, 0] == pytest.approx(np.pi / 3)
        assert caps[0, 1] == 9.0
        application = next(message for message in messages if "authored joint velocity" in message)
        assert "application acknowledged" in application
        assert "native coordinates/s" in application
        assert "unauthored native limits preserved" in application
        assert "enforced" not in application and "unlimited" not in application

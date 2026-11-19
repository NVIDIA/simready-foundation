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
"""Rebuilding the articulation view must never authorize deleting asset prims."""

import sys
from types import ModuleType, SimpleNamespace

import pytest
from pxr import Usd, UsdGeom
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


def _reinitialization_fixture(monkeypatch, *, remove_error=None, add_error=None, reset_error=None):
    calls = []
    previous = SimpleNamespace(dof_names=["old"])
    replacement = SimpleNamespace(dof_names=["new", "carrier"])

    def single_articulation(**kwargs):
        calls.append(("construct", {**kwargs, "scale": tuple(kwargs["scale"])}))
        return replacement

    for name in ("isaacsim", "isaacsim.core", "isaacsim.core.prims"):
        module = ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules["isaacsim.core.prims"].SingleArticulation = single_articulation

    def remove(name, **kwargs):
        calls.append(("remove", name, kwargs))
        if remove_error is not None:
            raise remove_error

    def add(articulation):
        calls.append(("add", articulation))
        if add_error is not None:
            raise add_error

    async def reset():
        calls.append(("reset",))
        if reset_error is not None:
            raise reset_error

    robot = RobotHandle.__new__(RobotHandle)
    robot._name = "test_gripper"
    robot._robot_prim_path = "/World/AssetRoot/Gripper"
    robot._stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(robot._stage, robot._robot_prim_path)
    robot._articulation = previous
    robot._world = SimpleNamespace(scene=SimpleNamespace(remove_object=remove, add=add), reset_async=reset)
    ctx = SimpleNamespace(step=lambda message: None)
    return robot, ctx, calls, previous, replacement


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TypeError("registry_only unsupported"), RuntimeError("registry unavailable")])
async def test_failed_registry_only_removal_never_falls_back_to_prim_deletion(monkeypatch, error):
    robot, ctx, calls, previous, _ = _reinitialization_fixture(monkeypatch, remove_error=error)
    with pytest.raises(RuntimeError, match="registry-only removal failed") as raised:
        await robot.reinitialize_articulation(ctx)
    assert raised.value.__cause__ is error
    assert calls == [("remove", "test_gripper", {"registry_only": True})]
    assert robot._articulation is previous


@pytest.mark.asyncio
async def test_replacement_registration_failure_does_not_reset_or_publish_view(monkeypatch):
    error = RuntimeError("replacement registration unavailable")
    robot, ctx, calls, previous, replacement = _reinitialization_fixture(monkeypatch, add_error=error)
    with pytest.raises(RuntimeError, match="registering the replacement view failed") as raised:
        await robot.reinitialize_articulation(ctx)
    assert raised.value.__cause__ is error
    assert calls == [
        ("remove", "test_gripper", {"registry_only": True}),
        (
            "construct",
            {"prim_path": "/World/AssetRoot/Gripper", "name": "test_gripper", "scale": (1.0, 1.0, 1.0)},
        ),
        ("add", replacement),
    ]
    assert robot._articulation is previous


@pytest.mark.asyncio
async def test_reset_failure_preserves_original_error_and_does_not_publish_view(monkeypatch):
    error = RuntimeError("physics reset failed")
    robot, ctx, calls, previous, _ = _reinitialization_fixture(monkeypatch, reset_error=error)
    with pytest.raises(RuntimeError, match="physics reset failed") as raised:
        await robot.reinitialize_articulation(ctx)
    assert raised.value is error
    assert calls[-1] == ("reset",)
    assert robot._articulation is previous


@pytest.mark.asyncio
async def test_successful_reinitialization_publishes_only_after_reset(monkeypatch):
    robot, ctx, calls, previous, replacement = _reinitialization_fixture(monkeypatch)
    original_reset = robot._world.reset_async

    async def check_reset():
        assert robot._articulation is previous
        await original_reset()

    robot._world.reset_async = check_reset
    await robot.reinitialize_articulation(ctx)
    assert calls == [
        ("remove", "test_gripper", {"registry_only": True}),
        (
            "construct",
            {"prim_path": "/World/AssetRoot/Gripper", "name": "test_gripper", "scale": (1.0, 1.0, 1.0)},
        ),
        ("add", replacement),
        ("reset",),
    ]
    assert robot._articulation is replacement

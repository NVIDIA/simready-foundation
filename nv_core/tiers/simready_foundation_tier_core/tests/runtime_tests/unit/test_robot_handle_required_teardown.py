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
import sys
from types import ModuleType, SimpleNamespace

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


def _handle(monkeypatch, clear_error=None, close_error=None, clear_result=None, close_result=None):
    calls = []

    def clear():
        calls.append("world")
        if clear_error is not None:
            raise clear_error
        return clear_result

    def close():
        calls.append("controller")
        if close_error is not None:
            raise close_error
        return close_result

    api = ModuleType("isaacsim.core.api")
    api.World = SimpleNamespace(clear_instance=clear)
    monkeypatch.setitem(sys.modules, "isaacsim.core.api", api)
    robot = RobotHandle.__new__(RobotHandle)
    robot._newton_actuators = SimpleNamespace(close=close)
    robot._mjc_tendon_controls = [object()]
    robot._world = robot._articulation = robot._root_prim = object()
    robot._initialized = True
    return robot, calls


@pytest.mark.parametrize("first_failure", ["world", "controller", "both"])
def test_required_teardown_preserves_first_error_and_drops_references(monkeypatch, first_failure):
    first = ValueError("world cleanup")
    second = RuntimeError("controller cleanup")
    robot, calls = _handle(
        monkeypatch,
        clear_error=first if first_failure in ("world", "both") else None,
        close_error=second if first_failure in ("controller", "both") else None,
    )
    with pytest.raises(Exception) as caught:
        robot.teardown(required=True)
    assert caught.value is (second if first_failure == "controller" else first)
    assert calls == ["world", "controller"]
    assert robot._newton_actuators is robot._world is robot._articulation is robot._root_prim is None
    assert robot._mjc_tendon_controls == []
    assert not robot._initialized


@pytest.mark.parametrize("operation", ["world", "controller"])
def test_required_teardown_reports_explicit_rejection(monkeypatch, operation):
    robot, calls = _handle(
        monkeypatch,
        clear_result=False if operation == "world" else None,
        close_result=False if operation == "controller" else None,
    )
    with pytest.raises(RuntimeError, match="cleanup was rejected"):
        robot.teardown(required=True)
    assert calls == ["world", "controller"]


def test_default_teardown_retains_best_effort_compatibility(monkeypatch):
    robot, calls = _handle(monkeypatch, clear_error=RuntimeError("world"), close_error=ValueError("controller"))
    robot.teardown()
    assert calls == ["world", "controller"]
    assert not robot._initialized


def test_successful_required_teardown_is_idempotent(monkeypatch):
    robot, calls = _handle(monkeypatch)
    robot.teardown(required=True)
    robot.teardown(required=True)
    assert calls == ["world", "controller", "world"]


@pytest.mark.parametrize("error_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("operation", ["world", "controller"])
def test_required_teardown_preserves_stop_requests_and_attempts_independent_cleanup(monkeypatch, error_type, operation):
    original = error_type("cleanup interrupted")
    robot, calls = _handle(
        monkeypatch,
        clear_error=original if operation == "world" else None,
        close_error=original if operation == "controller" else None,
    )
    with pytest.raises(BaseException) as caught:
        robot.teardown(required=True)
    assert caught.value is original
    assert calls == ["world", "controller"]
    assert robot._newton_actuators is None
    assert not robot._initialized

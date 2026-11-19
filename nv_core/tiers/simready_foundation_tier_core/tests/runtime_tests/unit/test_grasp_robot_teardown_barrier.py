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
"""Required generated-controller release cannot become safe on cleanup retry."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import UsdGeom
from test_grasp_execution_errors import grasp_module as grasp_module
from test_grasp_scene_fixture_controls import production_robot as production_robot
from test_grasp_scene_fixture_controls import production_scene as production_scene


@pytest.mark.parametrize(
    "cause",
    [
        OSError("bridge close failed"),
        asyncio.CancelledError("required cleanup cancelled"),
        KeyboardInterrupt("shutdown requested"),
    ],
)
def test_required_teardown_failure_stays_sticky_after_controller_refs_clear(production_robot, cause):
    robot = production_robot.robot
    calls = []

    def fail(*, required=False):
        calls.append(required)
        raise cause

    robot._tensor_art = SimpleNamespace(teardown=fail)
    robot._dof_index = {"left_joint": 0}
    robot._targets = np.zeros(1)
    for _ in range(2):
        with pytest.raises(type(cause)) as caught:
            robot.teardown()
        assert caught.value is cause
    assert calls == [True]
    assert robot._tensor_art is None
    assert robot._dof_index == {}
    assert robot._targets is None
    assert robot._required_teardown_failure is cause


def test_explicit_required_teardown_rejection_stays_sticky(production_robot):
    calls = []
    robot = production_robot.robot
    robot._tensor_art = SimpleNamespace(teardown=lambda *, required=False: calls.append(required) or False)
    with pytest.raises(RuntimeError, match="teardown was rejected") as first:
        robot.teardown()
    with pytest.raises(RuntimeError) as repeated:
        robot.teardown()
    assert repeated.value is first.value
    assert calls == [True]


def test_successful_required_teardown_remains_idempotent(production_robot):
    robot = production_robot.robot
    calls = []
    robot._tensor_art = SimpleNamespace(teardown=lambda *, required=False: calls.append(required))
    robot._dof_index = {"left_joint": 0}
    robot._targets = np.zeros(1)
    assert robot.teardown() is None
    assert robot.teardown() is None
    assert calls == [True]
    assert robot._required_teardown_failure is None
    assert robot._tensor_art is None
    assert robot._targets is None
    assert robot._dof_index == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cause", [OSError("bridge close failed"), asyncio.CancelledError("required cleanup cancelled")]
)
async def test_rebuild_failure_then_outer_cleanup_never_authorizes_topology(
    production_robot, grasp_module, monkeypatch, cause
):
    robot = production_robot.robot
    harness = production_robot.harness
    scene = harness.scene
    native_calls = []

    def fail(*, required=False):
        native_calls.append(required)
        raise cause

    robot._tensor_art = SimpleNamespace(teardown=fail)
    scene._robot = robot
    path = harness.module.GraspRobot.ROBOT_PATH
    UsdGeom.Xform.Define(harness.stage, path)
    monkeypatch.setattr(scene, "get_current_world_grasp_points", lambda: (np.zeros(3), np.array([0.1, 0.0, 0.0])))
    retired = []
    scene._ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=retired.append)
    physics = SimpleNamespace(stop=lambda: None, play=lambda: pytest.fail("unsafe rebuild restart"))
    with pytest.raises(type(cause)) as first:
        await scene.rebuild_gripper_at_settled_position(physics)
    assert first.value is cause
    assert harness.stage.GetPrimAtPath(path)

    async def update():
        pytest.fail("stage update after failed required controller teardown")

    def restore(_stage, _paths):
        pytest.fail("temporary articulation restore after failed required controller teardown")

    context = SimpleNamespace(
        _engine_session=scene._ctx._engine_session,
        scene=SimpleNamespace(clear=lambda: pytest.fail("scene clear after failed required controller teardown")),
    )
    with pytest.raises(type(cause)) as repeated:
        try:
            raise cause
        finally:
            await grasp_module._cleanup_identifier_scene(
                context,
                physics,
                robot,
                harness.stage,
                ["/Asset/temporary_articulation"],
                restore,
                update,
                original_error=cause,
                owned_fixture_paths=[path],
            )
    assert repeated.value is cause
    assert harness.stage.GetPrimAtPath(path)
    assert native_calls == [True]
    assert retired == [
        "Required FET005 old gripper removal failed.",
        "Required FET005 generated controller teardown failed.",
    ]

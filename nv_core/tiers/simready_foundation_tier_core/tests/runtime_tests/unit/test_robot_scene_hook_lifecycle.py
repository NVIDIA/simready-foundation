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
from types import SimpleNamespace

import pytest
from simready.evaluate_engine_kit import physics_utils
from simready.foundation.tier_core.runtime_tests import engine_guard
from simready.foundation.tier_core.runtime_tests.articulation_phases import robot_scene
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import RobotType


def _scene_fixture(monkeypatch, failure=None, exception_type=RuntimeError):
    Usd = pytest.importorskip("pxr.Usd")
    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/Asset", "Xform")

    class Builder:
        def __init__(self):
            self.shape_label = []
            self.imports = 0
            self.finalizations = 0

        def add_usd(self, *args, **kwargs):
            self.imports += 1
            return "imported"

        def finalize(self, *args, **kwargs):
            self.finalizations += 1
            return "finalized"

        def add_ground_plane(self, label):
            self.shape_label.append(label)

    originals = (Builder.add_usd, Builder.finalize)
    builder_instance = Builder()
    error = exception_type("setup checkpoint: " + str(failure))
    monkeypatch.setitem(sys.modules, "newton", SimpleNamespace(ModelBuilder=Builder))
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(physics_utils, "cook_skip_message", lambda result: None)
    monkeypatch.setattr(engine_guard, "newton_scene_initialized", lambda: True)
    monkeypatch.setattr(robot_scene, "determine_robot_type", lambda *args: RobotType.MOBILE_BASE)
    monkeypatch.setattr(robot_scene, "_has_gripper_signals", lambda *args: False)
    monkeypatch.setattr(robot_scene, "has_authored_robot_type", lambda *args: True)
    monkeypatch.setattr(robot_scene, "get_articulation_root_path", lambda *args: "/Asset")
    monkeypatch.setattr(robot_scene, "capture_default_state", lambda robot: object())
    monkeypatch.setattr(robot_scene, "compute_world_aligned_bbox", lambda prim: object())
    monkeypatch.setattr(robot_scene, "detect_passive_joints", lambda *args, **kwargs: (frozenset(), []))

    def checkpoint(name):
        assert Builder.add_usd is not originals[0]
        assert Builder.finalize is not originals[1]
        if failure == name:
            raise error

    class Robot:
        dof_count = 1
        dof_names = ["hinge"]

        def __init__(self, **kwargs):
            self.prim_path = kwargs["robot_prim_path"]

        async def initialize_newton(self, ctx):
            assert (Builder.add_usd, Builder.finalize) == originals
            if failure == "controller":
                raise error

    monkeypatch.setattr(robot_scene, "RobotHandle", Robot)

    class Scene:
        def __init__(self):
            self.stage = stage
            self.lighting = SimpleNamespace(add_dome=lambda **kwargs: checkpoint("lighting"))

        def load_asset(self, *args, **kwargs):
            return SimpleNamespace(prim_path="/Asset")

        def add_room(self):
            return SimpleNamespace(auto_size=lambda *args: None)

        def add_physics(self, **kwargs):
            checkpoint("add_physics")

            def play():
                checkpoint("play")
                assert builder_instance.add_usd() == "imported"
                assert builder_instance.finalize() == "finalized"

            return SimpleNamespace(play=play)

        def setup_camera_follow(self, config):
            checkpoint("camera")

        async def prepare_physics(self):
            checkpoint("prepare")
            return None

    class Context:
        config = {}
        asset_path = "asset.usd"

        def __init__(self):
            self.scene = Scene()
            self.settle_count = 0
            self.prechecks = []

        def set_settle_frames(self, frames):
            pass

        def step(self, message):
            pass

        warn = step

        def precheck_failure(self, message):
            self.prechecks.append(message)

        async def settle(self, **kwargs):
            self.settle_count += 1
            checkpoint("composition" if self.settle_count == 1 else "first_cook")

    return Context(), Builder, originals, error, builder_instance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["add_physics", "lighting", "camera", "composition", "prepare", "play", "controller"]
)
async def test_ground_hooks_restore_after_setup_exception_preserving_error(monkeypatch, failure):
    ctx, builder, originals, error, _ = _scene_fixture(monkeypatch, failure)
    with pytest.raises(RuntimeError) as caught:
        await robot_scene.setup_robot_test_scene(ctx)
    assert caught.value is error
    assert (builder.add_usd, builder.finalize) == originals


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["add_physics", "lighting", "camera", "composition", "prepare", "play", "first_cook", "controller"]
)
async def test_ground_hooks_restore_after_cancellation_preserving_error(monkeypatch, failure):
    ctx, builder, originals, error, _ = _scene_fixture(monkeypatch, failure, asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError) as caught:
        await robot_scene.setup_robot_test_scene(ctx)
    assert caught.value is error
    assert (builder.add_usd, builder.finalize) == originals


@pytest.mark.asyncio
async def test_first_cook_error_retains_cause_and_restores_hooks(monkeypatch):
    ctx, builder, originals, error, _ = _scene_fixture(monkeypatch, "first_cook")
    with pytest.raises(engine_guard.NewtonSceneInitializationError) as caught:
        await robot_scene.setup_robot_test_scene(ctx)
    assert caught.value.__cause__ is error
    assert (builder.add_usd, builder.finalize) == originals


@pytest.mark.asyncio
async def test_full_fake_scene_restores_before_controller_and_adds_one_ground(monkeypatch):
    ctx, builder, originals, _, instance = _scene_fixture(monkeypatch)
    robot, scene = await robot_scene.setup_robot_test_scene(ctx)
    assert robot.dof_count == 1
    assert scene["active_physics_engine"] == "newton"
    assert (builder.add_usd, builder.finalize) == originals
    assert instance.shape_label == ["fet028_ground_plane"]
    assert instance.imports == instance.finalizations == 1


@pytest.mark.asyncio
async def test_cook_precheck_return_restores_hooks(monkeypatch):
    ctx, builder, originals, _, _ = _scene_fixture(monkeypatch)
    monkeypatch.setattr(physics_utils, "cook_skip_message", lambda result: "SKIP:no qualified collider cook")
    assert await robot_scene.setup_robot_test_scene(ctx) == (None, {})
    assert ctx.prechecks == ["no qualified collider cook"]
    assert (builder.add_usd, builder.finalize) == originals

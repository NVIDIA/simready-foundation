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
from simready.foundation.tier_newton.runtime_tests import engine_guard
from simready.foundation.tier_newton.runtime_tests.articulation_phases import robot_scene
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_type import RobotType


def _scene_fixture(monkeypatch, failure=None, exception_type=RuntimeError):
    Usd = pytest.importorskip("pxr.Usd")
    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/Asset", "Xform")

    class Builder:
        def add_usd(self, *args, **kwargs):
            pass

        def finalize(self, *args, **kwargs):
            pass

    originals = (Builder.add_usd, Builder.finalize)
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
            raise exception_type("setup checkpoint: " + name)

    class Robot:
        dof_count = 1
        dof_names = ["hinge"]

        def __init__(self, **kwargs):
            self.prim_path = kwargs["robot_prim_path"]

        async def initialize_newton(self, ctx):
            # The first-cook block has already restored its hooks.
            assert (Builder.add_usd, Builder.finalize) == originals

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
            return SimpleNamespace(play=lambda: checkpoint("play"))

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

        def set_settle_frames(self, frames):
            pass

        def step(self, message):
            pass

        warn = step

        async def settle(self, **kwargs):
            self.settle_count += 1
            checkpoint("composition" if self.settle_count == 1 else "first_cook")

    return Context(), Builder, originals


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["add_physics", "lighting", "camera", "composition", "prepare"])
async def test_newton_ground_hooks_restore_after_early_setup_exception(monkeypatch, failure):
    ctx, builder, originals = _scene_fixture(monkeypatch, failure)
    with pytest.raises(RuntimeError, match="setup checkpoint"):
        await robot_scene.setup_robot_test_scene(ctx)
    assert (builder.add_usd, builder.finalize) == originals


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["composition", "prepare", "first_cook"])
async def test_newton_ground_hooks_restore_after_task_cancellation(monkeypatch, failure):
    ctx, builder, originals = _scene_fixture(monkeypatch, failure, asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await robot_scene.setup_robot_test_scene(ctx)
    assert (builder.add_usd, builder.finalize) == originals


@pytest.mark.asyncio
async def test_newton_ground_hooks_restore_before_controller_initialization(monkeypatch):
    ctx, builder, originals = _scene_fixture(monkeypatch)
    robot, scene = await robot_scene.setup_robot_test_scene(ctx)
    assert robot.dof_count == 1
    assert scene["active_physics_engine"] == "newton"
    assert (builder.add_usd, builder.finalize) == originals


@pytest.mark.asyncio
async def test_fixed_joint_root_keeps_controller_identity_but_uses_loaded_geometry_and_joints(monkeypatch):
    from pxr import UsdGeom, UsdPhysics
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    ctx, _, _ = _scene_fixture(monkeypatch)
    stage = ctx.scene.stage
    root = UsdPhysics.FixedJoint.Define(stage, "/Asset/root_joint").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(root)
    UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joints/hinge")
    UsdGeom.Cube.Define(stage, "/Asset/Body/Visual")
    monkeypatch.setattr(robot_scene, "get_articulation_root_path", lambda *args: str(root.GetPath()))
    selected_geometry = []

    def bounds(prim):
        selected_geometry.append(prim.GetPath())
        assert stage.GetPrimAtPath(str(prim.GetPath()) + "/Body/Visual")
        return object()

    monkeypatch.setattr(robot_scene, "compute_world_aligned_bbox", bounds)
    monkeypatch.setattr(robot_scene, "detect_passive_joints", detect_passive_joints)
    robot, scene = await robot_scene.setup_robot_test_scene(ctx)
    assert robot.prim_path == "/Asset/root_joint"
    assert scene["robot_root_prim"] == root
    assert scene["asset_prim"] == stage.GetPrimAtPath("/Asset")
    assert selected_geometry == [scene["asset_prim"].GetPath()]
    assert scene["passive_joint_indices"] == frozenset({0})

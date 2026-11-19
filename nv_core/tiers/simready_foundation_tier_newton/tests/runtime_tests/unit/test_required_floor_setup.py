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

import sys
from types import SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.evaluate_engine_kit import physics_utils
from simready.evaluate_engine_kit.scene_handle import KitSceneHandle
from simready.foundation.tier_newton.runtime_tests.articulation_phases import robot_scene


@pytest.mark.asyncio
@pytest.mark.parametrize("rejected", ["collision", "visibility"])
async def test_required_floor_disable_rejection_prevents_physics_setup(monkeypatch, rejected):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(asset)
    monkeypatch.setitem(sys.modules, "carb", SimpleNamespace(settings=SimpleNamespace(get_settings=lambda: None)))
    scene = KitSceneHandle(stage)
    room = scene.add_room()
    room.set_size(20, 30, 10)
    floor = stage.GetPrimAtPath("/World/Room/Floor")
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        if rejected == "collision":
            UsdPhysics.CollisionAPI(floor).GetCollisionEnabledAttr().Set(True)
        else:
            UsdGeom.Imageable(floor).CreateVisibilityAttr().Set(UsdGeom.Tokens.inherited)
    session_before = stage.GetSessionLayer().ExportToString()
    monkeypatch.setattr(scene, "load_asset", lambda *args, **kwargs: SimpleNamespace(prim_path="/Asset"))
    monkeypatch.setattr(scene, "add_room", lambda: room)
    monkeypatch.setattr(room, "auto_size", lambda *args: None)
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(robot_scene, "determine_robot_type", lambda *args: robot_scene.RobotType.ARM)
    monkeypatch.setattr(robot_scene, "has_authored_robot_type", lambda *args: True)
    monkeypatch.setattr(robot_scene, "_has_gripper_signals", lambda *args: False)

    def start_physics(**kwargs):
        raise AssertionError("physics must not execute with rejected floor collision")

    monkeypatch.setattr(scene, "add_physics", start_physics)
    ctx = SimpleNamespace(
        scene=scene,
        asset_path="fixture.usd",
        config={"activate_ground_plane": False},
        set_settle_frames=lambda *args: None,
        step=lambda *args: None,
    )
    with pytest.raises(RuntimeError, match="Cannot set room floor " + rejected):
        await robot_scene.setup_robot_test_scene(ctx)
    if rejected == "collision":
        assert UsdPhysics.CollisionAPI(floor).GetCollisionEnabledAttr().Get() is True
    assert stage.GetSessionLayer().ExportToString() == session_before


def test_legacy_floor_readback_uses_handle_path_and_preserves_edit_target():
    stage = Usd.Stage.CreateInMemory()
    floor = UsdGeom.Mesh.Define(stage, "/Fixture/CustomRoom/Floor").GetPrim()
    collision = UsdPhysics.CollisionAPI.Apply(floor).CreateCollisionEnabledAttr(True)
    image = UsdGeom.Imageable(floor)

    def hide():
        collision.Set(False)
        image.MakeInvisible()

    room = SimpleNamespace(_room_path="/Fixture/CustomRoom", hide_ground=hide)
    original_target = stage.GetEditTarget().GetLayer()
    robot_scene._hide_room_ground(stage, room)
    assert collision.Get() is False
    assert image.GetVisibilityAttr().Get() == UsdGeom.Tokens.invisible
    assert stage.GetEditTarget().GetLayer() == original_target


@pytest.mark.parametrize("missing", ["room_path", "floor", "collision_api"])
def test_floor_readback_rejects_missing_required_fixture(missing):
    stage = Usd.Stage.CreateInMemory()
    room = SimpleNamespace(_room_path="/Fixture/Room", hide_ground=lambda: None)
    if missing == "room_path":
        del room._room_path
    elif missing == "collision_api":
        UsdGeom.Mesh.Define(stage, "/Fixture/Room/Floor")
    with pytest.raises(RuntimeError, match="room floor"):
        robot_scene._hide_room_ground(stage, room)


@pytest.mark.parametrize("rejected", ["collision", "visibility"])
@pytest.mark.parametrize("sample_time", [0.0, 12.0])
def test_floor_readback_rejects_animated_fixture_opinions(rejected, sample_time):
    stage = Usd.Stage.CreateInMemory()
    floor = UsdGeom.Mesh.Define(stage, "/Fixture/Room/Floor").GetPrim()
    collision = UsdPhysics.CollisionAPI.Apply(floor).CreateCollisionEnabledAttr(False)
    visibility = UsdGeom.Imageable(floor).CreateVisibilityAttr(UsdGeom.Tokens.invisible)
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        attribute = collision if rejected == "collision" else visibility
        attribute.Set(True if rejected == "collision" else UsdGeom.Tokens.inherited, sample_time)
    session_before = stage.GetSessionLayer().ExportToString()
    room = SimpleNamespace(_room_path="/Fixture/Room", hide_ground=lambda: None)
    assert collision.Get() is False
    assert visibility.Get() == UsdGeom.Tokens.invisible
    with pytest.raises(RuntimeError, match="Cannot set room floor " + rejected):
        robot_scene._hide_room_ground(stage, room)
    assert stage.GetSessionLayer().ExportToString() == session_before

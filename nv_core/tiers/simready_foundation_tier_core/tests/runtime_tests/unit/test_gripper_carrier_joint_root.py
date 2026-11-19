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

"""Regression coverage for a gripper whose articulation root is a world joint.

All stages are synthetic. Runtime collaborators are faked so these tests exercise
the carrier's USD edits and lifecycle without requiring Kit or PhysX.
"""

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("pxr")
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402
from simready.foundation.tier_core.runtime_tests.articulation_phases import (  # noqa: E402
    gripper_carrier as carrier,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (  # noqa: E402
    RobotHandle,
)


def _rig(world_body="body1"):
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    stage.SetDefaultPrim(world)
    asset = UsdGeom.Xform.Define(stage, "/World/Imported/Gripper").GetPrim()
    base = UsdGeom.Xform.Define(stage, str(asset.GetPath()) + "/base").GetPrim()
    finger = UsdGeom.Xform.Define(stage, str(asset.GetPath()) + "/finger").GetPrim()
    for body in (base, finger):
        UsdPhysics.RigidBodyAPI.Apply(body)
    pin = UsdPhysics.FixedJoint.Define(stage, str(asset.GetPath()) + "/joints/world_pin")
    getattr(pin, f"Create{world_body.capitalize()}Rel")().SetTargets([base.GetPath()])
    UsdPhysics.ArticulationRootAPI.Apply(pin.GetPrim())
    slider = UsdPhysics.PrismaticJoint.Define(stage, str(asset.GetPath()) + "/joints/finger_slider")
    slider.CreateBody0Rel().SetTargets([base.GetPath()])
    slider.CreateBody1Rel().SetTargets([finger.GetPath()])
    return SimpleNamespace(stage=stage, asset=asset, base=base, finger=finger, pin=pin, slider=slider)


@pytest.mark.parametrize("world_body", ["body1", "body0"])
def test_fixed_joint_root_resolves_its_sibling_base_body(world_body):
    rig = _rig(world_body)

    assert carrier._resolve_articulation_root_body(rig.stage, str(rig.pin.GetPath())) == str(rig.base.GetPath())


def _container_rig(world_body="body1", reversed_slider=False):
    rig = _rig(world_body)
    rig.pin.GetPrim().RemoveAPI(UsdPhysics.ArticulationRootAPI)
    UsdPhysics.ArticulationRootAPI.Apply(rig.asset)
    if reversed_slider:
        rig.slider.CreateBody0Rel().SetTargets([rig.finger.GetPath()])
        rig.slider.CreateBody1Rel().SetTargets([rig.base.GetPath()])
    return rig


@pytest.mark.parametrize("world_body", ["body1", "body0"])
@pytest.mark.parametrize("reversed_slider", [False, True])
@pytest.mark.filterwarnings("ignore:LoadUsdPhysicsFromRange is deprecated:DeprecationWarning")
def test_container_root_prefers_native_world_anchor_over_slider_direction(world_body, reversed_slider):
    rig = _container_rig(world_body, reversed_slider)
    before = rig.stage.GetRootLayer().ExportToString()
    parsed = UsdPhysics.LoadUsdPhysicsFromRange(rig.stage, [rig.asset.GetPath()])
    _, articulations = parsed[UsdPhysics.ObjectType.Articulation]

    assert len(articulations) == 1
    assert articulations[0].isValid
    assert articulations[0].rootPrims == [rig.pin.GetPath()]
    assert carrier._resolve_articulation_root_body(
        rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath())
    ) == str(rig.base.GetPath())
    assert rig.stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("world_body", ["body1", "body0"])
def test_container_root_reuses_existing_world_pin_instead_of_pinning_the_reversed_jaw(world_body):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        _find_existing_world_pin,
    )

    rig = _container_rig(world_body, reversed_slider=True)
    body = carrier._resolve_articulation_root_body(rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath()))

    assert _find_existing_world_pin(rig.stage, rig.asset, body) == str(rig.pin.GetPath())
    assert not rig.stage.GetPrimAtPath("/World/_TestWorldPin")


@pytest.mark.parametrize("anchor_state", ["inactive", "disabled", "excluded"])
@pytest.mark.parametrize("reversed_slider", [False, True])
def test_container_root_ignores_inactive_disabled_or_excluded_anchors(anchor_state, reversed_slider):
    rig = _container_rig(reversed_slider=reversed_slider)
    if anchor_state == "inactive":
        rig.pin.GetPrim().SetActive(False)
    elif anchor_state == "disabled":
        rig.pin.CreateJointEnabledAttr(False)
        rig.pin.CreateBody1Rel().SetTargets(["/missing/ignored_disabled_endpoint"])
    else:
        rig.pin.CreateExcludeFromArticulationAttr(True)
    expected = rig.finger if reversed_slider else rig.base

    assert carrier._resolve_articulation_root_body(
        rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath())
    ) == str(expected.GetPath())


@pytest.mark.parametrize("second_endpoint", ["base", "finger"])
@pytest.mark.parametrize("world_body", ["body1", "body0"])
def test_container_root_rejects_multiple_active_world_anchors(second_endpoint, world_body):
    rig = _container_rig(world_body, reversed_slider=True)
    second_pin = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/joints/second_pin")
    second_pin.CreateBody0Rel().SetTargets([getattr(rig, second_endpoint).GetPath()])
    before = rig.stage.GetRootLayer().ExportToString()

    assert (
        carrier._resolve_articulation_root_body(rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath())) is None
    )
    assert rig.stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("world_body", ["body1", "body0"])
@pytest.mark.parametrize("invalid_case", ["missing", "multiple", "outside", "world_world", "self_joint"])
def test_container_root_rejects_malformed_or_out_of_scope_anchor_endpoints(world_body, invalid_case):
    rig = _container_rig(world_body, reversed_slider=True)
    endpoint = getattr(rig.pin, f"Create{world_body.capitalize()}Rel")()
    if invalid_case == "missing":
        endpoint.SetTargets(["/World/Imported/Gripper/missing"])
    elif invalid_case == "multiple":
        endpoint.SetTargets([rig.base.GetPath(), rig.finger.GetPath()])
    elif invalid_case == "outside":
        other = UsdGeom.Xform.Define(rig.stage, "/World/Other/base").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(other)
        endpoint.SetTargets([other.GetPath()])
    elif invalid_case == "world_world":
        endpoint.SetTargets([])
    else:
        other_body = "body0" if world_body == "body1" else "body1"
        getattr(rig.pin, f"Create{other_body.capitalize()}Rel")().SetTargets([rig.base.GetPath()])
    before = rig.stage.GetRootLayer().ExportToString()

    if invalid_case in {"missing", "multiple"}:
        with pytest.raises(RuntimeError, match="endpoint is missing|multiple targets"):
            carrier._resolve_articulation_root_body(rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath()))
    else:
        assert (
            carrier._resolve_articulation_root_body(rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath()))
            is None
        )
    assert rig.stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("invalid_case", ["disconnected", "cycle", "outside"])
def test_unanchored_container_fallback_rejects_unbounded_or_ambiguous_graphs(invalid_case):
    rig = _container_rig()
    rig.stage.RemovePrim(rig.pin.GetPath())
    if invalid_case == "disconnected":
        other = UsdGeom.Xform.Define(rig.stage, str(rig.asset.GetPath()) + "/disconnected").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(other)
    elif invalid_case == "cycle":
        back_edge = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/joints/back_edge")
        back_edge.CreateBody0Rel().SetTargets([rig.finger.GetPath()])
        back_edge.CreateBody1Rel().SetTargets([rig.base.GetPath()])
    else:
        other = UsdGeom.Xform.Define(rig.stage, "/World/Other/base").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(other)
        rig.slider.CreateBody0Rel().SetTargets([other.GetPath()])

    assert (
        carrier._resolve_articulation_root_body(rig.stage, str(rig.asset.GetPath()), str(rig.asset.GetPath())) is None
    )


@pytest.mark.parametrize("root_kind", ["container", "body", "joint"])
def test_root_resolution_is_bounded_to_the_selected_loaded_asset(root_kind):
    rig = _container_rig()
    root = {"container": rig.asset, "body": rig.base, "joint": rig.pin.GetPrim()}[root_kind]

    assert carrier._resolve_articulation_root_body(rig.stage, str(root.GetPath()), "/World/Other") is None


@pytest.mark.parametrize("world_body", ["body1", "body0"])
@pytest.mark.parametrize("merge_rail", [False, True])
def test_container_root_reversed_jaw_carrier_welds_base_and_restores_world_anchor(monkeypatch, world_body, merge_rail):
    rig = _container_rig(world_body, reversed_slider=True)
    robot = _Robot(rig)
    robot.set_articulation_root_path(rig.asset.GetPath())
    robot.articulation = _Articulation(rig, str(rig.asset.GetPath()))
    physics = _Physics()
    before = rig.stage.GetRootLayer().ExportToString()
    built = []

    def build(stage, body_path, position, **kwargs):
        built.append(body_path)
        assert not rig.pin.GetPrim().IsActive()
        _fake_gantry_builder(stage, body_path, position, **kwargs)

    monkeypatch.setattr(carrier, "_build_gantry", build)
    handle = asyncio.run(
        carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), merge_rail=merge_rail)
    )

    assert built == [str(rig.base.GetPath())]
    assert handle.world_pin_paths == (str(rig.pin.GetPath()),)
    asyncio.run(carrier.detach_carrier(rig.stage, handle))
    assert robot.prim_path == str(rig.asset.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert rig.stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("world_body", ["body1", "body0"])
def test_fixed_joint_root_suspends_only_its_own_world_pin(world_body):
    rig = _rig(world_body)
    other = UsdGeom.Xform.Define(rig.stage, "/World/Imported/Other/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(other)
    foreign = UsdPhysics.FixedJoint.Define(rig.stage, "/World/Imported/Other/world_pin")
    foreign.CreateBody1Rel().SetTargets([other.GetPath()])

    suspended = carrier._suspend_world_pins(rig.stage, str(rig.pin.GetPath()))

    assert suspended == (str(rig.pin.GetPath()),)
    assert not rig.pin.GetPrim().IsActive()
    assert foreign.GetPrim().IsActive()


def _world_transform(prim):
    return UsdGeom.XformCache().GetLocalToWorldTransform(prim)


def _assert_world_orientation(prim, expected):
    actual = _world_transform(prim)
    target = Gf.Matrix4d(1.0).SetRotate(Gf.Quatd(expected[0], Gf.Vec3d(*expected[1:])))
    for axis in (Gf.Vec3d(1, 0, 0), Gf.Vec3d(0, 1, 0), Gf.Vec3d(0, 0, 1)):
        assert Gf.IsClose(actual.TransformDir(axis).GetNormalized(), target.TransformDir(axis), 1e-6)


def _add_authored_transforms(rig, parent_angle=37.0, base_angle=90.0, scale=0.01):
    parent = UsdGeom.Xform(rig.stage.GetPrimAtPath("/World/Imported"))
    parent.AddTranslateOp().Set(Gf.Vec3d(4, -2, 7))
    parent.AddRotateZOp().Set(parent_angle)
    asset = UsdGeom.Xform(rig.asset)
    asset.AddTranslateOp().Set(Gf.Vec3d(0.5, -0.25, 0.75))
    asset.AddOrientOp().Set(Gf.Quatf(Gf.Rotation(Gf.Vec3d(1, 0, 0), 23).GetQuat()))
    asset.AddScaleOp().Set(Gf.Vec3f(scale))
    base = UsdGeom.Xform(rig.base)
    base.AddTranslateOp().Set(Gf.Vec3d(1, 2, 3))
    base.AddRotateYOp().Set(base_angle)
    UsdGeom.Xform(rig.finger).AddTranslateOp().Set(Gf.Vec3d(1, 4, 3))


@pytest.mark.parametrize("base_angle", [0.0, 90.0, -90.0, 180.0])
@pytest.mark.parametrize("parent_angle,scale", [(0.0, 1.0), (37.0, 0.01)])
def test_orientation_uses_base_world_frame_and_preserves_scaled_authored_offsets(base_angle, parent_angle, scale):
    rig = _rig()
    _add_authored_transforms(rig, parent_angle, base_angle, scale)
    base_local = UsdGeom.Xformable(rig.base).GetLocalTransformation()
    finger_local = UsdGeom.Xformable(rig.finger).GetLocalTransformation()
    anchor = _world_transform(rig.base).ExtractTranslation()
    before = rig.stage.GetRootLayer().ExportToString()
    snapshot = carrier._capture_root_orientation(rig.stage, str(rig.asset.GetPath()))
    desired = (0.0, 1.0, 0.0, 0.0)

    for _ in range(2):
        carrier._orient_gripper_base(rig.stage, str(rig.asset.GetPath()), str(rig.base.GetPath()), desired)
        _assert_world_orientation(rig.base, desired)
        assert Gf.IsClose(_world_transform(rig.base).ExtractTranslation(), anchor, 1e-6)
        assert Gf.IsClose(UsdGeom.Xformable(rig.base).GetLocalTransformation(), base_local, 1e-9)
        assert Gf.IsClose(UsdGeom.Xformable(rig.finger).GetLocalTransformation(), finger_local, 1e-9)
        assert UsdGeom.Xformable(rig.asset).GetLocalTransformation().GetDeterminant() == pytest.approx(scale**3)

    carrier._restore_root_orientation(rig.stage, str(rig.asset.GetPath()), snapshot)

    assert rig.stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("magnitude", [1e308, -1e308, 1e-300, np.nextafter(0.0, 1.0)])
@pytest.mark.filterwarnings("error::RuntimeWarning")
def test_orientation_normalizes_extreme_finite_quaternions_without_changing_the_input(magnitude):
    rig = _rig()
    _add_authored_transforms(rig)
    anchor = _world_transform(rig.base).ExtractTranslation()
    desired = np.asarray([magnitude, magnitude, 0.0, 0.0], dtype=np.float64)
    original = desired.copy()

    carrier._orient_gripper_base(rig.stage, str(rig.asset.GetPath()), str(rig.base.GetPath()), desired)

    half_root = float(np.sqrt(0.5))
    _assert_world_orientation(rig.base, (half_root, half_root, 0.0, 0.0))
    assert Gf.IsClose(_world_transform(rig.base).ExtractTranslation(), anchor, 1e-6)
    np.testing.assert_array_equal(desired, original)


@pytest.mark.parametrize(
    "quaternion",
    [(0, 0, 0, 0), (float("nan"), 0, 0, 0), (float("inf"), 0, 0, 0), (1, float("-inf"), 0, 0)],
)
def test_orientation_rejects_zero_or_nonfinite_quaternions_without_any_mutation(quaternion):
    rig = _rig()
    _add_authored_transforms(rig)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    desired = np.asarray(quaternion, dtype=np.float64)
    original = desired.copy()

    with pytest.raises(RuntimeError, match="finite nonzero quaternion"):
        carrier._orient_gripper_base(rig.stage, str(rig.asset.GetPath()), str(rig.base.GetPath()), desired)

    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    np.testing.assert_array_equal(desired, original)


def test_orientation_preserves_a_separate_mount_world_position():
    rig = _rig()
    _add_authored_transforms(rig)
    mount = UsdGeom.Xform.Define(rig.stage, str(rig.asset.GetPath()) + "/mount")
    mount.AddTranslateOp().Set(Gf.Vec3d(-1, 2, 0.5))
    mount_before = _world_transform(mount.GetPrim()).ExtractTranslation()
    base_local = UsdGeom.Xformable(rig.base).GetLocalTransformation()

    carrier._orient_gripper_base(
        rig.stage, str(rig.asset.GetPath()), str(rig.base.GetPath()), (0, 1, 0, 0), str(mount.GetPath())
    )

    _assert_world_orientation(rig.base, (0, 1, 0, 0))
    assert Gf.IsClose(_world_transform(mount.GetPrim()).ExtractTranslation(), mount_before, 1e-6)
    assert Gf.IsClose(UsdGeom.Xformable(rig.base).GetLocalTransformation(), base_local, 1e-9)


def test_orientation_rejects_a_base_disconnected_by_reset_transform_stack():
    rig = _rig()
    UsdGeom.Xformable(rig.base).SetResetXformStack(True)
    before = rig.stage.GetRootLayer().ExportToString()

    with pytest.raises(RuntimeError, match="reset transform stack"):
        carrier._orient_gripper_base(rig.stage, str(rig.asset.GetPath()), str(rig.base.GetPath()), (0, 1, 0, 0))

    assert rig.stage.GetRootLayer().ExportToString() == before


def test_world_pin_discovery_is_bounded_to_selected_body_graph_and_asset_scope():
    rig = _rig()
    disconnected = UsdGeom.Xform.Define(rig.stage, str(rig.asset.GetPath()) + "/unrelated_body").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(disconnected)
    disconnected_pin = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/joints/unrelated_pin")
    disconnected_pin.CreateBody1Rel().SetTargets([disconnected.GetPath()])
    foreign_body = UsdGeom.Xform.Define(rig.stage, "/World/Imported/Other/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(foreign_body)
    foreign_joint = UsdPhysics.FixedJoint.Define(rig.stage, "/World/Imported/Other/cross_asset_joint")
    foreign_joint.CreateBody0Rel().SetTargets([foreign_body.GetPath()])
    foreign_joint.CreateBody1Rel().SetTargets([rig.base.GetPath()])
    foreign_pin = UsdPhysics.FixedJoint.Define(rig.stage, "/World/Imported/Other/world_pin")
    foreign_pin.CreateBody1Rel().SetTargets([foreign_body.GetPath()])
    rig.asset.CreateRelationship("isaac:physics:robotJoints").SetTargets(
        [foreign_joint.GetPath(), foreign_pin.GetPath()]
    )

    root_body = carrier._resolve_articulation_root_body(rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath()))
    pins = carrier._suspend_world_pins(rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath()), root_body)

    assert root_body == str(rig.base.GetPath())
    assert pins == (str(rig.pin.GetPath()),)
    assert disconnected_pin.GetPrim().IsActive()
    assert foreign_pin.GetPrim().IsActive()
    assert foreign_joint.GetPrim().IsActive()


def test_framework_pin_path_does_not_authorize_disabling_a_foreign_robot_pin(monkeypatch):
    rig = _rig()
    foreign_body = UsdGeom.Xform.Define(rig.stage, "/World/Other/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(foreign_body)
    foreign_pin = UsdPhysics.FixedJoint.Define(rig.stage, "/World/framework_pin")
    foreign_pin.CreateBody1Rel().SetTargets([foreign_body.GetPath()])
    engine = ModuleType("simready.evaluate_engine_kit")
    engine.__path__ = []
    physics_utils = ModuleType("simready.evaluate_engine_kit.physics_utils")
    physics_utils.WORLD_PIN_PATH = str(foreign_pin.GetPath())
    monkeypatch.setitem(sys.modules, engine.__name__, engine)
    monkeypatch.setitem(sys.modules, physics_utils.__name__, physics_utils)

    pins = carrier._suspend_world_pins(
        rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath()), str(rig.base.GetPath())
    )

    assert pins == (str(rig.pin.GetPath()),)
    assert foreign_pin.GetPrim().IsActive()


@pytest.mark.parametrize("invalid_case", ["two_body_targets", "both_body_endpoints", "missing_body"])
def test_fixed_joint_root_rejects_ambiguous_or_invalid_topology(invalid_case):
    rig = _rig()
    if invalid_case == "two_body_targets":
        rig.pin.CreateBody1Rel().SetTargets([rig.base.GetPath(), rig.finger.GetPath()])
    elif invalid_case == "both_body_endpoints":
        rig.pin.CreateBody0Rel().SetTargets([rig.finger.GetPath()])
    else:
        rig.pin.CreateBody1Rel().SetTargets(["/World/Imported/Gripper/missing"])

    if invalid_case == "both_body_endpoints":
        assert (
            carrier._resolve_articulation_root_body(rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath())) is None
        )
    else:
        with pytest.raises(RuntimeError, match="multiple targets|endpoint is missing"):
            carrier._resolve_articulation_root_body(rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath()))


def test_joint_endpoint_resolves_owning_rigid_body_from_a_child_prim():
    rig = _rig("body0")
    collider = UsdGeom.Cube.Define(rig.stage, str(rig.base.GetPath()) + "/collider")
    rig.pin.CreateBody0Rel().SetTargets([collider.GetPath()])

    assert carrier._resolve_articulation_root_body(rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath())) == str(
        rig.base.GetPath()
    )


class _Physics:
    def __init__(self, playing=True):
        self.playing = playing
        self.stops = 0
        self.plays = 0

    def is_playing(self):
        return self.playing

    def stop(self):
        self.stops += 1
        self.playing = False

    def play(self):
        self.plays += 1
        self.playing = True


class _Articulation:
    def __init__(self, rig, bound_path=None):
        self.rig = rig
        self.bound_path = bound_path or str(rig.pin.GetPath())
        self.default_state = {
            "position": np.array([1.0, 2.0, 3.0]),
            "orientation": np.array([1.0, 0.0, 0.0, 0.0]),
        }
        self.joint_state = {
            "positions": np.array([0.1]),
            "velocities": np.array([0.2]),
            "efforts": np.array([0.3]),
        }

    def get_world_pose(self):
        transform = _world_transform(self.rig.base)
        quat = transform.ExtractRotationQuat()
        return np.array(transform.ExtractTranslation()), np.array([quat.GetReal(), *quat.GetImaginary()])

    def get_default_state(self):
        return SimpleNamespace(**self.default_state)

    def set_default_state(self, **kwargs):
        self.default_state.update(kwargs)

    def get_joints_default_state(self):
        return SimpleNamespace(**self.joint_state)

    def set_joints_default_state(self, **kwargs):
        self.joint_state.update(kwargs)

    def get_joint_positions(self):
        return self.joint_state["positions"]


class _Robot:
    def __init__(self, rig, reset_failure=False):
        self.rig = rig
        self.asset_prim = rig.asset
        self._robot_prim_path = str(rig.pin.GetPath())
        self.articulation = _Articulation(rig)
        self.initializations = []
        self.initialized_defaults = []
        self.resets = 0
        self.reset_failure = reset_failure
        self._world = SimpleNamespace(reset_async=self.reset_async)

    @property
    def prim_path(self):
        return self._robot_prim_path

    def set_articulation_root_path(self, path):
        self._robot_prim_path = str(path)

    async def initialize(self, ctx):
        self.initializations.append(self.prim_path)
        self.articulation = _Articulation(self.rig, self.prim_path)
        root = self.rig.base
        for prim in self.rig.stage.Traverse():
            if prim.IsA(UsdPhysics.FixedJoint) and prim.GetName() == "attach_joint":
                joint = UsdPhysics.FixedJoint(prim)
                if joint.GetExcludeFromArticulationAttr().Get() is False:
                    root = self.rig.stage.GetPrimAtPath(prim.GetPath().GetParentPath().AppendChild("gantry_base"))
        transform = _world_transform(root)
        rotation = Gf.Transform(transform).GetRotation().GetQuat().GetNormalized()
        self.articulation.default_state = {
            "position": np.asarray(transform.ExtractTranslation()),
            "orientation": np.asarray([rotation.GetReal(), *rotation.GetImaginary()]),
        }
        self.initialized_defaults.append(
            {name: value.copy() for name, value in self.articulation.default_state.items()}
        )
        self._world = SimpleNamespace(reset_async=self.reset_async)
        # RobotHandle.initialize already cooks and resets its fresh World.
        await self._world.reset_async()

    async def reset_async(self):
        self.resets += 1
        if self.reset_failure:
            self.reset_failure = False
            raise RuntimeError("injected reset failure")


def _fake_gantry_builder(stage, body_path, position, **kwargs):
    root_path = kwargs["root_path"]
    UsdGeom.Xform.Define(stage, root_path)
    gantry_base = UsdGeom.Xform.Define(stage, root_path + "/gantry_base")
    gantry_base.AddTranslateOp().Set(Gf.Vec3d(*position))
    UsdPhysics.RigidBodyAPI.Apply(gantry_base.GetPrim())
    lift = UsdGeom.Xform.Define(stage, root_path + "/lift")
    lift.AddTranslateOp().Set(Gf.Vec3d(*position))
    gantry_body = lift.GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(gantry_body)
    attach = UsdPhysics.FixedJoint.Define(stage, root_path + "/attach_joint")
    attach.CreateBody0Rel().SetTargets([gantry_body.GetPath()])
    attach.CreateBody1Rel().SetTargets([body_path])
    attach.CreateExcludeFromArticulationAttr(not kwargs.get("merge_into_articulation", False))


def _offset_site_rig():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        _read_gripper_site,
    )

    rig = _rig()
    UsdGeom.SetStageMetersPerUnit(rig.stage, 1.0)
    UsdGeom.Xform(rig.base).AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.1))
    UsdGeom.Xform(rig.finger).AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.1))
    rig.pin.CreateLocalPos0Attr().Set(Gf.Vec3f(0, 0, 0.1))
    body = UsdGeom.Xform.Define(rig.stage, str(rig.asset.GetPath()) + "/site_body")
    body.AddTranslateOp().Set(Gf.Vec3d(0.1, 0, 0.15))
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    mount = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/joints/site_mount")
    mount.CreateBody0Rel().SetTargets([rig.base.GetPath()])
    mount.CreateBody1Rel().SetTargets([body.GetPath()])
    mount.CreateLocalPos0Attr().Set(Gf.Vec3f(0.1, 0, 0.05))
    site = UsdGeom.Xform.Define(rig.stage, str(body.GetPath()) + "/site")
    site.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.05))
    site.GetPrim().CreateAttribute("simready:attactment:socketType", Sdf.ValueTypeNames.Token).Set("Gripper")
    site.GetPrim().CreateAttribute("gripper_maxOpening", Sdf.ValueTypeNames.Float).Set(0.1)
    site.GetPrim().CreateAttribute("gripper_maxPayload", Sdf.ValueTypeNames.Float).Set(1.0)
    for name, points in (
        ("gripper_forward_axis", [(0, 0, 0), (0, 0, 0.05)]),
        ("gripper_grip_line", [(-0.025, 0, 0), (0.025, 0, 0)]),
    ):
        curve = UsdGeom.BasisCurves.Define(rig.stage, str(site.GetPath()) + "/" + name)
        curve.CreatePointsAttr(points)
        curve.CreateCurveVertexCountsAttr([2])
        curve.CreateTypeAttr(UsdGeom.Tokens.linear)
    rig.site_body = body.GetPrim()
    rig.site = _read_gripper_site(site.GetPrim())
    assert rig.site is not None
    return rig


@pytest.mark.parametrize("orientation", ["parallel_jaw", "hand", None])
def test_offset_site_prediction_matches_carrier_pivot_and_restores_authored_pose(monkeypatch, orientation):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        gripper_close_lift as phase,
    )

    rig = _offset_site_rig()
    before = rig.stage.GetRootLayer().ExportToString()
    if orientation == "parallel_jaw":
        desired, predicted, _ = phase._compute_approach_orientation(
            rig.stage, str(rig.site_body.GetPath()), rig.site, (0, 0, -1), pivot_path=str(rig.base.GetPath())
        )
    elif orientation == "hand":
        desired, predicted, _ = phase._authored_hand_orientation(
            rig.stage, str(rig.site_body.GetPath()), rig.site, pivot_path=str(rig.base.GetPath())
        )
    else:
        desired, predicted = None, rig.site.grasp_center_world_initial()
    robot = _Robot(rig)
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    handle = asyncio.run(
        carrier.attach_carrier(
            rig.stage, {"physics": physics}, robot, str(rig.site_body.GetPath()), desired, merge_rail=True
        )
    )

    actual = np.asarray(_world_transform(rig.stage.GetPrimAtPath(rig.site.prim_path)).ExtractTranslation())
    np.testing.assert_allclose(predicted, actual, atol=1e-8)
    spawn = phase._authored_spawn_position(predicted, 0.04)
    np.testing.assert_allclose(spawn[:2], actual[:2], atol=1e-8)
    asyncio.run(carrier.detach_carrier(rig.stage, handle))
    assert rig.stage.GetRootLayer().ExportToString() == before
    assert robot.prim_path == str(rig.pin.GetPath())
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("kind", ["mimic_parallel_jaw", "independent_fingers"])
@pytest.mark.parametrize("shape", ["cube", "sphere"])
def test_trial_mapping_standoff_and_spawn_follow_the_offset_site_after_attachment(monkeypatch, kind, shape):
    from simready.foundation.tier_core.runtime_tests import engine_guard
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        fingertip_discovery,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        gripper_close_lift as phase,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        object_spawning,
    )

    rig = _offset_site_rig()
    before = rig.stage.GetRootLayer().ExportToString()
    robot = _Robot(rig)
    robot.dof_names = ["finger_slider"]
    robot.get_joint_positions = robot.articulation.get_joint_positions
    robot.get_joint_position_limits = lambda: (np.array([0.0]), np.array([1.0]))
    fingertips = fingertip_discovery.FingertipSet(
        kind=kind,
        tip_link_paths=[],
        mimic_master_dof=0,
        mimic_follower_dof=None,
        finger_chains=[[0]],
        master_open_closed_positions={0: (0.0, 1.0)},
    )
    metrics, moves, mapped = {}, [], []
    scene = SimpleNamespace(stage=rig.stage, enable_ground_plane=lambda: None)
    ctx = SimpleNamespace(
        scene=scene, add_metric=metrics.__setitem__, log=lambda message: None, warn=lambda message: None
    )
    config = dict(phase.get_defaults(), shapes=[shape], disable_capture=True)
    scene_info = {"physics": _Physics(), "asset_handle": SimpleNamespace(prim_path=str(rig.asset.GetPath()))}

    async def no_ticks(*args, **kwargs):
        pass

    async def map_hand(ctx, robot, fingertips, stage, config, center, base_path):
        actual = _world_transform(stage.GetPrimAtPath(rig.site.prim_path)).ExtractTranslation()
        np.testing.assert_allclose(center, actual, atol=1e-8)
        mapped.append(np.asarray(center).copy())
        return [{"idx": 0, "open": 0.0, "closed": 1.0, "name": "finger_slider"}], []

    async def map_jaw(*args):
        return 0.0, 1.0

    async def translate(**kwargs):
        moves.append(np.asarray(kwargs["delta_world"]).copy())

    class StopAfterSpawn(RuntimeError):
        pass

    def spawn(**kwargs):
        authored_after_attach = np.asarray(
            _world_transform(rig.stage.GetPrimAtPath(rig.site.prim_path)).ExtractTranslation()
        )
        actual = authored_after_attach + sum(moves, np.zeros(3))
        position = kwargs["pose_world"][3, :3]
        np.testing.assert_allclose(position[:2], actual[:2], atol=1e-8)
        standoff = kwargs["size_m"] + config["approach_extra_clearance_m"]
        assert actual[2] == pytest.approx(position[2] + standoff)
        raise StopAfterSpawn("spawn alignment checked")

    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None)
    monkeypatch.setattr(fingertip_discovery, "discover_fingertips", lambda *args: fingertips)
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)
    monkeypatch.setattr(carrier, "linear_translate", translate)
    monkeypatch.setattr(phase, "_reset_world", no_ticks)
    monkeypatch.setattr(phase, "_settle_for_seconds", no_ticks)
    monkeypatch.setattr(phase, "_detect_open_closed_positions", map_jaw)
    monkeypatch.setattr(phase, "_infer_hand_grasp_specs", map_hand)
    monkeypatch.setattr(phase, "_command_grasp_targets", lambda *args: None)
    monkeypatch.setattr(object_spawning, "spawn_test_object", spawn)

    with pytest.raises(StopAfterSpawn, match="spawn alignment checked"):
        asyncio.run(phase.run_gripper_close_lift(ctx, robot, scene_info, config))

    assert moves
    assert bool(mapped) == (kind == "independent_fingers")
    assert rig.stage.GetRootLayer().ExportToString() == before
    assert rig.pin.GetPrim().IsActive()
    assert robot.prim_path == str(rig.pin.GetPath())
    _assert_defaults_restored(robot)


def _assert_defaults_restored(robot):
    for name, expected in {"position": [1, 2, 3], "orientation": [1, 0, 0, 0]}.items():
        np.testing.assert_array_equal(robot.articulation.default_state[name], expected)
    for name, expected in {"positions": [0.1], "velocities": [0.2], "efforts": [0.3]}.items():
        np.testing.assert_array_equal(robot.articulation.joint_state[name], expected)


def test_content_boundary_uses_loaded_asset_instead_of_joint_parent():
    rig = _rig()
    robot = _Robot(rig)

    assert carrier._carrier_asset_root(rig.stage, robot, str(rig.base.GetPath())) == str(rig.asset.GetPath())


def test_content_boundary_rejects_an_unrelated_loaded_asset():
    rig = _rig()
    robot = _Robot(rig)
    robot.asset_prim = UsdGeom.Xform.Define(rig.stage, "/World/Other").GetPrim()

    with pytest.raises(RuntimeError, match="asset boundary"):
        carrier._carrier_asset_root(rig.stage, robot, str(rig.base.GetPath()))


def test_root_transfer_copies_settings_and_restores_after_controller_rebind_failure(monkeypatch):
    rig = _rig()
    root_setting = rig.pin.GetPrim().CreateAttribute(
        "physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int
    )
    root_setting.Set(32)
    root_setting.Set(64, 2.0)
    UsdPhysics.MassAPI.Apply(rig.base)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    robot = _Robot(rig)
    before = rig.stage.GetSessionLayer().ExportToString()
    setup_state = {}
    original_setter = robot.set_articulation_root_path

    def fail_after_rebinding(path):
        original_setter(path)
        if path == str(rig.base.GetPath()):
            assert setup_state["articulation_root_transfer"]["robot_path"] == str(rig.pin.GetPath())
            assert rig.base.GetAttribute(root_setting.GetName()).Get() == 32
            assert rig.base.GetAttribute(root_setting.GetName()).Get(2.0) == 64
            raise RuntimeError("injected controller rebind failure")

    monkeypatch.setattr(robot, "set_articulation_root_path", fail_after_rebinding)

    with pytest.raises(RuntimeError, match="injected controller rebind failure"):
        carrier._transfer_joint_root_for_carrier(rig.stage, robot, str(rig.base.GetPath()), setup_state)

    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.base.HasAPI(UsdPhysics.MassAPI)
    assert rig.base.HasAPI(UsdPhysics.RigidBodyAPI)
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert rig.stage.GetSessionLayer().ExportToString() == before


@pytest.mark.parametrize("world_body", ["body1", "body0"])
@pytest.mark.parametrize("edit_layer", ["root", "session"])
def test_attach_detach_restores_joint_controller_and_all_authored_opinions(monkeypatch, world_body, edit_layer):
    rig = _rig(world_body)
    _add_authored_transforms(rig)
    rig.pin.GetPrim().CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    rig.base.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(8)
    rig.pin.GetPrim().SetActive(True)
    if edit_layer == "session":
        rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
        UsdGeom.Xformable(rig.asset).GetOrderedXformOps()[1].Set(Gf.Quatf(Gf.Rotation(Gf.Vec3d(1, 0, 0), 11).GetQuat()))
        rig.base.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(12)
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    mount_before = _world_transform(rig.base).ExtractTranslation()
    robot = _Robot(rig)
    physics = _Physics()
    built = []

    def build(stage, body_path, position, **kwargs):
        built.append((body_path, position))
        assert not rig.pin.GetPrim().IsActive()
        assert robot.prim_path == str(rig.base.GetPath())
        assert rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
        _assert_world_orientation(rig.base, (0, 1, 0, 0))
        _fake_gantry_builder(stage, body_path, position, **kwargs)

    monkeypatch.setattr(carrier, "_build_gantry", build)
    handle = asyncio.run(
        carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
    )

    assert built[0][0] == str(rig.base.GetPath())
    assert Gf.IsClose(Gf.Vec3d(*built[0][1]), mount_before, 1e-6)
    assert handle.world_pin_paths == (str(rig.pin.GetPath()),)
    assert physics.playing
    asyncio.run(carrier.detach_carrier(rig.stage, handle))

    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert rig.pin.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.stage.GetPrimAtPath(handle.root_path)
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert physics.playing
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("failure_point", ["build", "reset"])
@pytest.mark.parametrize("initially_playing", [True, False])
def test_attach_failure_restores_controller_root_settings_and_orientation(
    monkeypatch, failure_point, initially_playing
):
    rig = _rig()
    _add_authored_transforms(rig)
    rig.pin.GetPrim().CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    robot = _Robot(rig, reset_failure=failure_point == "reset")
    physics = _Physics(initially_playing)
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()

    def build(stage, body_path, position, **kwargs):
        _fake_gantry_builder(stage, body_path, position, **kwargs)
        if failure_point == "build":
            raise RuntimeError("injected build failure")

    monkeypatch.setattr(carrier, "_build_gantry", build)

    with pytest.raises(RuntimeError, match="injected build failure|articulation re-cook failed"):
        asyncio.run(
            carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
        )

    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert rig.pin.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert physics.playing is initially_playing
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    _assert_defaults_restored(robot)


def test_attach_rejects_an_ambiguous_joint_root_before_mutating_stage(monkeypatch):
    rig = _rig()
    rig.pin.CreateBody1Rel().SetTargets([rig.base.GetPath(), rig.finger.GetPath()])
    robot = _Robot(rig)
    physics = _Physics()
    before = rig.stage.GetRootLayer().ExportToString()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    with pytest.raises(RuntimeError):
        asyncio.run(
            carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
        )

    assert rig.stage.GetRootLayer().ExportToString() == before
    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert physics.stops == 0
    assert physics.plays == 0


def test_attachment_orients_a_nonroot_site_body_while_welding_the_physical_root(monkeypatch):
    rig = _rig()
    _add_authored_transforms(rig)
    site = UsdGeom.Xform.Define(rig.stage, str(rig.asset.GetPath()) + "/gripper_site_body")
    site.AddTranslateOp().Set(Gf.Vec3d(-2, 1, 5))
    site.AddRotateYOp().Set(90.0)
    UsdPhysics.RigidBodyAPI.Apply(site.GetPrim())
    fixed = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/joints/site_fixed")
    fixed.CreateBody0Rel().SetTargets([rig.base.GetPath()])
    fixed.CreateBody1Rel().SetTargets([site.GetPath()])
    root_anchor = _world_transform(rig.base).ExtractTranslation()
    local_site = site.GetLocalTransformation()
    before = rig.stage.GetRootLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    built_bodies = []

    def build(stage, body_path, position, **kwargs):
        built_bodies.append(body_path)
        assert body_path == str(rig.base.GetPath())
        assert Gf.IsClose(Gf.Vec3d(*position), root_anchor, 1e-6)
        _assert_world_orientation(site.GetPrim(), (0, 1, 0, 0))
        assert Gf.IsClose(_world_transform(rig.base).ExtractTranslation(), root_anchor, 1e-6)
        assert Gf.IsClose(site.GetLocalTransformation(), local_site, 1e-9)
        _fake_gantry_builder(stage, body_path, position, **kwargs)

    monkeypatch.setattr(carrier, "_build_gantry", build)
    handle = asyncio.run(
        carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(site.GetPath()), (0, 1, 0, 0))
    )

    assert built_bodies == [str(rig.base.GetPath())]
    _assert_world_orientation(rig.base, robot.articulation.default_state["orientation"])
    asyncio.run(carrier.detach_carrier(rig.stage, handle))
    assert rig.stage.GetRootLayer().ExportToString() == before
    assert robot.prim_path == str(rig.pin.GetPath())
    _assert_defaults_restored(robot)


def test_orientation_attachment_rejects_a_content_root_with_an_independently_pinned_body(monkeypatch):
    rig = _rig()
    other = UsdGeom.Xform.Define(rig.stage, str(rig.asset.GetPath()) + "/other_robot/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(other)
    other_pin = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/other_robot/world_pin")
    other_pin.CreateBody1Rel().SetTargets([other.GetPath()])
    UsdPhysics.ArticulationRootAPI.Apply(other_pin.GetPrim())
    before = rig.stage.GetRootLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    with pytest.raises(RuntimeError):
        asyncio.run(
            carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
        )

    assert rig.stage.GetRootLayer().ExportToString() == before
    assert rig.pin.GetPrim().IsActive()
    assert other_pin.GetPrim().IsActive()
    assert physics.stops == 0
    assert physics.plays == 0


@pytest.mark.parametrize("cancel_again_during_cleanup", [False, True])
def test_task_cancellation_during_recook_finishes_restoration_before_propagating(
    monkeypatch, cancel_again_during_cleanup
):
    rig = _rig()
    _add_authored_transforms(rig)
    rig.pin.GetPrim().CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    rig.base.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(12)
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    async def exercise_cancellation():
        recook_started = asyncio.Event()
        restore_reset_started = asyncio.Event()
        finish_restore_reset = asyncio.Event()
        restore_reset_finished = asyncio.Event()

        async def gated_reset():
            robot.resets += 1
            if robot.resets == 1:
                recook_started.set()
                await asyncio.Future()
            else:
                restore_reset_started.set()
                await finish_restore_reset.wait()
                restore_reset_finished.set()

        monkeypatch.setattr(robot, "reset_async", gated_reset)
        task = asyncio.create_task(
            carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
        )
        await asyncio.wait_for(recook_started.wait(), timeout=2)
        assert robot.prim_path == str(rig.base.GetPath())
        assert not rig.pin.GetPrim().IsActive()
        assert rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
        task.cancel("cancel attachment during re-cook")
        await asyncio.wait_for(restore_reset_started.wait(), timeout=2)
        assert rig.stage.GetRootLayer().ExportToString() == root_before
        assert rig.stage.GetSessionLayer().ExportToString() == session_before
        assert robot.prim_path == str(rig.pin.GetPath())
        if cancel_again_during_cleanup:
            task.cancel("cancel again during restoration")
            await asyncio.sleep(0)
            assert not task.done()
            assert not restore_reset_finished.is_set()
        finish_restore_reset.set()
        with pytest.raises(asyncio.CancelledError, match="cancel attachment during re-cook"):
            await asyncio.wait_for(task, timeout=2)
        assert restore_reset_finished.is_set()

    asyncio.run(exercise_cancellation())

    assert robot.resets == 3
    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert rig.pin.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert physics.playing
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    _assert_defaults_restored(robot)


def test_detach_attempts_every_pin_and_remaining_restoration_when_one_pin_fails(monkeypatch):
    rig = _rig()
    _add_authored_transforms(rig)
    second_pin = UsdPhysics.FixedJoint.Define(rig.stage, str(rig.asset.GetPath()) + "/joints/second_world_pin")
    second_pin.CreateBody0Rel().SetTargets([rig.finger.GetPath()])
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)
    handle = asyncio.run(
        carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
    )
    assert set(handle.world_pin_paths) == {str(rig.pin.GetPath()), str(second_pin.GetPath())}
    assert not second_pin.GetPrim().IsActive()
    robot.articulation.set_joints_default_state(
        positions=np.array([7]), velocities=np.array([8]), efforts=np.array([9])
    )
    attempts = []
    original_restore = carrier._restore_world_pin

    def fail_first_pin(stage, path, state=None):
        attempts.append(path)
        if path == str(rig.pin.GetPath()):
            return False
        return original_restore(stage, path, state)

    monkeypatch.setattr(carrier, "_restore_world_pin", fail_first_pin)
    warnings = []
    ctx = SimpleNamespace(warn=warnings.append)

    with pytest.raises(RuntimeError, match="detach restoration failed.*world pin") as failure:
        asyncio.run(carrier.detach_carrier(rig.stage, handle, ctx=ctx))

    assert str(rig.pin.GetPath()) in str(failure.value)
    assert set(attempts) == set(handle.world_pin_paths)
    assert second_pin.GetPrim().IsActive()
    assert not rig.pin.GetPrim().IsActive()
    assert robot.prim_path == str(rig.pin.GetPath())
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.stage.GetPrimAtPath(handle.root_path)
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert not rig.asset.GetAttribute("xformOp:transform:fet028Approach").HasAuthoredValueOpinion()
    assert physics.playing
    assert robot.initializations[-1] == str(rig.pin.GetPath())
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    assert robot.resets == 3
    assert warnings
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("edit_layer", ["root", "session"])
def test_detach_rebuilds_the_original_controller_binding_and_preserves_a_stopped_timeline(monkeypatch, edit_layer):
    rig = _rig()
    _add_authored_transforms(rig)
    if edit_layer == "session":
        rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics(False)
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)
    handle = asyncio.run(
        carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
    )
    assert robot.articulation.bound_path == str(rig.base.GetPath())
    assert handle.physics_was_playing is False

    asyncio.run(carrier.detach_carrier(rig.stage, handle))

    assert robot.prim_path == str(rig.pin.GetPath())
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    assert robot.initializations[-1] == str(rig.pin.GetPath())
    assert physics.playing is False
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert rig.pin.GetPrim().IsActive()
    _assert_defaults_restored(robot)


def test_world_pin_suspension_records_restoration_before_a_partial_usd_mutation(monkeypatch):
    rig = _rig()
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    setup_state = {}
    original_set_active = Usd.Prim.SetActive

    def mutate_then_fail(prim, active):
        result = original_set_active(prim, active)
        if prim.GetPath() == rig.pin.GetPath() and active is False:
            assert setup_state["world_pin_paths"] == (str(rig.pin.GetPath()),)
            assert str(rig.pin.GetPath()) in setup_state["world_pin_states"]
            raise RuntimeError("injected failure after deactivation")
        return result

    monkeypatch.setattr(Usd.Prim, "SetActive", mutate_then_fail)

    with pytest.raises(RuntimeError, match="failed to suspend") as failure:
        carrier._suspend_world_pins(
            rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath()), str(rig.base.GetPath()), setup_state
        )

    assert "injected failure after deactivation" in str(failure.value.__cause__)
    assert rig.pin.GetPrim().IsActive()
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before


def _real_robot_handle_with_cached_root(rig):
    robot = RobotHandle.__new__(RobotHandle)
    robot._stage = rig.stage
    robot._asset_prim = rig.asset
    robot._robot_prim_path = str(rig.pin.GetPath())
    robot._root_prim = rig.pin.GetPrim()
    robot._initialized = True
    robot._articulation = _Articulation(rig)
    return robot


def test_robot_handle_rebinding_a_valid_root_invalidates_cached_prim_and_initialization():
    rig = _rig()
    robot = _real_robot_handle_with_cached_root(rig)
    original_articulation = robot.articulation
    before = rig.stage.GetRootLayer().ExportToString()

    robot.set_articulation_root_path(rig.base.GetPath())

    assert robot.prim_path == str(rig.base.GetPath())
    assert robot.root_prim is None
    assert robot._initialized is False
    assert robot.articulation is original_articulation
    assert robot.asset_prim == rig.asset
    assert rig.stage.GetRootLayer().ExportToString() == before


def test_robot_handle_rejects_a_missing_rebinding_target_without_changing_controller_state():
    rig = _rig()
    robot = _real_robot_handle_with_cached_root(rig)
    original_articulation = robot.articulation
    before = rig.stage.GetRootLayer().ExportToString()

    with pytest.raises(RuntimeError, match="missing prim"):
        robot.set_articulation_root_path("/World/Imported/Gripper/missing")

    assert robot.prim_path == str(rig.pin.GetPath())
    assert robot.root_prim == rig.pin.GetPrim()
    assert robot._initialized is True
    assert robot.articulation is original_articulation
    assert rig.stage.GetRootLayer().ExportToString() == before


def test_successful_trial_cleanup_preserves_detach_cancellation(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_close_lift import (
        _detach_trial_carrier,
    )

    async def cancelled_detach(stage, handle, ctx=None):
        raise asyncio.CancelledError("cancel trial cleanup")

    monkeypatch.setattr(carrier, "detach_carrier", cancelled_detach)

    with pytest.raises(asyncio.CancelledError, match="cancel trial cleanup"):
        asyncio.run(_detach_trial_carrier(None, None, SimpleNamespace()))


@pytest.mark.parametrize("edit_layer", ["root", "session"])
def test_transfer_replaces_blocked_defaults_and_stale_samples_then_detach_restores_exact_opinions(
    monkeypatch, edit_layer
):
    rig = _rig()
    blocked_name = "physxArticulation:solverPositionIterationCount"
    sampled_name = "physxArticulation:solverVelocityIterationCount"
    blocked_source = rig.pin.GetPrim().CreateAttribute(blocked_name, Sdf.ValueTypeNames.Int)
    blocked_source.Block()
    sampled_source = rig.pin.GetPrim().CreateAttribute(sampled_name, Sdf.ValueTypeNames.Int)
    sampled_source.Set(4)
    sampled_source.Set(10, 1.0)
    sampled_source.Set(20, 2.0)
    blocked_destination = rig.base.CreateAttribute(blocked_name, Sdf.ValueTypeNames.Int)
    blocked_destination.Set(8)
    blocked_destination.Set(12, 3.0)
    sampled_destination = rig.base.CreateAttribute(sampled_name, Sdf.ValueTypeNames.Int)
    sampled_destination.Set(2)
    sampled_destination.Set(100, 10.0)
    sampled_destination.Set(200, 20.0)
    if edit_layer == "session":
        rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    handle = asyncio.run(carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath())))

    copied_block = rig.base.GetAttribute(blocked_name)
    assert copied_block.HasAuthoredValueOpinion()
    assert copied_block.Get() is None
    assert copied_block.GetTimeSamples() == []
    assert copied_block.GetPropertyStack()[0].default == Sdf.ValueBlock()
    copied_samples = rig.base.GetAttribute(sampled_name)
    assert copied_samples.Get() == 4
    assert copied_samples.GetTimeSamples() == [1.0, 2.0]
    assert copied_samples.Get(1.0) == 10
    assert copied_samples.Get(2.0) == 20

    asyncio.run(carrier.detach_carrier(rig.stage, handle))

    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert rig.base.GetAttribute(blocked_name).Get() == 8
    assert rig.base.GetAttribute(blocked_name).GetTimeSamples() == [3.0]
    assert rig.base.GetAttribute(blocked_name).Get(3.0) == 12
    assert rig.base.GetAttribute(sampled_name).Get() == 2
    assert rig.base.GetAttribute(sampled_name).GetTimeSamples() == [10.0, 20.0]
    assert rig.base.GetAttribute(sampled_name).Get(10.0) == 100
    assert rig.base.GetAttribute(sampled_name).Get(20.0) == 200
    assert robot.articulation.bound_path == str(rig.pin.GetPath())


def test_detach_task_cancellation_waits_for_its_restored_controller_to_finish_recooking(monkeypatch):
    rig = _rig()
    _add_authored_transforms(rig)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    async def exercise_cancellation():
        handle = await carrier.attach_carrier(
            rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0)
        )
        reset_started = asyncio.Event()
        finish_reset = asyncio.Event()
        reset_finished = asyncio.Event()

        async def gated_restore_reset():
            reset_started.set()
            await finish_reset.wait()
            reset_finished.set()

        monkeypatch.setattr(robot, "reset_async", gated_restore_reset)
        task = asyncio.create_task(carrier.detach_carrier(rig.stage, handle))
        await asyncio.wait_for(reset_started.wait(), timeout=2)
        task.cancel("cancel detachment during re-cook")
        await asyncio.sleep(0)
        assert not task.done()
        assert not reset_finished.is_set()
        finish_reset.set()
        with pytest.raises(asyncio.CancelledError, match="cancel detachment during re-cook"):
            await asyncio.wait_for(task, timeout=2)
        assert reset_finished.is_set()

    asyncio.run(exercise_cancellation())

    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert robot.prim_path == str(rig.pin.GetPath())
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert physics.playing
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("stronger_opinion", ["articulation_setting", "world_pin_active", "orientation_order"])
def test_attach_rejects_stronger_session_opinions_that_override_temporary_root_edits(monkeypatch, stronger_opinion):
    rig = _rig()
    _add_authored_transforms(rig)
    setting_name = "physxArticulation:solverPositionIterationCount"
    rig.pin.GetPrim().CreateAttribute(setting_name, Sdf.ValueTypeNames.Int).Set(32)
    rig.base.CreateAttribute(setting_name, Sdf.ValueTypeNames.Int).Set(8)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    if stronger_opinion == "articulation_setting":
        rig.base.CreateAttribute(setting_name, Sdf.ValueTypeNames.Int).Set(12)
    elif stronger_opinion == "world_pin_active":
        rig.pin.GetPrim().SetActive(True)
    else:
        order = rig.asset.GetAttribute("xformOpOrder")
        order.Set(order.Get())
    rig.stage.SetEditTarget(rig.stage.GetRootLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    builds = []

    def build(stage, body_path, position, **kwargs):
        builds.append(body_path)
        _fake_gantry_builder(stage, body_path, position, **kwargs)

    monkeypatch.setattr(carrier, "_build_gantry", build)

    with pytest.raises(RuntimeError):
        asyncio.run(
            carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
        )

    assert builds == []
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    assert robot.prim_path == str(rig.pin.GetPath())
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert rig.pin.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert rig.base.GetAttribute(setting_name).Get() == (12 if stronger_opinion == "articulation_setting" else 8)
    assert physics.playing
    _assert_defaults_restored(robot)


def test_pin_suspension_rejects_an_authored_deactivation_shadowed_by_stronger_active_metadata():
    rig = _rig()
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    rig.pin.GetPrim().SetActive(True)
    rig.stage.SetEditTarget(rig.stage.GetRootLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    setup_state = {}

    with pytest.raises(RuntimeError, match="failed to suspend"):
        carrier._suspend_world_pins(
            rig.stage, str(rig.pin.GetPath()), str(rig.asset.GetPath()), str(rig.base.GetPath()), setup_state
        )

    assert setup_state["world_pin_paths"] == (str(rig.pin.GetPath()),)
    assert str(rig.pin.GetPath()) in setup_state["world_pin_states"]
    assert rig.pin.GetPrim().IsActive()
    assert rig.pin.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before


@pytest.mark.parametrize("root_setting", ["absent", "schema_fallback"])
@pytest.mark.parametrize("completion", ["detach", "build_failure"])
def test_destination_only_setting_cannot_become_active_when_the_joint_root_is_transferred(
    monkeypatch, root_setting, completion
):
    rig = _rig()
    setting_name = "physxArticulation:enabledSelfCollisions"
    expected_default = None
    original_default = True
    if root_setting == "schema_fallback":
        try:
            from pxr import PhysxSchema
        except ImportError:
            try:
                from physx_usd_schemas import PhysxSchema
            except ImportError:
                pytest.skip("PhysxSchema is required to test an actual schema fallback")
        PhysxSchema.PhysxArticulationAPI.Apply(rig.pin.GetPrim())
        source = rig.pin.GetPrim().GetAttribute(setting_name)
        assert not source.HasAuthoredValueOpinion()
        expected_default = source.Get()
        assert isinstance(expected_default, bool)
        original_default = not expected_default
    else:
        assert not rig.pin.GetPrim().GetAttribute(setting_name)
    destination = rig.base.CreateAttribute(setting_name, Sdf.ValueTypeNames.Bool)
    destination.Set(original_default)
    destination.Set(not original_default, 1.0)
    destination.Set(original_default, 2.0)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    builds = []

    def build(stage, body_path, position, **kwargs):
        builds.append(body_path)
        copied = rig.base.GetAttribute(setting_name)
        assert copied.Get() is expected_default
        assert copied.GetTimeSamples() == []
        if root_setting == "absent":
            assert copied.GetPropertyStack()[0].default == Sdf.ValueBlock()
        _fake_gantry_builder(stage, body_path, position, **kwargs)
        if completion == "build_failure":
            raise RuntimeError("injected destination-only setting build failure")

    monkeypatch.setattr(carrier, "_build_gantry", build)
    if completion == "build_failure":
        with pytest.raises(RuntimeError, match="injected destination-only setting build failure"):
            asyncio.run(carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath())))
    else:
        handle = asyncio.run(carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath())))
        asyncio.run(carrier.detach_carrier(rig.stage, handle))

    assert builds == [str(rig.base.GetPath())]
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    restored = rig.base.GetAttribute(setting_name)
    assert restored.Get() is original_default
    assert restored.GetTimeSamples() == [1.0, 2.0]
    assert restored.Get(1.0) is not original_default
    assert restored.Get(2.0) is original_default
    assert robot.prim_path == str(rig.pin.GetPath())
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("initially_playing", [False, True])
def test_live_pose_failure_before_stopping_physics_preserves_timeline_and_controller(monkeypatch, initially_playing):
    rig = _rig()
    _add_authored_transforms(rig)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    original_articulation = robot.articulation
    original_world = robot._world
    physics = _Physics(initially_playing)

    def failing_live_pose(paths):
        assert paths == [str(rig.base.GetPath())]
        raise RuntimeError("injected live pose read failure")

    monkeypatch.setattr(robot, "get_link_world_transforms", failing_live_pose, raising=False)
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    with pytest.raises(RuntimeError, match="injected live pose read failure"):
        asyncio.run(
            carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0))
        )

    assert physics.stops == 0
    assert physics.plays == 0
    assert physics.playing is initially_playing
    assert robot.initializations == []
    assert robot.resets == 0
    assert robot.articulation is original_articulation
    assert robot._world is original_world
    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert not rig.base.HasAPI(UsdPhysics.ArticulationRootAPI)
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("initially_playing", [False, True])
def test_partial_physics_stop_failure_still_restores_the_original_timeline(monkeypatch, initially_playing):
    rig = _rig()
    robot = _Robot(rig)
    physics = _Physics(initially_playing)
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    original_stop = physics.stop

    def mutate_then_fail():
        original_stop()
        if physics.stops == 1:
            raise RuntimeError("injected failure after physics stop")

    monkeypatch.setattr(physics, "stop", mutate_then_fail)
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    with pytest.raises(RuntimeError, match="injected failure after physics stop"):
        asyncio.run(carrier.attach_carrier(rig.stage, {"physics": physics}, robot, str(rig.base.GetPath())))

    assert physics.playing is initially_playing
    assert robot.initializations == [str(rig.pin.GetPath())]
    assert robot.articulation.bound_path == str(rig.pin.GetPath())
    assert rig.pin.GetPrim().IsActive()
    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("scale", [0.01, 2.0])
def test_scaled_attach_reset_default_matches_the_physical_root_rotation(monkeypatch, scale):
    rig = _rig()
    _add_authored_transforms(rig, scale=scale)
    rig.stage.SetEditTarget(rig.stage.GetSessionLayer())
    root_before = rig.stage.GetRootLayer().ExportToString()
    session_before = rig.stage.GetSessionLayer().ExportToString()
    robot = _Robot(rig)
    physics = _Physics()
    desired_quat = Gf.Rotation(Gf.Vec3d(0, 1, 0), 90).GetQuat()
    desired = (desired_quat.GetReal(), *desired_quat.GetImaginary())
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    handle = asyncio.run(
        carrier.attach_carrier(
            rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), desired, merge_rail=False
        )
    )

    _assert_world_orientation(rig.base, desired)
    expected_rotation = Gf.Transform(_world_transform(rig.base)).GetRotation().GetQuat()
    default = robot.articulation.default_state["orientation"]
    actual_rotation = Gf.Quatd(float(default[0]), Gf.Vec3d(*default[1:]))
    assert Gf.IsClose(Gf.Matrix4d(1).SetRotate(actual_rotation), Gf.Matrix4d(1).SetRotate(expected_rotation), 1e-6)

    asyncio.run(carrier.detach_carrier(rig.stage, handle))

    assert rig.stage.GetRootLayer().ExportToString() == root_before
    assert rig.stage.GetSessionLayer().ExportToString() == session_before
    _assert_defaults_restored(robot)


@pytest.mark.parametrize("root_api", ["container", "world_joint", "body"])
@pytest.mark.parametrize("merge_rail", [False, True])
def test_attach_reset_defaults_follow_the_new_physical_root(monkeypatch, root_api, merge_rail):
    rig = _rig()
    _add_authored_transforms(rig, scale=0.01)
    robot = _Robot(rig)
    if root_api != "world_joint":
        rig.pin.GetPrim().RemoveAPI(UsdPhysics.ArticulationRootAPI)
        root = rig.asset if root_api == "container" else rig.base
        UsdPhysics.ArticulationRootAPI.Apply(root)
        robot.set_articulation_root_path(root.GetPath())
    anchor = np.asarray(_world_transform(rig.base).ExtractTranslation())
    physics = _Physics()
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)

    handle = asyncio.run(
        carrier.attach_carrier(
            rig.stage, {"physics": physics}, robot, str(rig.base.GetPath()), (0, 1, 0, 0), merge_rail=merge_rail
        )
    )

    assert robot.resets == 1
    np.testing.assert_allclose(robot.articulation.default_state["position"], anchor)
    _assert_world_orientation(rig.base, (0, 1, 0, 0))
    if merge_rail:
        np.testing.assert_array_equal(robot.articulation.default_state["orientation"], [1, 0, 0, 0])
        np.testing.assert_array_equal(handle.rail_world_anchor, anchor)
    else:
        _assert_world_orientation(rig.base, robot.articulation.default_state["orientation"])
        assert handle.rail_world_anchor is None
    if robot.initializations:
        for name, value in robot.initialized_defaults[-1].items():
            np.testing.assert_array_equal(robot.articulation.default_state[name], value)


def _readback_handle(robot, **kwargs):
    return carrier.CarrierHandle(
        robot=robot,
        gripper_base_path="/World/Asset/base",
        physics=None,
        initial_target_z=0.0,
        world_pin_was_present=False,
        joint_z_path="/World/_FET028_Carrier/joint_z",
        **kwargs,
    )


def _attachment_world_frames(stage, joint):
    cache = UsdGeom.XformCache()
    frames = []
    for body_rel, position_attr, rotation_attr in (
        (joint.GetBody0Rel(), joint.GetLocalPos0Attr(), joint.GetLocalRot0Attr()),
        (joint.GetBody1Rel(), joint.GetLocalPos1Attr(), joint.GetLocalRot1Attr()),
    ):
        body = stage.GetPrimAtPath(body_rel.GetTargets()[0])
        world = cache.GetLocalToWorldTransform(body)
        # USD scales the local attachment point with its owning prim, but the
        # joint's orientation has rigid axes, not a scale component.
        basis = np.asarray(world)[:3, :3]
        body_rotation = basis / np.linalg.norm(basis, axis=1)[:, None]
        local_rotation = Gf.Matrix4d(1).SetRotate(Gf.Quatd(rotation_attr.Get()))
        frames.append(
            (
                np.asarray(world.Transform(Gf.Vec3d(position_attr.Get()))),
                np.asarray(local_rotation)[:3, :3] @ body_rotation,
            )
        )
    return frames


@pytest.mark.parametrize("scale", [(1, 1, 1), (0.01, 0.01, 0.01), (0.01, 0.02, 0.03)])
def test_real_gantry_builder_preserves_rotated_scaled_merged_attachment(scale):
    rig = _rig()
    UsdGeom.Xform(rig.asset).AddRotateZOp().Set(37)
    base = UsdGeom.Xform(rig.base)
    base.AddTranslateOp().Set(Gf.Vec3d(1, 2, 3))
    base.AddRotateXOp().Set(180)
    base.AddScaleOp().Set(Gf.Vec3f(*scale))
    before = _world_transform(rig.base)
    root = "/World/TestCarrier"
    carrier._build_gantry(
        rig.stage, str(rig.base.GetPath()), before.ExtractTranslation(), merge_into_articulation=True, root_path=root
    )
    joint = UsdPhysics.FixedJoint(rig.stage.GetPrimAtPath(root + "/attach_joint"))
    first, second = _attachment_world_frames(rig.stage, joint)
    np.testing.assert_allclose(first[0], second[0], atol=1e-6)
    np.testing.assert_allclose(first[1], second[1], atol=1e-6)
    assert Gf.IsClose(_world_transform(rig.base), before, 1e-9)
    assert joint.GetLocalRot0Attr().HasAuthoredValueOpinion()
    assert joint.GetExcludeFromArticulationAttr().Get() is False


def test_attachment_frames_preserve_scaled_local_attachment_points():
    stage = Usd.Stage.CreateInMemory()
    first = UsdGeom.Xform.Define(stage, "/First")
    first.AddTranslateOp().Set(Gf.Vec3d(1, 2, 3))
    first.AddRotateZOp().Set(30)
    first.AddScaleOp().Set(Gf.Vec3f(2, 3, 4))
    second = UsdGeom.Xform.Define(stage, "/Second")
    second.AddTranslateOp().Set(Gf.Vec3d(1.1, 2.2, 3.3))
    second.AddRotateXOp().Set(90)
    second.AddScaleOp().Set(Gf.Vec3f(0.01, 0.02, 0.03))
    joint = UsdPhysics.FixedJoint.Define(stage, "/Attach")
    joint.CreateBody0Rel().SetTargets([first.GetPath()])
    joint.CreateBody1Rel().SetTargets([second.GetPath()])
    carrier._align_attachment_frames(stage, joint, str(first.GetPath()), str(second.GetPath()))
    a, b = _attachment_world_frames(stage, joint)
    np.testing.assert_allclose(a[0], b[0], atol=1e-6)
    np.testing.assert_allclose(a[1], b[1], atol=1e-6)


@pytest.mark.parametrize("invalid", ["shear", "reflection", "zero_scale", "nonfinite"])
def test_real_gantry_builder_rejects_unrepresentable_frames_before_authoring(invalid):
    rig = _rig()
    transform = Gf.Matrix4d(1)
    if invalid == "shear":
        transform[0, 1] = 0.25
    elif invalid == "reflection":
        transform[0, 0] = -1
    elif invalid == "zero_scale":
        transform[0, 0] = 0
    else:
        transform[3, 0] = float("nan")
    UsdGeom.Xform(rig.base).AddTransformOp().Set(transform)
    before = rig.stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="attachment frame"):
        carrier._build_gantry(
            rig.stage, str(rig.base.GetPath()), (0, 0, 0), merge_into_articulation=True, root_path="/World/TestCarrier"
        )
    assert rig.stage.GetRootLayer().ExportToString() == before


def test_legacy_external_weld_preserves_its_identity_frame_convention():
    rig = _rig()
    UsdGeom.Xform(rig.base).AddRotateXOp().Set(180)
    carrier._build_gantry(
        rig.stage, str(rig.base.GetPath()), (0, 0, 0), merge_into_articulation=False, root_path="/World/TestCarrier"
    )
    joint = UsdPhysics.FixedJoint(rig.stage.GetPrimAtPath("/World/TestCarrier/attach_joint"))
    assert not joint.GetLocalRot0Attr().HasAuthoredValueOpinion()
    assert joint.GetExcludeFromArticulationAttr().Get() is True


def test_attach_does_not_probe_the_old_tensor_view_between_stop_and_rebuild(monkeypatch):
    rig = _rig()
    robot, physics = _Robot(rig), _Physics()
    old_articulation = robot.articulation
    reads, logs = [], []
    original = old_articulation.get_joint_positions

    def old_positions():
        reads.append("invalid old view" if physics.stops else "valid entry")
        if physics.stops:
            raise RuntimeError("the stopped view must not be queried")
        return original()

    old_articulation.get_joint_positions = old_positions
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)
    handle = asyncio.run(
        carrier.attach_carrier(
            rig.stage,
            {"physics": physics},
            robot,
            str(rig.base.GetPath()),
            ctx=SimpleNamespace(log=logs.append),
            merge_rail=True,
        )
    )
    assert reads == ["valid entry"]
    assert any("attach-probe[after reset_async]" in line for line in logs)
    asyncio.run(carrier.detach_carrier(rig.stage, handle))


def test_attach_without_world_fails_and_restores_before_any_post_stop_tensor_probe(monkeypatch):
    rig = _rig()
    before = rig.stage.GetRootLayer().ExportToString()
    robot, physics = _Robot(rig), _Physics()
    robot._world = None
    old_articulation = robot.articulation
    reads, logs = [], []
    original = old_articulation.get_joint_positions

    def old_positions():
        reads.append("invalid old view" if physics.stops else "valid entry")
        if physics.stops:
            raise RuntimeError("the stopped view must not be queried")
        return original()

    old_articulation.get_joint_positions = old_positions
    monkeypatch.setattr(carrier, "_build_gantry", _fake_gantry_builder)
    with pytest.raises(RuntimeError, match="re-cook requires a World"):
        asyncio.run(
            carrier.attach_carrier(
                rig.stage,
                {"physics": physics},
                robot,
                str(rig.base.GetPath()),
                ctx=SimpleNamespace(log=logs.append),
                merge_rail=True,
            )
        )
    assert reads == ["valid entry"]
    assert not any("attach-probe[after reset_async]" in line for line in logs)
    assert robot.prim_path == str(rig.pin.GetPath())
    assert rig.stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("controller_pose", [[1.0, 2.0, 3.0], [1.0, 2.0, 3.2]])
def test_generated_rail_readback_does_not_double_count_a_moving_controller_root(controller_pose):
    robot = SimpleNamespace(
        dof_names=["jaw", "joint_z"],
        get_world_pose=lambda: (controller_pose, [1, 0, 0, 0]),
        get_joint_positions=lambda: np.asarray([0.7, 0.2]),
    )
    handle = _readback_handle(robot, rail_world_anchor=(1.0, 2.0, 3.0))

    np.testing.assert_allclose(carrier.carrier_world_position(handle), [1.0, 2.0, 3.2])


@pytest.mark.parametrize("positions", [None, [], [float("nan")], [float("inf")], [1e35], ["0.2"], [True], [0.2j]])
def test_generated_rail_readback_requires_finite_actual_joint_evidence(positions):
    robot = SimpleNamespace(dof_names=["joint_z"], get_joint_positions=lambda: positions)
    handle = _readback_handle(robot, rail_world_anchor=(1.0, 2.0, 3.0))

    with pytest.raises(RuntimeError, match="finite live joint evidence"):
        carrier.carrier_world_position(handle)


@pytest.mark.parametrize("operation", ["translate", "shake"])
def test_generated_rail_overflow_aborts_before_capture_without_rejecting_unselected_nan(monkeypatch, operation):
    state = {"steps": 0, "commands": [], "captures": []}
    robot = SimpleNamespace(
        dof_names=["unselected", "joint_z"],
        get_joint_positions=lambda: [float("nan"), 0.0 if state["steps"] == 0 else 1e35],
    )
    handle = _readback_handle(robot, rail_world_anchor=(0, 0, 0))

    async def step():
        state["steps"] += 1

    async def capture(index, total):
        state["captures"].append(index)

    monkeypatch.setattr(carrier, "set_carrier_target_z", lambda stage, handle, target: state["commands"].append(target))
    monkeypatch.setattr(carrier, "carrier_target_z", lambda stage, handle: 0.0)
    with pytest.raises(RuntimeError, match="finite live joint evidence") as failure:
        if operation == "translate":
            asyncio.run(
                carrier.linear_translate(
                    SimpleNamespace(step_one=step), None, handle, np.array([0, 0, 0.1]), 0.1, fps=10, on_substep=capture
                )
            )
        else:
            asyncio.run(
                carrier.shake_gantry_z(
                    SimpleNamespace(step_one=step), None, handle, 0.1, 2, 0.1, fps=10, on_step=capture
                )
            )
    assert "representational safety envelope" in str(failure.value.__cause__)
    assert state["steps"] == len(state["commands"]) == 1
    assert state["captures"] == []


def test_generated_rail_readback_rejects_a_missing_live_rail_dof():
    robot = SimpleNamespace(dof_names=["jaw"], get_joint_positions=lambda: [0.2])
    handle = _readback_handle(robot, rail_world_anchor=(1.0, 2.0, 3.0))

    with pytest.raises(RuntimeError, match="rail DOF is absent"):
        carrier.carrier_world_position(handle)


def test_generated_rail_readback_propagates_failed_live_reads():
    def read_failure():
        raise RuntimeError("stale tensor view")

    robot = SimpleNamespace(dof_names=["joint_z"], get_joint_positions=read_failure)
    handle = _readback_handle(robot, rail_world_anchor=(1.0, 2.0, 3.0))

    with pytest.raises(RuntimeError, match="finite live joint evidence") as failure:
        carrier.carrier_world_position(handle)
    assert "stale tensor view" in str(failure.value.__cause__)


@pytest.mark.parametrize("engine,positions,expected_z", [("physx", None, 3.2), ("newton", [0.2], 3.0)])
def test_legacy_and_experimental_newton_readback_keep_their_pose_conventions(engine, positions, expected_z):
    robot = SimpleNamespace(
        dof_names=[] if positions is None else ["joint_z"],
        get_world_pose=lambda: ([1.0, 2.0, 3.2], [1, 0, 0, 0]),
        get_joint_positions=lambda: positions,
    )
    handle = _readback_handle(robot, active_physics_engine=engine)

    np.testing.assert_allclose(carrier.carrier_world_position(handle), [1.0, 2.0, expected_z])

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

import pytest
from simready_benchmark_kit_suite.fet005_grasp.newton_articulation import (
    NEWTON_TENSOR_DRIVE_SKIP,
    NewtonTensorDriveUnavailable,
    apply_temporary_newton_articulations,
    author_newton_pd_actuator,
    compute_newton_pd_parameters,
    infer_articulation_roots,
    remove_temporary_newton_articulations,
    tensor_drive_skip_result,
)


class _AuthoredProperty:
    def __init__(self):
        self.value = None

    def Set(self, value):
        self.value = value
        return True

    def SetTargets(self, value):
        self.value = value
        return True


class _FakePrim:
    def __init__(self, path):
        self.path = path
        self.apis = []
        self.attributes = {}
        self.relationships = {}
        self.metadata = {}

    def __bool__(self):
        return True

    def IsValid(self):
        return True

    def ApplyAPI(self, name):
        self.apis.append(name)
        return self

    def SetMetadata(self, name, value):
        self.metadata[name] = value
        return True

    def CreateAttribute(self, name, _value_type):
        return self.attributes.setdefault(name, _AuthoredProperty())

    def CreateRelationship(self, name):
        return self.relationships.setdefault(name, _AuthoredProperty())


class _FakeStage:
    def __init__(self, joint_path):
        self.prims = {joint_path: _FakePrim(joint_path)}
        self.defined = []

    def GetPrimAtPath(self, path):
        return self.prims.get(path)

    def DefinePrim(self, path, type_name):
        prim = _FakePrim(path)
        self.prims[path] = prim
        self.defined.append((path, type_name))
        return prim


def test_authors_native_newton_pd_actuator(monkeypatch):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "newton_usd_schemas", types.ModuleType("newton_usd_schemas"))
    joint_path = "/World/grasp_robot/gantry_x/left_joint"
    actuator_path = "/World/grasp_robot/actuators/left_finger_actuator"
    stage = _FakeStage(joint_path)

    actuator = author_newton_pd_actuator(stage, actuator_path, joint_path, 500.0, 100.0, 12.5, 0.2)

    assert stage.defined == [(actuator_path, "NewtonActuator")]
    assert stage.prims[joint_path].apis == []
    api_schemas = stage.prims[joint_path].metadata["apiSchemas"]
    assert api_schemas.prependedItems == ["NewtonJointAPI", "PhysicsJointStateAPI:linear"]
    assert stage.prims[joint_path].attributes["newton:velocityLimit"].value == 0.2
    assert actuator.apis == ["NewtonPDControlAPI", "NewtonMaxEffortClampingAPI"]
    assert [str(path) for path in actuator.relationships["newton:targets"].value] == [joint_path]
    assert actuator.attributes["newton:kp"].value == 500.0
    assert actuator.attributes["newton:kd"].value == 100.0
    assert actuator.attributes["newton:maxEffort"].value == 12.5
    assert actuator.attributes["visibility"].value == "invisible"


def test_newton_actuator_rejects_missing_target_joint(monkeypatch):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "newton_usd_schemas", types.ModuleType("newton_usd_schemas"))

    with pytest.raises(ValueError, match="target joint is missing"):
        author_newton_pd_actuator(_FakeStage("/other"), "/actuator", "/missing", 1.0, 1.0, 1.0, 1.0)


def test_newton_pd_parameters_caps_high_friction_credit():
    params = compute_newton_pd_parameters(
        required_grip_force=100.0,
        pad_mass=0.1,
        static_friction=5.0,
        requested_max_velocity=0.2,
    )

    assert params == {
        "stiffness": 2000.0,
        "damping": pytest.approx(28.2842712475),
        "max_effort": 50.0,
        "max_velocity": 0.2,
    }

try:
    from pxr import PhysxSchema  # noqa: F401

    _HAS_PHYSX_SCHEMA = True
except ImportError:
    _HAS_PHYSX_SCHEMA = False


def test_infers_toolbox_tree_root():
    joints = [
        ("/Joints/lid", "/Bodies/box", "/Bodies/lid"),
        ("/Joints/handle", "/Bodies/lid", "/Bodies/handle"),
        ("/Joints/lock0", "/Bodies/lid", "/Bodies/lock0"),
        ("/Joints/lock1", "/Bodies/lid", "/Bodies/lock1"),
    ]

    assert infer_articulation_roots(joints) == ["/Bodies/box"]


def test_infers_one_root_per_disconnected_component():
    joints = [
        ("/Joints/a", "/Bodies/root_a", "/Bodies/child_a"),
        ("/Joints/b", "/Bodies/root_b", "/Bodies/child_b"),
    ]

    assert infer_articulation_roots(joints) == ["/Bodies/root_a", "/Bodies/root_b"]


def test_world_joint_uses_child_as_root():
    assert infer_articulation_roots([("/Joints/world", None, "/Bodies/root")]) == ["/Bodies/root"]


def test_rejects_cycle_without_unique_root():
    joints = [
        ("/Joints/a", "/Bodies/a", "/Bodies/b"),
        ("/Joints/b", "/Bodies/b", "/Bodies/a"),
    ]

    with pytest.raises(ValueError, match="cycle"):
        infer_articulation_roots(joints)


def test_rejects_joint_without_child_body():
    with pytest.raises(ValueError, match="no resolved child"):
        infer_articulation_roots([("/Joints/broken", "/Bodies/root", None)])


def test_temporary_articulation_leaves_unresolved_topology_untouched():
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset")
    body = UsdGeom.Xform.Define(stage, "/Asset/body")
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/broken_joint")
    joint.GetBody0Rel().SetTargets([body.GetPath()])

    assert apply_temporary_newton_articulations(stage, str(asset.GetPath())) == []
    assert not body.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)


def _temporary_articulation_stage():
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset")
    root = UsdGeom.Xform.Define(stage, "/Asset/root")
    child = UsdGeom.Xform.Define(stage, "/Asset/child")
    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(child.GetPrim())
    joint = UsdPhysics.FixedJoint.Define(stage, "/Asset/fixed_joint")
    joint.GetBody0Rel().SetTargets([root.GetPath()])
    joint.GetBody1Rel().SetTargets([child.GetPath()])
    return stage, asset, root


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_temporary_articulation_applies_and_removes_both_articulation_apis():
    from pxr import PhysxSchema, UsdPhysics

    stage, asset, root = _temporary_articulation_stage()

    mutations = apply_temporary_newton_articulations(stage, str(asset.GetPath()))

    assert [mutation.path for mutation in mutations] == [str(root.GetPath())]
    assert root.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert root.GetPrim().HasAPI(PhysxSchema.PhysxArticulationAPI)
    assert PhysxSchema.PhysxArticulationAPI(root.GetPrim()).GetEnabledSelfCollisionsAttr().Get() is False

    remove_temporary_newton_articulations(stage, mutations)

    assert not root.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not root.GetPrim().HasAPI(PhysxSchema.PhysxArticulationAPI)


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_temporary_articulation_restores_existing_physx_self_collision_setting():
    from pxr import PhysxSchema, UsdPhysics

    stage, asset, root = _temporary_articulation_stage()
    physx_api = PhysxSchema.PhysxArticulationAPI.Apply(root.GetPrim())
    physx_api.CreateEnabledSelfCollisionsAttr(True)

    mutations = apply_temporary_newton_articulations(stage, str(asset.GetPath()))

    assert PhysxSchema.PhysxArticulationAPI(root.GetPrim()).GetEnabledSelfCollisionsAttr().Get() is False

    remove_temporary_newton_articulations(stage, mutations)

    assert not root.GetPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert root.GetPrim().HasAPI(PhysxSchema.PhysxArticulationAPI)
    assert PhysxSchema.PhysxArticulationAPI(root.GetPrim()).GetEnabledSelfCollisionsAttr().Get() is True


def test_tensor_drive_capability_error_returns_skip_signal():
    error = NewtonTensorDriveUnavailable("controller init failed")

    assert tensor_drive_skip_result(error) == {"skip": NEWTON_TENSOR_DRIVE_SKIP}
    assert tensor_drive_skip_result(RuntimeError("unrelated rebuild error")) is None

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

"""Regression coverage for nvBug 6976369 using real USD instances."""

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.rules_and_reqs.physics_bodies.physics_rigid_bodies import validation as rb


def _stage(instanceable):
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    stage.SetDefaultPrim(world)
    source = stage.CreateClassPrim("/Source")
    inst = UsdGeom.Xform.Define(stage, "/World/Inst").GetPrim()
    inst.GetReferences().AddInternalReference(source.GetPath())
    inst.SetInstanceable(instanceable)
    return stage, inst


def _issues(checker_type, stage):
    checker = checker_type()
    checker.CheckStage(stage)
    return checker.GetIssues()


@pytest.mark.parametrize("instanceable", [False, True])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_body_discovery(instanceable, count):
    stage, inst = _stage(instanceable)
    for index in range(count):
        body = UsdGeom.Xform.Define(stage, f"/Source/Body{index}").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
    assert inst.IsInstance() == instanceable
    assert bool(_issues(rb.RigidBodyCapabilityChecker, stage)) == (count == 0)
    assert bool(_issues(rb.MultibodyChecker, stage)) == (count < 2)


@pytest.mark.parametrize("instanceable", [False, True])
@pytest.mark.parametrize("mass_location", [None, "body", "collider"])
@pytest.mark.parametrize("body_inside", [False, True])
def test_owned_collider_mass(instanceable, mass_location, body_inside):
    stage, inst = _stage(instanceable)
    body = UsdGeom.Xform.Define(stage, "/Source/Body").GetPrim() if body_inside else inst
    UsdPhysics.RigidBodyAPI.Apply(body)
    collider_path = "/Source/Body/Col" if body_inside else "/Source/Col"
    collider = UsdGeom.Cube.Define(stage, collider_path).GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    if mass_location:
        UsdPhysics.MassAPI.Apply(body if mass_location == "body" else collider).CreateMassAttr(1.0)
    issues = _issues(rb.RigidBodyMassChecker, stage)
    assert len(issues) == (1 if mass_location is None else 0)
    if issues:
        path = "/World/Inst/Body/Col" if body_inside else "/World/Inst/Col"
        assert path in issues[0].message


@pytest.mark.parametrize("instanceable", [False, True])
def test_mass_ownership_stops_at_nested_body(instanceable):
    stage, inst = _stage(instanceable)
    UsdPhysics.RigidBodyAPI.Apply(inst)
    body = UsdGeom.Xform.Define(stage, "/Source/Child").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    UsdPhysics.MassAPI.Apply(body).CreateMassAttr(1.0)
    collider = UsdGeom.Cube.Define(stage, "/Source/Child/Col").GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    assert not _issues(rb.RigidBodyMassChecker, stage)


@pytest.mark.parametrize("instanceable", [False, True])
@pytest.mark.parametrize("joint_location", [None, "inside", "outside"])
def test_nested_body_joint(instanceable, joint_location):
    stage, inst = _stage(instanceable)
    parent = UsdGeom.Xform.Define(stage, "/Source/Parent").GetPrim()
    child = UsdGeom.Xform.Define(stage, "/Source/Parent/Child").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(parent)
    UsdPhysics.RigidBodyAPI.Apply(child)
    if joint_location:
        inside = joint_location == "inside"
        joint = UsdPhysics.FixedJoint.Define(stage, "/Source/Joint" if inside else "/World/Joint")
        prefix = "/Source" if inside else "/World/Inst"
        joint.CreateBody0Rel().SetTargets([prefix + "/Parent"])
        joint.CreateBody1Rel().SetTargets([prefix + "/Parent/Child"])
    issues = _issues(rb.NoNestedRigidBodyWithoutJointChecker, stage)
    assert len(issues) == (1 if joint_location is None else 0)
    if issues:
        assert "/World/Inst/Parent/Child" in issues[0].message


@pytest.mark.parametrize("instanceable", [False, True])
@pytest.mark.parametrize("valid", [False, True])
def test_mujoco_collider_schema(instanceable, valid):
    stage, inst = _stage(instanceable)
    collider = UsdGeom.Mesh.Define(stage, "/Source/Col").GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    if valid:
        collider.AddAppliedSchema("MjcCollisionAPI")
    issues = _issues(rb.MuJoCoColliderAPIChecker, stage)
    assert len(issues) == (0 if valid else 1)
    if issues:
        assert "/World/Inst/Col" in issues[0].message


@pytest.mark.parametrize("instanceable", [False, True])
def test_inactive_colliders_are_excluded(instanceable):
    stage, inst = _stage(instanceable)
    collider = UsdGeom.Mesh.Define(stage, "/Source/Col").GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    collider.SetActive(False)
    assert not _issues(rb.MuJoCoColliderAPIChecker, stage)

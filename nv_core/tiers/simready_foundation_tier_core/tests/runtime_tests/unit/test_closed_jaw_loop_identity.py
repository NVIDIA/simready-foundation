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
"""Actual closed-jaw discovery and mapper; stepped adapter, not native physics."""
import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
    discover_fingertips,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    detect_loop_joints,
)
from test_articulation_fingertip_discovery import PhysxSchema
from test_gripper_endpoint_mapping import (
    _CONFIG,
    _Context,
    _detect_open_closed_positions,
    _Robot,
)


def linkage(aliases=False, forwarding=False, body_root=True):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    for name, x in [
        ("base", 0),
        ("left_driver", -0.02),
        ("right_driver", 0.02),
        ("left_pad", -0.05),
        ("right_pad", 0.05),
    ]:
        body = UsdGeom.Xform.Define(stage, "/Asset/" + name)
        body.AddTranslateOp().Set((x, 0, 0))
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset/base"))
    pairs = [
        ("master", "base", "left_driver"),
        ("follower", "base", "right_driver"),
        ("left_link", "left_driver", "left_pad"),
        ("right_link", "right_driver", "right_pad"),
        ("left_closure", "base", "left_pad"),
        ("right_closure", "base", "right_pad"),
    ]
    for name, a, b in pairs:
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Joints/" + name)
        for index, body in enumerate((a, b)):
            path = "/Asset/" + body
            if forwarding:
                rel = asset.CreateRelationship("to_" + name + str(index))
                rel.SetTargets([path])
                path = str(rel.GetPath())
            joint.GetPrim().CreateRelationship("physics:body" + str(index)).SetTargets([path])
        if name.endswith("closure"):
            joint.CreateExcludeFromArticulationAttr(True)
        if name == "master":
            UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100)
    follower = stage.GetPrimAtPath("/Asset/Joints/follower")
    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(follower, UsdPhysics.Tokens.rotX)
    mimic.CreateReferenceJointRel().SetTargets(["/Asset/Joints/master"])
    mimic.CreateOffsetAttr().Set(0)
    mimic.CreateGearingAttr().Set(1)
    names = [row[0] for row in pairs[:4]]
    if aliases:
        names = ["/Asset/Joints/" + name + ":0" for name in names]
    robot = SimpleNamespace(prim_path="/Asset/base", asset_prim=asset, dof_names=names)
    robot.prim_path = "/Asset/base" if body_root else "/Asset"
    return stage, robot


@pytest.mark.parametrize("aliases,forwarding", [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize("body_root", [False, True])
def test_closed_jaw_discovery_to_mapper_preserves_selected_loop_identity(aliases, forwarding, body_root):
    stage, selected = linkage(aliases, forwarding, body_root)
    tips = ["/Asset/left_pad", "/Asset/right_pad"]
    for path in tips:
        cube = UsdGeom.Cube.Define(stage, path + "/shape")
        cube.CreateSizeAttr(0.002)

    def geometry(q):
        opening = 0.02 + 0.08 * q[0]
        return {
            "/Asset/left_driver": [-0.02, 0, -0.05],
            "/Asset/right_driver": [0.02, 0, -0.05],
            tips[0]: [-opening / 2, 0, -0.1],
            tips[1]: [opening / 2, 0, -0.1],
        }

    robot = _Robot(tips, geometry, leaders=3)
    robot.dof_names = selected.dof_names
    robot.prim_path = selected.prim_path
    robot.asset_prim = selected.asset_prim
    fingertips = discover_fingertips(stage, robot, None)
    assert fingertips.kind == "mimic_parallel_jaw"
    assert fingertips.mimic_master_dofs == [0]
    before = robot.targets.copy()
    endpoints = asyncio.run(_detect_open_closed_positions(_Context(robot), robot, fingertips, stage, _CONFIG, 0.1))
    assert endpoints == (1.0, 0.0)
    assert {index for index, _ in robot.actions} == {0}
    np.testing.assert_array_equal(robot.targets, before)


@pytest.mark.parametrize("defect", ["extra", "ambiguous_endpoint", "foreign_reference", "raw_coupling"])
def test_closed_jaw_unsafe_ownership_is_not_hidden_as_loop(defect):
    stage, robot = linkage(True, True)
    if defect == "extra":
        body = UsdGeom.Xform.Define(stage, "/Asset/independent").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Joints/extra")
        joint.CreateBody0Rel().SetTargets(["/Asset/base"])
        joint.CreateBody1Rel().SetTargets([body.GetPath()])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100)
        robot.dof_names.append(str(joint.GetPath()) + ":0")
    elif defect == "ambiguous_endpoint":
        stage.GetPrimAtPath("/Asset").GetRelationship("to_left_closure0").SetTargets(
            ["/Asset/base", "/Asset/right_pad"]
        )
    elif defect == "foreign_reference":
        stage.GetPrimAtPath("/Asset/Joints/follower").GetRelationship("physxMimicJoint:rotX:referenceJoint").SetTargets(
            ["/Foreign/master"]
        )
    else:
        follower = stage.GetPrimAtPath("/Asset/Joints/left_link")
        follower.AddAppliedSchema("NewtonMimicAPI")
    with pytest.raises(RuntimeError):
        discover_fingertips(stage, robot, None)


def test_loop_maps_every_native_axis_without_changing_driver_policy():
    stage, robot = linkage(True, True)
    robot.dof_names += ["/Asset/Joints/left_link:1", "/Asset/Joints/left_link:2"]
    indices, _ = detect_loop_joints(stage, robot.prim_path, robot.dof_names, robot.asset_prim)
    assert indices == {1, 2, 3, 4, 5}

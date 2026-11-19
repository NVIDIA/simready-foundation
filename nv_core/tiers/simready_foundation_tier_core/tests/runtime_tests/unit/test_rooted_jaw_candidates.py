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
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
    discover_fingertips,
)
from test_articulation_fingertip_discovery import PhysxSchema
from test_gripper_endpoint_mapping import (
    _CONFIG,
    _Context,
    _detect_open_closed_positions,
    _Robot,
)


def _jaw(reversed_edges=(), forwarding=False, nested=False, distal=False):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    prefix = "/Asset/base/" if nested else "/Asset/"
    bodies = ["/Asset/base", prefix + "left", prefix + "right"]
    if distal:
        bodies += [prefix + "left_tip", prefix + "right_tip"]
    for path in bodies:
        body = UsdGeom.Xform.Define(stage, path)
        body.SetResetXformStack(True)
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath(bodies[0]))
    edges = [("leader", bodies[0], bodies[1]), ("follower", bodies[0], bodies[2])]
    if distal:
        edges += [("left_fixed", bodies[1], bodies[3]), ("right_passive", bodies[2], bodies[4])]
    for name, parent, child in edges:
        joint_type = UsdPhysics.FixedJoint if name == "left_fixed" else UsdPhysics.RevoluteJoint
        joint = joint_type.Define(stage, "/Asset/Joints/" + name)
        ends = [parent, child]
        if name in reversed_edges:
            ends.reverse()
        for index, path in enumerate(ends):
            if forwarding:
                rel = asset.CreateRelationship("to_" + name + str(index))
                rel.SetTargets([path])
                path = str(rel.GetPath())
            joint.GetPrim().CreateRelationship("physics:body" + str(index)).SetTargets([path])
        if name == "leader":
            UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100)
    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(stage.GetPrimAtPath("/Asset/Joints/follower"), UsdPhysics.Tokens.rotX)
    mimic.CreateReferenceJointRel().SetTargets(["/Asset/Joints/leader"])
    mimic.CreateGearingAttr().Set(-1 if ("leader" in reversed_edges) == ("follower" in reversed_edges) else 1)
    mimic.CreateOffsetAttr().Set(0)
    return stage, SimpleNamespace(prim_path=bodies[0], asset_prim=asset), bodies


@pytest.mark.parametrize("reversed_edges", [(), ("leader", "follower"), ("follower",)])
@pytest.mark.parametrize("root_kind", ["body", "cooked"])
@pytest.mark.parametrize(
    "forwarding,nested,reordered,distal",
    [
        (False, False, False, False),
        (True, True, True, False),
        (False, True, False, True),
        (True, False, True, True),
    ],
)
def test_selected_root_orients_candidates_and_descendants_through_official_mapper(
    reversed_edges, forwarding, nested, reordered, distal, root_kind
):
    # Distal endpoints are independently reversed: raw-direction traversal loses them.
    edges = reversed_edges + (("left_fixed", "right_passive") if distal else ())
    stage, selected, bodies = _jaw(edges, forwarding, nested, distal)
    tips = bodies[3:] if distal else bodies[1:]
    for path in tips:
        UsdGeom.Cube.Define(stage, path + "/shape").CreateSizeAttr(0.002)
    leader = int(reordered)
    sign = -1 if "leader" in reversed_edges else 1

    def geometry(q):
        opening = 0.02 + sign * 0.08 * q[leader]
        poses = {bodies[1]: [-0.01, 0, -0.05], bodies[2]: [0.01, 0, -0.05]}
        poses.update({tips[0]: [-opening / 2, 0, -0.1], tips[1]: [opening / 2, 0, -0.1]})
        return poses

    robot = _Robot(tips, geometry)
    robot.dof_names = ["/Asset/Joints/leader:0", "/Asset/Joints/follower:0"]
    if reordered:
        robot.dof_names.reverse()
    robot.prim_path, robot.asset_prim = selected.prim_path, selected.asset_prim
    if root_kind == "cooked":
        stage.GetPrimAtPath(bodies[0]).RemoveAPI(UsdPhysics.ArticulationRootAPI)
        UsdPhysics.ArticulationRootAPI.Apply(selected.asset_prim)
        robot.prim_path = "/Asset"
        paths = list(reversed(bodies))
        names = [path.rsplit("/", 1)[1] for path in paths]
        parent_paths = {bodies[1]: bodies[0], bodies[2]: bodies[0]}
        if distal:
            parent_paths.update({bodies[3]: bodies[1], bodies[4]: bodies[2]})
        parents = {
            path.rsplit("/", 1)[1]: paths.index(parent_paths[path]) if path in parent_paths else -1 for path in paths
        }
        meta = SimpleNamespace(
            link_names=names, link_indices=dict(zip(names, range(len(paths)), strict=True)), link_parent_indices=parents
        )
        view = SimpleNamespace(link_paths=[paths], get_metatype=lambda index: meta)
        robot.articulation = SimpleNamespace(_articulation_view=SimpleNamespace(_physics_view=view))
    robot.actual[leader], robot.targets[leader] = sign * 0.4, sign * 0.45
    lower, upper = np.zeros(2), np.ones(2)
    if sign < 0:
        lower[leader], upper[leader] = -1, 0
    robot.get_joint_position_limits = lambda: (lower, upper)
    ctx = _Context(robot)

    async def step_one():
        ctx.steps += 1
        robot.actual[leader] = robot.targets[leader]

    ctx.step_one = step_one
    prior_targets, prior_position = robot.targets.copy(), robot.actual.copy()
    fingertips = discover_fingertips(stage, robot, None)
    assert fingertips.kind == "mimic_parallel_jaw"
    assert set(fingertips.candidate_tip_paths) == set(bodies[1:])
    assert fingertips.mimic_master_dofs == [leader]
    endpoints = asyncio.run(_detect_open_closed_positions(ctx, robot, fingertips, stage, _CONFIG, 0.1))
    assert endpoints == (float(sign), 0.0)
    assert {index for index, _ in robot.actions} == {leader}
    np.testing.assert_array_equal(robot.targets, prior_targets)
    np.testing.assert_allclose(robot.actual, prior_position)


@pytest.mark.parametrize("defect", ["missing_root", "ambiguous_root", "disabled_foreign_shadow"])
def test_selected_jaw_requires_qualified_root_and_excludes_foreign_disabled_shadows(defect):
    reversed_edges = ("leader", "follower") if defect == "disabled_foreign_shadow" else ()
    stage, robot, bodies = _jaw(reversed_edges, forwarding=True)
    robot.dof_names = ["leader", "follower"]
    if defect == "missing_root":
        stage.GetPrimAtPath(bodies[0]).RemoveAPI(UsdPhysics.ArticulationRootAPI)
        robot.prim_path = "/Asset"
        # A native row without complete parent metadata cannot pick its first link.
        robot.articulation = SimpleNamespace(
            _articulation_view=SimpleNamespace(
                _physics_view=SimpleNamespace(link_paths=[[bodies[2], bodies[0], bodies[1]]])
            )
        )
    elif defect == "ambiguous_root":
        UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath(bodies[1]))
        robot.prim_path = "/Asset"
    else:
        for path in ["/Asset/Foreign/base", "/Asset/Foreign/tip"]:
            body = UsdGeom.Xform.Define(stage, path).GetPrim()
            UsdPhysics.RigidBodyAPI.Apply(body)
        UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset/Foreign/base"))
        shadow = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Foreign/leader")
        shadow.CreateBody0Rel().SetTargets(["/Asset/Foreign/tip"])
        shadow.CreateBody1Rel().SetTargets(["/Asset/Foreign/base"])
        disabled = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Disabled/leader")
        disabled.CreateBody0Rel().SetTargets([bodies[1]])
        disabled.CreateBody1Rel().SetTargets([bodies[2]])
        disabled.CreateJointEnabledAttr(False)
        result = discover_fingertips(stage, robot, None)
        assert set(result.candidate_tip_paths) == set(bodies[1:])
        assert result.mimic_master_dofs == [0]
        return
    with pytest.raises(RuntimeError):
        discover_fingertips(stage, robot, None)

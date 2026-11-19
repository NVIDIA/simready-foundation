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
"""Tests for articulation_phases.passive_joints."""

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
    detect_passive_joints,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)


def _stage_with_joints(joint_specs):
    """joint_specs: list of (name, joint_type, drive_stiffness) tuples."""
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    UsdGeom.Xform.Define(stage, "/World/Asset/joints")
    for name, jt, stiffness in joint_specs:
        path = "/World/Asset/joints/%s" % name
        if jt == "revolute":
            j = UsdPhysics.RevoluteJoint.Define(stage, path)
            drive_api = "angular"
        else:
            j = UsdPhysics.PrismaticJoint.Define(stage, path)
            drive_api = "linear"
        if stiffness is not None:
            drive = UsdPhysics.DriveAPI.Apply(j.GetPrim(), drive_api)
            drive.CreateStiffnessAttr(float(stiffness))
    return stage


def test_detect_passive_joints_none_when_all_driven():
    stage = _stage_with_joints(
        [
            ("joint_a", "revolute", 100.0),
            ("joint_b", "revolute", 200.0),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_b"])
    assert indices == frozenset()
    assert names == []


def test_detect_passive_joints_flags_zero_stiffness():
    stage = _stage_with_joints(
        [
            ("joint_a", "revolute", 100.0),
            ("joint_passive", "revolute", 0.0),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])
    assert indices == frozenset({1})
    assert names == ["joint_passive"]


def test_detect_passive_joints_flags_missing_drive():
    stage = _stage_with_joints(
        [
            ("joint_a", "revolute", 100.0),
            ("joint_passive", "revolute", None),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])
    assert indices == frozenset({1})


def test_detect_passive_joints_prismatic_with_linear_drive():
    stage = _stage_with_joints(
        [
            ("slider_a", "prismatic", 50.0),
            ("slider_b", "prismatic", None),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["slider_a", "slider_b"])
    assert 1 in indices
    assert 0 not in indices


def test_detect_passive_joints_accepts_direct_newton_actuator_target():
    stage = _stage_with_joints([("joint_a", "revolute", None), ("joint_passive", "revolute", None)])
    actuator = stage.DefinePrim("/World/Asset/actuators/joint_a", "NewtonActuator")
    actuator.CreateRelationship("newton:targets").SetTargets(["/World/Asset/joints/joint_a"])

    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])

    assert indices == frozenset({1})
    assert names == ["joint_passive"]


def test_detect_passive_joints_follows_mjc_actuator_tendon_targets():
    stage = _stage_with_joints([("joint_a", "revolute", None), ("joint_passive", "revolute", None)])
    tendon = stage.DefinePrim("/World/Asset/actuators/tendon", "MjcTendon")
    tendon.CreateRelationship("mjc:path").SetTargets(["/World/Asset/joints/joint_a"])
    actuator = stage.DefinePrim("/World/Asset/actuators/fingers", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets([tendon.GetPath()])

    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])

    assert indices == frozenset({1})
    assert names == ["joint_passive"]


def test_detect_passive_joints_accepts_direct_mjc_joint_target():
    stage = _stage_with_joints([("joint_a", "revolute", None), ("joint_passive", "revolute", None)])
    actuator = stage.DefinePrim("/World/Asset/actuators/direct", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets(["/World/Asset/joints/joint_a"])
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])
    assert indices == frozenset({1})
    assert names == ["joint_passive"]


def test_detect_passive_joints_handles_invalid_input():
    stage = Usd.Stage.CreateInMemory()
    indices, names = detect_passive_joints(stage, "/NonExistent", ["joint_a"])
    assert indices == frozenset()


def _leaf_root_scene():
    stage = _stage_with_joints([("joint_a", "revolute", 100), ("joint_passive", "revolute", None)])
    root = UsdPhysics.FixedJoint.Define(stage, "/World/Asset/root_joint").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(root)
    for body in ("base", "a", "passive"):
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/World/Asset/" + body).GetPrim())
    UsdPhysics.Joint(root).CreateBody1Rel().SetTargets(["/World/Asset/base"])
    for name, body in (("joint_a", "a"), ("joint_passive", "passive")):
        joint = UsdPhysics.Joint(stage.GetPrimAtPath("/World/Asset/joints/" + name))
        joint.CreateBody0Rel().SetTargets(["/World/Asset/base"])
        joint.CreateBody1Rel().SetTargets(["/World/Asset/" + body])
    return stage, root, stage.GetPrimAtPath("/World/Asset")


def test_leaf_articulation_discovers_sibling_passives_without_room_probe_contamination():
    stage, root, asset = _leaf_root_scene()
    foreign_joint = UsdPhysics.RevoluteJoint.Define(stage, "/World/Room/joint_passive")
    UsdPhysics.DriveAPI.Apply(foreign_joint.GetPrim(), "angular").CreateStiffnessAttr(100)
    probe = stage.DefinePrim("/World/Probe/actuator", "NewtonActuator")
    probe.CreateRelationship("newton:targets").SetTargets(["/World/Asset/joints/joint_passive"])
    assert detect_passive_joints(stage, str(root.GetPath()), ["joint_a", "joint_passive"]) == (frozenset(), [])
    assert detect_passive_joints(stage, str(root.GetPath()), ["joint_a", "joint_passive"], asset_prim=asset) == (
        frozenset({1}),
        ["joint_passive"],
    )


def test_loaded_asset_scope_finds_sibling_actuator_without_changing_root_policy():
    stage, root, asset = _leaf_root_scene()
    actuator = stage.DefinePrim("/World/Asset/actuators/a", "NewtonActuator")
    actuator.CreateRelationship("newton:targets").SetTargets(["/World/Asset/joints/joint_passive"])
    assert detect_passive_joints(stage, str(root.GetPath()), ["joint_a", "joint_passive"], asset_prim=asset) == (
        frozenset(),
        [],
    )
    stage.RemovePrim(actuator.GetPath())
    root.CreateAttribute("newton:jointsAddMobility", Sdf.ValueTypeNames.Bool).Set(True)
    asset.CreateAttribute("newton:jointsAddMobility", Sdf.ValueTypeNames.Bool).Set(False)
    assert detect_passive_joints(stage, str(root.GetPath()), ["joint_a", "joint_passive"], asset_prim=asset) == (
        frozenset(),
        [],
    )


@pytest.mark.parametrize("invalid_scope", ["sibling", "different_stage", "missing"])
def test_explicit_asset_discovery_scope_must_contain_actual_root(invalid_scope):
    stage, root, _ = _leaf_root_scene()
    foreign_stage = Usd.Stage.CreateInMemory()
    if invalid_scope == "sibling":
        selected = UsdGeom.Xform.Define(stage, "/World/Probe").GetPrim()
    elif invalid_scope == "different_stage":
        selected = UsdGeom.Xform.Define(foreign_stage, "/World/Asset").GetPrim()
    else:
        selected = stage.GetPrimAtPath("/Missing")
    with pytest.raises(RequiredReadbackError, match="verified loaded asset subtree"):
        detect_passive_joints(stage, str(root.GetPath()), ["joint_passive"], asset_prim=selected)

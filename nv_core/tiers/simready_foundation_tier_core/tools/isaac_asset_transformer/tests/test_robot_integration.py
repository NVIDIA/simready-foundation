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
from __future__ import annotations

from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.asset_transformer import transform_package


def test_minimal_robot_transform_uses_public_schema_and_joint_patch(tmp_path) -> None:
    source_path = tmp_path / "source_robot.usda"
    output_root = tmp_path / "output"

    stage = Usd.Stage.CreateNew(str(source_path))
    robot = UsdGeom.Xform.Define(stage, "/robot")
    stage.SetDefaultPrim(robot.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(robot.GetPrim())

    base = UsdGeom.Xform.Define(stage, "/robot/base")
    UsdPhysics.RigidBodyAPI.Apply(base.GetPrim())
    link = UsdGeom.Xform.Define(stage, "/robot/link")
    UsdPhysics.RigidBodyAPI.Apply(link.GetPrim())
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/robot/joint")
    joint.CreateBody0Rel().SetTargets([base.GetPath()])
    joint.CreateBody1Rel().SetTargets([link.GetPath()])
    stage.GetRootLayer().Save()

    report = transform_package(
        str(source_path),
        output_root,
        profile="simready_physx_to_isaac_robot",
        interface_asset_name="robot.usda",
    )
    assert all(result.success for result in report.results)

    transformed = Usd.Stage.Open(str(output_root / "robot.usda"))
    transformed_robot = transformed.GetDefaultPrim()
    assert transformed_robot
    assert "IsaacRobotAPI" in transformed_robot.GetAppliedSchemas()
    assert transformed_robot.GetRelationship("isaac:physics:robotLinks").GetTargets()
    assert transformed_robot.GetRelationship("isaac:physics:robotJoints").GetTargets()
    physics = Usd.Stage.Open(str(output_root / "payloads/Physics/physics.usda"))
    transformed_joint = physics.GetPrimAtPath("/robot/joint")
    assert "PhysicsJointStateAPI:angular" in transformed_joint.GetAppliedSchemas()


def test_rv_robot_transform_keeps_activation_metadata_consistent(tmp_path) -> None:
    """Robot sources that follow the neutral RV contract (PhysX/Newton/MuJoCo
    with Enabled/Disabled and SimReady_Metadata activation descriptors) must
    keep descriptors that name existing variant options.
    """
    source_path = tmp_path / "rv_robot.usda"
    output_root = tmp_path / "output"
    runtimes = ("PhysX", "Newton", "MuJoCo")

    stage = Usd.Stage.CreateNew(str(source_path))
    robot = UsdGeom.Xform.Define(stage, "/robot")
    stage.SetDefaultPrim(robot.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(robot.GetPrim())
    base = UsdGeom.Xform.Define(stage, "/robot/base")
    UsdPhysics.RigidBodyAPI.Apply(base.GetPrim())
    link = UsdGeom.Xform.Define(stage, "/robot/link")
    UsdPhysics.RigidBodyAPI.Apply(link.GetPrim())
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/robot/joint")
    joint.CreateBody0Rel().SetTargets([base.GetPath()])
    joint.CreateBody1Rel().SetTargets([link.GetPath()])
    for runtime in runtimes:
        variant_set = robot.GetPrim().GetVariantSets().AddVariantSet(runtime)
        for option in ("Disabled", "Enabled"):
            variant_set.AddVariant(option)
        variant_set.SetVariantSelection("Enabled")
        with variant_set.GetVariantEditContext():
            robot.GetPrim().CreateAttribute(f"simready:test:{runtime.lower()}", Sdf.ValueTypeNames.Bool).Set(True)
        variant_set.SetVariantSelection("Disabled")
    stage.GetRootLayer().customLayerData = {
        "SimReady_Metadata": {
            "Variants": {
                "Physics": {
                    runtime: {"activateOption": "Enabled", "prim": "/robot", "variantSetName": runtime}
                    for runtime in runtimes
                }
            }
        }
    }
    stage.GetRootLayer().Save()

    report = transform_package(
        str(source_path),
        output_root,
        profile="simready_physx_to_isaac_robot",
        interface_asset_name="robot.usda",
    )
    assert [result.rule.name for result in report.results if not result.success] == []

    transformed = Usd.Stage.Open(str(output_root / "robot.usda"))
    transformed_robot = transformed.GetDefaultPrim()
    variant_sets = transformed_robot.GetVariantSets()
    assert set(variant_sets.GetNames()) == set(runtimes)
    descriptors = transformed.GetRootLayer().customLayerData["SimReady_Metadata"]["Variants"]["Physics"]
    for runtime in runtimes:
        variant_set = variant_sets.GetVariantSet(runtime)
        assert set(variant_set.GetVariantNames()) == {"Disabled", "Enabled"}
        assert variant_set.GetVariantSelection() == "Disabled"
        assert descriptors[runtime]["activateOption"] in variant_set.GetVariantNames()

    # Neutral physics is always composed, independent of the runtime selection.
    assert transformed.GetPrimAtPath("/robot/joint").IsA(UsdPhysics.RevoluteJoint)
    assert transformed.GetPrimAtPath("/robot/base").HasAPI(UsdPhysics.RigidBodyAPI)

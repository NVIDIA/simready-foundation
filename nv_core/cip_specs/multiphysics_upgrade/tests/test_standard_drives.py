# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Preserve authored standard drives without inventing runtime actuators."""

import math

import pytest
from fixtures import write_neutral_package
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from simready.multiphysics_upgrade.api import run_neutral_to_runtimes
from simready.multiphysics_upgrade.core import preflight_physics_topology


def add_drive(path, axis="angular", joint_type="revolute", drive_type="force"):
    stage = Usd.Stage.Open(str(path))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    cls = {
        "revolute": UsdPhysics.RevoluteJoint,
        "prismatic": UsdPhysics.PrismaticJoint,
        "fixed": UsdPhysics.FixedJoint,
    }[joint_type]
    joint = cls.Define(stage, "/RootNode/Joints/test_joint")
    joint.CreateBody1Rel().SetTargets(["/RootNode"])
    if joint_type != "fixed":
        joint.CreateAxisAttr("Y")
        joint.CreateLowerLimitAttr(0.0)
        joint.CreateUpperLimitAttr(90.0 if axis == "angular" else 0.5)
    drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), axis)
    drive.CreateTypeAttr(drive_type)
    drive.CreateDampingAttr(2.0)
    drive.CreateStiffnessAttr(1.0)
    drive.CreateMaxForceAttr(50.0)
    drive.CreateTargetPositionAttr(90.0 if axis == "angular" else 0.25)
    drive.CreateTargetVelocityAttr(10.0 if axis == "angular" else 0.1)
    stage.GetRootLayer().Save()
    return stage, joint.GetPrim(), drive


@pytest.mark.parametrize(
    "axis,joint_type,drive_type",
    [
        ("angular", "revolute", "force"),
        ("linear", "prismatic", "force"),
        ("angular", "revolute", "acceleration"),
        ("linear", "prismatic", "acceleration"),
    ],
)
def test_full_conversion_preserves_standard_drive(
    tmp_path, axis, joint_type, drive_type
):
    source = write_neutral_package(tmp_path / "source")
    stage, prim, _ = add_drive(source, axis, joint_type, drive_type)
    fields = (
        "type",
        "damping",
        "stiffness",
        "maxForce",
        "targetPosition",
        "targetVelocity",
    )
    expected = {
        field: prim.GetAttribute(f"drive:{axis}:physics:{field}").Get()
        for field in fields
    }
    original = source.read_bytes()
    result = run_neutral_to_runtimes(source, tmp_path / "export")
    assert result.ok, result.to_dict()
    assert source.read_bytes() == original
    exported = Usd.Stage.Open(str(result.output_usd))
    exported.SetEditTarget(exported.GetSessionLayer())
    root = exported.GetDefaultPrim()
    root.GetVariantSets().GetVariantSet("PhysX").SetVariantSelection("Enabled")
    joints = [
        p
        for p in exported.Traverse(Usd.TraverseInstanceProxies())
        if p.IsA(UsdPhysics.Joint)
    ]
    assert len(joints) == 1
    joint = joints[0]
    assert joint.HasAPI(UsdPhysics.DriveAPI, axis)
    assert joint.GetAttribute("physics:axis").Get() == "Y"
    assert len(UsdPhysics.Joint(joint).GetBody1Rel().GetTargets()) == 1
    assert {
        field: joint.GetAttribute(f"drive:{axis}:physics:{field}").Get()
        for field in fields
    } == expected
    assert UsdGeom.GetStageMetersPerUnit(exported) == UsdGeom.GetStageMetersPerUnit(
        stage
    )
    assert UsdPhysics.GetStageKilogramsPerUnit(
        exported
    ) == UsdPhysics.GetStageKilogramsPerUnit(stage)


@pytest.mark.parametrize(
    "field,value",
    [
        ("damping", -1.0),
        ("stiffness", math.inf),
        ("maxForce", -math.inf),
        ("targetPosition", math.nan),
        ("targetVelocity", math.inf),
        ("type", "invalid"),
    ],
)
def test_invalid_drive_still_requires_handoff(tmp_path, field, value):
    source = write_neutral_package(tmp_path / "source")
    stage, prim, _ = add_drive(source)
    prim.GetAttribute(f"drive:angular:physics:{field}").Set(value)
    assert "NEEDS_RUNTIME_BODY_WORK" in {
        b.code for b in preflight_physics_topology(stage).blockers
    }


@pytest.mark.parametrize(
    "axis,kind",
    [
        ("angular", "prismatic"),
        ("linear", "revolute"),
        ("rotX", "revolute"),
        ("angular", "fixed"),
    ],
)
def test_unsupported_axis_joint_remains_blocked(tmp_path, axis, kind):
    source = write_neutral_package(tmp_path / "source")
    stage, _, _ = add_drive(source, axis, kind)
    assert "NEEDS_RUNTIME_BODY_WORK" in {
        b.code for b in preflight_physics_topology(stage).blockers
    }


def test_unlimited_force_and_schema_fallbacks_are_supported(tmp_path):
    source = write_neutral_package(tmp_path / "source")
    stage, prim, drive = add_drive(source)
    for attribute in prim.GetAttributes():
        if attribute.GetName().startswith("drive:angular:physics:"):
            attribute.Clear()
    assert not preflight_physics_topology(stage).blockers
    assert drive.GetMaxForceAttr().Get() == math.inf


@pytest.mark.parametrize(
    "schema",
    [
        "PhysxMimicJointAPI:rotX",
        "PhysxSceneAPI",
        "PhysxArticulationAPI",
        "NewtonMimicAPI",
        "MjcActuator",
    ],
)
def test_runtime_specific_blockers_are_retained(tmp_path, schema):
    source = write_neutral_package(tmp_path / "source")
    stage, prim, _ = add_drive(source)
    prim.AddAppliedSchema(schema)
    assert "NEEDS_RUNTIME_BODY_WORK" in {
        b.code for b in preflight_physics_topology(stage).blockers
    }


def test_time_sampled_and_uninstanced_api_tokens_remain_blocked(tmp_path):
    source = write_neutral_package(tmp_path / "source")
    stage, prim, drive = add_drive(source)
    drive.GetTargetPositionAttr().Set(20.0, 1.0)
    assert preflight_physics_topology(stage).blockers
    drive.GetTargetPositionAttr().Clear()
    prim.AddAppliedSchema("PhysicsDriveAPI")
    assert preflight_physics_topology(stage).blockers


def test_instance_proxy_invalid_drive_is_not_missed(tmp_path):
    source = write_neutral_package(tmp_path / "source")
    stage, prim, _ = add_drive(source)
    prototype = UsdGeom.Xform.Define(stage, "/Prototype").GetPrim()
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Prototype/Joint")
    drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular")
    drive.CreateDampingAttr(-1.0)
    instance = stage.DefinePrim("/RootNode/Instance", "Xform")
    instance.GetReferences().AddInternalReference(Sdf.Path("/Prototype"))
    instance.SetInstanceable(True)
    # Keep the referenced source out of normal active traversal.
    prototype.SetSpecifier(Sdf.SpecifierClass)
    blockers = preflight_physics_topology(stage).blockers
    assert any("/RootNode/Instance/Joint" in path for b in blockers for path in b.paths)

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
"""Exercise PhysX schema queries with real USD stages and either schema provider.

Run against an installed/editable core tier built from the source under test.
The standalone run requires physx-usd-schemas; Kit's native bindings are preferred.
"""

import importlib
from pathlib import Path

import pytest
import usd_validation_nvidia as validation
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.rules_and_reqs.physics_bodies.physics_driven_joints import (
    validation as joints,
)
from simready.foundation.tier_core.rules_and_reqs.physics_bodies.physics_rigid_bodies import (
    validation as bodies,
)

try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema


def _issues(checker_type, prim):
    checker = checker_type()
    checker.CheckPrim(prim)
    issues = list(checker.GetIssues())
    assert all(i.severity != validation.IssueSeverity.ERROR for i in issues)
    return issues


def _engine_issues(checker_type, stage, requirement):
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(checker_type)
    issues = list(engine.validate(stage).issues)
    assert all(i.severity == validation.IssueSeverity.FAILURE for i in issues)
    assert all(i.requirement.code.endswith(f".{requirement}") for i in issues)
    return issues


def _joint(stage, path, lower=-90, upper=90):
    joint = UsdPhysics.RevoluteJoint.Define(stage, path)
    joint.CreateLowerLimitAttr(lower)
    joint.CreateUpperLimitAttr(upper)
    return joint.GetPrim()


def _mimic(stage, axis="rotX"):
    leader = _joint(stage, "/Leader")
    follower = _joint(stage, "/Follower", -180, 180)
    api = PhysxSchema.PhysxMimicJointAPI.Apply(follower, axis)
    api.CreateReferenceJointRel().SetTargets([leader.GetPath()])
    api.CreateGearingAttr(1.0)
    api.CreateNaturalFrequencyAttr(10.0)
    api.CreateDampingRatioAttr(1.0)
    return follower, api


def test_validators_load_available_physx_provider():
    assert joints.PhysxSchema is PhysxSchema
    assert bodies.PhysxSchema is PhysxSchema


@pytest.mark.parametrize("axis", ["rotX", "rotZ"])
def test_mimic_validator_accepts_any_valid_instance(axis):
    stage = Usd.Stage.CreateInMemory()
    prim, _ = _mimic(stage, axis)
    assert _issues(joints.MimicAPICheck, prim) == []


def test_invalid_mimic_reports_dj007_through_engine():
    stage = Usd.Stage.CreateInMemory()
    _prim, mimic = _mimic(stage)
    mimic.GetGearingAttr().Set(0.0)
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(joints.MimicAPICheck)
    issues = list(engine.validate(stage).issues)
    assert issues
    assert all(i.severity == validation.IssueSeverity.FAILURE for i in issues)
    assert all(i.requirement.code.endswith(".DJ.007") for i in issues)
    assert any("gear ratio == 0" in i.message for i in issues)


def test_non_mimic_joint_is_ignored():
    stage = Usd.Stage.CreateInMemory()
    assert _issues(joints.MimicAPICheck, _joint(stage, "/Joint")) == []


@pytest.mark.parametrize(
    "targets, message",
    [
        ([], "incorrect number of reference joints"),
        (["/Leader", "/Other"], "incorrect number of reference joints"),
        (["/Missing"], "invalid reference joint"),
        (["/Other"], "invalid reference joint"),
    ],
)
def test_invalid_mimic_reference_reports_failure_without_exception(targets, message):
    stage = Usd.Stage.CreateInMemory()
    _prim, mimic = _mimic(stage)
    UsdGeom.Xform.Define(stage, "/Other")
    mimic.GetReferenceJointRel().SetTargets(targets)
    issues = _engine_issues(joints.MimicAPICheck, stage, "DJ.007")
    assert any(message in i.message for i in issues)


def test_blocked_mimic_gearing_reports_failure_without_exception():
    stage = Usd.Stage.CreateInMemory()
    _prim, mimic = _mimic(stage)
    mimic.GetGearingAttr().Block()
    issues = _engine_issues(joints.MimicAPICheck, stage, "DJ.007")
    assert any("has no gear ratio" in i.message for i in issues)


@pytest.mark.parametrize("invalid_field", ["reference", "gearing"])
def test_invalid_mimic_instance_does_not_skip_remaining_instances(invalid_field):
    stage = Usd.Stage.CreateInMemory()
    prim, first = _mimic(stage)
    if invalid_field == "reference":
        first.GetReferenceJointRel().SetTargets([])
    else:
        first.GetGearingAttr().Block()
    second = PhysxSchema.PhysxMimicJointAPI.Apply(prim, "rotZ")
    second.CreateReferenceJointRel().SetTargets(["/Leader"])
    second.CreateGearingAttr(0.0)
    second.CreateNaturalFrequencyAttr(10.0)
    second.CreateDampingRatioAttr(1.0)
    issues = _engine_issues(joints.MimicAPICheck, stage, "DJ.007")
    assert len(issues) >= 2
    assert any("gear ratio == 0" in i.message for i in issues)


@pytest.mark.parametrize("has_mimic", [False, True])
def test_drive_or_mimic_requirement_detects_presence(has_mimic):
    stage = Usd.Stage.CreateInMemory()
    prim = _mimic(stage)[0] if has_mimic else _joint(stage, "/Joint")
    issues = _issues(joints.PhysicsJointHasDriveOrMimicAPI, prim)
    assert bool(issues) is not has_mimic
    assert all(i.requirement.code.endswith(".DJ.004") for i in issues)


@pytest.mark.parametrize("stiffness", [0.0, 100.0])
@pytest.mark.parametrize("checker_type", [joints.PhysicsJointHasDriveOrMimicAPI, joints.DriveJointValueReasonable])
def test_revolute_mimic_drive_gains_are_checked(checker_type, stiffness):
    stage = Usd.Stage.CreateInMemory()
    prim, _ = _mimic(stage)
    drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
    drive.CreateStiffnessAttr(stiffness)
    drive.CreateDampingAttr(0.0)
    issues = _issues(checker_type, prim)
    assert bool(issues) is (stiffness != 0.0)


def test_mimic_drive_state_path_reports_invalid_force():
    stage = Usd.Stage.CreateInMemory()
    prim, _ = _mimic(stage)
    drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
    drive.CreateStiffnessAttr(100.0)
    drive.CreateMaxForceAttr(0.0)
    state = PhysxSchema.JointStateAPI.Apply(prim, "angular")
    state.CreatePositionAttr(0.0)
    state.CreateVelocityAttr(0.0)
    issues = _issues(joints.PhysicsDriveAndJointState, prim)
    assert any(i.requirement.code.endswith(".DJ.001") and "Max Force is zero" in i.message for i in issues)


@pytest.mark.parametrize(
    "joint_type, axis", [(UsdPhysics.RevoluteJoint, "angular"), (UsdPhysics.PrismaticJoint, "linear")]
)
@pytest.mark.parametrize(
    "max_force, position, velocity, message",
    [
        (0.0, 0.0, 0.0, "Max Force is zero"),
        (float("inf"), 0.0, 0.0, "Max Force is infinite"),
        (10.0, 1.0, 0.0, "Joint state position is very different"),
        (10.0, 0.0, 1.0, "Joint state velocity is very different"),
        (10.0, 0.0, 0.0, None),
    ],
)
def test_non_mimic_drives_validate_force_and_state(joint_type, axis, max_force, position, velocity, message):
    stage = Usd.Stage.CreateInMemory()
    prim = joint_type.Define(stage, "/Joint").GetPrim()
    drive = UsdPhysics.DriveAPI.Apply(prim, axis)
    drive.CreateStiffnessAttr(100.0)
    drive.CreateMaxForceAttr(max_force)
    drive.CreateTargetPositionAttr(position)
    drive.CreateTargetVelocityAttr(velocity)
    state = PhysxSchema.JointStateAPI.Apply(prim, axis)
    state.CreatePositionAttr(0.0)
    state.CreateVelocityAttr(0.0)
    issues = _engine_issues(joints.PhysicsDriveAndJointState, stage, "DJ.001")
    if message is None:
        assert issues == []
    else:
        assert any(message in i.message for i in issues)


@pytest.mark.parametrize(
    "joint_type, axis", [(UsdPhysics.RevoluteJoint, "angular"), (UsdPhysics.PrismaticJoint, "linear")]
)
@pytest.mark.parametrize("attribute", ["max_force", "target_position", "target_velocity", "position", "velocity"])
@pytest.mark.parametrize("invalid_value", [None, float("nan"), float("inf"), -float("inf")])
def test_blocked_or_nonfinite_drive_readbacks_report_failure_without_exception(
    joint_type, axis, attribute, invalid_value
):
    stage = Usd.Stage.CreateInMemory()
    prim = joint_type.Define(stage, "/Joint").GetPrim()
    drive = UsdPhysics.DriveAPI.Apply(prim, axis)
    drive.CreateMaxForceAttr(10.0)
    drive.CreateTargetPositionAttr(0.0)
    drive.CreateTargetVelocityAttr(0.0)
    state = PhysxSchema.JointStateAPI.Apply(prim, axis)
    state.CreatePositionAttr(0.0)
    state.CreateVelocityAttr(0.0)
    attributes = {
        "max_force": drive.GetMaxForceAttr(),
        "target_position": drive.GetTargetPositionAttr(),
        "target_velocity": drive.GetTargetVelocityAttr(),
        "position": state.GetPositionAttr(),
        "velocity": state.GetVelocityAttr(),
    }
    invalid_attr = attributes[attribute]
    if invalid_value is None:
        invalid_attr.Block()
    else:
        invalid_attr.Set(invalid_value)
    issues = _engine_issues(joints.PhysicsDriveAndJointState, stage, "DJ.001")
    assert len(issues) == 1
    assert str(invalid_attr.GetPath()) in issues[0].message


def test_passive_mimic_drive_still_skips_force_and_state_checks():
    stage = Usd.Stage.CreateInMemory()
    prim, _ = _mimic(stage)
    drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
    drive.CreateStiffnessAttr(0.0)
    drive.CreateDampingAttr(0.0)
    drive.CreateMaxForceAttr(0.0)
    assert _engine_issues(joints.PhysicsDriveAndJointState, stage, "DJ.001") == []


@pytest.mark.parametrize("velocity", [0.0, 10.0])
def test_physx_joint_max_velocity(velocity):
    stage = Usd.Stage.CreateInMemory()
    prim = _joint(stage, "/Joint")
    PhysxSchema.PhysxJointAPI.Apply(prim).CreateMaxJointVelocityAttr(velocity)
    issues = _issues(joints.PhysicsJointMaxVelocity, prim)
    assert bool(issues) is (velocity == 0.0)


def _merged_collider(stage, has_geometry=True):
    prim = UsdGeom.Xform.Define(stage, "/Merged").GetPrim()
    stage.SetDefaultPrim(prim)
    UsdPhysics.CollisionAPI.Apply(prim)
    UsdPhysics.MeshCollisionAPI.Apply(prim)
    api = PhysxSchema.PhysxMeshMergeCollisionAPI.Apply(prim)
    if has_geometry:
        geometry = UsdGeom.Cube.Define(stage, "/Merged/Geometry")
        api.GetCollisionMeshesCollectionAPI().CreateIncludesRel().SetTargets([geometry.GetPath()])
    return prim


@pytest.mark.parametrize("has_geometry", [False, True])
def test_merged_collision_collection_is_checked(has_geometry):
    stage = Usd.Stage.CreateInMemory()
    prim = _merged_collider(stage, has_geometry)
    assert bodies._collisionmeshes_collection_has_gprim(prim) is has_geometry
    issues = _issues(bodies.PhysxRigidBodyColliderCapabilityChecker, prim)
    assert bool(issues) is not has_geometry
    assert all(i.requirement.code.endswith(".PHYSX.COL.001") for i in issues)
    assert _issues(bodies.PhysxRigidBodyColliderMeshChecker, prim) == []


def test_plain_xform_is_not_a_merged_collider():
    stage = Usd.Stage.CreateInMemory()
    prim = UsdGeom.Xform.Define(stage, "/Plain").GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim)
    UsdPhysics.MeshCollisionAPI.Apply(prim)
    assert not bodies._collisionmeshes_collection_has_gprim(prim)
    assert _issues(bodies.PhysxRigidBodyColliderCapabilityChecker, prim)
    assert _issues(bodies.PhysxRigidBodyColliderMeshChecker, prim)


@pytest.mark.parametrize("function", ["_set_collider_approximation_to_sdf", "_set_mesh_collider_sdf_approximation"])
def test_sdf_adapter_handles_merged_collider(tmp_path, monkeypatch, function):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    adapter = importlib.import_module("asset_handler_modules.neutral_to_physx")
    stage = Usd.Stage.CreateNew(str(tmp_path / "collider.usda"))
    prim = _merged_collider(stage)
    getattr(adapter, function)(stage)
    assert prim.HasAPI("PhysxCollisionAPI")
    assert prim.HasAPI("PhysxSDFMeshCollisionAPI")
    assert UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() == "sdf"

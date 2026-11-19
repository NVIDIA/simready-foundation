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
"""Real-schema DJ.007 checks for unavailable or malformed compliance values."""

import math

import pytest
import usd_validation_nvidia as validation

try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema

from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_core.rules_and_reqs.physics_bodies.physics_driven_joints import (
    validation as joints,
)


def _make_mimic(joint_type=UsdPhysics.RevoluteJoint):
    stage = Usd.Stage.CreateInMemory()
    leader = joint_type.Define(stage, "/Leader")
    follower = joint_type.Define(stage, "/Follower")
    leader.CreateLowerLimitAttr(0.0)
    leader.CreateUpperLimitAttr(2.0)
    follower.CreateLowerLimitAttr(-2.0)
    follower.CreateUpperLimitAttr(0.0)
    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), "rotX")
    mimic.CreateReferenceJointRel().SetTargets([leader.GetPath()])
    mimic.CreateGearingAttr(1.0)
    mimic.CreateOffsetAttr(0.0)
    mimic.CreateNaturalFrequencyAttr(-1.0)
    mimic.CreateDampingRatioAttr(-1.0)
    return stage, follower, mimic


def _check(stage):
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(joints.MimicAPICheck)
    issues = list(engine.validate(stage).issues)
    assert all(issue.severity != validation.IssueSeverity.ERROR for issue in issues)
    failures = [issue for issue in issues if issue.severity == validation.IssueSeverity.FAILURE]
    assert all(issue.requirement.code.endswith(".DJ.007") for issue in failures)
    return issues, failures


def _replace_with_raw_opinion(stage, follower, field, value):
    name = "physxMimicJoint:rotX:" + field
    follower.GetPrim().RemoveProperty(name)
    type_name = Sdf.ValueTypeNames.String if isinstance(value, str) else Sdf.ValueTypeNames.Bool
    opinion = Sdf.AttributeSpec(stage.GetRootLayer().GetPrimAtPath(follower.GetPath()), name, type_name)
    opinion.default = value


@pytest.mark.parametrize("field", ["naturalFrequency", "dampingRatio"])
@pytest.mark.parametrize("invalid", [None, math.nan, math.inf, -math.inf])
def test_mimic_compliance_unavailable_or_nonfinite_values_are_dj007_failures(field, invalid):
    stage, follower, _ = _make_mimic()
    attribute = follower.GetPrim().GetAttribute("physxMimicJoint:rotX:" + field)
    if invalid is None:
        attribute.Block()
    else:
        attribute.Set(invalid)
    _, failures = _check(stage)
    assert failures
    expected = "natural frequency" if field == "naturalFrequency" else "damping ratio"
    assert any(expected in issue.message.lower() for issue in failures)


@pytest.mark.parametrize("field", ["naturalFrequency", "dampingRatio"])
@pytest.mark.parametrize("invalid", ["0", "-1", "1", "not-a-number", True, False])
def test_mimic_compliance_wrong_typed_opinions_cannot_be_coerced_into_a_pass(field, invalid):
    stage, follower, _ = _make_mimic()
    _replace_with_raw_opinion(stage, follower, field, invalid)
    _, failures = _check(stage)
    assert failures


@pytest.mark.parametrize("natural_frequency", [-1.0, 0.0, 1.0, 10.0])
@pytest.mark.parametrize("damping_ratio", [-1.0, 0.0, 0.5])
def test_mimic_compliance_preserves_rigid_sentinels_and_existing_damping_zero_info(natural_frequency, damping_ratio):
    stage, _, mimic = _make_mimic()
    mimic.GetNaturalFrequencyAttr().Set(natural_frequency)
    mimic.GetDampingRatioAttr().Set(damping_ratio)
    issues, failures = _check(stage)
    assert failures == []
    if damping_ratio == 0.0:
        assert any(
            issue.severity == validation.IssueSeverity.INFO and "damping ratio == 0" in issue.message
            for issue in issues
        )
    else:
        assert issues == []


@pytest.mark.parametrize("joint_type", [UsdPhysics.RevoluteJoint, UsdPhysics.PrismaticJoint])
@pytest.mark.parametrize("authored", [True, False], ids=["explicit-zero", "schema-default"])
def test_mimic_compliance_accepts_rigid_zero_and_schema_defaults(joint_type, authored):
    stage, follower, mimic = _make_mimic(joint_type)
    for attribute in (mimic.GetNaturalFrequencyAttr(), mimic.GetDampingRatioAttr()):
        if authored:
            attribute.Set(0.0)
        else:
            follower.GetPrim().RemoveProperty(attribute.GetName())
        assert attribute.HasAuthoredValueOpinion() is authored
        assert attribute.Get() == 0.0
    _, failures = _check(stage)
    assert failures == []


@pytest.mark.parametrize("invalid_field", ["gearing", "limits"])
def test_rigid_zero_mimic_still_checks_gearing_and_limits(invalid_field):
    stage, follower, mimic = _make_mimic()
    mimic.GetNaturalFrequencyAttr().Set(0.0)
    if invalid_field == "gearing":
        mimic.GetGearingAttr().Set(0.0)
        expected = "gear ratio == 0"
    else:
        follower.GetLowerLimitAttr().Set(-1.0)
        expected = "mapped mimic lower limit"
    _, failures = _check(stage)
    assert len(failures) == 1
    assert expected in failures[0].message


@pytest.mark.parametrize("field", ["naturalFrequency", "dampingRatio"])
@pytest.mark.parametrize("invalid", [None, math.nan, "0"])
def test_invalid_compliance_instance_does_not_prevent_independent_remaining_checks(field, invalid):
    stage, follower, _ = _make_mimic()
    if isinstance(invalid, str):
        _replace_with_raw_opinion(stage, follower, field, invalid)
    else:
        attribute = follower.GetPrim().GetAttribute("physxMimicJoint:rotX:" + field)
        if invalid is None:
            attribute.Block()
        else:
            attribute.Set(invalid)
    second = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), "rotZ")
    second.CreateReferenceJointRel().SetTargets(["/Leader"])
    second.CreateGearingAttr(0.0)
    second.CreateOffsetAttr(0.0)
    second.CreateNaturalFrequencyAttr(-1.0)
    second.CreateDampingRatioAttr(-1.0)
    _, failures = _check(stage)
    assert len(failures) >= 2
    assert any("gear ratio == 0" in issue.message for issue in failures)


def _check_mujoco_dj002(stage):
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(joints.MuJoCoActuatorTargetsChecker)
    issues = list(engine.validate(stage).issues)
    assert all(issue.severity != validation.IssueSeverity.ERROR for issue in issues)
    failures = [issue for issue in issues if issue.severity == validation.IssueSeverity.FAILURE]
    assert all(issue.requirement.code.endswith(".MUJOCO.DJ.002") for issue in failures)
    return failures


def _apply_schemas(prim, names):
    prim.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(names)))


def test_mujoco_dj002_tendon_credits_only_selected_nonzero_fixed_tendon_entries():
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.SetDefaultPrim(root)
    j0 = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/J0").GetPrim()
    j1 = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/J1").GetPrim()
    _apply_schemas(j0, ["MjcJointAPI"])
    _apply_schemas(j1, ["MjcJointAPI"])

    tendon = stage.DefinePrim("/Robot/split", "MjcTendon")
    tendon.CreateAttribute("mjc:type", Sdf.ValueTypeNames.Token).Set("fixed")
    tendon.CreateRelationship("mjc:path").SetTargets([j0.GetPath(), j1.GetPath()])
    tendon.CreateAttribute("mjc:path:indices", Sdf.ValueTypeNames.IntArray).Set([0, 1])
    tendon.CreateAttribute("mjc:path:coef", Sdf.ValueTypeNames.DoubleArray).Set([0.5, 0.5])

    act = stage.DefinePrim("/Robot/act", "MjcActuator")
    act.CreateRelationship("mjc:target").SetTargets([tendon.GetPath()])
    assert _check_mujoco_dj002(stage) == []

    # Unselected J1 when mjc:path:indices = [0] must fail coverage for J1.
    tendon.GetAttribute("mjc:path:indices").Set([0])
    tendon.GetAttribute("mjc:path:coef").Set([1.0])
    failures = _check_mujoco_dj002(stage)
    assert any("/Robot/J1" in issue.message for issue in failures)

    # Zero-effect coefficient for J1 must fail coverage for J1.
    tendon.GetAttribute("mjc:path:indices").Set([0, 1])
    tendon.GetAttribute("mjc:path:coef").Set([1.0, 0.0])
    failures = _check_mujoco_dj002(stage)
    assert any("/Robot/J1" in issue.message for issue in failures)

    # Cancelling duplicate entries for J0 must fail as zero-effect transmission.
    tendon.GetAttribute("mjc:path:indices").Set([0, 0])
    tendon.GetAttribute("mjc:path:coef").Set([1.0, -1.0])
    failures = _check_mujoco_dj002(stage)
    assert any("no effective non-zero joint transmission" in issue.message for issue in failures)

    # Mismatched coef length vs selected indices must fail.
    tendon.GetAttribute("mjc:path:indices").Set([0])
    tendon.GetAttribute("mjc:path:coef").Set([1.0, 1.0])
    failures = _check_mujoco_dj002(stage)
    assert any("mjc:path:coef" in issue.message for issue in failures)

    # Out-of-range mjc:path:indices must fail.
    tendon.GetAttribute("mjc:path:indices").Set([2])
    tendon.GetAttribute("mjc:path:coef").Set([1.0])
    failures = _check_mujoco_dj002(stage)
    assert any("mjc:path:indices" in issue.message for issue in failures)

    # Spatial or unauthored mjc:type tendon does not provide joint actuation coverage.
    tendon.GetAttribute("mjc:path:indices").Set([0, 1])
    tendon.GetAttribute("mjc:path:coef").Set([0.5, 0.5])
    tendon.GetAttribute("mjc:type").Set("spatial")
    failures = _check_mujoco_dj002(stage)
    assert any("mjc:type" in issue.message for issue in failures)

    # Explicit empty default arrays mjc:path:indices = [] and mjc:path:coef = [] must pass
    # across all combinations (selecting all mjc:path targets in order with unit coefficients).
    tendon.GetAttribute("mjc:type").Set("fixed")
    tendon.GetAttribute("mjc:path:indices").Set([])
    tendon.GetAttribute("mjc:path:coef").Set([])
    assert _check_mujoco_dj002(stage) == []

    tendon.GetAttribute("mjc:path:indices").Set([0, 1])
    tendon.GetAttribute("mjc:path:coef").Set([])
    assert _check_mujoco_dj002(stage) == []

    tendon.GetAttribute("mjc:path:indices").Set([])
    tendon.GetAttribute("mjc:path:coef").Set([0.5, 0.5])
    assert _check_mujoco_dj002(stage) == []

    tendon.RemoveProperty("mjc:path:indices")
    tendon.GetAttribute("mjc:path:coef").Set([])
    assert _check_mujoco_dj002(stage) == []

    tendon.CreateAttribute("mjc:path:indices", Sdf.ValueTypeNames.IntArray).Set([])
    tendon.RemoveProperty("mjc:path:coef")
    assert _check_mujoco_dj002(stage) == []

    # Length mismatch after normalizing mjc:path:indices = [] (2 targets) vs coef = [1.0] must fail.
    tendon.CreateAttribute("mjc:path:coef", Sdf.ValueTypeNames.DoubleArray).Set([1.0])
    failures = _check_mujoco_dj002(stage)
    assert any("mjc:path:coef" in issue.message for issue in failures)


def test_mujoco_dj002_mimic_coefficient_precedence_and_schema_consumption():
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.SetDefaultPrim(root)
    leader = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/leader").GetPrim()
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/follower").GetPrim()
    _apply_schemas(leader, ["MjcJointAPI"])
    act = stage.DefinePrim("/Robot/act", "MjcActuator")
    act.CreateRelationship("mjc:target").SetTargets([leader.GetPath()])

    # 1. Plain NewtonMimicAPI with linear coef 0 and nonzero mjc:coef2 must fail
    #    (higher-order mjc:coef2..4 is only consumed with MjcEqualityJointAPI).
    _apply_schemas(follower, ["MjcJointAPI", "NewtonMimicAPI"])
    follower.CreateRelationship("newton:mimicJoint").SetTargets([leader.GetPath()])
    follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(0.0)
    follower.CreateAttribute("mjc:coef2", Sdf.ValueTypeNames.Double).Set(1.0)
    failures = _check_mujoco_dj002(stage)
    assert any("zero coupling coefficients" in issue.message for issue in failures)

    # Adding MjcEqualityJointAPI makes mjc:coef2 active and valid.
    _apply_schemas(follower, ["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"])
    assert _check_mujoco_dj002(stage) == []

    # 2. Canonical newton:mimicJoint + legacy mjc:coef1 = 0 with no authored newton:mimicCoef1
    #    resolves coef1 = 0 in the SDK and must fail.
    follower.RemoveProperty("newton:mimicCoef1")
    follower.RemoveProperty("mjc:coef2")
    follower.CreateAttribute("mjc:coef1", Sdf.ValueTypeNames.Double).Set(0.0)
    failures = _check_mujoco_dj002(stage)
    assert any("zero coupling coefficients" in issue.message for issue in failures)

    # Authoring nonzero newton:mimicCoef1 overrides legacy mjc:coef1 = 0 and passes.
    follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(1.5)
    assert _check_mujoco_dj002(stage) == []

    # 3. Legacy mjc:target + authored newton:mimicCoef1 = 0 + legacy mjc:coef1 = 1.5
    #    resolves coef1 = 0 in the SDK (newton:mimicCoef1 takes precedence) and must fail.
    follower.RemoveProperty("newton:mimicJoint")
    follower.CreateRelationship("mjc:target").SetTargets([leader.GetPath()])
    follower.GetAttribute("newton:mimicCoef1").Set(0.0)
    follower.GetAttribute("mjc:coef1").Set(1.5)
    failures = _check_mujoco_dj002(stage)
    assert any("zero coupling coefficients" in issue.message for issue in failures)


def test_mujoco_dj002_rejects_spherical_mimic_and_unactuated_mimic_cycles():
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.SetDefaultPrim(root)
    leader = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/leader").GetPrim()
    spherical_follower = UsdPhysics.SphericalJoint.Define(stage, "/Robot/spherical_follower").GetPrim()
    _apply_schemas(leader, ["MjcJointAPI"])
    _apply_schemas(spherical_follower, ["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"])
    spherical_follower.CreateRelationship("newton:mimicJoint").SetTargets([leader.GetPath()])

    act = stage.DefinePrim("/Robot/act", "MjcActuator")
    act.CreateRelationship("mjc:target").SetTargets([leader.GetPath()])
    failures = _check_mujoco_dj002(stage)
    assert any("/Robot/spherical_follower" in issue.message and "1-DOF" in issue.message for issue in failures)

    # Replace spherical follower with an unactuated mimic cycle (j_a <-> j_b) while leader is actuated.
    stage.RemovePrim("/Robot/spherical_follower")
    ja = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j_a").GetPrim()
    jb = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j_b").GetPrim()
    _apply_schemas(ja, ["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"])
    _apply_schemas(jb, ["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"])
    ja.CreateRelationship("newton:mimicJoint").SetTargets([jb.GetPath()])
    jb.CreateRelationship("newton:mimicJoint").SetTargets([ja.GetPath()])
    failures = _check_mujoco_dj002(stage)
    assert any("/Robot/j_a" in issue.message for issue in failures)
    assert any("/Robot/j_b" in issue.message for issue in failures)


def test_mujoco_dj002_loop_waiver_requires_actuated_loop_and_loop_only_branch():
    from pxr import Gf

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.SetDefaultPrim(root)
    for name in ("b0", "b1", "b2", "b3", "b4", "other0", "other1"):
        body = stage.DefinePrim(f"/Robot/{name}", "Xform")
        UsdPhysics.RigidBodyAPI.Apply(body)

    # Separate actuated joint on other0 -> other1
    other_j = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/other_j")
    other_j.CreateBody0Rel().SetTargets(["/Robot/other0"])
    other_j.CreateBody1Rel().SetTargets(["/Robot/other1"])
    _apply_schemas(other_j.GetPrim(), ["MjcJointAPI"])
    act = stage.DefinePrim("/Robot/act_other", "MjcActuator")
    act.CreateRelationship("mjc:target").SetTargets([other_j.GetPath()])

    # Non-degenerate planar 4-bar loop on b0 - b1 - b2 - b3 - b0 (closed by excluded j_close)
    j1 = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j1")
    j1.CreateBody0Rel().SetTargets(["/Robot/b0"])
    j1.CreateBody1Rel().SetTargets(["/Robot/b1"])
    j1.CreateAxisAttr("Z")
    j1.CreateLocalPos0Attr(Gf.Vec3f(0.0, 0.0, 0.0))
    j1.CreateLocalPos1Attr(Gf.Vec3f(0.0, 0.0, 0.0))
    _apply_schemas(j1.GetPrim(), ["MjcJointAPI"])

    j2 = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j2")
    j2.CreateBody0Rel().SetTargets(["/Robot/b1"])
    j2.CreateBody1Rel().SetTargets(["/Robot/b2"])
    j2.CreateAxisAttr("Z")
    j2.CreateLocalPos0Attr(Gf.Vec3f(1.0, 0.0, 0.0))
    j2.CreateLocalPos1Attr(Gf.Vec3f(1.0, 0.0, 0.0))
    _apply_schemas(j2.GetPrim(), ["MjcJointAPI"])

    j3 = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j3")
    j3.CreateBody0Rel().SetTargets(["/Robot/b2"])
    j3.CreateBody1Rel().SetTargets(["/Robot/b3"])
    j3.CreateAxisAttr("Z")
    j3.CreateLocalPos0Attr(Gf.Vec3f(1.0, 1.0, 0.0))
    j3.CreateLocalPos1Attr(Gf.Vec3f(1.0, 1.0, 0.0))
    _apply_schemas(j3.GetPrim(), ["MjcJointAPI"])

    j_close = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j_close")
    j_close.CreateBody0Rel().SetTargets(["/Robot/b3"])
    j_close.CreateBody1Rel().SetTargets(["/Robot/b0"])
    j_close.CreateAxisAttr("Z")
    j_close.CreateLocalPos0Attr(Gf.Vec3f(0.0, 1.0, 0.0))
    j_close.CreateLocalPos1Attr(Gf.Vec3f(0.0, 1.0, 0.0))
    j_close.CreateExcludeFromArticulationAttr(True)

    # Because no joint on the b0..b3 loop is actuated, j1, j2, j3 must all fail MUJOCO.DJ.002.
    failures = _check_mujoco_dj002(stage)
    assert len(failures) == 3

    # Once j1 is actuated on the 4-bar loop, passive loop-only branch joints j2 and j3 are covered.
    act_loop = stage.DefinePrim("/Robot/act_j1", "MjcActuator")
    act_loop.CreateRelationship("mjc:target").SetTargets([j1.GetPath()])
    assert _check_mujoco_dj002(stage) == []

    # Extending the loop to a planar 5-revolute linkage (b0 - b1 - b2 - b3 - b4 - b0) with only
    # one actuator leaves one free mechanism coordinate and must fail MUJOCO.DJ.002.
    j4 = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/j4")
    j4.CreateBody0Rel().SetTargets(["/Robot/b3"])
    j4.CreateBody1Rel().SetTargets(["/Robot/b4"])
    j4.CreateAxisAttr("Z")
    j4.CreateLocalPos0Attr(Gf.Vec3f(0.5, 1.5, 0.0))
    j4.CreateLocalPos1Attr(Gf.Vec3f(0.5, 1.5, 0.0))
    _apply_schemas(j4.GetPrim(), ["MjcJointAPI"])
    j_close.GetBody0Rel().SetTargets(["/Robot/b4"])
    failures = _check_mujoco_dj002(stage)
    assert failures

    # Actuating a second independent coordinate on the 5-bar linkage leaves zero free passive DOFs.
    act_loop2 = stage.DefinePrim("/Robot/act_j2", "MjcActuator")
    act_loop2.CreateRelationship("mjc:target").SetTargets([j2.GetPath()])
    assert _check_mujoco_dj002(stage) == []

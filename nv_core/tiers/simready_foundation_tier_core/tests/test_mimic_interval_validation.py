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
"""DJ.007 interval regressions against the actual Core rule and USD schemas.

Register the standalone PhysX plugins before creating any USD stages. These
checks exercise validation, not native simulation of a mimic mechanism.
"""

import math

import pytest
import usd_validation_nvidia as validation

try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema

from pxr import Sdf, Tf, Usd, UsdPhysics
from simready.foundation.tier_core.rules_and_reqs.physics_bodies.physics_driven_joints import (
    validation as joints,
)

_DEFAULT = object()


def _make_pair(joint_type, leader_bounds=(0.0, 2.0), follower_bounds=(-2.0, 0.0), gearing=1.0, offset=0.0, axis="rotX"):
    stage = Usd.Stage.CreateInMemory()
    leader = joint_type.Define(stage, "/Leader")
    follower = joint_type.Define(stage, "/Follower")
    for schema, bounds in ((leader, leader_bounds), (follower, follower_bounds)):
        schema.CreateLowerLimitAttr(bounds[0])
        schema.CreateUpperLimitAttr(bounds[1])
    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), axis)
    mimic.CreateReferenceJointRel().SetTargets([leader.GetPath()])
    if gearing is not _DEFAULT:
        mimic.CreateGearingAttr().Block() if gearing is None else mimic.CreateGearingAttr(gearing)
    if offset is not _DEFAULT:
        mimic.CreateOffsetAttr().Block() if offset is None else mimic.CreateOffsetAttr(offset)
    # The negative rigid-mimic sentinel remains valid; this change must not
    # accidentally require positive compliance parameters.
    mimic.CreateNaturalFrequencyAttr(-1.0)
    mimic.CreateDampingRatioAttr(-1.0)
    return stage, leader, follower, mimic


def _issues(stage):
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(joints.MimicAPICheck)
    issues = list(engine.validate(stage).issues)
    assert all(issue.severity == validation.IssueSeverity.FAILURE for issue in issues)
    assert all(issue.requirement.code.endswith(".DJ.007") for issue in issues)
    return issues


@pytest.mark.parametrize("depth", [1, 3])
@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
def test_mimic_accepts_forwarded_reference_joint_relationship(joint_type, depth):
    stage, leader, _, mimic = _make_pair(joint_type)
    target = leader.GetPath()
    aliases = stage.DefinePrim("/Aliases")
    for index in range(depth):
        rel = aliases.CreateRelationship(f"leader_{index}")
        rel.SetTargets([target])
        target = rel.GetPath()
    mimic.GetReferenceJointRel().SetTargets([target])
    assert mimic.GetReferenceJointRel().GetForwardedTargets() == [leader.GetPath()]
    assert _issues(stage) == []


@pytest.mark.parametrize("kind", ["empty", "cyclic", "multiple", "dangling", "attribute"])
def test_mimic_rejects_invalid_forwarded_reference_without_checker_error(kind):
    stage, leader, _, mimic = _make_pair(UsdPhysics.RevoluteJoint)
    aliases = stage.DefinePrim("/Aliases")
    rel = aliases.CreateRelationship("leader")
    if kind == "cyclic":
        other = aliases.CreateRelationship("cycle")
        other.SetTargets([rel.GetPath()])
        rel.SetTargets([other.GetPath()])
    elif kind == "multiple":
        other = UsdPhysics.RevoluteJoint.Define(stage, "/OtherLeader")
        rel.SetTargets([leader.GetPath(), other.GetPath()])
    elif kind == "dangling":
        rel.SetTargets([Sdf.Path("/Missing.leader")])
    elif kind == "attribute":
        attribute = aliases.CreateAttribute("not_a_relationship", Sdf.ValueTypeNames.Float)
        attribute.Set(1.0)
        rel.SetTargets([attribute.GetPath()])
    mimic.GetReferenceJointRel().SetTargets([rel.GetPath()])
    assert _issues(stage)


def test_bad_forwarding_does_not_skip_later_mimic_instance():
    stage, leader, follower, mimic = _make_pair(UsdPhysics.RevoluteJoint)
    rel = stage.DefinePrim("/Aliases").CreateRelationship("empty")
    mimic.GetReferenceJointRel().SetTargets([rel.GetPath()])
    other = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), "rotY")
    other.CreateReferenceJointRel().SetTargets([leader.GetPath()])
    other.CreateGearingAttr(0.0)
    other.CreateNaturalFrequencyAttr(-1.0)
    other.CreateDampingRatioAttr(-1.0)
    issues = _issues(stage)
    assert any("number of reference joints" in issue.message for issue in issues)
    assert any("gear ratio == 0" in issue.message for issue in issues)


def test_forwarding_resolution_exception_is_a_requirement_failure(monkeypatch):
    stage, _, _, _ = _make_pair(UsdPhysics.RevoluteJoint)

    def unavailable_targets(_relationship):
        raise Tf.ErrorException("forwarding unavailable")

    monkeypatch.setattr(Usd.Relationship, "GetForwardedTargets", unavailable_targets)
    issues = _issues(stage)
    assert any("unresolvable reference joint relationship" in issue.message for issue in issues)


@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
@pytest.mark.parametrize(
    "leader_bounds, follower_bounds, gearing, offset, valid",
    [
        ((0.0, 0.0265), (-0.0265, 0.0), 1.0, 0.0, True),
        ((0.0, 0.0265), (0.0, 0.0265), -1.0, 0.0, True),
        ((1.0, 3.0), (-8.0, -4.0), 2.0, 2.0, True),
        ((1.0, 3.0), (0.0, 4.0), -2.0, 2.0, True),
        ((0.0, 2.0), (-1.0, 0.0), 1.0, 0.0, False),
        ((0.0, 2.0), (-2.0, -0.5), 1.0, 0.0, False),
        ((0.0, 2.0), (0.0, 1.0), -1.0, 0.0, False),
        ((0.0, 2.0), (1.0, 2.0), -1.0, 0.0, False),
        ((1.0, 3.0), (-6.0, -2.0), 2.0, 2.0, False),
        ((0.0, 2.0), (-2.0, 0.0), 0.0, 0.0, False),
        # Single-point/locked intervals are ordered, with inclusive endpoints.
        ((1.0, 1.0), (-3.0, -3.0), 2.0, 1.0, True),
        # Extra legal follower travel is allowed, but every mapped reference
        # endpoint must remain in that interval.
        ((1.0, 3.0), (-10.0, -2.0), 2.0, 2.0, True),
    ],
)
def test_mimic_maps_complete_interval_including_equal_endpoints(
    joint_type, leader_bounds, follower_bounds, gearing, offset, valid
):
    stage, _, _, _ = _make_pair(joint_type, leader_bounds, follower_bounds, gearing, offset)
    assert (not _issues(stage)) is valid


@pytest.mark.parametrize("axis", ["rotX", "rotY", "rotZ", "transX", "transY", "transZ", "X", "Y", "Z"])
def test_mimic_interval_preserves_existing_supported_instance_names(axis):
    stage, _, _, _ = _make_pair(UsdPhysics.PrismaticJoint, axis=axis)
    assert _issues(stage) == []


@pytest.mark.parametrize("gearing", [1.0, _DEFAULT])
@pytest.mark.parametrize("offset", [0.0, _DEFAULT])
def test_mimic_unauthored_schema_defaults_remain_valid(gearing, offset):
    stage, _, _, mimic = _make_pair(UsdPhysics.RevoluteJoint, gearing=gearing, offset=offset)
    assert mimic.GetGearingAttr().Get() == 1.0
    assert mimic.GetOffsetAttr().Get() == 0.0
    assert _issues(stage) == []


@pytest.mark.parametrize("field", ["gearing", "offset"])
@pytest.mark.parametrize("invalid", [None, math.nan, math.inf, -math.inf])
def test_mimic_blocked_or_nonfinite_coefficients_are_failures_not_pass_or_exception(field, invalid):
    stage, _, _, _ = _make_pair(UsdPhysics.PrismaticJoint, **{field: invalid})
    issues = _issues(stage)
    assert issues
    expected = "gear" if field == "gearing" else "offset"
    assert any(expected in issue.message.lower() for issue in issues)


@pytest.mark.parametrize("field", ["gearing", "offset"])
@pytest.mark.parametrize("invalid", ["0", "1", True])
def test_mimic_wrong_typed_coefficients_cannot_be_coerced_into_a_pass(field, invalid):
    stage, _, follower, mimic = _make_pair(UsdPhysics.PrismaticJoint)
    attribute = mimic.GetGearingAttr() if field == "gearing" else mimic.GetOffsetAttr()
    name = attribute.GetName()
    follower.GetPrim().RemoveProperty(name)
    type_name = Sdf.ValueTypeNames.String if isinstance(invalid, str) else Sdf.ValueTypeNames.Bool
    malformed = Sdf.AttributeSpec(stage.GetRootLayer().GetPrimAtPath(follower.GetPath()), name, type_name)
    malformed.default = invalid
    assert _issues(stage)


@pytest.mark.parametrize("target", ["leader", "follower"])
@pytest.mark.parametrize("endpoint", ["lower", "upper"])
@pytest.mark.parametrize("invalid", [None, math.nan, "not-a-number", True])
def test_mimic_missing_nan_or_malformed_limits_do_not_produce_a_false_pass(target, endpoint, invalid):
    stage, leader, follower, _ = _make_pair(UsdPhysics.PrismaticJoint)
    joint = leader if target == "leader" else follower
    attribute = joint.GetLowerLimitAttr() if endpoint == "lower" else joint.GetUpperLimitAttr()
    if invalid is None:
        attribute.Block()
    elif isinstance(invalid, (str, bool)):
        # USD can read malformed weaker/raw layer opinions despite the schema's
        # declared float type. Author the reduced bad opinion through Sdf.
        attribute_name = attribute.GetName()
        joint.GetPrim().RemoveProperty(attribute_name)
        type_name = Sdf.ValueTypeNames.String if isinstance(invalid, str) else Sdf.ValueTypeNames.Bool
        malformed = Sdf.AttributeSpec(stage.GetRootLayer().GetPrimAtPath(joint.GetPath()), attribute_name, type_name)
        malformed.default = invalid
    else:
        attribute.Set(invalid)
    assert _issues(stage)


@pytest.mark.parametrize("target", ["leader", "follower"])
def test_mimic_reversed_limit_interval_is_failure(target):
    bounds = {"leader_bounds": (2.0, 0.0)} if target == "leader" else {"follower_bounds": (0.0, -2.0)}
    stage, _, _, _ = _make_pair(UsdPhysics.RevoluteJoint, **bounds)
    assert _issues(stage)


@pytest.mark.parametrize("target", ["leader", "follower"])
@pytest.mark.parametrize("bounds", [(math.inf, math.inf), (-math.inf, -math.inf)])
def test_mimic_infinite_endpoint_direction_must_allow_a_finite_joint_position(target, bounds):
    # Unlike conventional lower=-inf / upper=+inf, these intervals cannot
    # contain any finite joint position. Matched signed infinities must not
    # fabricate an apparently valid mirrored interval.
    opposing = (-bounds[1], -bounds[0])
    leader_bounds, follower_bounds = (bounds, opposing) if target == "leader" else (opposing, bounds)
    stage, _, _, _ = _make_pair(UsdPhysics.PrismaticJoint, leader_bounds, follower_bounds)
    assert _issues(stage)


@pytest.mark.parametrize(
    "leader_bounds, follower_bounds, gearing, offset, valid",
    [
        ((-math.inf, math.inf), (-math.inf, math.inf), 1.0, 0.0, True),
        ((-math.inf, math.inf), (-math.inf, math.inf), -1.0, 2.0, True),
        ((0.0, math.inf), (-math.inf, -2.0), 1.0, 2.0, True),
        ((-math.inf, 0.0), (2.0, math.inf), 1.0, -2.0, True),
        ((0.0, math.inf), (0.0, math.inf), -1.0, 0.0, True),
        ((0.0, 2.0), (-math.inf, math.inf), 1.0, 0.0, True),
        ((-math.inf, math.inf), (-2.0, 0.0), 1.0, 0.0, False),
        ((0.0, math.inf), (-2.0, 0.0), 1.0, 0.0, False),
    ],
)
def test_mimic_preserves_legitimate_unbounded_limits(leader_bounds, follower_bounds, gearing, offset, valid):
    stage, _, _, _ = _make_pair(UsdPhysics.PrismaticJoint, leader_bounds, follower_bounds, gearing, offset)
    assert (not _issues(stage)) is valid


@pytest.mark.parametrize("invalid_field", ["gearing", "offset"])
@pytest.mark.parametrize("invalid", [None, math.nan, math.inf])
def test_invalid_mimic_coefficient_does_not_skip_remaining_instances(invalid_field, invalid):
    stage, _, follower, _ = _make_pair(UsdPhysics.RevoluteJoint, **{invalid_field: invalid})
    second = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), "rotZ")
    second.CreateReferenceJointRel().SetTargets(["/Leader"])
    second.CreateGearingAttr(0.0)
    second.CreateOffsetAttr(0.0)
    second.CreateNaturalFrequencyAttr(-1.0)
    second.CreateDampingRatioAttr(-1.0)
    issues = _issues(stage)
    assert len(issues) >= 2
    assert any("gear ratio == 0" in issue.message for issue in issues)


@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
def test_single_dof_joint_cannot_reference_itself_even_when_equation_is_an_identity(joint_type):
    stage, _, follower, mimic = _make_pair(joint_type, follower_bounds=(-2.0, 2.0), gearing=-1.0)
    mimic.GetReferenceJointRel().SetTargets([follower.GetPath()])
    issues = _issues(stage)
    assert any("own joint DOF" in issue.message for issue in issues)

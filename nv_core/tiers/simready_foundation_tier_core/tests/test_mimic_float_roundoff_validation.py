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
"""Real USD Float boundary roundoff is not an actuator travel tolerance."""

import math

import pytest
from pxr import Sdf, UsdPhysics
from test_mimic_interval_validation import _issues, _make_pair


@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
@pytest.mark.parametrize(
    "leader_bounds, follower_bounds, gearing, offset",
    [
        # Stored Float coefficients expand to doubles: 0.2*2 + 0.1 becomes
        # 0.5000000074505806. Both gearing signs must retain boundary equality.
        ((0.0, 2.0), (-0.5, -0.1), 0.2, 0.1),
        ((0.0, 2.0), (0.1, 0.5), -0.2, -0.1),
        # Cancellation can leave an apparent nonzero endpoint although the
        # intended 0.3*3 - 0.9 boundary is zero. This requires an operand-scaled
        # roundoff bound, not relative tolerance against the zero result.
        ((2.0, 3.0), (0.0, 0.3), 0.3, -0.9),
        ((2.0, 3.0), (-0.3, 0.0), -0.3, 0.9),
    ],
)
def test_mimic_float_boundary_roundoff_and_cancellation_remain_valid(
    joint_type, leader_bounds, follower_bounds, gearing, offset
):
    stage, _, _, _ = _make_pair(joint_type, leader_bounds, follower_bounds, gearing, offset)
    assert _issues(stage) == []


@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
@pytest.mark.parametrize(
    "leader_bounds, follower_bounds, gearing, offset",
    [
        # Discrepancies above the float32 arithmetic-roundoff budget must not
        # be granted a physical margin at either endpoint or gearing sign.
        ((0.0, 2.0), (-0.499999, -0.1), 0.2, 0.1),
        ((0.0, 2.0), (-0.5, -0.100001), 0.2, 0.1),
        ((0.0, 2.0), (0.100001, 0.5), -0.2, -0.1),
        ((0.0, 2.0), (0.1, 0.499999), -0.2, -0.1),
        ((2.0, 3.0), (0.00001, 0.3), 0.3, -0.9),
        ((2.0, 3.0), (-0.3, -0.00001), -0.3, 0.9),
        # A fixed absolute epsilon would accept half the whole tiny interval;
        # the arithmetic bound must scale with the actual operands instead.
        ((0.0, 1e-8), (-5e-9, 0.0), 1.0, 0.0),
    ],
)
def test_mimic_genuine_limit_violations_are_not_hidden_by_float_roundoff(
    joint_type, leader_bounds, follower_bounds, gearing, offset
):
    stage, _, _, _ = _make_pair(joint_type, leader_bounds, follower_bounds, gearing, offset)
    issues = _issues(stage)
    assert any("mapped mimic" in issue.message for issue in issues)


@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
@pytest.mark.parametrize(
    "leader_bounds, follower_bounds, gearing, offset",
    [
        ((0.0, math.inf), (-0.5, -0.1), 1.0, 0.1),
        ((0.0, math.inf), (0.1, 0.5), -1.0, -0.1),
        ((-math.inf, math.inf), (-2.0, 2.0), 0.2, 0.1),
    ],
)
def test_mimic_infinite_mapped_interval_cannot_pass_with_infinite_roundoff_budget(
    joint_type, leader_bounds, follower_bounds, gearing, offset
):
    stage, _, _, _ = _make_pair(joint_type, leader_bounds, follower_bounds, gearing, offset)
    assert _issues(stage)


@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
def test_mimic_nonfinite_computed_roundoff_budget_cannot_authorize_an_invalid_interval(joint_type):
    # Malformed numeric Double opinions can exceed the schema's Float range.
    # Cancellation leaves mapped=0 finite, while the operand-magnitude sum
    # overflows. Such an infinite computed budget must not authorize [1, 2].
    stage, leader, _, mimic = _make_pair(joint_type, (0.0, 0.0), (1.0, 2.0))
    attributes = [leader.GetLowerLimitAttr(), leader.GetUpperLimitAttr(), mimic.GetOffsetAttr()]
    values = [-1e308, -1e308, 1e308]
    for attribute, value in zip(attributes, values, strict=True):
        prim = attribute.GetPrim()
        name = attribute.GetName()
        prim.RemoveProperty(name)
        opinion = Sdf.AttributeSpec(stage.GetRootLayer().GetPrimAtPath(prim.GetPath()), name, Sdf.ValueTypeNames.Double)
        opinion.default = value
    assert any("mapped mimic" in issue.message for issue in _issues(stage))

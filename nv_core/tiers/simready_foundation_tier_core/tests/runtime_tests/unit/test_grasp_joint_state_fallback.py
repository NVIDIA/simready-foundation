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
"""Schema-default joint state cannot masquerade as native measured state."""

from types import SimpleNamespace

import pytest
from pxr import Sdf, Usd, UsdPhysics
from test_grasp_scene_fixture_controls import production_robot as production_robot
from test_grasp_scene_fixture_controls import production_scene as production_scene

STATE = "state:linear:physics:position"


@pytest.mark.parametrize("state", [0.0, -0.02])
def test_authored_state_values_remain_eligible_without_replacing_zero(production_robot, state):
    robot = production_robot.robot
    prim = UsdPhysics.PrismaticJoint.Define(production_robot.harness.stage, robot.LEFT_JOINT).GetPrim()
    attribute = prim.CreateAttribute(STATE, Sdf.ValueTypeNames.Double)
    attribute.Set(state)
    assert attribute.GetResolveInfo(Usd.TimeCode.Default()).GetSource() == Usd.ResolveInfoSourceDefault
    assert robot.get_gripper_joint_position() == state


def test_drive_target_can_retain_its_legal_schema_default(production_robot):
    robot = production_robot.robot
    prim = UsdPhysics.PrismaticJoint.Define(production_robot.harness.stage, robot.LEFT_JOINT).GetPrim()
    drive = UsdPhysics.DriveAPI.Apply(prim, "linear")
    attribute = drive.GetTargetPositionAttr()
    assert attribute.HasValue()
    assert not attribute.HasAuthoredValueOpinion()
    assert attribute.GetResolveInfo(Usd.TimeCode.Default()).GetSource() == Usd.ResolveInfoSourceFallback
    assert robot.get_gripper_joint_target() == attribute.Get()


@pytest.mark.parametrize("has_authored", [False, True])
def test_fallback_state_is_rejected_before_numeric_read_even_with_nondefault_opinion(production_robot, has_authored):
    robot = production_robot.robot
    attribute = SimpleNamespace(
        IsValid=lambda: True,
        HasValue=lambda: True,
        HasAuthoredValueOpinion=lambda: has_authored,
        GetResolveInfo=lambda _time: SimpleNamespace(GetSource=lambda: Usd.ResolveInfoSourceFallback),
        Get=lambda: pytest.fail("schema fallback must not become a measured zero"),
    )
    prim = SimpleNamespace(IsValid=lambda: True, GetAttribute=lambda _name: attribute)
    robot._stage = SimpleNamespace(GetPrimAtPath=lambda _path: prim)
    with pytest.raises(RuntimeError, match="schema fallback"):
        robot.get_gripper_joint_position()


def test_real_physx_joint_schema_zero_fallback_is_not_live_state(production_robot):
    provider = pytest.importorskip("physx_usd_schemas")
    robot = production_robot.robot
    prim = UsdPhysics.PrismaticJoint.Define(production_robot.harness.stage, robot.LEFT_JOINT).GetPrim()
    provider.PhysxSchema.JointStateAPI.Apply(prim, "linear")
    attribute = prim.GetAttribute(STATE)
    assert attribute.IsValid() and attribute.HasValue()
    assert attribute.Get() == 0.0
    assert not attribute.HasAuthoredValueOpinion()
    assert attribute.GetResolveInfo(Usd.TimeCode.Default()).GetSource() == Usd.ResolveInfoSourceFallback
    with pytest.raises(RuntimeError, match="schema fallback"):
        robot.get_gripper_joint_position()
    # An actual authored native readback remains eligible, including zero.
    attribute.Set(0.0)
    assert robot.get_gripper_joint_position() == 0.0


def test_bilateral_pair_rejects_second_jaw_schema_fallback(production_robot):
    provider = pytest.importorskip("physx_usd_schemas")
    robot = production_robot.robot
    stage = production_robot.harness.stage
    for path in (robot.LEFT_JOINT, robot.GANTRY_X + "/right_joint"):
        prim = UsdPhysics.PrismaticJoint.Define(stage, path).GetPrim()
        provider.PhysxSchema.JointStateAPI.Apply(prim, "linear")
    stage.GetPrimAtPath(robot.LEFT_JOINT).GetAttribute(STATE).Set(-0.02)
    with pytest.raises(RuntimeError, match="schema fallback"):
        robot.get_finger_joint_positions()

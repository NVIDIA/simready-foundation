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
"""Tests for articulation_phases.robot_type."""
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.articulation_phases.robot_type import (
    RobotType,
    determine_robot_type,
    get_scene_defaults,
    has_authored_robot_type,
    read_robot_type,
)


def _stage_with_asset(robot_type_token=None, joint_types=None):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset_prim = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    if robot_type_token is not None:
        attr = asset_prim.CreateAttribute("isaac:robotType", Sdf.ValueTypeNames.String)
        attr.Set(robot_type_token)
    if joint_types:
        for i, jt in enumerate(joint_types):
            path = "/World/Asset/joint_%d" % i
            if jt == "revolute":
                UsdPhysics.RevoluteJoint.Define(stage, path)
            elif jt == "prismatic":
                UsdPhysics.PrismaticJoint.Define(stage, path)
    return stage, asset_prim


def test_read_robot_type_arm_default_when_no_attribute():
    stage, asset_prim = _stage_with_asset()
    assert read_robot_type(stage, asset_prim) == RobotType.ARM


def test_read_robot_type_gripper_from_attribute():
    stage, asset_prim = _stage_with_asset(robot_type_token="gripper")
    assert read_robot_type(stage, asset_prim) == RobotType.GRIPPER


def test_read_robot_type_is_case_insensitive():
    stage, asset_prim = _stage_with_asset(robot_type_token="GRIPPER")
    assert read_robot_type(stage, asset_prim) == RobotType.GRIPPER


def test_read_robot_type_unknown_falls_back_to_arm():
    stage, asset_prim = _stage_with_asset(robot_type_token="unknown_type_xyz")
    assert read_robot_type(stage, asset_prim) == RobotType.ARM


def test_read_robot_type_mobile_base_aliases():
    stage, asset_prim = _stage_with_asset(robot_type_token="wheeled")
    assert read_robot_type(stage, asset_prim) == RobotType.MOBILE_BASE


def test_determine_robot_type_scara_fallback_4_revolute_1_prismatic():
    stage, asset_prim = _stage_with_asset(joint_types=["revolute", "revolute", "revolute", "prismatic"])
    assert determine_robot_type(stage, asset_prim) == RobotType.SCARA


def test_determine_robot_type_no_scara_with_only_3_joints():
    stage, asset_prim = _stage_with_asset(joint_types=["revolute", "revolute", "prismatic"])
    assert determine_robot_type(stage, asset_prim) == RobotType.ARM


def test_determine_robot_type_no_scara_when_two_prismatic():
    stage, asset_prim = _stage_with_asset(joint_types=["revolute", "revolute", "revolute", "prismatic", "prismatic"])
    assert determine_robot_type(stage, asset_prim) == RobotType.ARM


def test_determine_robot_type_attribute_beats_structural_scara():
    stage, asset_prim = _stage_with_asset(
        robot_type_token="gripper",
        joint_types=["revolute", "revolute", "revolute", "prismatic"],
    )
    assert determine_robot_type(stage, asset_prim) == RobotType.GRIPPER


def test_get_scene_defaults_arm_no_ground_plane():
    # Gravity is on for all robot types now; arms simply float (no ground plane).
    d = get_scene_defaults(RobotType.ARM)
    assert d["activate_ground_plane"] is False


def test_get_scene_defaults_gripper_activates_ground_plane():
    d = get_scene_defaults(RobotType.GRIPPER)
    assert d["activate_ground_plane"] is True


def test_get_scene_defaults_unknown_returns_empty():
    d = get_scene_defaults(RobotType.COMPOSITE)
    assert d == {}


# has_authored_robot_type — companion to read_robot_type, used by the
# unauthored-fallback heuristic in setup_robot_test_scene.
# -----------------------------------------------------------------------------


def test_has_authored_robot_type_false_when_attribute_missing():
    stage, asset_prim = _stage_with_asset()
    assert has_authored_robot_type(stage, asset_prim) is False


def test_has_authored_robot_type_true_when_authored():
    stage, asset_prim = _stage_with_asset(robot_type_token="gripper")
    assert has_authored_robot_type(stage, asset_prim) is True


def test_has_authored_robot_type_false_when_attr_defined_but_unauthored():
    """A schema may define isaac:robotType but never author a value — that
    counts as 'not authored' so the heuristic still kicks in."""
    stage, asset_prim = _stage_with_asset()
    attr = asset_prim.CreateAttribute("isaac:robotType", Sdf.ValueTypeNames.String)
    # Don't call attr.Set(...) — the attribute exists but has no authored value.
    assert attr.HasAuthoredValue() is False
    assert has_authored_robot_type(stage, asset_prim) is False

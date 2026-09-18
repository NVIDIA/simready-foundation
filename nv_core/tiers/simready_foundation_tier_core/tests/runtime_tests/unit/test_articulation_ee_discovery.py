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
"""Tests for articulation_phases.ee_discovery."""
import pytest
from pxr import Usd, UsdGeom
from simready_benchmark_kit_suite.articulation_phases.ee_discovery import (
    _find_ee_from_robot_links,
    _find_fixed_ee_child,
    discover_end_effector_link,
)

try:
    from pxr import PhysxSchema  # noqa: F401

    _HAS_PHYSX_SCHEMA = True
except ImportError:
    _HAS_PHYSX_SCHEMA = False


def _make_robot_stage_with_flange():
    """Stage layout:

    /World (Xform)
        /robot (Xform, has isaac:physics:robotLinks rel)
            /link0 (Xform)
            /link1 (Xform)
            /J6_link (Xform, last in robotLinks)
                /flange (Xform)        <- expected EE
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    robot = UsdGeom.Xform.Define(stage, "/World/robot").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/robot/link0")
    UsdGeom.Xform.Define(stage, "/World/robot/link1")
    j6 = UsdGeom.Xform.Define(stage, "/World/robot/J6_link").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/robot/J6_link/flange")

    rel = robot.CreateRelationship("isaac:physics:robotLinks", custom=False)
    rel.AddTarget("/World/robot/link0")
    rel.AddTarget("/World/robot/link1")
    rel.AddTarget("/World/robot/J6_link")
    return stage, robot, j6


def test_find_fixed_ee_child_returns_flange_path():
    _stage, _robot, j6 = _make_robot_stage_with_flange()
    result = _find_fixed_ee_child(j6)
    assert result == "/World/robot/J6_link/flange"


def test_find_fixed_ee_child_returns_none_when_no_match():
    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/World/parent").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/parent/random_child")
    assert _find_fixed_ee_child(parent) is None


def test_discover_end_effector_link_uses_robot_links_rel_and_flange():
    stage, _robot, _j6 = _make_robot_stage_with_flange()
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/robot")
    assert result == "/World/robot/J6_link/flange"


def test_find_ee_from_robot_links_returns_last_target_when_no_flange():
    """No fixed EE child -> falls back to the last articulated link itself."""
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    robot = UsdGeom.Xform.Define(stage, "/World/robot").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/robot/link0")
    UsdGeom.Xform.Define(stage, "/World/robot/link1")
    UsdGeom.Xform.Define(stage, "/World/robot/some_terminal_link")

    rel = robot.CreateRelationship("isaac:physics:robotLinks", custom=False)
    rel.AddTarget("/World/robot/link0")
    rel.AddTarget("/World/robot/link1")
    rel.AddTarget("/World/robot/some_terminal_link")

    result = _find_ee_from_robot_links(stage, robot)
    assert result == "/World/robot/some_terminal_link"


def test_discover_end_effector_link_returns_none_for_missing_root():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/does_not_exist")
    assert result is None


def test_discover_end_effector_link_empty_stage_returns_none():
    stage = Usd.Stage.CreateInMemory()
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/robot")
    assert result is None


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_end_effector_link_with_physx_schema_present():
    """Smoke test: same flange-discovery path still works when PhysxSchema
    is importable in the environment."""
    stage, _robot, _j6 = _make_robot_stage_with_flange()
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/robot")
    assert result == "/World/robot/J6_link/flange"

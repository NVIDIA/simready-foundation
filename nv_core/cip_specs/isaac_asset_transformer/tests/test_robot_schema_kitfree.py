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
"""Tests for the Kit-free ``RobotSchemaRule`` fallback.

The Isaac robot schema (``usd.schema.isaac``) ships as a Kit extension and is not
available in this standalone/CI environment, so importing ``robot_schema`` here
selects the Kit-free fallback path (``_HAS_ISAAC_SCHEMA is False``). These tests
assert that the fallback authors exactly what the SimReady RC.007 validator
checks: an ``IsaacRobotAPI`` applied schema plus non-empty
``isaac:physics:robotLinks`` / ``isaac:physics:robotJoints`` relationships. The
``isaac:robotType`` attribute is intentionally left unauthored.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pxr")
from conftest import SOURCE_ROOT  # noqa: E402,F401  (ensures src is on sys.path)
from pxr import Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402
from simready.asset_transformer.rules.isaac_sim import robot_schema  # noqa: E402

_ROBOT_LINKS_REL = "isaac:physics:robotLinks"
_ROBOT_JOINTS_REL = "isaac:physics:robotJoints"


def _build_robot_stage() -> tuple[Usd.Stage, Usd.Prim]:
    """Create a minimal articulated robot: root + two rigid links + one joint."""
    stage = Usd.Stage.CreateInMemory()
    robot = UsdGeom.Xform.Define(stage, "/robot")
    stage.SetDefaultPrim(robot.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(robot.GetPrim())

    base_link = UsdGeom.Xform.Define(stage, "/robot/base_link")
    UsdPhysics.RigidBodyAPI.Apply(base_link.GetPrim())
    link_1 = UsdGeom.Xform.Define(stage, "/robot/link_1")
    UsdPhysics.RigidBodyAPI.Apply(link_1.GetPrim())

    UsdGeom.Xform.Define(stage, "/robot/joints")
    UsdPhysics.RevoluteJoint.Define(stage, "/robot/joints/joint_1")
    return stage, robot.GetPrim()


def test_fallback_is_active_without_isaac_schema():
    assert robot_schema._HAS_ISAAC_SCHEMA is False


def test_kitfree_fallback_authors_robot_api_and_relationships(tmp_path):
    stage, robot_prim = _build_robot_stage()
    rule = robot_schema.RobotSchemaRule(stage, str(tmp_path), "", {"params": {}})

    root_link, root_joint = rule._author_robot_schema_kitfree(stage, robot_prim)

    # ``IsaacRobotAPI`` is unregistered in the Kit-free runtime, so it will not
    # surface via GetAppliedSchemas() here; assert on the authored apiSchemas
    # list op (the Kit validator, which has the schema registered, resolves it).
    api_schemas = robot_prim.GetMetadata("apiSchemas").GetAddedOrExplicitItems()
    assert "IsaacRobotAPI" in api_schemas
    assert "PhysicsArticulationRootAPI" in api_schemas

    links_rel = robot_prim.GetRelationship(_ROBOT_LINKS_REL)
    assert links_rel
    assert set(links_rel.GetTargets()) == {
        Sdf.Path("/robot/base_link"),
        Sdf.Path("/robot/link_1"),
    }

    joints_rel = robot_prim.GetRelationship(_ROBOT_JOINTS_REL)
    assert joints_rel
    assert list(joints_rel.GetTargets()) == [Sdf.Path("/robot/joints/joint_1")]

    # robotType is intentionally deferred (RC.008/RC.009 remain out of scope).
    assert not robot_prim.GetAttribute("isaac:robotType").IsValid()

    assert root_link is not None and root_link.GetPath() == Sdf.Path("/robot/base_link")
    assert root_joint is not None and root_joint.GetPath() == Sdf.Path("/robot/joints/joint_1")


def test_kitfree_fallback_handles_no_physics_content(tmp_path):
    stage = Usd.Stage.CreateInMemory()
    robot = UsdGeom.Xform.Define(stage, "/robot")
    stage.SetDefaultPrim(robot.GetPrim())

    rule = robot_schema.RobotSchemaRule(stage, str(tmp_path), "", {"params": {}})
    root_link, root_joint = rule._author_robot_schema_kitfree(stage, robot.GetPrim())

    assert "IsaacRobotAPI" in robot.GetPrim().GetMetadata("apiSchemas").GetAddedOrExplicitItems()
    assert list(robot.GetPrim().GetRelationship(_ROBOT_LINKS_REL).GetTargets()) == []
    assert list(robot.GetPrim().GetRelationship(_ROBOT_JOINTS_REL).GetTargets()) == []
    assert root_link is None and root_joint is None

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
"""Tests for articulation_phases.mimic_joints."""
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.articulation_phases.mimic_joints import (
    MimicJointSpec,
    detect_mimic_joints,
)

try:
    from pxr import PhysxSchema  # noqa: F401

    _HAS_PHYSX_SCHEMA = True
except ImportError:
    _HAS_PHYSX_SCHEMA = False


def _make_stage_with_mimic(ref_path, follower_path, gear, offset):
    """Author a stage with a revolute reference joint and a prismatic follower joint.

    The follower carries PhysxMimicJointAPI pointing to the reference joint with
    the given gear + offset. Returns (stage, asset_prim, robot_prim_path).
    """
    from pxr import PhysxSchema

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot")
    # Dummy link prims for joint bodies.
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot/linkA")
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot/linkB")
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot/linkC")

    ref = UsdPhysics.RevoluteJoint.Define(stage, ref_path)
    ref.CreateBody0Rel().SetTargets(["/World/Asset/Robot/linkA"])
    ref.CreateBody1Rel().SetTargets(["/World/Asset/Robot/linkB"])

    follower = UsdPhysics.PrismaticJoint.Define(stage, follower_path)
    follower.CreateBody0Rel().SetTargets(["/World/Asset/Robot/linkB"])
    follower.CreateBody1Rel().SetTargets(["/World/Asset/Robot/linkC"])

    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), UsdPhysics.Tokens.rotX)
    # Attribute names resolved in plan Task 1 Step 1; update here if they differ.
    mimic.CreateReferenceJointRel().SetTargets([ref_path])
    mimic.CreateGearingAttr().Set(float(gear))
    mimic.CreateOffsetAttr().Set(float(offset))
    return stage, asset, "/World/Asset/Robot"


def test_detect_mimic_joints_returns_empty_for_asset_without_mimics():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot")
    specs = detect_mimic_joints(stage, asset, "/World/Asset/Robot", ["j0", "j1"])
    assert specs == []


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_detect_mimic_joints_extracts_reference_gear_offset():
    stage, asset, robot_path = _make_stage_with_mimic(
        "/World/Asset/Robot/ref_joint",
        "/World/Asset/Robot/follower_joint",
        gear=0.5,
        offset=0.01,
    )
    specs = detect_mimic_joints(stage, asset, robot_path, ["ref_joint", "follower_joint"])
    assert len(specs) == 1
    s = specs[0]
    assert isinstance(s, MimicJointSpec)
    assert s.follower_joint_path == "/World/Asset/Robot/follower_joint"
    assert s.reference_joint_path == "/World/Asset/Robot/ref_joint"
    assert abs(s.gear - 0.5) < 1e-9
    assert abs(s.offset - 0.01) < 1e-9
    assert s.reference_dof_index == 0
    assert s.follower_dof_index == 1


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_detect_mimic_joints_returns_none_dof_index_when_name_missing():
    stage, asset, robot_path = _make_stage_with_mimic(
        "/World/Asset/Robot/ref_joint",
        "/World/Asset/Robot/follower_joint",
        gear=1.0,
        offset=0.0,
    )
    specs = detect_mimic_joints(stage, asset, robot_path, ["some_other_joint"])
    assert len(specs) == 1
    assert specs[0].reference_dof_index is None
    assert specs[0].follower_dof_index is None


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_detect_mimic_joints_skips_mimic_with_no_reference():
    from pxr import PhysxSchema

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot")
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot/linkA")
    UsdGeom.Xform.Define(stage, "/World/Asset/Robot/linkB")
    follower = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/Robot/orphan_follower")
    follower.CreateBody0Rel().SetTargets(["/World/Asset/Robot/linkA"])
    follower.CreateBody1Rel().SetTargets(["/World/Asset/Robot/linkB"])
    PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), UsdPhysics.Tokens.rotX)
    # No reference joint authored -> should be skipped by the detector.
    specs = detect_mimic_joints(stage, asset, "/World/Asset/Robot", ["orphan_follower"])
    assert specs == []

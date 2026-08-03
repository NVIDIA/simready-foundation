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
"""Tests for articulation_phases.passive_joints."""
from pxr import Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.articulation_phases.passive_joints import (
    detect_passive_joints,
)


def _stage_with_joints(joint_specs):
    """joint_specs: list of (name, joint_type, drive_stiffness) tuples."""
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    UsdGeom.Xform.Define(stage, "/World/Asset/joints")
    for name, jt, stiffness in joint_specs:
        path = "/World/Asset/joints/%s" % name
        if jt == "revolute":
            j = UsdPhysics.RevoluteJoint.Define(stage, path)
            drive_api = "angular"
        else:
            j = UsdPhysics.PrismaticJoint.Define(stage, path)
            drive_api = "linear"
        if stiffness is not None:
            drive = UsdPhysics.DriveAPI.Apply(j.GetPrim(), drive_api)
            drive.CreateStiffnessAttr(float(stiffness))
    return stage


def test_detect_passive_joints_none_when_all_driven():
    stage = _stage_with_joints(
        [
            ("joint_a", "revolute", 100.0),
            ("joint_b", "revolute", 200.0),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_b"])
    assert indices == frozenset()
    assert names == []


def test_detect_passive_joints_flags_zero_stiffness():
    stage = _stage_with_joints(
        [
            ("joint_a", "revolute", 100.0),
            ("joint_passive", "revolute", 0.0),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])
    assert indices == frozenset({1})
    assert names == ["joint_passive"]


def test_detect_passive_joints_flags_missing_drive():
    stage = _stage_with_joints(
        [
            ("joint_a", "revolute", 100.0),
            ("joint_passive", "revolute", None),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["joint_a", "joint_passive"])
    assert indices == frozenset({1})


def test_detect_passive_joints_prismatic_with_linear_drive():
    stage = _stage_with_joints(
        [
            ("slider_a", "prismatic", 50.0),
            ("slider_b", "prismatic", None),
        ]
    )
    indices, names = detect_passive_joints(stage, "/World/Asset", ["slider_a", "slider_b"])
    assert 1 in indices
    assert 0 not in indices


def test_detect_passive_joints_handles_invalid_input():
    stage = Usd.Stage.CreateInMemory()
    indices, names = detect_passive_joints(stage, "/NonExistent", ["joint_a"])
    assert indices == frozenset()

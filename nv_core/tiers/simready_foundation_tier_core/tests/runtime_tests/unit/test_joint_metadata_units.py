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
import pytest
from simready.foundation.tier_core.runtime_tests.motion_observer import joint_metadata


@pytest.mark.parametrize("meters_per_unit", [1.0, 0.01])
@pytest.mark.parametrize("joint_type,expected_unit", [("prismatic", "unknown_native"), ("revolute", "rad")])
def test_joint_metadata_does_not_guess_linear_tensor_scale(meters_per_unit, joint_type, expected_unit):
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    schema = UsdPhysics.PrismaticJoint if joint_type == "prismatic" else UsdPhysics.RevoluteJoint
    joint = schema.Define(stage, "/Robot/joint")
    joint.CreateLowerLimitAttr(0.0)
    joint.CreateUpperLimitAttr(100.0)
    drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear" if joint_type == "prismatic" else "angular")
    drive.CreateTargetPositionAttr(50.0)
    drive.CreateStiffnessAttr(2.0)
    before = stage.GetRootLayer().ExportToString()

    info = joint_metadata(stage, root, "joint")

    assert info["identity_resolved"]
    assert info["unit"] == expected_unit
    assert info["meters_per_unit"] == meters_per_unit
    assert info["authored_drive"]["stiffness"] == 2.0
    if joint_type == "prismatic":
        assert "not verified" in info["unit_basis"]
    else:
        assert "radians" in info["unit_basis"]
    assert stage.GetRootLayer().ExportToString() == before

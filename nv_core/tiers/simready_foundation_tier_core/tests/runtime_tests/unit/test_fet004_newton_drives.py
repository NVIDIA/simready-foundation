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

"""Regression tests for temporary Newton position-drive authoring."""

from pxr import Usd, UsdPhysics
from simready_benchmark_kit_suite.fet004_multibody.newton_drive import (
    activate_newton_position_drives,
    restore_newton_position_drives,
)


def _joint(stage, path, type_name):
    if type_name == "PhysicsRevoluteJoint":
        UsdPhysics.RevoluteJoint.Define(stage, path)
    else:
        UsdPhysics.PrismaticJoint.Define(stage, path)
    return {"prim_path": path, "type_name": type_name}


def test_newton_position_drive_is_removed_when_it_was_temporary():
    stage = Usd.Stage.CreateInMemory()
    joint = _joint(stage, "/revolute", "PhysicsRevoluteJoint")
    prim = stage.GetPrimAtPath(joint["prim_path"])

    activated = activate_newton_position_drives(stage, [joint], {})

    assert prim.HasAPI(UsdPhysics.DriveAPI, "angular")
    drive = UsdPhysics.DriveAPI(prim, "angular")
    assert drive.GetStiffnessAttr().Get() == 1.0e4
    assert drive.GetDampingAttr().Get() == 5.0e2
    assert drive.GetMaxForceAttr().Get() == 1.0e7

    restore_newton_position_drives(stage, activated)

    assert not prim.HasAPI(UsdPhysics.DriveAPI, "angular")


def test_newton_position_drive_restores_existing_authored_values():
    stage = Usd.Stage.CreateInMemory()
    joint = _joint(stage, "/prismatic", "PhysicsPrismaticJoint")
    prim = stage.GetPrimAtPath(joint["prim_path"])
    drive = UsdPhysics.DriveAPI.Apply(prim, "linear")
    drive.CreateStiffnessAttr(12.0)
    drive.CreateDampingAttr(34.0)
    drive.CreateTargetPositionAttr(0.25)

    activated = activate_newton_position_drives(
        stage,
        [joint],
        {
            "newton_drive_stiffness_linear": 900.0,
            "newton_drive_damping": 80.0,
            "drive_max_force": 700.0,
        },
    )

    assert drive.GetStiffnessAttr().Get() == 900.0
    assert drive.GetDampingAttr().Get() == 80.0
    assert drive.GetMaxForceAttr().Get() == 700.0
    assert drive.GetTargetPositionAttr().Get() == 0.0

    restore_newton_position_drives(stage, activated)

    assert prim.HasAPI(UsdPhysics.DriveAPI, "linear")
    assert drive.GetStiffnessAttr().Get() == 12.0
    assert drive.GetDampingAttr().Get() == 34.0
    assert drive.GetTargetPositionAttr().Get() == 0.25
    assert not drive.GetMaxForceAttr().HasAuthoredValueOpinion()
    assert not drive.GetTargetVelocityAttr().HasAuthoredValueOpinion()

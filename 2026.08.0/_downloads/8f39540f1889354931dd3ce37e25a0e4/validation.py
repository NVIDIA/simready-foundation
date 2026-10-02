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

__all__ = [
    "IMUSensorChecker",
    "JointSensorChecker",
]

import logging

import simready.foundation.sensors.requirements as cap
from pxr import Usd, UsdGeom, UsdPhysics
from usd_validation_nvidia import BaseRuleChecker, register_requirements, register_rule

logger = logging.getLogger(__name__)


@register_rule("PhysicsSensors")
@register_requirements(cap.PhysicsSensorsRequirements.PS_001)
class IMUSensorChecker(BaseRuleChecker):
    """
    Validate that an IsaacImuSensor prim is attached to or parented
    under a prim that has PhysicsRigidBodyAPI.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.GetTypeName() != "IsaacImuSensor":
            return

        found_rigid_body = False
        test_prim = prim
        while test_prim:
            if test_prim.HasAPI(UsdPhysics.RigidBodyAPI):
                found_rigid_body = True
                break
            if test_prim.IsA(UsdGeom.Xformable):
                if UsdGeom.Xformable(test_prim).GetResetXformStack():
                    break
            test_prim = test_prim.GetParent()

        if not found_rigid_body:
            self._AddFailedCheck(
                message="IsaacImuSensor prim must be a descendant of a prim with PhysicsRigidBodyAPI.",
                at=prim,
                requirement=cap.PhysicsSensorsRequirements.PS_001,
            )


@register_rule("PhysicsSensors")
@register_requirements(cap.PhysicsSensorsRequirements.PS_002)
class JointSensorChecker(BaseRuleChecker):
    """
    Validate that an IsaacJointStateSensor prim also has PhysicsArticulationRootAPI.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.GetTypeName() != "IsaacJointStateSensor":
            return

        if not prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            self._AddFailedCheck(
                message="IsaacJointStateSensor prim must also have PhysicsArticulationRootAPI applied.",
                at=prim,
                requirement=cap.PhysicsSensorsRequirements.PS_002,
            )

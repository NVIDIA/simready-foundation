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
import omni.capabilities as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics, UsdShade


@usd_validation_nvidia.register_rule("ColliderApproximations")
@usd_validation_nvidia.register_requirements(cap.ColliderApproximationsRequirements.COL_001, override=True)
class ColliderApproximationsCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    COLLIDER_APPROXIMATION_REQUIREMENT = cap.ColliderApproximationsRequirements.COL_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                # Check if this is a mesh collider that needs SDF approximation
                if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
                    # Check for physics:approximation attribute
                    approx_attr = prim.GetAttribute("physics:approximation")
                    if not approx_attr:
                        self._AddFailedCheck(
                            "Mesh collider has no physics:approximation attribute.",
                            at=prim,
                            requirement=self.COLLIDER_APPROXIMATION_REQUIREMENT,
                        )
                        return

                    # Check if approximation is set to "sdf"
                    approx_value = approx_attr.Get()
                    if approx_value != "sdf":
                        self._AddFailedCheck(
                            f"Mesh collider approximation is set to '{approx_value}' instead of 'sdf'.",
                            at=prim,
                            requirement=self.COLLIDER_APPROXIMATION_REQUIREMENT,
                        )
                        return

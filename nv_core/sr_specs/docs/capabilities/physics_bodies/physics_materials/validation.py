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


@usd_validation_nvidia.register_rule("PhysicsMaterials")
@usd_validation_nvidia.register_requirements(cap.PhysicsMaterialsRequirements.PMT_001, override=True)
class PhysicsMaterialsCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    COLLISION_API_MATERIAL_BINDING_REQUIREMENT = cap.PhysicsMaterialsRequirements.PMT_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for prim in Usd.PrimRange(default_prim):
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue

            # Resolve the material bound for the "physics" purpose. This honors the
            # standard USD fallback to the allPurpose ``material:binding`` when no
            # explicit ``material:binding:physics`` relationship is authored.
            binding_api = UsdShade.MaterialBindingAPI(prim)
            material, _ = binding_api.ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.physics)

            if not material:
                self._AddFailedCheck(
                    "Prim has a collision API but no physics material bound (no material resolves for the 'physics' purpose).",
                    at=prim,
                    requirement=self.COLLISION_API_MATERIAL_BINDING_REQUIREMENT,
                )
                continue

            if not material.GetPrim().HasAPI(UsdPhysics.MaterialAPI):
                self._AddFailedCheck(
                    "Prim has a collision API but its bound physics material does not have PhysicsMaterialAPI applied.",
                    at=prim,
                    requirement=self.COLLISION_API_MATERIAL_BINDING_REQUIREMENT,
                )
                continue

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
import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics, UsdShade

_NEWTON_MATERIAL_API = "NewtonMaterialAPI"
_PHYSICS_MATERIAL_API = "PhysicsMaterialAPI"


def _applied_api_schemas(prim: Usd.Prim) -> set[str]:
    schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
    op = prim.GetMetadata("apiSchemas")
    if op is None:
        return schemas
    for items in (
        op.explicitItems,
        op.prependedItems,
        op.appendedItems,
        op.addedItems,
        op.orderedItems,
    ):
        schemas.update(str(schema) for schema in items)
    return schemas


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
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                # prim must also have a material binding through material:binding:physics
                material_binding = prim.GetRelationship("material:binding:physics")
                if not material_binding:
                    self._AddFailedCheck(
                        "Prim has a collision API but no material binding through material:binding:physics.",
                        at=prim,
                        requirement=self.COLLISION_API_MATERIAL_BINDING_REQUIREMENT,
                    )
                    return

                # material binding must be a valid material
                material_path = material_binding.GetTargets()
                if not material_path:
                    self._AddFailedCheck(
                        "Prim has a collision API but no material binding through material:binding:physics.",
                        at=prim,
                        requirement=self.COLLISION_API_MATERIAL_BINDING_REQUIREMENT,
                    )
                    return

                material_prim = stage.GetPrimAtPath(material_path[0])
                if not material_prim or not material_prim.IsA(UsdShade.Material):
                    self._AddFailedCheck(
                        "Prim has a collision API but no valid material binding through material:binding:physics.",
                        at=prim,
                        requirement=self.COLLISION_API_MATERIAL_BINDING_REQUIREMENT,
                    )
                    return


@usd_validation_nvidia.register_rule("NewtonMaterialAttributes")
@usd_validation_nvidia.register_requirements(cap.PhysicsMaterialsRequirements.NEWTON_MAT_001, override=True)
class NewtonMaterialAttributesChecker(usd_validation_nvidia.BaseRuleChecker):
    """NEWTON.MAT.001 - NewtonMaterialAPI must be applied on a physics Material.

    Aligned with the UsdPhysicsMaterialAPI convention (PMT.001): this validates schema
    placement only. NewtonMaterialAPI extends PhysicsMaterialAPI, so it must be applied on a
    ``UsdShade.Material`` that also carries ``PhysicsMaterialAPI``. The ``newton:*`` material
    attribute values are documented but not policed, the same way ``physics:*`` values on
    ``PhysicsMaterialAPI`` are trusted rather than validated.
    """

    NEWTON_MATERIAL_REQUIREMENT = cap.PhysicsMaterialsRequirements.NEWTON_MAT_001

    def CheckPrim(self, prim: Usd.Prim) -> None:
        applied_schemas = _applied_api_schemas(prim)
        if _NEWTON_MATERIAL_API not in applied_schemas:
            return

        if not prim.IsA(UsdShade.Material):
            self._AddFailedCheck(
                f"NewtonMaterialAPI is applied on '{prim.GetPath()}', which is not a UsdShade.Material. "
                "Apply NewtonMaterialAPI only on physics Material prims.",
                at=prim,
                requirement=self.NEWTON_MATERIAL_REQUIREMENT,
            )
            return

        if _PHYSICS_MATERIAL_API not in applied_schemas and not prim.HasAPI(UsdPhysics.MaterialAPI):
            self._AddFailedCheck(
                f"NewtonMaterialAPI is applied on '{prim.GetPath()}' but the material does not also carry "
                "PhysicsMaterialAPI. NewtonMaterialAPI extends PhysicsMaterialAPI and must be applied alongside it.",
                at=prim,
                requirement=self.NEWTON_MATERIAL_REQUIREMENT,
            )

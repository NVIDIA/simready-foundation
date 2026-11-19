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
__all__ = ["NewtonMaterialAttributesChecker"]

import simready.foundation.tier_newton.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics, UsdShade

from simready.foundation.tier_newton.rules_and_reqs._common import _applied_api_schemas

_NEWTON_MATERIAL_API = "NewtonMaterialAPI"
_PHYSICS_MATERIAL_API = "PhysicsMaterialAPI"


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

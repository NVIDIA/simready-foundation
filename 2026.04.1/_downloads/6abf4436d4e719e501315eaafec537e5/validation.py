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

from enum import Enum

import omni.asset_validator
from pxr import Usd, UsdShade

from ... import Requirement


def traverse_without_references_payloads(prim):
    """Recursively traverse prim hierarchy excluding references and payloads.

    Args:
        prim: The USD prim to start traversal from.

    Yields:
        USD prims in the hierarchy that don't have references or payloads.
    """
    yield prim

    for child in prim.GetChildren():
        # Skip children that have references or payloads
        if child.HasAuthoredReferences() or child.HasAuthoredPayloads():
            continue

        # Recursively traverse children
        yield from traverse_without_references_payloads(child)


class RobotMaterialsCapReqs(Requirement, Enum):
    RM_001 = (
        "RM.001",
        "no-nested-materials",
        "Materials must not contain nested materials to avoid unexpected rendering behavior.",
    )
    RM_002 = (
        "RM.002",
        "materials-on-top-level-only",
        "Materials must only be defined in the top-level Looks prim following USD best practices.",
    )


@omni.asset_validator.register_rule("RobotMaterials")
@omni.asset_validator.register_requirements(RobotMaterialsCapReqs.RM_001, override=True)
class NoNestedMaterialsChecker(omni.asset_validator.BaseRuleChecker):
    """Validates that materials don't contain nested materials.

    This rule checks that UsdShade.Material prims don't have child prims that are also
    materials, which can cause unexpected rendering behavior.
    """

    ROBOT_MATERIALS_REQUIREMENT = RobotMaterialsCapReqs.RM_001

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a material prim contains nested materials.

        Args:
            prim: The USD prim to validate.
        """
        if prim.IsA(UsdShade.Material):
            for child_prim in Usd.PrimRange(prim):
                if child_prim.GetPath() == prim.GetPath():
                    continue
                if child_prim.IsA(UsdShade.Material):
                    self._AddFailedCheck(
                        message=f"Material {prim.GetPath()} has nested material {child_prim.GetPath()}",
                        at=child_prim,
                        requirement=self.ROBOT_MATERIALS_REQUIREMENT,
                    )


@omni.asset_validator.register_rule("RobotMaterials")
@omni.asset_validator.register_requirements(RobotMaterialsCapReqs.RM_002, override=True)
class MaterialsOnTopLevelOnlyChecker(omni.asset_validator.BaseRuleChecker):
    """Validates that materials are only defined in the top-level Looks prim.

    This rule checks that all UsdShade.Material prims are direct children of the
    top-level Looks prim, following USD best practices for material organization.
    """

    ROBOT_MATERIALS_REQUIREMENT = RobotMaterialsCapReqs.RM_002

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check if all materials are properly organized in the Looks prim.

        Args:
            stage: The USD stage to validate.
        """
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddInfo(
                message="No default prim found in the stage, skipping MaterialsOnTopLevelOnly check",
            )
            return

        looks_prim = stage.GetPrimAtPath(f"{default_prim.GetPath()}/Looks")
        if not looks_prim or not looks_prim.IsValid():
            self._AddInfo(
                message="No Looks prim found in the stage, skipping MaterialsOnTopLevelOnly check",
            )
            return

        material_set = set()
        for prim in looks_prim.GetChildren():
            if prim.IsA(UsdShade.Material):
                material_set.add(prim)

        for prim in traverse_without_references_payloads(default_prim):
            if prim.IsA(UsdShade.Material):
                if prim not in material_set:
                    self._AddFailedCheck(
                        message=f"Material {prim.GetPath()} is not in the top level Looks prim",
                        at=prim,
                        requirement=self.ROBOT_MATERIALS_REQUIREMENT,
                    )

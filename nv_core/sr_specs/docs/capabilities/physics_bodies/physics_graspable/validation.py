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
from pxr import Usd, UsdPhysics, UsdShade

from ... import Requirement


class PhysicsGraspableCapReqs(Requirement, Enum):
    GSP_001 = (
        "GSP.001",
        "graspable-vector-line",
        "Graspable prim must have a vector line for grasping.",
    )


@omni.asset_validator.register_rule("PhysicsGraspable")
@omni.asset_validator.register_requirements(PhysicsGraspableCapReqs.GSP_001, override=True)
class GraspableVectorLineChecker(omni.asset_validator.BaseRuleChecker):

    GRASP_VECTOR_LINE_REQUIREMENT = PhysicsGraspableCapReqs.GSP_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim, cannot check for graspable prims.", at=stage)
            return

        # Collect all grasp vector prims
        grasp_vector_prims = []
        for prim in Usd.PrimRange(default_prim):
            if prim.GetTypeName() == "BasisCurves" and prim.GetName().startswith("grasp_identifier"):
                grasp_vector_prims.append(prim)
        # At least one grasp vector prim
        if not grasp_vector_prims:
            self._AddFailedCheck(
                "Asset must have at least one grasp vector prim.",
                at=default_prim,
                requirement=self.GRASP_VECTOR_LINE_REQUIREMENT,
            )
            return

        # Each grasp vector prim must have at least 2 points
        for grasp_prim in grasp_vector_prims:
            points_attr = grasp_prim.GetAttribute("points")
            if not points_attr:
                self._AddFailedCheck(
                    f"Grasp vector prim '{grasp_prim.GetName()}' is missing 'points' attribute.",
                    at=grasp_prim,
                    requirement=self.GRASP_VECTOR_LINE_REQUIREMENT,
                )
                continue

            # if < 2 points, fail
            points = points_attr.Get()
            if not points or len(points) < 2:
                self._AddFailedCheck(
                    f"Grasp vector prim '{grasp_prim.GetName()}' must have at least 2 points, but has {len(points) if points else 0}.",
                    at=grasp_prim,
                    requirement=self.GRASP_VECTOR_LINE_REQUIREMENT,
                )

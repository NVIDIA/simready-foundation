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
from pxr import Usd, UsdGeom, UsdShade


@usd_validation_nvidia.register_rule("EXAMPLE")
@usd_validation_nvidia.register_requirements(cap.ExampleRequirements.EX_001, override=True)
class HasMeshChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim.", at=stage)
            return
        for prim in Usd.PrimRange(default_prim):
            if UsdGeom.Mesh(prim):
                return
        self._AddFailedCheck(requirement=cap.ExampleRequirements.EX_001, message="Stage has no mesh prims.", at=stage)

    @classmethod
    def GetDescription(cls) -> str:
        return "Should have at least one mesh."


@usd_validation_nvidia.register_rule("EXAMPLE")
@usd_validation_nvidia.register_requirements(cap.ExampleRequirements.EX_002, override=True)
class BasicMaterialChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim.", at=stage)
            return
        for prim in Usd.PrimRange(default_prim):
            if UsdGeom.Mesh(prim):
                material = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0].GetPrim()
                mesh_path = prim.GetPath().pathString
                material_path = material.GetPath().pathString
                if material.GetName() != "basic_material":
                    self._AddFailedCheck(
                        requirement=cap.ExampleRequirements.EX_002,
                        message=f"Mesh {mesh_path} has the wrong material bound: {material_path}",
                        at=material,
                    )

    @classmethod
    def GetDescription(cls) -> str:
        return "All meshes should have a material called basic_material bound to them."


@usd_validation_nvidia.register_rule("EXAMPLE")
@usd_validation_nvidia.register_requirements(cap.ExampleRequirements.EX_003, override=True)
class TestPrimChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim.", at=stage)
            return
        test_prim = default_prim.GetChild("TestBlob")
        if not test_prim:
            self._AddFailedCheck(
                requirement=cap.ExampleRequirements.EX_003,
                message="Test prim 'TestBlob' not found under default prim.",
                at=default_prim,
            )

    @classmethod
    def GetDescription(cls) -> str:
        return "The default prim should have a child called TestBlob."

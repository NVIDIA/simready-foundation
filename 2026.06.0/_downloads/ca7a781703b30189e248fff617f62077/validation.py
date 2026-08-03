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
import os
from pathlib import Path

import omni.capabilities as cap
import usd_validation_nvidia
from pxr import Kind, Usd, UsdGeom, UsdPhysics, UsdShade


@usd_validation_nvidia.register_rule("IsaacComposition")
@usd_validation_nvidia.register_requirements(cap.CompositionRequirements.ISA_001, override=True)
class IsaacCompositionCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    ISAAC_COMPOSITION_REQUIREMENT = cap.CompositionRequirements.ISA_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim. Unable to validate.",
                at=stage,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        # Check if default prim has kind = "component"
        model_api = Usd.ModelAPI(default_prim)
        if not model_api.GetKind() == Kind.Tokens.component:
            self._AddFailedCheck(
                "Default prim must have kind='component' for proper Isaac Sim composition.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

        # Check for payload structure
        self._check_payload_structure(stage, default_prim)

        # Check for proper reference structure
        self._check_reference_structure(default_prim)

        # Check for proper hierarchy organization
        self._check_hierarchy_organization(stage, default_prim)

    def _check_payload_structure(self, stage: Usd.Stage, default_prim: Usd.Prim):
        """Check if the asset has proper payload structure"""
        stage_path = stage.GetRootLayer().identifier
        if not stage_path:
            return

        stage_dir = Path(stage_path).parent
        payloads_dir = stage_dir / "payloads"

        # Check if payloads directory exists
        if not payloads_dir.exists():
            self._AddFailedCheck(
                "Missing 'payloads/' directory for Isaac Sim composition.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        # Check for expected payload files
        asset_name = Path(stage_path).stem
        expected_files = ["geometries.usd", "base.usda", "instances.usda", "materials.usda"]

        for expected_file in expected_files:
            if not (payloads_dir / expected_file).exists():
                self._AddFailedCheck(
                    f"Missing expected payload file: payloads/{expected_file}",
                    at=default_prim,
                    requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
                )

    def _check_reference_structure(self, default_prim: Usd.Prim):
        """Check if default prim has proper references and payloads"""
        prim_spec = default_prim.GetStage().GetRootLayer().GetPrimAtPath(default_prim.GetPath())
        if not prim_spec:
            self._AddFailedCheck(
                "Could not resolve prim spec for default prim.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        ref_list = prim_spec.referenceList.GetAddedOrExplicitItems()
        has_base_ref = any(str(ref.assetPath) == "./payloads/base.usda" for ref in ref_list)

        if not has_base_ref:
            self._AddFailedCheck(
                "Default prim missing reference to _base.usd payload file.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

    def _check_hierarchy_organization(self, stage: Usd.Stage, default_prim: Usd.Prim):
        """Check for proper Isaac Sim hierarchy organization"""
        # Look for common Isaac Sim structure indicators
        found_looks = False
        found_meshes = False
        found_visuals = False

        # Check entire stage for expected scopes
        for prim in Usd.PrimRange(stage.GetPseudoRoot()):
            if prim.GetName() == "Looks" and prim.GetTypeName() == "Scope":
                found_looks = True
            elif prim.GetName() == "Meshes" and prim.GetTypeName() == "Scope":
                found_meshes = True
                # Check if Meshes scope is invisible
                imageable = UsdGeom.Imageable(prim)
                if imageable.GetVisibilityAttr():
                    visibility = imageable.GetVisibilityAttr().Get()
                    if visibility != UsdGeom.Tokens.invisible:
                        self._AddFailedCheck(
                            "Meshes scope should be invisible for proper Isaac Sim composition.",
                            at=prim,
                            requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
                        )
            elif prim.GetName() == "Visuals" and prim.GetTypeName() == "Scope":
                found_visuals = True
                # Check if Visuals scope is invisible
                imageable = UsdGeom.Imageable(prim)
                if imageable.GetVisibilityAttr():
                    visibility = imageable.GetVisibilityAttr().Get()
                    if visibility != UsdGeom.Tokens.invisible:
                        self._AddFailedCheck(
                            "Visuals scope should be invisible for proper Isaac Sim composition.",
                            at=prim,
                            requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
                        )

        # Warning if expected scopes are not found (may be in payloads)
        if not (found_looks or found_meshes or found_visuals):
            # This is a soft warning since these might be in payload files
            pass  # Could add informational message if needed

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
from typing import Optional

import omni.asset_validator
import omni.capabilities as cap
from pxr import Sdf, Usd

# Asset classes that have thermal cooling requirements
_COOLING_ASSET_CLASSES = {"cdu", "crah"}

# Connection point type prefixes required per cooling asset class
_REQUIRED_CP_TYPES = {
    "cdu": ("fws_supply", "fws_return", "tcs_supply", "tcs_return"),
    "crah": ("liq_supply", "liq_return"),
}


def _find_properties_sublayer(stage: Usd.Stage) -> Optional[Sdf.Layer]:
    root_layer = stage.GetRootLayer()
    for sublayer_path in root_layer.subLayerPaths:
        filename = sublayer_path.replace("\\", "/").split("/")[-1].lower()
        if "properties" in filename and filename.endswith(".usda"):
            for layer in stage.GetLayerStack():
                if "properties" in layer.identifier.replace("\\", "/").split("/")[-1].lower():
                    return layer
            resolved = Sdf.ComputeAssetPathRelativeToLayer(root_layer, sublayer_path)
            layer = Sdf.Layer.FindOrOpen(resolved)
            if layer:
                return layer
    return None


def _get_asset_class(stage: Usd.Stage) -> Optional[str]:
    layer = _find_properties_sublayer(stage)
    if not layer or not layer.defaultPrim:
        return None
    prim_spec = layer.GetPrimAtPath(f"/{layer.defaultPrim}")
    if not prim_spec:
        return None
    attr = prim_spec.attributes.get("aif:core:assetClass")
    if not attr or not attr.default:
        return None
    return str(attr.default).lower().strip()


def _get_connection_point_names(stage: Usd.Stage):
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return []
    for child in default_prim.GetChildren():
        if child.GetName() == "ConnectionPoints" and child.GetTypeName() == "Scope":
            return [p.GetName() for p in Usd.PrimRange(child) if p != child]
    return []


@omni.asset_validator.register_rule("AIF-ThermalCooling")
@omni.asset_validator.register_requirements(cap.ThermalCoolingRequirements.TC_001, override=True)
class AIFNominalCoolingCapacityChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that cooling equipment has aif:spec:nominalCoolingCapacity."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class = _get_asset_class(stage)
        if asset_class not in _COOLING_ASSET_CLASSES:
            return  # Not a cooling equipment asset: skip

        layer = _find_properties_sublayer(stage)
        if not layer or not layer.defaultPrim:
            return  # AM.001 already reported this
        prim_spec = layer.GetPrimAtPath(f"/{layer.defaultPrim}")
        if not prim_spec:
            return

        if "aif:spec:nominalCoolingCapacity" not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ThermalCoolingRequirements.TC_001,
                message=f"Cooling equipment (assetClass='{asset_class}') is missing required attribute: aif:spec:nominalCoolingCapacity.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-ThermalCooling")
@omni.asset_validator.register_requirements(cap.ThermalCoolingRequirements.TC_002, override=True)
class AIFThermalCoolingConnectionPointsChecker(omni.asset_validator.BaseRuleChecker):
    """Cross-domain check: cooling equipment must have matching piping connection points."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class = _get_asset_class(stage)
        if asset_class not in _COOLING_ASSET_CLASSES:
            return

        required_types = _REQUIRED_CP_TYPES.get(asset_class, ())
        if not required_types:
            return

        cp_names = _get_connection_point_names(stage)
        missing_types = []
        for cp_type in required_types:
            if not any(cp_type in name for name in cp_names):
                missing_types.append(cp_type)

        if missing_types:
            self._AddFailedCheck(
                requirement=cap.ThermalCoolingRequirements.TC_002,
                message=(
                    f"Cooling equipment (assetClass='{asset_class}') is missing connection point prims "
                    f"for: {', '.join(missing_types)}. "
                    f"Expected prim names matching: "
                    + ", ".join(f"*_{t}_*" for t in missing_types)
                ),
                at=stage,
            )

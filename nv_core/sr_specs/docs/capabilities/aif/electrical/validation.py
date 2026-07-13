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
#
# NOTE: EL.001-003 attribute names are not harmonized across equipment classes.
# This mapping table must be updated if upstream CSV templates harmonize naming.
from typing import Optional

import omni.asset_validator
import omni.capabilities as cap
from pxr import Sdf, Usd

# Asset classes that have AC electrical requirements. Compute Rack equipment
# (e.g. GB300) is excluded because it uses DC power profiles.
_AC_ASSET_CLASSES = {"cdu", "crah", "ups"}

# Per-class attribute name mapping for EL.001-003.
# Names differ across equipment classes due to unharmonized upstream CSV templates.
_NOMINAL_VOLTAGE_ATTR = {
    "cdu": "aif:spec:nominalVoltage",
    "crah": "aif:spec:electricalNominalVoltage",
    "ups": "aif:spec:electricalInputVoltage",
}
_POWER_RATING_ATTR = {
    "cdu": "aif:spec:powerRating",
    "crah": "aif:spec:electricalPowerRating",
    "ups": "aif:spec:upsRating",
}
_FREQUENCY_ATTR = {
    "cdu": "aif:spec:frequency",
    "crah": "aif:spec:electricalFrequency",
    "ups": "aif:spec:electricalInputFrequency",
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


def _get_asset_class_and_prim(stage: Usd.Stage):
    layer = _find_properties_sublayer(stage)
    if not layer or not layer.defaultPrim:
        return None, None
    prim_spec = layer.GetPrimAtPath(f"/{layer.defaultPrim}")
    if not prim_spec:
        return None, None
    attr = prim_spec.attributes.get("aif:core:assetClass")
    if not attr or not attr.default:
        return None, prim_spec
    return str(attr.default).lower().strip(), prim_spec


def _get_connection_point_names(stage: Usd.Stage):
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return []
    for child in default_prim.GetChildren():
        if child.GetName() == "ConnectionPoints" and child.GetTypeName() == "Scope":
            return [p.GetName() for p in Usd.PrimRange(child) if p != child]
    return []


@omni.asset_validator.register_rule("AIF-Electrical")
@omni.asset_validator.register_requirements(cap.ElectricalRequirements.EL_001, override=True)
class AIFNominalVoltageChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that AC-powered equipment has the appropriate nominal voltage attribute."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, prim_spec = _get_asset_class_and_prim(stage)
        if asset_class not in _AC_ASSET_CLASSES or prim_spec is None:
            return
        attr_name = _NOMINAL_VOLTAGE_ATTR[asset_class]
        if attr_name not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_001,
                message=f"AC-powered equipment (assetClass='{asset_class}') is missing nominal voltage attribute: {attr_name}.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Electrical")
@omni.asset_validator.register_requirements(cap.ElectricalRequirements.EL_002, override=True)
class AIFPowerRatingChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that AC-powered equipment has the appropriate power rating attribute."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, prim_spec = _get_asset_class_and_prim(stage)
        if asset_class not in _AC_ASSET_CLASSES or prim_spec is None:
            return
        attr_name = _POWER_RATING_ATTR[asset_class]
        if attr_name not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_002,
                message=f"AC-powered equipment (assetClass='{asset_class}') is missing power rating attribute: {attr_name}.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Electrical")
@omni.asset_validator.register_requirements(cap.ElectricalRequirements.EL_003, override=True)
class AIFElectricalFrequencyChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that AC-powered equipment has the appropriate electrical frequency attribute."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, prim_spec = _get_asset_class_and_prim(stage)
        if asset_class not in _AC_ASSET_CLASSES or prim_spec is None:
            return
        attr_name = _FREQUENCY_ATTR[asset_class]
        if attr_name not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_003,
                message=f"AC-powered equipment (assetClass='{asset_class}') is missing frequency attribute: {attr_name}.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Electrical")
@omni.asset_validator.register_requirements(cap.ElectricalRequirements.EL_004, override=True)
class AIFElectricalConnectionPointsChecker(omni.asset_validator.BaseRuleChecker):
    """Cross-domain check: AC-powered equipment must have electrical_nominal_voltage connection points."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, _ = _get_asset_class_and_prim(stage)
        if asset_class not in _AC_ASSET_CLASSES:
            return

        cp_names = _get_connection_point_names(stage)
        if not any("electrical_nominal_voltage" in name for name in cp_names):
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_004,
                message=(
                    f"AC-powered equipment (assetClass='{asset_class}') is missing an electrical connection point prim. "
                    "Expected at least one prim matching: *_electrical_nominal_voltage_*"
                ),
                at=stage,
            )

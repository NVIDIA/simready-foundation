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

# Equipment-specific attribute sets derived from CSV templates.
# Source: aif_simready_migration_plan/aif_metadata_csvs/
_EQUIPMENT_ATTRS = {
    "cdu": frozenset({
        "aif:spec:coolingType",
        "aif:spec:mountStyle",
        "aif:spec:coolingCapacityCurve",
        "aif:spec:referenceFacilityCoolantTemperature",
        "aif:spec:referenceTechnologyCoolantFlowRate",
        "aif:spec:referenceSecondaryCoolantTemperature",
        "aif:spec:totalHeatDissipated",
        "aif:spec:filterSizeCoolingCapacity",
        "aif:spec:pumpRedundancyStrategyCoolingCapacity",
        "aif:spec:workingFluidCoolingCapacity",
        "aif:spec:nominalCoolingCapacity",
        "aif:spec:maximumCoolingCapacity",
        "aif:spec:nominalFlow",
        "aif:spec:maximumFlow",
        "aif:spec:pumpFlowCurve",
        "aif:spec:maxSpeed",
        "aif:spec:ratedSpeed",
        "aif:spec:numberOfPumps",
        "aif:spec:maximumPowerConsumption2XPumps",
        "aif:spec:maximumPowerConsumption3XPumps",
        "aif:spec:filterSizePumps",
        "aif:spec:pumpRedundancyStrategyPumps",
        "aif:spec:workingFluidPumps",
        "aif:spec:wettedMaterialTcs",
        "aif:spec:wettedMaterialFws",
        "aif:spec:communication1",
        "aif:spec:communication2",
        "aif:spec:nominalVoltage",
        "aif:spec:current",
        "aif:spec:frequency",
        "aif:spec:powerRating",
        "aif:spec:powerFactor",
        "aif:spec:efficiency",
        "aif:spec:wiringMethod",
        "aif:spec:fwsSupplyPipingConnection",
        "aif:spec:fwsReturnPipingConnection",
        "aif:spec:tcsSupplyPipingConnection",
        "aif:spec:tcsReturnPipingConnection",
        "aif:spec:primaryFiltration",
        "aif:spec:primaryCircuitVolume",
        "aif:spec:secondaryFiltration",
        "aif:spec:secondaryCircuitVolume",
        "aif:spec:ratedVoltageIncomingPower",
        "aif:spec:ratedCableSize",
        "aif:spec:ratedMaxPower",
        "aif:spec:incomingPowerFeeds",
        "aif:spec:redundancyScheme",
        "aif:spec:powerTransferDevice",
        "aif:spec:powerTransferDesign",
        "aif:spec:breaker",
        "aif:spec:fuse",
        "aif:spec:disconnect",
        "aif:spec:motorSize",
        "aif:spec:motorPowerInfo",
        "aif:spec:ratedVoltageRotatingEquipment",
        "aif:spec:ratedHp",
        "aif:spec:powerFactorRotatingEquipment",
        "aif:spec:efficiencyRotatingEquipment",
        "aif:spec:auxiliaryPowerSourceAndConnections",
        "aif:spec:controlWiresForExternalComm",
        "aif:spec:controlHmi",
    }),
    "crah": frozenset({
        "aif:spec:faceArea",
        "aif:spec:nominalCoolingCapacity",
        "aif:spec:totalCapacity",
        "aif:spec:sensibleCapacity",
        "aif:spec:flowRate",
        "aif:spec:returnAirVolume",
        "aif:spec:fanMotorPowerMax",
        "aif:spec:unitPressureDrop",
        "aif:spec:externalStaticUnitPressure",
        "aif:spec:electricalPanelAccess",
        "aif:spec:nominalAirVolume",
        "aif:spec:maximumHp",
        "aif:spec:numberOfFans",
        "aif:spec:numberOfRows",
        "aif:spec:faceVelocity",
        "aif:spec:primaryPipeDiameter",
        "aif:spec:secondaryPipeDiameter",
        "aif:spec:pipingConnection",
        "aif:spec:primaryControl",
        "aif:spec:powerSupply",
        "aif:spec:electricalNominalVoltage",
        "aif:spec:electricalCurrent",
        "aif:spec:electricalFrequency",
        "aif:spec:electricalPowerRating",
        "aif:spec:electricalPhase",
        "aif:spec:electricalPanelOptions",
        "aif:spec:humidification",
        "aif:spec:airFilter",
        "aif:spec:coil",
        "aif:spec:highVoltageOptions",
        "aif:spec:monitoring",
    }),
    "ups": frozenset({
        "aif:spec:upsRating",
        "aif:spec:outputActivePower",
        "aif:spec:electricalInputVoltage",
        "aif:spec:electricalCurrent",
        "aif:spec:inputCurrentDistortion",
        "aif:spec:electricalInputFrequency",
        "aif:spec:electricalInputPhase",
        "aif:spec:inputPowerFactor",
        "aif:spec:electricalPowerWalkIn",
        "aif:spec:batteryType",
        "aif:spec:batteryFloatVoltage",
        "aif:spec:dcRippleVoltage",
        "aif:spec:nominalBatteryBus",
        "aif:spec:temperatureCompensatedBatteryCharging",
        "aif:spec:loadPowerFactor",
        "aif:spec:outputVoltage",
        "aif:spec:electricalOutputFrequency",
        "aif:spec:electricalOutputPhase",
        "aif:spec:outputThdNominalVoltage",
        "aif:spec:outputThdNominalVoltageWithNonLinearLoad",
        "aif:spec:transientRecoveryLoad",
        "aif:spec:voltageDisplacement",
        "aif:spec:overloadAtNominalVoltage",
        "aif:spec:upsEnclosureClass",
        "aif:spec:color",
        "aif:spec:operatingTemperature",
        "aif:spec:relativeHumidity",
        "aif:spec:operatingAltitude",
        "aif:spec:communicationOptions",
        "aif:spec:cardCompatibility",
        "aif:spec:protocolsAvailable",
    }),
    "gb300-rack": frozenset({
        "aif:spec:namePlatePower",
        "aif:spec:requiredAirFlowRate",
        "aif:spec:requiredLiquidFlowRate",
        "aif:spec:heatCaptureRatio",
        "aif:spec:liquidSidePqCurve",
        "aif:spec:significantInternalStructure",
        "aif:spec:doorsPerforations",
        "aif:spec:numGPUs",
        "aif:spec:maxPowerDcEdpp2",
        "aif:spec:maxPowerDcEdpp1",
        "aif:spec:maxPowerDcTdp",
        "aif:spec:maxPowerAcEdpp1",
        "aif:spec:idlePowerDefault30Pct",
        "aif:spec:idlePowerSmoothing90Pct",
        "aif:spec:rampUpRateDefault",
        "aif:spec:rampDownRateDefault",
        "aif:spec:liquidCooling",
        "aif:spec:airCooling",
    }),
}

_GB300_ALIASES = {"compute rack", "gb300_rack", "gb300 rack", "gb300"}


def _normalize_asset_class(raw: str) -> Optional[str]:
    slug = raw.lower().strip()
    if slug in _GB300_ALIASES:
        return "gb300-rack"
    return slug if slug in _EQUIPMENT_ATTRS else None


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
            layer = Sdf.Layer.FindRelativeToLayer(root_layer, sublayer_path)
            if layer:
                return layer
    return None


def _get_prim_spec(stage: Usd.Stage) -> Optional[Sdf.PrimSpec]:
    layer = _find_properties_sublayer(stage)
    if not layer or not layer.defaultPrim:
        return None
    return layer.GetPrimAtPath(f"/{layer.defaultPrim}")


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_001, override=True)
class AIFPropertiesSublayerChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that the stage has a *properties*.usda sublayer with a default prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        layer = _find_properties_sublayer(stage)
        if not layer:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_001,
                message=(
                    "Missing required sublayer: *properties*.usda. "
                    "The stage must include a sublayer with 'properties' in its name "
                    "(e.g., AssetName_Properties.usda)."
                ),
                at=stage,
            )
            return
        if not layer.defaultPrim:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_001,
                message="properties.usda sublayer has no defaultPrim specified.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_002, override=True)
class AIFAssetClassChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that aif:core:assetClass is present on the default prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return  # AM.001 already reported this
        if "aif:core:assetClass" not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_002,
                message="Missing required attribute: aif:core:assetClass.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_003, override=True)
class AIFAssetIdentificationChecker(omni.asset_validator.BaseRuleChecker):
    """Checks aif:core:manufacturer, aif:core:modelNumber, aif:core:assetVersion."""

    _REQUIRED = ("aif:core:manufacturer", "aif:core:modelNumber", "aif:core:assetVersion")

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        present = set(prim_spec.attributes.keys())
        missing = sorted(a for a in self._REQUIRED if a not in present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_003,
                message=f"Missing asset identification attributes: {', '.join(missing)}",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_004, override=True)
class AIFPhysicalDimensionsChecker(omni.asset_validator.BaseRuleChecker):
    """Checks physical dimension attributes on the default prim."""

    _REQUIRED = (
        "aif:core:height",
        "aif:core:width",
        "aif:core:depth",
        "aif:core:weight",
        "aif:core:overallGeometryDimensions",
        "aif:core:installationClearance",
        "aif:core:accessibilityRequirement",
    )

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        present = set(prim_spec.attributes.keys())
        missing = sorted(a for a in self._REQUIRED if a not in present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_004,
                message=f"Missing physical dimension attributes: {', '.join(missing)}",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_005, override=True)
class AIFSimReadyVersionChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that aif:core:simreadyVersion is present on the default prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        if "aif:core:simreadyVersion" not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_005,
                message="Missing required attribute: aif:core:simreadyVersion.",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_006, override=True)
class AIFAssetDescriptionChecker(omni.asset_validator.BaseRuleChecker):
    """Checks aif:core:assetDescription and aif:core:connectsToModelDocumentation."""

    _REQUIRED = ("aif:core:assetDescription", "aif:core:connectsToModelDocumentation")

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        present = set(prim_spec.attributes.keys())
        missing = sorted(a for a in self._REQUIRED if a not in present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_006,
                message=f"Missing asset description attributes: {', '.join(missing)}",
                at=stage,
            )


@omni.asset_validator.register_rule("AIF-Metadata")
@omni.asset_validator.register_requirements(cap.MetadataRequirements.AM_007, override=True)
class AIFEquipmentTemplateChecker(omni.asset_validator.BaseRuleChecker):
    """Reads aif:core:assetClass and checks required aif:spec:* attributes for that equipment class."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return

        asset_class_attr = prim_spec.attributes.get("aif:core:assetClass")
        if not asset_class_attr or not asset_class_attr.default:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_007,
                message="aif:core:assetClass is missing or empty; cannot determine equipment template.",
                at=stage,
            )
            return

        asset_class = _normalize_asset_class(str(asset_class_attr.default))
        if asset_class is None:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_007,
                message=(
                    f"No equipment template found for assetClass '{asset_class_attr.default}'. "
                    "Supported classes: cdu, crah, ups, compute rack / gb300."
                ),
                at=stage,
            )
            return

        required = _EQUIPMENT_ATTRS[asset_class]
        present = set(prim_spec.attributes.keys())
        missing = sorted(required - present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_007,
                message=(
                    f"Asset class '{asset_class_attr.default}' is missing {len(missing)} aif:spec:* attribute(s): "
                    f"{', '.join(missing[:5])}"
                    + (f" ... and {len(missing) - 5} more" if len(missing) > 5 else "")
                ),
                at=stage,
            )

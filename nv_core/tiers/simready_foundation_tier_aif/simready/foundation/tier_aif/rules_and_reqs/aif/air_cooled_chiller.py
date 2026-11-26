# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Condenser-air maps and equipment attributes for the air-cooled chiller."""
import usd_validation_nvidia

import simready.foundation.tier_aif.requirements as cap
from . import chiller_schema
from .chiller_schema import EVAPORATOR_AXES, PREFIX, _numeric, value

COOLING_AXES = EVAPORATOR_AXES + tuple(PREFIX + "performanceMapCoolingGrid" + suffix for suffix in (
    "CondenserAirEnteringDrybulbTemperature_K", "CondenserAirEnteringRelativeHumidity",
    "AmbientPressure_Pa", "CompressorSequenceNumber",
))
COOLING_LOOKUPS = tuple(PREFIX + "performanceMapCoolingLookup" + suffix for suffix in (
    "InputPower_W", "NetEvaporatorCapacity_W", "NetCondenserCapacity_W",
    "CondenserAirVolumetricFlowRate_m3PerS", "OilCoolerHeat_W", "AuxiliaryHeat_W", "OperationState",
))
CHECK_TEMPERATURE_RISE = False
RENAMED_DIMENSIONLESS_FIELDS = ("performanceMapCoolingGridCondenserAirEnteringRelativeHumidity",)
validate_condenser_interface = None  # The condenser exchanges heat with ambient air.


def validate_extra_attributes(prim, errors):
    fan = value(prim, "fanType")
    if isinstance(fan, str) and not fan.strip():
        errors.append("fanType: fan type must be a nonempty designation")
    charge = value(prim, "refrigerantChargePerCircuit_kg")
    if charge is not None and hasattr(charge, "__len__"):
        if not len(charge) or any(_numeric(v) and v <= 0 for v in charge):
            errors.append("refrigerantChargePerCircuit_kg: supply a positive charge for each circuit")
    efficiency = value(prim, "efficiencyRotatingEquipment")
    if _numeric(efficiency) and not 0 < efficiency <= 1:
        errors.append("efficiencyRotatingEquipment: rated motor efficiency must be greater than zero and at most one")
    speed = value(prim, "maximumCondenserFanRotationalSpeed_Hz")
    if _numeric(speed) and speed <= 0:
        errors.append("maximumCondenserFanRotationalSpeed_Hz: rated value must be positive")
    fans = value(prim, "numberOfFans")
    if _numeric(fans) and fans < 0:
        errors.append("numberOfFans: installed EC fan count must be nonnegative")
    humidity = value(prim, "performanceMapCoolingGridCondenserAirEnteringRelativeHumidity")
    if humidity is not None and hasattr(humidity, "__len__") and any(_numeric(v) and not 0 <= v <= 1 for v in humidity):
        errors.append("Condenser air relative humidity must be between 0 and 1")


def validate_condenser_map(prim, grids, lookups, errors):
    if any(not 0 <= humidity <= 1 for humidity in grids[3]):
        errors.append("Condenser air relative-humidity axis must lie within [0, 1]")
    for i, state in enumerate(lookups["OperationState"]):
        if state == "NORMAL" and lookups["NetCondenserCapacity_W"][i] > 0 and lookups["CondenserAirVolumetricFlowRate_m3PerS"][i] <= 0:
            errors.append(f"Cooling table index {i}: positive condenser heat rejection requires positive condenser air flow")


@usd_validation_nvidia.register_rule("AIF-AirCooledChiller")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_010, override=True)
class AIFAirChillerMapChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage):
        if not chiller_schema.has_class(stage, "AirCooledChiller"):
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_010,
                message="The air-cooled chiller capability requires the 'AirCooledChiller' string class "
                        "on both the Properties layer and the composed default prim.",
                at=stage,
            )
            return
        for error in chiller_schema.validate_maps(chiller_schema.properties_prim(stage)):
            self._AddFailedCheck(requirement=cap.MetadataRequirements.AM_010, message=error, at=stage)


@usd_validation_nvidia.register_rule("AIF-AirCooledChiller")
@usd_validation_nvidia.register_requirements(cap.ThermalCoolingRequirements.TC_003, override=True)
class AIFAirChillerThermalChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage):
        if chiller_schema.has_class(stage, "AirCooledChiller"):
            for error in chiller_schema.validate_thermal(stage):
                self._AddFailedCheck(requirement=cap.ThermalCoolingRequirements.TC_003, message=error, at=stage)


@usd_validation_nvidia.register_rule("AIF-AirCooledChiller")
@usd_validation_nvidia.register_requirements(cap.ElectricalRequirements.EL_005, override=True)
class AIFAirChillerElectricalChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage):
        if chiller_schema.has_class(stage, "AirCooledChiller"):
            for error in chiller_schema.validate_electrical(stage):
                self._AddFailedCheck(requirement=cap.ElectricalRequirements.EL_005, message=error, at=stage)

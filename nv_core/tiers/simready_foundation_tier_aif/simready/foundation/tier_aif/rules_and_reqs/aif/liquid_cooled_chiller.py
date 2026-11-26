# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Water-cooled condenser maps and the separate condenser-water circuit."""
import usd_validation_nvidia

import simready.foundation.tier_aif.requirements as cap
from . import chiller_schema
from .chiller_schema import (
    EVAPORATOR_AXES, PREFIX, _check_limits, _check_pressure_envelope,
    _map, _numeric, _validate_circuit, value,
)

COOLING_AXES = EVAPORATOR_AXES + tuple(PREFIX + "performanceMapCoolingGrid" + suffix for suffix in (
    "CondenserLiquidVolumetricFlowRate_m3PerS", "CondenserLiquidEnteringTemperature_K",
    "CompressorSequenceNumber",
))
COOLING_LOOKUPS = tuple(PREFIX + "performanceMapCoolingLookup" + suffix for suffix in (
    "InputPower_W", "NetEvaporatorCapacity_W", "NetCondenserCapacity_W",
    "OilCoolerHeat_W", "AuxiliaryHeat_W", "OperationState",
))
CONDENSER_PRESSURE_AXES = tuple(PREFIX + "performanceMapCondenserLiquidPressureDifferentialGrid" + suffix for suffix in (
    "CondenserLiquidVolumetricFlowRate_m3PerS", "CondenserLiquidEnteringTemperature_K",
))
CONDENSER_PRESSURE_LOOKUPS = (PREFIX + "performanceMapCondenserLiquidPressureDifferentialLookupCondenserLiquidDifferentialPressure_Pa",)
CHECK_TEMPERATURE_RISE = True
RENAMED_DIMENSIONLESS_FIELDS = ()
validate_extra_attributes = None  # The class sheet and shared fluid-fraction checks cover both water circuits.


def validate_condenser_map(prim, grids, lookups, errors):
    _check_limits(prim, "minimumOperatingCondenserLiquidVolumetricFlowRate_m3PerS",
                  "maximumOperatingCondenserLiquidVolumetricFlowRate_m3PerS", grids[2], errors)
    pressure = _map(prim, CONDENSER_PRESSURE_AXES, CONDENSER_PRESSURE_LOOKUPS, errors)
    if pressure is not None:
        pressure_axes, tables = pressure
        if any(v <= 0 for v in tables[0]):
            errors.append("Condenser liquid differential-pressure lookup values must be positive")
        _check_pressure_envelope("Condenser", pressure_axes, grids[2:4], errors)


def validate_condenser_interface(stage, prim, errors):
    capacity = value(prim, "referenceNetCondenserCapacity_W")
    if not _numeric(capacity) or capacity <= 0:
        errors.append("referenceNetCondenserCapacity_W must be positive")
    errors.extend(_validate_circuit(
        stage, prim, "condenser", "equipment_cooling", COOLING_AXES[2:4], "supply", check_temperature_rise=True,
    ))

@usd_validation_nvidia.register_rule("AIF-LiquidCooledChiller")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_011, override=True)
class AIFLiquidChillerMapChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage):
        if not chiller_schema.has_class(stage, "LiquidCooledChiller"):
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_011,
                message="The liquid-cooled chiller profile requires LiquidCooledChiller on the Properties "
                        "layer and composed default prim.",
                at=stage,
            )
            return
        for error in chiller_schema.validate_maps(chiller_schema.properties_prim(stage)):
            self._AddFailedCheck(requirement=cap.MetadataRequirements.AM_011, message=error, at=stage)


@usd_validation_nvidia.register_rule("AIF-LiquidCooledChiller")
@usd_validation_nvidia.register_requirements(cap.ThermalCoolingRequirements.TC_004, override=True)
class AIFLiquidChillerThermalChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage):
        if chiller_schema.has_class(stage, "LiquidCooledChiller"):
            for error in chiller_schema.validate_thermal(stage):
                self._AddFailedCheck(requirement=cap.ThermalCoolingRequirements.TC_004, message=error, at=stage)


@usd_validation_nvidia.register_rule("AIF-LiquidCooledChiller")
@usd_validation_nvidia.register_requirements(cap.ElectricalRequirements.EL_006, override=True)
class AIFLiquidChillerElectricalChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage):
        if chiller_schema.has_class(stage, "LiquidCooledChiller"):
            for error in chiller_schema.validate_electrical(stage):
                self._AddFailedCheck(requirement=cap.ElectricalRequirements.EL_006, message=error, at=stage)

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Liquid-chiller metadata, map boundaries, circuit identity and legacy isolation."""
import importlib.util
import math
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom
import pytest

from _harness import assert_no_failures, assert_rule_fires
from simready.foundation.tier_aif.rules_and_reqs.aif import liquid_cooled_chiller as liquid_variant
from simready.foundation.tier_aif.rules_and_reqs.aif import chiller_schema as schema
from simready.foundation.tier_aif.rules_and_reqs.aif import equipment_classes

TIER = Path(__file__).resolve().parents[1]
REPO = TIER.parents[2]
LIQUID_SCHEMA = schema.schema_for("LiquidCooledChiller")


@pytest.fixture(scope="module", autouse=True)
def registered_rules():
    # Earlier full-profile modules destroy their loader state at teardown.
    # Restore the installed tier registrations before these rule-level checks.
    import simready.validate as sv

    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])


def test_liquid_packaged_schema_matches_csv_and_preserves_legacy_registry():
    spec = importlib.util.spec_from_file_location("chiller_generator", TIER / "tools/generate_chiller_schema.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    expected = generator.schema_document(REPO / "standards/equipment-classes/aif-v0.3/liquid-cooled-chiller.csv")
    assert LIQUID_SCHEMA == {**expected, "introducedIn": "0.3.0"}
    assert len(LIQUID_SCHEMA["attributes"]) == 59
    assert len(LIQUID_SCHEMA["requiredAttributes"]) == 18
    assert schema.schema_for(" liquidcooledchiller ") is LIQUID_SCHEMA
    assert equipment_classes.normalize("LiquidCooledChiller") is None
    assert not any("CondenserAir" in name for name in LIQUID_SCHEMA["attributes"])


@pytest.fixture
def liquid(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "LiquidChiller.usda"))
    properties = Sdf.Layer.CreateNew(str(tmp_path / "LiquidChiller_Properties.usda"))
    stage.GetRootLayer().subLayerPaths = [properties.identifier]
    stage.SetEditTarget(properties)
    prim = UsdGeom.Xform.Define(stage, "/world").GetPrim()
    properties.defaultPrim = "world"
    stage.SetDefaultPrim(prim)
    prim.CreateAttribute("aif:core:assetClass", Sdf.ValueTypeNames.String).Set("LiquidCooledChiller")
    definitions = LIQUID_SCHEMA["attributeDefinitions"]
    values = {}
    for name, row in definitions.items():
        kind = row["Attribute Type"]
        if row["Options"] != "Not required":
            value = row["Options"].split(" | ")[0]
        elif kind in {"string", "token"}:
            value = "Synthetic"
        elif kind == "bool":
            value = False
        else:
            value = 1
        values[name] = [value] if kind.endswith("_array") else value
    values.update({schema.PREFIX + name: value for name, value in {
        "nominalVoltage_V": 400, "nominalFrequency_Hz": 50, "refrigerant": "R-134a",
        "referenceInputPower_W": 25000, "referenceNetEvaporatorCapacity_W": 100000,
        "referenceNetCondenserCapacity_W": 125000, "referenceOilCoolerHeat_W": 0,
        "referenceAuxiliaryHeat_W": 0, "referenceCOP": 4, "referenceCoolingMapPointIndex": 0,
        "minimumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS": .004,
        "maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS": .006,
        "minimumOperatingCondenserLiquidVolumetricFlowRate_m3PerS": .005,
        "maximumOperatingCondenserLiquidVolumetricFlowRate_m3PerS": .008,
        "evaporatorLeavingTemperatureSetpointMinimum_degC": 7,
        "evaporatorLeavingTemperatureSetpointMaximum_degC": 12,
    }.items()})
    axes = [[.004, .006], [280.15, 285.15], [.005, .008], [298.15, 303.15], [1, 2]]
    values.update(dict(zip(liquid_variant.COOLING_AXES, axes, strict=True)))
    size = math.prod(map(len, axes))
    tables = [[25000] * size, [100000] * size, [125000] * size,
              [0] * size, [0] * size, ["NORMAL"] * size]
    values.update(dict(zip(liquid_variant.COOLING_LOOKUPS, tables, strict=True)))
    values[schema.STANDBY_AXES[0]] = [293.15, 303.15]
    values[schema.STANDBY_LOOKUPS[0]] = [400, 500]
    values.update(dict(zip(schema.PRESSURE_AXES, axes[:2], strict=True)))
    values[schema.PRESSURE_LOOKUPS[0]] = [20000, 20000, 45000, 45000]
    values.update(dict(zip(liquid_variant.CONDENSER_PRESSURE_AXES, axes[2:4], strict=True)))
    values[liquid_variant.CONDENSER_PRESSURE_LOOKUPS[0]] = [18000, 18000, 46080, 46080]
    for name, value in values.items():
        row = definitions[name]
        attr = prim.CreateAttribute(name, schema.TYPE_NAMES[row["Attribute Type"]])
        attr.Set(value)
        attr.SetCustomDataByKey("units", row["SI Unit Values"])
    UsdGeom.Scope.Define(stage, "/world/ConnectionPoints")
    for name, system, direction, domain, flow, temperature in (
        ("evaporator_supply", "FWS", "supply", "thermal", 4, 7),
        ("evaporator_return", "FWS", "return", "thermal", 4, 13),
        ("condenser_supply", "equipment_cooling", "supply", "thermal", 5, 25),
        ("condenser_return", "equipment_cooling", "return", "thermal", 5, 31),
        ("power", "power", "input", "electrical", 0, 0),
    ):
        port = UsdGeom.Xform.Define(stage, "/world/ConnectionPoints/" + name).GetPrim()
        for suffix, value in (("domain", domain), ("direction", direction), ("system", system)):
            port.CreateAttribute("simready:connectionPoint:" + suffix, Sdf.ValueTypeNames.Token).Set(value)
        fields = ({"designFlowRate": flow, "maxFlowRate": 8, "designTemperature": temperature}
                  if domain == "thermal" else {"nominalVoltage": 400, "frequency": 50, "ratedPower": 45000})
        for suffix, value in fields.items():
            port.CreateAttribute("simready:connectionPoint:" + domain + ":" + suffix, Sdf.ValueTypeNames.Float).Set(value)
    return stage


def _save(stage):
    for layer in stage.GetLayerStack():
        if not layer.anonymous:
            layer.Save()
    return Path(stage.GetRootLayer().realPath)


def test_liquid_rules_pass_and_old_equipment_registry_rejects(liquid):
    path = _save(liquid)
    assert_no_failures(path, ["AM.008", "AM.011", "TC.004", "EL.006"])
    assert_rule_fires(path, "AM.007")


@pytest.mark.parametrize("mutation", ["missing", "type", "units", "fluid", "fraction"])
def test_liquid_metadata_rejects_invalid_condenser_values(liquid, mutation):
    prim = liquid.GetDefaultPrim()
    name = schema.PREFIX + "condenserLiquidMassFraction_kgPerKg"
    if mutation == "missing":
        prim.RemoveProperty(name)
    elif mutation == "type":
        prim.RemoveProperty(name)
        prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("1")
    elif mutation == "units":
        prim.GetAttribute(name).SetCustomDataByKey("units", "%")
    elif mutation == "fluid":
        prim.GetAttribute(schema.PREFIX + "condenserLiquidType").Set("UNKNOWN")
    else:
        prim.GetAttribute(name).Set(1.5)
    assert_rule_fires(_save(liquid), "AM.008")


@pytest.mark.parametrize("mutation", ["missing_grid", "zero_flow", "shape", "pressure_shape", "zero_pressure", "pressure_envelope", "flow_limit", "balance", "rating_index"])
def test_liquid_map_rejects_invalid_condenser_model(liquid, mutation):
    prim = liquid.GetDefaultPrim()
    if mutation == "missing_grid":
        prim.RemoveProperty(liquid_variant.COOLING_AXES[2])
    elif mutation == "zero_flow":
        prim.GetAttribute(liquid_variant.COOLING_AXES[2]).Set([0, .008])
    elif mutation == "shape":
        prim.GetAttribute(liquid_variant.COOLING_LOOKUPS[0]).Set([25000])
    elif mutation == "pressure_shape":
        prim.GetAttribute(liquid_variant.CONDENSER_PRESSURE_LOOKUPS[0]).Set([18000])
    elif mutation == "zero_pressure":
        prim.GetAttribute(liquid_variant.CONDENSER_PRESSURE_LOOKUPS[0]).Set([0, 18000, 46080, 46080])
    elif mutation == "pressure_envelope":
        prim.GetAttribute(liquid_variant.CONDENSER_PRESSURE_AXES[1]).Set([299.15, 303.15])
    elif mutation == "flow_limit":
        prim.GetAttribute(schema.PREFIX + "maximumOperatingCondenserLiquidVolumetricFlowRate_m3PerS").Set(.009)
    elif mutation == "balance":
        prim.GetAttribute(liquid_variant.COOLING_LOOKUPS[2]).Set([130000] * 32)
    else:
        prim.GetAttribute(schema.PREFIX + "referenceCoolingMapPointIndex").Set(32)
    assert_rule_fires(_save(liquid), "AM.011")


@pytest.mark.parametrize("mutation", ["missing", "wrong_system", "duplicate", "flow_units", "mismatched_flow", "temperature", "max_flow"])
def test_liquid_thermal_checks_separate_condenser_circuit(liquid, mutation):
    port = liquid.GetPrimAtPath("/world/ConnectionPoints/condenser_supply")
    prefix = "simready:connectionPoint:"
    if mutation == "missing":
        liquid.RemovePrim(port.GetPath())
    elif mutation == "wrong_system":
        port.GetAttribute(prefix + "system").Set("FWS")
    elif mutation == "duplicate":
        prim = UsdGeom.Xform.Define(liquid, "/world/ConnectionPoints/duplicate").GetPrim()
        for suffix, value in (("domain", "thermal"), ("system", "equipment_cooling"), ("direction", "supply")):
            prim.CreateAttribute(prefix + suffix, Sdf.ValueTypeNames.Token).Set(value)
    elif mutation == "flow_units":
        port.GetAttribute(prefix + "thermal:designFlowRate").Set(.005)
    elif mutation == "mismatched_flow":
        port.GetAttribute(prefix + "thermal:designFlowRate").Set(6)
    elif mutation == "temperature":
        port.GetAttribute(prefix + "thermal:designTemperature").Set(35)
    else:
        port.GetAttribute(prefix + "thermal:maxFlowRate").Set(7)
    assert_rule_fires(_save(liquid), "TC.004")


def test_liquid_electrical_capacity_uses_whole_chiller_rating(liquid):
    port = liquid.GetPrimAtPath("/world/ConnectionPoints/power")
    port.GetAttribute("simready:connectionPoint:electrical:ratedPower").Set(24000)
    assert_rule_fires(_save(liquid), "EL.006")


@pytest.mark.parametrize("circuit", ["evaporator", "condenser"])
@pytest.mark.parametrize("temperature", [float("nan"), float("inf"), -10])
def test_liquid_return_temperature_is_finite_and_warmer_at_positive_duty(liquid, circuit, temperature):
    port = liquid.GetPrimAtPath(f"/world/ConnectionPoints/{circuit}_return")
    port.GetAttribute("simready:connectionPoint:thermal:designTemperature").Set(temperature)
    assert_rule_fires(_save(liquid), "TC.004")

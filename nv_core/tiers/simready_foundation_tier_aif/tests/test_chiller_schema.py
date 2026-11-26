# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AIF 0.3 typed schema, tabular projection, interface and compatibility checks."""
import importlib.util
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom
import pytest

from _harness import _resolve_requirement, assert_no_failures, assert_rule_fires
from usd_validation_nvidia import IssueSeverity, ValidationEngine
from simready.foundation.tier_aif.rules_and_reqs.aif import air_cooled_chiller as air
from simready.foundation.tier_aif.rules_and_reqs.aif import chiller_schema as schema
from simready.foundation.tier_aif.rules_and_reqs.aif import equipment_classes

TIER = Path(__file__).resolve().parents[1]
REPO = TIER.parents[2]
AIR_SCHEMA = schema.schema_for("AirCooledChiller")

RENAMED_DIMENSIONLESS_ATTRIBUTES = (
    "cyclingDegradationCoefficient",
    "performanceMapCoolingGridCondenserAirEnteringRelativeHumidity",
    "referenceCOP",
)

REMOVED_OPERATING_FIELDS = {'aif:spec:evaporatorLeavingTemperatureSetpoint_degC',
 'aif:spec:referenceAmbientPressure_Pa',
 'aif:spec:referenceCompressorSequenceNumber',
 'aif:spec:referenceCondenserAirEnteringDrybulbTemperature_degC',
 'aif:spec:referenceCondenserAirEnteringRelativeHumidity_1',
 'aif:spec:referenceCondenserAirVolumetricFlowRate_m3PerS',
 'aif:spec:referenceEvaporatorLiquidLeavingTemperature_degC',
 'aif:spec:referenceEvaporatorLiquidVolumetricFlowRate_m3PerS',
 'aif:spec:referenceOperationState'}


def test_packaged_schema_matches_review_csv():
    path = TIER / "tools/generate_chiller_schema.py"
    spec = importlib.util.spec_from_file_location("chiller_generator", path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    expected = generator.schema_document(REPO / "standards/equipment-classes/aif-v0.3/air-cooled-chiller.csv")
    assert AIR_SCHEMA == {**expected, "introducedIn": "0.3.0"}
    assert len(AIR_SCHEMA["attributeDefinitions"]) == 58
    assert len(AIR_SCHEMA["requiredAttributes"]) == 17
    assert AIR_SCHEMA["attributeDefinitions"][schema.PREFIX + "performanceModelType"]["Options"] == "TABULAR"
    assert all(not name.endswith("_1") for name in AIR_SCHEMA["attributeDefinitions"])
    for name in RENAMED_DIMENSIONLESS_ATTRIBUTES:
        assert AIR_SCHEMA["attributeDefinitions"][schema.PREFIX + name]["SI Unit Values"] == "1"
    assert equipment_classes.normalize("AirCooledChiller") is None
    assert equipment_classes.normalize_03(" aircooledchiller ") == "air-cooled-chiller"
    assert schema.is_chiller(" aircooledchiller ")


def _values():
    values = {}
    for name, row in AIR_SCHEMA["attributeDefinitions"].items():
        kind = row["Attribute Type"]
        if row["Options"] != "Not required":
            v = row["Options"].split(" | ")[0]
            values[name] = [v] if kind.endswith("_array") else v
        elif kind in {"string", "token"}:
            values[name] = "Synthetic"
        elif kind == "bool":
            values[name] = False
        elif kind.endswith("_array"):
            values[name] = [1]
        else:
            values[name] = 1
    override = {'nominalVoltage_V': 400,
     'nominalFrequency_Hz': 50,
     'refrigerant': 'R-134a',
     'referenceInputPower_W': 25000,
     'referenceNetEvaporatorCapacity_W': 100000,
     'referenceNetCondenserCapacity_W': 125000,
     'referenceOilCoolerHeat_W': 0,
     'referenceAuxiliaryHeat_W': 0,
     'performanceModelType': 'TABULAR',
     'referenceCOP': 4,
     'minimumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS': 0.004,
     'maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS': 0.006,
     'evaporatorLeavingTemperatureSetpointMinimum_degC': 7,
     'evaporatorLeavingTemperatureSetpointMaximum_degC': 12}
    values.update({schema.PREFIX + k: v for k, v in override.items()})
    axes = [[.004, .006], [280.15, 285.15], [303.15, 308.15], [.4, .6], [101325], [1, 2]]
    values.update(dict(zip(air.COOLING_AXES, axes, strict=False)))
    size = 32
    tables = [[25000] * size, [100000] * size, [125000] * size, [12] * size,
              [0] * size, [0] * size, ["NORMAL"] * size]
    values.update(dict(zip(air.COOLING_LOOKUPS, tables, strict=False)))
    values[schema.STANDBY_AXES[0]] = [293.15, 303.15]
    values[schema.STANDBY_LOOKUPS[0]] = [400, 500]
    values.update(dict(zip(schema.PRESSURE_AXES, axes[:2], strict=False)))
    values[schema.PRESSURE_LOOKUPS[0]] = [20000, 20000, 45000, 45000]
    return values


@pytest.fixture
def asset(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "Chiller.usda"))
    properties = Sdf.Layer.CreateNew(str(tmp_path / "Chiller_Properties.usda"))
    stage.GetRootLayer().subLayerPaths = [properties.identifier]
    stage.SetEditTarget(properties)
    prim = UsdGeom.Xform.Define(stage, "/world").GetPrim()
    properties.defaultPrim = "world"
    stage.SetDefaultPrim(prim)
    prim.CreateAttribute("aif:core:assetClass", Sdf.ValueTypeNames.String).Set("AirCooledChiller")
    for name, v in _values().items():
        row = AIR_SCHEMA["attributeDefinitions"][name]
        attr = prim.CreateAttribute(name, schema.TYPE_NAMES[row["Attribute Type"]])
        attr.Set(v)
        attr.SetCustomDataByKey("units", row["SI Unit Values"])
    UsdGeom.Scope.Define(stage, "/world/ConnectionPoints")
    for name, domain, direction, system in (("supply", "thermal", "supply", "FWS"),
                                            ("return", "thermal", "return", "FWS"),
                                            ("power", "electrical", "input", "power")):
        port = UsdGeom.Xform.Define(stage, "/world/ConnectionPoints/" + name).GetPrim()
        for suffix, v in (("domain", domain), ("direction", direction), ("system", system)):
            port.CreateAttribute("simready:connectionPoint:" + suffix, Sdf.ValueTypeNames.Token).Set(v)
        fields = {"designFlowRate": 4, "maxFlowRate": 6, "designTemperature": 7 if direction == "supply" else 13} if domain == "thermal" else {"nominalVoltage": 400, "frequency": 50, "ratedPower": 45000}
        for suffix, v in fields.items():
            port.CreateAttribute("simready:connectionPoint:" + domain + ":" + suffix, Sdf.ValueTypeNames.Float).Set(v)
    return stage


def _save(stage):
    for layer in stage.GetLayerStack():
        if not layer.anonymous:
            layer.Save()
    return Path(stage.GetRootLayer().realPath)


def test_registered_chiller_rules_and_legacy_isolation(asset):
    path = _save(asset)
    assert_no_failures(path, ["AM.008", "AM.010", "TC.003", "EL.005"])
    assert_rule_fires(path, "AM.007")


def test_air_profile_rejects_a_liquid_chiller_declaration(asset):
    asset.GetDefaultPrim().GetAttribute("aif:core:assetClass").Set("LiquidCooledChiller")
    assert_rule_fires(_save(asset), "AM.010")


@pytest.mark.parametrize("properties_class,composed_class", [
    ("AirCooledChiller", "LiquidCooledChiller"),
    ("LiquidCooledChiller", "AirCooledChiller"),
    ("AirCooledChiller", "cdu"),
    ("cdu", "AirCooledChiller"),
])
def test_chiller_requires_consistent_class_across_layers(asset, properties_class, composed_class):
    root = asset.GetDefaultPrim()
    root.GetAttribute("aif:core:assetClass").Set(properties_class)
    with Usd.EditContext(asset, asset.GetRootLayer()):
        root.GetAttribute("aif:core:assetClass").Set(composed_class)
    path = _save(asset)
    assert_rule_fires(path, "AM.008")
    assert_rule_fires(path, "AM.010")


@pytest.mark.parametrize("declaration", ["missing-properties", "missing-composed-value", "mistyped-properties", "mistyped-root"])
def test_chiller_map_requires_typed_class_on_both_layers(asset, declaration):
    prim = asset.GetDefaultPrim()
    name = "aif:core:assetClass"
    if declaration == "missing-properties":
        assert prim.RemoveProperty(name)
        with Usd.EditContext(asset, asset.GetRootLayer()):
            prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("AirCooledChiller")
    elif declaration == "mistyped-properties":
        assert prim.RemoveProperty(name)
        prim.CreateAttribute(name, Sdf.ValueTypeNames.Token).Set("AirCooledChiller")
    else:
        with Usd.EditContext(asset, asset.GetRootLayer()):
            if declaration == "mistyped-root":
                spec = Sdf.CreatePrimInLayer(asset.GetRootLayer(), prim.GetPath())
                Sdf.AttributeSpec(spec, name, Sdf.ValueTypeNames.Token).default = "AirCooledChiller"
            else:
                prim.GetAttribute(name).Block()
    assert_rule_fires(_save(asset), "AM.010")


@pytest.mark.parametrize("name", RENAMED_DIMENSIONLESS_ATTRIBUTES)
def test_metadata_rejects_obsolete_dimensionless_names(asset, name):
    prim = asset.GetDefaultPrim()
    canonical = prim.GetAttribute(schema.PREFIX + name)
    obsolete = prim.CreateAttribute(canonical.GetName() + "_1", canonical.GetTypeName())
    obsolete.Set(canonical.Get())
    obsolete.SetCustomDataByKey("units", "1")
    prim.RemoveProperty(canonical.GetName())
    assert_rule_fires(_save(asset), "AM.008")


def test_non_tabular_model_fails_metadata_and_map_validation(asset):
    asset.GetDefaultPrim().GetAttribute(schema.PREFIX + "performanceModelType").Set("CURVE-FIT")
    path = _save(asset)
    for code in ("AM.008", "AM.010"):
        assert_rule_fires(path, code)


@pytest.mark.parametrize("mutation", ["missing", "type", "units", "enum", "nan", "fraction"])
def test_metadata_rejects_invalid_authoring(asset, mutation):
    prim = asset.GetDefaultPrim()
    if mutation == "missing":
        prim.RemoveProperty(schema.PREFIX + "nominalVoltage_V")
    elif mutation == "type":
        prim.RemoveProperty(schema.PREFIX + "nominalVoltage_V")
        prim.CreateAttribute(schema.PREFIX + "nominalVoltage_V", Sdf.ValueTypeNames.String).Set("400")
    elif mutation == "units":
        prim.GetAttribute(schema.PREFIX + "referenceInputPower_W").SetCustomDataByKey("units", "kW")
    elif mutation == "enum":
        prim.GetAttribute(schema.PREFIX + "compressorType").Set("UNKNOWN")
    elif mutation == "nan":
        prim.GetAttribute(schema.PREFIX + "nominalVoltage_V").Set(float("nan"))
    else:
        prim.GetAttribute(schema.PREFIX + "evaporatorLiquidMassFraction_kgPerKg").Set(1.5)
    assert_rule_fires(_save(asset), "AM.008")


@pytest.mark.parametrize("mutation", ["shape", "standby_shape", "pressure_shape", "zero_flow", "zero_pressure", "zero_airflow", "grid", "state", "cop", "balance", "envelope"])
def test_map_rejects_invalid_model(asset, mutation):
    prim = asset.GetDefaultPrim()
    if mutation == "shape":
        prim.GetAttribute(air.COOLING_LOOKUPS[0]).Set([25000])
    elif mutation == "standby_shape":
        prim.GetAttribute(schema.STANDBY_LOOKUPS[0]).Set([400])
    elif mutation == "pressure_shape":
        prim.GetAttribute(schema.PRESSURE_LOOKUPS[0]).Set([20000])
    elif mutation == "zero_flow":
        prim.GetAttribute(air.COOLING_AXES[0]).Set([0, .006])
    elif mutation == "zero_pressure":
        prim.GetAttribute(air.COOLING_AXES[4]).Set([0])
    elif mutation == "zero_airflow":
        prim.GetAttribute(air.COOLING_LOOKUPS[3]).Set([0] * 32)
    elif mutation == "grid":
        prim.GetAttribute(air.COOLING_AXES[0]).Set([.006, .004])
    elif mutation == "state":
        prim.GetAttribute(air.COOLING_LOOKUPS[-1]).Set(["FAULT"] * 32)
    elif mutation == "cop":
        prim.GetAttribute(schema.PREFIX + "referenceCOP").Set(5)
    elif mutation == "balance":
        prim.GetAttribute(air.COOLING_LOOKUPS[2]).Set([100000] * 32)
    else:
        prim.GetAttribute(schema.PREFIX + "maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS").Set(.008)
    assert_rule_fires(_save(asset), "AM.010")


def test_retained_ratings_are_not_anchored_to_an_invented_map_point(asset):
    prim = asset.GetDefaultPrim()
    prim.RemoveProperty(schema.PREFIX + "referenceCoolingMapPointIndex")
    powers = [30000 + i * 100 for i in range(32)]
    for name, table in zip(air.COOLING_LOOKUPS[:3], (powers, [p * 4 for p in powers], [p * 5 for p in powers]), strict=False):
        prim.GetAttribute(name).Set(table)
    # The retained 25 kW / 100 kW ratings have no declared operating conditions.
    # They must not be compared to the first or any substituted map point.
    assert schema.value(prim, "referenceInputPower_W") == 25000
    assert_no_failures(_save(asset), ["AM.010"])


@pytest.mark.parametrize("point_index", [0, 31])
def test_declared_rating_point_selects_only_that_cooling_lookup(asset, point_index):
    prim = asset.GetDefaultPrim()
    prim.GetAttribute(schema.PREFIX + "referenceCoolingMapPointIndex").Set(point_index)
    for name, rating in zip(air.COOLING_LOOKUPS[:3], (25000, 100000, 125000), strict=True):
        table = [rating / 2] * 32
        table[point_index] = rating
        prim.GetAttribute(name).Set(table)
    assert_no_failures(_save(asset), ["AM.010"])


@pytest.mark.parametrize("point_index", [-1, 32])
def test_declared_rating_point_must_be_in_range(asset, point_index):
    asset.GetDefaultPrim().GetAttribute(schema.PREFIX + "referenceCoolingMapPointIndex").Set(point_index)
    assert_rule_fires(_save(asset), "AM.010")


@pytest.mark.parametrize("rating", ["referenceInputPower_W", "referenceNetEvaporatorCapacity_W", "referenceNetCondenserCapacity_W"])
def test_rating_point_mismatch_is_reported_for_each_rating(asset, rating):
    prim = asset.GetDefaultPrim()
    prim.GetAttribute(schema.PREFIX + "referenceCoolingMapPointIndex").Set(0)
    prim.GetAttribute(schema.PREFIX + rating).Set(1)
    errors = schema.validate_maps(prim)
    assert any(rating in error and "referenceCoolingMapPointIndex" in error for error in errors)
    assert_rule_fires(_save(asset), "AM.010")


@pytest.mark.parametrize(("suffix", "invalid"), [
    ("numberOfFans", -1), ("fanType", " "),
    ("maximumCondenserFanRotationalSpeed_Hz", 0), ("maximumCondenserFanRotationalSpeed_Hz", -10),
    ("efficiencyRotatingEquipment", 0), ("efficiencyRotatingEquipment", 95),
    ("refrigerantChargePerCircuit_kg", []), ("refrigerantChargePerCircuit_kg", [1, 0]),
    ("refrigerantChargePerCircuit_kg", [-1, 2]),
])
def test_invalid_optional_equipment_ratings_fail_metadata(asset, suffix, invalid):
    asset.GetDefaultPrim().GetAttribute(schema.PREFIX + suffix).Set(invalid)
    assert_rule_fires(_save(asset), "AM.008")


@pytest.mark.parametrize(("name", "invalid"), [
    ("cyclingDegradationCoefficient", -0.1),
    ("performanceMapCoolingGridCondenserAirEnteringRelativeHumidity", [0.4, 1.1]),
])
def test_dimensionless_fractions_enforce_bounds(asset, name, invalid):
    asset.GetDefaultPrim().GetAttribute(schema.PREFIX + name).Set(invalid)
    assert_rule_fires(_save(asset), "AM.008")


def test_zero_ec_fans_and_multiple_refrigerant_circuits_are_valid(asset):
    prim = asset.GetDefaultPrim()
    prim.GetAttribute(schema.PREFIX + "numberOfFans").Set(0)
    prim.GetAttribute(schema.PREFIX + "refrigerantChargePerCircuit_kg").Set([1.5, 3])
    assert_no_failures(_save(asset), ["AM.008"])


def test_unresolved_optional_condition_does_not_require_presence(asset):
    prim = asset.GetDefaultPrim()
    for name in AIR_SCHEMA["attributeDefinitions"]:
        if name not in AIR_SCHEMA["requiredAttributes"] and not name.startswith(schema.PREFIX + "performanceMap"):
            prim.RemoveProperty(name)
    assert_no_failures(_save(asset), ["AM.008", "AM.010"])


@pytest.mark.parametrize("mutation", ["flow", "circuit", "missing"])
def test_thermal_interfaces_reject_wrong_mapping(asset, mutation):
    port = asset.GetPrimAtPath("/world/ConnectionPoints/supply")
    if mutation == "flow":
        port.GetAttribute("simready:connectionPoint:thermal:designFlowRate").Set(.004)
    elif mutation == "circuit":
        port.GetAttribute("simready:connectionPoint:system").Set("TCS")
    else:
        asset.RemovePrim(port.GetPath())
    assert_rule_fires(_save(asset), "TC.003")


@pytest.mark.parametrize("mutation", ["missing", "voltage", "capacity"])
def test_electrical_interfaces_reject_wrong_mapping(asset, mutation):
    port = asset.GetPrimAtPath("/world/ConnectionPoints/power")
    if mutation == "missing":
        asset.RemovePrim(port.GetPath())
    elif mutation == "voltage":
        port.GetAttribute("simready:connectionPoint:electrical:nominalVoltage").Set(230)
    else:
        port.GetAttribute("simready:connectionPoint:electrical:ratedPower").Set(250)
    assert_rule_fires(_save(asset), "EL.005")


@pytest.mark.parametrize("name", list(AIR_SCHEMA["attributeDefinitions"]))
def test_wrong_typed_metadata_reports_failure_without_execution_error(asset, name):
    prim = asset.GetDefaultPrim()
    prim.RemoveProperty(name)
    if AIR_SCHEMA["attributeDefinitions"][name]["Attribute Type"] == "string":
        prim.CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(1)
    else:
        prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("bad")
    engine = ValidationEngine(init_rules=False)
    for code in ("AM.008", "AM.010", "TC.003", "EL.005"):
        engine.enable_requirement(_resolve_requirement(code))
    results = list(engine.validate(str(_save(asset))))
    assert not [issue for issue in results if issue.severity is IssueSeverity.ERROR]
    assert any(issue.severity is IssueSeverity.FAILURE for issue in results)


def test_wrong_typed_maximum_flow_is_measured_thermal_failure(asset):
    prim = asset.GetDefaultPrim()
    name = schema.PREFIX + "maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS"
    prim.RemoveProperty(name)
    prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("bad")
    engine = ValidationEngine(init_rules=False)
    requirement = _resolve_requirement("TC.003")
    engine.enable_requirement(requirement)
    results = list(engine.validate(str(_save(asset))))
    assert not [issue for issue in results if issue.severity is IssueSeverity.ERROR]
    assert any(issue.severity is IssueSeverity.FAILURE and issue.requirement is requirement for issue in results)


@pytest.mark.parametrize(("port_name", "suffix", "code"), [
    ("supply", "thermal:designFlowRate", "TC.003"),
    ("supply", "thermal:maxFlowRate", "TC.003"),
    ("supply", "thermal:designTemperature", "TC.003"),
    ("return", "thermal:designFlowRate", "TC.003"),
    ("return", "thermal:maxFlowRate", "TC.003"),
    ("power", "electrical:nominalVoltage", "EL.005"),
    ("power", "electrical:frequency", "EL.005"),
    ("power", "electrical:ratedPower", "EL.005"),
])
def test_wrong_typed_connection_mapping_is_measured_failure(asset, port_name, suffix, code):
    port = asset.GetPrimAtPath("/world/ConnectionPoints/" + port_name)
    name = "simready:connectionPoint:" + suffix
    port.RemoveProperty(name)
    port.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("bad")
    engine = ValidationEngine(init_rules=False)
    requirement = _resolve_requirement(code)
    engine.enable_requirement(requirement)
    results = list(engine.validate(str(_save(asset))))
    assert not [issue for issue in results if issue.severity is IssueSeverity.ERROR]
    assert any(issue.severity is IssueSeverity.FAILURE and issue.requirement is requirement for issue in results)


def test_deleted_operating_fields_are_absent_from_schema_and_fixture(asset):
    assert not REMOVED_OPERATING_FIELDS.intersection(AIR_SCHEMA["attributeDefinitions"])
    assert not REMOVED_OPERATING_FIELDS.intersection(AIR_SCHEMA["attributes"])
    assert not REMOVED_OPERATING_FIELDS.intersection(AIR_SCHEMA["requiredAttributes"])
    assert not REMOVED_OPERATING_FIELDS.intersection(_values())
    assert all(not asset.GetDefaultPrim().HasProperty(name) for name in REMOVED_OPERATING_FIELDS)
    assert_no_failures(_save(asset), ["AM.008", "AM.010", "TC.003", "EL.005"])


@pytest.mark.parametrize("design_flow", [4.5, 5, 5.5])
def test_thermal_design_conditions_can_vary_inside_equipment_envelopes(asset, design_flow):
    for name in ("supply", "return"):
        port = asset.GetPrimAtPath("/world/ConnectionPoints/" + name)
        port.GetAttribute("simready:connectionPoint:thermal:designFlowRate").Set(design_flow)
        port.GetAttribute("simready:connectionPoint:thermal:maxFlowRate").Set(8)
    asset.GetPrimAtPath("/world/ConnectionPoints/supply").GetAttribute("simready:connectionPoint:thermal:designTemperature").Set(9)
    assert_no_failures(_save(asset), ["TC.003"])


@pytest.mark.parametrize(("suffix", "bad_value"), [
    ("designFlowRate", 3), ("designFlowRate", 7),
    ("maxFlowRate", 5), ("designTemperature", 6), ("designTemperature", 13),
])
def test_thermal_interface_respects_operating_envelopes(asset, suffix, bad_value):
    port = asset.GetPrimAtPath("/world/ConnectionPoints/supply")
    port.GetAttribute("simready:connectionPoint:thermal:" + suffix).Set(bad_value)
    assert_rule_fires(_save(asset), "TC.003")


def test_evaporator_pair_rejects_distinct_in_envelope_design_flows(asset):
    supply = asset.GetPrimAtPath("/world/ConnectionPoints/supply")
    return_port = asset.GetPrimAtPath("/world/ConnectionPoints/return")
    supply.GetAttribute("simready:connectionPoint:thermal:designFlowRate").Set(4)
    return_port.GetAttribute("simready:connectionPoint:thermal:designFlowRate").Set(6)
    assert schema.validate_thermal(asset) == [
        "Evaporator supply and return designFlowRate must match for the single evaporator circuit"
    ]
    assert_rule_fires(_save(asset), "TC.003")

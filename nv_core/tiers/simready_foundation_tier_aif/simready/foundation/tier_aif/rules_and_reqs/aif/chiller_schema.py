# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Common validation for packaged AIF 0.3 chiller classes."""
import math
from importlib import import_module

from pxr import Sdf, Usd

from . import _stage, equipment_classes

TYPE_NAMES = {
    "float": Sdf.ValueTypeNames.Float, "int": Sdf.ValueTypeNames.Int,
    "bool": Sdf.ValueTypeNames.Bool, "string": Sdf.ValueTypeNames.String,
    "token": Sdf.ValueTypeNames.Token, "float_array": Sdf.ValueTypeNames.FloatArray,
    "int_array": Sdf.ValueTypeNames.IntArray, "token_array": Sdf.ValueTypeNames.TokenArray,
}
PREFIX = "aif:spec:"
EVAPORATOR_AXES = tuple(PREFIX + "performanceMapCoolingGrid" + suffix for suffix in (
    "EvaporatorLiquidVolumetricFlowRate_m3PerS", "EvaporatorLiquidLeavingTemperature_K",
))
STANDBY_AXES = (PREFIX + "performanceMapStandbyGridEnvironmentDryBulbTemperature_K",)
STANDBY_LOOKUPS = (PREFIX + "performanceMapStandbyLookupInputPower_W",)
PRESSURE_AXES = tuple(PREFIX + "performanceMapEvaporatorLiquidPressureDifferentialGrid" + suffix for suffix in (
    "EvaporatorLiquidVolumetricFlowRate_m3PerS", "EvaporatorLiquidLeavingTemperature_K",
))
PRESSURE_LOOKUPS = (PREFIX + "performanceMapEvaporatorLiquidPressureDifferentialLookupEvaporatorLiquidDifferentialPressure_Pa",)


def schema_for(raw):
    """Look up the packaged chiller schema for an AIF 0.3 asset class."""
    key = equipment_classes.normalize_03(raw) if isinstance(raw, str) else None
    return equipment_classes.CHILLER_SCHEMAS.get(key)


def has_class(stage, token):
    """Check the dedicated profile's class in Properties and on the composed default prim."""
    schema = schema_for(token)
    return schema is not None and _stage.has_typed_attribute(
        stage, "aif:core:assetClass", Sdf.ValueTypeNames.String,
        lambda value: schema_for(value) is schema,
    )


def register_chiller_classes():
    """Import each installed class module to register its dedicated profile rules."""
    for schema in equipment_classes.CHILLER_SCHEMAS.values():
        _variant(schema)


def is_chiller(raw):
    return schema_for(raw) is not None


def _schema(prim):
    attr = prim.GetAttribute("aif:core:assetClass") if prim else None
    return schema_for(attr.Get() if attr else None)


def _variant(schema):
    # Each installed class supplies its own condenser maps and interface rules.
    return import_module("." + schema["class"].replace("-", "_"), __package__)


def properties_prim(stage):
    spec = _stage.properties_prim_spec(stage)
    return stage.GetPrimAtPath(spec.path) if spec is not None else None


def value(prim, suffix):
    attr = prim.GetAttribute(suffix if suffix.startswith(PREFIX) else PREFIX + suffix) if prim else None
    return attr.Get() if attr else None


def _close(a, b):
    return _numeric(a) and _numeric(b) and math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-7)


def _numeric(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)


def validate_attributes(prim):
    """Check authored metadata against this class's attribute definitions."""
    errors = []
    if not prim:
        return ["Missing default prim in the properties sublayer"]
    schema = _schema(prim)
    if schema is None:
        return ["No registered chiller schema for the properties prim"]
    variant = _variant(schema)
    for field in ("cyclingDegradationCoefficient", "referenceCOP") + variant.RENAMED_DIMENSIONLESS_FIELDS:
        name = PREFIX + field
        if prim.HasAttribute(name + "_1"):
            errors.append(f"Rename {name}_1 to {name} and retain dimensionless units '1'")
    for name, row in schema["attributeDefinitions"].items():
        attr = prim.GetAttribute(name)
        authored = bool(attr and attr.HasAuthoredValueOpinion())
        if not authored:
            if name in schema["requiredAttributes"]:
                errors.append(f"Missing required chiller attribute: {name}")
            continue
        if attr.GetTypeName() != TYPE_NAMES[row["Attribute Type"]]:
            errors.append(f"{name}: expected USD type {TYPE_NAMES[row['Attribute Type']]}")
            continue
        v = attr.Get()
        if v is None:
            errors.append(f"{name}: an authored default value is required")
            continue
        if attr.GetCustomDataByKey("units") != row["SI Unit Values"]:
            errors.append(f"{name}: customData units must be {row['SI Unit Values']!r}")
        entries = list(v) if row["Attribute Type"].endswith("_array") else [v]
        options = row["Options"].split(" | ") if row["Options"] != "Not required" else None
        for entry in entries:
            if options is not None and entry not in options:
                errors.append(f"{name}: value {entry!r} is outside Options")
            if row["Attribute Type"] in {"float", "int", "float_array", "int_array"}:
                if not _numeric(entry):
                    errors.append(f"{name}: numeric values must be finite")
                    continue
                if "MassFraction" in name or "cyclingDegradationCoefficient" in name:
                    if not 0 <= entry <= 1:
                        errors.append(f"{name}: value must be between 0 and 1")
                elif row["SI Unit Values"] in {"W", "Pa", "V", "Hz", "A", "m³/s", "mm", "(m²·K)/W"} and entry < 0:
                    errors.append(f"{name}: value must be nonnegative")
                if row["SI Unit Values"] == "K" and entry <= 0:
                    errors.append(f"{name}: absolute temperature must be positive")
                if ("CompressorSequenceNumber" in name or name.endswith("numberOfCompressors")) and entry < 1:
                    errors.append(f"{name}: count or sequence rank must be at least 1")
    refrigerant = value(prim, "refrigerant")
    if isinstance(refrigerant, str) and not refrigerant.startswith("R-"):
        errors.append("refrigerant must use an R- designation")
    for name in schema["requiredAttributes"]:
        attr = prim.GetAttribute(name)
        if attr and attr.GetTypeName() in (Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.Token) and attr.Get() == "":
            errors.append(f"{name}: required string value is empty")
    if variant.validate_extra_attributes is not None:
        variant.validate_extra_attributes(prim, errors)
    return errors


def _map(prim, axes, lookups, errors):
    definitions = _schema(prim)["attributeDefinitions"]
    grids, tables = [], []
    for name in axes + lookups:
        v = value(prim, name)
        if v is None or not hasattr(v, "__len__") or len(v) == 0:
            errors.append(f"TABULAR model is missing nonempty array: {name}")
            return None
        if prim.GetAttribute(name).GetTypeName() != TYPE_NAMES[definitions[name]["Attribute Type"]]:
            errors.append(f"{name}: wrong map array type")
            return None
    for name in axes:
        axis = list(value(prim, name))
        if not all(_numeric(v) for v in axis) or any(a >= b for a, b in zip(axis, axis[1:], strict=False)):
            errors.append(f"{name}: axes must be finite and strictly increasing")
            return None
        unit = definitions[name]["SI Unit Values"]
        if unit in {"m³/s", "K", "Pa"} and any(v <= 0 for v in axis):
            errors.append(f"{name}: flow, absolute-temperature and absolute-pressure axes must be positive")
            return None
        if name.endswith("CompressorSequenceNumber") and any(v < 1 for v in axis):
            errors.append(f"{name}: compressor sequence ranks start at 1")
            return None
        grids.append(axis)
    size = math.prod(map(len, grids))
    for name in lookups:
        table = list(value(prim, name))
        if len(table) != size:
            errors.append(f"{name}: lookup length {len(table)} must equal axis product {size}")
            return None
        if not name.endswith("OperationState") and not all(_numeric(v) for v in table):
            errors.append(f"{name}: lookup values must be finite")
            return None
        if name.endswith("OperationState") and any(v not in {"NORMAL", "STANDBY"} for v in table):
            errors.append(f"{name}: operation state must be NORMAL or STANDBY")
            return None
        tables.append(table)
    return grids, tables


def validate_maps(prim):
    if value(prim, "performanceModelType") != "TABULAR":
        return ["Chiller requires performanceModelType = TABULAR"]
    schema = _schema(prim)
    if schema is None:
        return ["No registered chiller schema for the properties prim"]
    errors = []
    variant = _variant(schema)
    cooling = _map(prim, variant.COOLING_AXES, variant.COOLING_LOOKUPS, errors)
    _map(prim, STANDBY_AXES, STANDBY_LOOKUPS, errors)
    pressure = _map(prim, PRESSURE_AXES, PRESSURE_LOOKUPS, errors)
    if cooling is None:
        return errors
    grids, tables = cooling
    lookups = {name.removeprefix(PREFIX + "performanceMapCoolingLookup"): table
               for name, table in zip(variant.COOLING_LOOKUPS, tables, strict=True)}
    point_index = value(prim, "referenceCoolingMapPointIndex")
    if point_index is not None:
        if type(point_index) is not int or not 0 <= point_index < len(lookups["InputPower_W"]):
            errors.append("referenceCoolingMapPointIndex must be an integer within the flattened cooling map")
        else:
            for field in ("InputPower_W", "NetEvaporatorCapacity_W", "NetCondenserCapacity_W"):
                rating = "reference" + field
                if not _close(value(prim, rating), lookups[field][point_index]):
                    errors.append(f"{rating} must equal the cooling lookup at referenceCoolingMapPointIndex {point_index}")
    for i, state in enumerate(lookups["OperationState"]):
        # A nonzero, separately rejected oil or auxiliary heat load needs its own balance model.
        if state == "NORMAL" and _close(lookups["OilCoolerHeat_W"][i], 0) and _close(lookups["AuxiliaryHeat_W"][i], 0):
            if not _close(lookups["NetCondenserCapacity_W"][i], lookups["NetEvaporatorCapacity_W"][i] + lookups["InputPower_W"][i]):
                errors.append(f"Cooling table index {i}: condenser capacity must balance evaporator capacity plus input power")
    cop = value(prim, "referenceCOP")
    power, capacity = value(prim, "referenceInputPower_W"), value(prim, "referenceNetEvaporatorCapacity_W")
    if cop is not None and _numeric(cop) and _numeric(power) and power > 0 and _numeric(capacity) and not _close(cop, capacity / power):
        errors.append("referenceCOP must equal net evaporator capacity divided by reference input power")
    _check_limits(prim, "minimumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS",
                  "maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS", grids[0], errors)
    _check_limits(prim, "evaporatorLeavingTemperatureSetpointMinimum_degC",
                  "evaporatorLeavingTemperatureSetpointMaximum_degC", [v - 273.15 for v in grids[1]], errors)
    if pressure is not None:
        _check_pressure_envelope("Evaporator", pressure[0], grids[:2], errors)
    variant.validate_condenser_map(prim, grids, lookups, errors)
    return errors


def _check_pressure_envelope(circuit, pressure_axes, cooling_axes, errors):
    for pressure, cooling, tolerance in zip(pressure_axes, cooling_axes, (1e-5, 1e-4), strict=True):
        if pressure[0] > cooling[0] + tolerance or pressure[-1] < cooling[-1] - tolerance:
            errors.append(f"{circuit} pressure-drop map must cover the cooling-map {circuit.lower()} envelope")
            return


def _check_limits(prim, lo, hi, axis, errors):
    lower, upper = value(prim, lo), value(prim, hi)
    if lower is not None and (not _numeric(lower) or (lower < axis[0] and not _close(lower, axis[0])) or (lower > axis[-1] and not _close(lower, axis[-1]))):
        errors.append(f"{lo}: limit must lie within the performance-map safe envelope")
    if upper is not None and (not _numeric(upper) or (upper > axis[-1] and not _close(upper, axis[-1])) or (upper < axis[0] and not _close(upper, axis[0]))):
        errors.append(f"{hi}: limit must lie within the performance-map safe envelope")
    if _numeric(lower) and _numeric(upper) and lower > upper:
        errors.append(f"{lo}: minimum limit exceeds maximum limit")


def _points(stage, domain):
    root = stage.GetDefaultPrim()
    scope = root.GetChild("ConnectionPoints") if root else None
    if not scope:
        return []
    return [p for p in Usd.PrimRange(scope) if p != scope and p.GetAttribute("simready:connectionPoint:domain").Get() == domain]


def _cp(prim, suffix):
    return prim.GetAttribute("simready:connectionPoint:" + suffix).Get()


def validate_thermal(stage):
    prim = properties_prim(stage)
    schema = _schema(prim)
    if schema is None:
        return ["No registered chiller schema for the properties prim"]
    variant = _variant(schema)
    errors = []
    capacity = value(prim, "referenceNetEvaporatorCapacity_W")
    if not _numeric(capacity) or capacity <= 0:
        errors.append("referenceNetEvaporatorCapacity_W must be positive")
    errors.extend(_validate_circuit(
        stage, prim, "evaporator", "FWS", EVAPORATOR_AXES, "supply",
        "evaporatorLeavingTemperatureSetpointMinimum_degC", "evaporatorLeavingTemperatureSetpointMaximum_degC",
        check_temperature_rise=variant.CHECK_TEMPERATURE_RISE,
    ))
    if variant.validate_condenser_interface is not None:
        variant.validate_condenser_interface(stage, prim, errors)
    return errors


def _validate_circuit(stage, prim, circuit, system, axes_names, temperature_direction,
                      low_temperature=None, high_temperature=None, *, check_temperature_rise=False):
    errors = []
    ports = _points(stage, "thermal")
    selected = {}
    for direction in ("supply", "return"):
        matches = [p for p in ports if _cp(p, "system") == system and _cp(p, "direction") == direction]
        if len(matches) != 1:
            errors.append(f"Expected one {system} {circuit} {direction} connection point")
        else:
            selected[direction] = matches[0]
    # Check connection design conditions against the equipment and map envelopes.
    axes = []
    for name in axes_names:
        attr = prim.GetAttribute(name) if prim else None
        axis = attr.Get() if attr else None
        if (not attr or attr.GetTypeName() != TYPE_NAMES[_schema(prim)["attributeDefinitions"][name]["Attribute Type"]]
                or axis is None or len(axis) == 0 or not all(_numeric(v) and v > 0 for v in axis)
                or any(a >= b for a, b in zip(axis, axis[1:], strict=False))):
            errors.append(f"{name}: a valid axis is required for thermal envelope checks")
            return errors
        axes.append(axis)
    bounds = []
    for low_name, high_name, axis in (
        (f"minimumOperating{circuit.title()}LiquidVolumetricFlowRate_m3PerS", f"maximumOperating{circuit.title()}LiquidVolumetricFlowRate_m3PerS", axes[0]),
        (low_temperature, high_temperature, [t - 273.15 for t in axes[1]]),
    ):
        low = value(prim, low_name) if low_name else None
        high = value(prim, high_name) if high_name else None
        if low is not None and not _numeric(low):
            errors.append(f"{low_name}: operating-envelope limit must be numeric")
            return errors
        if high is not None and not _numeric(high):
            errors.append(f"{high_name}: operating-envelope limit must be numeric")
            return errors
        low = axis[0] if low is None else low
        high = axis[-1] if high is None else high
        if (low > high or (low < axis[0] and not _close(low, axis[0]))
                or (high > axis[-1] and not _close(high, axis[-1]))):
            errors.append(f"{low_name}: operating limits must lie within the map envelope")
            return errors
        bounds.append((low, high))
    flow_low, flow_high = (v * 1000 for v in bounds[0])  # m³/s -> CP2 L/s.
    for port in selected.values():
        design = _cp(port, "thermal:designFlowRate")
        if (not _numeric(design) or design <= 0
                or (design < flow_low and not _close(design, flow_low))
                or (design > flow_high and not _close(design, flow_high))):
            errors.append(f"{port.GetName()}: designFlowRate in L/s must lie within the {circuit} envelope converted from m³/s")
        limit = _cp(port, "thermal:maxFlowRate")
        if (not _numeric(limit) or limit <= 0 or not _numeric(design)
                or (limit < design and not _close(limit, design))
                or (limit < flow_high and not _close(limit, flow_high))):
            errors.append(f"{port.GetName()}: maxFlowRate in L/s must cover design flow and the converted maximum {circuit} flow")
    supply = selected.get("supply")
    return_port = selected.get("return")
    if supply and return_port:
        supply_flow = _cp(supply, "thermal:designFlowRate")
        return_flow = _cp(return_port, "thermal:designFlowRate")
        if _numeric(supply_flow) and _numeric(return_flow) and not _close(supply_flow, return_flow):
            errors.append(f"{circuit.title()} supply and return designFlowRate must match for the single {circuit} circuit")
        if check_temperature_rise:
            supply_temperature = _cp(supply, "thermal:designTemperature")
            return_temperature = _cp(return_port, "thermal:designTemperature")
            if not _numeric(supply_temperature) or not _numeric(return_temperature):
                errors.append(f"{circuit.title()} supply and return designTemperature must be finite")
            else:
                duty = value(prim, f"referenceNet{circuit.title()}Capacity_W")
                if _numeric(duty) and duty > 0 and return_temperature <= supply_temperature:
                    errors.append(f"{circuit.title()} return designTemperature must exceed supply temperature for positive duty")
    temperature_port = selected.get(temperature_direction)
    if temperature_port:
        temperature = _cp(temperature_port, "thermal:designTemperature")
        low, high = bounds[1]
        if (not _numeric(temperature)
                or (temperature < low and not _close(temperature, low))
                or (temperature > high and not _close(temperature, high))):
            errors.append(f"{circuit.title()} {temperature_direction} designTemperature must lie within its map temperature envelope")

    return errors


def validate_electrical(stage):
    prim = properties_prim(stage)
    errors = []
    fields = ("nominalVoltage_V", "nominalFrequency_Hz", "referenceInputPower_W")
    vals = [value(prim, f) for f in fields]
    for name, v in zip(fields, vals, strict=False):
        if not _numeric(v) or v <= 0:
            errors.append(f"{name} must be positive")
    ports = [p for p in _points(stage, "electrical") if _cp(p, "system") == "power" and _cp(p, "direction") == "input"]
    if not ports:
        return errors + ["Missing electrical power/input connection point"]
    total = 0.0
    for port in ports:
        for suffix, expected in zip(("nominalVoltage", "frequency"), vals[:2], strict=False):
            actual = _cp(port, "electrical:" + suffix)
            if not _numeric(actual) or not _numeric(expected) or not _close(actual, expected):
                errors.append(f"{port.GetName()}: electrical {suffix} must match the chiller reference supply")
        rating = _cp(port, "electrical:ratedPower")
        if not _numeric(rating) or rating <= 0:
            errors.append(f"{port.GetName()}: electrical ratedPower must be positive")
        else:
            total += rating
    if _numeric(vals[2]) and total < vals[2] - 1e-4:
        errors.append("Electrical connection capacity must be at least referenceInputPower_W; reference input is not a nameplate rating")
    return errors

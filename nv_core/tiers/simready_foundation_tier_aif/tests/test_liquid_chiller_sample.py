# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Native USD evidence for the fictional two-circuit liquid chiller."""
from collections import Counter
import importlib.util
import itertools
import json
import math
from pathlib import Path
import shutil

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

REPO = Path(__file__).resolve().parents[4]
SAMPLE = REPO / "sample_content/aif/Synthetic_LiquidCooledChiller"
ASSET = SAMPLE / "asset/Synthetic_LiquidCooledChiller.usda"
CSV = REPO / "standards/equipment-classes/aif-v0.3/liquid-cooled-chiller.csv"
PREFIX = "aif:spec:"


@pytest.fixture(scope="module")
def stage():
    result = Usd.Stage.Open(str(ASSET))
    assert result
    return result


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("liquid_chiller_generator", SAMPLE / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def value(stage, suffix):
    return stage.GetDefaultPrim().GetAttribute(PREFIX + suffix).Get()


def cp(stage, name, suffix):
    return stage.GetPrimAtPath("/world/ConnectionPoints/" + name).GetAttribute(
        "simready:connectionPoint:" + suffix,
    ).Get()


def test_csv_inventory_types_units_and_choices(stage, generator):
    rows = generator.contract_rows()
    assert len(rows) == 59
    root = stage.GetDefaultPrim()
    assert {a.GetName() for a in root.GetAttributes() if a.GetName().startswith(PREFIX)} == {
        row["USD Attribute Namespace"] for row in rows
    }
    for row in rows:
        attr = root.GetAttribute(row["USD Attribute Namespace"])
        assert attr.GetTypeName() == generator.TYPES[row["Attribute Type"]]
        assert attr.HasAuthoredValueOpinion()
        assert attr.GetCustomDataByKey("units") == row["SI Unit Values"]
        assert row["Default Value"] == ""
        if row["Options"] != "Not required":
            options = row["Options"].split(" | ")
            assert list(attr.GetMetadata("allowedTokens")) == options
            entries = attr.Get() if row["Attribute Type"].endswith("_array") else [attr.Get()]
            assert all(entry in options for entry in entries)
    assert root.GetAttribute("aif:core:assetClass").Get() == "LiquidCooledChiller"
    assert len([a for a in root.GetAttributes() if a.GetName().startswith("aif:core:")]) == 16
    assert value(stage, "condenserType") == "LIQUID"
    assert not any("CondenserAir" in a.GetName() or "Fan" in a.GetName() for a in root.GetAttributes())
    for name in ("referenceEvaporatorLiquidVolumetricFlowRate_m3PerS",
                 "referenceCondenserLiquidEnteringTemperature_degC",
                 "evaporatorLeavingTemperatureSetpoint_degC", "chillerType"):
        assert not root.HasAttribute(PREFIX + name)


def test_liquid_map_reference_and_energy_balance(stage):
    source = json.loads((SAMPLE / "source.json").read_text())
    names = source["assumptions"]["cooling_grid_order"]
    assert names == ["EvaporatorLiquidVolumetricFlowRate_m3PerS", "EvaporatorLiquidLeavingTemperature_K",
                     "CondenserLiquidVolumetricFlowRate_m3PerS", "CondenserLiquidEnteringTemperature_K",
                     "CompressorSequenceNumber"]
    axes = [list(value(stage, "performanceMapCoolingGrid" + name)) for name in names]
    points = list(itertools.product(*axes))
    assert len(points) == 108
    outputs = {name: list(value(stage, "performanceMapCoolingLookup" + name)) for name in (
        "InputPower_W", "NetEvaporatorCapacity_W", "NetCondenserCapacity_W",
        "OilCoolerHeat_W", "AuxiliaryHeat_W", "OperationState",
    )}
    assert all(len(values) == len(points) for values in outputs.values())
    capacity = outputs["NetEvaporatorCapacity_W"]
    input_power = outputs["InputPower_W"]
    for index, (_evap_flow, _leaving, _cond_flow, _entering, sequence) in enumerate(points):
        assert outputs["NetCondenserCapacity_W"][index] == pytest.approx(capacity[index] + input_power[index])
        assert outputs["OilCoolerHeat_W"][index] == outputs["AuxiliaryHeat_W"][index] == 0
        assert outputs["OperationState"][index] == "NORMAL"
        if sequence == 1:
            # The following point uses both machines at the same water conditions.
            assert points[index + 1] == (*points[index][:-1], 2)
            assert 0 < capacity[index] < capacity[index + 1]
            assert 0 < input_power[index] < input_power[index + 1]
    index = value(stage, "referenceCoolingMapPointIndex")
    assert points[index] == pytest.approx([.024, 280.15, .028, 303.15, 2])
    for suffix, rating in (("InputPower_W", 90000.), ("NetEvaporatorCapacity_W", 500000.),
                           ("NetCondenserCapacity_W", 590000.)):
        assert outputs[suffix][index] == pytest.approx(rating)
        assert value(stage, "reference" + suffix) == pytest.approx(rating)
    assert value(stage, "referenceCOP") == pytest.approx(capacity[index] / input_power[index])
    # Equipment input at any map point must fit within the single physical AC feed.
    feed = cp(stage, "ElectricalInlet", "electrical:ratedPower")
    available = math.sqrt(3) * cp(stage, "ElectricalInlet", "electrical:nominalVoltage") * (
        cp(stage, "ElectricalInlet", "electrical:maxCurrent") * cp(stage, "ElectricalInlet", "electrical:powerFactor")
    )
    assert max(input_power) <= feed <= available
    assert value(stage, "evaporatorLeavingTemperatureSetpointMinimum_degC") == pytest.approx(axes[1][0] - 273.15, abs=1e-4)
    assert value(stage, "evaporatorLeavingTemperatureSetpointMaximum_degC") == pytest.approx(axes[1][-1] - 273.15, abs=1e-4)


@pytest.mark.parametrize(("circuit", "temperature_name", "flow", "pressure"), [
    ("Evaporator", "Leaving", .024, 35000), ("Condenser", "Entering", .028, 42000),
])
def test_both_pressure_maps_and_interface_pressure_drops(stage, circuit, temperature_name, flow, pressure):
    prefix = "performanceMap" + circuit + "LiquidPressureDifferential"
    flows = list(value(stage, prefix + "Grid" + circuit + "LiquidVolumetricFlowRate_m3PerS"))
    temperatures = list(value(stage, prefix + "Grid" + circuit + "Liquid" + temperature_name + "Temperature_K"))
    lookups = list(value(stage, prefix + "Lookup" + circuit + "LiquidDifferentialPressure_Pa"))
    assert len(lookups) == len(flows) * len(temperatures)
    for actual, (operating_flow, _temperature) in zip(lookups, itertools.product(flows, temperatures), strict=True):
        assert actual == pytest.approx(pressure * (operating_flow / flow) ** 2, abs=0.51)
    assert abs(cp(stage, circuit + "Supply", "thermal:operatingPressure")
               - cp(stage, circuit + "Return", "thermal:operatingPressure")) == pytest.approx(pressure)


def test_four_liquid_ports_and_electrical_inlet_have_physical_mating_frames(stage):
    source = json.loads((SAMPLE / "source.json").read_text())
    scope = stage.GetPrimAtPath("/world/ConnectionPoints")
    assert scope.GetTypeName() == "Scope" and len(scope.GetChildren()) == 5
    for name, item in source["ports"].items():
        port = stage.GetPrimAtPath("/world/ConnectionPoints/" + name)
        matrix = UsdGeom.Xformable(port).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        assert matrix.ExtractTranslation() == pytest.approx(item["position"])
        assert tuple(matrix[2][:3]) == pytest.approx(item["normal"])
        assert matrix.GetDeterminant() == pytest.approx(1)
        assert UsdGeom.Imageable(port).GetPurposeAttr().Get() == "guide"
        if name == "ElectricalInlet":
            plate = UsdGeom.Mesh(stage.GetPrimAtPath("/world/Geometry/ElectricalInletPlate"))
            assert item["position"][0] == pytest.approx(min(p[0] for p in plate.GetPointsAttr().Get()))
        else:
            flange = UsdGeom.Mesh(stage.GetPrimAtPath("/world/Geometry/" + name + "Flange"))
            assert item["position"][0] == pytest.approx(max(p[0] for p in flange.GetPointsAttr().Get()))
            bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]).ComputeLocalBound(flange.GetPrim()).ComputeAlignedRange()
            assert item["position"][1] == pytest.approx(bounds.GetMidpoint()[1])
            assert item["position"][2] == pytest.approx(bounds.GetMidpoint()[2])
            # One connected flange with a bore and eight through-holes has
            # genus nine. Check watertight edges as well as the Euler count.
            indices = list(flange.GetFaceVertexIndicesAttr().Get())
            counts = list(flange.GetFaceVertexCountsAttr().Get())
            offset, edges = 0, Counter()
            for count in counts:
                face = indices[offset:offset+count]
                offset += count
                for a, b in zip(face, face[1:]+face[:1], strict=True):
                    edges[tuple(sorted((a, b)))] += 1
            assert set(edges.values()) == {2}
            assert len(flange.GetPointsAttr().Get()) - len(edges) + len(counts) == 2 - 2*9
    for circuit, system, capacity, flow in (("Evaporator", "FWS", 500000., .024),
                                           ("Condenser", "equipment_cooling", 590000., .028)):
        for role in ("Supply", "Return"):
            name = circuit + role
            assert cp(stage, name, "system") == system
            assert cp(stage, name, "direction") == role.lower()
            assert cp(stage, name, "thermal:designFlowRate") / 1000 == pytest.approx(flow)
            assert cp(stage, name, "thermal:portDiameter") < value(stage, circuit.lower() + "NominalPipeOutsideDiameter_mm") / 1000
        delta_temperature = abs(cp(stage, circuit + "Supply", "thermal:designTemperature")
                                - cp(stage, circuit + "Return", "thermal:designTemperature"))
        assert flow * 1000 * 4180 * delta_temperature == pytest.approx(capacity, rel=1e-6)
    assert cp(stage, "EvaporatorSupply", "thermal:designTemperature") < cp(stage, "EvaporatorReturn", "thermal:designTemperature")
    assert cp(stage, "CondenserSupply", "thermal:designTemperature") < cp(stage, "CondenserReturn", "thermal:designTemperature")
    assert cp(stage, "ElectricalInlet", "electrical:ratedPower") > value(stage, "referenceInputPower_W")


def test_closed_mesh_mass_extents_materials_and_provenance(stage):
    root = stage.GetDefaultPrim()
    assert str(root.GetPath()) == "/world"
    assert UsdGeom.Xformable(root).GetLocalTransformation() == Gf.Matrix4d(1)
    assert UsdGeom.GetStageUpAxis(stage) == "Z"
    assert UsdGeom.GetStageMetersPerUnit(stage) == UsdPhysics.GetStageKilogramsPerUnit(stage) == 1
    meshes = [UsdGeom.Mesh(prim) for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
    names = {mesh.GetPrim().GetName() for mesh in meshes}
    assert {"EvaporatorShell", "CondenserShell"} <= names
    assert not any("Fan" in name for name in names)
    assert len([name for name in names if name.startswith("Compressor_") and name.endswith("_Shell")]) == value(stage, "numberOfCompressors") == 2
    materials = json.loads((SAMPLE / "source.json").read_text())["materials"]
    mass = 0
    for mesh in meshes:
        points = mesh.GetPointsAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        assert all(math.isfinite(coordinate) for point in points for coordinate in point)
        assert sum(counts) == len(indices)
        assert all(0 <= index < len(points) for index in indices)
        bound = UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()[0]
        assert bound
        offset, signed_volume = 0, 0
        for count in counts:
            face = indices[offset:offset + count]
            a = Gf.Vec3d(points[face[0]])
            for index in range(1, count - 1):
                b, c = Gf.Vec3d(points[face[index]]), Gf.Vec3d(points[face[index + 1]])
                signed_volume += Gf.Dot(a, Gf.Cross(b, c)) / 6
            offset += count
        volume = abs(signed_volume)
        assert volume == pytest.approx(mesh.GetPrim().GetCustomDataByKey("synthetic:solidVolume_m3"), rel=2e-4, abs=1e-8)
        mass += volume * materials[bound.GetPrim().GetName()]["density_kg_m3"]
    assert root.GetAttribute("aif:core:weight").Get() == pytest.approx(mass, rel=2e-4)
    assert UsdPhysics.MassAPI(root).GetMassAttr().Get() == pytest.approx(mass, rel=2e-4)
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]).ComputeWorldBound(root).ComputeAlignedRange()
    assert bounds.GetMin()[2] == pytest.approx(0)
    size = bounds.GetSize()
    assert not root.HasAttribute("aif:core:overallGeometryDimensions")
    physical_mm = [root.GetAttribute("aif:core:" + field).Get() for field in ("width", "depth", "height")]
    assert physical_mm == pytest.approx(tuple(v * 1000 for v in size))
    metadata = stage.GetRootLayer().customLayerData["SimReady_Metadata"]
    assert metadata["mass"] == pytest.approx(mass, rel=2e-4)
    assert metadata["asset_extents"] == pytest.approx(size)
    assert metadata["synthetic"] is True and metadata["asset_license"] == "CC-BY 4.0"
    assert "fictional" in root.GetAttribute("aif:core:assetDescription").Get().lower()


@pytest.mark.parametrize(("field", "new", "error"), [
    ("nominalVoltage_V", False, "Missing required chiller attributes"),
    ("performanceMapCondenserLiquidPressureDifferentialLookupCondenserLiquidDifferentialPressure_Pa", False, "Missing required chiller attributes"),
    ("undeclared", True, "Unknown chiller attributes"),
])
def test_generator_rejects_invalid_inventory(tmp_path, generator, field, new, error):
    source = generator.source_data()
    if new:
        source["attributes"][PREFIX + field] = 1
    else:
        del source["attributes"][PREFIX + field]
    with pytest.raises(ValueError, match=error):
        generator.properties_layer(tmp_path / "Properties.usda", source, 1, (1, 1, 1))


def test_generator_rejects_curve_fit_and_omits_unsupplied_optional_values(tmp_path, generator):
    source = generator.source_data()
    source["attributes"][PREFIX + "performanceModelType"] = "CURVE-FIT"
    with pytest.raises(ValueError, match="TABULAR"):
        generator.properties_layer(tmp_path / "Invalid.usda", source, 1, (1, 1, 1))
    source["attributes"][PREFIX + "performanceModelType"] = "TABULAR"
    del source["attributes"][PREFIX + "iplv_kWPerTon"]
    generator.properties_layer(tmp_path / "Optional.usda", source, 1, (1, 1, 1))
    stage = Usd.Stage.Open(str(tmp_path / "Optional.usda"))
    assert not stage.GetDefaultPrim().HasAttribute(PREFIX + "iplv_kWPerTon")


def test_relocation_and_deterministic_regeneration(tmp_path, generator):
    relocated = tmp_path / "relocated"
    shutil.copytree(SAMPLE / "asset", relocated / "asset")
    stage = Usd.Stage.Open(str(relocated / "asset/Synthetic_LiquidCooledChiller.usda"))
    assert stage and len(list(stage.GetPrimAtPath("/world/Geometry").GetChildren())) > 80
    generated = tmp_path / "generated"
    generator.generate(generated)
    for path in (SAMPLE / "asset").rglob("*.usda"):
        other = generated / "asset" / path.relative_to(SAMPLE / "asset")
        assert Sdf.Layer.FindOrOpen(str(path)).ExportToString() == Sdf.Layer.FindOrOpen(str(other)).ExportToString()

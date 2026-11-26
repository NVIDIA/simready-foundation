# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Read the published fictional chiller through native USD composition."""
import csv
import importlib.util
import itertools
import json
import math
from pathlib import Path
import shutil

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

REPO = Path(__file__).resolve().parents[4]
SAMPLE = REPO / "sample_content/aif/Synthetic_AirCooledChiller"
ASSET = SAMPLE / "asset/Synthetic_AirCooledChiller.usda"
CSV = REPO / "standards/equipment-classes/aif-v0.3/air-cooled-chiller.csv"
PREFIX = "aif:spec:"
REMOVED_ATTRIBUTES = {
    "evaporatorLeavingTemperatureSetpoint_degC",
    "referenceEvaporatorLiquidVolumetricFlowRate_m3PerS",
    "referenceEvaporatorLiquidLeavingTemperature_degC",
    "referenceCondenserAirEnteringDrybulbTemperature_degC",
    "referenceCondenserAirEnteringRelativeHumidity_1",
    "referenceCondenserAirVolumetricFlowRate_m3PerS",
    "referenceAmbientPressure_Pa",
    "referenceCompressorSequenceNumber",
    "referenceOperationState",
}


@pytest.fixture(scope="module")
def stage():
    result = Usd.Stage.Open(str(ASSET))
    assert result
    return result


@pytest.fixture(scope="module")
def generator():
    module_spec = importlib.util.spec_from_file_location("chiller_sample_generator", SAMPLE / "generate.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def value(stage, name):
    return stage.GetDefaultPrim().GetAttribute(PREFIX + name).Get()


def test_csv_inventory_types_units_and_choices(stage):
    with CSV.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 58
    expected_types = {"float":"float", "int":"int", "bool":"bool", "string":"string",
                      "token":"token", "float_array":"float[]", "int_array":"int[]", "token_array":"token[]"}
    root = stage.GetDefaultPrim()
    assert {a.GetName() for a in root.GetAttributes() if a.GetName().startswith(PREFIX)} == {r["USD Attribute Namespace"] for r in rows}
    model_type = root.GetAttribute(PREFIX + "performanceModelType")
    assert model_type.Get() == "TABULAR"
    assert list(model_type.GetMetadata("allowedTokens")) == ["TABULAR"]
    for row in rows:
        attr = root.GetAttribute(row["USD Attribute Namespace"])
        assert str(attr.GetTypeName()) == expected_types[row["Attribute Type"]]
        assert attr.HasAuthoredValueOpinion()
        assert attr.GetCustomDataByKey("units") == row["SI Unit Values"]
        assert row["Default Value"] == ""
        if row["Options"] != "Not required":
            choices = row["Options"].split(" | ")
            assert list(attr.GetMetadata("allowedTokens")) == choices
            values = attr.Get() if row["Attribute Type"].endswith("_array") else [attr.Get()]
            assert all(v in choices for v in values)
    assert len([a for a in root.GetAttributes() if a.GetName().startswith("aif:core:")]) == 16
    assert root.GetAttribute("aif:core:assetClass").Get() == "AirCooledChiller"
    source=json.loads((SAMPLE/"source.json").read_text())
    for name in REMOVED_ATTRIBUTES:
        assert not root.HasAttribute(PREFIX+name)
        assert PREFIX+name not in source["attributes"]
        assert all(PREFIX+name not in prim.attributes for layer in stage.GetUsedLayers()
                   for prim in layer.rootPrims)


def test_cooling_map_reference_and_energy_balance(stage):
    axis_names = ["EvaporatorLiquidVolumetricFlowRate_m3PerS", "EvaporatorLiquidLeavingTemperature_K",
                  "CondenserAirEnteringDrybulbTemperature_K", "CondenserAirEnteringRelativeHumidity",
                  "AmbientPressure_Pa", "CompressorSequenceNumber"]
    axes = [list(value(stage,"performanceMapCoolingGrid"+name)) for name in axis_names]
    points = list(itertools.product(*axes))
    assert len(points) == 32
    assert points[0][-1] == 1 and points[1][-1] == 2
    assert points[0] == pytest.approx([.004,280.15,303.15,.4,101325,1])
    outputs = {name:list(value(stage,"performanceMapCoolingLookup"+name)) for name in
               ["InputPower_W","NetEvaporatorCapacity_W","NetCondenserCapacity_W",
                "CondenserAirVolumetricFlowRate_m3PerS","OilCoolerHeat_W","AuxiliaryHeat_W","OperationState"]}
    assert all(len(v) == len(points) for v in outputs.values())
    for i,(flow,leaving,entering,_rh,_pressure,sequence) in enumerate(points):
        scale=(flow/.004)*(1+.01*(leaving-280.15))*(1-.005*(entering-303.15))*(1+.25*(sequence-1))
        cooling=100000*scale
        power=25000*scale*(1+.01*(entering-303.15))
        assert outputs["NetEvaporatorCapacity_W"][i] == pytest.approx(cooling,rel=2e-6)
        assert outputs["InputPower_W"][i] == pytest.approx(power,rel=2e-6)
        assert outputs["NetCondenserCapacity_W"][i] == pytest.approx(cooling+power,rel=2e-6)
        assert outputs["CondenserAirVolumetricFlowRate_m3PerS"][i] == pytest.approx(12*scale,rel=2e-6)
        assert outputs["OperationState"][i] == "NORMAL"
        assert outputs["OilCoolerHeat_W"][i] == outputs["AuxiliaryHeat_W"][i] == 0
    rating_index = value(stage, "referenceCoolingMapPointIndex")
    assert rating_index == 0
    for lookup,reference in [("InputPower_W","referenceInputPower_W"),("NetEvaporatorCapacity_W","referenceNetEvaporatorCapacity_W"),
                             ("NetCondenserCapacity_W","referenceNetCondenserCapacity_W")]:
        assert outputs[lookup][rating_index] == pytest.approx(value(stage,reference))
    assert value(stage,"referenceCOP") == pytest.approx(value(stage,"referenceNetEvaporatorCapacity_W")/value(stage,"referenceInputPower_W"))
    assert value(stage,"evaporatorLeavingTemperatureSetpointMinimum_degC") == pytest.approx(axes[1][0]-273.15)
    assert value(stage,"evaporatorLeavingTemperatureSetpointMaximum_degC") == pytest.approx(axes[1][-1]-273.15)


def test_ports_have_physical_faces_frames_and_unit_mappings(stage):
    scope=stage.GetPrimAtPath("/world/ConnectionPoints")
    assert scope.GetTypeName() == "Scope" and len(scope.GetChildren()) == 3
    source=json.loads((SAMPLE/"source.json").read_text())
    for name,item in source["ports"].items():
        port=stage.GetPrimAtPath("/world/ConnectionPoints/"+name)
        matrix=UsdGeom.Xformable(port).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        assert matrix.ExtractTranslation() == pytest.approx(item["position"])
        assert Gf.Vec3d(*matrix[2][:3]) == pytest.approx(item["normal"])
        assert matrix.GetDeterminant() == pytest.approx(1.0)
        assert UsdGeom.Imageable(port).GetPurposeAttr().Get() == "guide"
        for prop,(_type_name,expected) in item["properties"].items():
            actual=port.GetAttribute("simready:connectionPoint:"+prop).Get()
            assert actual == pytest.approx(expected) if isinstance(expected,(float,int)) else actual == expected
    supply=stage.GetPrimAtPath("/world/ConnectionPoints/EvaporatorSupply")
    operating_flow=supply.GetAttribute("simready:connectionPoint:thermal:designFlowRate").Get()/1000
    assert value(stage,"minimumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS")-1e-8 <= operating_flow
    assert operating_flow <= value(stage,"maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS")+1e-8
    assert supply.GetAttribute("simready:connectionPoint:thermal:maxFlowRate").Get() == pytest.approx(value(stage,"maximumOperatingEvaporatorLiquidVolumetricFlowRate_m3PerS")*1000)
    assert supply.GetAttribute("simready:connectionPoint:thermal:portDiameter").Get() < value(stage,"evaporatorNominalPipeOutsideDiameter_mm")/1000
    flange=UsdGeom.Mesh(stage.GetPrimAtPath("/world/Geometry/EvaporatorSupplyFlange"))
    flange_face=max(p[0] for p in flange.GetPointsAttr().Get())
    assert source["ports"]["EvaporatorSupply"]["position"][0] == pytest.approx(flange_face)


def test_geometry_counts_mass_extents_materials_and_provenance(stage):
    root=stage.GetDefaultPrim()
    assert str(root.GetPath()) == "/world"
    assert UsdGeom.Xformable(root).GetLocalTransformation() == Gf.Matrix4d(1)
    assert UsdGeom.GetStageUpAxis(stage) == "Z"
    assert UsdGeom.GetStageMetersPerUnit(stage) == UsdPhysics.GetStageKilogramsPerUnit(stage) == 1
    meshes=[UsdGeom.Mesh(p) for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]
    names={m.GetPrim().GetName() for m in meshes}
    assert len([n for n in names if n.endswith("_Shroud")]) == value(stage, "numberOfFans") == 4
    assert len([n for n in names if n.startswith("Compressor_") and n.endswith("_Shell")]) == value(stage,"numberOfCompressors") == 2
    materials=json.loads((SAMPLE/"source.json").read_text())["materials"]
    mass=0.0
    geometric_mass=0.0
    for mesh in meshes:
        points=mesh.GetPointsAttr().Get()
        indices=mesh.GetFaceVertexIndicesAttr().Get()
        counts=mesh.GetFaceVertexCountsAttr().Get()
        assert all(math.isfinite(c) for p in points for c in p)
        assert sum(counts) == len(indices)
        assert all(0<=i<len(points) for i in indices)
        material=UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()[0]
        assert material
        signed_volume=0.0
        offset=0
        for count in counts:
            face=indices[offset:offset+count]
            a=Gf.Vec3d(points[face[0]])
            for i in range(1,count-1):
                b,c=Gf.Vec3d(points[face[i]]),Gf.Vec3d(points[face[i+1]])
                signed_volume+=Gf.Dot(a,Gf.Cross(b,c))/6
            offset+=count
        volume=abs(signed_volume)
        assert volume == pytest.approx(mesh.GetPrim().GetCustomDataByKey("synthetic:solidVolume_m3"),rel=2e-4,abs=1e-8)
        geometric_mass+=volume*materials[material.GetPrim().GetName()]["density_kg_m3"]
        mass+=mesh.GetPrim().GetCustomDataByKey("synthetic:mass_kg")
    assert mass == pytest.approx(geometric_mass,rel=2e-4)
    assert root.GetAttribute("aif:core:weight").Get() == pytest.approx(mass)
    assert UsdPhysics.MassAPI(root).GetMassAttr().Get() == pytest.approx(mass)
    bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_]).ComputeWorldBound(root).ComputeAlignedRange()
    assert bounds.GetMin()[2] == pytest.approx(0.0)
    extents=bounds.GetSize()
    assert not root.HasProperty("aif:core:overallGeometryDimensions")
    dimensions = [root.GetAttribute(f"aif:core:{axis}").Get() for axis in ("width", "depth", "height")]
    assert dimensions == pytest.approx([v * 1000 for v in extents])
    metadata=stage.GetRootLayer().customLayerData["SimReady_Metadata"]
    assert metadata["mass"] == pytest.approx(mass)
    assert metadata["asset_extents"] == pytest.approx(extents)
    assert metadata["qcode"] == "Q1501558"
    assert metadata["synthetic"] is True and metadata["asset_license"] == "CC-BY 4.0"
    assert "fictional" in root.GetAttribute("aif:core:assetDescription").Get().lower()


def test_generator_preserves_source_without_optional_fields(tmp_path, generator):
    source = generator.source_data()
    omitted = {
        PREFIX + name for name in (
            "referenceCoolingMapPointIndex", "numberOfFans", "fanType",
            "maximumCondenserFanRotationalSpeed_Hz", "efficiencyRotatingEquipment",
            "refrigerantChargePerCircuit_kg",
        )
    }
    for name in omitted:
        del source["attributes"][name]
    path = tmp_path / "Properties.usda"
    generator.properties_layer(path, source, 1.0, (1.0, 1.0, 1.0))
    stage = Usd.Stage.Open(str(path))
    actual = {attr.GetName() for attr in stage.GetDefaultPrim().GetAttributes() if attr.GetName().startswith(PREFIX)}
    assert actual == set(source["attributes"])


@pytest.mark.parametrize(("field", "new_field", "error"), [
    ("nominalVoltage_V", False, "Missing required chiller attributes"),
    ("performanceMapCoolingLookupInputPower_W", False, "Missing required chiller attributes"),
    ("undeclared", True, "Unknown chiller attributes"),
])
def test_generator_rejects_invalid_attribute_inventory(tmp_path, generator, field, new_field, error):
    source = generator.source_data()
    if new_field:
        source["attributes"][PREFIX + field] = 1
    else:
        del source["attributes"][PREFIX + field]
    with pytest.raises(ValueError, match=error):
        generator.properties_layer(tmp_path / "Properties.usda", source, 1.0, (1.0, 1.0, 1.0))


def test_generator_rejects_non_tabular_model(tmp_path, generator):
    source = generator.source_data()
    source["attributes"][PREFIX + "performanceModelType"] = "CURVE-FIT"
    with pytest.raises(ValueError, match="TABULAR"):
        generator.properties_layer(tmp_path / "Properties.usda", source, 1.0, (1.0, 1.0, 1.0))


def test_package_relocates_and_generator_reproduces(tmp_path, generator):
    relocated=tmp_path/"relocated"
    shutil.copytree(SAMPLE/"asset",relocated/"asset")
    stage=Usd.Stage.Open(str(relocated/"asset/Synthetic_AirCooledChiller.usda"))
    assert stage and len(list(stage.GetPrimAtPath("/world/Geometry").GetChildren())) > 100
    assert not any(layer.anonymous for layer in stage.GetUsedLayers() if layer != stage.GetSessionLayer())
    generated=tmp_path/"generated"
    generator.generate(generated)
    for path in (SAMPLE/"asset").rglob("*.usda"):
        other=generated/"asset"/path.relative_to(SAMPLE/"asset")
        assert Sdf.Layer.FindOrOpen(str(path)).ExportToString() == Sdf.Layer.FindOrOpen(str(other)).ExportToString()

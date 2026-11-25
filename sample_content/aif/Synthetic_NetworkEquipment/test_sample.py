# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check relationships between source values, authored geometry and CSV contract."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil

import pytest
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, Vt

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("network_sample_generator", HERE / "generate.py")
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    destination = tmp_path_factory.mktemp("network_sample")
    generate.generate(destination)
    return destination


def _root_authored_bytes(path):
    """Remove only official validation stamps from an anonymous root copy."""
    layer = Sdf.Layer.CreateAnonymous("comparison.usda")
    layer.ImportFromString(path.read_text(encoding="utf-8"))
    paths = list(layer.subLayerPaths)
    layer.subLayerPaths = []  # Metadata comparison needs no child-layer resolution.
    stage = Usd.Stage.Open(layer)
    stage.ClearMetadataByDictKey("customLayerData", "SimReady_Metadata:validation")
    del stage
    layer.subLayerPaths = paths
    return layer.ExportToString().encode("utf-8")


def test_regeneration_matches_committed_layers(generated):
    for original in sorted((HERE / "asset").rglob("*.usda")):
        regenerated = generated / original.relative_to(HERE)
        if original.name == f"{generate.NAME}.usda":
            assert _root_authored_bytes(regenerated) == _root_authored_bytes(original), original
        else:
            assert regenerated.read_bytes() == original.read_bytes(), original
    assert (generated / "dcc_source/preview.usda").read_bytes() == (HERE / "dcc_source/preview.usda").read_bytes()


def test_sample_dimensions_and_mass_follow_geometry(generated):
    stage = Usd.Stage.Open(str(generated / "asset" / f"{generate.NAME}.usda"))
    root = stage.GetDefaultPrim()
    size = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"]).ComputeWorldBound(root).ComputeAlignedRange().GetSize()
    assert not root.GetAttribute("aif:core:overallGeometryDimensions")
    dimensions = stage.GetRootLayer().customLayerData["SimReady_Metadata"]["asset_extents"]
    for actual, authored in zip(size, dimensions, strict=True):
        assert actual == pytest.approx(authored, rel=1e-6)
    for axis, name in enumerate(("width", "depth", "height")):
        assert size[axis] * 1000 == pytest.approx(root.GetAttribute("aif:core:" + name).Get(), rel=1e-6)
    mass = sum(prim.GetCustomDataByKey("synthetic:mass_kg") or 0 for prim in stage.Traverse())
    assert mass == pytest.approx(root.GetAttribute("aif:core:weight").Get(), rel=1e-6)
    assert mass == pytest.approx(UsdPhysics.MassAPI(root).GetMassAttr().Get(), rel=1e-6)


def test_ports_match_openings_and_point_outward(generated):
    source = json.loads((HERE / "source.json").read_text())
    p = source["ports"]
    stage = Usd.Stage.Open(str(generated / "asset" / f"{generate.NAME}.usda"))
    scope = stage.GetDefaultPrim().GetChild("ConnectionPoints")
    ports = scope.GetChildren()
    assert len(ports) == p["count"] + 1
    for i in range(p["count"]):
        port = scope.GetChild(f"ethernet_{i+1:02}")
        transform = UsdGeom.Xformable(port).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        assert Gf.IsClose(transform.ExtractTranslation(), Gf.Vec3d(p["first_x_m"]+i*p["spacing_m"],p["front_y_m"],p["height_z_m"]),1e-7)
        assert Gf.IsClose(transform.TransformDir(Gf.Vec3d(0,0,1)),Gf.Vec3d(0,-1,0),1e-7)
        width = port.GetAttribute("simready:connectionPoint:network:portWidth").Get()
        height = port.GetAttribute("simready:connectionPoint:network:portHeight").Get()
        assert width == pytest.approx(p["opening_width_m"])
        assert height == pytest.approx(p["opening_height_m"])
        left = stage.GetPrimAtPath(f"{generate.ROOT}/Geometry/Port{i+1:02}Left")
        right = stage.GetPrimAtPath(f"{generate.ROOT}/Geometry/Port{i+1:02}Right")
        left_extent = UsdGeom.Mesh(left).GetExtentAttr().Get()
        right_extent = UsdGeom.Mesh(right).GetExtentAttr().Get()
        assert right_extent[0][0] - left_extent[1][0] == pytest.approx(width, abs=1e-7)


def test_relocated_asset_resolves_relative_layers(generated, tmp_path):
    relocated = tmp_path / "moved"
    shutil.copytree(generated, relocated)
    stage = Usd.Stage.Open(str(relocated / "asset" / f"{generate.NAME}.usda"))
    assert stage and stage.GetDefaultPrim()
    assert len(stage.GetUsedLayers()) == 5  # entry, three asset sublayers, session
    assert stage.GetPrimAtPath(generate.ROOT + "/Geometry/TopRear")
    assert stage.GetPrimAtPath(generate.ROOT + "/ConnectionPoints/ethernet_08")


def test_source_contract_drift_is_rejected(tmp_path, monkeypatch):
    altered = tmp_path / "altered.csv"
    with generate.CSV.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows, fields = list(reader), reader.fieldnames
    rows[0]["USD Attribute Namespace"] = "aif:core:unreviewedName"
    with altered.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(generate, "CSV", altered)
    with pytest.raises(ValueError, match="CSV/source attribute mismatch"):
        generate.generate(tmp_path / "invalid")


def test_component_identity_units_and_provenance(generated):
    path = generated / "asset" / f"{generate.NAME}.usda"
    stage = Usd.Stage.Open(str(path))
    root = stage.GetDefaultPrim()
    model = Usd.ModelAPI(root)
    source = json.loads((generated / "source.json").read_text())
    assert str(root.GetPath()) == generate.ROOT
    assert model.GetKind() == Kind.Tokens.component
    assert model.GetAssetName() == generate.NAME
    assert model.GetAssetVersion() == source["attributes"]["aif:core:assetVersion"]
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1
    assert UsdPhysics.GetStageKilogramsPerUnit(stage) == 1
    assert UsdGeom.GetStageUpAxis(stage) == "Z"
    metadata = stage.GetRootLayer().customLayerData["SimReady_Metadata"]
    provenance_source = (path.parent / metadata["source_file"]).resolve()
    assert provenance_source == (generated / "source.json").resolve()
    assert provenance_source.read_bytes() == (HERE / "source.json").read_bytes()
    assert root.GetAttribute("aif:core:connectsToModelDocumentation").Get() == generate.DOCUMENTATION
    assert root.GetAttribute("aif:core:assetValidatorVersion").Get() == source["asset_validator_version"]
    receipt = json.loads((HERE / "validation.json").read_text())
    assert source["asset_validator_version"] == "simready-validate " + receipt["package_versions"]["simready-validate"]
    assert "float mass =" in stage.GetRootLayer().ExportToString()


def test_density_weighted_mass_is_measured_from_meshes(generated):
    stage = Usd.Stage.Open(str(generated / "asset" / f"{generate.NAME}.usda"))
    source = json.loads((generated / "source.json").read_text())
    total = 0
    boxes = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        points = [Gf.Vec3d(value) for value in mesh.GetPointsAttr().Get()]
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        volume, offset = 0, 0
        for count in mesh.GetFaceVertexCountsAttr().Get():
            face = indices[offset:offset+count]
            offset += count
            for i in range(1, count-1):
                volume += Gf.Dot(points[face[0]], Gf.Cross(points[face[i]], points[face[i+1]])) / 6
        assert volume > 0
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        assert material
        density = source["materials"][material.GetPrim().GetName()]["density_kg_m3"]
        measured = volume * density
        assert measured == pytest.approx(prim.GetCustomDataByKey("synthetic:mass_kg"), rel=1e-5, abs=1e-9)
        total += measured
        boxes.append((str(prim.GetPath()), UsdGeom.BBoxCache(
            Usd.TimeCode.Default(), ["default"]).ComputeWorldBound(prim).ComputeAlignedRange()))
    assert total == pytest.approx(stage.GetDefaultPrim().GetAttribute("aif:core:weight").Get(), rel=1e-6)
    # The authored solids are disjoint, including LED cutouts and the first port's web.
    for index, (left_name, left) in enumerate(boxes):
        for right_name, right in boxes[index+1:]:
            overlap = [min(left.GetMax()[axis], right.GetMax()[axis])
                       - max(left.GetMin()[axis], right.GetMin()[axis]) for axis in range(3)]
            assert min(overlap) <= 1e-7, (left_name, right_name, overlap)


def test_every_port_frame_and_mating_depth_matches_geometry(generated):
    stage = Usd.Stage.Open(str(generated / "asset" / f"{generate.NAME}.usda"))
    scope = stage.GetDefaultPrim().GetChild("ConnectionPoints")
    for index, port in enumerate(scope.GetChildren()):
        tag = "Management" if port.GetName() == "management_01" else f"Port{index+1:02}"
        bounds = {side: UsdGeom.Mesh(stage.GetPrimAtPath(
            f"{generate.ROOT}/Geometry/{tag}{side}")).GetExtentAttr().Get()
                  for side in ("Left", "Right", "Lower", "Upper", "Back")}
        transform = UsdGeom.Xformable(port).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        center = transform.ExtractTranslation()
        width = bounds["Right"][0][0] - bounds["Left"][1][0]
        height = bounds["Upper"][0][2] - bounds["Lower"][1][2]
        depth = bounds["Back"][0][1] - center[1]
        prefix = "simready:connectionPoint:network:"
        assert port.GetAttribute(prefix+"portWidth").Get() == pytest.approx(width, abs=1e-7)
        assert port.GetAttribute(prefix+"portHeight").Get() == pytest.approx(height, abs=1e-7)
        assert port.GetAttribute(prefix+"matingDepth").Get() == pytest.approx(depth, abs=1e-7)
        assert center[0] == pytest.approx((bounds["Right"][0][0]+bounds["Left"][1][0])/2, abs=1e-7)
        assert center[2] == pytest.approx((bounds["Upper"][0][2]+bounds["Lower"][1][2])/2, abs=1e-7)
        assert center[1] == pytest.approx(bounds["Left"][0][1], abs=1e-7)
        assert Gf.IsClose(transform.TransformDir(Gf.Vec3d(0,0,1)), Gf.Vec3d(0,-1,0), 1e-7)
        assert Gf.IsClose(transform.TransformDir(Gf.Vec3d(0,1,0)), Gf.Vec3d(0,0,1), 1e-7)


def test_source_dimension_disagreement_is_rejected(tmp_path, monkeypatch):
    source = json.loads((HERE / "source.json").read_text())
    source["attributes"]["aif:core:height"] *= 2
    (tmp_path / "source.json").write_text(json.dumps(source))
    monkeypatch.setattr(generate, "HERE", tmp_path)
    with pytest.raises(ValueError, match="Source height=.*disagrees with generated geometry"):
        generate.generate(tmp_path / "invalid-dimensions")


def test_root_comparison_ignores_only_official_validation_stamp(generated, tmp_path):
    path = generated / "asset" / f"{generate.NAME}.usda"
    before = _root_authored_bytes(path)
    layer = Sdf.Layer.CreateAnonymous("stamped.usda")
    layer.ImportFromString(path.read_text())
    layer.subLayerPaths = []
    stage = Usd.Stage.Open(layer)
    stage.SetMetadataByDictKey("customLayerData", "SimReady_Metadata:validation",
                              {"profile": "Networking", "profile_version": "0.3.0"})
    del stage
    original_layer = Sdf.Layer.FindOrOpen(str(path))
    paths = list(original_layer.subLayerPaths)
    layer.subLayerPaths = paths
    stamped = tmp_path / "stamped.usda"
    layer.Export(str(stamped))
    assert _root_authored_bytes(stamped) == before
    layer.subLayerPaths = []
    stage = Usd.Stage.Open(layer)
    stage.SetMetadataByDictKey("customLayerData", "SimReady_Metadata:mass", Vt.Float(99))
    del stage
    layer.subLayerPaths = paths
    layer.Export(str(stamped))
    assert _root_authored_bytes(stamped) != before


def test_output_carries_declared_root_and_authoring_stage(generated):
    relative = Path("asset/.metadata/com.nvidia.simready.root_usds.json")
    assert (generated / relative).read_bytes() == (HERE / relative).read_bytes()
    tracking = json.loads((generated / relative).read_text())
    assert tracking["format_version"] == "1.0"
    assert tracking["entries"] == [f"{generate.NAME}.usda"]
    assert not (generated / "preview.usda").exists()
    preview = Usd.Stage.Open(str(generated / "dcc_source/preview.usda"))
    assert preview.GetPrimAtPath("/Presentation/Switch/Geometry/TopRear")

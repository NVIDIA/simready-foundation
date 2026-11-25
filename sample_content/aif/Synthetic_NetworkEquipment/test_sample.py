# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check relationships between source values, authored geometry and CSV contract."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil

import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("network_sample_generator", HERE / "generate.py")
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    destination = tmp_path_factory.mktemp("network_sample")
    generate.generate(destination)
    return destination


def test_regeneration_matches_committed_layers(generated):
    for original in sorted((HERE / "asset").rglob("*.usda")):
        regenerated = generated / original.relative_to(HERE)
        assert regenerated.read_bytes() == original.read_bytes(), original
    assert (generated / "preview.usda").read_bytes() == (HERE / "preview.usda").read_bytes()


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
        left = stage.GetPrimAtPath(f"/world/Geometry/Port{i+1:02}Left")
        right = stage.GetPrimAtPath(f"/world/Geometry/Port{i+1:02}Right")
        left_extent = UsdGeom.Mesh(left).GetExtentAttr().Get()
        right_extent = UsdGeom.Mesh(right).GetExtentAttr().Get()
        assert right_extent[0][0] - left_extent[1][0] == pytest.approx(width, abs=1e-7)


def test_relocated_asset_resolves_relative_layers(generated, tmp_path):
    relocated = tmp_path / "moved"
    shutil.copytree(generated, relocated)
    stage = Usd.Stage.Open(str(relocated / "asset" / f"{generate.NAME}.usda"))
    assert stage and stage.GetDefaultPrim()
    assert len(stage.GetUsedLayers()) == 5  # entry, three asset sublayers, session
    assert stage.GetPrimAtPath("/world/Geometry/TopRear")
    assert stage.GetPrimAtPath("/world/ConnectionPoints/ethernet_08")


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

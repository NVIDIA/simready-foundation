# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Networking capability checks using the registered validation engine."""
import json
from pathlib import Path
import tomllib

import pytest
from pxr import Sdf, Usd, UsdGeom

from _harness import assert_no_failures, assert_rule_fires
from simready.foundation.tier_aif.rules_and_reqs.aif import equipment_classes


@pytest.fixture(scope="module", autouse=True)
def registered_network_rules():
    # Other profile-test modules destroy the shared registry at teardown.
    import simready.validate as sv

    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield
    sv.destroy()


@pytest.fixture
def network_asset(tmp_path):
    properties = Usd.Stage.CreateNew(str(tmp_path / "Network_Properties.usda"))
    root = UsdGeom.Xform.Define(properties, "/Network").GetPrim()
    properties.SetDefaultPrim(root)
    values = {
        "assetClass": (Sdf.ValueTypeNames.String, "network-equipment"),
        "manufacturer": (Sdf.ValueTypeNames.String, "Synthetic"),
        "modelNumber": (Sdf.ValueTypeNames.String, "NET-TEST"),
        "assetVersion": (Sdf.ValueTypeNames.String, "0.1.0"),
        "width": (Sdf.ValueTypeNames.Float, 440.),
        "height": (Sdf.ValueTypeNames.Float, 44.),
        "depth": (Sdf.ValueTypeNames.Float, 600.),
        "weight": (Sdf.ValueTypeNames.Float, 12.),
        "installationClearance": (Sdf.ValueTypeNames.Float, 0.),
        "accessibilityRequirement": (Sdf.ValueTypeNames.Float, 1000.),
    }
    for name, (kind, value) in values.items():
        root.CreateAttribute("aif:core:" + name, kind).Set(value)
    for name, value in (("cpuAllocation", 2), ("memory_MB", 4096), ("storage_GB", 20)):
        root.CreateAttribute("aif:spec:" + name, Sdf.ValueTypeNames.Int).Set(value)
    root.CreateAttribute("aif:spec:osImage", Sdf.ValueTypeNames.String).Set("synthetic://test-image")
    properties.GetRootLayer().Save()
    stage = Usd.Stage.CreateNew(str(tmp_path / "Network.usda"))
    stage.GetRootLayer().subLayerPaths = ["Network_Properties.usda"]
    stage.SetDefaultPrim(stage.GetPrimAtPath("/Network"))
    UsdGeom.Scope.Define(stage, "/Network/ConnectionPoints")
    port = UsdGeom.Xform.Define(stage, "/Network/ConnectionPoints/Port01").GetPrim()
    port.CreateAttribute("simready:connectionPoint:domain", Sdf.ValueTypeNames.Token).Set("network")
    stage.GetRootLayer().Save()
    return stage, properties


def _save(asset):
    for stage in asset:
        stage.GetRootLayer().Save()
    return Path(asset[0].GetRootLayer().realPath)


def test_positive_typed_contract(network_asset):
    assert_no_failures(_save(network_asset), ["NET.001", "NET.002", "NET.003"])


def test_optional_image_may_be_absent(network_asset):
    network_asset[1].GetDefaultPrim().RemoveProperty("aif:spec:osImage")
    assert_no_failures(_save(network_asset), ["NET.002"])


@pytest.mark.parametrize("name,kind,value,requirement", [
    ("aif:core:manufacturer", Sdf.ValueTypeNames.String, "  ", "NET.001"),
    ("aif:core:height", Sdf.ValueTypeNames.Float, float("nan"), "NET.001"),
    ("aif:core:width", Sdf.ValueTypeNames.Float, -1., "NET.001"),
    ("aif:core:depth", Sdf.ValueTypeNames.Double, 600., "NET.001"),
    ("aif:core:weight", Sdf.ValueTypeNames.Float, 0., "NET.001"),
    ("aif:core:installationClearance", Sdf.ValueTypeNames.Float, -1., "NET.001"),
    ("aif:spec:cpuAllocation", Sdf.ValueTypeNames.Float, 2., "NET.002"),
    ("aif:spec:memory_MB", Sdf.ValueTypeNames.Int, 0, "NET.002"),
    ("aif:spec:storage_GB", Sdf.ValueTypeNames.Int, -1, "NET.002"),
    ("aif:spec:osImage", Sdf.ValueTypeNames.String, "", "NET.002"),
    ("aif:spec:osImage", Sdf.ValueTypeNames.Token, "image", "NET.002"),
])
def test_invalid_metadata_rejected(network_asset, name, kind, value, requirement):
    prim = network_asset[1].GetDefaultPrim()
    prim.RemoveProperty(name)
    prim.CreateAttribute(name, kind).Set(value)
    assert_rule_fires(_save(network_asset), requirement)


@pytest.mark.parametrize("name,requirement", [
    ("aif:core:modelNumber", "NET.001"),
    ("aif:core:accessibilityRequirement", "NET.001"),
    ("aif:spec:cpuAllocation", "NET.002"),
    ("aif:spec:memory_MB", "NET.002"),
    ("aif:spec:storage_GB", "NET.002"),
])
def test_missing_required_properties_rejected(network_asset, name, requirement):
    network_asset[1].GetDefaultPrim().RemoveProperty(name)
    assert_rule_fires(_save(network_asset), requirement)


def test_stronger_layer_invalid_override_rejected(network_asset):
    network_asset[0].GetDefaultPrim().GetAttribute("aif:spec:memory_MB").Set(0)
    assert_rule_fires(_save(network_asset), "NET.002")


def test_root_only_value_cannot_replace_properties_contract(network_asset):
    name = "aif:spec:cpuAllocation"
    network_asset[1].GetDefaultPrim().RemoveProperty(name)
    network_asset[0].GetDefaultPrim().CreateAttribute(name, Sdf.ValueTypeNames.Int).Set(2)
    assert_rule_fires(_save(network_asset), "NET.002")


@pytest.mark.parametrize("mutation", ["missing", "wrong_domain", "wrong_type", "nested"])
def test_network_port_required(network_asset, mutation):
    stage = network_asset[0]
    path = "/Network/ConnectionPoints/Port01"
    if mutation == "missing":
        stage.RemovePrim(path)
    elif mutation == "wrong_domain":
        stage.GetPrimAtPath(path).GetAttribute("simready:connectionPoint:domain").Set("thermal")
    elif mutation == "wrong_type":
        stage.GetPrimAtPath(path).SetTypeName("Scope")
    else:
        stage.RemovePrim(path)
        UsdGeom.Scope.Define(stage, "/Network/ConnectionPoints/Group")
        port = UsdGeom.Xform.Define(stage, "/Network/ConnectionPoints/Group/Port01").GetPrim()
        port.CreateAttribute("simready:connectionPoint:domain", Sdf.ValueTypeNames.Token).Set("network")
    assert_rule_fires(_save(network_asset), "NET.003")


def test_class_registration_is_aif03_only():
    assert equipment_classes.normalize("network-equipment") is None
    assert equipment_classes.normalize_03("network-equipment") == "network-equipment"
    for token in ("cdu", "compute-rack", "crah", "ups", "gb300"):
        assert equipment_classes.normalize(token) == equipment_classes.normalize_03(token)
    assert "network-equipment" not in equipment_classes.ATTRIBUTES
    assert "network-equipment" not in equipment_classes.AC_CLASSES
    assert "network-equipment" not in equipment_classes.THERMAL_CLASSES
    assert equipment_classes.ATTRIBUTES_03["network-equipment"] == {
        "aif:spec:cpuAllocation", "aif:spec:memory_MB", "aif:spec:storage_GB"
    }


def test_only_aif03_selects_network_contract():
    root = Path(__file__).parents[1] / "simready/foundation/tier_aif"
    profile = tomllib.loads((root / "profiles/aif_entity.toml").read_text())
    assert not (root / "profiles/aif_network_equipment.toml").exists()
    selected = profile["AIF-Entity"]["0.3.0"]
    assert "CAP204_Networking.0-3-0" in {x["selector"] for x in selected["capabilities"]}
    manifest = json.loads((root / "capabilities/CAP204_Networking.0-3-0.json").read_text())
    assert manifest["requirements"] == ["NET.001", "NET.002", "NET.003"]
    assert manifest["dependencies"] == ["CAP200_AifMetadata.0-3-0", "CAP201_ConnectionPoints.0-3-0"]
    for version in ("0.1.0", "0.2.0"):
        assert all("CAP204" not in entry["selector"]
                   for entry in profile["AIF-Entity"][version]["capabilities"])


def test_legacy_template_rejects_legacy_shaped_network_equipment(network_asset):
    root = network_asset[1].GetDefaultPrim()
    root.CreateAttribute("aif:core:overallGeometryDimensions", Sdf.ValueTypeNames.Float3).Set((440., 600., 44.))
    path = _save(network_asset)
    # All seven legacy physical properties and required network properties exist.
    assert_no_failures(path, ["AM.004", "AM.008"])
    assert_rule_fires(path, "AM.007")
    assert_rule_fires(path, "AM.009")


@pytest.mark.parametrize("asset_class", ["cdu", "crah", "ups", "compute-rack"])
def test_network_rules_skip_preexisting_classes(network_asset, asset_class):
    network_asset[1].GetDefaultPrim().GetAttribute("aif:core:assetClass").Set(asset_class)
    network_asset[1].GetDefaultPrim().RemoveProperty("aif:spec:cpuAllocation")
    network_asset[0].RemovePrim("/Network/ConnectionPoints")
    assert_no_failures(_save(network_asset), ["AM.008", "AM.009", "NET.001", "NET.002", "NET.003"])


@pytest.mark.parametrize("properties_class,composed_class", [
    ("network-equipment", "compute-rack"),
    ("compute-rack", "network-equipment"),
])
def test_mismatched_composed_class_cannot_bypass_network_checks(network_asset, properties_class, composed_class):
    network_asset[1].GetDefaultPrim().GetAttribute("aif:core:assetClass").Set(properties_class)
    network_asset[0].GetDefaultPrim().GetAttribute("aif:core:assetClass").Set(composed_class)
    assert_rule_fires(_save(network_asset), "NET.001")


def test_aif03_rejects_unknown_equipment(network_asset):
    network_asset[1].GetDefaultPrim().GetAttribute("aif:core:assetClass").Set("unknown-network-type")
    assert_rule_fires(_save(network_asset), "AM.008")


@pytest.mark.parametrize("layer", ["properties", "root"])
def test_optional_image_relationship_is_rejected(network_asset, layer):
    network_asset[1].GetDefaultPrim().RemoveProperty("aif:spec:osImage")
    stage = network_asset[1 if layer == "properties" else 0]
    stage.GetDefaultPrim().CreateRelationship("aif:spec:osImage")
    assert_rule_fires(_save(network_asset), "NET.002")

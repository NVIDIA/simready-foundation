# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AIF 0.3 validates common equipment metadata types and inherits class templates."""

import pytest
from pxr import Sdf, Usd, UsdGeom

from _harness import assert_no_failures, assert_rule_does_not_report, assert_rule_fires, assert_rule_reports
from simready.foundation.tier_aif.rules_and_reqs.aif import equipment_classes


LEGACY_CLASSES = ("cdu", "compute-rack", "crah", "ups")


def make_properties_asset(tmp_path, asset_class, complete):
    """Supply only what the two equipment-template rules consume."""
    props_path = tmp_path / "Asset_Properties.usda"
    props = Usd.Stage.CreateNew(str(props_path))
    root = UsdGeom.Xform.Define(props, "/Asset").GetPrim()
    props.SetDefaultPrim(root)
    root.CreateAttribute("aif:core:assetClass", Sdf.ValueTypeNames.String).Set(asset_class)
    required = sorted(equipment_classes.ATTRIBUTES[asset_class])
    for name in required if complete else required[1:]:
        root.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("presence-only fixture")
    props.GetRootLayer().Save()
    path = tmp_path / "Asset.usda"
    stage = Usd.Stage.CreateNew(str(path))
    stage.GetRootLayer().subLayerPaths = [props_path.name]
    stage.SetDefaultPrim(stage.GetPrimAtPath("/Asset"))
    stage.GetRootLayer().Save()
    return path


@pytest.mark.parametrize("asset_class", LEGACY_CLASSES)
@pytest.mark.parametrize("complete", [True, False], ids=["complete", "missing-attribute"])
def test_preexisting_class_template_expectations_are_carried_forward(tmp_path, asset_class, complete):
    path = make_properties_asset(tmp_path, asset_class, complete)
    assert_no_failures(path, ["AM.007", "AM.008"])
    for code in ("AM.007", "AM.008"):
        if complete:
            assert_rule_does_not_report(path, code, "WARNING")
        else:
            assert_rule_reports(path, code, "WARNING")


@pytest.mark.parametrize(
    "name,wrong_type",
    [
        ("aif:core:assetClass", Sdf.ValueTypeNames.Token),
        ("aif:core:assetDescription", Sdf.ValueTypeNames.Token),
        ("aif:core:connectsToModelDocumentation", Sdf.ValueTypeNames.Token),
        ("aif:core:simreadyVersion", Sdf.ValueTypeNames.Token),
        ("aif:core:manufacturer", Sdf.ValueTypeNames.Token),
        ("aif:core:modelNumber", Sdf.ValueTypeNames.Token),
        ("aif:core:assetVersion", Sdf.ValueTypeNames.Token),
        ("aif:core:height", Sdf.ValueTypeNames.Double),
        ("aif:core:width", Sdf.ValueTypeNames.Double),
        ("aif:core:depth", Sdf.ValueTypeNames.Double),
        ("aif:core:weight", Sdf.ValueTypeNames.Double),
        ("aif:core:installationClearance", Sdf.ValueTypeNames.Double),
        ("aif:core:accessibilityRequirement", Sdf.ValueTypeNames.Double),
    ],
)
def test_aif03_requires_exact_usd_types(tmp_path, name, wrong_type):
    path = make_properties_asset(tmp_path, "compute-rack", complete=True)
    props = Usd.Stage.Open(str(tmp_path / "Asset_Properties.usda"))
    root = props.GetDefaultPrim()
    root.RemoveProperty(name)
    attr = root.CreateAttribute(name, wrong_type)
    if name == "aif:core:assetClass":
        attr.Set("compute-rack")
    props.GetRootLayer().Save()
    assert_no_failures(path, ["AM.007"])
    assert_rule_fires(path, "AM.008")


def test_aif03_requires_attributes_for_common_metadata(tmp_path):
    path = make_properties_asset(tmp_path, "compute-rack", complete=True)
    props = Usd.Stage.Open(str(tmp_path / "Asset_Properties.usda"))
    props.GetDefaultPrim().CreateRelationship("aif:core:manufacturer")
    props.GetRootLayer().Save()
    assert_rule_fires(path, "AM.008")


@pytest.mark.parametrize(
    "name,value,layer_type,composed_type",
    [
        ("aif:core:height", 42.0, Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Double),
        ("aif:core:height", 42.0, Sdf.ValueTypeNames.Double, Sdf.ValueTypeNames.Float),
    ],
    ids=["stronger-wrong-type", "stronger-masks-wrong-type"],
)
def test_aif03_checks_layer_and_composed_types_on_existing_class(tmp_path, name, value, layer_type, composed_type):
    path = make_properties_asset(tmp_path, "compute-rack", complete=True)
    stage = Usd.Stage.Open(str(path))
    root = stage.GetDefaultPrim()
    assert_no_failures(path, ["AM.007", "AM.008"])
    assert_rule_does_not_report(path, "AM.008", "WARNING")
    props = stage.GetLayerStack()[-1]
    with Usd.EditContext(stage, props):
        root.CreateAttribute(name, layer_type).Set(value)
    props.Save()

    root_spec = Sdf.CreatePrimInLayer(stage.GetRootLayer(), root.GetPath())
    Sdf.AttributeSpec(root_spec, name, composed_type).default = value
    stage.GetRootLayer().Save()
    assert root.GetAttribute(name).GetTypeName() == composed_type
    assert_no_failures(path, ["AM.007"])
    assert_rule_fires(path, "AM.008")


DIMENSION_SCALARS = ("width", "depth", "height", "weight", "installationClearance", "accessibilityRequirement")
RETIRED_DIMENSIONS = "aif:core:overallGeometryDimensions"


@pytest.fixture
def scalar_dimensions_asset(tmp_path):
    path = make_properties_asset(tmp_path, "compute-rack", complete=True)
    props = Usd.Stage.Open(str(tmp_path / "Asset_Properties.usda"))
    for name in DIMENSION_SCALARS:
        props.GetDefaultPrim().CreateAttribute(f"aif:core:{name}", Sdf.ValueTypeNames.Float).Set(1.0)
    props.GetRootLayer().Save()
    return path, props


@pytest.mark.parametrize("name", DIMENSION_SCALARS)
def test_aif03_requires_each_dimension_scalar(scalar_dimensions_asset, name):
    path, props = scalar_dimensions_asset
    assert_no_failures(path, ["AM.009"])
    assert props.GetDefaultPrim().RemoveProperty(f"aif:core:{name}")
    props.GetRootLayer().Save()
    assert_rule_fires(path, "AM.009")


@pytest.mark.parametrize("layer", ["properties", "root"])
@pytest.mark.parametrize("kind", ["float3", "relationship"])
def test_aif03_rejects_retired_dimensions_declarations(scalar_dimensions_asset, layer, kind):
    path, props = scalar_dimensions_asset
    stage = props if layer == "properties" else Usd.Stage.Open(str(path))
    root = stage.GetDefaultPrim()
    if kind == "float3":
        root.CreateAttribute(RETIRED_DIMENSIONS, Sdf.ValueTypeNames.Float3)
    else:
        root.CreateRelationship(RETIRED_DIMENSIONS)
    stage.GetRootLayer().Save()
    assert_no_failures(path, ["AM.008"])
    assert_rule_fires(path, "AM.009")

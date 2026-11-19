# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""In-place conformance chain behavior."""

from __future__ import annotations

import pytest
from metadata_fixtures import (
    COMPLETE_METADATA,
    add_unanchored_reference,
    read_simready_metadata,
    write_metadata_package,
    write_png,
)
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from simready.metadata_conform import conform_package
from simready.metadata_conform.conform import (
    CODE_METADATA_INCOMPLETE,
    CODE_PHYSICAL_EVIDENCE_MISSING,
    CODE_PHYSICAL_VALUE_REJECTED,
    CODE_THUMBNAIL_MISSING,
)


def _codes(outcome) -> set[str]:
    return {blocker.code for blocker in outcome.blockers}


def _complete_package(root):
    asset = write_metadata_package(root)
    write_png(asset.parent / ".thumbs" / f"{asset.name}.png")
    return asset


def test_conforms_a_complete_package(tmp_path):
    asset = _complete_package(tmp_path / "asset")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert outcome.ok, outcome.blockers
    stamped = read_simready_metadata(asset)
    assert stamped["author"] == "Asset Team"
    assert stamped["rigid_body_count"] == 1
    assert stamped["mass"] == pytest.approx(2.5)
    assert stamped["qcode"] == "Q42177"
    assert len(stamped["asset_extents"]) == 3


def test_derives_physical_fields_from_the_stage(tmp_path):
    asset = _complete_package(tmp_path / "asset")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    for name in ("rigid_body_count", "asset_extents", "mass"):
        assert outcome.field_sources[name] == "derived"
    extents = outcome.resolved_metadata["asset_extents"]
    assert [round(float(item), 6) for item in extents] == [1.0, 1.0, 1.0]


@pytest.mark.parametrize("arc", ["reference", "sublayer", "payload"])
def test_rejects_external_layers_before_any_path_edits(tmp_path, arc):
    from simready.metadata_conform.core.paths import repair_simple_asset_paths, ExternalLayerError

    package = tmp_path / "staged"
    asset = _complete_package(package)
    external = Usd.Stage.CreateNew(str(tmp_path / "shared.usda"))
    prim = UsdGeom.Xform.Define(external, "/Shared").GetPrim()
    external.SetDefaultPrim(prim)
    prim.CreateAttribute("texture", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath("texture.png"))
    external.GetRootLayer().Save()
    write_png(package / "texture.png")
    stage = Usd.Stage.Open(str(asset))
    if arc == "sublayer":
        stage.GetRootLayer().subLayerPaths.append(external.GetRootLayer().identifier)
    elif arc == "reference":
        stage.OverridePrim("/Shared").GetReferences().AddReference(external.GetRootLayer().identifier)
    else:
        stage.OverridePrim("/Shared").GetPayloads().AddPayload(external.GetRootLayer().identifier)
    stage.GetDefaultPrim().CreateAttribute("texture", Sdf.ValueTypeNames.Asset).Set(
        Sdf.AssetPath("texture.png")
    )
    stage.GetRootLayer().Save()
    before = {path: path.read_bytes() for path in (asset, tmp_path / "shared.usda")}

    with pytest.raises(ExternalLayerError):
        repair_simple_asset_paths(asset, package)
    outcome = conform_package(asset, package_root=package, metadata=dict(COMPLETE_METADATA))
    assert "EXTERNAL_LAYER" in _codes(outcome)
    assert not outcome.path_repairs
    for path, data in before.items():
        assert path.read_bytes() == data
    assert prim.GetAttribute("texture").Get().path == "texture.png"


@pytest.mark.parametrize("kilograms_per_unit, authored_mass", [(0.001, 2500), (1.0, 2.5), (1000, 0.0025)])
def test_converts_mass_and_density_to_kilograms(tmp_path, kilograms_per_unit, authored_mass):
    asset = write_metadata_package(tmp_path / "asset", mass=authored_mass)
    write_png(asset.parent / ".thumbs" / f"{asset.name}.png")
    stage = Usd.Stage.Open(str(asset))
    UsdPhysics.SetStageKilogramsPerUnit(stage, kilograms_per_unit)
    stage.GetRootLayer().Save()

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert outcome.ok, outcome.blockers
    assert read_simready_metadata(asset)["mass"] == pytest.approx(2.5)
    report = outcome.derivation["mass_check"]
    assert report["total_mass_kg"] == pytest.approx(2.5)
    assert report["bodies"][0]["mass"] == pytest.approx(2.5)
    assert report["implied_density_kg_m3"] == pytest.approx(15)
    assert report["bodies"][0]["implied_density"] == pytest.approx(15)


def test_rejects_caller_supplied_physical_values(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    before = read_simready_metadata(asset)

    outcome = conform_package(
        asset, metadata={**COMPLETE_METADATA, "mass": 999.0}
    )

    assert CODE_PHYSICAL_VALUE_REJECTED in _codes(outcome)
    # Rejected before any write, so nothing was stamped.
    assert read_simready_metadata(asset) == before


def test_missing_physical_evidence_is_a_blocker(tmp_path):
    asset = write_metadata_package(tmp_path / "asset", mass=None)
    write_png(asset.parent / ".thumbs" / f"{asset.name}.png")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert CODE_PHYSICAL_EVIDENCE_MISSING in _codes(outcome)
    blocker = next(
        item
        for item in outcome.blockers
        if item.code == CODE_PHYSICAL_EVIDENCE_MISSING
    )
    assert "mass" in blocker.paths
    assert "mass" not in read_simready_metadata(asset)


def test_missing_provenance_strings_are_named(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    partial = {
        key: value
        for key, value in COMPLETE_METADATA.items()
        if key not in {"author", "category"}
    }

    outcome = conform_package(asset, metadata=partial)

    blocker = next(
        item for item in outcome.blockers if item.code == CODE_METADATA_INCOMPLETE
    )
    assert set(blocker.paths) == {"author", "category"}
    # Everything resolvable is still stamped, so a rerun only needs the gaps.
    assert read_simready_metadata(asset)["asset_name"] == "sm_test_prop_01"


def test_missing_thumbnail_is_a_blocker(tmp_path):
    asset = write_metadata_package(tmp_path / "asset")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert CODE_THUMBNAIL_MISSING in _codes(outcome)


def test_repairs_unanchored_authored_reference(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    add_unanchored_reference(asset)

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert outcome.ok, outcome.blockers
    assert len(outcome.path_repairs) == 1
    repair = outcome.path_repairs[0]
    assert repair["original"] == "part_01.usda"
    assert repair["replacement"] == "parts/part_01.usda"
    layer = Sdf.Layer.FindOrOpen(str(asset))
    prim_spec = layer.GetPrimAtPath("/RootNode/Part")
    assert prim_spec.referenceList.explicitItems[0].assetPath == "parts/part_01.usda"


def test_mutation_audit_records_geometry_and_physics_stability(tmp_path):
    asset = _complete_package(tmp_path / "asset")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    audit = outcome.mutation_audit
    assert audit["passed"]
    assert audit["before_digest"] == audit["after_digest"]


def test_existing_nested_metadata_supplies_missing_strings(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    layer = Sdf.Layer.FindOrOpen(str(asset))
    layer.customLayerData = {
        "SimReady_Metadata": {"author": "Prior Author", "category": "prior"}
    }
    layer.Save()
    del layer

    partial = {
        key: value
        for key, value in COMPLETE_METADATA.items()
        if key not in {"author", "category"}
    }
    outcome = conform_package(asset, metadata=partial)

    assert outcome.ok, outcome.blockers
    assert outcome.field_sources["author"] == "existing"
    assert outcome.resolved_metadata["author"] == "Prior Author"


def test_top_level_layer_keys_are_promoted(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    layer = Sdf.Layer.FindOrOpen(str(asset))
    layer.customLayerData = {"author": "Layer Author", "category": "layer"}
    layer.Save()
    del layer

    partial = {
        key: value
        for key, value in COMPLETE_METADATA.items()
        if key not in {"author", "category"}
    }
    outcome = conform_package(asset, metadata=partial)

    assert outcome.ok, outcome.blockers
    assert outcome.field_sources["author"] == "existing_layer"


def test_sr_001_identity_is_also_authored_at_the_top_level(tmp_path):
    """SR.001 will not flatten SimReady_Metadata, so identity lives in both."""
    asset = _complete_package(tmp_path / "asset")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert outcome.ok, outcome.blockers
    layer = Sdf.Layer.FindOrOpen(str(asset))
    custom = dict(layer.customLayerData)
    assert "SimReady_Metadata" in custom
    nested = read_simready_metadata(asset)
    for field in ("asset_name", "asset_type", "source_file", "usd_date_generated"):
        assert custom[field] == nested[field]


def test_only_the_sr_001_identity_fields_are_lifted(tmp_path):
    """Lifting more than SR.001 asks for would author claims twice over."""
    asset = _complete_package(tmp_path / "asset")

    conform_package(asset, metadata=dict(COMPLETE_METADATA))

    layer = Sdf.Layer.FindOrOpen(str(asset))
    custom = dict(layer.customLayerData)
    for field in ("author", "asset_license", "category", "qcode", "mass"):
        assert field not in custom


def test_top_level_identity_survives_a_rerun(tmp_path):
    """A second conform pass must not read its own lift as a rival source."""
    asset = _complete_package(tmp_path / "asset")

    conform_package(asset, metadata=dict(COMPLETE_METADATA))
    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert outcome.ok, outcome.blockers
    layer = Sdf.Layer.FindOrOpen(str(asset))
    custom = dict(layer.customLayerData)
    assert custom["asset_name"] == "sm_test_prop_01"
    assert read_simready_metadata(asset)["asset_name"] == "sm_test_prop_01"


def test_package_sidecar_json_supplies_missing_strings(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    (asset.parent / "simready_metadata.json").write_text(
        '{"SimReady_Metadata": {"author": "Sidecar Author", "category": "sidecar"}}',
        encoding="utf-8",
    )

    partial = {
        key: value
        for key, value in COMPLETE_METADATA.items()
        if key not in {"author", "category"}
    }
    outcome = conform_package(asset, metadata=partial)

    assert outcome.ok, outcome.blockers
    assert outcome.field_sources["author"] == "sidecar"
    assert outcome.resolved_metadata["author"] == "Sidecar Author"


def test_request_wins_over_every_other_source(tmp_path):
    asset = _complete_package(tmp_path / "asset")
    (asset.parent / "simready_metadata.json").write_text(
        '{"author": "Sidecar Author"}', encoding="utf-8"
    )

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    assert outcome.field_sources["author"] == "request"
    assert outcome.resolved_metadata["author"] == "Asset Team"


def test_invalid_qcode_in_request_falls_back_to_derived(tmp_path):
    asset = _complete_package(tmp_path / "asset")

    outcome = conform_package(
        asset, metadata={**COMPLETE_METADATA, "qcode": "not-a-qcode"}
    )

    assert outcome.ok, outcome.blockers
    assert outcome.field_sources["qcode"] == "derived"
    assert outcome.resolved_metadata["qcode"] == "Q42177"


def test_missing_qcode_everywhere_is_a_blocker(tmp_path):
    asset = write_metadata_package(tmp_path / "asset", qcode=None)
    write_png(asset.parent / ".thumbs" / f"{asset.name}.png")

    outcome = conform_package(asset, metadata=dict(COMPLETE_METADATA))

    blocker = next(
        item for item in outcome.blockers if item.code == CODE_METADATA_INCOMPLETE
    )
    assert blocker.paths == ("qcode",)

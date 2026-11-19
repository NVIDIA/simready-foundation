# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Public API: request validation, staging, and transactional promotion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from metadata_fixtures import (
    COMPLETE_METADATA,
    add_unanchored_reference,
    read_simready_metadata,
    write_metadata_package,
    write_png,
)

from simready.metadata_conform import (
    MetadataConformRequest,
    PROTOCOL_VERSION,
    run_metadata_conform,
)
from simready.metadata_conform.api import (
    CODE_OUTPUT_EXISTS,
    CODE_OUTPUT_IS_SOURCE,
    CODE_OUTPUT_NOT_DIRECTORY,
    CODE_SOURCE_NOT_FOUND,
    CODE_SOURCE_NOT_USD,
    STAGE_REQUEST,
)
from simready.metadata_conform.conform import CODE_THUMBNAIL_MISSING


def _codes(result) -> set[str]:
    return {error.code for error in result.errors}


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _source_package(root: Path):
    asset = write_metadata_package(root)
    write_png(asset.parent / ".thumbs" / f"{asset.name}.png")
    return asset


def test_conforms_and_promotes_a_package(tmp_path):
    asset = _source_package(tmp_path / "source")
    output = tmp_path / "dest" / "simready_usd"

    result = run_metadata_conform(asset, output, metadata=dict(COMPLETE_METADATA))

    assert result.ok, [error.to_dict() for error in result.errors]
    assert result.output_usd == str(output / asset.name)
    assert Path(result.output_usd).is_file()
    assert (output / ".thumbs" / "256x256" / f"{asset.name}.png").is_file()
    assert read_simready_metadata(output / asset.name)["author"] == "Asset Team"
    assert result.elapsed_s >= 0.0


def test_never_mutates_the_source_package(tmp_path):
    source_root = tmp_path / "source"
    asset = _source_package(source_root)
    add_unanchored_reference(asset)
    before = _tree_digest(source_root)

    result = run_metadata_conform(
        asset, tmp_path / "dest" / "simready_usd", metadata=dict(COMPLETE_METADATA)
    )

    assert result.ok, [error.to_dict() for error in result.errors]
    assert _tree_digest(source_root) == before


def test_external_layer_blocks_promotion_and_preserves_shared_source(tmp_path):
    from pxr import Sdf, Usd, UsdGeom

    source_root = tmp_path / "source"
    asset = _source_package(source_root)
    external_path = tmp_path / "shared.usda"
    external = Usd.Stage.CreateNew(str(external_path))
    prim = UsdGeom.Xform.Define(external, "/Shared").GetPrim()
    external.SetDefaultPrim(prim)
    prim.CreateAttribute("texture", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath("texture.png"))
    external.GetRootLayer().Save()
    write_png(asset.parent / "texture.png")
    stage = Usd.Stage.Open(str(asset))
    stage.OverridePrim("/Shared").GetReferences().AddReference(str(external_path))
    stage.GetRootLayer().Save()
    before = _tree_digest(source_root)
    shared_before = external_path.read_bytes()
    output = tmp_path / "dest" / "simready_usd"

    result = run_metadata_conform(asset, output, metadata=dict(COMPLETE_METADATA))

    assert not result.ok
    assert "EXTERNAL_LAYER" in _codes(result)
    assert not output.exists()
    assert _tree_digest(source_root) == before
    assert external_path.read_bytes() == shared_before


def test_rejects_a_non_usd_source(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("not usd", encoding="utf-8")

    result = run_metadata_conform(source, tmp_path / "dest")

    assert CODE_SOURCE_NOT_USD in _codes(result)
    assert result.errors[0].stage == STAGE_REQUEST


def test_rejects_a_missing_source(tmp_path):
    result = run_metadata_conform(tmp_path / "gone.usda", tmp_path / "dest")

    assert CODE_SOURCE_NOT_FOUND in _codes(result)


def test_rejects_output_equal_to_the_source_package(tmp_path):
    asset = _source_package(tmp_path / "source")

    result = run_metadata_conform(asset, asset.parent)

    assert CODE_OUTPUT_IS_SOURCE in _codes(result)


def test_rejects_an_existing_output_without_replace_existing(tmp_path):
    asset = _source_package(tmp_path / "source")
    output = tmp_path / "dest" / "simready_usd"
    output.mkdir(parents=True)

    result = run_metadata_conform(asset, output, metadata=dict(COMPLETE_METADATA))

    assert CODE_OUTPUT_EXISTS in _codes(result)


def test_rejects_an_output_path_that_is_a_file(tmp_path):
    asset = _source_package(tmp_path / "source")
    output = tmp_path / "dest"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("occupied", encoding="utf-8")

    result = run_metadata_conform(asset, output)

    assert CODE_OUTPUT_NOT_DIRECTORY in _codes(result)


def test_replaces_an_existing_output_transactionally(tmp_path):
    asset = _source_package(tmp_path / "source")
    output = tmp_path / "dest" / "simready_usd"
    output.mkdir(parents=True)
    (output / "stale.txt").write_text("stale", encoding="utf-8")

    result = run_metadata_conform(
        asset, output, metadata=dict(COMPLETE_METADATA), replace_existing=True
    )

    assert result.ok, [error.to_dict() for error in result.errors]
    assert result.replaced_existing
    assert not (output / "stale.txt").exists()
    assert (output / asset.name).is_file()
    # No staging or backup residue is left beside the promoted output.
    residue = [
        item.name
        for item in output.parent.iterdir()
        if item.name.startswith((".metadata_stage_", ".simready_usd.backup_"))
    ]
    assert residue == []


def test_failure_leaves_a_pre_existing_output_untouched(tmp_path):
    # No thumbnail anywhere, so conformance blocks before promotion.
    asset = write_metadata_package(tmp_path / "source")
    output = tmp_path / "dest" / "simready_usd"
    output.mkdir(parents=True)
    (output / "previous.txt").write_text("previous", encoding="utf-8")
    before = _tree_digest(output)

    result = run_metadata_conform(
        asset, output, metadata=dict(COMPLETE_METADATA), replace_existing=True
    )

    assert not result.ok
    assert CODE_THUMBNAIL_MISSING in _codes(result)
    assert _tree_digest(output) == before


def test_failure_preserves_staging_in_the_diagnostics_directory(tmp_path):
    asset = write_metadata_package(tmp_path / "source")
    diagnostics = tmp_path / "dest" / ".diagnostics"

    result = run_metadata_conform(
        asset,
        tmp_path / "dest" / "simready_usd",
        metadata=dict(COMPLETE_METADATA),
        diagnostics_dir=diagnostics,
    )

    assert not result.ok
    preserved = Path(result.diagnostics_path)
    assert preserved.is_dir()
    assert (preserved / "package" / asset.name).is_file()


def test_writes_a_json_report_on_success_and_failure(tmp_path):
    asset = _source_package(tmp_path / "source")
    report = tmp_path / "reports" / "metadata.json"

    result = run_metadata_conform(
        asset,
        tmp_path / "dest" / "simready_usd",
        metadata=dict(COMPLETE_METADATA),
        report_path=report,
    )

    assert result.ok, [error.to_dict() for error in result.errors]
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert payload["resolved_metadata"]["author"] == "Asset Team"
    assert payload["mutation_audit"]["passed"] is True

    failing_report = tmp_path / "reports" / "failed.json"
    failure = run_metadata_conform(
        write_metadata_package(tmp_path / "source2"),
        tmp_path / "dest2" / "simready_usd",
        metadata=dict(COMPLETE_METADATA),
        report_path=failing_report,
    )
    assert not failure.ok
    failed_payload = json.loads(failing_report.read_text(encoding="utf-8"))
    assert failed_payload["ok"] is False
    assert failed_payload["errors"]


def test_report_is_json_encodable_for_usd_scalars(tmp_path):
    asset = _source_package(tmp_path / "source")

    result = run_metadata_conform(
        asset, tmp_path / "dest" / "simready_usd", metadata=dict(COMPLETE_METADATA)
    )

    # asset_extents is a Gf.Vec3f once stamped; the payload must still encode.
    encoded = json.dumps(result.to_dict())
    assert "asset_extents" in encoded


def test_explicit_thumbnail_source_is_installed(tmp_path):
    asset = write_metadata_package(tmp_path / "source")
    external = write_png(tmp_path / "renders" / "beauty.png")
    output = tmp_path / "dest" / "simready_usd"

    result = run_metadata_conform(
        asset,
        output,
        metadata=dict(COMPLETE_METADATA),
        thumbnail_source=external,
    )

    assert result.ok, [error.to_dict() for error in result.errors]
    assert result.thumbnail["status"] == "provided"
    target = output / ".thumbs" / "256x256" / f"{asset.name}.png"
    assert target.read_bytes() == external.read_bytes()


def test_request_from_dict_round_trip():
    request = MetadataConformRequest.from_dict(
        {
            "protocol_version": PROTOCOL_VERSION,
            "source_usd": "a/b.usda",
            "output_folder": "c/d",
            "metadata": {"author": "Team"},
            "thumbnail_source": "e/f.png",
            "replace_existing": True,
            "report_path": "g/report.json",
            "diagnostics_dir": "h",
        }
    )

    assert request.source_usd == Path("a/b.usda")
    assert request.metadata == {"author": "Team"}
    assert request.thumbnail_source == Path("e/f.png")
    assert request.replace_existing is True


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"source_usd": "a.usda"},
        {"source_usd": "", "output_folder": "out"},
        {"source_usd": "a.usda", "output_folder": "out", "replace_existing": "yes"},
        {"source_usd": "a.usda", "output_folder": "out", "metadata": "nope"},
        {"source_usd": "a.usda", "output_folder": "out", "thumbnail_source": ""},
    ],
)
def test_request_from_dict_rejects_malformed_payloads(payload):
    with pytest.raises(ValueError):
        MetadataConformRequest.from_dict(payload)

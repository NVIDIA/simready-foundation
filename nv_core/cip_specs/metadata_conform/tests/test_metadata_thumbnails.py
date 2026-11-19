# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""SR.002 thumbnail discovery, ranking, and explicit installation.

The regression cases here come from a real Blender-authored package: the add-on
writes ``<name>_<variant>.usd.png`` into ``.thumbs/`` and copies it into
``.thumbs/256x256/``, and the asset it belongs to is renamed to ``.usda`` when
the Isaac interface layer is composed. Without the alternate-suffix tier and the
canonical-directory tiebreak, that package reports two equally ranked candidates
and blocks.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from metadata_fixtures import corrupt_png, write_png

from simready.metadata_conform.core.thumbnails import (
    STATUS_AMBIGUOUS,
    STATUS_INVALID,
    STATUS_MISSING,
    STATUS_PROVIDED,
    STATUS_RETAINED,
    STATUS_SELECTED,
    ExistingThumbnailProvider,
    ExplicitThumbnailProvider,
    discover_candidates,
    is_valid_png,
    normalize_thumbnail,
    target_path,
)

ASSET_NAME = "sm_prop_01.usda"


def _package(root: Path) -> Path:
    """Create an NP.005 shaped package and return its (empty) root USD path."""
    usd_dir = root / "simready_usd"
    usd_dir.mkdir(parents=True, exist_ok=True)
    asset = usd_dir / ASSET_NAME
    asset.write_text("#usda 1.0\n", encoding="utf-8")
    return asset


def test_target_path_is_the_exact_sr_002_location(tmp_path):
    asset = _package(tmp_path)

    target = target_path(asset)

    assert target == asset.parent / ".thumbs" / "256x256" / f"{ASSET_NAME}.png"


def test_is_valid_png_accepts_a_well_formed_file(tmp_path):
    assert is_valid_png(write_png(tmp_path / "good.png"))


def test_is_valid_png_rejects_a_bad_crc(tmp_path):
    assert not is_valid_png(corrupt_png(tmp_path / "bad.png"))


def test_is_valid_png_rejects_a_non_png(tmp_path):
    path = tmp_path / "not.png"
    path.write_bytes(b"just bytes")

    assert not is_valid_png(path)


def test_existing_target_is_retained(tmp_path):
    asset = _package(tmp_path)
    target = target_path(asset)
    write_png(target)
    original = target.read_bytes()

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_RETAINED
    assert result.ok
    assert target.read_bytes() == original


def test_no_png_at_all_is_missing(tmp_path):
    asset = _package(tmp_path)

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_MISSING
    assert not result.ok


def test_exact_asset_filename_is_selected(tmp_path):
    asset = _package(tmp_path)
    source = write_png(asset.parent / ".thumbs" / f"{ASSET_NAME}.png")

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_SELECTED
    assert result.selected == source.resolve()
    assert target_path(asset).read_bytes() == source.read_bytes()


def test_blender_usd_suffix_name_is_recognized_for_a_usda_asset(tmp_path):
    """`sm_prop_01.usd.png` is the thumbnail for `sm_prop_01.usda`."""
    asset = _package(tmp_path)
    source = write_png(asset.parent / ".thumbs" / "sm_prop_01.usd.png")

    candidates = discover_candidates(asset)
    result = ExistingThumbnailProvider().provide(asset)

    assert candidates[0].score == 850
    assert candidates[0].reason == "asset stem with alternate USD suffix"
    assert result.status == STATUS_SELECTED
    assert target_path(asset).read_bytes() == source.read_bytes()


def test_blender_thumbs_pair_resolves_via_the_canonical_directory(tmp_path):
    """The add-on writes the same name into .thumbs/ and .thumbs/256x256/."""
    asset = _package(tmp_path)
    sibling = write_png(asset.parent / ".thumbs" / "sm_prop_01.usd.png", value=10)
    canonical = write_png(
        asset.parent / ".thumbs" / "256x256" / "sm_prop_01.usd.png", value=200
    )

    candidates = discover_candidates(asset)
    result = ExistingThumbnailProvider().provide(asset)

    tied = [item for item in candidates if item.score == candidates[0].score]
    assert {item.path for item in tied} == {sibling.resolve(), canonical.resolve()}
    assert result.status == STATUS_SELECTED
    assert result.selected == canonical.resolve()
    assert target_path(asset).read_bytes() == canonical.read_bytes()


def test_genuine_tie_outside_the_canonical_directory_is_ambiguous(tmp_path):
    asset = _package(tmp_path)
    write_png(asset.parent / ".thumbs" / "left.png")
    write_png(asset.parent / ".thumbs" / "right.png")

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_AMBIGUOUS
    assert not result.ok
    assert not target_path(asset).exists()


def test_two_canonical_candidates_stay_ambiguous(tmp_path):
    asset = _package(tmp_path)
    write_png(asset.parent / ".thumbs" / "256x256" / "left.png")
    write_png(asset.parent / ".thumbs" / "256x256" / "right.png")

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_AMBIGUOUS


def test_unrecognized_package_png_is_not_promoted(tmp_path):
    asset = _package(tmp_path)
    write_png(tmp_path / "textures" / "albedo.png")

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_MISSING
    assert result.reason == "no recognized thumbnail naming or location"


def test_invalid_pngs_are_never_candidates(tmp_path):
    asset = _package(tmp_path)
    corrupt_png(asset.parent / ".thumbs" / f"{ASSET_NAME}.png")

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_MISSING


def test_explicit_source_is_installed_at_the_target(tmp_path):
    asset = _package(tmp_path)
    external = write_png(tmp_path / "renders" / "anything.png", value=77)

    result = ExplicitThumbnailProvider(external).provide(asset)

    assert result.status == STATUS_PROVIDED
    assert result.ok
    assert target_path(asset).read_bytes() == external.read_bytes()


def test_explicit_source_beats_a_conflicting_discovery(tmp_path):
    """An ambiguous package still conforms when the caller names the file."""
    asset = _package(tmp_path)
    write_png(asset.parent / ".thumbs" / "left.png")
    write_png(asset.parent / ".thumbs" / "right.png")
    external = write_png(tmp_path / "renders" / "chosen.png", value=42)

    result = normalize_thumbnail(asset, thumbnail_source=external)

    assert result.status == STATUS_PROVIDED
    assert target_path(asset).read_bytes() == external.read_bytes()


def test_explicit_source_already_at_the_target_is_retained(tmp_path):
    asset = _package(tmp_path)
    target = write_png(target_path(asset))

    result = ExplicitThumbnailProvider(target).provide(asset)

    assert result.status == STATUS_RETAINED


def test_explicit_source_that_is_missing_blocks(tmp_path):
    asset = _package(tmp_path)

    result = ExplicitThumbnailProvider(tmp_path / "gone.png").provide(asset)

    assert result.status == STATUS_MISSING
    assert not result.ok


def test_explicit_source_that_is_not_a_png_blocks(tmp_path):
    asset = _package(tmp_path)
    broken = corrupt_png(tmp_path / "renders" / "broken.png")

    result = ExplicitThumbnailProvider(broken).provide(asset)

    assert result.status == STATUS_INVALID
    assert not result.ok
    assert not target_path(asset).exists()


def test_writing_the_target_does_not_write_through_a_hardlink(tmp_path):
    """A staged package hardlinks non-USD payload; the source must not change."""
    asset = _package(tmp_path)
    original = write_png(tmp_path / "original" / "thumb.png", value=11)
    target = target_path(asset)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(original, target)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("filesystem does not support hardlinks")
    corrupt_png(target)  # target is now invalid, so it loses candidate status
    replacement = write_png(asset.parent / ".thumbs" / f"{ASSET_NAME}.png", value=222)

    result = ExistingThumbnailProvider().provide(asset)

    assert result.status == STATUS_SELECTED
    assert target.read_bytes() == replacement.read_bytes()
    assert original.read_bytes() != replacement.read_bytes()


def test_candidate_evidence_is_reported(tmp_path):
    asset = _package(tmp_path)
    write_png(asset.parent / ".thumbs" / "256x256" / "sm_prop_01.usd.png")

    result = ExistingThumbnailProvider().provide(asset)
    payload = result.to_dict()

    assert payload["status"] == STATUS_SELECTED
    assert payload["candidates"][0]["preferred"] is True
    assert payload["candidates"][0]["score"] == 850

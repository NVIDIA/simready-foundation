"""Tests for SR.002 — thumbnail existence for SimReady assets.

Validates via the ``Package-Candidate`` profile, which now includes
FET033_SIMREADY_PACKAGING (SR.002 thumbnail requirement).  The
``ThumbnailExists`` checker fires during ``CheckStage`` for every USD
file validated in pre-validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TESTDATA_DIR = Path(__file__).resolve().parent / "testdata"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_minimal_usda(path: Path) -> None:
    """Write a minimal valid USDA file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '#usda 1.0\n(\n    defaultPrim = "Root"\n)\n\ndef Xform "Root"\n{\n}\n'
    )


def _create_thumbnail(usd_path: Path) -> Path:
    """Create a 1-byte PNG placeholder at the expected thumbnail path."""
    thumb_dir = usd_path.parent / ".thumbs" / "256x256"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb = thumb_dir / f"{usd_path.name}.png"
    thumb.write_bytes(b"\x89PNG")
    return thumb


# ---------------------------------------------------------------------------
# CheckStage tests (pre-validation path via Package-Candidate / FET033)
# ---------------------------------------------------------------------------

class TestThumbnailExistsStageChecker:
    """Tests for the per-USD CheckStage validator (SR.002)."""

    def test_pass_with_thumbnail(self, tmp_path: Path) -> None:
        """A USD file with a thumbnail at the correct path should pass SR.002."""
        import simready.validate as sv

        usd = tmp_path / "asset.usda"
        _create_minimal_usda(usd)
        _create_thumbnail(usd)

        config = sv.AssetValidationConfig(
            asset_path=str(usd),
            profile_id="Package-Candidate",
            profile_version="1.0.0",
        )
        results = sv.validate_asset_list([config])
        assert len(results) == 1
        result = results[0]
        assert result is not None

        features = result.features_summary
        assert "FET033_SIMREADY_PACKAGING" in features
        feat = features["FET033_SIMREADY_PACKAGING"]
        failing = feat.get("failing requirements", "")
        assert "SR.002" not in str(failing), (
            f"SR.002 should not fail when thumbnail exists: {failing}"
        )

    def test_fail_without_thumbnail(self, tmp_path: Path) -> None:
        """A USD file without a thumbnail should fail SR.002."""
        import simready.validate as sv

        usd = tmp_path / "asset.usda"
        _create_minimal_usda(usd)

        config = sv.AssetValidationConfig(
            asset_path=str(usd),
            profile_id="Package-Candidate",
            profile_version="1.0.0",
        )
        results = sv.validate_asset_list([config])
        assert len(results) == 1
        result = results[0]
        assert result is not None

        features = result.features_summary
        assert "FET033_SIMREADY_PACKAGING" in features
        feat = features["FET033_SIMREADY_PACKAGING"]
        assert not feat.get("passed"), (
            "FET033 should fail when thumbnail is missing"
        )
        failing = feat.get("failing requirements", "")
        assert "SR.002" in str(failing), (
            f"SR.002 should be in failing requirements: {failing}"
        )

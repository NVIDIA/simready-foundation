"""Tests for the committed sample packages under ``simple_packages/``.

Validates each sample package against the ``Package`` profile at the
package level (via :func:`sr_pkg_sample.post_validation.post_validate`)
and, where applicable, against the ``Prop-Robotics-Neutral`` profile at
the asset level (via :func:`simready.validate.validate_asset`).

The committed samples cover the packaging feature matrix:

* ``apple_a01_nobom`` — minimal package, no BOM.  FET030 passes, FET032
  fails (no BOM).
* ``apple_a01_usd_bom`` — single USD dir with BOM + SHA-256 hashes.
  Both packaging features pass.
* ``apple_a01_usd_bom_multi_hash`` — same content as ``apple_a01_usd_bom``,
  but every hash object carries both ``sha256`` and ``blake3`` (the
  default output of ``create_simready_package.py``).  Both packaging
  features pass.
* ``fruit_f01_multi_usd`` — two USD dirs (apple_a01 + orange_a01
  simready_usd).  Both are AA.001-clean, so all packaging features pass.
* ``apple_a01_materials`` — no USD files (material library).  Both
  packaging features pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import simready.validate as sv
from sr_pkg_sample import PostValidationResult, ValidationFailed
from sr_pkg_sample.post_validation import post_validate

PACKAGE_DEF_NAME = "com.nvidia.simready.packaging.json"
ROOT_USDS_FILENAME = "com.nvidia.simready.root_usds.json"

NEUTRAL_PASS = {
    "FET000_CORE",
    "FET001_BASE_NEUTRAL",
    "FET003_BASE_NEUTRAL",
    "FET005_BASE_NEUTRAL",
}


@pytest.fixture(scope="session")
def simple_packages_dir(foundations_dir: Path) -> Path:
    d = (
        foundations_dir
        / "sample_content"
        / "packaging"
        / "simple_packages"
    )
    if not d.is_dir():
        pytest.skip(f"simple_packages directory missing: {d}")
    return d


def _pkg_def(simple_packages_dir: Path, name: str) -> Path:
    p = simple_packages_dir / name / PACKAGE_DEF_NAME
    if not p.is_file():
        pytest.skip(f"Package definition missing: {p}")
    return p


def _passed_features(result: sv.AssetValidationResult | None) -> set[str]:
    if result is None:
        return set()
    return {
        fid
        for fid, data in result.features_summary.items()
        if data.get("passed")
    }


def _discover_root_usds(pkg_dir: Path) -> list[str]:
    metadata = pkg_dir / ".metadata" / ROOT_USDS_FILENAME
    if metadata.is_file():
        data = json.loads(metadata.read_text())
        entries = data.get("entries", [])
        if entries:
            return sorted(entries)
    return sorted(
        str(p.relative_to(pkg_dir)).replace("\\", "/")
        for p in pkg_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in (".usd", ".usda", ".usdc")
    )


# ---------------------------------------------------------------------------
# Package-level tests (Package profile)
# ---------------------------------------------------------------------------

class TestNoBomPackage:
    """``apple_a01_nobom`` — minimal, no BOM."""

    async def test_package_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """FET030 passes (valid def, clean USD), FET032 fails (no BOM)."""
        pkg_def = _pkg_def(simple_packages_dir, "apple_a01_nobom")
        with pytest.raises(ValidationFailed) as exc_info:
            await post_validate(pkg_def)

        assert "FET032_PACKAGING_INTROSPECTION" in exc_info.value.failures

        result = exc_info.value.result
        assert isinstance(result, PostValidationResult)
        pkg_results = result.results.get("Package", [])
        assert pkg_results
        _rel, engine_result = pkg_results[0]
        assert engine_result is not None
        assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
        assert not engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]

    async def test_asset_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Single USD passes Prop-Robotics-Neutral."""
        pkg_dir = simple_packages_dir / "apple_a01_nobom"
        assets = _discover_root_usds(pkg_dir)
        assert assets == ["apple_a01/simready_usd/sm_apple_a01_01.usd"]

        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str((pkg_dir / assets[0]).resolve()),
            profile_id="Prop-Robotics-Neutral",
            profile_version="1.0.0",
        ))
        assert _passed_features(result) == NEUTRAL_PASS


class TestUsdBomPackage:
    """``apple_a01_usd_bom`` — single USD with BOM + full hashes."""

    async def test_package_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Both packaging features pass."""
        pkg_def = _pkg_def(simple_packages_dir, "apple_a01_usd_bom")
        result = await post_validate(pkg_def)

        assert result.passed
        pkg_results = result.results.get("Package", [])
        assert pkg_results
        _rel, engine_result = pkg_results[0]
        assert engine_result is not None
        assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
        assert engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]

    async def test_asset_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Single USD passes Prop-Robotics-Neutral."""
        pkg_dir = simple_packages_dir / "apple_a01_usd_bom"
        assets = _discover_root_usds(pkg_dir)
        assert assets == ["apple_a01/simready_usd/sm_apple_a01_01.usd"]

        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str((pkg_dir / assets[0]).resolve()),
            profile_id="Prop-Robotics-Neutral",
            profile_version="1.0.0",
        ))
        assert _passed_features(result) == NEUTRAL_PASS


class TestUsdBomMultiHashPackage:
    """``apple_a01_usd_bom_multi_hash`` — single USD with BOM + SHA-256 + BLAKE3.

    Mirrors ``apple_a01_usd_bom`` but every hash object also carries a
    ``blake3`` digest, as produced by ``create_simready_package.py`` when
    the ``blake3`` library is installed (the default).  PKG.HASH.001
    leaves BLAKE3 as a SHOULD; this sample exists so the BLAKE3 codepath
    is covered end-to-end.
    """

    PACKAGE_NAME = "apple_a01_usd_bom_multi_hash"

    async def test_package_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Both packaging features pass — multi-hash output stays conformant."""
        pkg_def = _pkg_def(simple_packages_dir, self.PACKAGE_NAME)
        result = await post_validate(pkg_def)

        assert result.passed
        pkg_results = result.results.get("Package", [])
        assert pkg_results
        _rel, engine_result = pkg_results[0]
        assert engine_result is not None
        assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
        assert engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]

    async def test_asset_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Single USD passes Prop-Robotics-Neutral (same content as apple_a01_usd_bom)."""
        pkg_dir = simple_packages_dir / self.PACKAGE_NAME
        assets = _discover_root_usds(pkg_dir)
        assert assets == ["apple_a01/simready_usd/sm_apple_a01_01.usd"]

        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str((pkg_dir / assets[0]).resolve()),
            profile_id="Prop-Robotics-Neutral",
            profile_version="1.0.0",
        ))
        assert _passed_features(result) == NEUTRAL_PASS

    def test_blake3_hashes_present(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Every hash object in the package definition carries sha256 + blake3.

        Locks in the multi-hash shape so a regression that drops BLAKE3
        from script output trips this sample.
        """
        pkg_def = _pkg_def(simple_packages_dir, self.PACKAGE_NAME)
        data = json.loads(pkg_def.read_text())

        for field in ("content_hash", "package_hash"):
            assert field in data, f"missing {field}"
            assert set(data[field]) >= {"sha256", "blake3"}, (
                f"{field} missing sha256/blake3: {data[field]}"
            )

        for entry in data.get("metadata", []):
            name = entry.get("name", "<unknown>")
            assert "hash" in entry, f"metadata entry {name!r} missing 'hash'"
            assert set(entry["hash"]) >= {"sha256", "blake3"}, (
                f"metadata[{name!r}].hash missing sha256/blake3: {entry['hash']}"
            )

        bom_path = (
            pkg_def.parent / ".metadata" / "com.nvidia.simready.packaging.bom.json"
        )
        bom = json.loads(bom_path.read_text())
        for item in bom.get("items", []):
            rel = item.get("relative_path", "<unknown>")
            assert set(item.get("hash", {})) >= {"sha256", "blake3"}, (
                f"bom item {rel!r}.hash missing sha256/blake3: {item.get('hash')}"
            )


class TestMultiUsdPackage:
    """``fruit_f01_multi_usd`` — two AA.001-clean USD dirs."""

    async def test_package_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Both packaging features pass (clean USDs, valid BOM + hashes)."""
        pkg_def = _pkg_def(simple_packages_dir, "fruit_f01_multi_usd")
        result = await post_validate(pkg_def)

        assert result.passed
        pkg_results = result.results.get("Package", [])
        assert pkg_results
        _rel, engine_result = pkg_results[0]
        assert engine_result is not None
        assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
        assert engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]

    async def test_asset_validation_apple(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """apple_a01 USD passes Prop-Robotics-Neutral."""
        pkg_dir = simple_packages_dir / "fruit_f01_multi_usd"
        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str((pkg_dir / "apple_a01" / "simready_usd" / "sm_apple_a01_01.usd").resolve()),
            profile_id="Prop-Robotics-Neutral",
            profile_version="1.0.0",
        ))
        assert _passed_features(result) == NEUTRAL_PASS

    async def test_asset_validation_orange(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """orange_a01 USD passes Prop-Robotics-Neutral."""
        pkg_dir = simple_packages_dir / "fruit_f01_multi_usd"
        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str((pkg_dir / "orange_a01" / "simready_usd" / "sm_obs_orange_a01_01.usd").resolve()),
            profile_id="Prop-Robotics-Neutral",
            profile_version="1.0.0",
        ))
        assert _passed_features(result) == NEUTRAL_PASS

    async def test_root_usds_discovery(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """root_usds.json lists both USD entry points."""
        pkg_dir = simple_packages_dir / "fruit_f01_multi_usd"
        assets = _discover_root_usds(pkg_dir)
        assert assets == [
            "apple_a01/simready_usd/sm_apple_a01_01.usd",
            "orange_a01/simready_usd/sm_obs_orange_a01_01.usd",
        ]


class TestMaterialsPackage:
    """``apple_a01_materials`` — no USD files, material library."""

    async def test_package_validation(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """Both packaging features pass (valid def + BOM, no USDs to trip AA.001)."""
        pkg_def = _pkg_def(simple_packages_dir, "apple_a01_materials")
        result = await post_validate(pkg_def)

        assert result.passed
        pkg_results = result.results.get("Package", [])
        assert pkg_results
        _rel, engine_result = pkg_results[0]
        assert engine_result is not None
        assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
        assert engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]

    async def test_no_assets_discovered(
        self,
        simple_packages_dir: Path,
    ) -> None:
        """No USD files means no assets to validate."""
        pkg_dir = simple_packages_dir / "apple_a01_materials"
        assets = _discover_root_usds(pkg_dir)
        assert assets == []

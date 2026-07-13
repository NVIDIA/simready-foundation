"""Tests for the packaging validators (PKG.DEF.001, PKG.META.001,
PKG.HASH.001, PKG.BOM.001, PKG.CONF.001).

Each test validates a hand-crafted fixture package under ``testdata/``
against the ``Package 1.0.0`` profile and asserts that exactly the
expected set of packaging features passes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sr_pkg_sample import ValidationFailed
from sr_pkg_sample._validate_package import (
    PackageValidationConfig,
    validate_package,
)
from sr_pkg_sample.post_validation import post_validate

try:
    import blake3 as _blake3_check  # noqa: F401

    BLAKE3_AVAILABLE = True
except ImportError:
    BLAKE3_AVAILABLE = False

PACKAGE_DEF_NAME = "com.nvidia.simready.packaging.json"
TESTDATA_DIR = Path(__file__).resolve().parent / "testdata"

PKG_PASS = {"FET030_PACKAGING_CORE", "FET032_PACKAGING_INTROSPECTION"}
PKG_NO_BOM = {"FET030_PACKAGING_CORE"}
PKG_FAIL: set[str] = set()

requires_blake3 = pytest.mark.skipif(
    not BLAKE3_AVAILABLE,
    reason="blake3 module not importable; the validator skips blake3 verification.",
)


def _passed_features(result) -> set[str]:
    if result is None:
        return set()
    return {
        fid
        for fid, data in result.features_summary.items()
        if data.get("passed")
    }


def _validate_fixture(fixture_name: str) -> set[str]:
    """Run ``validate_package`` on a versioned testdata fixture and return passing features."""
    pkg_def = TESTDATA_DIR / fixture_name / "1.0.0" / PACKAGE_DEF_NAME
    assert pkg_def.is_file(), f"Fixture missing: {pkg_def}"
    result = validate_package(
        PackageValidationConfig(
            asset_path=str(pkg_def),
            profile_id="Package",
            profile_version="1.0.0",
        )
    )
    return _passed_features(result)


# ---------------------------------------------------------------------------
# PKG.DEF.001 — manifest schema (PackageDefinitionChecker)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected",
    [
        ("def_missing_required_fields", PKG_FAIL),
        ("def_package_id_forbidden_chars", PKG_FAIL),
        ("def_license_empty", PKG_FAIL),
        ("def_metadata_entry_missing_fields", PKG_FAIL),
        ("def_description_too_long", PKG_NO_BOM),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_pkg_def_001(fixture_name: str, expected: set[str]) -> None:
    assert _validate_fixture(fixture_name) == expected


# ---------------------------------------------------------------------------
# PKG.META.001 — metadata files (MetadataFilesChecker)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected",
    [
        ("meta_not_object", PKG_FAIL),
        ("meta_missing_format_version", PKG_FAIL),
        ("meta_missing_file_without_dir", PKG_FAIL),
        ("meta_unlisted_entry", PKG_NO_BOM),
        ("meta_missing_file_with_dir", PKG_NO_BOM),
        ("meta_happy_case", PKG_NO_BOM),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_pkg_meta_001(fixture_name: str, expected: set[str]) -> None:
    assert _validate_fixture(fixture_name) == expected


# ---------------------------------------------------------------------------
# PKG.HASH.001 — hash integrity (HashObjectFormatChecker)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected",
    [
        ("hash_content_mismatch_no_bom", PKG_FAIL),
        ("hash_content_mismatch_bom", PKG_FAIL),
        ("hash_content_extra_file_no_bom", PKG_FAIL),
        ("hash_package_hash_mismatch", PKG_FAIL),
        ("hash_missing_sha256", PKG_FAIL),
        ("hash_content_blake2b_mismatch", PKG_FAIL),
        ("hash_bom_item_first1m_mismatch", PKG_FAIL),
        ("hash_metadata_entry_sha256_mismatch", PKG_FAIL),
        ("hash_content_extra_file_bom", PKG_PASS),
        ("hash_zero_byte_file_bom", PKG_PASS),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_pkg_hash_001(fixture_name: str, expected: set[str]) -> None:
    assert _validate_fixture(fixture_name) == expected


# Multi-algo BLAKE3 negative fixtures — gated on the optional ``blake3``
# Python module. When unavailable, the validator format-checks but does
# not recompute the blake3 digest, so a tampered value would silently
# pass. The corresponding skip is documented in PKG.HASH.001 and in the
# validator's _digest_from_bytes helper.

@requires_blake3
@pytest.mark.parametrize(
    "fixture_name, expected",
    [
        ("hash_content_blake3_mismatch", PKG_FAIL),
        ("hash_package_blake3_mismatch", PKG_FAIL),
        ("hash_bom_item_blake3_mismatch", PKG_FAIL),
        ("hash_metadata_entry_blake3_mismatch", PKG_FAIL),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_pkg_hash_001_blake3(fixture_name: str, expected: set[str]) -> None:
    assert _validate_fixture(fixture_name) == expected


# ---------------------------------------------------------------------------
# PKG.CONF.001 — conformance metadata content_hash verification
# ---------------------------------------------------------------------------


async def test_pkg_conf_001_content_hash_mismatch() -> None:
    """ConformanceMetadataChecker must fail when a conformance file's
    declared ``content_hash`` does not match the BOM-derived value.

    The fixture has a correctly-formed package + BOM, and a conformance
    metadata file in ``.metadata/`` whose ``content_hash.sha256`` is
    zeroed. The conformance checker re-derives the content hash from
    the BOM (per the PKG.HASH.001 multi-algo computation) and reports
    the mismatch under PKG.CONF.001 → FET030_PACKAGING_CORE.
    """
    assert _validate_fixture("hash_conformance_content_hash_mismatch") == PKG_FAIL


# ---------------------------------------------------------------------------
# Cross-cutting / content-shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected",
    [
        ("content_mixed_extensions", PKG_PASS),
        ("pkg_faulty_usd_with_bom", PKG_PASS),
        ("pkg_faulty_usd_no_bom", PKG_NO_BOM),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_packaging_content_shape(fixture_name: str, expected: set[str]) -> None:
    assert _validate_fixture(fixture_name) == expected


# ---------------------------------------------------------------------------
# PKG.BOM.001 — per-file BOM hash verification
# ---------------------------------------------------------------------------


async def test_bom_file_hash_mismatch_detected() -> None:
    """Post-validation must fail when a content file doesn't match its BOM hash.

    The ``bom_file_hash_mismatch`` fixture is a minimal package where
    ``content_hash`` and ``package_hash`` are correctly derived from the
    BOM entries (so all aggregate-hash checks pass), but the actual
    ``readme.txt`` on disk has different content than what the BOM's
    per-file ``sha256`` claims.

    Without per-file verification, validation passes despite the
    tampered file.
    """
    pkg_def = TESTDATA_DIR / "bom_file_hash_mismatch" / PACKAGE_DEF_NAME
    with pytest.raises(ValidationFailed) as exc_info:
        await post_validate(pkg_def)

    assert "FET030_PACKAGING_CORE" in exc_info.value.failures

"""Tests for the ``post_validate`` step.

Drives :func:`sr_pkg_sample.post_validation.post_validate` directly against
committed sample packages under ``sample_content/packaging/simple_packages/``
and against a freshly built package produced by the full step API.

``apple_a01_nobom`` is used as the partial-failure fixture: it has a valid
package definition and clean USD content, so ``FET030_PACKAGING_CORE``
passes, but lacks a BOM so ``FET032_PACKAGING_INTROSPECTION`` fails —
matching ``run_tests_hack.py``'s ``PKG_NO_BOM`` expectation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sr_pkg_sample import PostValidationResult, UsageError, ValidationFailed
from sr_pkg_sample.post_validation import post_validate
from sr_pkg_sample.pre_validation import pre_validate

PACKAGE_DEF_NAME = "com.nvidia.simready.packaging.json"


@pytest.fixture(scope="session")
def sample_package_def(foundations_dir: Path) -> Path:
    """Path to the ready-to-validate sample package definition (no-BOM variant)."""
    pkg_def = (
        foundations_dir
        / "sample_content"
        / "packaging"
        / "simple_packages"
        / "apple_a01_nobom"
        / PACKAGE_DEF_NAME
    )
    if not pkg_def.is_file():
        pytest.skip(f"Sample package definition missing: {pkg_def}")
    return pkg_def


async def test_post_validate_nobom_sample_partial_fail(
    sample_package_def: Path,
) -> None:
    """``apple_a01_nobom`` passes FET030 but fails FET032 (no BOM).

    ``FET030_PACKAGING_CORE`` passes because the package definition is
    valid and the single USD is AA.001-clean.
    ``FET032_PACKAGING_INTROSPECTION`` fails because the package has no
    ``com.nvidia.simready.packaging.bom.json``.  ``post_validate`` must
    raise ``ValidationFailed`` with ``FET032`` in the failures and
    attach the partial ``PostValidationResult``.
    """
    with pytest.raises(ValidationFailed) as exc_info:
        await post_validate(sample_package_def)

    assert "FET032_PACKAGING_INTROSPECTION" in exc_info.value.failures
    assert "FET030_PACKAGING_CORE" not in exc_info.value.failures

    result = exc_info.value.result
    assert isinstance(result, PostValidationResult)
    assert not result.passed
    assert "FET032_PACKAGING_INTROSPECTION" in result.failed_features

    pkg_results = result.results.get("Package", [])
    assert pkg_results
    _rel, engine_result = pkg_results[0]
    assert engine_result is not None
    assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
    assert not engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]


async def test_post_validate_built_package_passes(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """End-to-end happy path: clean source -> built package -> all features pass.

    Drives the full workflow on a BOM-carrying, AA.001-clean package
    built on the fly, asserting that every feature in the ``Package``
    profile reports ``PASS``.
    """
    pytest.importorskip(
        "wrapp",
        reason="wrapp is required to build the fixture for this happy-path test",
    )
    from sr_pkg_sample.create_package_using_wrapp import create_package

    name, version, license_id = "apple_a01", "1.0.0", "MIT"
    repo = tmp_path / "repo"
    repo.mkdir()

    await pre_validate(sample_source_copy)

    created = await create_package(
        name, version, license_id, str(sample_source_copy), str(repo)
    )

    pkg_def = repo / ".packages" / name / version / PACKAGE_DEF_NAME
    assert pkg_def.is_file(), f"package definition missing at {pkg_def}"
    assert created.pkg_def_url.endswith(PACKAGE_DEF_NAME)

    result = await post_validate(pkg_def)

    assert isinstance(result, PostValidationResult)
    assert result.passed
    assert not result.failed_features

    pkg_results = result.results.get("Package", [])
    assert pkg_results
    _rel, engine_result = pkg_results[0]
    assert engine_result is not None
    assert engine_result.features_summary["FET030_PACKAGING_CORE"]["passed"]
    assert engine_result.features_summary["FET032_PACKAGING_INTROSPECTION"]["passed"]


async def test_post_validate_nonexistent_path(tmp_path: Path) -> None:
    """A missing package-def path raises ``UsageError``."""
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(UsageError, match="not found"):
        await post_validate(missing)


# ---------------------------------------------------------------------------
# Phase C: evidence writing
# ---------------------------------------------------------------------------

import json  # noqa: E402


async def test_post_validate_write_evidence(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """``write_evidence=True`` writes a conformance JSON next to the package def."""
    pytest.importorskip("wrapp")
    from sr_pkg_sample.create_package_using_wrapp import create_package

    repo = tmp_path / "repo"
    repo.mkdir()

    await pre_validate(sample_source_copy)

    await create_package(
        "apple_a01", "1.0.0", "MIT",
        str(sample_source_copy), str(repo),
    )

    pkg_def = repo / ".packages" / "apple_a01" / "1.0.0" / "com.nvidia.simready.packaging.json"
    result = await post_validate(pkg_def, write_evidence=True)

    assert result.evidence_paths

    metadata_dir = pkg_def.parent / ".metadata"
    evidence_files = sorted(
        p for p in metadata_dir.iterdir()
        if p.name.startswith("com.nvidia.simready.conformance.Package@")
    )
    assert evidence_files, f"no evidence file found in {metadata_dir}"
    evidence_data = json.loads(evidence_files[0].read_text())
    assert evidence_data["profile"] == "Package"

    definition = json.loads(pkg_def.read_text())
    def_metadata_names = {e["name"] for e in definition.get("metadata", [])}
    for ef in evidence_files:
        assert ef.name not in def_metadata_names, (
            f"evidence file {ef.name} must NOT be in the package definition metadata array"
        )


async def test_post_validate_no_evidence_by_default(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """Without ``write_evidence``, no conformance JSON is written."""
    pytest.importorskip("wrapp")
    from sr_pkg_sample.create_package_using_wrapp import create_package

    repo = tmp_path / "repo"
    repo.mkdir()

    await pre_validate(sample_source_copy)

    await create_package(
        "apple_a01", "1.0.0", "MIT",
        str(sample_source_copy), str(repo),
    )

    pkg_def = repo / ".packages" / "apple_a01" / "1.0.0" / "com.nvidia.simready.packaging.json"
    result = await post_validate(pkg_def)

    assert not result.evidence_paths

    metadata_dir = pkg_def.parent / ".metadata"
    evidence_files = [
        p for p in metadata_dir.iterdir()
        if p.name.startswith("com.nvidia.simready.conformance.Package@")
    ]
    assert not evidence_files, (
        f"evidence file should not exist without write_evidence: {evidence_files}"
    )

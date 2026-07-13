"""Tests for the ``pre_validate`` step.

Drives :func:`sr_pkg_sample.pre_validation.pre_validate` directly against the
apple_a01 sample and per-test copies with package artifacts injected
at the root.  Asserts that the function:

* returns a :class:`PreValidationResult` with ``.passed == True`` on a
  clean source folder;
* raises :class:`UsageError` for a missing source path;
* raises :class:`UsageError` when ``write_metadata=True`` and no root
  USDs are specified (neither ``root_usds`` nor an existing
  ``.metadata/com.nvidia.simready.root_usds.json``);
* accepts ``allow_no_usd_files=True`` to permit an empty source;
* falls back to an existing ``root_usds.json`` when ``root_usds`` is
  not provided;
* when ``write_metadata=True`` and OpenUSD root layers are given, writes
  ``.metadata/`` files (BOM, ``root_usds.json``, conformance JSONs
  with ``content_hash``) and reports them in
  ``result.metadata_written``.

The ``.wrapp``-marker guard lives in ``create_package_using_wrapp``,
not here — pre-validation is packaging-backend-agnostic.

CLI-surface tests for ``create_simready_package.py`` (missing
positional arguments, help, ``--only-pre-validation``) live in
:mod:`tests.test_create_simready_package`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_pkg_sample import PreValidationResult, UsageError
from sr_pkg_sample.pre_validation import pre_validate


async def test_pre_validate_happy_path(sample_source: Path) -> None:
    """A clean apple_a01 source passes the ``Package-Candidate`` profile.

    ``sample_source`` points at
    ``sample_content/common_assets/props_general/apple_a01/simready_usd``
    whose single USD (``sm_apple_a01_01.usd``) is ``AA.001``-clean —
    ``run_tests_hack.py`` already covers it under ``NEUTRAL_PASS``.
    """
    result = await pre_validate(sample_source)

    assert isinstance(result, PreValidationResult)
    assert result.passed
    assert not result.failed_features

    pc_results = result.results.get("Package-Candidate", [])
    assert pc_results
    for _rel, engine_result in pc_results:
        assert engine_result is not None
        for fid, detail in engine_result.features_summary.items():
            assert detail["passed"], f"{fid} unexpectedly failed"


async def test_pre_validate_nonexistent_path(tmp_path: Path) -> None:
    """A missing source path raises ``UsageError``."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(UsageError, match="(not found|not a directory)"):
        await pre_validate(missing)


async def test_pre_validate_ignores_existing_package_def(
    sample_source_copy: Path,
) -> None:
    """An existing package definition in the source is silently ignored.

    A user may re-package a folder that was packaged before (e.g. to
    publish a new version after edits).  The old
    ``com.nvidia.simready.packaging.json`` must not block pre-flight —
    the create step will overwrite it.
    """
    (sample_source_copy / "com.nvidia.simready.packaging.json").write_text("{}")
    result = await pre_validate(sample_source_copy)
    assert isinstance(result, PreValidationResult)
    assert result.results


async def test_pre_validate_allows_metadata_dir(sample_source_copy: Path) -> None:
    """``.metadata/`` no longer blocks pre-flight (pre-validation writes there)."""
    (sample_source_copy / ".metadata").mkdir()

    result = await pre_validate(sample_source_copy)
    assert result.passed


# -- write_metadata tests ---------------------------------------------------

async def test_pre_validate_write_metadata_happy_path(
    sample_source_copy: Path,
) -> None:
    """``write_metadata=True`` produces conformance files + BOM with content_hash."""
    result = await pre_validate(
        sample_source_copy,
        root_usds=["sm_apple_a01_01.usd"],
        write_metadata=True,
    )

    assert isinstance(result, PreValidationResult)
    assert result.passed
    assert result.metadata_written

    meta = sample_source_copy / ".metadata"
    assert meta.is_dir()

    root_usds_path = meta / "com.nvidia.simready.root_usds.json"
    assert root_usds_path.is_file()
    root_usds_data = json.loads(root_usds_path.read_text())
    assert "entries" in root_usds_data
    assert len(root_usds_data["entries"]) == 1

    bom_path = meta / "com.nvidia.simready.packaging.bom.json"
    assert bom_path.is_file()
    bom_data = json.loads(bom_path.read_text())
    assert "items" in bom_data
    assert len(bom_data["items"]) > 0

    conf_files = list(meta.glob("com.nvidia.simready.conformance.*.json"))
    assert len(conf_files) == 1
    conf_data = json.loads(conf_files[0].read_text())
    assert conf_data["profile"] == "Package-Candidate"
    assert "content_hash" in conf_data
    assert "sha256" in conf_data["content_hash"]


async def test_pre_validate_no_root_usd_raises(sample_source_copy: Path) -> None:
    """``write_metadata=True`` without ``root_usds`` and no ``root_usds.json`` raises."""
    with pytest.raises(UsageError, match="no root USD files specified"):
        await pre_validate(sample_source_copy, write_metadata=True)


async def test_pre_validate_no_root_usd_allowed(tmp_path: Path) -> None:
    """``allow_no_usd_files=True`` returns an empty result instead of raising."""
    empty_source = tmp_path / "empty_asset"
    empty_source.mkdir()

    result = await pre_validate(
        empty_source, write_metadata=True, allow_no_usd_files=True,
    )
    assert isinstance(result, PreValidationResult)
    assert result.passed
    assert result.results == {}


async def test_pre_validate_no_usd_simple_path_raises(tmp_path: Path) -> None:
    """Simple path (no ``write_metadata``) with an empty dir raises."""
    empty_source = tmp_path / "empty_asset"
    empty_source.mkdir()

    with pytest.raises(UsageError, match="no USD files found"):
        await pre_validate(empty_source)


async def test_pre_validate_no_usd_simple_path_allowed(tmp_path: Path) -> None:
    """Simple path with ``allow_no_usd_files=True`` returns an empty result."""
    empty_source = tmp_path / "empty_asset"
    empty_source.mkdir()

    result = await pre_validate(empty_source, allow_no_usd_files=True)
    assert isinstance(result, PreValidationResult)
    assert result.passed
    assert result.results == {}


async def test_pre_validate_root_usds_json_fallback(sample_source_copy: Path) -> None:
    """An existing ``root_usds.json`` is used when ``root_usds`` is not provided."""
    meta = sample_source_copy / ".metadata"
    meta.mkdir(exist_ok=True)
    (meta / "com.nvidia.simready.root_usds.json").write_text(
        json.dumps({"format_version": "1.0", "entries": ["sm_apple_a01_01.usd"]}),
    )

    result = await pre_validate(sample_source_copy, write_metadata=True)
    assert isinstance(result, PreValidationResult)
    assert result.passed


async def test_pre_validate_multiple_root_usds_with_explicit(
    sample_source_copy: Path,
) -> None:
    """Explicit ``root_usds`` resolves the ambiguity of multiple OpenUSD root layers.

    Each USD sits in its own ``<asset>/<intermediate>/`` hierarchy so
    NP.005 (one USD per folder) is satisfied for the validated entry
    point.  The source is the common parent of both asset folders.
    """
    source = sample_source_copy.parent          # .../apple_a01
    extra_dir = source / "extra_asset" / "extra_usd"
    extra_dir.mkdir(parents=True)
    (extra_dir / "extra.usda").write_bytes(b"#usda 1.0\n")

    root_usd = [
        f"{sample_source_copy.name}/{p.name}"
        for p in sample_source_copy.iterdir()
        if p.is_file() and p.suffix.lower() == ".usd"
    ][0]
    await pre_validate(
        source,
        root_usds=[root_usd],
        write_metadata=True,
    )

    root_usds_path = source / ".metadata" / "com.nvidia.simready.root_usds.json"
    data = json.loads(root_usds_path.read_text())
    assert data["entries"] == [root_usd]


async def test_pre_validate_write_metadata_false_no_side_effects(
    sample_source_copy: Path,
) -> None:
    """``write_metadata=False`` (default) does not create ``.metadata/``."""
    result = await pre_validate(sample_source_copy, write_metadata=False)
    assert not (sample_source_copy / ".metadata").exists()
    assert not result.metadata_written

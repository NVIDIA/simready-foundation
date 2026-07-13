"""Tests for the ``create_package`` step (WRAPP-backed implementation).

Drives :func:`sr_pkg_sample.create_package_using_wrapp.create_package` directly
against a writable apple_a01 sample copy and a per-test throwaway repo
directory.  Asserts that the function:

* drives WRAPP end-to-end to build a package at
  ``<repo>/.packages/<name>/<version>/`` that carries a parseable
  ``com.nvidia.simready.packaging.json`` plus
  ``.metadata/com.nvidia.simready.packaging.bom.json``;
* extends the ``.wrapp`` catalog so ``wrapp.export_package`` lays the
  two metadata JSONs out alongside the source files in the exported
  tar — the actual user-facing reason we patch the catalog
  (catalog-aware tooling like ``wrapp install`` / ``wrapp export``
  would otherwise drop them);
* keeps the BOM as a strict "content-only" view of the catalog — the
  metadata files MUST NOT show up in ``bom.items[]`` even after the
  catalog augmentation, since they live in
  ``definition.metadata[]`` instead;
* refuses to run when the source root already carries a ``*.wrapp``
  marker for a *different* package name (would otherwise silently get
  absorbed as a sub-dependency by ``wrapp.create``);
* refuses to continue when ``wrapp.create`` ends up absorbing nested
  ``*.wrapp`` markers from sub-folders — nested packages are not yet
  part of the SimReady packaging standard.

Gated behind ``pytest.importorskip('wrapp')`` so a venv without the
WRAPP wheel skips the entire module instead of erroring out.
"""

from __future__ import annotations

import json
import shutil
import tarfile
from pathlib import Path

import pytest

pytest.importorskip("wrapp")
import wrapp  # noqa: E402  (must come after importorskip)

from sr_pkg_sample import CreatedPackage, UsageError  # noqa: E402
from sr_pkg_sample.create_package_using_wrapp import create_package  # noqa: E402


async def test_create_package_happy_path(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """End-to-end: build a package + definition + BOM from a clean source.

    The generated ``com.nvidia.simready.packaging.json`` must carry the
    license passed in and a ``package_id`` that includes both the
    requested ``<name>`` and ``<version>`` (``std_pkg_def`` always
    appends them — see ``wrapp.generate_package_definition``).  The
    BOM has to be non-empty because the apple_a01 sample ships a USD
    plus material/texture files.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    name = "apple_a01"
    version = "1.0.0"
    license_id = "MIT"

    created = await create_package(name, version, license_id, str(sample_source_copy), str(repo))

    assert isinstance(created, CreatedPackage)
    assert created.pkg_def_url.endswith("com.nvidia.simready.packaging.json")
    assert created.bom_url.endswith("com.nvidia.simready.packaging.bom.json")

    pkg_dir = repo / ".packages" / name / version
    wrapp_file = pkg_dir / f".{name}.wrapp"
    pkg_def = pkg_dir / "com.nvidia.simready.packaging.json"
    bom = pkg_dir / ".metadata" / "com.nvidia.simready.packaging.bom.json"

    assert wrapp_file.is_file(), f"missing wrapp marker: {wrapp_file}"
    assert pkg_def.is_file(), f"missing package def: {pkg_def}"
    assert bom.is_file(), f"missing BOM: {bom}"

    definition = json.loads(pkg_def.read_text())
    assert definition["license"] == license_id, definition
    package_id = definition["package_id"]
    assert name in package_id and version in package_id, package_id

    bom_data = json.loads(bom.read_text())
    assert "items" in bom_data, bom_data
    assert bom_data["items"], (
        f"BOM items list is empty for a non-empty source folder: {bom_data}"
    )

    pkg_def_relpath = "com.nvidia.simready.packaging.json"
    bom_relpath = ".metadata/com.nvidia.simready.packaging.bom.json"

    tar_path = tmp_path / "exported.tar"

    async with wrapp.ContextManager() as scheduler:
        await wrapp.export_package(
            catalog=None,
            repo=str(repo),
            package_name=name,
            version=version,
            output=str(tar_path),
            overwrite=True,
            scheduler=scheduler,
        )

    assert tar_path.is_file(), f"wrapp.export_package did not produce {tar_path}"

    with tarfile.open(tar_path) as tf:
        members = {m.name: m for m in tf.getmembers()}

    assert pkg_def_relpath in members, (
        f"package definition missing from exported tar: {sorted(members)}"
    )
    assert bom_relpath in members, (
        f"BOM missing from exported tar: {sorted(members)}"
    )
    assert members[pkg_def_relpath].size > 0, (
        f"{pkg_def_relpath} exported as empty: {members[pkg_def_relpath].size}"
    )
    assert members[bom_relpath].size > 0, (
        f"{bom_relpath} exported as empty: {members[bom_relpath].size}"
    )

    bom_relpaths = {item["relative_path"] for item in bom_data["items"]}
    assert pkg_def_relpath not in bom_relpaths, (
        f"package definition leaked into BOM items: {sorted(bom_relpaths)}"
    )
    assert bom_relpath not in bom_relpaths, (
        f"BOM listed itself as a content item: {sorted(bom_relpaths)}"
    )


async def test_create_package_accepts_file_url(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """``<source>`` and ``<repo>`` also accept ``file://`` URLs.

    WRAPP itself takes both bare paths and URLs; ``create_package``
    must therefore not choke on a ``file:///...`` URL — it should
    normalize it to a local path and produce the same outputs as the
    bare-path happy path.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    created = await create_package(
        "apple_a01",
        "1.0.0",
        "MIT",
        sample_source_copy.as_uri(),
        repo.as_uri(),
    )

    assert isinstance(created, CreatedPackage)

    pkg_dir = repo / ".packages" / "apple_a01" / "1.0.0"
    assert (pkg_dir / ".apple_a01.wrapp").is_file()
    assert (pkg_dir / "com.nvidia.simready.packaging.json").is_file()
    assert (pkg_dir / ".metadata" / "com.nvidia.simready.packaging.bom.json").is_file()


async def test_create_package_rejects_mismatched_wrapp(
    sample_source_copy: Path, tmp_path: Path
) -> None:
    """A root-level ``foo.wrapp`` marker aborts before WRAPP runs.

    Touches a ``foo.wrapp`` marker at the root of the copied source,
    then requests ``<name>=apple_a01``.  ``create_package`` must raise
    :class:`UsageError` with a message that names both the offending
    file and the ``foo`` package it identifies, and offers the user
    the choice of deleting the marker or rerunning with ``foo`` as
    the package name.
    """
    stale = sample_source_copy / "foo.wrapp"
    stale.write_bytes(b"")
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(UsageError) as exc_info:
        await create_package(
            "apple_a01",
            "1.0.0",
            "MIT",
            str(sample_source_copy),
            str(repo),
        )

    msg = str(exc_info.value)
    assert "foo.wrapp" in msg, msg
    assert "'foo'" in msg, msg


async def test_create_package_rejects_nested_subpackage(
    sample_source_copy: Path, tmp_path: Path
) -> None:
    """A nested ``.wrapp`` file makes WRAPP absorb it as a subpackage.

    Builds a real one-file throwaway package with ``wrapp.create``,
    drops its ``.dummy.wrapp`` marker into a subdirectory of the apple
    source, then runs ``create_package``.  The pre-flight check only
    inspects the source root, so ``wrapp.create`` runs and folds the
    nested package in as a sub-dependency.  The post-create check must
    then spot the absorbed dependency and raise :class:`UsageError`
    with the ``nested packages ... not yet supported`` message.
    """

    work_dir = tmp_path / "dummy_pkg"
    work_dir.mkdir(parents=True, exist_ok=True)
    async with wrapp.ContextManager() as scheduler:
        tiny_src = work_dir / "tiny_src"
        tiny_src.mkdir()
        (tiny_src / "leaf.txt").write_text("leaf\n")
        tiny_repo = work_dir / "tiny_repo"
        await wrapp.create(
            "dummy",
            "1.0",
            source=str(tiny_src),
            catalog=False,
            repo=str(tiny_repo),
            scheduler=scheduler,
        )
    dummy_marker = tiny_repo / ".packages" / "dummy" / "1.0" / ".dummy.wrapp"

    nested_dir = sample_source_copy / "nested_pkg"
    nested_dir.mkdir()
    shutil.copy(dummy_marker, nested_dir / dummy_marker.name)

    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(UsageError) as exc_info:
        await create_package(
            "apple_a01",
            "1.0.0",
            "MIT",
            str(sample_source_copy),
            str(repo),
        )

    msg = str(exc_info.value)
    assert "nested packages" in msg.lower(), msg
    assert "'dummy'" in msg, msg


# ---------------------------------------------------------------------------
# Phase B: conformance metadata trust-handoff
# ---------------------------------------------------------------------------

from sr_pkg_sample import BuildFailed  # noqa: E402
from sr_pkg_sample.pre_validation import pre_validate  # noqa: E402


async def test_create_registers_conformance_metadata(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """Pre-validate with write_metadata → create → conformance in metadata array.

    The full flow writes .metadata/ during pre-validation, then the
    create step should verify the content_hash and register the
    conformance and root_usds entries alongside the BOM in the package
    definition's ``metadata`` array.
    """
    await pre_validate(
        sample_source_copy,
        root_usds=["sm_apple_a01_01.usd"],
        write_metadata=True,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    created = await create_package(
        "apple_a01", "1.0.0", "MIT",
        str(sample_source_copy), str(repo),
    )

    pkg_def = json.loads(Path(created.pkg_def_url).read_text())
    metadata_names = {e["name"] for e in pkg_def.get("metadata", [])}

    assert "com.nvidia.simready.packaging.bom.json" in metadata_names
    assert "com.nvidia.simready.root_usds.json" in metadata_names

    conformance_entries = [
        n for n in metadata_names
        if n.startswith("com.nvidia.simready.conformance.")
    ]
    assert conformance_entries, (
        f"no conformance entries in metadata: {metadata_names}"
    )

    for entry in pkg_def["metadata"]:
        assert "hash" in entry, f"metadata entry {entry['name']!r} missing hash"
        assert "sha256" in entry["hash"], f"metadata entry {entry['name']!r} missing sha256"

    assert "package_hash" in pkg_def


async def test_create_without_metadata_only_has_bom(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """When no .metadata/ exists, the package definition has only the BOM entry."""
    repo = tmp_path / "repo"
    repo.mkdir()
    created = await create_package(
        "apple_a01", "1.0.0", "MIT",
        str(sample_source_copy), str(repo),
    )

    pkg_def = json.loads(Path(created.pkg_def_url).read_text())
    metadata_names = [e["name"] for e in pkg_def.get("metadata", [])]
    assert metadata_names == ["com.nvidia.simready.packaging.bom.json"]


async def test_create_rejects_stale_metadata(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """content_hash mismatch between pre-validation and current source aborts the build."""
    await pre_validate(
        sample_source_copy,
        root_usds=["sm_apple_a01_01.usd"],
        write_metadata=True,
    )

    extra_file = sample_source_copy / "extra_file_added_after_preval.txt"
    extra_file.write_text("this changes the content_hash\n")

    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(BuildFailed, match="content_hash mismatch"):
        await create_package(
            "apple_a01", "1.0.0", "MIT",
            str(sample_source_copy), str(repo),
        )

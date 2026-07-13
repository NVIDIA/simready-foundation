"""End-to-end install / unzip / republish tests.

Where the per-step tests stop at "the producer can build a package", these
tests prove the next link in the chain — a SimReady-conformant package
can also be redistributed, consumed, and re-published:

* :func:`test_wrapp_install_and_open_stage` builds via the full async
  WRAPP workflow, installs the result with ``wrapp.install`` into a
  fresh destination, re-validates the installed copy, and opens the
  root USD with OpenUSD.
* :func:`test_zip_unzip_and_open_stage` builds via the no-WRAPP
  workflow (``Package-NoBOM`` profile), zips the source folder, unzips
  it elsewhere, re-validates, and opens the root USD with OpenUSD.
* :func:`test_install_modify_republish` simulates two users sharing a
  package through a WRAPP repository: User A produces v1.0.0, User B
  installs it, edits the working folder, and republishes v1.1.0
  through the full workflow.

All three drive the high-level async orchestrators in
:mod:`sr_pkg_sample.workflow` (``create_simready_package`` and
``create_simready_package_no_wrapp``) instead of the per-step API, so
they exercise the same code path users hit when they invoke
``create_simready_package.py`` from the CLI.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from pxr import Usd

from sr_pkg_sample import (
    CreatedPackage,
    create_simready_package_no_wrapp,
    post_validate,
)

APPLE_ROOT_USD = "sm_apple_a01_01.usd"
PACKAGE_DEF_NAME = "com.nvidia.simready.packaging.json"
BOM_RELPATH = ".metadata/com.nvidia.simready.packaging.bom.json"

EXTRA_FILE_RELPATH = "extras/extra_data.json"
EXTRA_FILE_BODY = '{"note": "added by User B"}\n'


def _assert_stage_loads(usd_path: Path) -> None:
    """Open *usd_path* with OpenUSD and check it has at least one root prim."""
    assert usd_path.is_file(), f"USD file missing: {usd_path}"
    stage = Usd.Stage.Open(str(usd_path))
    assert stage is not None, f"Usd.Stage.Open returned None for {usd_path}"
    children = stage.GetPseudoRoot().GetChildren()
    assert children, f"stage at {usd_path} has no root prims"


# ---------------------------------------------------------------------------
# Test 1: WRAPP build + install + validate + open USD
# ---------------------------------------------------------------------------

# Tests 1 and 3 build with WRAPP and install with wrapp.install; gate the
# whole pair behind importorskip so a no-wrapp venv just skips the WRAPP
# tests instead of erroring out.
wrapp = pytest.importorskip("wrapp")

from sr_pkg_sample import create_simready_package  # noqa: E402


async def _wrapp_install(
    package_name: str, version: str, repo: Path, destination: Path
) -> None:
    """Install ``<package_name>@<version>`` from *repo* into *destination*."""
    async with wrapp.ContextManager() as scheduler:
        await wrapp.install(
            package_name,
            version,
            destination=str(destination),
            repo=str(repo),
            scheduler=scheduler,
        )


async def test_wrapp_install_and_open_stage(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """Build with the full WRAPP workflow, install, re-validate, open USD.

    Drives the public async ``create_simready_package`` orchestrator —
    the same path ``create_simready_package.py`` takes — so the test
    fails if pre-validation, the build, or post-validation breaks for
    a producer.  Then exercises the consumer side: ``wrapp.install``
    must lay the package definition, BOM, and source files out in the
    destination (the catalog patch in
    ``create_package_using_wrapp.py`` is what makes that work), the
    installed copy must independently satisfy the ``Package`` profile,
    and the root USD must open with OpenUSD.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    created = await create_simready_package(
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        str(repo),
        root_usds=[APPLE_ROOT_USD],
    )

    assert isinstance(created, CreatedPackage)
    pkg_dir = repo / ".packages" / "apple_a01" / "1.0.0"
    assert (pkg_dir / PACKAGE_DEF_NAME).is_file()
    assert (pkg_dir / BOM_RELPATH).is_file()

    dest = tmp_path / "installed"
    dest.mkdir()
    await _wrapp_install("apple_a01", "1.0.0", repo, dest)

    installed_pkg_def = dest / PACKAGE_DEF_NAME
    installed_bom = dest / BOM_RELPATH
    installed_root_usd = dest / APPLE_ROOT_USD
    assert installed_pkg_def.is_file(), (
        f"package definition missing after install: {installed_pkg_def}"
    )
    assert installed_bom.is_file(), f"BOM missing after install: {installed_bom}"
    assert installed_root_usd.is_file(), (
        f"root USD missing after install: {installed_root_usd}"
    )

    await post_validate(installed_pkg_def)

    _assert_stage_loads(installed_root_usd)


# ---------------------------------------------------------------------------
# Test 2: no-WRAPP build + zip + unzip + validate + open USD
# ---------------------------------------------------------------------------


def _zip_tree(root: Path, archive: Path) -> None:
    """Zip every regular file under *root* into *archive* with relative paths."""
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(root))


async def test_zip_unzip_and_open_stage(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """Build via the no-WRAPP workflow, zip + unzip elsewhere, re-validate, open USD.

    Drives ``create_simready_package_no_wrapp`` (the lightweight,
    BOM-less path) end-to-end against the apple sample.  The test then
    treats the source folder as the package, zips it, extracts it
    somewhere else, and asserts:

    * the archive carries the package definition and the root USD;
    * the unzipped copy independently satisfies the ``Package-NoBOM``
      profile (core packaging rules — no FET032 introspection, since
      this path has no BOM);
    * the root USD opens with OpenUSD.
    """
    created = await create_simready_package_no_wrapp(
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
    )

    assert isinstance(created, CreatedPackage)
    assert (sample_source_copy / PACKAGE_DEF_NAME).is_file()
    assert created.bom_url is None

    archive = tmp_path / "package.zip"
    _zip_tree(sample_source_copy, archive)

    unzipped = tmp_path / "unzipped"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(unzipped)

    unzipped_pkg_def = unzipped / PACKAGE_DEF_NAME
    unzipped_root_usd = unzipped / APPLE_ROOT_USD
    assert unzipped_pkg_def.is_file(), (
        f"package definition missing after unzip: {unzipped_pkg_def}"
    )
    assert unzipped_root_usd.is_file(), (
        f"root USD missing after unzip: {unzipped_root_usd}"
    )

    await post_validate(unzipped_pkg_def, profiles=["Package-NoBOM"])

    _assert_stage_loads(unzipped_root_usd)


# ---------------------------------------------------------------------------
# Test 3: install, modify, republish (two-user loop)
# ---------------------------------------------------------------------------


def _bom_relpaths(bom_path: Path) -> set[str]:
    """Return the set of ``relative_path`` values in *bom_path*."""
    bom = json.loads(bom_path.read_text())
    return {item["relative_path"] for item in bom.get("items", [])}


async def test_install_modify_republish(
    sample_source_copy: Path, tmp_path: Path,
) -> None:
    """Two-user loop: User A publishes v1.0.0, User B installs + edits + republishes v1.1.0.

    Proves the consumer round-trip: ``wrapp.install`` produces a folder
    that survives an edit + republish cycle, the Phase A/B trust
    handoff (pre-validation writes ``content_hash``, create verifies +
    registers) works on real consumer-edited content, and a modified
    asset shows up in the new BOM with a fresh hash.

    The cleanup step (``rm com.nvidia.simready.packaging.json``,
    ``rm -rf .metadata/``) is deliberate: ``wrapp.install`` lays both
    out in the destination as v1.0.0 artefacts, and re-running
    pre-validation would otherwise check the stale ``content_hash``
    against the modified files and abort.  Keeping ``.apple_a01.wrapp``
    is fine — same-name install markers are allowed by
    ``_check_existing_package``.
    """
    source_a = sample_source_copy
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()

    created_v1 = await create_simready_package(
        "apple_a01",
        "1.0.0",
        "MIT",
        str(source_a),
        str(repo_a),
        root_usds=[APPLE_ROOT_USD],
    )
    assert isinstance(created_v1, CreatedPackage)

    working_b = tmp_path / "working_b" / "apple_a01" / "simready_usd"
    working_b.mkdir(parents=True)
    await _wrapp_install("apple_a01", "1.0.0", repo_a, working_b)

    extra_file = working_b / EXTRA_FILE_RELPATH
    extra_file.parent.mkdir(parents=True, exist_ok=True)
    extra_file.write_text(EXTRA_FILE_BODY)

    (working_b / PACKAGE_DEF_NAME).unlink()
    shutil.rmtree(working_b / ".metadata")

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()

    created_v2 = await create_simready_package(
        "apple_a01",
        "1.1.0",
        "MIT",
        str(working_b),
        str(repo_b),
        root_usds=[APPLE_ROOT_USD],
    )
    assert isinstance(created_v2, CreatedPackage)

    pkg_dir_v1 = repo_a / ".packages" / "apple_a01" / "1.0.0"
    pkg_dir_v2 = repo_b / ".packages" / "apple_a01" / "1.1.0"

    bom_v1 = _bom_relpaths(pkg_dir_v1 / BOM_RELPATH)
    bom_v2 = _bom_relpaths(pkg_dir_v2 / BOM_RELPATH)

    assert EXTRA_FILE_RELPATH in bom_v2, (
        f"v1.1.0 BOM is missing the new file: {sorted(bom_v2)}"
    )
    assert EXTRA_FILE_RELPATH not in bom_v1, (
        f"v1.0.0 BOM unexpectedly already contained {EXTRA_FILE_RELPATH}: "
        f"{sorted(bom_v1)}"
    )

    def_v1 = json.loads((pkg_dir_v1 / PACKAGE_DEF_NAME).read_text())
    def_v2 = json.loads((pkg_dir_v2 / PACKAGE_DEF_NAME).read_text())
    assert "1.0.0" in def_v1["package_id"], def_v1["package_id"]
    assert "1.1.0" in def_v2["package_id"], def_v2["package_id"]

    _assert_stage_loads(pkg_dir_v2 / APPLE_ROOT_USD)

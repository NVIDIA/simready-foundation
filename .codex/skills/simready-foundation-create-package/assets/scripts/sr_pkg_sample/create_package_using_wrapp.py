"""Build a SimReady-conformant package using WRAPP.

This is the create phase of the SimReady packaging workflow.  It
orchestrates pre-flight checks, ``wrapp.create``, metadata generation,
and catalog patching — all delegated to the ``wrapp_compat``
sub-package, which houses the WRAPP 2.2 workarounds that WRAPP 2.3
will absorb natively.

The public entry point is :func:`create_package`.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse

import wrapp
from wrapp.utils.storage import wrapp_url_is_folder
from wrapp.utils.utils import normalize_url

from ._conformance_writer import (
    CONFORMANCE_PREFIX,
    ROOT_USDS_FILENAME,
)
from ._package_def import CreatedPackage
from .wrapp_compat.checks import check_existing_package
from .wrapp_compat.create_and_emit import (
    METADATA_FOLDER,
    create_package_wrapp,
)
from .wrapp_compat.std_pkg_def import _hash_bytes, default_hash_algos
from .errors import BuildFailed, UsageError


def _source_to_local_path(source: str) -> Path | None:
    """Resolve *source* to a local :class:`Path`, or ``None`` for remote URLs."""
    normalized = normalize_url(source)
    if normalized.startswith("file://"):
        return Path(unquote(urlparse(normalized).path))
    if "://" in normalized:
        return None
    return Path(normalized)


async def _verify_and_collect_metadata(
    source: str,
    scheduler_node,
    *,
    sha256_only: bool = False,
) -> list[dict]:
    """Scan ``source/.metadata/`` for pre-validation conformance files.

    If conformance files with ``content_hash`` are found, recomputes
    the BOM-derived content hash from the current source files and
    compares.  A mismatch means the source changed after
    pre-validation — the build is aborted so the user can re-run
    pre-validation.

    Returns a list of ``{"name": ..., "hash": {"sha256": ..., ...}}``
    dicts ready for insertion into the package definition's ``metadata``
    array, covering every verified conformance file and
    ``root_usds.json`` (but NOT the BOM — ``std_pkg_def`` handles that
    separately).  Returns an empty list when no conformance files are
    found (the package definition will only carry the BOM entry).
    """
    local = _source_to_local_path(source)
    if local is None:
        return []

    metadata_dir = local / METADATA_FOLDER
    if not metadata_dir.is_dir():
        return []

    conformance_files = sorted(
        p for p in metadata_dir.iterdir()
        if p.is_file()
        and p.name.startswith(CONFORMANCE_PREFIX)
        and p.name.endswith(".json")
    )
    if not conformance_files:
        return []

    files_with_hash = []
    for cf in conformance_files:
        data = json.loads(cf.read_text(encoding="utf-8"))
        ch = data.get("content_hash")
        if ch is not None:
            files_with_hash.append((cf, ch))

    if files_with_hash:
        from ._bom import compute_bom, compute_content_hash

        # ``compute_bom`` structurally excludes the package definition,
        # the entire ``.metadata/`` tree and ``*.wrapp`` files — that
        # matches the spec's "content-only" view of the package
        # (PKG.BOM.001), so no caller-driven ``exclude`` set is needed.
        bom = await compute_bom(
            source, sha256_only=sha256_only, scheduler_node=scheduler_node,
        )
        fresh_hash = compute_content_hash(bom["items"], sha256_only=sha256_only)
        assert fresh_hash is not None, (
            "compute_bom returned items without SHA-256 hashes"
        )
        for cf, expected in files_with_hash:
            if fresh_hash.get("sha256") != expected.get("sha256"):
                raise BuildFailed(
                    f"content_hash mismatch for {cf.name}: the source files "
                    f"have changed since pre-validation.  Re-run "
                    f"pre-validation, or remove the .metadata/ directory "
                    f"from the source folder to proceed without conformance "
                    f"metadata in the package definition."
                )

    hash_algos = default_hash_algos(sha256_only)
    entries: list[dict] = []
    for cf in conformance_files:
        entries.append({
            "name": cf.name,
            "hash": _hash_bytes(cf.read_bytes(), hash_algos),
        })

    root_usds_path = metadata_dir / ROOT_USDS_FILENAME
    if root_usds_path.is_file():
        entries.append({
            "name": ROOT_USDS_FILENAME,
            "hash": _hash_bytes(root_usds_path.read_bytes(), hash_algos),
        })

    return entries


async def create_package(
    name: str,
    version: str,
    license_id: str,
    source: str,
    repo: str,
    *,
    sha256_only: bool = False,
) -> CreatedPackage:
    """Build a SimReady-conformant package from ``source`` into ``repo``.

    Parameters
    ----------
    name, version:
        Package coordinates; combined into the SimReady ``package_id``
        (``<prefix>.<name>.<version>``).
    license_id:
        SPDX licence identifier copied verbatim into the package
        definition (e.g. ``MIT``, ``Apache-2.0``).
    source:
        Path or URL of the folder to publish.  Any storage scheme the
        installed WRAPP wheel supports is accepted (local paths,
        ``file://``, ``s3://``, ``omniverse://``, ...).
    repo:
        Path or URL of the WRAPP repository to publish into.
    sha256_only:
        When ``True``, only SHA-256 hashes are computed.  When
        ``False`` (the default), BLAKE3 hashes are included alongside
        SHA-256 when the ``blake3`` library is importable.

    Returns
    -------
    CreatedPackage
        URLs of the freshly written package-definition file and BOM
        sidecar.  Pass ``CreatedPackage.pkg_def_url`` to
        :func:`sr_pkg_sample.post_validate` to verify the new package.

    Raises
    ------
    UsageError
        Source is not a directory, already carries a ``.wrapp`` marker
        for a different package, or holds nested ``.wrapp`` subpackages
        that aren't supported by the SimReady standard yet.
    BuildFailed
        Any other failure during the build (WRAPP error, I/O error,
        ...).  The original exception is reachable through
        :attr:`BuildFailed.__cause__`.
    """
    hash_algos = default_hash_algos(sha256_only)
    try:
        async with wrapp.ContextManager() as scheduler:
            if not await wrapp_url_is_folder(source):
                raise UsageError(f"source is not a directory: {source}")

            existing_err = await check_existing_package(source, name)
            if existing_err is not None:
                raise UsageError(existing_err)

            extra_metadata = await _verify_and_collect_metadata(
                source, scheduler.parent_task_node(),
                sha256_only=sha256_only,
            )

            pkg_def_url, bom_url, marker_url = await create_package_wrapp(
                name, version, license_id, source, repo,
                extra_metadata=extra_metadata,
                hash_algos=hash_algos,
                scheduler=scheduler,
            )
    except UsageError:
        raise
    except Exception as exc:
        raise BuildFailed(f"WRAPP build failed: {exc}") from exc

    return CreatedPackage(pkg_def_url=pkg_def_url, bom_url=bom_url, marker_url=marker_url)

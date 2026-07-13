"""BOM computation and content-hash derivation via WRAPP's storage layer.

Provides :func:`compute_bom` to walk a source folder (local or remote)
and build the ``com.nvidia.simready.packaging.bom.json`` data structure
with per-file hashes, plus :func:`compute_content_hash` which
implements the deterministic PKG.HASH.001 content hash from those
per-file hashes.

These functions will be absorbed into WRAPP in a future release; this
module provides them in the meantime so the packaging sample can
produce conformance metadata with the current WRAPP 2.2.0 wheel.
"""

from __future__ import annotations

from typing import Optional

from ._package_def import PACKAGING_DEFINITION_FILENAME
from .wrapp_compat.std_pkg_def import (
    STANDARD_FORMAT_VERSION,
    FileHashResult,
    HashAlgorithms,
    compute_hashes_from_path,
    default_hash_algos,
    hash_files,
)


async def compute_bom(
    source: str,
    *,
    sha256_only: bool = False,
    scheduler_node=None,
) -> dict:
    """Build a BOM dict from *source*, computing per-file hashes.

    Walks *source* recursively via WRAPP's storage router so the same
    code works for local paths, ``file://``, ``s3://`` etc.

    Three kinds of paths are *always* excluded because they are never
    package content, keeping the BOM aligned with PKG.BOM.001's
    "content-only" view and matching what ``wrapp.create`` packs into
    a ``.wrapp`` catalog:

    * the package definition file
      (``com.nvidia.simready.packaging.json``) at the package root,
    * anything under the reserved ``.metadata/`` folder
      (BOM, conformance metadata, root-USDs list, …), and
    * any ``*.wrapp`` file (install markers / package-container
      artifacts).

    Excluding them here keeps pre-validation's BOM identical to the
    post-creation BOM produced by
    :func:`wrapp_compat.std_pkg_def.generate_bom_metadata` so the
    ``content_hash`` matches across phases.

    Parameters
    ----------
    source:
        Root folder to inventory.  Any WRAPP-supported scheme.
    sha256_only:
        When ``True``, only compute SHA-256 hashes.  When ``False``
        (the default), BLAKE3 hashes are included alongside SHA-256
        when the ``blake3`` library is importable.
    scheduler_node:
        WRAPP scheduler node for concurrent downloads; pass
        ``scheduler.parent_task_node()`` when running inside a
        ``WrappSchedulerCLI`` context.

    Returns
    -------
    dict
        Standard BOM structure:
        ``{"format_version": "1.0", "content_root": ..., "items": [...]}``.
    """
    from wrapp.utils.storage import wrapp_list_file_tree
    from wrapp.utils.utils import join_paths, normalize_url

    from .errors import BuildFailed

    algos = default_hash_algos(sha256_only)
    source_normalized = normalize_url(source)

    items: list[dict] = []
    urls: list[str] = []

    try:
        async for entry in wrapp_list_file_tree(source):
            if not entry.is_regular_file:
                continue
            rel = entry.relative_path
            if _is_structural_exclusion(rel):
                continue
            url = join_paths(source_normalized, rel)
            items.append({"relative_path": rel, "size": entry.size or 0})
            urls.append(url)
    except NotImplementedError as exc:
        raise BuildFailed(
            f"the storage backend for {source!r} does not support "
            f"recursive file listing, which is required for BOM "
            f"computation.  Use a local path or a storage backend "
            f"with recursive listing support."
        ) from exc

    if urls and scheduler_node is not None:
        results = await hash_files(urls, algos, scheduler_node)
        for bom_item, result in zip(items, results):
            bom_item["hash"] = result.hashes
            bom_item["size"] = result.size
    elif urls:
        for bom_item, url in zip(items, urls):
            result = _hash_local(url, algos)
            bom_item["hash"] = result.hashes
            bom_item["size"] = result.size

    return {
        "format_version": STANDARD_FORMAT_VERSION,
        "content_root": source,
        "items": items,
    }


_METADATA_PREFIX = ".metadata/"
_WRAPP_SUFFIX = ".wrapp"


def _is_structural_exclusion(rel: str) -> bool:
    """Return True for paths that are never package content.

    Mirrors the structural exclusions in
    :func:`wrapp_compat.std_pkg_def.generate_bom_metadata` so the BOM
    pre-validation computes is identical to the BOM ``wrapp.create`` +
    ``std_pkg_def`` produce, keeping ``content_hash`` consistent
    across the pre/post creation handoff.
    """
    if rel == PACKAGING_DEFINITION_FILENAME:
        return True
    if rel == ".metadata" or rel.startswith(_METADATA_PREFIX):
        return True
    # ``.<package>.wrapp`` install markers (left behind by
    # ``wrapp.install``) and any other ``.wrapp`` container files —
    # these are catalog artefacts, never standalone content.
    if rel.endswith(_WRAPP_SUFFIX):
        return True
    return False


def _hash_local(url: str, algos: HashAlgorithms) -> FileHashResult:
    """Hash a single local file (fallback when no scheduler node is available)."""
    from wrapp.utils.utils import normalize_url

    path = normalize_url(url)
    if path.startswith("file://"):
        from urllib.parse import unquote, urlparse

        path = unquote(urlparse(path).path)
    return compute_hashes_from_path(path, algos)


def compute_content_hash(
    bom_items: list, *, sha256_only: bool = False,
) -> Optional[dict[str, str]]:
    """Compute the content_hash per PKG.HASH.001.

    Returns ``{"sha256": "<hex>", ...}``, or ``None`` if any BOM item
    is missing its SHA-256 hash.  When *sha256_only* is ``False``
    (the default) and ``blake3`` is available, a ``"blake3"`` key is
    added.
    """
    from .wrapp_compat.std_pkg_def import _hash_bytes

    for item in bom_items:
        if "hash" not in item or "sha256" not in item["hash"]:
            return None

    sorted_items = sorted(
        bom_items, key=lambda item: item["relative_path"].encode("utf-8")
    )

    buf = bytearray()
    for item in sorted_items:
        buf.extend(item["relative_path"].encode("utf-8"))
        buf.append(0x00)
        buf.extend(bytes.fromhex(item["hash"]["sha256"]))

    return _hash_bytes(bytes(buf), default_hash_algos(sha256_only))

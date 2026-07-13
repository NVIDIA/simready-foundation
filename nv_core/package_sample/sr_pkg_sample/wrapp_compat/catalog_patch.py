"""Patch the ``.wrapp`` catalog to include SimReady metadata files.

After ``wrapp.create``, the ``.wrapp`` catalog only lists files that
were in the source tree at create time.  The SimReady metadata JSONs
that get written *after* the create — the package definition, the
freshly-recomputed BOM, and any post-creation conformance evidence
written by ``post_validate`` — therefore need to be injected into the
catalog explicitly.  Without this patch, ``wrapp export`` /
``wrapp install`` would silently drop them.

WRAPP 2.3 is expected to support a ``metadata`` concept natively,
making this post-hoc patching unnecessary.
"""

from __future__ import annotations

import io

import wrapp
from wrapp.datastructures.catalog import CatalogItem
from wrapp.datastructures.package import read_package_info, write_package_info
from wrapp.utils.nucleus_hash import calc_nucleus_hash_from_stream


def metadata_catalog_item(relative_path: str, source_path: str, payload: bytes) -> CatalogItem:
    """Build a ``CatalogItem`` for a metadata JSON whose bytes we hold in memory.

    Computes the Nucleus-format hash (``sha-256-flat;1048576;<hex>``) and size
    directly from ``payload`` so we do not re-fetch the file we just wrote.
    """
    nucleus_hash, size = calc_nucleus_hash_from_stream(io.BytesIO(payload))
    return CatalogItem(
        source_path=source_path,
        relative_path=relative_path,
        hash=nucleus_hash,
        size=size,
    )


async def augment_wrapp_catalog(
    wrapp_marker_url: str,
    *,
    files: list[tuple[str, str, bytes]],
    context: wrapp.CommandParameters,
) -> None:
    """Add (or replace) catalog entries for the given files and resave.

    Reads the freshly-written marker, merges *files* into ``catalog.items``
    so that any pre-existing entry with the same ``relative_path`` is
    overwritten with the new payload's hash / size, sorts the result by
    ``relative_path`` to preserve WRAPP's invariant, and saves the
    catalog back.

    :param wrapp_marker_url: URL of the ``.<name>.wrapp`` marker to patch.
    :param files: List of ``(relative_path, source_url, payload)`` tuples
        to inject.  ``relative_path`` is the path inside the package
        (forward-slash separated, e.g. ``com.nvidia.simready.packaging.json``
        or ``.metadata/com.nvidia.simready.packaging.bom.json``).
        ``source_url`` is the absolute URL of the freshly-written file
        in the repo (used as the catalog item's ``source_path``).
        ``payload`` is the raw bytes of the file (used to compute the
        Nucleus hash and size without a re-read).
    :param context: WRAPP command parameters passed to
        :func:`wrapp.write_package_info`.
    :raises RuntimeError: When the marker has no catalog (should never
        happen for a freshly-created package).
    """
    if not files:
        return

    package_info = await read_package_info(wrapp_marker_url)
    if package_info is None or package_info.catalog is None:
        raise RuntimeError(
            f"WRAPP marker at {wrapp_marker_url} unexpectedly has no catalog"
        )

    new_items = {
        rel: metadata_catalog_item(rel, source_url, payload)
        for rel, source_url, payload in files
    }

    # Drop any existing entries with the same ``relative_path`` so the
    # caller's payload wins.  This keeps the catalog minimal — without
    # this dedup step ``augment_wrapp_catalog`` would create a duplicate
    # entry every time it's called for a path that already came in via
    # ``wrapp.create``'s source scan (e.g. the BOM, which pre-validation
    # writes into source/.metadata/ before create freezes the catalog).
    package_info.catalog.items = [
        item
        for item in package_info.catalog.items
        if item.relative_path not in new_items
    ]
    package_info.catalog.items.extend(new_items.values())
    package_info.catalog.items.sort(key=lambda item: item.relative_path)

    await write_package_info(wrapp_marker_url, package_info, context=context)

"""WRAPP create + SimReady metadata emission.

Orchestrates the sequence that WRAPP 2.3 would perform natively:

1. ``wrapp.create`` to freeze the source tree into a WRAPP package.
2. Post-create nested-subpackage check.
3. ``std_pkg_def`` to produce the package definition and BOM.
4. Inject extra metadata (pre-validation conformance files).
5. Write the two JSON files through WRAPP's storage layer.
6. Patch the ``.wrapp`` catalog so the JSONs ride along in exports.

The public entry point is :func:`create_package_wrapp`.
"""

from __future__ import annotations

import json

import wrapp
from wrapp.utils.storage import wrapp_write_file_content
from wrapp.utils.storage_interface import Result
from wrapp.utils.utils import join_paths

from .catalog_patch import augment_wrapp_catalog
from .checks import check_no_nested_subpackages
from .std_pkg_def import (
    HashAlgorithms,
    compute_package_hash,
    default_hash_algos,
    std_pkg_def,
)

PACKAGING_DEFINITION_FILENAME = "com.nvidia.simready.packaging.json"
BOM_METADATA_FILENAME = "com.nvidia.simready.packaging.bom.json"
METADATA_FOLDER = ".metadata"
PACKAGE_ID_PREFIX = "com.nvidia.simready"


def inject_extra_metadata(
    definition: dict,
    extra_metadata: list[dict],
    *,
    hash_algos: HashAlgorithms | None = None,
) -> None:
    """Add verified conformance entries to the definition and recompute package_hash.

    Mutates *definition* in place: extends ``metadata``, re-sorts it,
    and — when ``content_hash`` is present — recomputes ``package_hash``
    so it covers the full metadata array.
    """
    if not extra_metadata:
        return

    if hash_algos is None:
        hash_algos = default_hash_algos()

    definition.setdefault("metadata", []).extend(extra_metadata)
    definition["metadata"].sort(key=lambda e: e["name"])

    if "content_hash" in definition and "package_hash" in definition:
        definition["package_hash"] = compute_package_hash(
            definition["package_id"],
            definition["license"],
            definition["content_hash"],
            definition["metadata"],
            hash_algos=hash_algos,
        )


async def create_package_wrapp(
    name: str,
    version: str,
    license_id: str,
    source: str,
    repo: str,
    *,
    extra_metadata: list[dict],
    hash_algos: HashAlgorithms | None = None,
    scheduler: wrapp.Scheduler,
) -> tuple[str, str, str]:
    """Run ``wrapp.create`` + ``std_pkg_def``, write the JSON outputs, and patch the catalog.

    This is the sequence that WRAPP 2.3's native ``create`` +
    ``std-pkg-def`` would perform in a single command.

    Returns ``(pkg_def_url, bom_url, marker_url)``.  The marker URL is
    returned so that follow-up phases (e.g. post-validation) can patch
    additional metadata into the catalog by calling
    :func:`augment_wrapp_catalog` again.
    """
    if hash_algos is None:
        hash_algos = default_hash_algos()

    pkg_dir_url = join_paths(repo, ".packages", name, version)
    wrapp_marker_url = join_paths(pkg_dir_url, f".{name}.wrapp")
    pkg_def_url = join_paths(pkg_dir_url, PACKAGING_DEFINITION_FILENAME)
    bom_url = join_paths(pkg_dir_url, METADATA_FOLDER, BOM_METADATA_FILENAME)

    context = wrapp.CommandParameters()

    await wrapp.create(
        name,
        version,
        source=source,
        catalog=False,
        repo=repo,
        scheduler=scheduler,
    )

    nested_err = await check_no_nested_subpackages(wrapp_marker_url)
    if nested_err is not None:
        from ..errors import UsageError
        raise UsageError(nested_err)

    std_result = await std_pkg_def(
        wrapp_marker_url,
        license_id,
        package_id_prefix=PACKAGE_ID_PREFIX,
        hash_algos=hash_algos,
        scheduler=scheduler,
    )

    inject_extra_metadata(std_result.definition, extra_metadata, hash_algos=hash_algos)

    def_json = json.dumps(std_result.definition, indent=2)
    bom_json = json.dumps(std_result.bom, indent=2)

    def_result = await wrapp_write_file_content(context, pkg_def_url, def_json)
    if def_result != Result.OK:
        raise RuntimeError(
            f"WRAPP write failed for package definition at {pkg_def_url}: {def_result}"
        )
    bom_result = await wrapp_write_file_content(context, bom_url, bom_json)
    if bom_result != Result.OK:
        raise RuntimeError(
            f"WRAPP write failed for BOM at {bom_url}: {bom_result}"
        )

    await augment_wrapp_catalog(
        wrapp_marker_url,
        files=[
            (PACKAGING_DEFINITION_FILENAME, pkg_def_url, def_json.encode("utf-8")),
            (
                f"{METADATA_FOLDER}/{BOM_METADATA_FILENAME}",
                bom_url,
                bom_json.encode("utf-8"),
            ),
        ],
        context=context,
    )

    return pkg_def_url, bom_url, wrapp_marker_url

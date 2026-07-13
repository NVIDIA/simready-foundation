#!/usr/bin/env python3
# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
"""Standalone port of WRAPP 2.3.0's ``wrapp std-pkg-def`` command for WRAPP 2.2.0.

Generate a standard-compliant SimReady Asset Package definition
(``com.nvidia.simready.packaging.json``) and its BOM sidecar
(``.metadata/com.nvidia.simready.packaging.bom.json``) for a single package
in a WRAPP repository.

This module ships inside ``package_sample/sr_pkg_sample/`` so the sample can run
against the publicly released WRAPP 2.2.0 wheel from NGC (which does not
yet ship ``wrapp std-pkg-def`` — that command was added in 2.3.0).  It
reuses every 2.2.0 wrapp public primitive and inlines the small
``wrapp.utils.file_hasher`` module that was only introduced in 2.3.0
(adjusted to use 2.2.0's ``wrapp_get_cached_file`` instead of 2.3.0's
``wrapp_access_local_copy``).

``sr_pkg_sample.create_package_using_wrapp`` imports the :func:`std_pkg_def`
coroutine directly; the typer CLI below is preserved so the file is
still runnable as a ``wrapp std-pkg-def`` stand-in (handy for debugging
without the rest of the sample).

Prerequisites
-------------
- WRAPP 2.2.0 importable in the current Python environment.

Usage
-----
    python std_pkg_def_standalone.py <package> <version> \\
        --repo <repo-url> --license <SPDX-id> \\
        [--package-id-prefix com.nvidia.simready] \\
        [--output local-path.json] [--overwrite] \\
        [standard wrapp flags: --auth, --jobs, --verbose, ...]

Run ``python std_pkg_def_standalone.py --help`` for the full list.
"""
import hashlib
import json
import logging
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    BinaryIO,
    Dict,
    List,
    Optional,
    Sequence,
)

try:
    import blake3 as _blake3_mod
    BLAKE3_AVAILABLE = True
except ImportError:
    _blake3_mod = None
    BLAKE3_AVAILABLE = False

import typer

from wrapp.app import (
    measure_time,
    print_stats,
)
from wrapp.datastructures.authentication import capture_auth
from wrapp.datastructures.catalog import (
    Catalog,
    CatalogItem,
)
from wrapp.datastructures.command_context import (
    CommandParameters,
    SchedulerContext,
    WrappSchedulerCLI,
    context_from_params,
    log_exception_and_raise_exit,
)
from wrapp.datastructures.package import (
    PackageInfo,
    load_package_setup,
    wrapp_file_in_repo,
)
from wrapp.options import (
    AuthOption,
    DebugLevelFlag,
    InteractiveAuthFlag,
    JobsNumber,
    JsonLoggingFlag,
    LogFileOption,
    OverwriteFlag,
    ProgressReportOption,
    RepoRequiredOption,
    StatsFlag,
    TimeFlag,
    VerboseFlag,
)
from wrapp.repo.repository import Repository
from wrapp.utils.api_marker import wrapp_public_api
from wrapp.utils.cli_progress_printer import ProgressReportVerbosity
from wrapp.utils.coro import (
    async_typer,
    force_wrapp_thread,
)
from wrapp.utils.ensure_scheduler import ensure_scheduler
from wrapp.utils.logging import log_args
from wrapp.utils.nucleus_hash import (
    _NUCLEUS_SHA_HEADER,
    is_nucleus_hash,
)
from wrapp.utils.storage import (
    Result,
    wrapp_get_cached_file,
    wrapp_stat,
    wrapp_write_file_content,
)
from wrapp.utils.task_throttler import CPUThrottler
from wrapp.utils.utils import (
    FailedCommand,
    StorageOperationError,
    join_paths,
    normalize_url,
)
from wrapp.utils.wrapp_init_for_cmd import wrapp_init_for_cmd

logger = logging.getLogger("omni.wrapp")

PACKAGING_DEFINITION_FILENAME = "com.nvidia.simready.packaging.json"
BOM_METADATA_FILENAME = "com.nvidia.simready.packaging.bom.json"
METADATA_FOLDER = ".metadata"
STANDARD_FORMAT_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Inlined from wrapp.utils.file_hasher (new in WRAPP 2.3.0).
#
# ``HashAlgorithms`` / ``FileHashResult`` / ``compute_hashes_from_stream`` /
# ``compute_hashes_from_path`` are copied verbatim from 2.3.0.  ``hash_files``
# is rewritten against 2.2.0's ``wrapp_get_cached_file`` (2.3.0's
# ``wrapp_access_local_copy`` does not exist at 2.2.0).
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class HashAlgorithms:
    """Flags selecting which hash algorithms to compute.  At least one must be True."""

    nucleus: bool = False
    sha256: bool = False
    blake3: bool = False


def default_hash_algos(sha256_only: bool = False) -> HashAlgorithms:
    """Build the standard ``HashAlgorithms`` for packaging hash objects.

    SHA-256 is always enabled (MUST per PKG.HASH.001).  BLAKE3 is
    enabled unless *sha256_only* is ``True`` or the ``blake3`` library
    is not importable.
    """
    return HashAlgorithms(
        sha256=True,
        blake3=not sha256_only and BLAKE3_AVAILABLE,
    )


@dataclass
class FileHashResult:
    """Result of hashing a single file."""

    hashes: Dict[str, str] = field(default_factory=dict)
    size: int = 0


def compute_hashes_from_stream(f: BinaryIO, algos: HashAlgorithms) -> FileHashResult:
    """Read *f* in 1 MB chunks and compute the requested hashes in a single pass."""
    sha256_h = hashlib.sha256() if algos.sha256 else None
    blake3_h = _blake3_mod.blake3() if (algos.blake3 and _blake3_mod is not None) else None
    nucleus_chunk_digests: Optional[list] = [] if algos.nucleus else None

    first_chunk: Optional[bytes] = None
    total_size = 0

    while True:
        chunk = f.read(_CHUNK_SIZE)
        if not chunk:
            break

        if sha256_h is not None:
            sha256_h.update(chunk)
        if blake3_h is not None:
            blake3_h.update(chunk)
        if nucleus_chunk_digests is not None:
            nucleus_chunk_digests.append(hashlib.sha256(chunk).digest())

        if first_chunk is None:
            first_chunk = chunk
        total_size += len(chunk)

    hashes: Dict[str, str] = {}

    if sha256_h is not None:
        hashes["sha256"] = sha256_h.hexdigest()

    if blake3_h is not None:
        hashes["blake3"] = blake3_h.hexdigest()

    if nucleus_chunk_digests is not None:
        n = hashlib.sha256()
        for d in nucleus_chunk_digests:
            n.update(d)
        hashes["nucleus"] = _NUCLEUS_SHA_HEADER + n.hexdigest()

    if total_size > _CHUNK_SIZE and first_chunk is not None:
        if sha256_h is not None:
            hashes["sha256-first1m"] = hashlib.sha256(first_chunk).hexdigest()

    return FileHashResult(hashes=hashes, size=total_size)


def compute_hashes_from_path(path: str, algos: HashAlgorithms) -> FileHashResult:
    """Open a local file and compute the requested hashes via :func:`compute_hashes_from_stream`."""
    with open(path, "rb") as f:
        return compute_hashes_from_stream(f, algos)


async def hash_files(
    urls: Sequence[str],
    algos: HashAlgorithms,
    parent_node,
) -> List[FileHashResult]:
    """Download and hash multiple remote files concurrently (WRAPP 2.2.0 variant).

    Each file is fetched via 2.2.0's :func:`wrapp_get_cached_file` (which returns
    a ``LocalReadOnlyFile`` with ``.local_path()`` / ``.close()``), and hashed in
    a :class:`CPUThrottler` thread so neither downloads nor CPU work block the
    event loop.

    Returns a list of :class:`FileHashResult` in the same order as *urls*.
    On failure the error propagates immediately.
    """
    results: List[Optional[FileHashResult]] = [None] * len(urls)

    async def _hash_one(idx: int, url: str) -> None:
        status, cache_file = await wrapp_get_cached_file(url, download=True)
        if status != Result.OK or cache_file is None:
            raise StorageOperationError(f"failed to fetch {url} for hashing: {status}")
        try:
            holder: list = []
            await CPUThrottler.me().process_local_task_multi_threaded(
                holder.append,
                compute_hashes_from_path,
                cache_file.local_path(),
                algos,
            )
            results[idx] = holder[0]
        finally:
            cache_file.close()

    async with parent_node.create_task_group_node("hash files") as tg:
        for idx, url in enumerate(urls):
            tg.create_task(_hash_one(idx, url))

    return results  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(add_completion=False)


LicenseOption = typer.Option(
    ...,
    "--license",
    help='SPDX license identifier (e.g. "Apache-2.0", "LicenseRef-NVIDIA-Proprietary")',
)

PackageIdPrefixOption = typer.Option(
    None,
    "--package-id-prefix",
    help='Optional prefix for the package_id (e.g. "com.nvidia.simready" → package_id becomes prefix.name.version)',
)

NoHashesFlag = typer.Option(
    False,
    "--no-hashes",
    help="Skip computing file-level hashes and content_hash/package_hash (avoids downloading file content)",
)

OutputOption = typer.Option(
    None,
    "--output",
    "-o",
    help="Write the definition to a local file instead of alongside the package in the repo",
)


@app.command(name="std-pkg-def")
@measure_time
@print_stats
@wrapp_init_for_cmd
@capture_auth
@async_typer
async def std_pkg_def_command(
    package: str = typer.Argument(..., help="package name"),
    version: str = typer.Argument(..., help="version"),
    repo: str = RepoRequiredOption,
    license_id: str = LicenseOption,
    package_id_prefix: Optional[str] = PackageIdPrefixOption,
    no_hashes: bool = NoHashesFlag,
    output: Optional[str] = OutputOption,
    overwrite: bool = OverwriteFlag,
    auth: Optional[List[str]] = AuthOption,
    interactive_auth: bool = InteractiveAuthFlag,
    jobs: int = JobsNumber,
    debug: bool = DebugLevelFlag,
    json_logging: bool = JsonLoggingFlag,
    verbose: bool = VerboseFlag,
    progress_report: ProgressReportVerbosity = ProgressReportOption,
    stats: bool = StatsFlag,
    log_file: str = LogFileOption,
    time: bool = TimeFlag,
) -> None:
    """
    Generate a standard-compliant package definition (com.nvidia.simready.packaging.json)
    for a single package in a repository.

    By default writes the file alongside the package in the repo.
    Use --output to write to a local file instead.
    """
    context, scheduler_params = context_from_params()
    try:
        repo_object = Repository(repo_url=repo)
        wrapp_url = wrapp_file_in_repo(repo_object, package, version)

        async with WrappSchedulerCLI(params=scheduler_params) as scheduler:
            result = await std_pkg_def(
                wrapp_url,
                license_id,
                package_id_prefix=package_id_prefix,
                compute_hashes=not no_hashes,
                context=context,
                scheduler=scheduler,
            )

            definition_json = json.dumps(result.definition, indent=2)
            bom_json = json.dumps(result.bom, indent=2)

            if output:
                if not overwrite:
                    await _check_not_exists(output)
                await wrapp_write_file_content(context, output, definition_json)
                logger.info(f"Wrote standard package definition to {output}")
            else:
                package_version_url = repo_object.package_url(package, version)
                definition_url = join_paths(package_version_url, PACKAGING_DEFINITION_FILENAME)
                bom_url = join_paths(package_version_url, METADATA_FOLDER, BOM_METADATA_FILENAME)

                if not overwrite:
                    await _check_not_exists(definition_url)
                    await _check_not_exists(bom_url)

                await wrapp_write_file_content(context, definition_url, definition_json)
                logger.info(f"Wrote standard package definition at {definition_url}")

                await wrapp_write_file_content(context, bom_url, bom_json)
                logger.info(f"Wrote BOM metadata at {bom_url}")

    except FailedCommand as e:
        logger.error(f"Failure generating standard package definition for {package} {version}: {e}")
        raise typer.Exit(1)
    except StorageOperationError as e:
        logger.error(f"Error generating standard package definition for {package} {version}: {e}")
        raise typer.Exit(2)
    except Exception as e:
        log_exception_and_raise_exit(e, context)


async def _check_not_exists(url: str) -> None:
    """Raise FailedCommand if *url* already exists in the repo."""
    result, _ = await wrapp_stat(url)
    if result == Result.OK:
        raise FailedCommand(f"file already exists and --overwrite is not specified: {url}")
    if result != Result.ERROR_NOT_FOUND:
        raise StorageOperationError(f"error checking {url}: {result}")


@dataclass
class StandardPackageResult:
    """Holds the generated standard package definition and BOM."""

    definition: dict
    bom: dict


@force_wrapp_thread
@ensure_scheduler
@wrapp_public_api
@log_args
async def std_pkg_def(
    wrapp_url: str,
    license_id: str,
    *,
    package_id_prefix: Optional[str] = None,
    compute_hashes: bool = True,
    hash_algos: Optional[HashAlgorithms] = None,
    context: CommandParameters = CommandParameters(),
    scheduler: Optional[SchedulerContext] = None,
) -> StandardPackageResult:
    """
    Generate a standard-compliant package definition and BOM for a WRAPP package.

    Loads the package from *wrapp_url*, builds the package definition and BOM
    metadata dicts, and — when *compute_hashes* is True — downloads file content
    to compute per-file, content-level, and package-level hashes.

    :param wrapp_url: URL of the .wrapp file in a repository
    :param license_id: SPDX license identifier (e.g., "Apache-2.0", "LicenseRef-NVIDIA-Proprietary")
    :param package_id_prefix: Optional prefix for the package_id (e.g. "com.nvidia.simready")
    :param compute_hashes: Whether to download files and compute all hashes (default True)
    :param hash_algos: Algorithm selection (default: SHA-256 + BLAKE3 when available)
    :param context: Optionally, global configuration parameters.
    :param scheduler: Optionally pre-constructed SchedulerContext.
    :return: StandardPackageResult containing the definition and BOM dicts
    :raises FailedCommand: When the package cannot be loaded
    """
    if hash_algos is None:
        hash_algos = default_hash_algos()
    if scheduler is None:
        raise RuntimeError("No scheduler present and ensure_scheduler malfunctioned, program error!")

    package_info = await load_package_setup(wrapp_url)
    if package_info is None:
        raise FailedCommand(f"Could not load package at {wrapp_url}")

    definition = generate_package_definition(package_info, license_id, package_id_prefix=package_id_prefix)
    bom = generate_bom_metadata(package_info)

    if bom["items"] and compute_hashes:
        assert package_info.catalog is not None
        await _compute_file_hashes_for_bom(
            bom, package_info.catalog, scheduler.parent_task_node(),
            hash_algos=hash_algos,
        )

    if compute_hashes:
        bom_json = json.dumps(bom, indent=2)
        content_hash_obj = compute_content_hash(bom["items"], hash_algos=hash_algos)
        if content_hash_obj is not None:
            bom_hash_obj = _hash_bytes(bom_json.encode("utf-8"), hash_algos)
            for entry in definition.get("metadata", []):
                if entry["name"] == BOM_METADATA_FILENAME:
                    entry["hash"] = bom_hash_obj
            definition["content_hash"] = content_hash_obj
            definition["package_hash"] = compute_package_hash(
                definition["package_id"],
                definition["license"],
                content_hash_obj,
                definition.get("metadata", []),
                hash_algos=hash_algos,
            )

    return StandardPackageResult(definition=definition, bom=bom)


@wrapp_public_api
def generate_package_definition(
    package: PackageInfo,
    license_id: str,
    *,
    package_id_prefix: Optional[str] = None,
) -> dict:
    """
    Generate a standard-compliant package definition dict from a WRAPP PackageInfo.

    Produces a dict conforming to the SimReady Asset Package specification.
    The caller is responsible for serializing and writing the result to storage.

    :param package: A loaded PackageInfo (from any WRAPP repo, redirect or otherwise)
    :param license_id: SPDX license identifier (e.g., "Apache-2.0", "LicenseRef-NVIDIA-Proprietary")
    :param package_id_prefix: Optional prefix for the package_id (e.g. "com.nvidia.simready")
    :return: A dict representing the com.nvidia.simready.packaging.json content
    """
    if package_id_prefix:
        package_id = f"{package_id_prefix}.{package.name}.{package.version}"
    else:
        package_id = f"{package.name}.{package.version}"

    definition: dict = {
        "format_version": STANDARD_FORMAT_VERSION,
        "package_id": package_id,
        "license": license_id,
        "metadata": [
            {"name": BOM_METADATA_FILENAME},
        ],
    }

    return definition


@wrapp_public_api
def generate_bom_metadata(package: PackageInfo) -> dict:
    """
    Generate a standard-compliant BOM metadata dict from a WRAPP PackageInfo.

    Produces a dict for the .metadata/com.nvidia.simready.packaging.bom.json file.
    Always returns a BOM — even for metapackages (no catalog / empty catalog) —
    so that the .wrapp file is implicitly excluded from standard package content.

    Two kinds of catalog paths are *always* skipped because they are never
    package content:

    * the package definition file
      (``com.nvidia.simready.packaging.json``) at the package root, and
    * anything under the reserved ``.metadata/`` folder
      (BOM, conformance metadata, root-USDs list, …).

    PKG.BOM.001 keeps the BOM as a *content-only* inventory;
    PKG.CONF.001 / PKG.HASH.001 reserve the ``.metadata/`` namespace for
    metadata sidecars; and the package definition is the index of the
    package, not part of its content. Including any of these in
    ``items[]`` would (a) violate the spec and (b) break
    ``content_hash`` equality between the pre-validation phase (which
    walks the filesystem and excludes the same set) and the
    post-creation phase (which derives the hash from the BOM buffer).

    :param package: A loaded PackageInfo (from any WRAPP repo, redirect or otherwise)
    :return: A dict representing the BOM metadata file content
    """
    catalog = package.catalog
    metadata_prefix = METADATA_FOLDER + "/"

    bom: dict = {
        "format_version": STANDARD_FORMAT_VERSION,
    }

    if catalog is not None and catalog.items:
        bom["content_root"] = catalog.root
        content_root = normalize_url(catalog.root)
        bom["items"] = [
            _catalog_item_to_bom_item(item, content_root)
            for item in catalog.items
            if item.relative_path != PACKAGING_DEFINITION_FILENAME
            and item.relative_path != METADATA_FOLDER
            and not item.relative_path.startswith(metadata_prefix)
        ]
    else:
        bom["items"] = []

    return bom


def _hash_bytes(data: bytes, hash_algos: HashAlgorithms) -> Dict[str, str]:
    """Compute SHA-256 (and optionally BLAKE3) of *data*, returning a hash object."""
    obj: Dict[str, str] = {"sha256": hashlib.sha256(data).hexdigest()}
    if hash_algos.blake3 and _blake3_mod is not None:
        obj["blake3"] = _blake3_mod.blake3(data).hexdigest()
    return obj


def _parse_nucleus_hash_hex(hash_value: str) -> Optional[str]:
    """Extract the hex digest from a Nucleus hash string (``sha-256-flat;1048576;<hex>``)."""
    if not is_nucleus_hash(hash_value):
        return None
    return hash_value.rsplit(";", 1)[-1]


def _catalog_item_to_bom_item(item: CatalogItem, content_root_normalized: str) -> dict:
    """Convert a single CatalogItem to a standard BOM item dict."""
    size = item.size
    if size is None:
        logger.warning(f"BOM item '{item.relative_path}' has no size; using 0 as fallback (non-conformant)")
        size = 0

    bom_item: dict = {
        "relative_path": item.relative_path,
        "size": size,
    }

    hash_obj = _build_hash_object(item)
    if hash_obj:
        bom_item["hash"] = hash_obj

    expected_source = content_root_normalized + "/" + item.relative_path
    actual_source = normalize_url(item.source_path)
    if actual_source != expected_source:
        bom_item["content_location"] = item.source_path

    return bom_item


def _build_hash_object(item: CatalogItem) -> dict:
    """Build a hash object from available hashes on a CatalogItem.

    The Nucleus hash (SHA-256 over 1 MB chunks, then SHA-256 of the concatenated
    per-chunk digests) is stored under the key ``sha256-flat-1mb``.
    """
    hash_obj: dict = {}
    if item.hash is not None:
        nucleus_hex = _parse_nucleus_hash_hex(item.hash)
        if nucleus_hex is not None:
            hash_obj["sha256-flat-1mb"] = nucleus_hex
        else:
            logger.warning(
                f"BOM item '{item.relative_path}' has unrecognised hash format; " "only Nucleus hashes (sha-256-flat;…) are supported"
            )
    return hash_obj


async def _compute_file_hashes_for_bom(
    bom: dict, catalog: Catalog, parent_node, *, hash_algos: HashAlgorithms,
) -> None:
    """Download files and compute per-file hashes for every BOM item.

    Files are fetched and hashed **concurrently** (downloads via the hub cache
    or a managed temp file, hash computation dispatched to a CPU thread pool).

    On failure the error propagates — SHA-256 is mandatory per spec.
    """
    catalog_index = {item.relative_path: item for item in catalog.items}
    bom_items = bom["items"]
    urls = [catalog.get_source_url_for_item(catalog_index[item["relative_path"]]) for item in bom_items]
    results = await hash_files(urls, hash_algos, parent_node)
    for bom_item, result in zip(bom_items, results):
        bom_item.setdefault("hash", {}).update(result.hashes)


def compute_content_hash(
    bom_items: list, *, hash_algos: HashAlgorithms,
) -> Optional[Dict[str, str]]:
    """Compute the content_hash per PKG.HASH.001.

    Returns ``{"sha256": "<hex>", ...}``, or ``None`` if any item is
    missing its SHA-256 hash.  When ``hash_algos.blake3`` is ``True``
    and the ``blake3`` library is available, a ``"blake3"`` key is
    added (hashed from the same deterministic buffer).
    """
    for item in bom_items:
        if "hash" not in item or "sha256" not in item["hash"]:
            logger.warning(f"BOM item '{item['relative_path']}' missing sha256 hash; cannot compute content_hash")
            return None

    sorted_items = sorted(bom_items, key=lambda item: item["relative_path"].encode("utf-8"))

    buf = bytearray()
    for item in sorted_items:
        buf.extend(item["relative_path"].encode("utf-8"))
        buf.append(0x00)
        buf.extend(bytes.fromhex(item["hash"]["sha256"]))

    return _hash_bytes(bytes(buf), hash_algos)


def compute_package_hash(
    package_id: str,
    license_id: str,
    content_hash: Dict[str, str],
    metadata_entries: list,
    *,
    hash_algos: HashAlgorithms,
) -> Dict[str, str]:
    """Compute the package_hash per PKG.HASH.001.

    Returns ``{"sha256": "<hex>", ...}``.  When ``hash_algos.blake3``
    is ``True`` and ``blake3`` is available, a ``"blake3"`` key is added.
    """
    sorted_entries = sorted(metadata_entries, key=lambda e: e["name"].encode("utf-8"))

    buf = bytearray()
    buf.extend(package_id.encode("utf-8"))
    buf.append(0x00)
    buf.extend(license_id.encode("utf-8"))
    buf.append(0x00)
    buf.extend(bytes.fromhex(content_hash["sha256"]))
    for entry in sorted_entries:
        buf.extend(entry["name"].encode("utf-8"))
        buf.append(0x00)
        buf.extend(bytes.fromhex(entry["hash"]["sha256"]))

    return _hash_bytes(bytes(buf), hash_algos)


if __name__ == "__main__":
    app()

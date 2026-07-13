"""Pre-flight validation: is this source folder ready to package?

Validates the root USD files in a source directory against one or
more profiles via :func:`simready.validate.validate_asset`.

Root USDs must be specified explicitly (``--root-usd`` on the CLI,
or ``root_usds`` in the Python API).  If a previous run already
wrote ``.metadata/com.nvidia.simready.root_usds.json``, its contents
are used as a fallback.  Passing ``--no-usd-files`` allows a source
folder that intentionally contains no USD files.

This is the first phase of the SimReady packaging workflow — it
catches problems *before* the source is wrapped into a package.  It
is intentionally agnostic of which tool will run the create phase
afterwards, so guards for build-tool artifacts (e.g. stray ``.wrapp``
files) live in the create step instead.

Two mutually exclusive side-effect modes are available:

* ``write_metadata=True`` (WRAPP flow) — writes ``.metadata/`` files
  (BOM, ``root_usds.json``, conformance JSONs with ``content_hash``)
  that the subsequent create step can verify and register.  Requires
  WRAPP at runtime.
* ``stamp_usd=True`` (no-WRAPP flow) — passes
  ``write_metadata=True`` on each :class:`AssetValidationConfig` so
  ``simready.validate`` stamps validation results directly into the
  USD file's ``customLayerData``.  No ``.metadata/``, no BOM, no
  WRAPP dependency.

``simready.validate.initialize`` must already have run before
:func:`pre_validate` is called — see the README for the one-time
setup snippet.
"""

from __future__ import annotations

import logging
from pathlib import Path

import simready.validate as sv

from ._conformance_writer import (
    build_asset_results,
    read_root_usds_metadata,
    write_bom_metadata,
    write_conformance_metadata,
    write_root_usds_metadata,
)
from .errors import UsageError, ValidationFailed
from .results import PreValidationResult

DEFAULT_PROFILE_ID = "Package-Candidate"
DEFAULT_PROFILE_VERSION = "1.0.0"

_USD_SUFFIXES = frozenset({".usd", ".usda"})

logger = logging.getLogger(__name__)


def _discover_usd_files(source: Path) -> list[Path]:
    """Recursively collect every USD/USDA file beneath ``source``."""
    return sorted(
        p
        for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in _USD_SUFFIXES
    )


def _collect_failed_features(
    result: sv.AssetValidationResult | None,
    profile_id: str,
    profile_version: str,
) -> set[str]:
    """Extract the set of failed feature IDs from a single engine result.

    Returns ``{"<engine-error>"}`` when the engine returned no result
    or no features, so callers can tell engine misconfiguration apart
    from a genuine feature failure.
    """
    if result is None:
        return {"<engine-error>"}

    features = result.features_summary
    if not features:
        return {"<engine-error>"}

    return {
        fid
        for fid in features
        if not bool(features[fid].get("passed"))
    }


def _resolve_root_usds(
    source: Path,
    root_usds: list[str] | None,
) -> list[str] | None:
    """Determine which USD files are root entry points.

    Resolution order:

    1. Explicit *root_usds* list (from ``--root-usd`` flags).
    2. Existing ``root_usds.json`` in ``.metadata/``.

    Returns ``None`` when neither source provides any entries — the
    caller decides whether to error or allow it (see
    *allow_no_usd_files*).
    """
    if root_usds:
        return root_usds

    existing = read_root_usds_metadata(source)
    if existing:
        return existing

    return None


def _validate_profile(
    source: Path,
    usd_files: list[Path],
    profile_id: str,
    profile_version: str,
    *,
    stamp_usd: bool = False,
) -> tuple[set[str], list[tuple[str, sv.AssetValidationResult | None]]]:
    """Validate *usd_files* against a single profile.

    Returns ``(failed_features, results_with_rel_paths)``.
    """
    configs = [
        sv.AssetValidationConfig(
            asset_path=str(usd),
            profile_id=profile_id,
            profile_version=profile_version,
            write_metadata=stamp_usd,
        )
        for usd in usd_files
    ]
    results = sv.validate_asset_list(configs)

    failed_features: set[str] = set()
    results_with_rel: list[tuple[str, sv.AssetValidationResult | None]] = []

    for usd, result in zip(usd_files, results):
        rel = usd.relative_to(source).as_posix()
        failed_features |= _collect_failed_features(result, profile_id, profile_version)
        results_with_rel.append((rel, result))

    return failed_features, results_with_rel


async def _compute_bom_and_hash(
    source: str, *, sha256_only: bool = False,
) -> tuple[dict, dict | None]:
    """Compute BOM + ``content_hash`` from *source*.

    ``compute_bom`` applies the spec's structural exclusions itself
    (package definition, ``.metadata/``, ``*.wrapp``), so this wrapper
    is just a thin convenience around ``compute_bom`` +
    ``compute_content_hash``.
    """
    import wrapp

    from ._bom import compute_bom, compute_content_hash

    async with wrapp.ContextManager() as scheduler:
        bom = await compute_bom(
            source,
            sha256_only=sha256_only,
            scheduler_node=scheduler.parent_task_node(),
        )
    content_hash = compute_content_hash(bom["items"], sha256_only=sha256_only)
    return bom, content_hash


async def pre_validate(
    source: Path,
    *,
    profiles: list[str] | None = None,
    root_usds: list[str] | None = None,
    write_metadata: bool = False,
    stamp_usd: bool = False,
    allow_no_usd_files: bool = False,
    sha256_only: bool = False,
) -> PreValidationResult:
    """Run asset validation over USD files in ``source``.

    Returns a :class:`PreValidationResult` whose ``.results`` dict
    maps each profile ID to ``[(rel_path, AssetValidationResult | None)]``
    pairs.  Inspect ``result.passed`` or ``result.failed_features``
    for the overall outcome; drill into
    ``AssetValidationResult.features_summary`` for per-feature detail.

    Parameters
    ----------
    source:
        Directory holding the asset that you are preparing to publish.
    profiles:
        Profile IDs to validate against.  Defaults to
        ``["Package-Candidate"]``.
    root_usds:
        Explicit list of root-USD relative paths (from ``--root-usd``
        on the CLI).  When ``None``, falls back to an existing
        ``.metadata/com.nvidia.simready.root_usds.json``; if that
        file is also absent the call errors unless
        *allow_no_usd_files* is ``True``.  Only meaningful when
        ``write_metadata=True``; otherwise all USDs under *source*
        are validated.
    write_metadata:
        When ``True``, write ``.metadata/`` files (BOM,
        ``root_usds.json``, conformance JSONs) into *source*.  The
        create step can later verify and register these.  Requires
        WRAPP at runtime.  Mutually exclusive with *stamp_usd*.
    stamp_usd:
        When ``True``, pass ``write_metadata=True`` on each
        :class:`AssetValidationConfig` so ``simready.validate`` stamps
        results into the USD file's ``customLayerData``.  No
        ``.metadata/``, no BOM, no WRAPP dependency.  Mutually
        exclusive with *write_metadata*.
    allow_no_usd_files:
        When ``True``, silently return an empty result if no USD files
        are found in *source*.  When ``False`` (the default), raise
        :class:`UsageError` instead — use ``--no-usd-files`` on the
        CLI to opt out.
    sha256_only:
        When ``True``, only SHA-256 hashes are computed.  When
        ``False`` (the default), BLAKE3 hashes are included alongside
        SHA-256 in BOM items and the ``content_hash`` written to
        conformance metadata when the ``blake3`` library is importable.

    Returns
    -------
    PreValidationResult

    Raises
    ------
    UsageError
        Source path is missing, is not a directory, already carries a
        built-package marker, has ambiguous OpenUSD root layers, or contains no
        USD files (unless *allow_no_usd_files* is ``True``).
    ValidationFailed
        At least one USD failed at least one feature.
        ``ValidationFailed.result`` carries the full
        :class:`PreValidationResult`.
    """
    if write_metadata and stamp_usd:
        raise UsageError(
            "write_metadata and stamp_usd are mutually exclusive"
        )

    source = Path(source)
    if not source.is_dir():
        raise UsageError(
            f"source folder not found or not a directory: {source}"
        )

    profile_list = profiles or [DEFAULT_PROFILE_ID]

    if write_metadata:
        return await _pre_validate_with_metadata(
            source, profile_list, root_usds,
            allow_no_usd_files=allow_no_usd_files,
            sha256_only=sha256_only,
        )
    else:
        return _pre_validate_simple(
            source, profile_list,
            stamp_usd=stamp_usd,
            allow_no_usd_files=allow_no_usd_files,
        )


def _pre_validate_simple(
    source: Path,
    profile_list: list[str],
    *,
    stamp_usd: bool = False,
    allow_no_usd_files: bool = False,
) -> PreValidationResult:
    """Walk all USDs, validate, return results.

    When *stamp_usd* is ``True``, ``simready.validate`` also writes
    validation results into each USD file's ``customLayerData``.
    """
    usd_files = _discover_usd_files(source)
    if not usd_files:
        if not allow_no_usd_files:
            raise UsageError(
                f"no USD files found under {source}; pass --no-usd-files "
                f"to allow this."
            )
        logger.warning("no USD files found under %s; nothing to validate.", source)
        return PreValidationResult(
            source=source,
            profile_version=DEFAULT_PROFILE_VERSION,
            results={},
        )

    all_failed: set[str] = set()
    all_results: dict[str, list[tuple[str, sv.AssetValidationResult | None]]] = {}
    for profile_id in profile_list:
        failed, results_with_rel = _validate_profile(
            source, usd_files, profile_id, DEFAULT_PROFILE_VERSION,
            stamp_usd=stamp_usd,
        )
        all_failed |= failed
        all_results[profile_id] = results_with_rel

    result = PreValidationResult(
        source=source,
        profile_version=DEFAULT_PROFILE_VERSION,
        results=all_results,
        failed_features=sorted(all_failed),
    )

    if all_failed:
        profiles_str = ", ".join(profile_list)
        summary = f"{source} did not pass [{profiles_str}]."
        raise ValidationFailed(summary, failures=sorted(all_failed), result=result)

    return result


async def _pre_validate_with_metadata(
    source: Path,
    profile_list: list[str],
    root_usds_arg: list[str] | None,
    *,
    allow_no_usd_files: bool = False,
    sha256_only: bool = False,
) -> PreValidationResult:
    """Validate OpenUSD root layers + write .metadata/ artefacts."""
    resolved_roots = _resolve_root_usds(source, root_usds_arg)
    if not resolved_roots:
        if not allow_no_usd_files:
            raise UsageError(
                f"no root USD files specified for {source}; use "
                f"--root-usd to identify the entry-point USD(s), or "
                f"pass --no-usd-files if the source intentionally "
                f"contains none."
            )
        logger.warning(
            "no root USD files identified under %s; nothing to validate.",
            source,
        )
        return PreValidationResult(
            source=source,
            profile_version=DEFAULT_PROFILE_VERSION,
            results={},
        )

    usd_files = [source / r for r in resolved_roots]
    missing = [str(u) for u in usd_files if not u.is_file()]
    if missing:
        raise UsageError(
            f"root USD file(s) not found: {', '.join(missing)}"
        )

    all_failed: set[str] = set()
    per_profile_results: dict[str, list[tuple[str, sv.AssetValidationResult | None]]] = {}

    for profile_id in profile_list:
        failed, results_with_rel = _validate_profile(
            source, usd_files, profile_id, DEFAULT_PROFILE_VERSION,
        )
        all_failed |= failed
        per_profile_results[profile_id] = results_with_rel

    bom, content_hash = await _compute_bom_and_hash(
        str(source), sha256_only=sha256_only,
    )

    metadata_written: list[str] = []

    write_root_usds_metadata(source, resolved_roots)
    metadata_written.append(".metadata/com.nvidia.simready.root_usds.json")

    write_bom_metadata(source, bom)
    metadata_written.append(".metadata/com.nvidia.simready.packaging.bom.json")

    for profile_id, results_with_rel in per_profile_results.items():
        asset_results = build_asset_results(results_with_rel)
        path = write_conformance_metadata(
            source,
            profile_id,
            DEFAULT_PROFILE_VERSION,
            asset_results,
            content_hash=content_hash,
        )
        metadata_written.append(str(path.relative_to(source)))

    result = PreValidationResult(
        source=source,
        profile_version=DEFAULT_PROFILE_VERSION,
        results=per_profile_results,
        metadata_written=metadata_written,
        failed_features=sorted(all_failed),
    )

    if all_failed:
        profiles_str = ", ".join(profile_list)
        summary = f"{source} did not pass [{profiles_str}]."
        raise ValidationFailed(summary, failures=sorted(all_failed), result=result)

    return result

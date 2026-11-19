# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Public metadata-conformance API with explicit paths and structured results.

One call stages a copy of the source package, repairs authored asset paths,
derives and stamps SR.003 provenance, normalizes the SR.002 thumbnail, and only
then promotes the result onto the destination folder. The source package is
never mutated, and a pre-existing destination is restored when promotion fails.
"""

from __future__ import annotations

import gc
import json
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pxr import Usd

from . import staging as staging_support
from .conform import ConformOutcome, conform_package
from .protocol import PROTOCOL_VERSION
from .version import __version__

STAGE_REQUEST = "request"
STAGE_SETUP = "setup"
STAGE_PREFLIGHT = "preflight"
STAGE_CONFORM = "conform"
STAGE_PROMOTE = "promote"

CODE_SOURCE_NOT_USD = "SOURCE_NOT_USD"
CODE_SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
CODE_OUTPUT_IS_SOURCE = "OUTPUT_IS_SOURCE"
CODE_OUTPUT_EXISTS = "OUTPUT_EXISTS"
CODE_OUTPUT_NOT_DIRECTORY = "OUTPUT_NOT_DIRECTORY"
CODE_INVALID_METADATA = "INVALID_METADATA"
CODE_CONFORM_FAILED = "CONFORM_FAILED"
CODE_PROMOTE_FAILED = "PROMOTE_FAILED"
CODE_PROMOTE_ROLLED_BACK = "PROMOTE_ROLLED_BACK"

_USD_SUFFIXES = {".usd", ".usda", ".usdc", ".usdz"}


@dataclass(frozen=True)
class ResultError:
    """One structured failure with a stable code and originating stage."""

    code: str
    stage: str
    detail: str
    paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": self.stage,
            "detail": self.detail,
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class MetadataConformRequest:
    """One conformance request."""

    source_usd: Path
    output_folder: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    thumbnail_source: Path | None = None
    replace_existing: bool = False
    report_path: Path | None = None
    diagnostics_dir: Path | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MetadataConformRequest:
        """Build a request from a decoded JSON object.

        Raises:
            ValueError: When a required field is missing or has the wrong type.
        """
        if not isinstance(payload, dict):
            raise ValueError(
                f"request must be a JSON object, got {type(payload).__name__}"
            )

        def _required_path(key: str) -> Path:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"request field '{key}' must be a non-empty string")
            return Path(value)

        def _optional_path(key: str) -> Path | None:
            value = payload.get(key)
            if value is None:
                return None
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"request field '{key}' must be a non-empty string when present"
                )
            return Path(value)

        replace_existing = payload.get("replace_existing", False)
        if not isinstance(replace_existing, bool):
            raise ValueError("request field 'replace_existing' must be a boolean")

        metadata = payload.get("metadata", {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError("request field 'metadata' must be a JSON object")

        return cls(
            source_usd=_required_path("source_usd"),
            output_folder=_required_path("output_folder"),
            metadata=dict(metadata),
            thumbnail_source=_optional_path("thumbnail_source"),
            replace_existing=replace_existing,
            report_path=_optional_path("report_path"),
            diagnostics_dir=_optional_path("diagnostics_dir"),
        )


@dataclass
class MetadataConformResult:
    """Outcome of one conformance run, including every structured failure."""

    ok: bool
    source_usd: str
    output_folder: str
    output_usd: str | None = None
    report_path: str | None = None
    diagnostics_path: str | None = None
    replaced_existing: bool = False
    errors: list[ResultError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolved_metadata: dict[str, Any] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)
    path_repairs: list[dict[str, str]] = field(default_factory=list)
    thumbnail: dict[str, Any] = field(default_factory=dict)
    derivation: dict[str, Any] = field(default_factory=dict)
    mutation_audit: dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "package_version": __version__,
            "ok": self.ok,
            "source_usd": self.source_usd,
            "output_folder": self.output_folder,
            "output_usd": self.output_usd,
            "report_path": self.report_path,
            "diagnostics_path": self.diagnostics_path,
            "replaced_existing": self.replaced_existing,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": list(self.warnings),
            "resolved_metadata": _jsonable(self.resolved_metadata),
            "field_sources": dict(self.field_sources),
            "path_repairs": list(self.path_repairs),
            "thumbnail": _jsonable(self.thumbnail),
            "derivation": _jsonable(self.derivation),
            "mutation_audit": _jsonable(self.mutation_audit),
            "elapsed_s": self.elapsed_s,
        }


def _jsonable(value: Any) -> Any:
    """Coerce USD scalars and paths into JSON-encodable values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__iter__") and not isinstance(value, (bytes, str)):
        try:
            return [_jsonable(item) for item in value]
        except TypeError:
            return str(value)
    return str(value)


def _release_usd_handles() -> None:
    gc.collect()
    Usd.StageCache().Clear()


class _StagedFailure(Exception):
    """Internal control flow marker for a failed staged run."""


def run_metadata_conform(
    source_usd: Path | str,
    output_folder: Path | str,
    *,
    metadata: dict[str, Any] | None = None,
    thumbnail_source: Path | str | None = None,
    replace_existing: bool = False,
    report_path: Path | str | None = None,
    diagnostics_dir: Path | str | None = None,
) -> MetadataConformResult:
    """Conform a package to FET_031 and FET_033, then promote it.

    Args:
        source_usd: Root USD of the source package. Never modified.
        output_folder: Destination package directory.
        metadata: Caller-supplied provenance strings and an optional ``qcode``.
            The physical fields are rejected here and derived from the asset.
        thumbnail_source: PNG to install as the SR.002 thumbnail.
        replace_existing: Allow transactional replacement of ``output_folder``.
        report_path: Where to write the machine-readable JSON report.
        diagnostics_dir: Where to preserve staging output when a run fails.

    Returns:
        A result whose ``errors`` list is empty only when ``ok`` is true.
    """
    started = time.perf_counter()
    source = Path(source_usd).expanduser()
    output = Path(output_folder).expanduser()
    report = Path(report_path).expanduser().resolve() if report_path else None
    diagnostics = (
        Path(diagnostics_dir).expanduser().resolve() if diagnostics_dir else None
    )
    thumbnail = Path(thumbnail_source).expanduser() if thumbnail_source else None

    result = MetadataConformResult(
        ok=False,
        source_usd=str(source),
        output_folder=str(output),
        report_path=str(report) if report else None,
    )

    def _fail(
        code: str, stage: str, detail: str, paths: tuple[str, ...] = ()
    ) -> MetadataConformResult:
        result.errors.append(
            ResultError(code=code, stage=stage, detail=detail, paths=paths)
        )
        result.elapsed_s = round(time.perf_counter() - started, 6)
        _write_report(result, report)
        return result

    if source.suffix.lower() not in _USD_SUFFIXES:
        return _fail(
            CODE_SOURCE_NOT_USD, STAGE_REQUEST, f"source is not a USD file: {source}"
        )
    if not source.is_file():
        return _fail(
            CODE_SOURCE_NOT_FOUND, STAGE_REQUEST, f"source USD not found: {source}"
        )

    source = source.resolve()
    output = output.resolve()
    result.source_usd = str(source)
    result.output_folder = str(output)

    if output == source.parent:
        return _fail(
            CODE_OUTPUT_IS_SOURCE,
            STAGE_REQUEST,
            f"output folder is the source package: {output}",
        )
    if output.exists():
        if not output.is_dir():
            return _fail(
                CODE_OUTPUT_NOT_DIRECTORY,
                STAGE_REQUEST,
                f"output path exists and is not a directory: {output}",
            )
        if not replace_existing:
            return _fail(
                CODE_OUTPUT_EXISTS, STAGE_REQUEST, f"output already exists: {output}"
            )

    if metadata is not None and not isinstance(metadata, dict):
        return _fail(
            CODE_INVALID_METADATA, STAGE_REQUEST, "metadata must be a mapping"
        )

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".metadata_stage_", dir=str(output.parent))
        )
    except OSError as exc:
        return _fail(
            CODE_PROMOTE_FAILED,
            STAGE_SETUP,
            f"could not create staging directory next to {output}: {exc}",
        )

    work = staging / "package"
    outcome: ConformOutcome | None = None
    try:
        try:
            staging_support.copy_package(source.parent, work)
        except OSError as exc:
            result.errors.append(
                ResultError(
                    code=CODE_CONFORM_FAILED,
                    stage=STAGE_SETUP,
                    detail=f"could not stage a working copy: {exc}",
                    paths=(str(source.parent),),
                )
            )
            raise _StagedFailure from exc

        work_usd = work / source.name
        if not work_usd.is_file():
            result.errors.append(
                ResultError(
                    code=CODE_CONFORM_FAILED,
                    stage=STAGE_PREFLIGHT,
                    detail=f"staged package is missing expected USD: {work_usd}",
                    paths=(str(work_usd),),
                )
            )
            raise _StagedFailure

        try:
            outcome = conform_package(
                work_usd,
                metadata=metadata,
                thumbnail_source=thumbnail,
                package_root=work,
            )
        except Exception as exc:  # noqa: BLE001 - conformance boundary
            result.errors.append(
                ResultError(
                    code=CODE_CONFORM_FAILED, stage=STAGE_CONFORM, detail=str(exc)
                )
            )
            raise _StagedFailure from exc

        _absorb_outcome(result, outcome)
        if not outcome.ok:
            raise _StagedFailure

        _release_usd_handles()
        staging_support.materialize_symlinks(work)
        if not _promote(work, output, result):
            raise _StagedFailure

        result.ok = True
        result.output_usd = str(output / source.name)
    except _StagedFailure:
        result.diagnostics_path = staging_support.preserve_diagnostics(
            staging, diagnostics
        )
    finally:
        _release_usd_handles()
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    result.elapsed_s = round(time.perf_counter() - started, 6)
    _write_report(result, report)
    return result


def _absorb_outcome(result: MetadataConformResult, outcome: ConformOutcome) -> None:
    """Copy conformance evidence and blockers onto the public result."""
    result.resolved_metadata = outcome.resolved_metadata
    result.field_sources = outcome.field_sources
    result.path_repairs = outcome.path_repairs
    result.thumbnail = outcome.thumbnail
    result.derivation = outcome.derivation
    result.mutation_audit = outcome.mutation_audit
    result.warnings.extend(outcome.warnings)
    result.warnings.extend(
        f"{name}: {warning}" for name, warning in outcome.field_warnings.items()
    )
    for blocker in outcome.blockers:
        result.errors.append(
            ResultError(
                code=blocker.code,
                stage=STAGE_CONFORM,
                detail=blocker.detail,
                paths=tuple(blocker.paths),
            )
        )


def _promote(work: Path, output: Path, result: MetadataConformResult) -> bool:
    """Move ``work`` onto ``output``, restoring any previous output on failure."""
    backup: Path | None = None
    if output.exists():
        backup = output.parent / f".{output.name}.backup_{uuid.uuid4().hex[:8]}"
        try:
            shutil.move(str(output), str(backup))
        except OSError as exc:
            result.errors.append(
                ResultError(
                    code=CODE_PROMOTE_FAILED,
                    stage=STAGE_PROMOTE,
                    detail=f"could not move existing output aside: {exc}",
                    paths=(str(output),),
                )
            )
            return False

    try:
        shutil.move(str(work), str(output))
    except OSError as exc:
        detail = f"could not promote staged package to {output}: {exc}"
        if backup is not None:
            restored = staging_support.restore_backup(backup, output)
            result.errors.append(
                ResultError(
                    code=(
                        CODE_PROMOTE_ROLLED_BACK if restored else CODE_PROMOTE_FAILED
                    ),
                    stage=STAGE_PROMOTE,
                    detail=(
                        f"{detail}; previous output restored"
                        if restored
                        else f"{detail}; previous output left at {backup}"
                    ),
                    paths=(str(output), str(backup)),
                )
            )
        else:
            result.errors.append(
                ResultError(
                    code=CODE_PROMOTE_FAILED,
                    stage=STAGE_PROMOTE,
                    detail=detail,
                    paths=(str(output),),
                )
            )
        return False

    if backup is not None:
        result.replaced_existing = True
        shutil.rmtree(backup, ignore_errors=True)
    return True


def _write_report(result: MetadataConformResult, report_path: Path | None) -> None:
    if report_path is None:
        return
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        result.report_path = None

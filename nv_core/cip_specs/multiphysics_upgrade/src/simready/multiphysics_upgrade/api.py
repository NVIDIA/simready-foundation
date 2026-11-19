# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Public neutral-to-runtimes API with explicit paths and structured results.

One call stages a copy of the source package, authors the PhysX/Newton/MuJoCo
runtime payloads, composes the Isaac interface, and only then promotes the
result onto the destination folder. The source package is never mutated, and a
pre-existing destination is restored when promotion fails.
"""

from __future__ import annotations

import gc
import os
import shutil
import stat
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pxr import Usd

from . import core, neutral_to_runtimes
from .protocol import PROTOCOL_VERSION
from .transformer_bootstrap import TransformerUnavailableError
from .version import __version__

STAGE_REQUEST = "request"
STAGE_SETUP = "setup"
STAGE_PREFLIGHT = "preflight"
STAGE_TRANSFORM = "transform"
STAGE_PROMOTE = "promote"

CODE_SOURCE_NOT_USD = "SOURCE_NOT_USD"
CODE_SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
CODE_OUTPUT_IS_SOURCE = "OUTPUT_IS_SOURCE"
CODE_OUTPUT_EXISTS = "OUTPUT_EXISTS"
CODE_OUTPUT_NOT_DIRECTORY = "OUTPUT_NOT_DIRECTORY"
CODE_STAGE_OPEN_FAILED = "STAGE_OPEN_FAILED"
CODE_TRANSFORMER_UNAVAILABLE = "TRANSFORMER_UNAVAILABLE"
CODE_TRANSFORM_FAILED = "TRANSFORM_FAILED"
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
class NeutralToRuntimesRequest:
    """One transformation request."""

    source_usd: Path
    output_folder: Path
    replace_existing: bool = False
    report_path: Path | None = None
    diagnostics_dir: Path | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> NeutralToRuntimesRequest:
        """Build a request from a decoded JSON object.

        Raises:
            ValueError: When a required field is missing or has the wrong type.
        """
        if not isinstance(payload, dict):
            raise ValueError(f"request must be a JSON object, got {type(payload).__name__}")

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
                raise ValueError(f"request field '{key}' must be a non-empty string when present")
            return Path(value)

        replace_existing = payload.get("replace_existing", False)
        if not isinstance(replace_existing, bool):
            raise ValueError("request field 'replace_existing' must be a boolean")

        return cls(
            source_usd=_required_path("source_usd"),
            output_folder=_required_path("output_folder"),
            replace_existing=replace_existing,
            report_path=_optional_path("report_path"),
            diagnostics_dir=_optional_path("diagnostics_dir"),
        )


@dataclass
class NeutralToRuntimesResult:
    """Outcome of one transformation, including every structured failure."""

    ok: bool
    source_usd: str
    output_folder: str
    output_usd: str | None = None
    report_path: str | None = None
    diagnostics_path: str | None = None
    replaced_existing: bool = False
    errors: list[ResultError] = field(default_factory=list)
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
            "elapsed_s": self.elapsed_s,
        }


def _release_usd_handles() -> None:
    gc.collect()
    Usd.StageCache().Clear()


def _materialize_symlinks(root: Path) -> None:
    """Replace symlinks with real files so the package survives staging cleanup.

    Staged packages share non-USD payload with the source through hardlinks when
    the filesystem allows it, and symlinks otherwise. Hardlinks stay valid after
    the source is removed; symlinks do not, so they are copied before promotion.
    """
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_symlink():
            continue
        target = Path(os.path.realpath(path))
        path.unlink()
        if target.is_dir():
            shutil.copytree(target, path)
        else:
            shutil.copy2(target, path)
            path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _preserve_diagnostics(staging: Path, diagnostics_dir: Path | None) -> str | None:
    """Move failed staging output aside for inspection; return its location."""
    if diagnostics_dir is None:
        return None
    try:
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        destination = diagnostics_dir / f"failed_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        shutil.move(str(staging), str(destination))
        return str(destination)
    except OSError:
        return None


def run_neutral_to_runtimes(
    source_usd: Path | str,
    output_folder: Path | str,
    *,
    replace_existing: bool = False,
    report_path: Path | str | None = None,
    diagnostics_dir: Path | str | None = None,
) -> NeutralToRuntimesResult:
    """Transform a neutral prop package into a multiphysics Isaac package.

    Args:
        source_usd: Root USD of the neutral source package. Never modified.
        output_folder: Destination package directory.
        replace_existing: Allow transactional replacement of ``output_folder``.
        report_path: Where to write the machine-readable JSON report.
        diagnostics_dir: Where to preserve staging output when a run fails.

    Returns:
        A result whose ``errors`` list is empty only when ``ok`` is true.
    """
    started = time.perf_counter()
    source = Path(source_usd).expanduser()
    output = Path(output_folder).expanduser()
    report = Path(report_path).expanduser().resolve() if report_path is not None else None
    diagnostics = Path(diagnostics_dir).expanduser().resolve() if diagnostics_dir is not None else None

    result = NeutralToRuntimesResult(
        ok=False,
        source_usd=str(source),
        output_folder=str(output),
        report_path=str(report) if report else None,
    )

    def _fail(code: str, stage: str, detail: str, paths: tuple[str, ...] = ()) -> NeutralToRuntimesResult:
        result.errors.append(ResultError(code=code, stage=stage, detail=detail, paths=paths))
        result.elapsed_s = round(time.perf_counter() - started, 6)
        _write_report(result, report)
        return result

    if source.suffix.lower() not in _USD_SUFFIXES:
        return _fail(CODE_SOURCE_NOT_USD, STAGE_REQUEST, f"source is not a USD file: {source}")
    if not source.is_file():
        return _fail(CODE_SOURCE_NOT_FOUND, STAGE_REQUEST, f"source USD not found: {source}")

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
                CODE_OUTPUT_EXISTS,
                STAGE_REQUEST,
                f"output already exists: {output}",
            )

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".multiphysics_stage_", dir=str(output.parent)))
    except OSError as exc:
        return _fail(
            CODE_PROMOTE_FAILED,
            STAGE_SETUP,
            f"could not create staging directory next to {output}: {exc}",
        )

    work = staging / "package"
    staged_usd: Path | None = None
    try:
        try:
            work_usd = neutral_to_runtimes.copy_source_package(source, work)
            stage = Usd.Stage.Open(str(work_usd))
            if stage is None:
                raise core.UpgradeError(
                    [
                        core.Blocker(
                            code=CODE_STAGE_OPEN_FAILED,
                            requirement="neutral_to_runtimes",
                            detail=f"could not open staged USD {work_usd}",
                        )
                    ]
                )
            neutral_to_runtimes.upgrade_stage(stage)
            del stage
            _release_usd_handles()
            staged_usd = neutral_to_runtimes.isaac_transform(work_usd)
        except core.UpgradeError as exc:
            for blocker in exc.blockers:
                result.errors.append(
                    ResultError(
                        code=blocker.code,
                        stage=STAGE_PREFLIGHT,
                        detail=blocker.detail,
                        paths=tuple(blocker.paths),
                    )
                )
            raise _StagedFailure from exc
        except TransformerUnavailableError as exc:
            result.errors.append(
                ResultError(code=CODE_TRANSFORMER_UNAVAILABLE, stage=STAGE_SETUP, detail=str(exc))
            )
            raise _StagedFailure from exc
        except Exception as exc:  # noqa: BLE001 - transformation boundary
            result.errors.append(
                ResultError(code=CODE_TRANSFORM_FAILED, stage=STAGE_TRANSFORM, detail=str(exc))
            )
            raise _StagedFailure from exc

        _release_usd_handles()
        _materialize_symlinks(work)
        promoted = _promote(work, output, result)
        if not promoted:
            raise _StagedFailure

        result.ok = True
        result.output_usd = str(output / staged_usd.name) if staged_usd else None
    except _StagedFailure:
        result.diagnostics_path = _preserve_diagnostics(staging, diagnostics)
    finally:
        _release_usd_handles()
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    result.elapsed_s = round(time.perf_counter() - started, 6)
    _write_report(result, report)
    return result


class _StagedFailure(Exception):
    """Internal control flow marker for a failed staged run."""


def _promote(work: Path, output: Path, result: NeutralToRuntimesResult) -> bool:
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
            restored = _restore_backup(backup, output)
            result.errors.append(
                ResultError(
                    code=CODE_PROMOTE_ROLLED_BACK if restored else CODE_PROMOTE_FAILED,
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


def _restore_backup(backup: Path, output: Path) -> bool:
    try:
        if output.exists():
            shutil.rmtree(output, ignore_errors=True)
        shutil.move(str(backup), str(output))
        return True
    except OSError:
        return False


def _write_report(result: NeutralToRuntimesResult, report_path: Path | None) -> None:
    if report_path is None:
        return
    try:
        core.write_report(report_path, result.to_dict())
    except OSError:
        result.report_path = None

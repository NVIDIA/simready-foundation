# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Standalone transactional multiphysics upgrade runner (no omni.cip required).

Never edits the source package in place. Takes a root USD path, copies that
file's parent package directory to a temporary work directory, runs the fixed
ordered edge sequence, stamps the target profile, inspects neutral/runtime
isolation, optionally invokes ``simready-validate``, and atomically promotes to
``--output`` only on success.
"""

from __future__ import annotations

import argparse
import gc
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pxr import Usd

from . import core
from .edges import DEFAULT_SELECTED_OPTIONALS, PASSTHROUGH_FEATURES, plan_edges
from .tier_paths import require_tier_root, rules_dir
from .types import Blocker


def _release_usd_handles() -> None:
    """Drop retained USD stage/layer handles (needed on Windows before delete/move)."""
    gc.collect()
    Usd.StageCache().Clear()


def _elapsed_s(started: float) -> float:
    return round(time.perf_counter() - started, 6)


def _append_step(report: dict[str, Any], **step: Any) -> None:
    report.setdefault("steps", []).append(step)


def _build_profiling(
    steps: list[dict[str, Any]],
    *,
    total_s: float | None = None,
    adapters_loop_s: float | None = None,
) -> dict[str, Any]:
    """Summarize adapter apply time vs surrounding overhead for status reports."""
    adapters = [
        {
            "step": step.get("step"),
            "status": step.get("status"),
            "elapsed_s": step.get("elapsed_s"),
        }
        for step in steps
        if step.get("kind") == "adapter" and step.get("elapsed_s") is not None
    ]
    overhead_items = [
        {
            "step": step.get("step"),
            "kind": step.get("kind"),
            "status": step.get("status"),
            "edge": step.get("edge"),
            "elapsed_s": step.get("elapsed_s"),
        }
        for step in steps
        if step.get("kind") in {"phase", "overhead"} and step.get("elapsed_s") is not None
    ]
    by_category: dict[str, float] = {}
    for item in overhead_items:
        key = str(item["step"])
        by_category[key] = round(by_category.get(key, 0.0) + float(item["elapsed_s"]), 6)

    adapters_total_s = round(sum(float(item["elapsed_s"]) for item in adapters), 6)
    overhead_total_s = round(sum(float(item["elapsed_s"]) for item in overhead_items), 6)
    profiling: dict[str, Any] = {
        "adapters": adapters,
        "adapters_total_s": adapters_total_s,
        "overhead": {
            "items": overhead_items,
            "by_category": dict(sorted(by_category.items())),
            "total_s": overhead_total_s,
        },
        # Back-compat aliases used by earlier consumers.
        "phases": overhead_items,
        "non_adapters_total_s": overhead_total_s,
        "phases_total_s": overhead_total_s,
        "other_s": overhead_total_s,
    }
    if adapters_loop_s is not None:
        loop_s = round(adapters_loop_s, 6)
        profiling["adapters_loop_s"] = loop_s
        profiling["adapters_overhead_s"] = round(max(0.0, loop_s - adapters_total_s), 6)
    if total_s is not None:
        total = round(total_s, 6)
        profiling["total_s"] = total
        profiling["unaccounted_s"] = round(max(0.0, total - adapters_total_s - overhead_total_s), 6)
    return profiling


def _emit_asset_status(report: dict[str, Any]) -> None:
    """Always print a structured per-asset status (success, blocked, or error)."""
    profiling = report.get("profiling") or {}
    overhead = profiling.get("overhead") or {}
    payload: dict[str, Any] = {
        "status": report.get("status"),
        "source_usd": report.get("source_usd"),
        "output": report.get("output"),
        "detected_unibody": report.get("detected_unibody"),
        "profiling": {
            "total_s": profiling.get("total_s"),
            "adapters_total_s": profiling.get("adapters_total_s"),
            "overhead_total_s": overhead.get("total_s"),
            "overhead_by_category": overhead.get("by_category"),
            "unaccounted_s": profiling.get("unaccounted_s"),
            "adapters_loop_s": profiling.get("adapters_loop_s"),
            "adapters_overhead_s": profiling.get("adapters_overhead_s"),
            "adapters": profiling.get("adapters"),
        },
    }
    if report.get("error"):
        payload["error"] = report["error"]
    if report.get("blockers"):
        payload["blockers"] = report["blockers"]
    blocked_steps = [
        {
            "step": step.get("step"),
            "status": step.get("status"),
            "elapsed_s": step.get("elapsed_s"),
            "blockers": step.get("blockers"),
            "detail": step.get("detail"),
        }
        for step in report.get("steps") or []
        if step.get("status") in {"blocked", "failed", "error", "failed_prevalidate", "failed_postvalidate"}
    ]
    if blocked_steps:
        payload["failed_steps"] = blocked_steps
    print(json.dumps(payload, indent=2))


def _finalize_report(
    report: dict[str, Any],
    *,
    report_path: Path | None,
    run_started: float | None = None,
    adapters_loop_s: float | None = None,
) -> None:
    total_s = _elapsed_s(run_started) if run_started is not None else None
    report["profiling"] = _build_profiling(
        report.get("steps", []),
        total_s=total_s,
        adapters_loop_s=adapters_loop_s,
    )
    if report_path:
        core.write_report(report_path, report)
    _emit_asset_status(report)


def _which_simready_validate() -> str | None:
    return shutil.which("simready-validate")


def _run_validate(
    usd_path: Path,
    profile: str,
    version: str,
) -> dict:
    exe = _which_simready_validate()
    if not exe:
        return {
            "status": "skipped",
            "detail": "simready-validate not found on PATH",
        }
    tier_root = require_tier_root()
    cmd = [
        exe,
        "--rules-path",
        str(rules_dir(tier_root)),
        "--features-path",
        str(tier_root / "features"),
        "--profiles-path",
        str(tier_root / "profiles"),
        "--profile",
        profile,
        "--version",
        version,
        str(usd_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {"status": "error", "detail": str(exc), "cmd": cmd}
    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "cmd": cmd,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _selected_contract_ids(selector: Any, catalog: list[str]) -> list[str]:
    """Contract ids one profile selector names.

    An exact selector is the id itself, so it needs no catalog: a profile may
    select another tier's contracts. Only a wildcard or bare-family selector is
    resolved, and only against ``catalog``.
    """
    from simready.foundation.contracts import CapabilityId, CapabilitySelector, FeatureId

    segments = (selector.name, selector.runtime, selector.version)
    if "_" in selector.name and not any(char in segment for segment in segments for char in "*?["):
        return [str(selector)]
    is_capability = isinstance(selector, CapabilitySelector)
    parse = CapabilityId.parse if is_capability else FeatureId.parse
    prefix = "CAP" if is_capability else "FET"
    return [item for item in catalog if item.startswith(prefix) and selector.matches(parse(item))]


def _load_profile_features(profile: str, version: str) -> tuple[list[str], list[str]]:
    """Read the required/optional contract ids a tier profile selects.

    Only the profile's own selectors are returned; contracts they depend on are
    left to the validator, as the upgrade edges never target them directly.
    """
    from simready.foundation.contracts import ContractError, load_profile_definitions

    tier_root = require_tier_root()
    try:
        profiles = load_profile_definitions([tier_root / "profiles"])
    except ContractError as exc:
        raise ValueError(
            f"{tier_root / 'profiles'} is not a Foundations 2 profile catalog; "
            f"this upgrade needs a Foundations 2 tier ({exc})"
        ) from exc
    definition = profiles.get((profile, version))
    if definition is None:
        raise ValueError(f"Profile not found: {profile}@{version}")
    catalog = sorted(
        json.loads(path.read_text(encoding="utf-8"))["id"]
        for section in ("features", "capabilities")
        for path in (tier_root / section).glob("*.json")
    )
    required: list[str] = []
    optional: list[str] = []
    for entry in definition.features + definition.capabilities:
        target = optional if entry.optional else required
        for contract_id in _selected_contract_ids(entry.selector, catalog):
            if contract_id not in target:
                target.append(contract_id)
    return required, optional


def build_plan(
    *,
    source_profile: str,
    source_version: str,
    target_profile: str = "Robotics-Prop",
    target_version: str = "3.1.0",
) -> dict:
    edges = plan_edges()
    source_required, source_optional = _load_profile_features(source_profile, source_version)
    target_required, target_optional = _load_profile_features(target_profile, target_version)
    selected = list(DEFAULT_SELECTED_OPTIONALS)

    invalid_selected = sorted(set(selected) - set(target_optional))
    available = set(source_required + source_optional)
    executed: list[dict] = []
    missing_inputs: list[str] = []
    for edge in edges:
        input_pin = edge.input_feature.key()
        if input_pin not in available:
            missing_inputs.append(f"{edge.name}: {input_pin}")
        available.add(edge.output_feature.key())
        executed.append(
            {
                "name": edge.name,
                "input": input_pin,
                "output": edge.output_feature.key(),
            }
        )

    desired = set(target_required + selected)
    unresolved = sorted(desired - available)
    return {
        "source_profile": f"{source_profile}@{source_version}",
        "target_profile": f"{target_profile}@{target_version}",
        "source_features": source_required,
        "target_required_features": target_required,
        "target_optional_features": target_optional,
        "passthrough": [f.key() for f in PASSTHROUGH_FEATURES],
        "selected_optional_features": selected,
        "edges": executed,
        "missing_inputs": missing_inputs,
        "invalid_selected_features": invalid_selected,
        "unresolved_target_features": unresolved,
        "note": (
            "FET_004 multibody edges are always planned; unibody assets skip them at "
            "runtime when NOT_MULTIBODY is detected."
        ),
    }


_USD_SUFFIXES = {".usd", ".usda", ".usdc", ".usdz"}


def _is_usd_path(path: Path) -> bool:
    return path.suffix.lower() in _USD_SUFFIXES


def package_root_for_usd(usd_path: Path) -> Path:
    """Package directory for package-level copy/promote is the USD's parent."""
    return usd_path.resolve().parent


@dataclass
class AssetJob:
    """One asset upgrade request (input is the root USD path)."""

    input_path: Path
    output_folder: Path


def _coerce_job(entry: Any, *, index: int) -> AssetJob:
    if not isinstance(entry, dict):
        raise ValueError(f"assets[{index}] must be an object, got {type(entry).__name__}")
    missing = [key for key in ("input_path", "output_folder") if not entry.get(key)]
    if missing:
        raise ValueError(f"assets[{index}] is missing required field(s): {', '.join(missing)}")
    return AssetJob(
        input_path=Path(entry["input_path"]),
        output_folder=Path(entry["output_folder"]),
    )


def load_assets_json(path: Path) -> list[AssetJob]:
    """Load a JSON asset list.

    Accepted shapes:
    - ``[{"input_path": "<usd>", "output_folder": "..."}, ...]``
    - ``{"assets": [ ...same as above... ]}``

    ``input_path`` is the root USD file. The package directory is its parent.
    Multibody vs unibody is detected at runtime from rigid-body count; do not pass
    a ``unibody`` flag.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if "assets" not in payload:
            raise ValueError("Asset JSON object must contain an 'assets' array")
        entries = payload["assets"]
    else:
        entries = payload
    if not isinstance(entries, list) or not entries:
        raise ValueError("Asset JSON must be a non-empty list (or an object with non-empty 'assets')")
    return [_coerce_job(entry, index=i) for i, entry in enumerate(entries)]


def _resolve_job_paths(
    job: AssetJob,
) -> AssetJob:
    return AssetJob(
        input_path=job.input_path.resolve(),
        output_folder=job.output_folder.resolve(),
    )


def run_upgrade(
    source_usd: Path,
    output: Path | None,
    *,
    report_path: Path | None,
    plan_only: bool,
    source_profile: str,
    source_version: str,
    target_profile: str,
    target_version: str,
    require_validation: bool = True,
) -> int:
    source_usd = source_usd.resolve()
    package_root = package_root_for_usd(source_usd) if _is_usd_path(source_usd) else source_usd
    plan = build_plan(
        source_profile=source_profile,
        source_version=source_version,
        target_profile=target_profile,
        target_version=target_version,
    )
    report: dict = {
        "source_usd": str(source_usd),
        "source_package": str(package_root),
        "output": str(output) if output else None,
        "plan": plan,
        "steps": [],
        "status": "planned",
    }

    if plan_only:
        if report_path:
            core.write_report(report_path, report)
            print(json.dumps({"status": "planned", "report": str(report_path)}, indent=2))
        else:
            print(json.dumps(report, indent=2))
        return 0

    if not _is_usd_path(source_usd):
        report["status"] = "error"
        report["error"] = f"source must be a USD file path, got: {source_usd}"
        _finalize_report(report, report_path=report_path)
        return 2
    if not source_usd.is_file():
        report["status"] = "error"
        report["error"] = f"source USD not found: {source_usd}"
        _finalize_report(report, report_path=report_path)
        return 2

    if (
        plan["missing_inputs"]
        or plan["invalid_selected_features"]
        or plan["unresolved_target_features"]
    ):
        report["status"] = "unresolved_plan"
        report["error"] = "Upgrade plan has unresolved feature edges."
        _finalize_report(report, report_path=report_path)
        return 2

    if output is None:
        raise SystemExit("--output is required unless --plan is set")

    output = output.resolve()
    report["output"] = str(output)
    if output.exists():
        report["status"] = "blocked"
        report["error"] = f"output already exists: {output}"
        _finalize_report(report, report_path=report_path)
        return 2

    work_parent = output.parent
    work_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=".multiphysics_upgrade_", dir=str(work_parent)))
    work = tmp_dir / "package"
    run_started = time.perf_counter()

    try:
        step_started = time.perf_counter()
        core.copy_package_transactional(package_root, work)
        _append_step(
            report,
            step="copy_package",
            kind="phase",
            status="ok",
            elapsed_s=_elapsed_s(step_started),
        )
        usd_path = work / source_usd.name
        if not usd_path.is_file():
            raise core.UpgradeError(
                [
                    Blocker(
                        code="WORK_USD_MISSING",
                        requirement="runner",
                        detail=f"Copied package is missing expected USD: {usd_path}",
                    )
                ]
            )
        report["work_usd"] = str(usd_path)

        # Prevalidate source profile on the *copy* (never touch source).
        step_started = time.perf_counter()
        pre = (
            _run_validate(usd_path, source_profile, source_version)
            if require_validation
            else {"status": "skipped", "detail": "disabled by --skip-validation"}
        )
        _append_step(
            report,
            step="prevalidate_source",
            kind="phase",
            **pre,
            elapsed_s=_elapsed_s(step_started),
        )
        if pre.get("status") == "skipped" and require_validation:
            report["status"] = "validation_unavailable"
            report["error"] = "simready-validate is required; use --skip-validation to opt out."
            _finalize_report(report, report_path=report_path, run_started=run_started)
            return 2
        if pre.get("status") in {"failed", "error"}:
            report["status"] = "failed_prevalidate"
            report["error"] = "Source prevalidation failed."
            _finalize_report(report, report_path=report_path, run_started=run_started)
            return 2

        open_started = time.perf_counter()
        stage = Usd.Stage.Open(str(usd_path))
        _append_step(
            report,
            step="stage_open",
            kind="overhead",
            edge="all_adapters",
            status="ok" if stage is not None else "failed",
            elapsed_s=_elapsed_s(open_started),
        )
        if stage is None:
            raise core.UpgradeError(
                [
                    Blocker(
                        code="STAGE_OPEN_FAILED",
                        requirement="runner",
                        detail=f"Could not open {usd_path}",
                    )
                ]
            )

        skipped_multibody = False
        adapters_loop_started = time.perf_counter()
        adapters_loop_s: float | None = None
        blocked_edge = None
        blocked_exc: core.UpgradeError | None = None
        for edge in plan_edges():
            apply_started = time.perf_counter()
            try:
                mutation = edge.apply(stage)
                _append_step(
                    report,
                    step=edge.name,
                    kind="adapter",
                    input=edge.input_feature.key(),
                    output=edge.output_feature.key(),
                    status=mutation.status,
                    detail=mutation.detail,
                    artifacts=mutation.artifacts,
                    elapsed_s=_elapsed_s(apply_started),
                )
            except core.UpgradeError as exc:
                apply_s = _elapsed_s(apply_started)
                # Unibody assets skip FET_004 edges instead of failing the upgrade.
                if "multibody" in edge.name and any(b.code == "NOT_MULTIBODY" for b in exc.blockers):
                    skipped_multibody = True
                    _append_step(
                        report,
                        step=edge.name,
                        kind="adapter",
                        status="skipped",
                        detail="not a multibody asset",
                        blockers=core.blockers_to_dicts(exc.blockers),
                        elapsed_s=apply_s,
                    )
                    continue
                _append_step(
                    report,
                    step=edge.name,
                    kind="adapter",
                    status="blocked",
                    blockers=core.blockers_to_dicts(exc.blockers),
                    elapsed_s=apply_s,
                )
                blocked_edge = edge
                blocked_exc = exc
                break

        adapters_loop_s = _elapsed_s(adapters_loop_started)
        if blocked_exc is not None:
            release_started = time.perf_counter()
            stage = None
            _release_usd_handles()
            _append_step(
                report,
                step="stage_release",
                kind="overhead",
                edge="all_adapters",
                status="ok",
                elapsed_s=_elapsed_s(release_started),
            )
            report["status"] = "blocked"
            report["blockers"] = core.blockers_to_dicts(blocked_exc.blockers)
            report["error"] = f"Blocked on {blocked_edge.name}"
            _finalize_report(
                report,
                report_path=report_path,
                run_started=run_started,
                adapters_loop_s=adapters_loop_s,
            )
            return 2

        selected = list(DEFAULT_SELECTED_OPTIONALS)
        if skipped_multibody:
            selected = [pin for pin in selected if not pin.startswith(("FET004_", "CAP004_"))]
        step_started = time.perf_counter()
        stamp = core.stamp_target_profile(stage, target_profile, target_version, selected)
        _append_step(
            report,
            step="stamp_profile",
            kind="phase",
            **stamp.__dict__,
            elapsed_s=_elapsed_s(step_started),
        )
        report["detected_unibody"] = skipped_multibody

        step_started = time.perf_counter()
        isolation = core.inspect_neutral_runtime_isolation(stage)
        _append_step(
            report,
            step="inspect_isolation",
            kind="phase",
            **isolation.__dict__,
            elapsed_s=_elapsed_s(step_started),
        )

        save_started = time.perf_counter()
        stage.GetRootLayer().Save()
        _append_step(
            report,
            step="stage_save",
            kind="overhead",
            edge="all_adapters",
            status="ok",
            elapsed_s=_elapsed_s(save_started),
        )
        release_started = time.perf_counter()
        stage = None
        _release_usd_handles()
        _append_step(
            report,
            step="stage_release",
            kind="overhead",
            edge="all_adapters",
            status="ok",
            elapsed_s=_elapsed_s(release_started),
        )

        step_started = time.perf_counter()
        post = (
            _run_validate(usd_path, target_profile, target_version)
            if require_validation
            else {"status": "skipped", "detail": "disabled by --skip-validation"}
        )
        _append_step(
            report,
            step="postvalidate_target",
            kind="phase",
            **post,
            elapsed_s=_elapsed_s(step_started),
        )
        if post.get("status") == "skipped" and require_validation:
            report["status"] = "validation_unavailable"
            report["error"] = "simready-validate is required; output not promoted."
            _finalize_report(
                report,
                report_path=report_path,
                run_started=run_started,
                adapters_loop_s=adapters_loop_s,
            )
            return 2
        if post.get("status") in {"failed", "error"}:
            report["status"] = "failed_postvalidate"
            report["error"] = "Target postvalidation failed; output not promoted."
            _finalize_report(
                report,
                report_path=report_path,
                run_started=run_started,
                adapters_loop_s=adapters_loop_s,
            )
            return 2

        # Atomic promote: move completed package into the final output path.
        step_started = time.perf_counter()
        _release_usd_handles()
        shutil.move(str(work), str(output))
        _append_step(
            report,
            step="promote_output",
            kind="phase",
            status="ok",
            elapsed_s=_elapsed_s(step_started),
        )
        report["status"] = "ok"
        report["output"] = str(output)
        _finalize_report(
            report,
            report_path=report_path,
            run_started=run_started,
            adapters_loop_s=adapters_loop_s,
        )
        return 0
    except core.UpgradeError as exc:
        report["status"] = "blocked"
        report["blockers"] = core.blockers_to_dicts(exc.blockers)
        report["error"] = f"Blocked: {[b.code for b in exc.blockers]}"
        _finalize_report(report, report_path=report_path, run_started=run_started)
        return 2
    except Exception as exc:  # noqa: BLE001 - runner boundary
        report["status"] = "error"
        report["error"] = str(exc)
        _finalize_report(report, report_path=report_path, run_started=run_started)
        return 1
    finally:
        _release_usd_handles()
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_asset_errors(asset_report: dict[str, Any]) -> list[str]:
    """Flatten structured upgrade failures into a readable error list."""
    errors: list[str] = []
    if asset_report.get("error"):
        errors.append(str(asset_report["error"]))

    for blocker in asset_report.get("blockers") or []:
        code = blocker.get("code", "UNKNOWN")
        detail = blocker.get("detail", "")
        errors.append(f"{code}: {detail}".strip(": "))

    for step in asset_report.get("steps") or []:
        step_name = step.get("step", "step")
        for blocker in step.get("blockers") or []:
            code = blocker.get("code", "UNKNOWN")
            detail = blocker.get("detail", "")
            errors.append(f"{step_name}: {code}: {detail}".strip(": "))
        if step.get("status") in {"failed", "error", "failed_prevalidate", "failed_postvalidate"}:
            if step.get("detail"):
                errors.append(f"{step_name}: {step['detail']}")
            if step.get("stderr"):
                errors.append(f"{step_name}: {step['stderr'][-1000:]}")

    status = asset_report.get("status")
    if not errors and status and status != "ok":
        errors.append(str(status))
    if not errors:
        errors.append("Upgrade failed without a structured error message.")
    return list(dict.fromkeys(errors))


def run_asset_batch(
    jobs: list[AssetJob],
    *,
    report_path: Path,
    plan_only: bool,
    source_profile: str,
    source_version: str,
    target_profile: str,
    target_version: str,
    require_validation: bool,
) -> int:
    """Upgrade one or more packages; continues after per-asset failures."""
    resolved = [_resolve_job_paths(job) for job in jobs]
    batch_report: dict[str, Any] = {
        "status": "planned" if plan_only else "running",
        "source_profile": f"{source_profile}@{source_version}",
        "target_profile": f"{target_profile}@{target_version}",
        "total": len(resolved),
        "assets": [],
    }

    if plan_only:
        # Plan is profile-level; include resolved asset targets for inspection.
        plan = build_plan(
            source_profile=source_profile,
            source_version=source_version,
            target_profile=target_profile,
            target_version=target_version,
        )
        batch_report["plan"] = plan
        batch_report["assets"] = [
            {
                "input_path": str(job.input_path),
                "output_folder": str(job.output_folder),
                "pass": None,
                "errors": [],
            }
            for job in resolved
        ]
        core.write_report(report_path, batch_report)
        print(json.dumps({"status": "planned", "report": str(report_path)}, indent=2))
        return 0

    worst = 0
    with tempfile.TemporaryDirectory(prefix="multiphysics_batch_reports_") as report_tmp:
        temporary_report_root = Path(report_tmp)
        for index, job in enumerate(resolved):
            asset_report_path = temporary_report_root / f"asset_{index}.json"
            code = run_upgrade(
                job.input_path,
                job.output_folder,
                report_path=asset_report_path,
                plan_only=False,
                source_profile=source_profile,
                source_version=source_version,
                target_profile=target_profile,
                target_version=target_version,
                require_validation=require_validation,
            )
            # Release any retained USD layer handles before the next package (Windows).
            _release_usd_handles()

            if asset_report_path.is_file():
                asset_report = json.loads(asset_report_path.read_text(encoding="utf-8"))
            else:
                asset_report = {
                    "status": "error",
                    "error": "The asset run did not produce a structured report.",
                }

            passed = code == 0
            entry = {
                "input_path": str(job.input_path),
                "output_folder": str(job.output_folder),
                "pass": passed,
                "errors": [] if passed else _extract_asset_errors(asset_report),
                "detected_unibody": asset_report.get("detected_unibody"),
                "status": asset_report.get("status"),
                "returncode": code,
                "profiling": asset_report.get("profiling"),
                "steps": asset_report.get("steps", []),
            }
            batch_report["assets"].append(entry)
            worst = max(worst, code)

    batch_report["status"] = "ok" if worst == 0 else "failed"
    core.write_report(report_path, batch_report)
    print(
        json.dumps(
            {
                "status": batch_report["status"],
                "total": batch_report["total"],
                "passed": sum(1 for asset in batch_report["assets"] if asset["pass"]),
                "failed": sum(1 for asset in batch_report["assets"] if not asset["pass"]),
                "report": str(report_path),
            },
            indent=2,
        )
    )
    return worst


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "Source root USD path (never edited). Package-level copy/promote uses "
            "the USD's parent directory. Omit when using --assets-json."
        ),
    )
    ap.add_argument(
        "--assets-json",
        type=Path,
        default=None,
        help=(
            "JSON list of assets to upgrade. Accepts "
            "[{\"input_path\": \"<usd>\", \"output_folder\": \"...\"}, ...] "
            "or {\"assets\": [...]}. Multibody vs unibody is detected at runtime."
        ),
    )
    ap.add_argument("--output", type=Path, default=None, help="Destination package directory.")
    ap.add_argument(
        "--report",
        type=Path,
        default=None,
        help="JSON report path. Required with --assets-json; contains every success and failure.",
    )
    ap.add_argument("--plan", action="store_true", help="Print the ordered edge plan and exit.")
    ap.add_argument("--source-profile", required=True)
    ap.add_argument("--source-version", required=True)
    ap.add_argument("--target-profile", default="Robotics-Prop")
    ap.add_argument("--target-version", default="3.1.0")
    ap.add_argument(
        "--skip-validation",
        action="store_true",
        help="Allow promotion when simready-validate is unavailable (isolation inspection still runs).",
    )
    args = ap.parse_args(argv)

    if args.assets_json and args.source:
        ap.error("Pass either a positional source or --assets-json, not both")
    if not args.assets_json and args.source is None:
        ap.error("Provide a positional source USD path or --assets-json")
    if args.assets_json and args.output:
        ap.error("Use per-asset 'output_folder' fields with --assets-json (not --output)")
    if args.assets_json and args.report is None:
        ap.error("--report is required with --assets-json")

    if args.assets_json:
        try:
            jobs = load_assets_json(args.assets_json.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Failed to load --assets-json: {exc}", file=sys.stderr)
            return 2
        return run_asset_batch(
            jobs,
            report_path=args.report.resolve(),
            plan_only=args.plan,
            source_profile=args.source_profile,
            source_version=args.source_version,
            target_profile=args.target_profile,
            target_version=args.target_version,
            require_validation=not args.skip_validation,
        )

    return run_upgrade(
        args.source,
        args.output,
        report_path=args.report,
        plan_only=args.plan,
        source_profile=args.source_profile,
        source_version=args.source_version,
        target_profile=args.target_profile,
        target_version=args.target_version,
        require_validation=not args.skip_validation,
    )


if __name__ == "__main__":
    raise SystemExit(main())

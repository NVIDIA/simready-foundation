# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Author PhysX/Newton/MuJoCo runtime payloads on a Neutral prop stage, then
run the Isaac transformer over the result.

Copies the source USD's package folder into DEST, then edits the copy:

    $env:PYTHONPATH = "nv_core/cip_specs"
    python -m asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes path/to/sm_asset_01.usd path/to/dest_folder
    python -m asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes --assets-json asset_list.json --report batch.json
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
from pathlib import Path

from pxr import Usd

from . import core
from .runner import AssetJob, load_assets_json
from .transformer_bootstrap import load_transform_package

# Scratch name for the generated Isaac interface layer. The transformer opens
# its interface path with Sdf.Layer.FindOrOpen, so naming it after the asset
# would author the interface on top of the pre-transform content instead of
# replacing it.
ISAAC_INTERFACE_NAME = "__isaac_interface__.usda"

# Legacy simready_physx_usd counterparts mix real edits with schema defaults
# (mass=0 / CoM at origin) that we cannot treat as trusted tuning yet.
IMPORT_PHYSX_TUNING = False


def copy_source_package(source_usd: Path, dest_folder: Path) -> Path:
    """Copy the folder that contains ``source_usd`` into ``dest_folder``.

    Returns the path to the copied USD. Refuses to overwrite ``dest_folder`` or
    to copy a package onto itself.
    """
    source_usd = source_usd.resolve()
    dest_folder = dest_folder.resolve()
    package_root = source_usd.parent
    if dest_folder == package_root:
        raise core.UpgradeError(
            [
                core.Blocker(
                    code="DEST_IS_SOURCE",
                    requirement="neutral_to_runtimes",
                    detail=f"dest folder is the source package: {dest_folder}",
                )
            ]
        )
    core.copy_package_transactional(package_root, dest_folder)
    dest_usd = dest_folder / source_usd.name
    if not dest_usd.is_file():
        raise core.UpgradeError(
            [
                core.Blocker(
                    code="WORK_USD_MISSING",
                    requirement="neutral_to_runtimes",
                    detail=f"Copied package is missing expected USD: {dest_usd}",
                )
            ]
        )
    return dest_usd


def resolve_physx_tuning_usd(source_usd: Path, explicit_path: Path | None = None) -> Path | None:
    """Resolve an optional legacy ``simready_physx_usd`` counterpart."""
    if explicit_path is not None:
        candidate = explicit_path.expanduser().resolve()
        return candidate if candidate.is_file() else None

    source_usd = source_usd.resolve()
    if source_usd.parent.name.lower() != "simready_usd":
        return None
    candidate = source_usd.parent.parent / "simready_physx_usd" / source_usd.name
    return candidate.resolve() if candidate.is_file() else None


def upgrade_stage(stage: Usd.Stage, tuned_stage: Usd.Stage | None = None) -> dict:
    core.apply_minimal_upgrade(stage)

    core.apply_runtime_scaffold(stage, "PhysX")
    core.apply_runtime_scaffold(stage, "Newton")
    core.apply_runtime_scaffold(stage, "MuJoCo")

    core.apply_standard_to_physx_rigid_body(stage)
    core.apply_standard_to_newton_rigid_body(stage)
    core.apply_standard_to_mujoco_rigid_body(stage)

    tuning_report = (
        core.apply_physics_tuning(stage, tuned_stage)
        if tuned_stage is not None
        else {
            "status": "not_found",
            "summary": {"applied": 0, "unchanged": 0, "skipped": 0},
            "changes": [],
            "skipped": [],
        }
    )
    stage.GetRootLayer().Save()
    return tuning_report


def isaac_transform(work_usd: Path) -> Path:
    """Transform the package holding ``work_usd`` into Isaac composition.

    ``transform_package`` writes its layered output into the package folder it
    is given, so pointing it at the folder we already copied keeps the whole
    result in one place. The generated interface starts under a scratch name and
    is moved onto the asset name here; both live in the package root, so the
    interface's relative layer paths stay valid across the move.
    """
    transform_package = load_transform_package()
    transform_package(str(work_usd), work_usd.parent, interface_asset_name=ISAAC_INTERFACE_NAME)

    # Move the interface before deleting anything, so a transform that produced
    # no interface layer fails without taking the asset with it.
    interface_usd = work_usd.with_suffix(".usda")
    os.replace(work_usd.parent / ISAAC_INTERFACE_NAME, interface_usd)
    if work_usd != interface_usd:
        work_usd.unlink()
    return interface_usd


def _release_usd_handles() -> None:
    gc.collect()
    Usd.StageCache().Clear()


def run_one(
    source_usd: Path,
    dest_folder: Path,
    *,
    physx_tuning_usd: Path | None = None,
) -> dict:
    """Copy, upgrade, and Isaac-transform one asset. Never edits the source."""
    source_usd = source_usd.resolve()
    dest_folder = dest_folder.resolve()
    result = {
        "input_path": str(source_usd),
        "output_folder": str(dest_folder),
        "pass": False,
        "errors": [],
        "output_usd": None,
    }
    if not source_usd.is_file():
        result["errors"].append(f"could not find source USD {source_usd}")
        return result

    try:
        dest_usd = copy_source_package(source_usd, dest_folder)
        stage = Usd.Stage.Open(str(dest_usd))
        if stage is None:
            result["errors"].append(f"could not open {dest_usd}")
            return result

        tuned_stage = None
        if IMPORT_PHYSX_TUNING:
            requested = physx_tuning_usd.expanduser().resolve() if physx_tuning_usd else None
            tuning_usd = resolve_physx_tuning_usd(source_usd, requested)
            tuned_stage = Usd.Stage.Open(str(tuning_usd)) if tuning_usd is not None else None
            if tuning_usd is not None and tuned_stage is None:
                result["errors"].append(f"could not open PhysX tuning USD {tuning_usd}")
                return result
            tuning_report = upgrade_stage(stage, tuned_stage)
            tuning_report["neutral_source_usd"] = str(source_usd)
            tuning_report["physx_tuning_usd"] = (
                str(tuning_usd or requested) if (tuning_usd or requested) else None
            )
            tuning_report["auto_discovery"] = requested is None
            core.write_report(dest_folder / "physics_tuning_report.json", tuning_report)
        else:
            upgrade_stage(stage)

        del tuned_stage
        del stage
        _release_usd_handles()

        output_usd = isaac_transform(dest_usd)
        result["pass"] = True
        result["output_usd"] = str(output_usd)
        return result
    except core.UpgradeError as exc:
        result["errors"].append(str(exc))
        return result
    except Exception as exc:
        result["errors"].append(str(exc))
        return result
    finally:
        _release_usd_handles()


def run_asset_batch(jobs: list[AssetJob], report_path: Path) -> int:
    """Run ``run_one`` for each job. Failures do not stop the rest of the list."""
    batch_report = {
        "status": "ok",
        "total": len(jobs),
        "assets": [],
    }
    worst = 0
    for job in jobs:
        print(f"processing {job.input_path} -> {job.output_folder}", flush=True)
        entry = run_one(job.input_path, job.output_folder)
        batch_report["assets"].append(entry)
        if entry["pass"]:
            print(f"ok: {entry['output_usd']}", flush=True)
        else:
            worst = 2
            for err in entry["errors"]:
                print(err, file=sys.stderr)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source_usd",
        type=Path,
        nargs="?",
        default=None,
        help="Neutral root USD. Omit when using --assets-json.",
    )
    parser.add_argument(
        "dest_folder",
        type=Path,
        nargs="?",
        default=None,
        help="New output package directory. Omit when using --assets-json.",
    )
    parser.add_argument(
        "--assets-json",
        type=Path,
        default=None,
        help=(
            "JSON list of assets. Accepts "
            "[{\"input_path\": \"<usd>\", \"output_folder\": \"...\"}, ...] "
            "or {\"assets\": [...]}."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Batch JSON report path. Required with --assets-json.",
    )
    parser.add_argument(
        "--physx-tuning-usd",
        type=Path,
        default=None,
        help=(
            "Legacy PhysX-tuned counterpart for a single-asset run. By default, "
            "a same-named USD is looked up in the sibling simready_physx_usd folder."
        ),
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.assets_json and (args.source_usd or args.dest_folder):
        parser.error("Pass either positional source/dest or --assets-json, not both")
    if args.assets_json and args.report is None:
        parser.error("--report is required with --assets-json")
    if args.assets_json and args.physx_tuning_usd is not None:
        parser.error("Use per-asset counterparts with --assets-json (not --physx-tuning-usd)")
    if not args.assets_json and (args.source_usd is None or args.dest_folder is None):
        parser.error("Provide source USD and dest folder, or --assets-json")

    if args.assets_json:
        try:
            jobs = load_assets_json(args.assets_json.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Failed to load --assets-json: {exc}", file=sys.stderr)
            return 2
        return run_asset_batch(jobs, args.report.resolve())

    entry = run_one(args.source_usd, args.dest_folder, physx_tuning_usd=args.physx_tuning_usd)
    if entry["pass"]:
        print(f"ok: {entry['output_usd']}")
        return 0
    for err in entry["errors"]:
        print(err, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

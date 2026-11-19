#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise RV.010/RV.011 attribution through the installed public validator CLI.

This is static validation QA, not simulation or asset conformance. Generated
negative fixtures intentionally fail requirements outside the attribution gate.
See docs/guides/runtime_attribution_qa.md for the test plan.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

RUNTIMES = ("PhysX", "Newton", "MuJoCo")
CONTRACTS = {name: f"CAP000_Core.{name}.0-2-0" for name in RUNTIMES}
CODES = {"RV.010", "RV.011"}
CASES = {"clean": None, "inline_physx": "RV.010", "foreign_physx": "RV.011"}


def make_fixture(directory: Path, case: str) -> Path:
    """Author separate geometry and runtime payload layers; never edit samples."""
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics

    directory.mkdir(parents=True)
    (directory / "payloads").mkdir()
    geometry = Usd.Stage.CreateNew(str(directory / "payloads" / "geometry.usda"))
    root = UsdGeom.Xform.Define(geometry, "/Asset").GetPrim()
    geometry.SetDefaultPrim(root)
    UsdGeom.Cube.Define(geometry, "/Asset/Cube")
    UsdPhysics.RigidBodyAPI.Apply(root)
    UsdPhysics.MassAPI.Apply(root).CreateMassAttr(1.0)
    geometry.GetRootLayer().Save()

    physics = directory / "runnables" / "physics"
    physics.mkdir(parents=True)
    for runtime in RUNTIMES:
        payload = Usd.Stage.CreateNew(str(physics / f"{runtime.lower()}.usda"))
        body = UsdGeom.Xform.Define(payload, "/Asset").GetPrim()
        payload.SetDefaultPrim(body)
        if case == "foreign_physx" and runtime == "PhysX":
            # Native Newton data is foreign in the PhysX composition. Reading
            # apiSchemas also detects the leak without a Newton schema plugin.
            body.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonCollisionAPI"]))
            body.CreateAttribute("newton:contactGap", Sdf.ValueTypeNames.Float).Set(0.01)
        payload.GetRootLayer().Save()

    path = directory / "asset.usda"
    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root.GetReferences().AddReference("./payloads/geometry.usda")
    metadata = {}
    for runtime in RUNTIMES:
        variants = root.GetVariantSets().AddVariantSet(runtime)
        variants.AddVariant("Disabled")
        variants.AddVariant("Enabled")
        variants.SetVariantSelection("Enabled")
        with variants.GetVariantEditContext():
            root.GetPayloads().AddPayload(f"./runnables/physics/{runtime.lower()}.usda")
            if case == "inline_physx" and runtime == "PhysX":
                root.CreateAttribute("qa:inlineOpinion", Sdf.ValueTypeNames.Float).Set(1.0)
        variants.SetVariantSelection("Disabled")
        metadata[runtime] = {"prim": "/Asset", "variantSetName": runtime, "activateOption": "Enabled"}
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": {"Variants": {"Physics": metadata}}}
    stage.GetRootLayer().Save()
    return path


def failed_codes(entry: dict, key: str) -> set[str]:
    """Read both JSON arrays and the validator's serialized Python-list fields."""
    value = entry.get(key, [])
    if isinstance(value, str):
        value = ast.literal_eval(value)
    if not isinstance(value, list) or not all(isinstance(code, str) for code in value):
        raise ValueError(f"Invalid requirement list in {key}: {value!r}")
    return {code.removeprefix("com.nvidia.simready.") for code in value}


def check_report(report: dict, assets: dict[str, Path], profile: str, required: str | None) -> list[str]:
    failures = []
    for case, asset in assets.items():
        record = report.get(str(asset))
        if not isinstance(record, dict):
            failures.append(f"{profile}/{case}: no asset result")
            continue
        if record.get("profile_id") != profile or record.get("profile_version") != ("5.0.0" if required is None else "0.0.0"):
            failures.append(f"{profile}/{case}: profile identity missing or incorrect")
        summary = record.get("features_summary", {})
        for runtime, contract in CONTRACTS.items():
            entry = summary.get(contract)
            if not isinstance(entry, dict):
                failures.append(f"{profile}/{case}: missing {contract}")
                continue
            hard = failed_codes(entry, "failing requirements") & CODES
            soft = failed_codes(entry, "optional requirements") & CODES
            expected = {CASES[case]} if runtime == "PhysX" and CASES[case] else set()
            expected_hard = expected if runtime == required else set()
            expected_soft = expected if runtime != required else set()
            if hard != expected_hard or soft != expected_soft:
                failures.append(f"{profile}/{case}/{runtime}: hard={sorted(hard)}, optional={sorted(soft)}; "
                                f"expected hard={sorted(expected_hard)}, optional={sorted(expected_soft)}")
            if expected and entry.get("passed") is not False:
                failures.append(f"{profile}/{case}/{runtime}: negative check marked passed")
            if required is not None and entry.get("passed") is not (not bool(expected)):
                failures.append(f"{profile}/{case}/{runtime}: incorrect contract verdict")
            if required is not None and entry.get("blocking_failure") != bool(expected_hard):
                failures.append(f"{profile}/{case}/{runtime}: incorrect blocking_failure")
    return failures


def source_catalog_args(root: Path) -> list[str]:
    args = []
    for tier in ("core", "newton"):
        package = root / f"nv_core/tiers/simready_foundation_tier_{tier}/simready/foundation/tier_{tier}"
        args += ["--rules-path", str(package / "rules_and_reqs")]
        for name in ("features", "capabilities"):
            if (package / name).is_dir():
                args += ["--features-path", str(package / name)]
        if (package / "profiles").is_dir():
            args += ["--profiles-path", str(package / "profiles")]
    return args


def installed_catalog_args() -> list[str]:
    """Keep installed tier content available when adding a QA profile path."""
    args, found = [], set()
    required = {"tier_core", "tier_newton"}
    for entry in sorted(entry_points(group="simready.tier"), key=lambda item: (item.name, item.value)):
        content = entry.load()
        if content.name not in required or content.name in found:
            continue
        found.add(content.name)
        args += ["--rules-path", str(content.rules_and_requirements_path)]
        for path in (content.feature_contracts_path, content.capability_contracts_path):
            if path.is_dir():
                args += ["--features-path", str(path)]
        if content.profile_contracts_path.is_dir():
            args += ["--profiles-path", str(content.profile_contracts_path)]
    if required - found:
        raise RuntimeError(f"Missing installed simready.tier descriptors: {', '.join(sorted(required - found))}")
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory (must not exist)")
    parser.add_argument("--validator", default=shutil.which("simready-validate"), help="Installed simready-validate executable")
    parser.add_argument("--catalog-root", type=Path, help="Optional Foundation checkout whose Core/Newton catalogs are under test")
    args = parser.parse_args()
    if not args.validator:
        parser.error("simready-validate is not installed or not on PATH; pass --validator")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    assets = {case: make_fixture(output / case, case) for case in CASES}
    asset_list = output / "assets.txt"
    asset_list.write_text("\n".join(map(str, assets.values())) + "\n", encoding="utf-8")
    catalog_args = source_catalog_args(args.catalog_root.resolve()) if args.catalog_root else installed_catalog_args()
    failures, runs = [], []
    for required in (None, "PhysX", "Newton"):
        profile = "Robotics-Prop" if required is None else f"QA-Runtime-Attribution-{required}Required"
        extra = []
        if required is not None:
            # QA-only profiles isolate hard/soft bucketing; published profiles
            # remain immutable. Dependencies retain the native Core contract.
            selectors = [f'{{selector = "{contract}", optional = {str(runtime != required).lower()}}}'
                         for runtime, contract in CONTRACTS.items()]
            config = output / f"{profile}.toml"
            config.write_text(f'[{profile}]\n"0.0.0" = {{capabilities = [{", ".join(selectors)}]}}\n', encoding="utf-8")
            extra = ["--profiles-path", str(config)]
        report_path = output / f"{profile}.json"
        command = [args.validator, *catalog_args, *extra, "--profile", profile, "--version",
                   "5.0.0" if required is None else "0.0.0", "--asset_list", str(asset_list),
                   "--output", str(report_path)]
        run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (output / f"{profile}.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        runs.append({"command": command, "exit_code": run.returncode, "report": str(report_path)})
        if run.returncode not in (0, 1):
            failures.append(f"{profile}: CLI exited {run.returncode}")
        if required is not None and run.returncode != (1 if required == "PhysX" else 0):
            failures.append(f"{profile}: unexpected profile verdict (CLI exit {run.returncode})")
        try:
            failures.extend(check_report(json.loads(report_path.read_text(encoding="utf-8")), assets, profile, required))
        except (OSError, ValueError, TypeError, SyntaxError) as exc:
            failures.append(f"{profile}: unreadable report: {exc}")
    result = {"qa_passed": not failures, "scope": "static runtime attribution; partial - not submission-ready",
              "full_profile_target": "Robotics-Prop@5.0.0", "runs": runs, "failures": failures}
    (output / "qa_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"{'PASS' if not failures else 'FAIL'}: runtime attribution QA; evidence: {output}")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())

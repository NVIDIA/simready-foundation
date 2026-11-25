# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validate a named installed 0.3 profile and record measured offline coverage."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import simready.validate as sv
from pxr import Usd
from usd_validation_nvidia import ProfileRegistry, RequirementsRegistry, ValidationEngine


HERE = Path(__file__).resolve().parent
ASSET = HERE / "asset/Synthetic_NetworkEquipment.usda"


def validate(output, profile_id="AIF-Entity"):
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    try:
        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str(ASSET), profile_id=profile_id, profile_version="0.3.0",
        ))
        if result is None or not result.features_summary:
            raise RuntimeError("Full-profile evaluation is unavailable; inspect validator diagnostics")
        if "CAP204_Networking.0-3-0" not in result.features_summary:
            raise RuntimeError(f"{profile_id} 0.3.0 is missing the Networking capability")
        if profile_id == "Networking" and "FET207_SimulationNetworkTopology.0-3-0" not in result.features_summary:
            raise RuntimeError("Networking 0.3.0 is missing the Simulation Network Topology feature")
        profile = ProfileRegistry().find(profile_id, "0.3.0")
        registry = RequirementsRegistry()
        requirements = [registry.find_requirement(code) for code in sorted(profile.mandatory_requirements)]
        if not requirements or not all(requirements):
            raise RuntimeError("The selected profile has unavailable requirements")
        engine = ValidationEngine(init_rules=False)
        for requirement in requirements:
            engine.enable_requirement(requirement)
        issues = engine.validate(str(ASSET))
        executed_rules = {rule for rule, _ in engine.stats.get_rule_times()}
        executed = [r.code for r in requirements if registry.get_validator(r) in executed_rules]
        passed = (sv.features_summary_passed(result.features_summary)
                  and len(executed) == len(requirements) and not issues)
        report = {
            "schema": "simready-example-validation-summary-v1",
            "asset": "asset/Synthetic_NetworkEquipment.usda",
            "profile": {"name": profile_id, "version": "0.3.0"},
            "passed": passed,
            "executed_requirements": len(executed),
            "selected_requirements": len(requirements),
            "requirement_codes": sorted(executed),
            "contracts": result.features_summary,
            "issues": [{"severity": issue.severity.name, "message": issue.message} for issue in issues],
            "package_versions": {name: version(name) for name in (
                "simready-validate", "usd-validation-nvidia", "usd-core",
                "simready-foundation-tier-core", "simready-foundation-tier-aif",
            )},
            "asset_file_sha256": {
                str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((HERE / "asset").rglob("*")) if path.is_file()
            },
        }
        if output is not None:
            Path(output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{profile_id} 0.3.0: {'PASS' if passed else 'FAIL'}; "
              f"{len(executed)}/{len(requirements)} requirements executed; {len(issues)} issues")
        if not passed:
            raise SystemExit(1)
        return report
    finally:
        sv.destroy()


def stamp_profiles():
    """Record both genuine static profile passes, then hash the final files.

    Preflight executes both complete profiles before the interface is changed.
    The maintained validator writes profile-keyed USD receipts; it does not run
    or stamp runtime tests. Read-only reruns then refresh both human summaries
    against the final stamped interface, preserving single-profile CLI behavior.
    """
    profiles = ("AIF-Entity", "Networking")
    for profile_id in profiles:
        validate(None, profile_id)
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    try:
        stage = Usd.Stage.Open(str(ASSET))
        results = sv.validate_stage_against_profiles(
            stage, targets=[sv.ProfileTarget(name, "0.3.0") for name in profiles],
            asset_path=str(ASSET),
        )
        if len(results) != len(profiles) or not all(
            result is not None and sv.features_summary_passed(result.features_summary)
            for result in results
        ):
            raise RuntimeError("Both static profile passes are required; inspect validator diagnostics")
        # The validator rewrites customLayerData through Python, which widens
        # authored USD floats to doubles. Apply only its validation dictionary.
        receipts = Usd.Stage.CreateInMemory()
        sv.set_simready_validation_metadata(receipts, sv.get_simready_validation_metadata(stage))
        sv.add_profile_validation_results_to_metadata(receipts, results)
        stage.SetMetadataByDictKey("customLayerData", "SimReady_Metadata:validation",
                                   sv.get_simready_validation_metadata(receipts))
        stage.GetRootLayer().Save()
    finally:
        sv.destroy()
    return {
        profile_id: validate(HERE / filename, profile_id)
        for profile_id, filename in (
            ("AIF-Entity", "validation.json"),
            ("Networking", "validation-networking.json"),
        )
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stamp", action="store_true",
                        help="Record both genuine static profile receipts and refresh both standard reports")
    parser.add_argument("--profile", choices=("AIF-Entity", "Networking"), default="AIF-Entity")
    parser.add_argument("--output", type=Path, help="Report path; defaults to a separate report per profile")
    args = parser.parse_args()
    if args.stamp:
        if args.output is not None:
            parser.error("--stamp refreshes both standard reports; --output applies to a single-profile run")
        stamp_profiles()
    else:
        report_name = "validation.json" if args.profile == "AIF-Entity" else "validation-networking.json"
        validate(args.output or HERE / report_name, args.profile)

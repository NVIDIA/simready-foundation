# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validate a named installed 0.3 profile and record measured offline coverage."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import simready.validate as sv
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
        Path(output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{profile_id} 0.3.0: {'PASS' if passed else 'FAIL'}; "
              f"{len(executed)}/{len(requirements)} requirements executed; {len(issues)} issues")
        if not passed:
            raise SystemExit(1)
        return report
    finally:
        sv.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("AIF-Entity", "Networking"), default="AIF-Entity")
    parser.add_argument("--output", type=Path, help="Report path; defaults to a separate report per profile")
    args = parser.parse_args()
    report_name = "validation.json" if args.profile == "AIF-Entity" else "validation-networking.json"
    validate(args.output or HERE / report_name, args.profile)

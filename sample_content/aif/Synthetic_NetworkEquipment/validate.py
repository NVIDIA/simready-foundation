# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validate the full installed AIF-Entity 0.3 profile and record measured coverage."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import simready.validate as sv
from usd_validation_nvidia import ProfileRegistry, RequirementsRegistry, ValidationEngine


HERE = Path(__file__).resolve().parent
ASSET = HERE / "asset/Synthetic_NetworkEquipment.usda"


def validate(output):
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    try:
        result = sv.validate_asset(sv.AssetValidationConfig(
            asset_path=str(ASSET), profile_id="AIF-Entity", profile_version="0.3.0",
        ))
        if result is None or not result.features_summary:
            raise RuntimeError("Full-profile evaluation is unavailable; inspect validator diagnostics")
        if "CAP204_NetworkEquipment.0-3-0" not in result.features_summary:
            raise RuntimeError("AIF-Entity 0.3.0 is missing the network-equipment capability")
        profile = ProfileRegistry().find("AIF-Entity", "0.3.0")
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
            "profile": {"name": "AIF-Entity", "version": "0.3.0"},
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
        print(f"AIF-Entity 0.3.0: {'PASS' if passed else 'FAIL'}; "
              f"{len(executed)}/{len(requirements)} requirements executed; {len(issues)} issues")
        if not passed:
            raise SystemExit(1)
        return report
    finally:
        sv.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "validation.json")
    validate(parser.parse_args().output)

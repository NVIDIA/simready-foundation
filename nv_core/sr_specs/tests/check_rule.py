# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Spot-check a single asset against a single validation rule.

This is a developer convenience CLI, not part of the pytest test suite. Use it
when you want to run one rule against one asset and see the actual outcome
without going through the pytest reporting layer.

Usage:
    python -m tests.check_rule <asset.usda> <CODE>

Example:
    python -m tests.check_rule tests\\aif\\fixtures\\variants\\am_fail_no_assetClass.usda AM.002

Exit codes:
    0  success (the script ran cleanly; the rule outcome is in stdout)
    1  usage error (missing/extra args, asset not found, unknown rule code)
"""
import sys
from pathlib import Path

from omni.asset_validator import IssueSeverity, RequirementsRegistry, ValidationEngine
from simready.validate.impl.loader import load_validation_implementation

USAGE = (
    "Usage: python -m tests.check_rule <asset.usda> <CODE>\n"
    "  e.g.  python -m tests.check_rule "
    "tests/aif/fixtures/variants/am_fail_no_assetClass.usda AM.002"
)

# tests/check_rule.py -> tests/ -> sr_specs/. The docs/ tree holds the
# capability, feature, and profile definitions the loader reads.
_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def main() -> int:
    if len(sys.argv) != 3:
        print(USAGE, file=sys.stderr)
        return 1

    asset_path = Path(sys.argv[1]).resolve()
    code = sys.argv[2]

    if not asset_path.exists():
        print(f"ERROR: Asset not found: {asset_path}", file=sys.stderr)
        return 1

    # Pytest's conftest.py runs the bootstrap automatically, but this script
    # is invoked as plain Python; we have to run the loader ourselves so the
    # RequirementsRegistry is populated before we query it.
    load_validation_implementation(
        rules_and_requirements_paths=[_DOCS_DIR / "capabilities"],
        features_paths=[_DOCS_DIR / "features"],
        profiles_paths=[_DOCS_DIR / "profiles" / "profiles.toml"],
    )

    requirement = RequirementsRegistry().find_requirement(code)
    if requirement is None:
        print(f"ERROR: Unknown requirement code: {code}", file=sys.stderr)
        return 1

    # Build a fresh engine with only this one rule enabled so collateral
    # failures from unrelated rules don't pollute the report.
    engine = ValidationEngine(init_rules=False)
    engine.enable_requirement(requirement)
    results = engine.validate(str(asset_path))

    failures = [
        issue
        for issue in results
        if issue.severity is IssueSeverity.FAILURE
        and issue.requirement is not None
        and issue.requirement.code == code
    ]

    print()
    print("=" * 72)
    print(f"Asset:       {asset_path}")
    print(f"Requirement: {code}")
    print("=" * 72)
    if failures:
        print(f"RESULT: {code} FIRED ({len(failures)} failure issue(s))")
        for i, issue in enumerate(failures, 1):
            print(f"  [{i}] {issue.message}")
    else:
        print(f"RESULT: {code} did not fire (asset passes under this rule)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

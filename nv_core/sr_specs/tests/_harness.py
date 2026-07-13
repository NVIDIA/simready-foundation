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
Shared assertion helpers for fixture-based validator tests.

This is a regular Python module (not a pytest conftest). Domain test files
import these helpers with `from .._harness import ...`. Both helpers take
requirement *codes* (strings like "AM.002") and resolve them against the
RequirementsRegistry that conftest.py's bootstrap populated. That registry
is the framework's single source of truth for code -> rule class, so the
test code never needs its own mapping table.

The two helpers wrap the same three-step pattern:

    1. Build a fresh ValidationEngine with no rules pre-loaded.
    2. Enable the requirement(s) we want to evaluate (the engine looks up
       the underlying rule class via RequirementsRegistry).
    3. Run the engine against the asset and inspect the returned Results
       for FAILURE-severity issues.

The leading underscore in the filename (`_harness.py`) marks it as an
internal-to-the-test-suite module: it is not a test file pytest should
collect, and the underscore signals "implementation detail."
"""
from pathlib import Path

from omni.asset_validator import IssueSeverity, RequirementsRegistry, ValidationEngine


def _resolve_requirement(code: str):
    """Look up a requirement by its spec code (e.g., 'AM.002') or fail loudly."""
    req = RequirementsRegistry().find_requirement(code)
    assert req is not None, (
        f"Requirement code '{code}' is not registered. "
        f"Check the spelling, or confirm load_validation_implementation() "
        f"in conftest.py is pointing at the right docs/capabilities path."
    )
    return req


def assert_rule_fires(asset_path: Path, requirement_code: str) -> None:
    """Validate `asset_path` against a single requirement and assert it
    produces at least one FAILURE issue tagged with that requirement.

    Used by negative tests: each broken variant fixture is paired with
    exactly one targeted requirement, and we assert the validator catches it.

    Args:
        asset_path: Filesystem path to the .usda/.usd fixture to validate.
                    Must exist on disk; checked upfront so the test fails
                    with a clear "fixture missing" message rather than an
                    opaque engine error.
        requirement_code: A spec code like "AM.002". Resolved against
                    RequirementsRegistry, which the bootstrap populates.
    """
    assert asset_path.exists(), f"Fixture not found on disk: {asset_path}"

    requirement = _resolve_requirement(requirement_code)

    # init_rules=False starts with an empty rule set. Without this, the engine
    # would auto-load every registered rule and run them all, which would
    # report unrelated failures from this minimal fixture and obscure the
    # signal we care about.
    engine = ValidationEngine(init_rules=False)
    engine.enable_requirement(requirement)
    results = engine.validate(str(asset_path))

    # Filter to FAILURE-severity issues attributed to the targeted requirement.
    # Matching by issue.requirement.code is more robust than matching by rule
    # class: if the framework ever changes how it threads the rule class onto
    # issues, the requirement field stays stable.
    failures = [
        issue
        for issue in results
        if issue.severity is IssueSeverity.FAILURE
        and issue.requirement is not None
        and issue.requirement.code == requirement_code
    ]
    assert failures, (
        f"Expected {requirement_code} to report at least one FAILURE on "
        f"{asset_path.name}, but none were reported.\n"
        f"All issues returned by the engine: {list(results)}"
    )


def assert_no_failures(asset_path: Path, requirement_codes: list[str]) -> None:
    """Validate `asset_path` against the given requirements and assert ZERO
    FAILURE-severity issues are produced.

    Used by clean-baseline tests: full compliant assets must pass cleanly
    under their applicable requirement set (the list varies because some
    fixtures are equipment classes for which not every rule applies, e.g.
    GB300 compute rack has no thermal-cooling subsystem).

    Args:
        asset_path: Filesystem path to the .usda/.usd fixture to validate.
        requirement_codes: Every requirement that must pass on this fixture.
    """
    assert asset_path.exists(), f"Fixture not found on disk: {asset_path}"

    engine = ValidationEngine(init_rules=False)
    for code in requirement_codes:
        engine.enable_requirement(_resolve_requirement(code))
    results = engine.validate(str(asset_path))

    failures = [issue for issue in results if issue.severity is IssueSeverity.FAILURE]
    assert not failures, (
        f"Expected no failures on {asset_path.name} under requirements "
        f"{requirement_codes}, but got:\n"
        + "\n".join(
            f"  {(issue.rule.__name__ if issue.rule else '?')}: {issue.message}"
            for issue in failures
        )
    )

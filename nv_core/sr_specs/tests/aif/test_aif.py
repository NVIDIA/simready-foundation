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
Integration tests for AIF test fixtures.

Each non-compliant variant under fixtures/variants/ is designed to target
exactly one AIF requirement. NEGATIVE_FIXTURES maps each variant to that
requirement code; CLEAN_FIXTURES maps each compliant baseline to the
requirement set it must pass. See ./README.md for the human-readable
expectation matrix.

How the tests work:
  1. tests/conftest.py runs simready.validate's loader at session start.
     That populates RequirementsRegistry with every checker class registered
     under its spec code (AM.002 -> AIFAssetClassChecker, etc.).
  2. Each test calls assert_rule_fires / assert_no_failures with a code
     string (e.g., "AM.002"). The harness in tests/_harness.py resolves the
     code via RequirementsRegistry, uses ValidationEngine.enable_requirement
     to run only that rule, and asserts the expected outcome.

No local code-to-class mapping is maintained here. The framework's
RequirementsRegistry is the single source of truth.
"""
from pathlib import Path

import pytest

from .._harness import assert_no_failures, assert_rule_fires

# Convenience constants used by CLEAN_FIXTURES below.
# ALL_AIF is the full 16-requirement set; AIF_NON_TC_EL drops thermal-cooling
# and electrical (used by equipment classes that have no cooling or power
# subsystem of their own, e.g. Compute Racks).
ALL_AIF: list[str] = [
    "AM.001", "AM.002", "AM.003", "AM.004", "AM.005", "AM.006", "AM.007",
    "CP.001", "CP.004", "CP.005",
    "TC.001", "TC.002",
    "EL.001", "EL.002", "EL.003", "EL.004",
]
AIF_NON_TC_EL: list[str] = [c for c in ALL_AIF if not c.startswith(("TC.", "EL."))]

# Path-to-requirement-code map for the deliberately-broken variant fixtures.
# Each entry asserts: when this fixture is validated against ONLY the named
# requirement, that requirement must report at least one FAILURE. Paths are
# relative to FIXTURES_DIR. To add a new negative case, drop the .usda(s)
# into variants/ and add one line here.
NEGATIVE_FIXTURES: dict[str, str] = {
    "variants/am_fail_no_properties_sublayer.usda": "AM.001",
    "variants/am_fail_no_assetClass.usda":          "AM.002",
    "variants/am_fail_no_manufacturer.usda":        "AM.003",
    "variants/am_fail_no_dimensions.usda":          "AM.004",
    "variants/am_fail_no_simready_version.usda":    "AM.005",
    "variants/am_fail_no_description.usda":         "AM.006",
    "variants/am_fail_no_cooling_type.usda":        "AM.007",
    "variants/cp_fail_no_scope.usda":               "CP.001",
    "variants/cp_fail_no_default_prim.usda":        "CP.001",
    "variants/cp_fail_empty_scope.usda":            "CP.001",
    "variants/cp_fail_wrong_type_scope.usda":       "CP.001",
    "variants/cp_fail_bad_names.usda":              "CP.004",
    "variants/cp_fail_uppercase_names.usda":        "CP.004",
    "variants/cp_fail_no_sublayer.usda":            "CP.005",
    "variants/tc_fail_no_cooling_capacity.usda":    "TC.001",
    "variants/tc_fail_no_thermal_cps.usda":         "TC.002",
    "variants/el_fail_no_voltage.usda":             "EL.001",
    "variants/el_fail_no_power_rating.usda":        "EL.002",
    "variants/el_fail_no_frequency.usda":           "EL.003",
    "variants/el_fail_no_electrical_cps.usda":      "EL.004",
}

# Path-to-requirement-list map for compliant baseline fixtures.
# Each entry asserts: when this fixture is validated against the listed
# requirements, ZERO failures are reported. The list matters because some
# fixtures only satisfy a subset by design (see GB300 and cp_pass_complete).
CLEAN_FIXTURES: dict[str, list[str]] = {
    "Generic_CDU/asset/Generic_CDU.usda": ALL_AIF,
    # GB300 is a Compute Rack; TC and EL rules do not apply to AIF-Rack-Neutral.
    "gb300/asset/gb300.usda": AIF_NON_TC_EL,
    # Synthetic positive companion to the cp_fail_* variants. AM/TC/EL would
    # fail on this minimal stub because it has no equipment metadata.
    "variants/cp_pass_complete.usda": ["CP.001", "CP.004", "CP.005"],
}

# Root of the AIF fixture tree: tests/aif/fixtures/.
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# One parametrized case per entry in NEGATIVE_FIXTURES. `ids=` controls the
# pytest report names so failures show the fixture path, not "negative0".
@pytest.mark.parametrize(
    ("asset_rel", "target_code"),
    NEGATIVE_FIXTURES.items(),
    ids=list(NEGATIVE_FIXTURES.keys()),
)
def test_negative_fixture_triggers_targeted_rule(asset_rel: str, target_code: str) -> None:
    assert_rule_fires(FIXTURES_DIR / asset_rel, target_code)


# One parametrized case per entry in CLEAN_FIXTURES.
@pytest.mark.parametrize(
    ("asset_rel", "requirement_codes"),
    CLEAN_FIXTURES.items(),
    ids=list(CLEAN_FIXTURES.keys()),
)
def test_clean_baseline_has_no_failures(asset_rel: str, requirement_codes: list[str]) -> None:
    assert_no_failures(FIXTURES_DIR / asset_rel, requirement_codes)

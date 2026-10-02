# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""What the AIF-Entity profile resolves to, per version.

`test_aif.py` enables requirements directly on the engine, so it never reads
`profiles/aif_entity.toml` or any `features/FET_*.json`. Every defect in the
feature graph is invisible to it: a wrong requirement code, a wrong version pin,
a dependency edge pulling in a feature version the profile did not select.

That last one shipped. FET202 and FET203 at 0.1.0 depend on FET201@0.1.0, so
AIF-Entity 0.2.0 -- which selects FET201@0.2.0 directly -- resolved both
versions of Connection Points at once and re-enabled CP.004, the naming rule
v0.2.0 exists to retire. These cases are what would have caught it.
"""
import pytest

# What each AIF-Entity version must select, feature id to version. The core
# features come from tier_core; naming them here is what catches a tier_core
# rename or a missing dependency.
EXPECTED: dict[str, dict[str, str]] = {
    "0.1.0": {
        "FET_000_STANDARD": "0.1.0",
        "FET_001_STANDARD": "1.0.0",
        "FET200_AIF": "0.1.0",
        "FET201_AIF": "0.1.0",
        "FET202_AIF": "0.1.0",
        "FET203_AIF": "0.1.0",
    },
    # FET202 and FET203 move to 0.2.0 with FET201. At 0.1.0 they depend on
    # FET201@0.1.0, so selecting them here would resolve both Connection Points
    # versions at once and re-enable CP.004, which v0.2.0 exists to retire.
    "0.2.0": {
        "FET_000_STANDARD": "0.2.0",
        "FET_001_STANDARD": "1.0.0",
        "FET200_AIF": "0.1.0",
        "FET201_AIF": "0.2.0",
        "FET202_AIF": "0.2.0",
        "FET203_AIF": "0.2.0",
        "FET_031_STANDARD": "0.1.0",
        "FET_033_STANDARD": "0.4.0",
    },
}


@pytest.fixture(scope="module")
def profiles() -> dict:
    """Every profile the installed tiers register, through entry-point discovery.

    Empty path lists are what `simready-validate` passes when it is given no
    explicit --rules-path / --features-path / --profiles-path, so this resolves
    the same way the CLI does: from the installed wheels, not from the source
    tree.
    """
    simready_validate = pytest.importorskip(
        "simready.validate",
        reason="requires simready-validate to resolve profiles from entry points",
    )
    simready_validate.destroy()
    simready_validate.initialize(
        rules_and_requirements_paths=[], features_paths=[], profiles_paths=[]
    )
    yield simready_validate.get_available_profiles()
    simready_validate.destroy()


def _selected(profiles: dict, version: str) -> dict[str, str]:
    """Flatten one profile version's feature list to id -> version."""
    entries = profiles["AIF-Entity"][version]["features"]
    return {fid: spec["version"] for entry in entries for fid, spec in entry.items()}


def test_aif_entity_is_registered(profiles: dict) -> None:
    """The profile resolves at all.

    The loader drops a profile that names an unregistered feature and reports it
    only as a log line, so an asset validated against it reports nothing rather
    than failing. tier_core supplies FET_000_STANDARD and FET_001_STANDARD; this
    is what fails when that dependency is absent or too old.
    """
    assert "AIF-Entity" in profiles, (
        "AIF-Entity did not register. Either a feature it selects is unregistered "
        f"-- tier_core supplies two of them -- or the profile was skipped. "
        f"Registered: {sorted(profiles)}"
    )
    assert set(profiles["AIF-Entity"]) == set(EXPECTED)


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_profile_selects_expected_features(profiles: dict, version: str) -> None:
    """Each version selects exactly the features it names, at the right versions."""
    assert _selected(profiles, version) == EXPECTED[version]


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_no_feature_selected_at_two_versions(profiles: dict, version: str) -> None:
    """One feature id appears once. Two versions means two requirement sets."""
    entries = profiles["AIF-Entity"][version]["features"]
    seen: dict[str, set] = {}
    for entry in entries:
        for fid, spec in entry.items():
            seen.setdefault(fid, set()).add(spec["version"])
    duplicated = {fid: sorted(v) for fid, v in seen.items() if len(v) > 1}
    assert not duplicated, (
        f"AIF-Entity {version} selects these at more than one version: {duplicated}."
    )

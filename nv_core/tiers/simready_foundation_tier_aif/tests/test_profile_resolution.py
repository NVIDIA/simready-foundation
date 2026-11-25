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
"""What the AIF-Entity profile resolves to, per version.

`test_aif.py` enables requirements directly on the engine, so it never reads
`profiles/aif_entity.toml` or the feature/capability catalogs. Every defect in
the contract graph is invisible to it: a wrong requirement code, a wrong version
pin, a dependency edge pulling in a version the profile did not select.

That last one shipped in the legacy graph: FET202 and FET203 at 0.1.0 pulled
FET201@0.1.0 into AIF-Entity 0.2.0 and re-enabled CP.004, the naming rule
v0.2.0 exists to retire. Foundations 2 preserves those static contracts as CAPs.
Check both the public selector snapshot and the registry's expanded membership:
the snapshot alone cannot reveal a dependency that reintroduces an old CAP.
"""

from importlib.metadata import entry_points

import pytest
from simready.foundation.contracts import (
    CapabilityId,
    FeatureId,
    ResolvedProfile,
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
)
from usd_validation_nvidia import Profile, ProfileRegistry

# Published dotted identities contain the contract version. The registry's
# internal Capability.version is 0.0.0 for Foundations 2 and is not that version.
# Keep feature and capability selections distinct; static AIF contracts are CAPs.
EXPECTED: dict[str, dict[str, tuple[str, ...]]] = {
    "0.1.0": {
        "features": ("FET001_MinimalPlaceableVisual.1-0-0",),
        "capabilities": (
            "CAP000_Core.0-1-0",
            "CAP200_AifMetadata.0-1-0",
            "CAP201_ConnectionPoints.0-1-0",
            "CAP202_ThermalCooling.0-1-0",
            "CAP203_Electrical.0-1-0",
        ),
    },
    # Thermal Cooling and Electrical move with Connection Points. Their 0.1.0
    # dependencies would otherwise reintroduce the retired CP.004 naming rule.
    "0.2.0": {
        "features": ("FET001_MinimalPlaceableVisual.1-0-0",),
        "capabilities": (
            "CAP000_Core.0-2-0",
            "CAP200_AifMetadata.0-1-0",
            "CAP201_ConnectionPoints.0-2-0",
            "CAP202_ThermalCooling.0-2-0",
            "CAP203_Electrical.0-2-0",
            "CAP031_SelfContainedPackage.0-1-0",
            "CAP033_SimReadyPackage.0-4-0",
        ),
    },
}

EXPECTED_CONNECTION_REQUIREMENTS = {
    "0.1.0": {"CP.001", "CP.004", "CP.005"},
    "0.2.0": {"CP.001", "CP.005", "CP.010", "CP.011", "CP.012"},
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
    simready_validate.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield simready_validate.get_available_profiles()
    simready_validate.destroy()


@pytest.fixture(scope="module")
def resolved_profiles(profiles: dict) -> dict[str, Profile]:
    """Read dependency-expanded membership through the public registry API."""
    registry = ProfileRegistry()
    resolved = {}
    for version in EXPECTED:
        profile = registry.find("AIF-Entity", version)
        assert profile is not None, f"AIF-Entity {version} did not register"
        resolved[version] = profile
    return resolved


def test_aif_entity_is_registered(profiles: dict) -> None:
    """The profile resolves at all.

    The loader drops a profile that names an unregistered feature and reports it
    only as a log line, so an asset validated against it reports nothing rather
    than failing. tier_core supplies the Core/packaging CAPs and the minimal
    visual FET; this is what fails when that dependency is absent or too old.
    """
    assert "AIF-Entity" in profiles, (
        "AIF-Entity did not register. Either a feature it selects is unregistered "
        "or capability is missing from tier_core, or the profile was skipped. "
        f"Registered: {sorted(profiles)}"
    )
    assert set(profiles["AIF-Entity"]) == set(EXPECTED) | {"0.3.0"}


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_profile_keeps_exact_selectors(profiles: dict, version: str) -> None:
    """The public snapshot retains exact required FET and CAP selectors."""
    expected = {
        kind: [{"selector": identity} for identity in identities] for kind, identities in EXPECTED[version].items()
    }
    assert profiles["AIF-Entity"][version] == expected


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_profile_resolves_expected_contracts(resolved_profiles: dict[str, Profile], version: str) -> None:
    """Dependencies neither add an old contract nor weaken required selections."""
    profile = resolved_profiles[version]
    expected = sorted(identity for identities in EXPECTED[version].values() for identity in identities)
    assert sorted(contract.id for contract in profile.capabilities) == expected
    assert not profile.optional_capabilities
    assert profile.mandatory_requirements == {
        requirement.code for contract in profile.capabilities for requirement in contract.requirements
    }


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_no_contract_selected_at_two_versions(resolved_profiles: dict[str, Profile], version: str) -> None:
    """One dotted FET/CAP family/runtime resolves to one requirement version."""
    seen: dict[str, set[str]] = {}
    for contract in resolved_profiles[version].capabilities:
        family, contract_version = contract.id.rsplit(".", 1)
        seen.setdefault(family, set()).add(contract_version)
    duplicated = {fid: sorted(v) for fid, v in seen.items() if len(v) > 1}
    assert not duplicated, f"AIF-Entity {version} selects these at more than one version: {duplicated}."


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_profile_requires_its_connection_point_vocabulary(resolved_profiles: dict[str, Profile], version: str) -> None:
    """CP.004 remains required in 0.1.0 and is not revived in 0.2.0."""
    prefix = "com.nvidia.simready."
    required = resolved_profiles[version].mandatory_requirements
    assert {code for code in required if code.startswith(prefix + "CP.")} == {
        prefix + code for code in EXPECTED_CONNECTION_REQUIREMENTS[version]
    }


@pytest.fixture(scope="module")
def catalog_profiles() -> dict[str, ResolvedProfile]:
    """Preserve the independent Foundation catalog resolver checks from !614."""
    tiers = [entry_point.load() for entry_point in entry_points(group="simready.tier")]
    features = load_feature_definitions([tier.feature_contracts_path for tier in tiers])
    capabilities = load_capability_definitions([tier.capability_contracts_path for tier in tiers])
    definitions = load_profile_definitions([tier.profile_contracts_path for tier in tiers])
    return {
        version: resolve_profile(profile, features, capabilities)
        for (name, version), profile in definitions.items()
        if name == "AIF-Entity"
    }


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_catalog_resolves_expected_contracts(catalog_profiles: dict[str, ResolvedProfile], version: str) -> None:
    """Check catalog expansion independently of Validate's registry projection."""
    profile = catalog_profiles[version]
    actual = {contract.id for contract in (*profile.features, *profile.capabilities)}
    expected = {identity for identities in EXPECTED[version].values() for identity in identities}
    assert actual == expected


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_catalog_has_one_version_per_contract_family(
    catalog_profiles: dict[str, ResolvedProfile], version: str
) -> None:
    """Keep !614's typed family/runtime invariant independent of the registry."""
    profile = catalog_profiles[version]
    seen: dict[tuple[str, str], set[str]] = {}
    for contract in (*profile.features, *profile.capabilities):
        parsed = FeatureId.parse(contract.id) if contract.id.startswith("FET") else CapabilityId.parse(contract.id)
        seen.setdefault((parsed.family, parsed.runtime), set()).add(parsed.version)
    duplicated = {
        f"{family}.{runtime}": sorted(versions) for (family, runtime), versions in seen.items() if len(versions) > 1
    }
    assert not duplicated, f"AIF-Entity {version} resolves these at more than one version: {duplicated}."


def test_aif03_inherits_mandatory_contracts(profiles: dict, catalog_profiles: dict[str, ResolvedProfile]) -> None:
    base = ProfileRegistry().find("AIF-Entity", "0.2.0")
    current = ProfileRegistry().find("AIF-Entity", "0.3.0")
    replaced = {"com.nvidia.simready.AM.004", "com.nvidia.simready.AM.007"}
    replacements = {"com.nvidia.simready.AM.008", "com.nvidia.simready.AM.009"}
    assert current.mandatory_requirements == (base.mandatory_requirements - replaced) | replacements
    expected = {
        "FET001_MinimalPlaceableVisual.1-0-0",
        "CAP000_Core.0-2-0",
        "CAP031_SelfContainedPackage.0-1-0",
        "CAP033_SimReadyPackage.0-4-0",
        "CAP200_AifMetadata.0-3-0",
        "CAP201_ConnectionPoints.0-3-0",
        "CAP202_ThermalCooling.0-3-0",
        "CAP203_Electrical.0-3-0",
    }
    assert {c.id for c in current.capabilities} - current.optional_capabilities == expected
    catalog = catalog_profiles["0.3.0"]
    assert {c.id for c in (*catalog.features, *catalog.capabilities) if not c.optional} == expected

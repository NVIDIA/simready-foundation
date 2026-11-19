# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The optimization profile exposes independent static capabilities."""

from __future__ import annotations

import json
import subprocess
import sys
import pytest
from importlib.metadata import distribution, entry_points
from pathlib import Path

from simready.foundation.contracts import (
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "simready/foundation/tier_isaac"
CONTRACTS = {
    "CAP102_RigidBodyCollapse.Isaac.0-1-0": "OPT.001",
    "CAP103_VisualMeshMerge.Isaac.0-1-0": "OPT.002",
    "CAP104_RenderCollisionSeparation.Isaac.0-1-0": "OPT.003",
    "CAP105_MaterialXRemoval.Isaac.0-1-0": "OPT.004",
}


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"])
def test_optimization_profile_resolves_against_the_complete_tier_catalog(version):
    roots = [
        descriptor.parent
        for descriptor in sorted(PROJECT_ROOT.parent.glob("*/simready/foundation/*/_tier.py"))
    ]
    features = load_feature_definitions(root / "features" for root in roots)
    capabilities = load_capability_definitions(root / "capabilities" for root in roots)
    profiles = load_profile_definitions([PACKAGE_ROOT / "profiles"])
    assert set(profiles) == {("Asset-Optimization", "1.0.0"), ("Asset-Optimization", "1.1.0")}
    resolved = resolve_profile(profiles[("Asset-Optimization", version)], features, capabilities)
    contracts = {key: value for key, value in CONTRACTS.items()
                 if version == "1.1.0" or value != "OPT.004"}

    assert not resolved.features
    assert [item.id for item in resolved.capabilities] == sorted(contracts)
    assert all(not item.optional for item in resolved.capabilities)
    assert {
        requirement
        for item in resolved.capabilities
        for requirement in capabilities[item.id].requirements
    } == set(contracts.values())

    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import feature_adapters

    for adapter in feature_adapters():
        assert adapter.input_feature in features
        assert adapter.output_feature in capabilities


def test_capabilities_are_independent_new_contracts():
    capabilities = load_capability_definitions([PACKAGE_ROOT / "capabilities"])
    assert set(capabilities) == set(CONTRACTS)
    for contract_id, requirement in CONTRACTS.items():
        manifest = json.loads((PACKAGE_ROOT / "capabilities" / f"{contract_id}.json").read_text())
        assert "legacy_identity" not in manifest
        definition = capabilities[contract_id]
        assert definition.requirements == (requirement,)
        assert not definition.dependencies
        assert not definition.features


def test_tier_descriptor_does_not_import_usd_or_validators():
    # Entry-point resolution must work before USD or validation startup. Blocking
    # both imports proves this in a fresh interpreter, regardless of test order.
    script = """
import importlib.abc
import sys

class DependencyGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pxr' or fullname == 'usd_validation_nvidia':
            raise AssertionError('descriptor imported ' + fullname)

sys.meta_path.insert(0, DependencyGuard())
sys.path.insert(0, sys.argv[1])
from simready.foundation.tier_isaac import tier
assert tier.rules_package.endswith('.rules_and_reqs')
assert tier.rules_and_requirements_path.is_dir()
assert tier.capability_contracts_path.is_dir()
assert tier.profile_contracts_path.is_dir()
assert tier.runtime_tests_path is None
"""
    subprocess.run(
        [sys.executable, "-c", script, str(PROJECT_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_installed_tier_bundles_its_conform_skills():
    tier_entry_points = [point for point in entry_points(group="simready.tier") if point.name == "tier_isaac"]
    assert len(tier_entry_points) == 1
    tier = tier_entry_points[0].load()
    installed_files = {str(path) for path in distribution("simready-foundation-tier-isaac").files}

    for number in (102, 103, 104, 105):
        relative = f"simready-foundation-conform-cap-{number}-isaac/SKILL.md"
        assert (tier.skills_path / relative).is_file()
        assert f"simready/foundation/tier_isaac/skills/{relative}" in installed_files

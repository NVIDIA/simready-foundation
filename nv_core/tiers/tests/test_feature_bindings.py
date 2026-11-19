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

"""Every contract in every tier names runtime tests and requirements that exist.

The contract loader already rejects a FET without ``runtime_tests`` unless it is
a source FET that a tested FET derives from. It does not check that a bound test
exists, or that a listed requirement has a validator: the catalogs are generated
from the suites and validators as they were at generation time, and a test or
validator removed or renamed since then leaves a binding that resolves to
nothing. Evaluate then plans no test for the feature, and validation skips the
contract over its unregistered requirement, reporting it only in a log line.
"""

from __future__ import annotations

import ast
import importlib
import json
from importlib.metadata import entry_points
from pathlib import Path

import pytest
import usd_validation_nvidia
from build_tiers import discover_tiers
from migrate_foundations2_catalog import _runtime_provider_metadata
from simready.foundation.contracts import (
    load_capability_definitions,
    load_feature_definitions,
)

_TIERS_ROOT = Path(__file__).resolve().parents[1]

# simready.validate resolves a requirement code without a namespace under this one.
_REQUIREMENT_NAMESPACE = "com.nvidia.simready"


@pytest.fixture(scope="module")
def tiers() -> list:
    return sorted(
        (entry_point.load() for entry_point in entry_points(group="simready.tier")),
        key=lambda tier: tier.name,
    )


def _registered_runtime_tests(suite: Path) -> set[str]:
    """``<provider>:<name>`` of every ``@test`` in an Evaluate test package.

    Read from the source rather than through Evaluate's discovery, which imports
    each test file and skips those that need Kit, so their tests would look
    missing here. Like discovery, this skips files whose name starts with ``_``.
    Reuse catalog ownership rules so canonical and transitional descriptors agree.
    """
    metadata = _runtime_provider_metadata(suite)
    provider = metadata["provider"] if metadata is not None else suite.name
    registered = set()
    for path in suite.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and getattr(decorator.func, "id", None) == "test"):
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        registered.add(f"{provider}:{keyword.value.value}")
    return registered


@pytest.fixture
def runtime_suite(tmp_path: Path) -> Path:
    suite = tmp_path / "runtime_suite"
    suite.mkdir()
    (suite / "__init__.py").write_text('raise RuntimeError("Do not import the test provider")\n', encoding="utf-8")
    (suite / "probe.py").write_text(
        'raise RuntimeError("Kit-only test files must be scanned without import")\n'
        '@test(name="probe")\nasync def probe(ctx): pass\n',
        encoding="utf-8",
    )
    return suite


@pytest.mark.parametrize(
    "descriptors",
    [
        ("benchmark-provider.json",),
        ("evaluate-provider.json",),
        ("benchmark-provider.json", "evaluate-provider.json"),
    ],
)
def test_runtime_binding_scanner_uses_declared_provider(runtime_suite: Path, descriptors: tuple[str, ...]) -> None:
    metadata = {"provider": "declared.provider", "import_package": "runtime_suite"}
    for filename in descriptors:
        (runtime_suite / filename).write_text(json.dumps(metadata), encoding="utf-8")
    assert _registered_runtime_tests(runtime_suite) == {"declared.provider:probe"}


def test_runtime_binding_scanner_preserves_descriptorless_provider(runtime_suite: Path) -> None:
    assert _registered_runtime_tests(runtime_suite) == {"runtime_suite:probe"}


def test_runtime_binding_scanner_rejects_conflicting_descriptors(runtime_suite: Path) -> None:
    for filename, provider in [
        ("benchmark-provider.json", "canonical.provider"),
        ("evaluate-provider.json", "conflicting.provider"),
    ]:
        (runtime_suite / filename).write_text(
            json.dumps({"provider": provider, "import_package": "runtime_suite"}), encoding="utf-8"
        )
    with pytest.raises(ValueError, match="Conflicting runtime suite ownership"):
        _registered_runtime_tests(runtime_suite)


def test_runtime_binding_scanner_does_not_hide_invalid_canonical_descriptor(runtime_suite: Path) -> None:
    (runtime_suite / "benchmark-provider.json").write_text("not JSON", encoding="utf-8")
    (runtime_suite / "evaluate-provider.json").write_text(
        json.dumps({"provider": "declared.provider", "import_package": "runtime_suite"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Invalid runtime suite ownership"):
        _registered_runtime_tests(runtime_suite)


def test_every_tier_is_installed(tiers: list) -> None:
    """The other tests only see the tiers requirements.txt installs."""
    in_checkout = {
        descriptor.parent.name
        for tier_dir in discover_tiers(str(_TIERS_ROOT))
        for descriptor in Path(tier_dir).glob("simready/foundation/*/_tier.py")
    }
    assert {tier.name for tier in tiers} == in_checkout


def test_every_runtime_test_binding_names_a_registered_test(tiers: list) -> None:
    features = load_feature_definitions([tier.feature_contracts_path for tier in tiers])
    registered = set()
    for tier in tiers:
        if tier.runtime_tests_path is not None:
            registered |= _registered_runtime_tests(tier.runtime_tests_path)

    unbound = {
        feature_id: missing
        for feature_id, feature in sorted(features.items())
        if (missing := sorted(set(feature.runtime_tests) - registered))
    }
    assert not unbound, f"Features bound to runtime tests no tier registers: {unbound}"


def test_every_contract_requirement_has_a_validator(tiers: list) -> None:
    for tier in tiers:
        importlib.import_module(tier.rules_package)
    registry = usd_validation_nvidia.RequirementsRegistry()

    features = load_feature_definitions([tier.feature_contracts_path for tier in tiers])
    capabilities = load_capability_definitions([tier.capability_contracts_path for tier in tiers])
    contracts = {
        **{contract_id: feature.all_requirements for contract_id, feature in features.items()},
        **{contract_id: capability.requirements for contract_id, capability in capabilities.items()},
    }

    unregistered: dict[str, list[str]] = {}
    unimplemented: dict[str, list[str]] = {}
    for contract_id, codes in sorted(contracts.items()):
        for code in codes:
            requirement = registry.find_requirement(code) or registry.find_requirement(
                f"{_REQUIREMENT_NAMESPACE}.{code}"
            )
            if requirement is None:
                unregistered.setdefault(code, []).append(contract_id)
            elif registry.get_validator(requirement) is None:
                unimplemented.setdefault(code, []).append(contract_id)

    assert not unregistered, f"Contracts list requirements no tier registers: {unregistered}"
    assert not unimplemented, f"Contracts list requirements with no validator: {unimplemented}"

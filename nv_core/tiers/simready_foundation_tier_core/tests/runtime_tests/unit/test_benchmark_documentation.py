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
"""Keep the shipped Evaluate reference aligned with enabled registrations."""

import ast
import json
import re
from pathlib import Path

#: A dotted ``FET<family>_<Name>[.<Runtime>].<version>`` ID; ``%s`` is the family pattern.
_CONTRACT_ID = r"FET%s_[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)?\.\d+(?:-\d+)*"


def _foundation_root():
    # type: () -> Path
    for parent in Path(__file__).resolve().parents:
        if (parent / "nv_core" / "sr_specs" / "docs").is_dir():
            return parent
    raise AssertionError("could not locate the SimReady Foundation root")


def _static_dict(node):
    """Return the statically-resolvable entries of a ``{...}`` or ``dict(...)`` node.

    Non-literal entries (for example ``config_defaults=phase.get_defaults()``)
    are skipped rather than rejecting the whole dict, so literal metadata such
    as ``version`` and ``enabled`` still resolves for the ``**KWARGS`` spread.
    """
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                continue
            try:
                result[ast.literal_eval(key)] = ast.literal_eval(value)
            except Exception:
                continue
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
        result = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            try:
                result[keyword.arg] = ast.literal_eval(keyword.value)
            except Exception:
                continue
        return result
    return None


def _module_dict_constants(tree):
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = _static_dict(node.value)
        if value is not None:
            constants[target.id] = value
    return constants


def _test_registration(call, constants):
    """Effective @test(...) keyword args, expanding a module-level ``**KWARGS`` dict.

    Engine-parametrized tests split across tiers keep the shared decorator
    metadata (version, enabled, config_defaults, ...) in a module-level
    ``dict`` constant that both the Core and Newton copies spread via
    ``**KWARGS`` while declaring their own ``features`` and ``name``.  This
    resolves that spread so the static reference stays introspectable.
    """
    kwargs = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            if isinstance(keyword.value, ast.Name):
                kwargs.update(constants.get(keyword.value.id, {}))
            continue
        try:
            kwargs[keyword.arg] = ast.literal_eval(keyword.value)
        except Exception:
            continue
    return kwargs


def _registered_tests():
    root = _foundation_root()
    source_root = (
        root / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready/foundation/tier_core/runtime_tests"
    )
    registrations = {}
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        constants = _module_dict_constants(tree)
        for node in ast.walk(tree):
            for decorator in getattr(node, "decorator_list", []):
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Name):
                    continue
                if decorator.func.id != "test":
                    continue
                kwargs = _test_registration(decorator, constants)
                name = kwargs.get("name")
                assert name, "@test registration without a literal name in %s" % source_path
                assert name not in registrations, "duplicate @test name %r in %s and %s" % (
                    name,
                    registrations.get(name, {}).get("source"),
                    source_path,
                )
                feature_specs = kwargs.get("features", [])
                feature_ids = tuple(feature["id"] for feature in feature_specs)
                families = set()
                for feature_id in feature_ids:
                    match = re.fullmatch(_CONTRACT_ID % r"(\d{3})", feature_id)
                    assert match, "%s: non-canonical feature ID %r" % (source_path, feature_id)
                    families.add("FET%s" % match.group(1))
                # A test may serve features of several families; one run gives each of them a
                # verdict. Its documentation lives with the family package that holds it, and
                # that family has to be one the test serves.
                package = re.fullmatch(r"fet(\d{3})_\w+", source_path.relative_to(source_root).parts[0])
                assert package, f"{source_path}: runtime tests must live in a fet###_<topic> package"
                family = f"FET{package.group(1)}"
                assert family in families, f"{source_path}: serves {sorted(families)} but lives in the {family} package"
                registrations[name] = {
                    "enabled": kwargs.get("enabled", True),
                    "features": feature_ids,
                    "family": family,
                    "source": source_path,
                    "version": kwargs.get("version"),
                }
    return registrations


def _documented_tests():
    root = _foundation_root()
    docs_root = (
        root
        / "nv_core"
        / "tiers"
        / "simready_foundation_tier_core"
        / "simready/foundation/tier_core/runtime_tests"
        / "docs"
    )
    documented = {}
    row_pattern = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$", re.MULTILINE)
    required_headings = ("Summary", "What Pass Guarantees", "What It Checks")
    required_heading_groups = (
        ("How It Works", "Execution Model"),
        ("How to Fix", "Common Failure Modes"),
        ("Expected Result", "Evidence"),
    )
    for doc_path in docs_root.glob("fet[0-9][0-9][0-9]/*.md"):
        text = doc_path.read_text(encoding="utf-8")
        properties = {key.strip(): value.strip() for key, value in row_pattern.findall(text)}
        names = []
        if properties.get("Test name"):
            names = [properties["Test name"]]
        elif properties.get("Test names"):
            names = re.findall(r"`([^`]+)`", properties["Test names"])
        if not names:
            continue
        headings = set(re.findall(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
        for heading in required_headings:
            assert heading in headings, "%s: missing required section %r" % (doc_path, heading)
        for alternatives in required_heading_groups:
            assert headings.intersection(alternatives), "%s: expected one of sections %r" % (doc_path, alternatives)
        features = properties.get("Feature(s)")
        version = properties.get("Test version")
        assert features is not None, "%s: missing 'Feature(s)' property" % doc_path
        assert version is not None, "%s: missing 'Test version' property" % doc_path
        versions_by_name = dict(re.findall(r"`([a-z0-9_]+)`\s+(\d+\.\d+\.\d+)", version))
        if versions_by_name:
            assert set(versions_by_name) == set(
                names
            ), f"{doc_path}: per-test versions must cover exactly the documented names"
        feature_ids = tuple(re.findall(_CONTRACT_ID % r"\d{3}", features))
        assert feature_ids, "%s: no feature IDs in 'Feature(s)' property" % doc_path
        family_match = re.fullmatch(r"fet(\d{3})", doc_path.parent.name)
        assert family_match, "%s: per-test docs must live in docs/fet###/" % doc_path
        family = "FET%s" % family_match.group(1)
        for name in names:
            assert name not in documented, "test %r documented more than once: %s and %s" % (
                name,
                documented.get(name, {}).get("source"),
                doc_path,
            )
            documented[name] = {
                "features": feature_ids,
                "family": family,
                "source": doc_path,
                "version": versions_by_name.get(name, version),
            }
    return documented


def _family_documents():
    root = _foundation_root()
    docs_root = (
        root
        / "nv_core"
        / "tiers"
        / "simready_foundation_tier_core"
        / "simready/foundation/tier_core/runtime_tests"
        / "docs"
    )
    families = {}
    required_headings = ("Overview", "What a Passing Family Means", "Tests", "Relationship to the Feature")
    for doc_path in docs_root.glob("fet[0-9][0-9][0-9]-*.md"):
        match = re.match(r"^fet(\d{3})-", doc_path.name)
        assert match
        family = "FET%s" % match.group(1)
        assert family not in families, "family %s documented more than once: %s and %s" % (
            family,
            families.get(family, {}).get("source"),
            doc_path,
        )
        text = doc_path.read_text(encoding="utf-8")
        headings = set(re.findall(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
        for heading in required_headings:
            assert heading in headings, "%s: missing required section %r" % (doc_path, heading)
        linked_tests = re.findall(
            r"^\* - \[([a-z0-9_]+)\]\(fet\d{3}/[^)]+\.md\)",
            text,
            re.MULTILINE,
        )
        assert len(linked_tests) == len(set(linked_tests)), "%s: duplicate test link" % doc_path
        families[family] = {"source": doc_path, "tests": set(linked_tests)}
    return families


def _visible_family_index():
    root = _foundation_root()
    index_path = (
        root
        / "nv_core"
        / "tiers"
        / "simready_foundation_tier_core"
        / "simready/foundation/tier_core/runtime_tests"
        / "docs"
        / "tests.md"
    )
    text = index_path.read_text(encoding="utf-8").split("```{toctree}", 1)[0]
    entries = {}
    for number, target in re.findall(r"\[FET(\d{3})[^]]*\]\((fet\d{3}-[^)]+\.md)\)", text):
        family = "FET%s" % number
        assert family not in entries, "%s: duplicate visible family entry %s" % (index_path, family)
        entries[family] = target
    return entries


def test_enabled_registrations_match_benchmark_reference():
    registrations = _registered_tests()
    documented = _documented_tests()
    enabled = {name: data for name, data in registrations.items() if data["enabled"]}

    assert set(documented) == set(enabled)
    for name, registration in enabled.items():
        assert documented[name]["version"] == registration["version"], name
        assert tuple(sorted(documented[name]["features"])) == tuple(sorted(registration["features"])), name
        assert documented[name]["family"] == registration["family"], name


def test_family_reference_and_visible_index_cover_enabled_registrations():
    registrations = _registered_tests()
    enabled = {name: data for name, data in registrations.items() if data["enabled"]}
    enabled_families = {data["family"] for data in enabled.values()}
    families = _family_documents()
    visible = _visible_family_index()

    assert set(families) == enabled_families
    assert set(visible) == enabled_families
    for family, data in families.items():
        assert visible[family] == data["source"].name
        family_tests = {name for name, registration in enabled.items() if registration["family"] == family}
        assert data["tests"] == family_tests, (
            "%s: family test links do not match enabled registrations" % data["source"]
        )


def test_disabled_registrations_are_not_documented_as_shipped_tests():
    registrations = _registered_tests()
    documented = _documented_tests()
    disabled = {name for name, data in registrations.items() if not data["enabled"]}

    assert disabled.isdisjoint(documented)


def test_authoring_registration_examples_match_public_api_and_manifest_binding():
    from packaging.specifiers import SpecifierSet
    from simready.evaluate import test as register_test

    root = _foundation_root()
    tier_root = root / "nv_core" / "tiers" / "simready_foundation_tier_core"
    suite = tier_root / "simready/foundation/tier_core/runtime_tests"
    guide = (suite / "docs" / "authoring.md").read_text(encoding="utf-8")
    manifest = json.loads(
        (
            tier_root / "simready" / "foundation" / "tier_core" / "features" / "FET004_Multibody.PhysX.0-4-0.json"
        ).read_text(encoding="utf-8")
    )
    provider = json.loads((suite / "benchmark-provider.json").read_text(encoding="utf-8"))["provider"]
    examples = [
        code
        for code in re.findall(r"```python\n(.*?)\n```", guide, re.DOTALL)
        if code.startswith("@test(") and 'name="joint_movement"' in code
    ]
    assert len(examples) == 2

    async def documented_test(ctx):
        pass

    for example in examples:
        tree = ast.parse(example + "\nasync def documented_test(ctx):\n    pass\n")
        metadata = _test_registration(tree.body[0].decorator_list[0], {})
        # Execute the documented metadata against the public decorator without
        # registering or launching a runtime test.
        assert (
            register_test(
                **metadata,
                description="Documentation metadata qualification.",
                expected_video="No engine is launched by this unit check.",
                version="1.0.0",
                enabled=False,
            )(documented_test)
            is documented_test
        )
        feature = metadata["features"][0]
        if feature["id"] == manifest["id"]:
            assert feature["version"] == "*"
            assert feature["id"] in _registered_tests()[metadata["name"]]["features"]
            assert f"{provider}:{metadata['name']}" in manifest["runtime_tests"]
        else:
            assert feature["id"] == manifest["legacy_identity"]["id"]
            assert SpecifierSet(feature["version"]).contains(manifest["legacy_identity"]["version"])


def test_running_guide_isaac_toml_examples_discover_independent_runtimes(tmp_path):
    from simready.evaluate_engine_kit.plugin import KitPlugin

    guide = (_foundation_root() / "nv_core" / "sr_specs" / "docs" / "guides" / "evaluate" / "running.md").read_text(
        encoding="utf-8"
    )
    examples = [code for code in re.findall(r"```toml\n(.*?)\n```", guide, re.DOTALL) if "[kit.isaac_sim]" in code]
    assert len(examples) == 2
    for index, example in enumerate(examples):
        config_path = tmp_path / f"engines-{index}.toml"
        config_path.write_text(example, encoding="utf-8")
        engines = {item.name: item for item in KitPlugin()._discover_from_engines_toml(str(config_path))}
        assert set(engines) == {"isaac_sim", "isaac_sim_newton"}
        assert engines["isaac_sim"].runtime == "PhysX"
        assert engines["isaac_sim_newton"].runtime == "Newton"
        assert engines["isaac_sim_newton"].experience == "isaacsim.exp.full.newton"
        assert all(set(engine.tags) == {"isaac", "kit"} for engine in engines.values())
        if index == 0:
            # Separate pip Isaac owns its launcher and Python; host Python
            # must not silently be substituted for the configured environment.
            for engine in engines.values():
                assert engine.python_executable
                assert Path(engine.python_executable).parent == Path(engine.executable_path).parent


def test_runtime_authoring_skill_routes_to_existing_owned_suite_guides():
    root = _foundation_root()
    tiers_root = root / "nv_core" / "tiers"
    skill_path = root / "skills" / "simready-foundation-add-runtime-test" / "SKILL.md"
    expected_guides = {
        tiers_root / tier / suite / "docs" / guide
        for tier, suite, guide in (
            ("simready_foundation_tier_core", "simready/foundation/tier_core/runtime_tests", "authoring.md"),
            ("simready_foundation_tier_newton", "simready/foundation/tier_newton/runtime_tests", "runtime-tests.md"),
            ("simready_foundation_tier_sensors", "simready/foundation/sensors/runtime_tests", "tests.md"),
        )
    }
    links = re.findall(r"\[[^\]]+\]\(([^)]+\.md)\)", skill_path.read_text(encoding="utf-8"))
    resolved_links = {(skill_path.parent / link).resolve() for link in links}
    routed_guides = {path for path in resolved_links if path.is_relative_to(tiers_root)}
    assert routed_guides == expected_guides
    for guide in sorted(routed_guides):
        assert guide.is_file(), f"runtime authoring guide does not exist: {guide}"
        suite = guide.parent.parent
        provider = json.loads((suite / "benchmark-provider.json").read_text(encoding="utf-8"))["provider"]
        assert provider in guide.read_text(encoding="utf-8"), f"guide must describe its owning provider: {guide}"

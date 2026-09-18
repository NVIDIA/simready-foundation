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
"""Keep the shipped Benchmark reference aligned with enabled registrations."""

import ast
import re
from pathlib import Path


def _foundation_root():
    # type: () -> Path
    for parent in Path(__file__).resolve().parents:
        if (parent / "nv_core" / "sr_specs" / "docs").is_dir():
            return parent
    raise AssertionError("could not locate the SimReady Foundation root")


def _literal_keyword(call, name, default=None):
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.literal_eval(keyword.value)
    return default


def _registered_tests():
    root = _foundation_root()
    source_root = root / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready_benchmark_kit_suite"
    registrations = {}
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            for decorator in getattr(node, "decorator_list", []):
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Name):
                    continue
                if decorator.func.id != "test":
                    continue
                name = _literal_keyword(decorator, "name")
                assert name, "@test registration without a literal name in %s" % source_path
                assert name not in registrations, "duplicate @test name %r in %s and %s" % (
                    name,
                    registrations.get(name, {}).get("source"),
                    source_path,
                )
                feature_specs = _literal_keyword(decorator, "features", [])
                feature_ids = tuple(feature["id"] for feature in feature_specs)
                families = set()
                for feature_id in feature_ids:
                    match = re.match(r"^FET_(\d{3})_", feature_id)
                    assert match, "%s: non-canonical feature ID %r" % (source_path, feature_id)
                    families.add("FET%s" % match.group(1))
                assert len(families) == 1, "%s: one test must not span FET families %r" % (source_path, families)
                registrations[name] = {
                    "enabled": _literal_keyword(decorator, "enabled", True),
                    "features": feature_ids,
                    "family": families.pop(),
                    "source": source_path,
                    "version": _literal_keyword(decorator, "version"),
                }
    return registrations


def _documented_tests():
    root = _foundation_root()
    docs_root = root / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready_benchmark_kit_suite" / "docs"
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
        feature_ids = tuple(re.findall(r"FET_\d{3}_[A-Z0-9_]+", features))
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
                "version": version,
            }
    return documented


def _family_documents():
    root = _foundation_root()
    docs_root = root / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready_benchmark_kit_suite" / "docs"
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
        / "simready_benchmark_kit_suite"
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

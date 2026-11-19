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

"""Relocation planning for the Foundations 2 catalog transformer.

These cover the planning and refusal logic rather than the projection itself:
the relocation deletes the published Foundations 1 tree, so its safety checks
are the part that must not regress.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING_ROOT))

import migrate_foundations2_catalog as migrate  # noqa: E402


def _tier(tmp_path: Path, contracts: list[dict], *, feature_pages: list[str]) -> Path:
    """Build a package root with a staged catalog and Foundations 1 pages."""
    package_root = tmp_path / "simready_foundation_tier_x" / "simready" / "foundation" / "tier_x"
    staging = package_root / migrate.STAGING_DIRNAME
    for section in ("features", "capabilities", "profiles"):
        (staging / section).mkdir(parents=True, exist_ok=True)
    (package_root / "features").mkdir(parents=True, exist_ok=True)
    (package_root / "profiles").mkdir(parents=True, exist_ok=True)

    (staging / "catalog-map.json").write_text(json.dumps({"schema": "test", "contracts": contracts}), encoding="utf-8")
    for contract in contracts:
        section = "features" if contract["kind"] == "feature" else "capabilities"
        (staging / section / f"{contract['id']}.json").write_text("{}", encoding="utf-8")
    for name in feature_pages:
        (package_root / "features" / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
    return package_root


def _contract(legacy_id: str, new_id: str, kind: str, *, page: str | None = None) -> dict:
    contract = {"legacy_id": legacy_id, "legacy_version": "0.1.0", "kind": kind, "id": new_id}
    if page is not None:
        contract["legacy_page"] = page
    return contract


def test_unnamed_family_is_refused_rather_than_given_a_placeholder():
    """An unnamed family must stop the projection, not invent a name.

    A placeholder becomes a permanent contract ID and a permanent filename, and
    nothing downstream flags it -- so the generator has to insist that whoever
    publishes a new family also names it.
    """
    manifest = {"id": "FET_010_STANDARD", "version": "0.1.0", "display_name": "Display Color"}
    assert "010" in migrate.FAMILY_NAMES, "fixture assumes 010 is named; pick an unnamed family"

    with pytest.raises(KeyError, match="has no FAMILY_NAMES entry"):
        migrate._new_id("FET", {"id": "FET_997_STANDARD", "version": "0.1.0"})

    # A named family still projects normally.
    assert migrate._new_id("FET", manifest) == "FET010_DisplayColor.0-1-0"


def test_unnamed_family_error_points_at_the_display_name():
    with pytest.raises(KeyError, match="Widget Alignment"):
        migrate._new_id(
            "FET",
            {"id": "FET_998_STANDARD", "version": "0.1.0", "display_name": "Widget Alignment"},
        )


def test_contract_stem_drops_only_the_version_segment():
    assert migrate._contract_stem("FET004_Multibody.PhysX.0-4-0") == "FET004_Multibody.PhysX"
    assert migrate._contract_stem("CAP000_Core.0-1-0") == "CAP000_Core"


def test_hub_includes_new_contracts_without_a_legacy_catalog(tmp_path, monkeypatch):
    capabilities = tmp_path / "capabilities"
    capabilities.mkdir()
    for version in ("0-1-0", "0-2-0"):
        contract_id = f"CAP102_RigidBodyCollapse.Isaac.{version}"
        (capabilities / f"{contract_id}.json").write_text(
            json.dumps({"id": contract_id, "display_name": "Rigid-Body Collapse"}),
            encoding="utf-8",
        )
    monkeypatch.setattr(migrate, "_package_roots", lambda: [tmp_path])

    assert migrate._hub_contract_rows("capabilities") == [
        ("CAP102_RigidBodyCollapse.Isaac", "Rigid-Body Collapse", "Isaac", ["0-1-0", "0-2-0"])
    ]
    assert migrate._hub_contract_rows("features") == []


def test_hub_reports_openusd_for_neutral_ids_without_runtime_segments(tmp_path, monkeypatch):
    features = tmp_path / "features"
    features.mkdir()
    (features / "FET003_RigidBody.0-2-0.json").write_text(
        json.dumps({"id": "FET003_RigidBody.0-2-0", "display_name": "Rigid Body"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate, "_package_roots", lambda: [tmp_path])

    assert migrate._hub_contract_rows("features") == [
        ("FET003_RigidBody", "Rigid Body", "OpenUSD", ["0-2-0"])
    ]


def test_pre_underscore_legacy_ids_project_like_canonical_ones():
    """The AIF tier publishes `FET201_AIF` rather than `FET_201_AIF`."""
    assert migrate._family("FET201_AIF") == "201"
    assert migrate._new_id("CAP", {"id": "FET201_AIF", "version": "0.2.0"}) == ("CAP201_ConnectionPoints.0-2-0")


def test_legacy_page_is_read_from_the_manifest_path():
    manifest = {"id": "FET200_AIF", "path": "features/FET_200-aif_metadata.html"}
    assert migrate._legacy_page(manifest) == "FET_200-aif_metadata"
    assert migrate._legacy_page({"id": "FET_003_PHYSX"}) == "FET_003_PHYSX"


def test_feature_pages_split_between_features_and_capabilities(tmp_path):
    package_root = _tier(
        tmp_path,
        [
            _contract("FET_003_PHYSX", "FET003_RigidBody.PhysX.0-4-0", "feature"),
            _contract("FET_000_STANDARD", "CAP000_Core.0-1-0", "capability"),
        ],
        feature_pages=["FET_003_PHYSX", "FET_000_STANDARD"],
    )

    plan = migrate._relocation_plan(package_root)
    moves = {source.name: destination.relative_to(package_root).as_posix() for source, destination in plan["markdown"]}

    assert moves == {
        "FET_003_PHYSX.md": "features/FET003_RigidBody.PhysX.md",
        "FET_000_STANDARD.md": "capabilities/CAP000_Core.md",
    }


def test_all_versions_of_one_contract_share_a_single_page(tmp_path):
    package_root = _tier(
        tmp_path,
        [
            {
                "legacy_id": "FET_003_PHYSX",
                "legacy_version": version,
                "kind": "feature",
                "id": f"FET003_RigidBody.PhysX.0-{minor}-0",
            }
            for version, minor in (("0.1.0", 1), ("0.4.0", 4))
        ],
        feature_pages=["FET_003_PHYSX"],
    )

    plan = migrate._relocation_plan(package_root)

    assert len(plan["markdown"]) == 1
    assert plan["markdown"][0][1].name == "FET003_RigidBody.PhysX.md"


def test_page_not_named_after_its_contract_relocates_through_its_legacy_page(tmp_path):
    package_root = _tier(
        tmp_path,
        [
            _contract(
                "FET201_AIF",
                "CAP201_ConnectionPoints.0-1-0",
                "capability",
                page="FET_201-connection_points",
            )
        ],
        feature_pages=["FET_201-connection_points"],
    )

    plan = migrate._relocation_plan(package_root)

    moves = [
        (source.name, destination.relative_to(package_root).as_posix()) for source, destination in plan["markdown"]
    ]
    assert moves == [("FET_201-connection_points.md", "capabilities/CAP201_ConnectionPoints.md")]
    assert plan["targets"]["FET_201-connection_points"] == ("capabilities", "CAP201_ConnectionPoints")


def test_one_page_documenting_two_contracts_is_refused(tmp_path):
    package_root = _tier(
        tmp_path,
        [
            _contract("FET_003_PHYSX", "FET003_RigidBody.PhysX.0-4-0", "feature"),
            _contract("FET_003_NEWTON", "FET003_RigidBody.Newton.0-1-0", "feature", page="FET_003_PHYSX"),
        ],
        feature_pages=["FET_003_PHYSX"],
    )

    with pytest.raises(ValueError, match="cannot relocate to two contracts"):
        migrate._relocation_plan(package_root)


def test_page_without_a_contract_is_refused_rather_than_dropped(tmp_path):
    package_root = _tier(
        tmp_path,
        [_contract("FET_003_PHYSX", "FET003_RigidBody.PhysX.0-4-0", "feature")],
        feature_pages=["FET_003_PHYSX", "FET_999_ORPHAN"],
    )

    with pytest.raises(ValueError, match="no generated contract"):
        migrate._relocation_plan(package_root)


def test_two_pages_claiming_one_destination_are_refused(tmp_path):
    package_root = _tier(
        tmp_path,
        [
            _contract("FET_003_PHYSX", "FET003_RigidBody.PhysX.0-4-0", "feature"),
            _contract("FET_003_PHYSX_ALT", "FET003_RigidBody.PhysX.0-4-0", "feature"),
        ],
        feature_pages=["FET_003_PHYSX", "FET_003_PHYSX_ALT"],
    )

    with pytest.raises(ValueError, match="both relocate to"):
        migrate._relocation_plan(package_root)


def test_legacy_manifests_are_removed_and_contracts_carried_over(tmp_path):
    package_root = _tier(
        tmp_path,
        [_contract("FET_003_PHYSX", "FET003_RigidBody.PhysX.0-4-0", "feature")],
        feature_pages=["FET_003_PHYSX"],
    )
    (package_root / "features" / "FET_003_PHYSX-0.4.0.json").write_text("{}", encoding="utf-8")
    (package_root / migrate.STAGING_DIRNAME / "profiles" / "props.toml").write_text("", encoding="utf-8")

    plan = migrate._relocation_plan(package_root)

    assert [path.name for path in plan["remove"]] == ["FET_003_PHYSX-0.4.0.json"]
    destinations = {destination.relative_to(package_root).as_posix() for _, destination in plan["contracts"]}
    assert "features/FET003_RigidBody.PhysX.0-4-0.json" in destinations
    assert "profiles/props.toml" in destinations
    # Provenance survives the staging directory it was generated into.
    assert "catalog-map.json" in destinations


def test_already_relocated_tree_is_refused(tmp_path):
    package_root = _tier(
        tmp_path,
        [_contract("FET_003_PHYSX", "FET003_RigidBody.PhysX.0-4-0", "feature")],
        feature_pages=["FET_003_PHYSX"],
    )
    (package_root / "capabilities").mkdir()

    with pytest.raises(ValueError, match="revert the relocation"):
        migrate._assert_relocatable(package_root)


TARGETS = {
    "FET_000_STANDARD": ("capabilities", "CAP000_Core"),
    "FET_003_PHYSX": ("features", "FET003_RigidBody.PhysX"),
    "FET_201-connection_points": ("capabilities", "CAP201_ConnectionPoints"),
}


def test_link_to_a_page_in_the_same_section_stays_bare():
    text = "See [Rigid Body](FET_003_PHYSX.md) for details."
    rewritten, count = migrate._rewrite_contract_links(text, "features", TARGETS)
    assert rewritten == "See [Rigid Body](FET003_RigidBody.PhysX.md) for details."
    assert count == 1


def test_link_across_sections_gains_a_relative_prefix():
    text = "| Dependency | [Core](FET_000_STANDARD.md) |"
    rewritten, _ = migrate._rewrite_contract_links(text, "features", TARGETS)
    assert rewritten == "| Dependency | [Core](../capabilities/CAP000_Core.md) |"


def test_link_between_two_capability_pages_stays_bare():
    text = "[Core](FET_000_STANDARD.md)"
    rewritten, _ = migrate._rewrite_contract_links(text, "capabilities", TARGETS)
    assert rewritten == "[Core](CAP000_Core.md)"


def test_anchor_and_dot_slash_forms_are_preserved():
    text = "[a](./FET_003_PHYSX.md#requirements) and [b](FET_000_STANDARD.md#usage)"
    rewritten, count = migrate._rewrite_contract_links(text, "features", TARGETS)
    assert "(FET003_RigidBody.PhysX.md#requirements)" in rewritten
    assert "(../capabilities/CAP000_Core.md#usage)" in rewritten
    assert count == 2


def test_link_to_a_page_named_differently_from_its_contract_is_rewritten():
    text = "| Dependency | [Connection Points](FET_201-connection_points.md) |"
    rewritten, count = migrate._rewrite_contract_links(text, "capabilities", TARGETS)
    assert rewritten == "| Dependency | [Connection Points](CAP201_ConnectionPoints.md) |"
    assert count == 1


def test_unknown_and_non_contract_links_are_left_alone():
    text = "[x](FET_999_GONE.md) [y](../profiles/robot-body.md) [z](https://example.com/a.md)"
    rewritten, count = migrate._rewrite_contract_links(text, "features", TARGETS)
    assert rewritten == text
    assert count == 0


def test_relocating_without_a_generated_catalog_is_refused(tmp_path):
    package_root = tmp_path / "tier_x"
    (package_root / migrate.STAGING_DIRNAME).mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="generate before relocating"):
        migrate._relocation_plan(package_root)


def _hub(tmp_path: Path, *entries: str) -> Path:
    path = tmp_path / "features.md"
    body = ["# Features", "", "```{toctree}", ":maxdepth: 1", ":hidden:", "", *entries, "```", ""]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def test_hub_preserves_leading_and_trailing_non_contract_entries(tmp_path):
    """Dropping these orphans the pages they point at, with no error."""
    path = _hub(
        tmp_path,
        "Feature dependency graph <feature-dependency-graph>",
        "Core <FET_000_STANDARD>",
        "Rigid Body <FET003_RigidBody.PhysX>",
        "Draft - Object Color <drafts/FET_010-object-color-feature-card>",
    )

    leading, trailing = migrate._hub_preserved_entries(path)

    assert leading == ["Feature dependency graph <feature-dependency-graph>"]
    assert trailing == ["Draft - Object Color <drafts/FET_010-object-color-feature-card>"]


def test_hub_treats_pages_named_differently_from_their_contracts_as_contracts(tmp_path):
    path = _hub(
        tmp_path,
        "Feature dependency graph <feature-dependency-graph>",
        "AIF Core Metadata <FET_200-aif_metadata>",
    )

    assert migrate._hub_preserved_entries(path) == (
        ["Feature dependency graph <feature-dependency-graph>"],
        [],
    )


def test_hub_with_no_contract_entries_keeps_everything_as_leading(tmp_path):
    path = _hub(tmp_path, "Feature dependency graph <feature-dependency-graph>")

    leading, trailing = migrate._hub_preserved_entries(path)

    assert leading == ["Feature dependency graph <feature-dependency-graph>"]
    assert trailing == []


def test_hub_without_an_existing_page_preserves_nothing(tmp_path):
    assert migrate._hub_preserved_entries(tmp_path / "absent.md") == ([], [])


_OUTBOUND_TARGETS = {
    "FET_000_STANDARD": ("capabilities", "CAP000_Core"),
    "FET_003_PHYSX": ("features", "FET003_RigidBody.PhysX"),
    "FET_201-connection_points": ("capabilities", "CAP201_ConnectionPoints"),
}


def test_outbound_link_keeps_its_prefix_and_swaps_the_section():
    text = "[a](../features/FET_000_STANDARD.md) [b](../../../features/FET_003_PHYSX.md)"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == (
        "[a](../capabilities/CAP000_Core.md) " "[b](../../../features/FET003_RigidBody.PhysX.md)"
    )
    assert count == 2


def test_outbound_repository_root_path_is_rewritten_too():
    """Conform skills cite full repository paths rather than relative links."""
    text = "`nv_core/tiers/t/simready/foundation/tier_core/features/FET_000_STANDARD.md`"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == ("`nv_core/tiers/t/simready/foundation/tier_core/capabilities/CAP000_Core.md`")
    assert count == 1


def test_outbound_anchor_is_preserved():
    text = "[a](../features/FET_003_PHYSX.md#mass)"

    rewritten, _ = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == "[a](../features/FET003_RigidBody.PhysX.md#mass)"


def test_outbound_link_without_an_extension_gains_one():
    """The AIF profile page links `../features/FET_202-thermal_cooling` bare."""
    text = "[a](../features/FET_201-connection_points) [b](../features/FET_003_PHYSX#mass)"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == (
        "[a](../capabilities/CAP201_ConnectionPoints.md) " "[b](../features/FET003_RigidBody.PhysX.md#mass)"
    )
    assert count == 2


def test_outbound_mention_outside_a_link_target_is_left_alone():
    """Without `.md`, only the end of a link target marks a page reference."""
    text = "`features/FET_003_PHYSX*.json` and features/FET_003_PHYSX in prose"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == text
    assert count == 0


_OUTBOUND_MANIFESTS = {
    ("FET_003_PHYSX", "0.4.0"): ("features", "FET003_RigidBody.PhysX.0-4-0"),
    ("FET_000_STANDARD", "0.1.0"): ("capabilities", "CAP000_Core.0-1-0"),
}


def test_outbound_manifest_path_is_repointed_per_version():
    """Each published version projects to its own contract file."""
    text = "`x/features/FET_003_PHYSX-0.4.0.json` `y/features/FET_000_STANDARD-0.1.0.json`"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS, _OUTBOUND_MANIFESTS)

    assert rewritten == (
        "`x/features/FET003_RigidBody.PhysX.0-4-0.json` " "`y/capabilities/CAP000_Core.0-1-0.json`"
    )
    assert count == 2


def test_outbound_manifest_with_an_unpublished_version_is_left_alone():
    """`FET_022_MUJOCO-1.json` names a version that was never published."""
    text = "`docs/features/FET_022_MUJOCO-1.json`"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS, _OUTBOUND_MANIFESTS)

    assert rewritten == text
    assert count == 0


def test_outbound_page_and_manifest_in_one_file_both_rewrite():
    text = "[a](../features/FET_003_PHYSX.md) `../features/FET_003_PHYSX-0.4.0.json`"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS, _OUTBOUND_MANIFESTS)

    assert rewritten == (
        "[a](../features/FET003_RigidBody.PhysX.md) " "`../features/FET003_RigidBody.PhysX.0-4-0.json`"
    )
    assert count == 2


def test_outbound_manifests_are_skipped_when_no_manifest_map_is_given():
    text = "`../features/FET_003_PHYSX-0.4.0.json`"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == text
    assert count == 0


def test_outbound_unknown_and_malformed_references_are_left_alone():
    """`FET_022-driven_joints.md` names a page that never existed; leave it."""
    text = "[x](../features/FET_022-driven_joints.md) [y](../features/FET_999_GONE.md)"

    rewritten, count = migrate._rewrite_outbound_contract_links(text, _OUTBOUND_TARGETS)

    assert rewritten == text
    assert count == 0


def test_outbound_discovery_skips_contract_pages_generated_output_and_guides(tmp_path, monkeypatch):
    guides = tmp_path / "nv_core" / "sr_specs" / "docs" / "guides"
    guides.mkdir(parents=True)
    (guides / "using_features.md").write_text("", encoding="utf-8")
    (guides / "foundations2-layout-migration.md").write_text("", encoding="utf-8")
    contracts = tmp_path / "nv_core" / "tiers" / "t" / "features"
    contracts.mkdir(parents=True)
    (contracts / "FET004_Multibody.PhysX.md").write_text("", encoding="utf-8")
    build = tmp_path / "nv_core" / "_build"
    build.mkdir()
    (build / "assembled.md").write_text("", encoding="utf-8")
    skill = tmp_path / "skills" / "conform"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("", encoding="utf-8")
    nested_checkout = tmp_path / "_git"
    nested_checkout.mkdir()
    (nested_checkout / "old.md").write_text("", encoding="utf-8")

    monkeypatch.setattr(migrate, "REPO_ROOT", tmp_path)

    found = {path.name for path in migrate._outbound_markdown_files({contracts})}

    assert found == {"using_features.md", "SKILL.md"}


def _tier_dir(tmp_path: Path, *package_names: str, descriptor: bool = True) -> Path:
    tier_dir = tmp_path / "simready_foundation_tier_x"
    foundation = tier_dir / "simready" / "foundation"
    for name in package_names:
        (foundation / name).mkdir(parents=True)
        if descriptor:
            (foundation / name / "_tier.py").write_text("", encoding="utf-8")
    foundation.mkdir(parents=True, exist_ok=True)
    return tier_dir


def test_generating_on_a_relocated_tree_is_refused_before_writing(tmp_path, monkeypatch):
    """Otherwise it finds no Foundations 1 manifests and writes an empty catalog."""
    tier_dir = _tier_dir(tmp_path, "tier_x")
    package_root = tier_dir / "simready" / "foundation" / "tier_x"
    (package_root / "catalog-map.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)

    with pytest.raises(ValueError, match="already relocated"):
        migrate.generate()
    assert not (package_root / migrate.STAGING_DIRNAME).exists()


def test_a_tier_not_yet_relocated_may_be_generated(tmp_path):
    package_root = _tier_dir(tmp_path, "tier_x") / "simready" / "foundation" / "tier_x"
    (package_root / migrate.STAGING_DIRNAME).mkdir()
    (package_root / migrate.STAGING_DIRNAME / "catalog-map.json").write_text("{}", encoding="utf-8")

    migrate._assert_generatable(package_root)


def test_package_root_without_a_tier_prefix_is_discovered(tmp_path):
    """The sensors tier's package is named ``sensors``, not ``tier_sensors``.

    Discovering on the directory name silently skipped that whole tier, so the
    marker is the ``_tier.py`` descriptor instead.
    """
    tier_dir = _tier_dir(tmp_path, "sensors")

    assert migrate._tier_package_root(tier_dir).name == "sensors"


def test_directories_without_a_descriptor_are_not_package_roots(tmp_path):
    tier_dir = _tier_dir(tmp_path, "tier_core")
    foundation = tier_dir / "simready" / "foundation"
    (foundation / "__pycache__").mkdir()
    (foundation / "contracts.py").write_text("", encoding="utf-8")

    assert migrate._tier_package_root(tier_dir).name == "tier_core"


def test_tier_without_a_package_root_is_skipped(tmp_path):
    tier_dir = _tier_dir(tmp_path, "not_a_package", descriptor=False)

    assert migrate._tier_package_root(tier_dir) is None


def test_tier_with_two_package_roots_is_refused(tmp_path):
    tier_dir = _tier_dir(tmp_path, "tier_core", "sensors")

    with pytest.raises(ValueError, match="more than one package root"):
        migrate._tier_package_root(tier_dir)


def _suite_tier(tmp_path: Path, tier: str, suite: str, test_source: str) -> None:
    tier_dir = tmp_path / f"simready_foundation_tier_{tier}"
    package_root = tier_dir / "simready" / "foundation" / f"tier_{tier}"
    package_root.mkdir(parents=True)
    (package_root / "_tier.py").write_text("", encoding="utf-8")
    (tier_dir / "pyproject.toml").write_text(
        f'[tool.hatch.build.targets.wheel]\npackages = ["simready", "{suite}"]\n',
        encoding="utf-8",
    )
    (tier_dir / suite).mkdir()
    (tier_dir / suite / "__init__.py").write_text('raise AssertionError("must not import suite")\n', encoding="utf-8")
    (tier_dir / suite / "test_drop.py").write_text(test_source, encoding="utf-8")


def test_runtime_tests_are_discovered_in_every_tier_suite(tmp_path, monkeypatch):
    """Scanning only the core suite demoted tests owned by other tiers to CAPs."""
    _suite_tier(
        tmp_path,
        "core",
        "simready_benchmark_kit_suite",
        '@test(\n    features=[{"id": "FET_003_PHYSX", "version": ">=0.1.0"}],\n    name="ground_drop",\n)\n',
    )
    _suite_tier(
        tmp_path,
        "newton",
        "simready_benchmark_newton_suite",
        '@test(\n    features=[{"id": "FET_003_NEWTON", "version": ">=0.1.0"}],\n    name="ground_drop_newton",\n)\n',
    )
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)

    mappings = migrate._discover_runtime_tests()

    assert mappings["FET_003_PHYSX"] == [(">=0.1.0", "simready_benchmark_kit_suite:ground_drop")]
    assert mappings["FET_003_NEWTON"] == [(">=0.1.0", "simready_benchmark_newton_suite:ground_drop_newton")]
    provider_file = (
        tmp_path / "simready_foundation_tier_core" / "simready_benchmark_kit_suite" / "benchmark-provider.json"
    )
    provider_file.write_text(json.dumps({"provider": "simready.foundation.tier_core.runtime_tests"}), encoding="utf-8")
    assert migrate._discover_runtime_tests()["FET_003_PHYSX"] == [
        (">=0.1.0", "simready.foundation.tier_core.runtime_tests:ground_drop")
    ]


def test_a_declared_suite_missing_from_disk_is_refused(tmp_path, monkeypatch):
    _suite_tier(tmp_path, "core", "simready_benchmark_kit_suite", "")
    (tmp_path / "simready_foundation_tier_core" / "pyproject.toml").write_text(
        '[tool.hatch.build.targets.wheel]\npackages = ["simready", "simready_benchmark_gone_suite"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match="simready_benchmark_gone_suite"):
        migrate._discover_runtime_tests()


def test_no_suite_in_any_tier_is_refused(tmp_path, monkeypatch):
    _tier_dir(tmp_path, "tier_x")
    (tmp_path / "simready_foundation_tier_x" / "pyproject.toml").write_text(
        '[tool.hatch.build.targets.wheel]\npackages = ["simready"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match="ships a Benchmark test suite"):
        migrate._discover_runtime_tests()


def _namespaced_suite(tmp_path):
    tier = tmp_path / "simready_foundation_tier_example"
    package = tier / "simready/foundation/tier_example"
    suite = package / "runtime_tests"
    suite.mkdir(parents=True)
    (package / "_tier.py").write_text(
        'raise AssertionError("must not import descriptor")\n_RUNTIME_TESTS_ROOT = _owned_package_directory("simready.foundation.tier_example.runtime_tests")\n'
    )
    (tier / "pyproject.toml").write_text('[tool.hatch.build.targets.wheel]\npackages = ["simready"]\n')
    (suite / "__init__.py").write_text('raise AssertionError("must not import suite")\n')
    (suite / "evaluate-provider.json").write_text(
        json.dumps({"provider": "example.provider", "import_package": "simready.foundation.tier_example.runtime_tests"})
    )
    (suite / "probe.py").write_text(
        '@test(\n    features=[{"id": "FET_003_PHYSX", "version": ">=0.1.0"}],\n    name="probe",\n)\n'
    )
    return tier, suite


def test_catalog_discovers_declared_namespace_suite_without_importing_it(tmp_path, monkeypatch):
    _namespaced_suite(tmp_path)
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)
    assert migrate._discover_runtime_tests()["FET_003_PHYSX"] == [(">=0.1.0", "example.provider:probe")]


def test_catalog_discovers_canonical_descriptor_and_refuses_conflicting_transition(tmp_path, monkeypatch):
    _, suite = _namespaced_suite(tmp_path)
    descriptor = suite / "benchmark-provider.json"
    (suite / "evaluate-provider.json").rename(descriptor)
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)
    assert migrate._discover_runtime_tests()["FET_003_PHYSX"] == [(">=0.1.0", "example.provider:probe")]
    data = json.loads(descriptor.read_text())
    data["provider"] = "different.provider"
    (suite / "evaluate-provider.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Conflicting"):
        migrate._discover_runtime_tests()


def _historical_catalog_suite(tmp_path, monkeypatch):
    _suite_tier(
        tmp_path,
        "example",
        "historical_suite",
        '@test(\n    features=[{"id": "FET_003_PHYSX", "version": ">=0.1.0"}],\n    name="probe",\n)\n',
    )
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)
    return tmp_path / "simready_foundation_tier_example" / "historical_suite"


@pytest.mark.parametrize("filename", ["benchmark-provider.json", "evaluate-provider.json"])
def test_catalog_refuses_foreign_explicit_owner_for_historical_flat_suite(tmp_path, monkeypatch, filename):
    suite = _historical_catalog_suite(tmp_path, monkeypatch)
    (suite / filename).write_text(
        json.dumps({"provider": "stable.pack", "import_package": "foreign.pack"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="ownership.*import_package"):
        migrate._discover_runtime_tests()


@pytest.mark.parametrize("field", ["provider", "aliases"])
@pytest.mark.parametrize("identity", ["CON", "con.extension", "LPT9", "trailing.", "a" * 129])
def test_catalog_refuses_nonportable_provider_and_alias_identities(tmp_path, monkeypatch, field, identity):
    suite = _historical_catalog_suite(tmp_path, monkeypatch)
    metadata = {"provider": "stable.pack", "aliases": ["historical_suite"]}
    metadata[field] = [identity] if field == "aliases" else identity
    (suite / "benchmark-provider.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="ownership.*identit"):
        migrate._discover_runtime_tests()


@pytest.mark.parametrize("identity", ["a" * 128, "CONSOLE", "pack.CON"])
def test_catalog_accepts_portable_identity_boundary_values(tmp_path, monkeypatch, identity):
    suite = _historical_catalog_suite(tmp_path, monkeypatch)
    (suite / "benchmark-provider.json").write_text(
        json.dumps({"provider": identity, "aliases": ["valid.alias"]}), encoding="utf-8"
    )
    assert migrate._discover_runtime_tests() == {"FET_003_PHYSX": [(">=0.1.0", f"{identity}:probe")]}


@pytest.mark.parametrize("explicit_first", [False, True])
def test_catalog_accepts_equivalent_inferred_and_explicit_historical_descriptors(tmp_path, monkeypatch, explicit_first):
    suite = _historical_catalog_suite(tmp_path, monkeypatch)
    omitted = {"provider": "stable.pack", "aliases": ["historical_suite"]}
    explicit = {**omitted, "import_package": "historical_suite"}
    canonical, transitional = (explicit, omitted) if explicit_first else (omitted, explicit)
    (suite / "benchmark-provider.json").write_text(json.dumps(canonical), encoding="utf-8")
    (suite / "evaluate-provider.json").write_text(json.dumps(transitional), encoding="utf-8")
    assert migrate._discover_runtime_tests() == {"FET_003_PHYSX": [(">=0.1.0", "stable.pack:probe")]}


@pytest.mark.parametrize("conflict", ["provider", "aliases"])
def test_catalog_retains_historical_descriptor_conflict_detection(tmp_path, monkeypatch, conflict):
    suite = _historical_catalog_suite(tmp_path, monkeypatch)
    canonical = {"provider": "stable.pack", "aliases": ["historical_suite"]}
    transitional = {**canonical, "import_package": "historical_suite"}
    transitional[conflict] = "different.pack" if conflict == "provider" else ["different_alias"]
    (suite / "benchmark-provider.json").write_text(json.dumps(canonical), encoding="utf-8")
    (suite / "evaluate-provider.json").write_text(json.dumps(transitional), encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting"):
        migrate._discover_runtime_tests()


@pytest.mark.parametrize("failure", ["missing_manifest", "wrong_owner", "not_shipped", "missing_package"])
def test_catalog_refuses_invalid_advertised_namespace_ownership(tmp_path, monkeypatch, failure):
    tier, suite = _namespaced_suite(tmp_path)
    descriptor = suite / "evaluate-provider.json"
    if failure == "missing_manifest":
        descriptor.unlink()
    elif failure == "wrong_owner":
        descriptor.write_text(json.dumps({"provider": "example.provider", "import_package": "unrelated.runtime_tests"}))
    elif failure == "not_shipped":
        (tier / "pyproject.toml").write_text("[tool.hatch.build.targets.wheel]\npackages = []\n")
    else:
        (suite / "__init__.py").unlink()
    monkeypatch.setattr(migrate, "TIERS_ROOT", tmp_path)
    with pytest.raises((ValueError, FileNotFoundError), match="ownership"):
        migrate._discover_runtime_tests()


def _static_extension(tmp_path, monkeypatch):
    root = tmp_path / "tier_core"
    for section in ("features", "capabilities", "profiles"):
        (root / section).mkdir(parents=True)
    existing = _contract("FET_003_STANDARD", "FET003_RigidBody.0-1-0", "feature")
    (root / "catalog-map.json").write_text(json.dumps({"contracts": [existing]}))
    (root / "features" / "FET_026_STANDARD-0.1.0.json").write_text(
        json.dumps(
            {
                "id": "FET_026_STANDARD",
                "version": "0.1.0",
                "requirements": ["MC.001"],
                "dependencies": [{"FET_003_STANDARD": {"version": "0.1.0"}}],
            }
        )
    )
    (root / "features" / "FET_026_STANDARD.md").write_text("# Mates\n")
    profile = root / "profiles" / "prop.toml"
    published = '[Prop]\n"1.0.0" = {features = [{selector = "FET003_RigidBody.0-1-0"}]}\n'
    profile.write_text(
        published + '"2.0.0" = {features = [{"FET_026_STANDARD" = {version = "0.1.0"}, optional = true}]}\n'
    )
    monkeypatch.setattr(migrate, "_package_roots", lambda: iter([root]))
    monkeypatch.setattr(migrate, "_discover_runtime_tests", lambda: {})
    return root, profile, published


def test_static_extension_preserves_published_profile_and_optional_obligation(tmp_path, monkeypatch):
    root, profile, published = _static_extension(tmp_path, monkeypatch)
    snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert migrate.extend_static_catalogs(dry_run=True) == {"capabilities": 1, "profiles": 1, "pages": 1}
    assert snapshot == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    migrate.extend_static_catalogs()
    assert profile.read_text().startswith(published)
    versions = migrate.tomllib.loads(profile.read_text())["Prop"]
    assert versions["2.0.0"]["features"] == []
    assert versions["2.0.0"]["capabilities"] == [{"selector": "CAP026_Mates.0-1-0", "optional": True}]
    contract = json.loads((root / "capabilities" / "CAP026_Mates.0-1-0.json").read_text())
    assert contract["requirements"] == ["MC.001"]
    assert contract["features"] == ["FET003_RigidBody.0-1-0"]
    assert contract["legacy_identity"] == {"id": "FET_026_STANDARD", "version": "0.1.0"}
    assert "version" not in contract
    assert migrate.extend_static_catalogs() == {"capabilities": 0, "profiles": 0, "pages": 0}


def test_static_extension_refuses_runtime_contract_without_mutation(tmp_path, monkeypatch):
    root, _, _ = _static_extension(tmp_path, monkeypatch)
    monkeypatch.setattr(migrate, "_discover_runtime_tests", lambda: {"FET_026_STANDARD": [(">=0.1.0", "suite:mates")]})
    snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="runtime family requires explicit native"):
        migrate.extend_static_catalogs()
    assert snapshot == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_static_extension_unknown_dependency_does_not_partially_write(tmp_path, monkeypatch):
    root, _, _ = _static_extension(tmp_path, monkeypatch)
    path = root / "features" / "FET_026_STANDARD-0.1.0.json"
    data = json.loads(path.read_text())
    data["dependencies"] = [{"FET_997_STANDARD": {"version": "0.1.0"}}]
    path.write_text(json.dumps(data))
    snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(KeyError):
        migrate.extend_static_catalogs()
    assert snapshot == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_extend_static_preserves_native_entries_and_ignores_native_only_tiers(tmp_path, monkeypatch):
    root = tmp_path / "core"
    (root / "features").mkdir(parents=True)
    native = {"kind": "feature", "id": "FET006_Materials.0-3-0", "native": True}
    semantic = _contract("FET_011_STANDARD", "FET011_SemanticLabels.0-2-0", "feature")
    (root / "catalog-map.json").write_text(json.dumps({"contracts": [native, semantic]}))
    manifest = {
        "id": "FET_039_STANDARD",
        "version": "0.1.0",
        "requirements": ["AFF.001", "AFF.002"],
        "dependencies": [{"FET_011_STANDARD": {"version": "0.2.0"}}],
    }
    # The helper's default legacy version is 0.1.0; this dependency is 0.2.0.
    semantic["legacy_version"] = "0.2.0"
    (root / "catalog-map.json").write_text(json.dumps({"contracts": [native, semantic]}))
    (root / "features/FET_039_STANDARD-0.1.0.json").write_text(json.dumps(manifest))
    native_only = tmp_path / "isaac"
    native_only.mkdir()
    monkeypatch.setattr(migrate, "_package_roots", lambda: [root, native_only])
    monkeypatch.setattr(migrate, "_discover_runtime_tests", lambda: {})
    assert migrate.extend_static_catalogs(dry_run=True)["capabilities"] == 1
    destination = root / "capabilities/CAP039_ObjectAffordances.0-1-0.json"
    assert not destination.exists()
    assert migrate.extend_static_catalogs()["capabilities"] == 1
    assert json.loads(destination.read_text())["features"] == ["FET011_SemanticLabels.0-2-0"]
    assert native in json.loads((root / "catalog-map.json").read_text())["contracts"]
    pages, manifests = migrate._outbound_targets()
    assert "FET006_Materials" not in pages
    assert ("FET_039_STANDARD", "0.1.0") in manifests

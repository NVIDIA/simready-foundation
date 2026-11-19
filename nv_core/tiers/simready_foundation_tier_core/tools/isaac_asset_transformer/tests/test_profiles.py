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
from __future__ import annotations

from isaacsim.asset.transformer import RuleRegistry
from isaacsim.asset.transformer.rules import (
    register_all_rules as register_upstream_rules,
)
from simready.asset_transformer import load_profile, profile_transforms_dir
from simready.asset_transformer.patches import (
    PATCH_VERSION,
    apply_simready_rule_patches,
)
from simready.asset_transformer.rules import (
    register_all_rules as register_simready_rules,
)


def _registered_rules() -> RuleRegistry:
    apply_simready_rule_patches()
    register_upstream_rules()
    register_simready_rules()
    return RuleRegistry()


def test_every_bundled_profile_resolves_registered_rules() -> None:
    registry = _registered_rules()
    for profile_path in profile_transforms_dir().glob("*.json"):
        profile = load_profile(profile_path)
        assert all(registry.get(rule.type) is not None for rule in profile.rules), profile_path.name
        for rule in profile.rules:
            rule_class = registry.get(rule.type)
            assert rule_class is not None
            instance = rule_class.__new__(rule_class)
            allowed = {parameter.name for parameter in instance.get_configuration_parameters()}
            assert set(rule.params) <= allowed, f"{profile_path.name}: {rule.name}"


def test_robot_profile_is_preserved() -> None:
    profile = load_profile("simready_physx_to_isaac_robot")
    rules = {rule.name: rule for rule in profile.rules}
    rule_names = set(rules)

    assert profile.profile_name == "SimReady PhysX to Isaac Robot"
    assert "Make Robot Schema" in rule_names
    assert "Route Isaac Robot Schemas" in rule_names
    assert rules["Make Robot Schema"].type.startswith("isaacsim.asset.transformer.rules.")

    # Neutral physics must always be composed so the default composition carries
    # rigid bodies and joints (otherwise the Robot-Body physics validators see an
    # empty stage). It is sublayered into base.usda instead of a Physics variant.
    interface = rules["Generate Interface"].params
    assert {
        "asset_path": "payloads/base.usda",
        "target_path": "payloads/Physics/physics.usda",
        "connection_type": "Sublayer",
    } in interface["connections"]
    assert interface.get("clear_default_variant_sets", []) == []

    # Runtime variants follow the neutral RV contract: exactly Enabled/Disabled,
    # Disabled by default, so the copied SimReady_Metadata activation
    # descriptors (activateOption = "Enabled") name an option that exists.
    assert interface["excluded_variant_sets"] == ["Physics"]
    assert interface["include_none_variant"] is False
    assert interface["capitalize_variant_names"] is True
    assert interface["default_variant_selections"] == {
        "PhysX": "Disabled",
        "Newton": "Disabled",
        "MuJoCo": "Disabled",
    }
    for name in ("Flatten Base", "Generate Interface"):
        selections = rules[name].params.get("selected_variants") or rules[name].params["default_variant_selections"]
        assert {key: selections[key] for key in ("PhysX", "Newton", "MuJoCo")} == {
            "PhysX": "Disabled",
            "Newton": "Disabled",
            "MuJoCo": "Disabled",
        }
    rule_names = [rule.name for rule in profile.rules]
    assert rule_names.index("Generate Interface") < rule_names.index("Rewrite Neutral Runtime Variants")
    assert "Route Runtime Instance Opinions" in rule_names
    assert "Copy Thumbnails" in rule_names

    registry = _registered_rules()
    assert all(registry.get(rule.type) is not None for rule in profile.rules)


def test_prop_profile_has_clean_runtime_contract() -> None:
    profile = load_profile("simready_physx_to_isaac_prop")
    rules = {rule.name: rule for rule in profile.rules}

    assert "Make Robot Schema" not in rules
    assert "Route Isaac Robot Schemas" not in rules
    assert "Route Runtime Instance Opinions" in rules
    assert "Rewrite Neutral Runtime Variants" in rules
    assert "Clean Prop Package" in rules
    assert rules["Route Geometries"].type == ("isaacsim.asset.transformer.rules.perf.geometries.GeometriesRoutingRule")
    assert rules["Route Materials"].type == ("isaacsim.asset.transformer.rules.perf.materials.MaterialsRoutingRule")
    assert rules["Flatten Base"].type == ("isaacsim.asset.transformer.rules.structure.flatten.FlattenRule")
    assert rules["Route Materials"].params["textures_folder"] == "Textures"
    assert rules["Route Materials"].params["mdl_folder"] == "materials"

    interface = rules["Generate Interface"].params
    assert interface["excluded_variant_sets"] == ["Physics"]
    assert interface["include_none_variant"] is False
    assert interface["capitalize_variant_names"] is True
    assert interface["default_variant_selections"] == {
        "PhysX": "Disabled",
        "Newton": "Disabled",
        "MuJoCo": "Disabled",
    }
    rule_names = [rule.name for rule in profile.rules]
    assert rule_names.index("Delete Physics Drive and Joint State APIs") < rule_names.index(
        "Rewrite Neutral Runtime Variants"
    )
    assert rule_names.index("Rewrite Neutral Runtime Variants") < rule_names.index("Clean Prop Package")

    registry = _registered_rules()
    assert all(registry.get(rule.type) is not None for rule in profile.rules)
    rule_class = registry.get(rules["Route Geometries"].type)
    assert rule_class is not None
    assert getattr(rule_class, "__simready_patch_version__") == PATCH_VERSION
    for name in ("Route Materials", "Flatten Base"):
        assert registry.get(rules[name].type) is not None

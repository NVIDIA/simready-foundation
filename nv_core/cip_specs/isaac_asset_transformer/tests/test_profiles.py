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

from simready.asset_transformer import load_profile


def test_robot_profile_is_preserved() -> None:
    profile = load_profile("simready_physx_to_isaac_robot")
    rules = {rule.name: rule for rule in profile.rules}
    rule_names = set(rules)

    assert profile.profile_name == "SimReady PhysX to Isaac Robot"
    assert "Make Robot Schema" in rule_names
    assert "Route Isaac Robot Schemas" in rule_names
    assert all(rule.type.startswith("simready.asset_transformer.rules.") for rule in profile.rules)

    # The composed robot interface must default-select the PhysX physics variant
    # so the default composition carries rigid bodies and joints (otherwise the
    # Robot-Body-Isaac physics validators see an empty stage).
    interface = rules["Generate Interface"].params
    assert interface["default_variant_selections"] == {"Physics": "physx"}
    assert interface.get("clear_default_variant_sets", []) == []


def test_prop_profile_has_clean_runtime_contract() -> None:
    profile = load_profile("simready_physx_to_isaac_prop")
    rules = {rule.name: rule for rule in profile.rules}

    assert "Make Robot Schema" not in rules
    assert "Route Isaac Robot Schemas" not in rules
    assert "Route Runtime Instance Opinions" in rules
    assert "Clean Prop Package" in rules

    interface = rules["Generate Interface"].params
    assert interface["excluded_variant_sets"] == ["Physics"]
    assert interface["include_none_variant"] is False
    assert interface["capitalize_variant_names"] is True
    assert interface["default_variant_selections"] == {
        "PhysX": "Enabled",
        "Newton": "Disabled",
        "MuJoCo": "Disabled",
    }

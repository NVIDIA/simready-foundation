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

from pathlib import Path

from simready.asset_transformer.rules import discover_rule_classes


def test_dependency_free_rule_catalog_imports_without_kit() -> None:
    names = {rule.__name__ for rule in discover_rule_classes()}
    assert {
        "FlattenRule",
        "GeometriesRoutingRule",
        "InterfaceConnectionRule",
        "MaterialsRoutingRule",
        "PropCleanupRule",
        "VariantRoutingRule",
    } <= names


def test_complete_upstream_rule_sources_are_vendored() -> None:
    rules_root = Path(__file__).parents[1] / "src/simready/asset_transformer/rules"
    expected = {
        "isaac_sim/merge_mesh.py",
        "isaac_sim/mjc_to_physx_conversion.py",
        "isaac_sim/physx_to_mjc_conversion.py",
        "isaac_sim/robot_schema.py",
        "isaac_sim/urdf_to_mjc_physx_conversion.py",
        "isaac_sim/joint_state_api.py",
        "isaac_sim/physics_joint_pose_fix.py",
        "isaac_sim/make_lists_non_explicit.py",
        "structure/flatten.py",
        "structure/interface.py",
        "structure/variants.py",
        "core/prims.py",
        "core/properties.py",
        "core/remove_schema.py",
        "core/schemas.py",
        "perf/geometries.py",
        "perf/materials.py",
    }
    present = {path.relative_to(rules_root).as_posix() for path in rules_root.rglob("*.py")}
    assert expected <= present

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
"""Profile transformations for independent static Isaac optimization contracts.

CAP102 collapses fixed-joint bodies, CAP104 removes inactive collision schemas,
CAP103 merges visual meshes, and CAP105 replaces MaterialX shading with a preview.
Each adapter is independently selectable; priorities apply them in that order.
Eligibility comes from the composed stage and is shared with validation.

The ``simready.feature_adapters`` entry point exposes these without importing Derive.
"""

from dataclasses import dataclass
from typing import Callable

from pxr import Usd

from .fixed_joint_merge import cook_stage as _merge_fixed_joint_bodies
from .render_collision_separation import cook_stage as _separate_render_collision
from .visual_mesh_merge import cook_stage as _merge_visual_meshes
from .materialx_preview import cook_stage as _remove_materialx


def fixed_joint_rigid_body_merge(
    input_stage: Usd.Stage, output_stage: Usd.Stage
) -> None:
    """Merge rigid bodies welded by unbreakable fixed joints."""
    _merge_fixed_joint_bodies(input_stage, output_stage)
    output_stage.Save()


def remove_inactive_render_collision_schemas(
    input_stage: Usd.Stage, output_stage: Usd.Stage
) -> None:
    """Remove collision schemas that cannot produce a simulator shape."""
    _separate_render_collision(output_stage)
    output_stage.Save()


def rigid_body_visual_mesh_merge(
    input_stage: Usd.Stage, output_stage: Usd.Stage
) -> None:
    """Merge the visual meshes each rigid body owns.

    Derive passes the preceding adapter's result as ``input_stage``. Read that
    chained stage and author the merged result only to ``output_stage``.
    """
    _merge_visual_meshes(input_stage, output_stage)
    output_stage.Save()


def remove_materialx_shaders(input_stage: Usd.Stage, output_stage: Usd.Stage) -> None:
    """Keep or derive a USD Preview Surface and remove MaterialX rendering."""
    _remove_materialx(output_stage)
    output_stage.Save()


@dataclass(frozen=True)
class FeatureAdapterDefinition:
    """Dependency-neutral adapter metadata for ``FeatureAdapter.register_definition``."""

    name: str
    input_feature: str
    input_feature_version: str
    output_feature: str
    output_feature_version: str
    callback: Callable[[Usd.Stage, Usd.Stage], None]
    priority: int


def feature_adapters() -> tuple[FeatureAdapterDefinition, ...]:
    """Return the adapter inventory loaded through ``simready.feature_adapters``."""
    return (
        FeatureAdapterDefinition(
            name="fixed_joint_rigid_body_merge",
            input_feature="FET003_RigidBody.0-2-0",
            input_feature_version="0.0.0",
            output_feature="CAP102_RigidBodyCollapse.Isaac.0-1-0",
            output_feature_version="0.0.0",
            callback=fixed_joint_rigid_body_merge,
            priority=200,
        ),
        FeatureAdapterDefinition(
            name="remove_inactive_render_collision_schemas",
            input_feature="FET003_RigidBody.0-2-0",
            input_feature_version="0.0.0",
            output_feature="CAP104_RenderCollisionSeparation.Isaac.0-1-0",
            output_feature_version="0.0.0",
            callback=remove_inactive_render_collision_schemas,
            priority=150,
        ),
        FeatureAdapterDefinition(
            name="rigid_body_visual_mesh_merge",
            input_feature="FET003_RigidBody.0-2-0",
            input_feature_version="0.0.0",
            output_feature="CAP103_VisualMeshMerge.Isaac.0-1-0",
            output_feature_version="0.0.0",
            callback=rigid_body_visual_mesh_merge,
            priority=100,
        ),
        FeatureAdapterDefinition(
            name="remove_materialx_shaders",
            input_feature="FET006_Materials.Openpbr.0-2-0",
            input_feature_version="0.0.0",
            output_feature="CAP105_MaterialXRemoval.Isaac.0-1-0",
            output_feature_version="0.0.0",
            callback=remove_materialx_shaders,
            priority=50,
        ),
    )

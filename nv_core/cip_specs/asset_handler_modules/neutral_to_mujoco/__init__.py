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
"""Feature adapters that convert neutral (Standard) physics assets to MuJoCo.

Mirrors ``neutral_to_physx`` but targets the MuJoCo runtime feature contracts.
Where the PhysX adapter authors ``Physx*`` collision schemas and an SDF
approximation, these adapters author the MuJoCo collision schemas
(``MjcCollisionAPI`` / ``MjcMeshCollisionAPI``) with the ``convexHull``
approximation that ``MUJOCO.COL.001`` / ``MUJOCO.COL.002`` require. The composed
stage stays MuJoCo + neutral (no ``Physx*`` data).

A ``UsdPhysics.Scene`` with ``MjcSceneAPI`` is a scenario-level concern (global
solver/contact options for a stage containing one or more assets) and is not
authored here for a single asset.

MuJoCo USD schemas are not guaranteed to be registered in every runtime, so
applied schemas are written by name via ``Usd.Prim.AddAppliedSchema`` (the
validators read ``apiSchemas`` by name), rather than a typed schema class.
"""

import os
import sys

from omni.cip.configurable.feature_adapter import feature_adapter
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

# Add the root directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_MUJOCO_COLLISION_API = "MjcCollisionAPI"
_MUJOCO_MESH_COLLISION_API = "MjcMeshCollisionAPI"


@feature_adapter(
    name="rigid_body_neutral_to_robot_mujoco",
    input_feature_id="FET_003_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_004_ROBOT_MUJOCO",
    output_feature_version="0.1.0",
)
def rigid_body_neutral_to_robot_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_mujoco_collision(default_prim)
        output_stage.Save()


@feature_adapter(
    name="rigid_body_neutral_to_prop_mujoco",
    input_feature_id="FET_003_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_003_MUJOCO",
    output_feature_version="0.1.0",
)
def rigid_body_neutral_to_prop_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_mujoco_collision(default_prim)
        output_stage.Save()


@feature_adapter(
    name="collider_neutral_to_prop_mujoco",
    input_feature_id="FET_004_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_004_MUJOCO",
    output_feature_version="0.1.0",
)
def collider_neutral_to_prop_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_mujoco_collision(default_prim)
        output_stage.Save()


def _compute_extent(stage: Usd.Stage):
    # compute extent for all meshes
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            boundable = UsdGeom.Boundable(prim)
            extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
            if extent:
                boundable.GetExtentAttr().Set(extent)


def _apply_mujoco_collision(prim: Usd.Prim):
    """Annotate existing colliders with MuJoCo mesh-collision schemas.

    Does not create geometry. Applies ``MjcCollisionAPI`` on every active
    collider and ``MjcMeshCollisionAPI`` on mesh colliders. Mesh colliders that
    combine ``UsdPhysics.MeshCollisionAPI`` with ``MjcCollisionAPI`` must use
    ``physics:approximation = "convexHull"`` (MUJOCO.COL.002). No ``Physx*`` data
    is authored, keeping the stage MuJoCo + neutral (RV.011).
    """
    for child in Usd.PrimRange(prim):
        if not child.HasAPI(UsdPhysics.CollisionAPI):
            continue

        is_mesh = child.IsA(UsdGeom.Mesh)
        if is_mesh and not child.HasAPI(UsdPhysics.MeshCollisionAPI):
            UsdPhysics.MeshCollisionAPI.Apply(child)

        _add_applied_schema(child, _MUJOCO_COLLISION_API)

        group = child.GetAttribute("mjc:group")
        if not group:
            group = child.CreateAttribute("mjc:group", Sdf.ValueTypeNames.Int)
        group.Set(0)

        if is_mesh:
            _add_applied_schema(child, _MUJOCO_MESH_COLLISION_API)

            approx = child.GetAttribute("physics:approximation")
            if not approx:
                approx = child.CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token)
            approx.Set("convexHull")

            inertia = child.GetAttribute("mjc:inertia")
            if not inertia:
                inertia = child.CreateAttribute("mjc:inertia", Sdf.ValueTypeNames.Token)
            inertia.Set("convex")

            maxhullvert = child.GetAttribute("mjc:maxhullvert")
            if not maxhullvert:
                maxhullvert = child.CreateAttribute("mjc:maxhullvert", Sdf.ValueTypeNames.Int)
            maxhullvert.Set(-1)


def _add_applied_schema(prim: Usd.Prim, schema_name: str):
    # AddAppliedSchema writes the name into the apiSchemas list op without
    # requiring the (MuJoCo) schema plugin to be registered.
    if schema_name not in _applied_api_schemas(prim):
        prim.AddAppliedSchema(schema_name)


def _applied_api_schemas(prim: Usd.Prim) -> set:
    schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
    op = prim.GetMetadata("apiSchemas")
    if op is None:
        return schemas
    for items in (
        op.explicitItems,
        op.prependedItems,
        op.appendedItems,
        op.addedItems,
        op.orderedItems,
    ):
        schemas.update(str(schema) for schema in items)
    return schemas

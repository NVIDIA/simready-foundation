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

from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from .. import feature_adapter

_MUJOCO_COLLISION_API = "MjcCollisionAPI"
_MUJOCO_MESH_COLLISION_API = "MjcMeshCollisionAPI"
_MUJOCO_ACTUATOR_TYPE = "MjcActuator"
# Schemas that must not appear on a fixed connection joint: MjcJointAPI marks an
# articulation degree of freedom, and the weld/fixed-joint forms are not in the
# official mjcPhysics schema (CN.MUJOCO.001).
_MUJOCO_NON_FIXED_JOINT_APIS = (
    "MjcJointAPI",
    "MjcWeldAPI",
    "MjcFixedJointAPI",
)


@feature_adapter(
    name="rigid_body_neutral_to_robot_mujoco",
    input_feature_id="FET003_RigidBody.0-1-0",
    output_feature_id="CAP004_Multibody.RobotMuJoCo.0-1-0",
)
def rigid_body_neutral_to_robot_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_mujoco_collision(default_prim)
        output_stage.Save()


@feature_adapter(
    name="rigid_body_neutral_to_prop_mujoco",
    input_feature_id="FET003_RigidBody.0-1-0",
    output_feature_id="CAP003_RigidBody.MuJoCo.0-1-0",
)
def rigid_body_neutral_to_prop_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_mujoco_collision(default_prim)
        output_stage.Save()


@feature_adapter(
    name="collider_neutral_to_prop_mujoco",
    input_feature_id="FET004_Multibody.0-1-0",
    output_feature_id="CAP004_Multibody.MuJoCo.0-1-0",
)
def collider_neutral_to_prop_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_mujoco_collision(default_prim)
        output_stage.Save()


def connection_joint_neutral_to_mujoco(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Apply CAP029_ConnectionJoint.MuJoCo.0-1-0 to staged profile output."""
    _apply_mujoco_connection_joints(output_stage)


def _apply_mujoco_connection_joints(stage: Usd.Stage):
    """Make the authored joint of every jointed connection MuJoCo-ready.

    MuJoCo has no fixed joint and the official mjcPhysics schema defines no weld
    or fixed-joint type, so ``CN.MUJOCO.001`` is mostly subtractive: strip
    ``MjcJointAPI`` (which marks an articulation degree of freedom a fixed joint
    does not have) and any invented weld schema, drop ``MjcActuator`` targeting
    of the connection joint, and author explicit contact filtering on the welded
    pair.

    Converting a permanent ``jointed`` connection to ``compound``, which is the
    better MuJoCo fit, changes the rigid-body topology and is left to
    ``simready-foundation-conform-fet-029-mujoco``.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return

    joints = list(_resolve_connection_joints(stage, default_prim))
    if not joints:
        return

    joint_paths = {joint.GetPath() for joint in joints}
    for joint in joints:
        for schema_name in _MUJOCO_NON_FIXED_JOINT_APIS:
            if schema_name in _applied_api_schemas(joint):
                joint.RemoveAppliedSchema(schema_name)

        attr = joint.GetAttribute("physics:collisionEnabled")
        if not attr:
            attr = joint.CreateAttribute("physics:collisionEnabled", Sdf.ValueTypeNames.Bool)
        attr.Set(False)

    _clear_mujoco_actuator_targets(default_prim, joint_paths)
    stage.Save()


def _clear_mujoco_actuator_targets(default_prim: Usd.Prim, joint_paths: set):
    """Drop connection joints from MjcActuator target lists.

    An actuator is removed only when the connection joint was its sole target;
    an actuator that also drives real degrees of freedom keeps those targets.
    """
    for prim in Usd.PrimRange(default_prim):
        if prim.GetTypeName() != _MUJOCO_ACTUATOR_TYPE:
            continue
        for rel in prim.GetRelationships():
            targets = rel.GetTargets()
            remaining = [target for target in targets if target not in joint_paths]
            if len(remaining) == len(targets):
                continue
            if remaining:
                rel.SetTargets(remaining)
            else:
                prim.SetActive(False)


def _resolve_connection_joints(stage: Usd.Stage, default_prim: Usd.Prim):
    """Yield the joint prim of every connection whose realization is ``jointed``."""
    for prim in Usd.PrimRange(default_prim):
        realization = prim.GetAttribute("simready:mate:realization")
        if not realization or realization.Get() != "jointed":
            continue
        rel = prim.GetRelationship("simready:mate:joint")
        if not rel:
            continue
        targets = rel.GetTargets()
        if len(targets) != 1:
            continue
        joint = stage.GetPrimAtPath(targets[0])
        if joint and joint.IsValid():
            yield joint


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

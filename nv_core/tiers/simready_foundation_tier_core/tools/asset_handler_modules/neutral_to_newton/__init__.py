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
"""Feature adapters that convert neutral (Standard) physics assets to Newton.

Mirrors ``neutral_to_physx`` but targets the Newton runtime feature contracts.
Where the PhysX adapter authors ``Physx*`` collision schemas and an SDF
approximation, these adapters author the Newton collision schemas
(``NewtonCollisionAPI`` / ``NewtonMeshCollisionAPI``) that ``NEWTON.COL.001`` and
``NEWTON.COL.002`` require, keeping the composed stage strictly Newton (no
``Mjc*`` / ``Physx*`` data). They also apply ``NewtonMaterialAPI`` with default friction
tuning to bound physics materials for ``NEWTON.MAT.001``.

Newton and MuJoCo USD schemas are not guaranteed to be registered in every
runtime, so applied schemas are written by name via ``Usd.Prim.AddAppliedSchema``
(the validators read ``apiSchemas`` by name), rather than a typed schema class.
"""

from pxr import Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from .. import feature_adapter

_NEWTON_COLLISION_API = "NewtonCollisionAPI"
_NEWTON_MESH_COLLISION_API = "NewtonMeshCollisionAPI"
_NEWTON_SDF_COLLISION_API = "NewtonSDFCollisionAPI"
_NEWTON_MATERIAL_API = "NewtonMaterialAPI"
# Concrete schema defaults for the always-present Newton friction attributes. The
# contact-response attributes default to the -inf sentinel (engine default), so they are
# left unauthored rather than written explicitly.
_NEWTON_MATERIAL_DEFAULTS = (
    ("newton:torsionalFriction", 0.005),
    ("newton:rollingFriction", 0.0001),
)
_NEWTON_JOINT_API = "NewtonJointAPI"
# Newton defines no fixed-joint schema; strip the invented form if an upstream
# tool authored it (CN.NEWTON.001).
_NEWTON_FIXED_JOINT_API = "NewtonFixedJointAPI"
# Degree-of-freedom tuning has no meaning on a fixed connection joint.
_NEWTON_JOINT_DOF_ATTRS = (
    "newton:armature",
    "newton:damping",
    "newton:friction",
    "newton:velocityLimit",
    "newton:limitStiffness",
    "newton:limitDamping",
)


@feature_adapter(
    name="rigid_body_neutral_to_robot_newton",
    input_feature_id="FET003_RigidBody.0-1-0",
    output_feature_id="FET004_Multibody.RobotNewton.0-1-0",
)
def rigid_body_neutral_to_robot_newton(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_newton_collision(default_prim)
        _apply_newton_materials(default_prim)
        output_stage.Save()


@feature_adapter(
    name="rigid_body_neutral_to_prop_newton",
    input_feature_id="FET003_RigidBody.0-1-0",
    output_feature_id="FET003_RigidBody.Newton.0-1-0",
)
def rigid_body_neutral_to_prop_newton(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_newton_collision(default_prim)
        _apply_newton_materials(default_prim)
        output_stage.Save()


@feature_adapter(
    name="collider_neutral_to_prop_newton",
    input_feature_id="FET004_Multibody.0-1-0",
    output_feature_id="FET004_Multibody.Newton.0-1-0",
)
def collider_neutral_to_prop_newton(input_stage: Usd.Stage, output_stage: Usd.Stage):
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _apply_newton_collision(default_prim)
        _apply_newton_materials(default_prim)
        output_stage.Save()


def connection_joint_neutral_to_newton(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Apply CAP029_ConnectionJoint.Newton.0-1-0 to staged profile output."""
    _apply_newton_connection_joints(output_stage)


def _apply_newton_connection_joints(stage: Usd.Stage):
    """Make the authored joint of every jointed connection Newton-ready.

    Newton maps ``UsdPhysicsFixedJoint`` directly and defines no fixed-joint
    schema of its own, so ``CN.NEWTON.001`` is mostly subtractive: strip
    ``NewtonJointAPI`` and the ``newton:*`` degree-of-freedom tuning attributes
    from a joint that has no degree of freedom, and author explicit contact
    filtering rather than relying on importer defaults.

    ``newton:selfCollisionEnabled`` is authored on any articulation root that
    lacks it, defaulting to ``False`` per ``NEWTON.BA.001``. Reducing a fused
    pair of articulations to a single articulation root is left to
    ``simready-foundation-conform-fet-029-newton``: choosing which root survives
    is an authoring intent decision, not a derivable one.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return

    changed = False
    for joint in _resolve_connection_joints(stage, default_prim):
        for schema_name in (_NEWTON_JOINT_API, _NEWTON_FIXED_JOINT_API):
            if schema_name in _applied_api_schemas(joint):
                joint.RemoveAppliedSchema(schema_name)
        for attr_name in _NEWTON_JOINT_DOF_ATTRS:
            if joint.HasAttribute(attr_name):
                joint.RemoveProperty(attr_name)

        attr = joint.GetAttribute("physics:collisionEnabled")
        if not attr:
            attr = joint.CreateAttribute("physics:collisionEnabled", Sdf.ValueTypeNames.Bool)
        attr.Set(False)
        changed = True

    for prim in Usd.PrimRange(default_prim):
        if not prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            continue
        attr = prim.GetAttribute("newton:selfCollisionEnabled")
        if not attr:
            attr = prim.CreateAttribute("newton:selfCollisionEnabled", Sdf.ValueTypeNames.Bool)
        if not attr.HasAuthoredValueOpinion():
            attr.Set(False)
        changed = True

    if changed:
        stage.Save()


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


def _apply_newton_collision(prim: Usd.Prim):
    """Annotate existing colliders with Newton mesh-collision schemas.

    Does not create geometry. Applies ``NewtonCollisionAPI`` on every active
    collider and ``NewtonMeshCollisionAPI`` on mesh colliders, and authors the
    shared ``newton:contactGap`` attribute (``0`` = no additional gap; the schema
    default ``-inf`` would defer to the engine). No ``Mjc*`` / ``Physx*`` data and
    no ``physics:approximation = "sdf"`` are authored, keeping the stage strictly
    Newton (RV.011).

    ``NewtonSDFCollisionAPI`` and ``NewtonMeshCollisionAPI`` are mutually exclusive
    per the Newton schema, so a collider that already declares SDF collision keeps
    that representation and is not switched to mesh collision here.
    """
    for child in Usd.PrimRange(prim):
        if not child.HasAPI(UsdPhysics.CollisionAPI):
            continue

        has_sdf = _NEWTON_SDF_COLLISION_API in _applied_api_schemas(child)
        is_mesh = child.IsA(UsdGeom.Mesh)
        if is_mesh and not has_sdf and not child.HasAPI(UsdPhysics.MeshCollisionAPI):
            UsdPhysics.MeshCollisionAPI.Apply(child)

        _add_applied_schema(child, _NEWTON_COLLISION_API)
        if is_mesh and not has_sdf:
            _add_applied_schema(child, _NEWTON_MESH_COLLISION_API)

        contact_gap = child.GetAttribute("newton:contactGap")
        if not contact_gap:
            contact_gap = child.CreateAttribute("newton:contactGap", Sdf.ValueTypeNames.Float)
        contact_gap.Set(0.0)


def _apply_newton_materials(prim: Usd.Prim):
    """Apply ``NewtonMaterialAPI`` with default friction tuning to physics materials.

    Targets ``UsdShade.Material`` prims that carry ``PhysicsMaterialAPI`` (the physics
    materials bound to colliders). Authors only the always-present Newton friction defaults
    (``newton:torsionalFriction``, ``newton:rollingFriction``); the contact-response
    attributes are left at their ``-inf`` engine-default sentinel. Satisfies ``NEWTON.MAT.001``.
    """
    for child in Usd.PrimRange(prim):
        if not child.IsA(UsdShade.Material) or not child.HasAPI(UsdPhysics.MaterialAPI):
            continue
        _add_applied_schema(child, _NEWTON_MATERIAL_API)
        for attr_name, value in _NEWTON_MATERIAL_DEFAULTS:
            attr = child.GetAttribute(attr_name)
            if not attr:
                attr = child.CreateAttribute(attr_name, Sdf.ValueTypeNames.Float)
            if not attr.HasAuthoredValueOpinion():
                attr.Set(value)


def _add_applied_schema(prim: Usd.Prim, schema_name: str):
    # AddAppliedSchema writes the name into the apiSchemas list op without
    # requiring the (Newton) schema plugin to be registered.
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

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
"""Shared helpers for the Optimizations validators.

Everything here reads *composed* state. Optimization intent is read as raw
applied-schema tokens rather than through generated schema classes, because the
SimReady optimization schemas are not registered as a USD plugin in every
consuming process; the applied token is the declaration.
"""

from __future__ import annotations

import math

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade


# Attribute-name fragments that make a generated layer non-reproducible.


# Frames within this of each other are treated as coincident, so a rebase that
# would only introduce floating-point noise is skipped.
TRANSFORM_TOLERANCE = 1e-6


def traverse(prim: Usd.Prim) -> Usd.PrimRange:
    """Traverse including instance proxies.

    ``Usd.PrimRange`` skips instance proxies by default, and real SimReady
    assets put collision meshes and their material bindings inside instanced
    prototypes for memory reasons. Traversing without proxies finds zero
    colliders on such an asset, which makes a collider-preservation check pass
    for the wrong reason. Proxies are read-only, which is fine here: these
    helpers only inspect.
    """
    return Usd.PrimRange(prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))


def applied_schemas(prim: Usd.Prim) -> list[str]:
    value = prim.GetMetadata("apiSchemas") if prim else None
    return list(value.GetAppliedItems()) if value else []


COLLISION_SCHEMA_TOKENS = frozenset(
    {
        "MjcCollisionAPI",
        "MjcMeshCollisionAPI",
        "NewtonCollisionAPI",
        "NewtonMeshCollisionAPI",
        "NewtonSDFCollisionAPI",
        "PhysicsCollisionAPI",
        "PhysicsMeshCollisionAPI",
        "PhysxCollisionAPI",
        "PhysxConvexDecompositionCollisionAPI",
        "PhysxConvexHullCollisionAPI",
        "PhysxMeshMergeCollisionAPI",
        "PhysxSDFMeshCollisionAPI",
        "PhysxTriangleMeshCollisionAPI",
    }
)


def inactive_render_collision_schemas(prim: Usd.Prim) -> list[str]:
    """Known collision schemas that cannot produce a shape on render geometry.

    ``default`` and ``render`` purpose prims are renderable. They are only
    render-only when the composed ``PhysicsCollisionAPI`` is absent or its
    ``physics:collisionEnabled`` value is false. An enabled collider may remain
    renderable; this rule does not require duplicate render/collision geometry.
    """
    if not prim or not prim.IsValid():
        return []
    imageable = UsdGeom.Imageable(prim)
    if not imageable or imageable.ComputePurpose() not in (
        UsdGeom.Tokens.default_,
        UsdGeom.Tokens.render,
    ):
        return []

    schemas = sorted(set(applied_schemas(prim)) & COLLISION_SCHEMA_TOKENS)
    if not schemas:
        return []

    if prim.HasAPI(UsdPhysics.CollisionAPI):
        enabled = UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
        if enabled is None or bool(enabled):
            return []
    return schemas


def is_rigid_body(prim: Usd.Prim) -> bool:
    return bool(prim) and prim.HasAPI(UsdPhysics.RigidBodyAPI)


def rigid_body_owner(prim: Usd.Prim) -> Usd.Prim | None:
    """The nearest ancestor-or-self carrying an effective PhysicsRigidBodyAPI."""
    current = prim
    while current and not current.IsPseudoRoot():
        if is_rigid_body(current):
            return current
        current = current.GetParent()
    return None


def world_transform(prim: Usd.Prim) -> Gf.Matrix4d:
    return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())


# What makes a body a separately simulated endpoint. Named explicitly rather than
# pattern-matched: a substring test on "Sensor" would catch prims that merely
# mention one, and miss any schema that does not spell it that way.
#
# Applied to the body itself.
KEEP_SEPARATE_SCHEMAS = ("PhysxContactReportAPI",)

# Typed sensor prims. All derive from IsaacBaseSensor, but the inheritance is
# only queryable where the Isaac schema plugin is registered, and a validator
# must work where it is not.
SENSOR_PRIM_TYPES = (
    "IsaacContactSensor",
    "IsaacImuSensor",
    "IsaacLightBeamSensor",
    "IsaacRaycastSensor",
)

# Sensors expressed as applied API schemas rather than typed prims.
SENSOR_API_SCHEMAS = (
    "IsaacRtxLidarSensorAPI",
    "IsaacRtxRadarSensorAPI",
)


def needs_separate_simulation(body: Usd.Prim) -> str:
    """Why this body must stay its own simulated endpoint, or "" if nothing needs it.

    Shared by the validator and the adapter so the two cannot answer the same
    question differently.
    """
    applied = set(applied_schemas(body))
    for schema in KEEP_SEPARATE_SCHEMAS:
        if schema in applied:
            return f"{schema} is applied to it"

    for descendant in traverse(body):
        type_name = str(descendant.GetTypeName())
        if type_name in SENSOR_PRIM_TYPES:
            return f"<{descendant.GetPath()}> is a {type_name} beneath it"
        for schema in SENSOR_API_SCHEMAS:
            if schema in applied_schemas(descendant):
                return f"<{descendant.GetPath()}> carries {schema}"
    return ""


def mergeable_visual_meshes(body: Usd.Prim) -> list[Usd.Prim]:
    """The visual meshes this body owns that may be combined into one.

    Excluded, and each for its own reason:

    * meshes owned by a *nested* rigid body, which moves independently;
    * collision geometry, where merging convex pieces would fill a concavity;
    * anything not drawn in the default or render purpose, since proxy and guide
      geometry are shown under different conditions;
    * invisible meshes, which an author may be toggling;
    * instance proxies, because merging would de-instance shared prototypes and
      trade memory for render cost without being asked.
    """
    found = []
    it = iter(Usd.PrimRange(body, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)))
    for prim in it:
        if prim != body and is_rigid_body(prim):
            it.PruneChildren()
            continue
        if not prim.IsA(UsdGeom.Mesh) or prim.IsInstanceProxy():
            continue
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        imageable = UsdGeom.Imageable(prim)
        if imageable.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
            continue
        if imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
            continue
        found.append(prim)
    return found


# Applied schemas that only mean something on a rigid body, and become stale
# metadata the moment it stops being one. Named explicitly rather than
# pattern-matched, so a schema is only stripped when we know what it is.
#
# PhysxRigidBodyAPI is inert without the base API -- PhysX keys body-ness off
# UsdPhysicsRigidBodyAPI and this only adds solver settings -- but leaving it
# behind tells any tool reading applied schemas that this prim is a PhysX rigid
# body when it is not.
#
# PhysicsMassAPI is the sharper one: the merge folds a dissolved body's mass
# into the retained body's aggregate, so leaving the value behind means anything
# summing mass across prims counts it twice.
DISSOLVED_BODY_SCHEMAS = (
    "PhysxRigidBodyAPI",
    "PhysicsMassAPI",
)


# Relationships whose targets mean "a rigid body". When a merge dissolves a body,
# Usd.NamespaceEditor repoints these at the dissolved body's new path, which is
# correct as a namespace edit and wrong as physics: that prim is about to lose
# PhysicsRigidBodyAPI, so the target has to become the retained body instead.
#
# Joints are handled separately. physics:body0/body1 may name a *descendant* of
# the body -- the published beer bottle points them at a collision mesh, and
# UsdPhysics resolves ownership up the namespace -- so they match by prefix.
# These match the dissolved body exactly: a descendant collider stays a valid
# target for them, and rewriting it to the body would widen what it means.
BODY_RELATIONSHIPS = (
    "physics:filteredPairs",
    "isaac:physics:robotLinks",
)


def is_joint_enabled(joint_prim: Usd.Prim) -> bool:
    """False when the author disabled the joint, so it welds nothing."""
    attr = joint_prim.GetAttribute("physics:jointEnabled")
    return not (attr and attr.HasAuthoredValue() and not attr.Get())


def is_dynamic_body(prim: Usd.Prim) -> bool:
    """A rigid body the solver actually integrates.

    A kinematic or disabled body is not a merge candidate: merging one into a
    dynamic body would start simulating something the author pinned.
    """
    if not is_rigid_body(prim):
        return False
    for name, blocking in (("physics:kinematicEnabled", True),
                           ("physics:rigidBodyEnabled", False)):
        attr = prim.GetAttribute(name)
        if attr and attr.HasAuthoredValue() and bool(attr.Get()) is blocking:
            return False
    return True


def joints(stage: Usd.Stage) -> list[Usd.Prim]:
    """Every physics joint on the stage.

    Searched from the pseudo-root, not the default prim: a rig scope outside the
    asset root still welds the bodies inside it, and that survives flattening.
    """
    default_prim = stage.GetPseudoRoot()
    if not default_prim:
        return []
    return [p for p in traverse(default_prim) if p.IsActive() and UsdPhysics.Joint(p)]


def active_joints(stage: Usd.Stage) -> list[Usd.Prim]:
    """Active physics joints anywhere on the stage, including external rig scopes."""
    return joints(stage)


def joint_bodies(joint_prim: Usd.Prim) -> tuple[list[str], list[str]]:
    joint = UsdPhysics.Joint(joint_prim)
    if not joint:
        return [], []
    body0 = [str(t) for t in joint.GetBody0Rel().GetTargets()]
    body1 = [str(t) for t in joint.GetBody1Rel().GetTargets()]
    return body0, body1


def resolved_joint_bodies(stage: Usd.Stage, joint_prim: Usd.Prim) -> tuple[list[str], list[str]]:
    """Joint endpoints resolved to the rigid bodies that actually own them.

    A joint relationship may legitimately target a descendant of the body -- a
    collision mesh, for instance -- because ``UsdPhysics`` resolves ownership by
    walking up to the nearest ancestor carrying ``PhysicsRigidBodyAPI``. Real
    published assets do this, so comparing relationship targets to body paths
    literally silently misses their joints.

    An endpoint that resolves to no rigid body at all is dropped, which leaves
    an empty list and is indistinguishable from an unauthored relationship.
    Both mean the same thing to the merge: that end is the world.
    """

    def resolve(targets: list[str]) -> list[str]:
        owners = []
        for target in targets:
            prim = stage.GetPrimAtPath(target)
            owner = rigid_body_owner(prim) if prim and prim.IsValid() else None
            if owner is not None:
                owners.append(str(owner.GetPath()))
        return sorted(set(owners))

    body0, body1 = joint_bodies(joint_prim)
    return resolve(body0), resolve(body1)


def is_unbreakable(joint_prim: Usd.Prim) -> tuple[bool, str]:
    """A joint is unbreakable when break force and torque are unauthored or infinite."""
    for attr_name in ("physics:breakForce", "physics:breakTorque"):
        attr = joint_prim.GetAttribute(attr_name)
        if not attr or not attr.HasAuthoredValue():
            continue
        value = attr.Get()
        if value is None:
            continue
        if not math.isinf(float(value)):
            return False, f"{attr_name} = {value}"
    return True, ""

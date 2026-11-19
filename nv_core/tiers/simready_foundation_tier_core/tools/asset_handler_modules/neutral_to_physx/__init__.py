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
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from .. import feature_adapter

# Prefer Kit's native bindings; standalone USD uses the codeless schema package.
try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema


@feature_adapter(
    name="rigid_body_neutral_to_robot_physx",
    input_feature_id="FET003_RigidBody.0-1-0",
    output_feature_id="FET004_Multibody.RobotPhysX.0-2-0",
)
def rigid_body_neutral_to_robot_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)


@feature_adapter(
    name="rigid_body_neutral_to_robot_physx_2",
    input_feature_id="FET004_Multibody.0-2-0",
    output_feature_id="FET004_Multibody.RobotPhysX.0-3-0",
)
def rigid_body_neutral_to_robot_physx_2(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)


@feature_adapter(
    name="rigid_body_neutral_to_prop_physx",
    input_feature_id="FET003_RigidBody.0-1-0",
    output_feature_id="FET003_RigidBody.PhysX.0-1-0",
)
def rigid_body_neutral_to_prop_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)


@feature_adapter(
    name="collider_neutral_to_prop_physx",
    input_feature_id="FET004_Multibody.0-1-0",
    output_feature_id="FET004_Multibody.PhysX.0-1-0",
)
def collider_neutral_to_prop_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # set collider approximation to SDF
    _set_collider_approximation_to_sdf(output_stage)


@feature_adapter(
    name="collider_neutral_to_prop_physx_2",
    input_feature_id="FET004_Multibody.0-2-0",
    output_feature_id="FET004_Multibody.RobotPhysX.0-3-0",
)
def collider_neutral_to_prop_physx_2(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # set collider approximation to SDF
    _set_mesh_collider_sdf_approximation(output_stage)


def connection_joint_neutral_to_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Apply CAP029_ConnectionJoint.PhysX.0-1-0 to staged profile output."""
    _apply_physx_connection_joints(output_stage)


_PHYSX_JOINT_API = "PhysxJointAPI"
_PHYSX_JOINT_NAMESPACE = "physxJoint:"


def _apply_physx_connection_joints(stage: Usd.Stage):
    """Constrain the authored joint of every jointed connection to the PhysX contract.

    Applies ``CN.PHYSX.001`` to the neutral ``UsdPhysicsFixedJoint`` that
    ``CN.009`` requires; it does not create a joint. A connection whose
    ``simready:mate:joint`` does not resolve is left alone for the Standard gate
    to report.

    PhysX maps ``UsdPhysicsFixedJoint`` directly, so the PhysX delta is mostly
    subtractive. ``PhysxJointAPI`` and every ``physxJoint:`` attribute tune a
    degree of freedom that a fixed joint does not have, so they are removed. The
    sweep is by namespace, which also clears a ``physxJoint:`` name that no PhysX
    schema defines and that therefore composed as a custom attribute.

    Attach strength is ``physics:breakForce`` / ``physics:breakTorque``, which
    ``CN.009`` requires on the input stage, so it is not authored here.

    The joint belongs to the articulation it fuses, so
    ``physics:excludeFromArticulation`` is cleared where it is true and is
    otherwise left alone. Giving up the plug component's articulation root so one
    root survives is a composition edit on the assembly, not a PhysX overlay, and
    is left to the assembly author.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return

    changed = False
    for joint in _resolve_connection_joints(stage, default_prim):
        _set_bool(joint, "physics:collisionEnabled", False)

        joint.RemoveAppliedSchema(_PHYSX_JOINT_API)
        for attr in list(joint.GetAuthoredAttributes()):
            if attr.GetName().startswith(_PHYSX_JOINT_NAMESPACE):
                joint.RemoveProperty(attr.GetName())

        exclude = UsdPhysics.Joint(joint).GetExcludeFromArticulationAttr()
        if exclude and exclude.Get():
            exclude.Set(False)
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


def _set_bool(prim: Usd.Prim, attr_name: str, value: bool):
    attr = prim.GetAttribute(attr_name)
    if not attr:
        attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Bool)
    attr.Set(value)


def _compute_extent(stage: Usd.Stage):
    # compute extent for all meshes
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            boundable = UsdGeom.Boundable(prim)
            extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
            boundable.GetExtentAttr().Set(extent)


def _set_collider_approximation_to_sdf(stage: Usd.Stage):
    # Set the collider approximation to SDF
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return
    for child in Usd.PrimRange(default_prim):
        found_collider = False
        if child.HasAPI(UsdPhysics.MeshCollisionAPI):
            collider = UsdPhysics.MeshCollisionAPI(child)
            approx_attr = collider.GetApproximationAttr()
            if approx_attr:
                approx_attr.Set("sdf")
                found_collider = True
        elif child.HasAPI(UsdPhysics.CollisionAPI):
            collider = UsdPhysics.MeshCollisionAPI(child)
            approx_attr = child.GetAttribute("physics:approximation")
            if not approx_attr:
                child.CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token)
                approx_attr = child.GetAttribute("physics:approximation")
            approx_attr.Set("sdf")
            found_collider = True
        if found_collider:
            if PhysxSchema is None:
                raise RuntimeError("PhysxSchema is not available in this environment")
            child.ApplyAPI("PhysxCollisionAPI")
            child.ApplyAPI("PhysxSDFMeshCollisionAPI")
            child.ApplyAPI(UsdPhysics.MeshCollisionAPI)

    stage.Save()


def _set_mesh_collider_sdf_approximation(stage: Usd.Stage):
    # Set SDF collision approximation on mesh colliders only.
    #
    # Unlike _set_collider_approximation_to_sdf, this only touches UsdGeom.Mesh
    # (or PhysxMeshMergeCollisionAPI) colliders, preserves an already-authored
    # approximation unless it is "none", and authors a default sdfResolution.
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return
    for child in Usd.PrimRange(default_prim):
        if not child.HasAPI(UsdPhysics.CollisionAPI):
            continue

        is_mesh = child.IsA(UsdGeom.Mesh)
        is_merge_mesh = PhysxSchema is not None and child.HasAPI("PhysxMeshMergeCollisionAPI")
        # Leave regular non-mesh colliders (Cube, Sphere, etc.) untouched.
        if not (is_mesh or is_merge_mesh):
            continue

        child.ApplyAPI(UsdPhysics.MeshCollisionAPI)
        collider = UsdPhysics.MeshCollisionAPI(child)
        approx_attr = collider.GetApproximationAttr()

        # Only set "sdf" when nothing meaningful is authored yet.
        # or "none", which would use the expsensive triangle mesh approximation.
        if not approx_attr.HasAuthoredValue() or approx_attr.Get() == "none":
            collider.CreateApproximationAttr("sdf")
            approx_value = "sdf"
        else:
            approx_value = approx_attr.Get()

        if approx_value == "sdf":
            if PhysxSchema is None:
                raise RuntimeError("PhysxSchema is not available in this environment")
            child.ApplyAPI("PhysxCollisionAPI")
            sdf_api = PhysxSchema.PhysxSDFMeshCollisionAPI.Apply(child)
            resolution_attr = sdf_api.GetSdfResolutionAttr()
            if not resolution_attr.HasAuthoredValue():
                sdf_api.CreateSdfResolutionAttr(256)

    stage.Save()

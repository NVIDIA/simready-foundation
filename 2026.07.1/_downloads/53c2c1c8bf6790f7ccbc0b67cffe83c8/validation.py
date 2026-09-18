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
import math

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None

from ..utils import BaseRuleCheckerWCache

_NEWTON_COLLISION_API = "NewtonCollisionAPI"
_NEWTON_MESH_COLLISION_API = "NewtonMeshCollisionAPI"
_NEWTON_SDF_COLLISION_API = "NewtonSDFCollisionAPI"
_NEWTON_MASS_API = "NewtonMassAPI"
_MUJOCO_COLLISION_API = "MjcCollisionAPI"
_MUJOCO_MESH_COLLISION_API = "MjcMeshCollisionAPI"


def _applied_api_schemas(prim: Usd.Prim) -> set[str]:
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


def _has_applied_api_schema(prim: Usd.Prim, schema_name: str) -> bool:
    return schema_name in _applied_api_schemas(prim)


def _has_newton_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _NEWTON_COLLISION_API)


def _has_newton_mesh_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _NEWTON_MESH_COLLISION_API)


def _has_newton_sdf_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _NEWTON_SDF_COLLISION_API)


def _has_mujoco_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _MUJOCO_COLLISION_API)


def _has_mujoco_mesh_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _MUJOCO_MESH_COLLISION_API)


def _as_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _authored_value(prim: Usd.Prim, attr_name: str):
    attr = prim.GetAttribute(attr_name)
    if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
        return None
    return attr.Get()


def _is_numeric_sequence(value) -> bool:
    if value is None or isinstance(value, (str, bytes)):
        return False
    try:
        values = list(value)
    except TypeError:
        return False
    return bool(values) and all(_as_float(item) is not None for item in values)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_001, override=True)
class RigidBodyCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                return
        self._AddFailedCheck(
            requirement=cap.PhysicsRigidBodiesRequirements.RB_001,
            message="No physics rigid bodies found under the default prim.",
            at=stage,
        )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(
    cap.PhysicsRigidBodiesRequirements.RB_003,
    cap.PhysicsRigidBodiesRequirements.RB_005,
    cap.PhysicsRigidBodiesRequirements.RB_006,
    cap.PhysicsRigidBodiesRequirements.RB_009,
    override=True,
)
class RigidBodyChecker(BaseRuleCheckerWCache):
    _NESTED_RIGID_BODY_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.RB_006
    _RIGID_BODY_ORIENTATION_SCALE_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.RB_009
    _RIGID_BODY_NON_XFORMABLE_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.RB_003
    _RIGID_BODY_NON_INSTANCEABLE_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.RB_005

    _NESTED_RIGID_BODY_MESSAGE = (
        "Enabled rigid body is missing xformstack reset, when a child of a rigid body ({0}) in hierarchy. "
        "Simulation of multiple rigid bodies in a hierarchy will cause unpredicted results. Please fix the hierarchy "
        "or use XformStack reset."
    )
    _RIGID_BODY_NON_XFORMABLE_MESSAGE = "Rigid body API has to be applied to an xformable prim."
    _RIGID_BODY_NON_INSTANCEABLE_MESSAGE = "RigidBodyAPI on an instance proxy is not supported."
    _RIGID_BODY_ORIENTATION_SCALE_MESSAGE = "ScaleOrientation is not supported for rigid bodies."

    def CheckPrim(self, usd_prim: Usd.Prim):
        rb_api = UsdPhysics.RigidBodyAPI(usd_prim)
        if not rb_api:
            return

        # Check if rigid body is applied to xformable
        xformable = UsdGeom.Xformable(usd_prim)
        if not xformable:
            self._AddFailedCheck(
                message=self._RIGID_BODY_NON_XFORMABLE_MESSAGE,
                at=usd_prim,
                requirement=self._RIGID_BODY_NON_XFORMABLE_REQUIREMENT,
            )

        # Check instancing
        if usd_prim.IsInstanceProxy():
            report_instance_error = True

            # Check kinematic state
            kinematic = False
            rb_api.GetKinematicEnabledAttr().Get(kinematic)
            if kinematic:
                report_instance_error = False

            # Check if rigid body is enabled
            enabled = rb_api.GetRigidBodyEnabledAttr().Get()
            if not enabled:
                report_instance_error = False

            if report_instance_error:
                self._AddFailedCheck(
                    message=self._RIGID_BODY_NON_INSTANCEABLE_MESSAGE,
                    at=usd_prim,
                    requirement=self._RIGID_BODY_NON_INSTANCEABLE_REQUIREMENT,
                )

        # Check scale orientation
        if xformable:
            mat = self._xform_cache.GetLocalToWorldTransform(usd_prim)
            tr = Gf.Transform(mat)
            sc = tr.GetScale()

            if (
                not self._scale_is_uniform(sc)
                and tr.GetPivotOrientation().GetQuaternion() != Gf.Quaternion.GetIdentity()
            ):
                self._AddFailedCheck(
                    message=self._RIGID_BODY_ORIENTATION_SCALE_MESSAGE,
                    at=usd_prim,
                    requirement=self._RIGID_BODY_ORIENTATION_SCALE_REQUIREMENT,
                )

        # Check nested rigid body
        has_dynamic_parent, body_parent = self._has_dynamic_body_parent(usd_prim, rb_api)
        if has_dynamic_parent:
            self._AddFailedCheck(
                message=self._NESTED_RIGID_BODY_MESSAGE.format(body_parent.GetPath()),
                at=usd_prim,
                requirement=self._NESTED_RIGID_BODY_REQUIREMENT,
            )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_007, override=True)
class RigidBodyMassChecker(usd_validation_nvidia.BaseRuleChecker):
    def has_mass(self, prim: Usd.Prim) -> bool:
        return prim.HasAPI(UsdPhysics.MassAPI) and prim.GetAttribute("physics:mass").Get() is not None

    def _collect_owned_colliders(self, prim: Usd.Prim) -> list:
        """Collect colliders owned by ``prim``, not crossing into nested rigid bodies.

        The traversal stops descending at any child carrying its own
        ``RigidBodyAPI``: that body (and its subtree) owns its own mass and is
        validated on its own. ``prim`` itself is included when it is a collider.
        """
        colliders = []
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            colliders.append(prim)
        for child in prim.GetChildren():
            if child.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            colliders.extend(self._collect_owned_colliders(child))
        return colliders

    def check_rigid_body_mass_helper(self, prim: Usd.Prim) -> None:
        # Either the rigid body itself has a mass attribute, or ALL of its child
        # colliders have one. The collider search does NOT extend into other
        # rigid bodies or their children -- a nested rigid body owns its own mass.
        if self.has_mass(prim):
            return
        for child in self._collect_owned_colliders(prim):
            if not self.has_mass(child):
                self._AddFailedCheck(
                    requirement=cap.PhysicsRigidBodiesRequirements.RB_007,
                    message=f"Rigid body '{prim.GetPath()}' has no mass and child collider '{child.GetPath()}' has no mass.",
                    at=child,
                )

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                self.check_rigid_body_mass_helper(prim)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_008, override=True)
class RigidBodyHasMassAPI(usd_validation_nvidia.BaseRuleChecker):
    """Validates the *values* of authored mass properties wherever MassAPI is applied.

    This rule does NOT require ``MassAPI`` on the rigid body prim itself. Mass may
    be authored on the body or distributed across its child colliders -- that
    presence/location requirement is owned by ``RigidBodyMassChecker`` (RB_007).
    Here we only validate that, wherever a ``MassAPI`` is applied and its
    attributes are authored, the values are physically consistent:

    - authored ``physics:mass`` of 0 is reported as info (not a failure),
    - authored ``physics:diagonalInertia`` satisfies the inertia triangle
      inequality (a zero vector is reported as info),
    - an authored ``physics:principalAxes`` quaternion is normalized
      (unauthored is treated by the engine as identity, so it is skipped).
    """

    def check_mass_prim(self, prim: Usd.Prim) -> None:
        """Validate authored mass property values on a single prim with MassAPI.

        Args:
            prim: A prim carrying ``UsdPhysics.MassAPI``.
        """
        path = prim.GetPath()

        # MassAPI predeclares these attributes, so HasAttribute() is True even
        # without an authored opinion; only validate values that are authored.
        mass_attr = prim.GetAttribute("physics:mass")
        inertia_attr = prim.GetAttribute("physics:diagonalInertia")
        pa_attr = prim.GetAttribute("physics:principalAxes")

        if mass_attr and mass_attr.HasAuthoredValue():
            mass_value = mass_attr.Get()
            if mass_value == 0:
                self._AddInfo(message=f"MassAPI on {path} has mass of 0", at=prim)

        if inertia_attr and inertia_attr.HasAuthoredValue():
            diagonal_inertia = inertia_attr.Get()
            if diagonal_inertia == Gf.Vec3f(0, 0, 0):
                self._AddInfo(message=f"MassAPI on {path} has diagonal inertia of [0, 0, 0]", at=prim)
            else:
                # check triangle inequality: I1 + I2 >= I3, I1 + I3 >= I2, I2 + I3 >= I1
                i1, i2, i3 = diagonal_inertia[0], diagonal_inertia[1], diagonal_inertia[2]
                if i1 + i2 < i3:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsRigidBodiesRequirements.RB_008,
                        message=f"MassAPI on {path} violates inertia triangle inequality: I1 + I2 ({i1 + i2}) < I3 ({i3})",
                        at=prim,
                    )
                if i1 + i3 < i2:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsRigidBodiesRequirements.RB_008,
                        message=f"MassAPI on {path} violates inertia triangle inequality: I1 + I3 ({i1 + i3}) < I2 ({i2})",
                        at=prim,
                    )
                if i2 + i3 < i1:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsRigidBodiesRequirements.RB_008,
                        message=f"MassAPI on {path} violates inertia triangle inequality: I2 + I3 ({i2 + i3}) < I1 ({i1})",
                        at=prim,
                    )

        # principalAxes normalization: enforce ONLY when authored AND length is
        # meaningfully non-zero (unauthored means the engine treats it as identity).
        if pa_attr and pa_attr.HasAuthoredValue():
            length = pa_attr.Get().GetLength()
            if length > 1e-4 and abs(length - 1.0) > 1e-4:
                self._AddFailedCheck(
                    requirement=cap.PhysicsRigidBodiesRequirements.RB_008,
                    message=f"MassAPI on {path} has principal axes that is not normalized, but: {length}",
                    at=prim,
                )

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Validate authored mass property values on every prim with MassAPI.

        Args:
            stage: The USD stage to validate.
        """
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.MassAPI):
                self.check_mass_prim(prim)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_013, override=True)
class RigidBodyHasCollider(usd_validation_nvidia.BaseRuleChecker):
    """Validates that enabled rigid bodies have collision geometry.

    Ported from Isaac Sim's ``RigidBodyHasCollider``: a prim with an enabled
    RigidBodyAPI must have CollisionAPI on itself or a descendant, which is
    required for collision detection in physics simulation.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if an enabled rigid body has collision geometry.

        Args:
            prim: The USD prim to validate.
        """
        rigid_body_api = UsdPhysics.RigidBodyAPI(prim)
        if not rigid_body_api:
            return
        # check if the rigid body api is enabled
        if not rigid_body_api.GetRigidBodyEnabledAttr().Get():
            return
        for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies()):
            if p.HasAPI(UsdPhysics.CollisionAPI):
                return
        self._AddFailedCheck(
            requirement=cap.PhysicsRigidBodiesRequirements.RB_013,
            message=f"Rigid body {prim.GetPath()} has rigid body api but no collision api",
            at=prim,
        )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_001, override=True)
class RigidBodyColliderCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.HasAPI(UsdPhysics.CollisionAPI) and not prim.IsA(UsdGeom.Gprim):
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.RB_COL_001,
                message=f"Prim '{prim.GetPath()}' has CollisionAPI but is not a UsdGeom GPrim.",
                at=prim,
            )


def _collisionmeshes_collection_has_gprim(prim: Usd.Prim) -> bool:
    """Return True if the PhysxMeshMergeCollisionAPI's collisionmeshes collection includes at least one Gprim."""
    if PhysxSchema is None:
        return False
    if not prim.HasAPI(PhysxSchema.PhysxMeshMergeCollisionAPI):
        return False
    mesh_merge_api = PhysxSchema.PhysxMeshMergeCollisionAPI(prim)
    if not mesh_merge_api:
        return False
    coll_api = mesh_merge_api.GetCollisionMeshesCollectionAPI()
    if not coll_api:
        return False
    try:
        query = coll_api.ComputeMembershipQuery()
        stage = prim.GetStage()
        included_paths = coll_api.ComputeIncludedPaths(query, stage)
    except Exception:
        return False
    for path in included_paths:
        if not path.IsPrimPath():
            continue
        member_prim = stage.GetPrimAtPath(path)
        if not member_prim or not member_prim.IsValid():
            continue
        if member_prim.IsA(UsdGeom.Gprim):
            return True
        for p in Usd.PrimRange(member_prim, Usd.TraverseInstanceProxies()):
            if p.IsA(UsdGeom.Gprim):
                return True
    return False


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.PHYSX_COL_001, override=True)
class PhysxRigidBodyColliderCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """CollisionAPI may only be applied to a Gprim or to an Xform with PhysxMeshMergeCollisionAPI whose collisionmeshes collection includes at least one Gprim."""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            return
        if prim.IsA(UsdGeom.Gprim):
            return
        if (
            prim.IsA(UsdGeom.Xformable)
            and PhysxSchema is not None
            and prim.HasAPI(PhysxSchema.PhysxMeshMergeCollisionAPI)
        ):
            if _collisionmeshes_collection_has_gprim(prim):
                return
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.PHYSX_COL_001,
                message=(
                    f"Prim '{prim.GetPath()}' has CollisionAPI and PhysxMeshMergeCollisionAPI but its collisionmeshes "
                    "collection does not include any UsdGeom Gprim."
                ),
                at=prim,
            )
            return
        self._AddFailedCheck(
            requirement=cap.PhysicsRigidBodiesRequirements.PHYSX_COL_001,
            message=(
                f"Prim '{prim.GetPath()}' has CollisionAPI but is not a UsdGeom Gprim nor an Xform with "
                "PhysxMeshMergeCollisionAPI (with at least one Gprim in its collisionmeshes collection)."
            ),
            at=prim,
        )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_002, override=True)
class RigidBodyColliderMeshChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and not prim.IsA(UsdGeom.Mesh):
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.RB_COL_002,
                message=f"Prim '{prim.GetPath()}' has MeshCollisionAPI but is not a UsdGeom Mesh.",
                at=prim,
            )
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and not prim.HasAPI(UsdPhysics.CollisionAPI):
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.RB_COL_002,
                message=f"Prim '{prim.GetPath()}' has MeshCollisionAPI but does not have CollisionAPI.",
                at=prim,
            )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.PHYSX_COL_002, override=True)
class PhysxRigidBodyColliderMeshChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckPrim(self, prim: Usd.Prim) -> None:
        is_mesh = prim.IsA(UsdGeom.Mesh)
        is_merge_mesh = PhysxSchema is not None and prim.HasAPI(PhysxSchema.PhysxMeshMergeCollisionAPI)
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and not (is_mesh or is_merge_mesh):
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.PHYSX_COL_002,
                message=(
                    f"Prim '{prim.GetPath()}' has MeshCollisionAPI but is not a UsdGeom Mesh "
                    "nor a prim with PhysxMeshMergeCollisionAPI."
                ),
                at=prim,
            )
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and not prim.HasAPI(UsdPhysics.CollisionAPI):
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.PHYSX_COL_002,
                message=f"Prim '{prim.GetPath()}' has MeshCollisionAPI but does not have CollisionAPI.",
                at=prim,
            )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.NEWTON_COL_001, override=True)
class NewtonColliderAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Newton colliders must use a valid Newton collision schema representation."""

    NEWTON_COLLIDER_API_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.NEWTON_COL_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim. Unable to validate.",
                at=stage,
                requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
            )
            return

        for prim in Usd.PrimRange(default_prim):
            has_newton_collision_api = _has_newton_collision_api(prim)
            has_newton_mesh_api = _has_newton_mesh_collision_api(prim)
            has_newton_sdf_api = _has_newton_sdf_collision_api(prim)

            if has_newton_mesh_api and has_newton_sdf_api:
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has both NewtonMeshCollisionAPI and NewtonSDFCollisionAPI. "
                        "Choose one Newton mesh collision representation."
                    ),
                    at=prim,
                )

            if has_newton_collision_api and not prim.IsA(UsdGeom.Gprim):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has NewtonCollisionAPI but is not a UsdGeom Gprim. "
                        "Apply NewtonCollisionAPI to a collider shape prim."
                    ),
                    at=prim,
                )

            if has_newton_sdf_api and not prim.IsA(UsdGeom.Gprim):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has NewtonSDFCollisionAPI but is not a UsdGeom Gprim. "
                        "Apply NewtonSDFCollisionAPI to a collider shape prim."
                    ),
                    at=prim,
                )

            if has_newton_mesh_api and not prim.IsA(UsdGeom.Mesh):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has NewtonMeshCollisionAPI but is not a UsdGeom Mesh. "
                        "Apply NewtonMeshCollisionAPI to mesh collider prims."
                    ),
                    at=prim,
                )

            if (
                prim.IsA(UsdGeom.Mesh)
                and (prim.HasAPI(UsdPhysics.MeshCollisionAPI) or has_newton_collision_api)
                and not has_newton_mesh_api
                and not has_newton_sdf_api
            ):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Newton mesh collider '{prim.GetPath()}' must apply either NewtonMeshCollisionAPI "
                        "or NewtonSDFCollisionAPI."
                    ),
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.NEWTON_COL_002, override=True)
class NewtonSDFAttributesChecker(usd_validation_nvidia.BaseRuleChecker):
    """Authored Newton SDF attributes must have valid values."""

    NEWTON_SDF_ATTRIBUTES_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.NEWTON_COL_002
    _NON_NEGATIVE_FLOAT_ATTRIBUTES = (
        "newton:contactMargin",
        "newton:contactGap",
        "newton:sdfPadding",
    )
    _POSITIVE_FLOAT_ATTRIBUTES = ("newton:sdfTargetVoxelSize",)
    _OPTIONAL_ATTRIBUTES = (
        *_NON_NEGATIVE_FLOAT_ATTRIBUTES,
        *_POSITIVE_FLOAT_ATTRIBUTES,
        "newton:sdfMaxResolution",
        "newton:sdfNarrowBandInner",
        "newton:sdfNarrowBandOuter",
        "newton:sdfTextureFormat",
        "newton:hydroelasticStiffness",
    )
    _SDF_TEXTURE_FORMATS = {"uint8", "uint16", "float32"}
    _HYDROELASTIC_ENABLED_ATTR = "newton:hydroelasticEnabled"
    # An authored SDF source that satisfies the "hydroelastic requires an SDF source"
    # parse-time rule. A mesh may also carry an attached mesh.sdf, which cannot be
    # detected from USD authoring, so a missing source is a warning, not a failure.
    _SDF_SOURCE_ATTRS = (
        "newton:sdfMaxResolution",
        "newton:sdfTargetVoxelSize",
    )

    def _get_authored_value(self, prim: Usd.Prim, attr_name: str):
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return None

        value = attr.Get()
        if value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF collider '{prim.GetPath()}' has no value for attribute '{attr_name}'.",
                at=attr,
            )
        return value

    def _validate_non_negative_float(self, prim: Usd.Prim, attr_name: str, value) -> None:
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_positive_float(self, prim: Usd.Prim, attr_name: str, value) -> None:
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value <= 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be positive.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_positive_integer(self, prim: Usd.Prim, attr_name: str, value) -> None:
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value < 1 or numeric_value != int(numeric_value):
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be a positive integer.",
                at=prim.GetAttribute(attr_name),
            )
            return
        if int(numeric_value) % 8 != 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be divisible by 8.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_non_empty_token(self, prim: Usd.Prim, attr_name: str, value) -> None:
        token_value = str(value)
        if not token_value:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be non-empty.",
                at=prim.GetAttribute(attr_name),
            )
            return
        if attr_name == "newton:sdfTextureFormat" and token_value not in self._SDF_TEXTURE_FORMATS:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be one of "
                    f"{sorted(self._SDF_TEXTURE_FORMATS)}."
                ),
                at=prim.GetAttribute(attr_name),
            )

    def _validate_narrow_band(self, prim: Usd.Prim, inner, outer) -> None:
        numeric_inner = _as_float(inner)
        numeric_outer = _as_float(outer)

        if inner is not None and numeric_inner is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute 'newton:sdfNarrowBandInner' on '{prim.GetPath()}' must be numeric.",
                at=prim.GetAttribute("newton:sdfNarrowBandInner"),
            )
        if outer is not None and numeric_outer is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute 'newton:sdfNarrowBandOuter' on '{prim.GetPath()}' must be numeric.",
                at=prim.GetAttribute("newton:sdfNarrowBandOuter"),
            )
        if numeric_inner is not None and numeric_outer is not None and numeric_inner >= numeric_outer:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton SDF collider '{prim.GetPath()}' must satisfy "
                    "newton:sdfNarrowBandInner < newton:sdfNarrowBandOuter."
                ),
                at=prim,
            )

    def _validate_hydroelastic(self, prim: Usd.Prim, values: dict) -> None:
        enabled_attr = prim.GetAttribute(self._HYDROELASTIC_ENABLED_ATTR)
        if not enabled_attr.IsValid() or not enabled_attr.HasAuthoredValueOpinion():
            return
        enabled = enabled_attr.Get()
        if not isinstance(enabled, bool):
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton SDF attribute '{self._HYDROELASTIC_ENABLED_ATTR}' on '{prim.GetPath()}' "
                    "must be a boolean."
                ),
                at=enabled_attr,
            )
            return
        if not enabled:
            return
        # hydroelasticEnabled = true requires an authored SDF source (or an attached
        # mesh.sdf, which USD authoring cannot express -> warn rather than fail).
        if any(values.get(attr_name) is not None for attr_name in self._SDF_SOURCE_ATTRS):
            return
        self._AddWarning(
            requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
            message=(
                f"Newton SDF collider '{prim.GetPath()}' sets "
                f"{self._HYDROELASTIC_ENABLED_ATTR} = true but authors no SDF source "
                "(newton:sdfMaxResolution or newton:sdfTargetVoxelSize). Newton requires an SDF "
                "source at parse time unless the mesh carries an attached mesh.sdf."
            ),
            at=prim,
        )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not _has_newton_sdf_collision_api(prim) or not prim.IsA(UsdGeom.Gprim):
            return

        values = {attr_name: self._get_authored_value(prim, attr_name) for attr_name in self._OPTIONAL_ATTRIBUTES}

        for attr_name in self._NON_NEGATIVE_FLOAT_ATTRIBUTES:
            if values[attr_name] is not None:
                self._validate_non_negative_float(prim, attr_name, values[attr_name])

        for attr_name in self._POSITIVE_FLOAT_ATTRIBUTES:
            if values[attr_name] is not None:
                self._validate_positive_float(prim, attr_name, values[attr_name])

        if values["newton:sdfMaxResolution"] is not None:
            self._validate_positive_integer(prim, "newton:sdfMaxResolution", values["newton:sdfMaxResolution"])

        self._validate_narrow_band(prim, values["newton:sdfNarrowBandInner"], values["newton:sdfNarrowBandOuter"])

        texture_format = values["newton:sdfTextureFormat"]
        if texture_format is not None:
            self._validate_non_empty_token(prim, "newton:sdfTextureFormat", texture_format)

        if values["newton:hydroelasticStiffness"] is not None:
            self._validate_positive_float(
                prim,
                "newton:hydroelasticStiffness",
                values["newton:hydroelasticStiffness"],
            )

        self._validate_hydroelastic(prim, values)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.MUJOCO_COL_001, override=True)
class MuJoCoColliderAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates MuJoCo collider API placement and authored collider attributes."""

    MUJOCO_COLLIDER_API_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.MUJOCO_COL_001
    _INTEGER_ATTRIBUTES = ("mjc:group", "mjc:priority", "mjc:condim")
    _NON_NEGATIVE_NUMERIC_ATTRIBUTES = ("mjc:solmix", "mjc:margin", "mjc:gap")
    _ARRAY_ATTRIBUTES = ("mjc:solref", "mjc:solimp")

    def _validate_integer(self, prim: Usd.Prim, attr_name: str, *, non_negative: bool = False) -> None:
        value = _authored_value(prim, attr_name)
        if value is None:
            return
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value != int(numeric_value) or (non_negative and numeric_value < 0):
            descriptor = "a non-negative integer" if non_negative else "an integer"
            self._AddFailedCheck(
                requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
                message=f"MuJoCo collider attribute '{attr_name}' on '{prim.GetPath()}' must be {descriptor}.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_non_negative_number(self, prim: Usd.Prim, attr_name: str) -> None:
        value = _authored_value(prim, attr_name)
        if value is None:
            return
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
                message=f"MuJoCo collider attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_numeric_array(self, prim: Usd.Prim, attr_name: str) -> None:
        value = _authored_value(prim, attr_name)
        if value is None:
            return
        if not _is_numeric_sequence(value):
            self._AddFailedCheck(
                requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
                message=f"MuJoCo collider attribute '{attr_name}' on '{prim.GetPath()}' must be a numeric array.",
                at=prim.GetAttribute(attr_name),
            )

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim. Unable to validate.",
                at=stage,
                requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
            )
            return

        for prim in Usd.PrimRange(default_prim):
            has_collision_api = prim.HasAPI(UsdPhysics.CollisionAPI)
            has_mujoco_collision_api = _has_mujoco_collision_api(prim)

            if has_collision_api and not has_mujoco_collision_api:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
                    message=f"MuJoCo collider '{prim.GetPath()}' must apply MjcCollisionAPI.",
                    at=prim,
                )
                continue

            if not has_mujoco_collision_api:
                continue

            if not has_collision_api:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
                    message=f"Prim '{prim.GetPath()}' applies MjcCollisionAPI but does not apply PhysicsCollisionAPI.",
                    at=prim,
                )
            if not prim.IsA(UsdGeom.Gprim):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_COLLIDER_API_REQUIREMENT,
                    message=f"Prim '{prim.GetPath()}' applies MjcCollisionAPI but is not a UsdGeom Gprim.",
                    at=prim,
                )

            self._validate_integer(prim, "mjc:group", non_negative=True)
            self._validate_integer(prim, "mjc:priority")
            self._validate_integer(prim, "mjc:condim", non_negative=True)
            for attr_name in self._NON_NEGATIVE_NUMERIC_ATTRIBUTES:
                self._validate_non_negative_number(prim, attr_name)
            for attr_name in self._ARRAY_ATTRIBUTES:
                self._validate_numeric_array(prim, attr_name)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.MUJOCO_COL_002, override=True)
class MuJoCoMeshCollisionAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates MuJoCo mesh collision API placement and attributes."""

    MUJOCO_MESH_COLLISION_API_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.MUJOCO_COL_002
    _INERTIA_TOKENS = {"legacy", "convex", "exact", "shell"}

    def CheckPrim(self, prim: Usd.Prim) -> None:
        has_mujoco_mesh_collision_api = _has_mujoco_mesh_collision_api(prim)

        if has_mujoco_mesh_collision_api and not prim.IsA(UsdGeom.Mesh):
            self._AddFailedCheck(
                requirement=self.MUJOCO_MESH_COLLISION_API_REQUIREMENT,
                message=f"Prim '{prim.GetPath()}' applies MjcMeshCollisionAPI but is not a UsdGeom.Mesh.",
                at=prim,
            )
            return

        if has_mujoco_mesh_collision_api:
            inertia = _authored_value(prim, "mjc:inertia")
            if inertia is not None and str(inertia) not in self._INERTIA_TOKENS:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_MESH_COLLISION_API_REQUIREMENT,
                    message=(
                        f"MuJoCo mesh collision attribute 'mjc:inertia' on '{prim.GetPath()}' must be one of "
                        f"{sorted(self._INERTIA_TOKENS)}."
                    ),
                    at=prim.GetAttribute("mjc:inertia"),
                )

            max_hull_vertices = _authored_value(prim, "mjc:maxhullvert")
            numeric_value = _as_float(max_hull_vertices)
            if max_hull_vertices is not None and (
                numeric_value is None or numeric_value != int(numeric_value) or numeric_value < -1
            ):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_MESH_COLLISION_API_REQUIREMENT,
                    message=(
                        f"MuJoCo mesh collision attribute 'mjc:maxhullvert' on '{prim.GetPath()}' "
                        "must be an integer greater than or equal to -1."
                    ),
                    at=prim.GetAttribute("mjc:maxhullvert"),
                )

        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and _has_mujoco_collision_api(prim):
            approximation_attr = prim.GetAttribute("physics:approximation")
            approximation = approximation_attr.Get() if approximation_attr.IsValid() else None
            if str(approximation) != "convexHull":
                self._AddFailedCheck(
                    requirement=self.MUJOCO_MESH_COLLISION_API_REQUIREMENT,
                    message=(
                        f"MuJoCo mesh collider '{prim.GetPath()}' must author " "physics:approximation = 'convexHull'."
                    ),
                    at=approximation_attr if approximation_attr.IsValid() else prim,
                )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_003, override=True)
class RigidBodyColliderNonUniformScaleChecker(usd_validation_nvidia.BaseRuleChecker):

    def is_uniform_scale_geoms(self, prim: Usd.Prim) -> bool:
        return (
            prim.IsA(UsdGeom.Sphere)
            or prim.IsA(UsdGeom.Capsule)
            or prim.IsA(UsdGeom.Cylinder)
            or prim.IsA(UsdGeom.Cone)
            or prim.IsA(UsdGeom.Points)
        )

    def has_uniform_scale(self, prim: Usd.Prim) -> bool:
        scale_attr = prim.GetAttribute("xformOp:scale")
        if scale_attr.IsValid():
            scale_value = scale_attr.Get()
            if not all(x == scale_value[0] for x in scale_value):
                return False

        scale_x = prim.GetAttribute("xformOp:scaleX")
        scale_y = prim.GetAttribute("xformOp:scaleY")
        scale_z = prim.GetAttribute("xformOp:scaleZ")

        if any(scale.IsValid() for scale in [scale_x, scale_y, scale_z]):
            if not all(scale.IsValid() for scale in [scale_x, scale_y, scale_z]) or not all(
                scale.Get() == scale_x.Get() for scale in [scale_y, scale_z]
            ):
                return False

        return True  # no or uniform scale.

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.HasAPI(UsdPhysics.CollisionAPI) and self.is_uniform_scale_geoms(prim):
            if not self.has_uniform_scale(prim):
                self._AddFailedCheck(
                    requirement=cap.PhysicsRigidBodiesRequirements.RB_COL_003,
                    message=f"Prim '{prim.GetPath()}' has non-uniform scale but is a geometry type that requires uniform scale.",
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_004, override=True)
class ColliderChecker(BaseRuleCheckerWCache):
    _COLLIDER_NON_UNIFORM_SCALE_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.RB_COL_004
    _COLLIDER_NON_UNIFORM_SCALE_MESSAGE = "Non-uniform scale is not supported for {0} geometry."

    def CheckPrim(self, usd_prim: Usd.Prim):
        collision_api = UsdPhysics.CollisionAPI(usd_prim)
        if not collision_api:
            return

        if not usd_prim.IsA(UsdGeom.Gprim):
            return

        # Note: Removed Capsule_1 and Cylinder_1 from this check as they are not supported by older USD versions
        if (
            usd_prim.IsA(UsdGeom.Sphere)
            or usd_prim.IsA(UsdGeom.Capsule)
            or usd_prim.IsA(UsdGeom.Cylinder)
            or usd_prim.IsA(UsdGeom.Cone)
            or usd_prim.IsA(UsdGeom.Points)
        ):
            xform = UsdGeom.Xformable(usd_prim)
            if xform and not self._check_non_uniform_scale(xform):
                self._AddFailedCheck(
                    message=self._COLLIDER_NON_UNIFORM_SCALE_MESSAGE.format(usd_prim.GetTypeName()),
                    at=usd_prim,
                    requirement=self._COLLIDER_NON_UNIFORM_SCALE_REQUIREMENT,
                )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_010, override=True)
class InvisibleCollisionMeshHasPurposeGuide(usd_validation_nvidia.BaseRuleChecker):
    """Validates that invisible collision meshes have purpose set to 'guide'.

    This rule checks that collision meshes with visibility set to 'invisible'
    have their purpose set to 'guide', following USD best practices.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if invisible collision meshes have proper purpose setting.

        Args:
            prim: The USD prim to validate.
        """
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            return
        prim_imageable = UsdGeom.Imageable(prim)
        prim_visibility = prim_imageable.ComputeVisibility()

        match prim_visibility:
            case UsdGeom.Tokens.inherited:
                return
            case UsdGeom.Tokens.invisible:
                prim_purpose = prim_imageable.ComputePurpose()
                if prim_purpose != UsdGeom.Tokens.guide:
                    self._AddWarning(
                        message=f"Invisible collision mesh {prim.GetPath()} purpose: [{prim_purpose}], not [guide]",
                        at=prim,
                    )
                return
            case _:
                return


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_MB_001, override=True)
class MultibodyChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        rigid_body_count = 0
        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                if rigid_body_count > 0:
                    return
                rigid_body_count += 1
        self._AddFailedCheck(
            requirement=cap.PhysicsRigidBodiesRequirements.RB_MB_001,
            message=f"Not enough physics rigid bodies found under the default prim. Found {rigid_body_count}, expected at least 2.",
            at=stage,
        )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_011, override=True)
class NestedRigidBodyMassChecker(usd_validation_nvidia.BaseRuleChecker):
    def check_rigid_body_mass_helper(self, prim: Usd.Prim) -> None:
        """Validate positive mass within one rigid body's owned subtree.

        Instance-proxy descendants must be included because transformed assets
        commonly place collider and mass opinions inside instance prototypes.
        Descendant rigid bodies are pruned and validated independently.
        """
        found_valid_mass = False
        reported_negative_mass = False

        def _traverse(p: Usd.Prim, is_rigid_body_root: bool = False) -> None:
            nonlocal found_valid_mass, reported_negative_mass
            if p.HasAPI(UsdPhysics.MassAPI):
                mass_val = p.GetAttribute("physics:mass").Get()
                if mass_val is not None:
                    if mass_val < 0.0:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsRigidBodiesRequirements.RB_011,
                            message=f"Rigid body '{p.GetPath()}' has negative mass: {mass_val}",
                            at=p,
                        )
                        reported_negative_mass = True
                    elif mass_val > 0.0 and (is_rigid_body_root or p.HasAPI(UsdPhysics.CollisionAPI)):
                        found_valid_mass = True

            for child in p.GetFilteredChildren(Usd.TraverseInstanceProxies()):
                if not child.HasAPI(UsdPhysics.RigidBodyAPI):
                    _traverse(child)

        _traverse(prim, is_rigid_body_root=True)

        if found_valid_mass or reported_negative_mass:
            return

        self._AddFailedCheck(
            requirement=cap.PhysicsRigidBodiesRequirements.RB_011,
            message=(
                f"Rigid body '{prim.GetPath()}' has no valid mass: neither the body nor any "
                f"child collider carries a positive MassAPI mass."
            ),
            at=prim,
        )

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        for prim in Usd.PrimRange(default_prim, Usd.TraverseInstanceProxies()):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                self.check_rigid_body_mass_helper(prim)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_012, override=True)
class NoNestedRigidBodyWithoutJointChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that nested rigid bodies are connected by a joint.

    When a rigid body is a descendant of another rigid body in the prim hierarchy,
    there must be a joint (defined anywhere in the scene) that connects the two.
    """

    _NESTED_WITHOUT_JOINT_MESSAGE = (
        "Rigid body '{0}' is nested under rigid body '{1}' but no joint connects them. "
        "Nested rigid bodies must be connected by a joint for correct multi-body simulation."
    )

    def _resolve_body_path(self, stage: Usd.Stage, path: Sdf.Path) -> Sdf.Path:
        """Resolve a joint body target to a rigid body path.

        If the target prim is a Mesh (CollisionAPI), the parent is treated as the
        rigid body, matching the convention used by PhysicsJointCapabilityChecker.
        """
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            return path
        if prim.IsA(UsdGeom.Mesh) and prim.HasAPI(UsdPhysics.CollisionAPI):
            return prim.GetParent().GetPath()
        return path

    def _collect_joint_pairs(self, stage: Usd.Stage, default_prim: Usd.Prim) -> set:
        """Build a set of frozenset pairs representing joint-connected body paths."""
        joint_pairs = set()
        for prim in Usd.PrimRange(default_prim):
            if not prim.IsA(UsdPhysics.Joint):
                continue
            joint = UsdPhysics.Joint(prim)
            body0_targets = joint.GetBody0Rel().GetTargets()
            body1_targets = joint.GetBody1Rel().GetTargets()
            if not body0_targets or not body1_targets:
                # One side is world-anchored; skip since this doesn't connect two rigid bodies
                continue
            body0_path = self._resolve_body_path(stage, body0_targets[0])
            body1_path = self._resolve_body_path(stage, body1_targets[0])
            joint_pairs.add(frozenset((body0_path, body1_path)))
        return joint_pairs

    def _find_parent_rigid_body(self, prim: Usd.Prim) -> Usd.Prim | None:
        """Walk ancestors to find the nearest parent with RigidBodyAPI."""
        current = prim.GetParent()
        pseudo_root = prim.GetStage().GetPseudoRoot()
        while current and current != pseudo_root:
            if current.HasAPI(UsdPhysics.RigidBodyAPI):
                return current
            current = current.GetParent()
        return None

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        # Build the set of body-pairs connected by joints (joints can live anywhere)
        joint_pairs = self._collect_joint_pairs(stage, default_prim)

        # Check every rigid body for an ancestor rigid body without a connecting joint
        for prim in Usd.PrimRange(default_prim):
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            parent_rb = self._find_parent_rigid_body(prim)
            if parent_rb is None:
                continue  # Not nested
            # Nested: verify a joint connects the two
            pair = frozenset((prim.GetPath(), parent_rb.GetPath()))
            if pair not in joint_pairs:
                self._AddFailedCheck(
                    requirement=cap.PhysicsRigidBodiesRequirements.RB_012,
                    message=self._NESTED_WITHOUT_JOINT_MESSAGE.format(prim.GetPath(), parent_rb.GetPath()),
                    at=prim,
                )


@usd_validation_nvidia.register_rule("NewtonMassAttributes")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.NEWTON_MAS_001, override=True)
class NewtonMassAttributesChecker(usd_validation_nvidia.BaseRuleChecker):
    """NEWTON.MAS.001 - validate NewtonMassAPI placement and authored mass attribute values."""

    NEWTON_MASS_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.NEWTON_MAS_001

    _MASS_MODEL_ATTR = "newton:massModel"
    _INERTIA_ATTR = "newton:inertia"
    _SHELL_THICKNESS_ATTR = "newton:shellThickness"
    _ALLOWED_MASS_MODELS = ("solid", "shell")

    def _newton_mass_attrs_authored(self, prim: Usd.Prim) -> bool:
        for attr_name in (self._INERTIA_ATTR, self._MASS_MODEL_ATTR, self._SHELL_THICKNESS_ATTR):
            attr = prim.GetAttribute(attr_name)
            if attr.IsValid() and attr.HasAuthoredValueOpinion():
                return True
        return False

    def _validate_inertia(self, prim: Usd.Prim) -> None:
        value = _authored_value(prim, self._INERTIA_ATTR)
        if value is None:
            return
        elements = list(value)
        if not elements:
            # Empty array is the "no opinion" default; standard mass resolution applies.
            return
        attr = prim.GetAttribute(self._INERTIA_ATTR)
        if len(elements) != 6:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._INERTIA_ATTR}' on '{prim.GetPath()}' must have exactly 6 elements "
                    f"[Ixx, Iyy, Izz, Ixy, Ixz, Iyz], got {len(elements)}."
                ),
                at=attr,
            )
            return
        numeric = [_as_float(item) for item in elements]
        if any(value is None for value in numeric):
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=f"'{self._INERTIA_ATTR}' on '{prim.GetPath()}' must contain only finite numbers.",
                at=attr,
            )
            return
        if any(diagonal < 0 for diagonal in numeric[:3]):
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._INERTIA_ATTR}' on '{prim.GetPath()}' has a negative diagonal moment "
                    "(Ixx, Iyy, Izz must be non-negative)."
                ),
                at=attr,
            )

    def _validate_mass_model(self, prim: Usd.Prim) -> None:
        value = _authored_value(prim, self._MASS_MODEL_ATTR)
        if value is None:
            return
        if str(value) not in self._ALLOWED_MASS_MODELS:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._MASS_MODEL_ATTR}' on '{prim.GetPath()}' must be 'solid' or 'shell', " f"got '{value}'."
                ),
                at=prim.GetAttribute(self._MASS_MODEL_ATTR),
            )

    def _validate_shell_thickness(self, prim: Usd.Prim) -> None:
        value = _authored_value(prim, self._SHELL_THICKNESS_ATTR)
        if value is None:
            return
        # -inf is the sentinel that lets the active solver choose the thickness.
        if isinstance(value, float) and value == float("-inf"):
            return
        numeric_value = _as_float(value)
        attr = prim.GetAttribute(self._SHELL_THICKNESS_ATTR)
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._SHELL_THICKNESS_ATTR}' on '{prim.GetPath()}' must be a finite number "
                    "or the -inf sentinel that defers to the solver."
                ),
                at=attr,
            )
            return
        if numeric_value <= 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._SHELL_THICKNESS_ATTR}' on '{prim.GetPath()}' must be greater than 0 "
                    "(or the -inf sentinel)."
                ),
                at=attr,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        has_api = _has_applied_api_schema(prim, _NEWTON_MASS_API)
        if not has_api and not self._newton_mass_attrs_authored(prim):
            return

        if not prim.IsA(UsdGeom.Xformable):
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"NewtonMassAPI / Newton mass attributes on '{prim.GetPath()}' require an Xformable prim, "
                    f"got '{prim.GetTypeName()}'."
                ),
                at=prim,
            )
            return

        self._validate_inertia(prim)
        self._validate_mass_model(prim)
        self._validate_shell_thickness(prim)

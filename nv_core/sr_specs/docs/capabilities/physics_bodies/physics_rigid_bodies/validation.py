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
from enum import Enum

import omni.asset_validator
import omni.capabilities as cap
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None

from ... import Requirement
from ..utils import BaseRuleCheckerWCache


class MultibodyReqs(Requirement, Enum):
    RB_MB_001 = (
        "RB.MB.001",
        "has-multiple-rigid-bodies",
        "The asset must contain at least two physics rigid bodies.",
    )


class PhysxRigidBodyColliderReqs(Requirement, Enum):
    PHYSX_COL_001 = (
        "PHYSX.COL.001",
        "physx-collider-capability",
        "CollisionAPI may only be applied to a UsdGeom Gprim or to an Xform that has PhysxMeshMergeCollisionAPI and whose collisionmeshes collection includes at least one Gprim.",
    )

    PHYSX_COL_002 = (
        "PHYSX.COL.002",
        "physx-collider-mesh",
        "MeshCollisionAPI may only be applied to a UsdGeom Mesh or to a prim that has PhysxMeshMergeCollisionAPI. CollisionAPI is required whenever MeshCollisionAPI is applied.",
    )


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_001, override=True)
class RigidBodyCapabilityChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(
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

            if not self._scale_is_uniform(sc) and tr.GetPivotOrientation().GetQuaternion() != Gf.Quaternion.GetIdentity():
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_007, override=True)
class RigidBodyMassChecker(omni.asset_validator.BaseRuleChecker):
    def has_mass(self, prim: Usd.Prim) -> bool:
        return prim.HasAPI(UsdPhysics.MassAPI) and prim.GetAttribute("physics:mass").Get() is not None

    def check_rigid_body_mass_helper(self, prim: Usd.Prim) -> None:
        # either the rigid body itself has a mass attribute
        # or ALL of its children with collision have a mass attribute
        if self.has_mass(prim):
            return
        for child in Usd.PrimRange(prim):
            if child.HasAPI(UsdPhysics.CollisionAPI):
                if not self.has_mass(child):
                    self._AddFailedCheck(
                        requirement=cap.PhysicsRigidBodiesRequirements.RB_007,
                        message=f"Rigid body '{prim.GetPath()}' has no mass and child '{child.GetPath()}' has no mass.",
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_001, override=True)
class RigidBodyColliderCapabilityChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(PhysxRigidBodyColliderReqs.PHYSX_COL_001, override=True)
class PhysxRigidBodyColliderCapabilityChecker(omni.asset_validator.BaseRuleChecker):
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
                requirement=PhysxRigidBodyColliderReqs.PHYSX_COL_001,
                message=(
                    f"Prim '{prim.GetPath()}' has CollisionAPI and PhysxMeshMergeCollisionAPI but its collisionmeshes "
                    "collection does not include any UsdGeom Gprim."
                ),
                at=prim,
            )
            return
        self._AddFailedCheck(
            requirement=PhysxRigidBodyColliderReqs.PHYSX_COL_001,
            message=(
                f"Prim '{prim.GetPath()}' has CollisionAPI but is not a UsdGeom Gprim nor an Xform with "
                "PhysxMeshMergeCollisionAPI (with at least one Gprim in its collisionmeshes collection)."
            ),
            at=prim,
        )


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_002, override=True)
class RigidBodyColliderMeshChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.PHYSX_COL_002, override=True)
class PhysxRigidBodyColliderMeshChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.PHYSX_COL_002, override=True)
class PhysxRigidBodyColliderMeshChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_003, override=True)
class RigidBodyColliderNonUniformScaleChecker(omni.asset_validator.BaseRuleChecker):

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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_COL_004, override=True)
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


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_010, override=True)
class InvisibleCollisionMeshHasPurposeGuide(omni.asset_validator.BaseRuleChecker):
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
                prim_purpose = prim_imageable.GetPurposeAttr().Get()
                if prim_purpose != UsdGeom.Tokens.guide:
                    self._AddWarning(
                        message=f"Invisible collision mesh {prim.GetPath()} purpose: [{prim_purpose}], not [guide]",
                        at=prim,
                    )
                return
            case _:
                return


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(MultibodyReqs.RB_MB_001, override=True)
class MultibodyChecker(omni.asset_validator.BaseRuleChecker):
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
            requirement=MultibodyReqs.RB_MB_001,
            message=f"Not enough physics rigid bodies found under the default prim. Found {rigid_body_count}, expected at least 2.",
            at=stage,
        )


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_011, override=True)
class NestedRigidBodyMassChecker(omni.asset_validator.BaseRuleChecker):
    def has_mass(self, prim: Usd.Prim) -> bool:
        return prim.HasAPI(UsdPhysics.MassAPI) and prim.GetAttribute("physics:mass").Get() is not None

    def check_rigid_body_mass_helper(self, prim: Usd.Prim) -> None:
        # do a full traversal of all children, excluding any children with RigidBodyAPI
        # sum the mass of all prims (parent and children) and check if the total mass is greater than 0
        # if the total mass is 0, that means the value(s) will be auto computed
        # and we should expect to find one or more valid colliders with non-zero volume
        # if no valid colliders are found, we should add a failure
        total_mass = 0.0
        found_valid_collider = False

        def _get_mass(p: Usd.Prim) -> float:
            if p.HasAPI(UsdPhysics.MassAPI):
                mass_val = p.GetAttribute("physics:mass").Get()
                if mass_val is not None and mass_val > 0:
                    return float(mass_val)
            return 0.0

        def _has_non_zero_volume(p: Usd.Prim) -> bool:
            if not p.IsA(UsdGeom.Boundable):
                return False
            boundable = UsdGeom.Boundable(p)
            extent = boundable.GetExtentAttr().Get()
            if extent is None or len(extent) < 2:
                return False
            range_vec = extent[1] - extent[0]
            return all(range_vec[i] > 0 for i in range(3))

        def _traverse(p: Usd.Prim) -> None:
            nonlocal total_mass, found_valid_collider
            mass = _get_mass(p)
            if mass < 0.0:
                self._AddFailedCheck(
                    requirement=cap.PhysicsRigidBodiesRequirements.RB_011,
                    message=f"Rigid body '{p.GetPath()}' has negative mass: {mass}",
                    at=p,
                )
                return
            total_mass += max(0.0, mass)
            if p.HasAPI(UsdPhysics.CollisionAPI) and _has_non_zero_volume(p):
                found_valid_collider = True
            for child in p.GetChildren():
                if not child.HasAPI(UsdPhysics.RigidBodyAPI):
                    _traverse(child)

        _traverse(prim)

        if total_mass > 0:
            return

        if not found_valid_collider:
            self._AddFailedCheck(
                requirement=cap.PhysicsRigidBodiesRequirements.RB_011,
                message=(
                    f"Rigid body '{prim.GetPath()}' has no explicit mass and no valid "
                    f"colliders with non-zero volume for mass auto-computation."
                ),
                at=prim,
            )

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                self.check_rigid_body_mass_helper(prim)


@omni.asset_validator.register_rule("PhysicsRigidBodies")
@omni.asset_validator.register_requirements(cap.PhysicsRigidBodiesRequirements.RB_012, override=True)
class NoNestedRigidBodyWithoutJointChecker(omni.asset_validator.BaseRuleChecker):
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

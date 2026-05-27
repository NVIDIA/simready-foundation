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
import omni.asset_validator
import omni.capabilities as cap
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from ..utils import BaseRuleCheckerWCache


@omni.asset_validator.register_rule("PhysicsJoints")
@omni.asset_validator.register_requirements(cap.PhysicsJointsRequirements.JT_001, override=True)
class PhysicsJointCapabilityChecker(omni.asset_validator.BaseRuleChecker):

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        rigid_body_path_list = []
        joint_list = []
        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                rigid_body_path_list.append(prim.GetPath())

            if prim.IsA(UsdPhysics.Joint):
                joint_list.append(prim)

        if len(rigid_body_path_list) == 0:
            return

        rigid_bodies_from_joint_set = set()
        for joint_prim in joint_list:
            joint = UsdPhysics.Joint(joint_prim)
            joint_body_0 = joint.GetBody0Rel().GetTargets()
            joint_body_1 = joint.GetBody1Rel().GetTargets()
            if joint_body_0:
                joint_body_0_path = joint_body_0[0]
                joint_body_0_prim = stage.GetPrimAtPath(joint_body_0_path)
                if joint_body_0_prim.IsA(UsdGeom.Mesh):
                    rigid_bodies_from_joint_set.add(joint_body_0_path)
                    rigid_bodies_from_joint_set.add(joint_body_0_prim.GetParent().GetPath())
                else:
                    rigid_bodies_from_joint_set.add(joint_body_0_path)
            if joint_body_1:
                joint_body_1_path = joint_body_1[0]
                joint_body_1_prim = stage.GetPrimAtPath(joint_body_1_path)
                if joint_body_1_prim.IsA(UsdGeom.Mesh):
                    rigid_bodies_from_joint_set.add(joint_body_1_path)
                    rigid_bodies_from_joint_set.add(joint_body_1_prim.GetParent().GetPath())
                else:
                    rigid_bodies_from_joint_set.add(joint_body_1_path)

        return all(body in rigid_bodies_from_joint_set for body in rigid_body_path_list)


@omni.asset_validator.register_rule("PhysicsJoints")
@omni.asset_validator.register_requirements(
    cap.PhysicsJointsRequirements.JT_002, cap.PhysicsJointsRequirements.JT_003, override=True
)
class PhysicsJointChecker(omni.asset_validator.BaseRuleChecker):
    _JOINT_INVALID_PRIM_REL_REQUIREMENT = cap.PhysicsJointsRequirements.JT_002
    _JOINT_MULTIPLE_PRIMS_REL_REQUIREMENT = cap.PhysicsJointsRequirements.JT_003

    _JOINT_INVALID_PRIM_REL_MESSAGE = (
        "Joint's Body{0} relationship points to a non-existent prim {1}, joint will not be parsed."
    )
    _JOINT_MULTIPLE_PRIMS_REL_MESSAGE = (
        "Joint prim does have a Body{0} relationship to multiple bodies and this is not supported."
    )

    def CheckPrim(self, usd_prim: Usd.Prim):
        physics_joint = UsdPhysics.Joint(usd_prim)

        if not physics_joint:
            return

        # Check valid relationship prims
        rel0path = _get_rel(physics_joint.GetBody0Rel())
        rel1path = _get_rel(physics_joint.GetBody1Rel())

        # Check relationship validity
        if not _check_joint_rel(rel0path, usd_prim):
            self._AddFailedCheck(
                message=self._JOINT_INVALID_PRIM_REL_MESSAGE.format(0, rel0path),
                at=usd_prim,
                requirement=self._JOINT_INVALID_PRIM_REL_REQUIREMENT,
            )

        if not _check_joint_rel(rel1path, usd_prim):
            self._AddFailedCheck(
                message=self._JOINT_INVALID_PRIM_REL_MESSAGE.format(1, rel1path),
                at=usd_prim,
                requirement=self._JOINT_INVALID_PRIM_REL_REQUIREMENT,
            )

        # Check multiple relationship prims
        targets0 = physics_joint.GetBody0Rel().GetTargets()
        targets1 = physics_joint.GetBody1Rel().GetTargets()

        # Check relationship validity
        if len(targets0) > 1:
            self._AddFailedCheck(
                message=self._JOINT_MULTIPLE_PRIMS_REL_MESSAGE.format(0),
                at=usd_prim,
                requirement=self._JOINT_MULTIPLE_PRIMS_REL_REQUIREMENT,
            )

        if len(targets1) > 1:
            self._AddFailedCheck(
                message=self._JOINT_MULTIPLE_PRIMS_REL_MESSAGE.format(1),
                at=usd_prim,
                requirement=self._JOINT_MULTIPLE_PRIMS_REL_REQUIREMENT,
            )


@omni.asset_validator.register_rule("PhysicsJoints")
@omni.asset_validator.register_requirements(
    cap.PhysicsJointsRequirements.JT_ART_002,
    cap.PhysicsJointsRequirements.JT_ART_003,
    cap.PhysicsJointsRequirements.JT_ART_004,
    override=True,
)
class ArticulationChecker(BaseRuleCheckerWCache):
    _NESTED_ARTICULATION_REQUIREMENT = cap.PhysicsJointsRequirements.JT_ART_002
    _ARTICULATION_ON_STATIC_BODY_REQUIREMENT = cap.PhysicsJointsRequirements.JT_ART_003
    _ARTICULATION_ON_KINEMATIC_BODY_REQUIREMENT = cap.PhysicsJointsRequirements.JT_ART_004

    _NESTED_ARTICULATION_MESSAGE = "Nested ArticulationRootAPI not supported."
    _ARTICULATION_ON_STATIC_BODY_MESSAGE = "ArticulationRootAPI definition on a static rigid body is not allowed."
    _ARTICULATION_ON_KINEMATIC_BODY_MESSAGE = "ArticulationRootAPI definition on a kinematic rigid body is not allowed."

    def CheckPrim(self, usd_prim: Usd.Prim):
        art_api = UsdPhysics.ArticulationRootAPI(usd_prim)

        if not art_api:
            return

        # Check for nested articulation roots
        if self._is_under_articulation_root(usd_prim):
            self._AddFailedCheck(
                message=self._NESTED_ARTICULATION_MESSAGE,
                at=usd_prim,
                requirement=self._NESTED_ARTICULATION_REQUIREMENT,
            )

        # Check rigid body static or kinematic errors
        rbo_api = UsdPhysics.RigidBodyAPI(usd_prim)
        if rbo_api:
            # Check if rigid body is enabled
            body_enabled = rbo_api.GetRigidBodyEnabledAttr().Get()
            if not body_enabled:
                self._AddFailedCheck(
                    message=self._ARTICULATION_ON_STATIC_BODY_MESSAGE,
                    at=usd_prim,
                    requirement=self._ARTICULATION_ON_STATIC_BODY_REQUIREMENT,
                )

            # Check if kinematic is enabled
            kinematic_enabled = rbo_api.GetKinematicEnabledAttr().Get()
            if kinematic_enabled:
                self._AddFailedCheck(
                    message=self._ARTICULATION_ON_KINEMATIC_BODY_MESSAGE,
                    at=usd_prim,
                    requirement=self._ARTICULATION_ON_KINEMATIC_BODY_REQUIREMENT,
                )


def _get_rel(ref: Usd.Relationship) -> Sdf.Path:
    targets = ref.GetTargets()

    if not targets:
        return Sdf.Path()

    return targets[0]


def _check_joint_rel(rel_path: Sdf.Path, joint_prim: Usd.Prim) -> bool:
    if rel_path == Sdf.Path():
        return True

    rel_prim = joint_prim.GetStage().GetPrimAtPath(rel_path)
    return rel_prim.IsValid()

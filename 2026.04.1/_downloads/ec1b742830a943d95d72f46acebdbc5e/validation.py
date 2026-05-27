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
__all__ = ["PhysicsDrivenJointsValidation"]

from collections import defaultdict
from enum import Enum

import omni.asset_validator
from pxr import Gf, Usd, UsdGeom, UsdPhysics

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None

from ... import Requirement


class DrivenJointsCapReq(Requirement, Enum):
    DJ_001 = (
        "DJ.001",
        "physics-drive-and-joint-state",
        "Physics driven joints must have proper drive and state configuration for controlled simulation.",
    )

    DJ_002 = (
        "DJ.002",
        "joint-has-joint-state-api",
        "Driven joints must implement proper joint state API for simulation state management.",
    )

    DJ_003 = (
        "DJ.003",
        "joint-has-correct-transform-and-state",
        "Driven joints must maintain correct transform relationships and state consistency.",
    )

    DJ_004 = (
        "DJ.004",
        "physics-joint-has-drive-or-mimic-api",
        "PhysX driven joints must implement drive API or mimic functionality for controlled motion.",
    )

    DJ_005 = (
        "DJ.005",
        "physics-joint-max-velocity",
        "PhysX driven joints must have appropriate maximum velocity limits configured.",
    )

    DJ_006 = (
        "DJ.006",
        "drive-joint-value-reasonable",
        "Drive joint parameters must be within reasonable ranges for stable simulation.",
    )

    DJ_007 = (
        "DJ.007",
        "mimic-api-check",
        "Mimic API configuration must be properly validated for coordinated joint motion.",
    )

    DJ_008 = (
        "DJ.008",
        "robot-schema-joint-exist",
        "Robot schema joints must exist and be properly defined for Isaac Sim integration.",
    )

    DJ_009 = (
        "DJ.009",
        "robot-schema-links-exist",
        "Robot schema links must exist and be properly connected to joints for kinematic chain definition.",
    )

    DJ_010 = (
        "DJ.010",
        "check-robot-relationships",
        "Robot joint and link relationships must be validated for proper kinematic tree structure.",
    )

    DJ_011 = (
        "DJ.011",
        "no-articulation-loops",
        "Articulation must have no loops and at most one joint between any two bodies.",
    )


def get_world_body_transform(stage, cache, joint, body0base):
    """Get the world transform of a joint computed from either body 0 or body 1.

    Args:
        stage: The USD stage containing the joint.
        cache: XformCache for efficient transform computation.
        joint: The joint to compute the transform for.
        body0base: If True, compute transform from body 0, otherwise from body 1.

    Returns:
        The world transform of the joint.
    """
    # get both bodies if available
    b0paths = joint.GetBody0Rel().GetTargets()
    b1paths = joint.GetBody1Rel().GetTargets()

    b0prim = None
    b1prim = None

    if len(b0paths):
        b0prim = stage.GetPrimAtPath(b0paths[0])
        if not b0prim.IsValid():
            b0prim = None

    if len(b1paths):
        b1prim = stage.GetPrimAtPath(b1paths[0])
        if not b1prim.IsValid():
            b1prim = None

    b0locpos = joint.GetLocalPos0Attr().Get()
    b1locpos = joint.GetLocalPos1Attr().Get()
    b0locrot = joint.GetLocalRot0Attr().Get()
    b1locrot = joint.GetLocalRot1Attr().Get()

    # switch depending on which is the base
    if body0base:
        t0prim = b0prim
        t0locpos = b0locpos
        t0locrot = b0locrot
        t1prim = b1prim
    else:
        t0prim = b1prim
        t0locpos = b1locpos
        t0locrot = b1locrot
        t1prim = b0prim

    if t0prim:
        t0world = cache.GetLocalToWorldTransform(t0prim)
    else:
        t0world = Gf.Matrix4d()
        t0world.SetIdentity()

    if t1prim:
        t1world = cache.GetLocalToWorldTransform(t1prim)
    else:
        t1world = Gf.Matrix4d()
        t1world.SetIdentity()

    t0local = Gf.Transform()
    t0local.SetRotation(Gf.Rotation(Gf.Quatd(t0locrot)))
    t0local.SetTranslation(Gf.Vec3d(t0locpos))
    t0mult = t0local * Gf.Transform(t0world)

    return t0mult


def GetJointDrivesAndJointStates(joint):
    """Get the drive APIs and joint state APIs for a joint.

    Args:
        joint: The joint to get drive and state APIs for.

    Returns:
        A tuple of (drive_apis, joint_state_apis) for the joint.
    """
    if PhysxSchema is None:
        raise RuntimeError("PhysxSchema is not available in this environment")
    driveAPIs = []
    joint_states = []
    if joint.IsA(UsdPhysics.RevoluteJoint):
        driveAPIs.append(UsdPhysics.DriveAPI(joint, "angular"))
        joint_states.append(PhysxSchema.JointStateAPI(joint, "angular"))
    elif joint.IsA(UsdPhysics.PrismaticJoint):
        driveAPIs.append(UsdPhysics.DriveAPI(joint, "linear"))
        joint_states.append(PhysxSchema.JointStateAPI(joint, "linear"))
    else:
        axis = [f"{prefix}{i}" for prefix in ["rot", "trans"] for i in ["X", "Y", "Z"]]
        for axis in axis:
            driveAPI = UsdPhysics.DriveAPI(joint, axis)
            joint_state = PhysxSchema.JointStateAPI(joint, axis)
            if driveAPI:
                driveAPIs.append(driveAPI)
                joint_states.append(joint_state)
    return driveAPIs, joint_states


def GfQuatToVec4d(quat: Gf.Quatd) -> Gf.Vec4d:
    """Convert a quaternion to a 4D vector.

    Args:
        quat: The quaternion to convert.

    Returns:
        A Vec4d with (real, imaginary_x, imaginary_y, imaginary_z) components.
    """
    return Gf.Vec4d(quat.GetReal(), quat.GetImaginary()[0], quat.GetImaginary()[1], quat.GetImaginary()[2])


def GfRotationToVec4d(rot: Gf.Rotation) -> Gf.Vec4d:
    """Convert a rotation to a 4D vector.

    Args:
        rot: The rotation to convert.

    Returns:
        A Vec4d representation of the rotation's quaternion.
    """
    return GfQuatToVec4d(rot.GetQuat())


def get_prismatic_or_revolute_limits(joint_prim: Usd.Prim) -> tuple[float, float]:
    """Get the lower and upper limits for prismatic or revolute joints.

    Args:
        joint_prim: The joint prim to get limits from.

    Returns:
        A tuple containing (lower_limit, upper_limit) or (None, None) if not applicable.
    """
    if joint_prim.IsA(UsdPhysics.RevoluteJoint):
        joint = UsdPhysics.RevoluteJoint(joint_prim)
        return joint.GetLowerLimitAttr().Get(), joint.GetUpperLimitAttr().Get()
    elif joint_prim.IsA(UsdPhysics.PrismaticJoint):
        joint = UsdPhysics.PrismaticJoint(joint_prim)
        return joint.GetLowerLimitAttr().Get(), joint.GetUpperLimitAttr().Get()
    else:
        return None, None


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_001, override=True)
class PhysicsDriveAndJointState(omni.asset_validator.BaseRuleChecker):
    """Validator to check physics driven joints for proper drive and joint state configuration."""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has proper drive and joint state configuration.

        Args:
            prim: The USD prim to validate.
        """
        drives, joint_states = GetJointDrivesAndJointStates(prim)
        if not drives:
            return
        is_mimic = prim.HasAPI(PhysxSchema.PhysxMimicJointAPI)
        stop = True
        if is_mimic:
            for drive, joint_state in zip(drives, joint_states):
                stiffness = drive.GetStiffnessAttr().Get()
                damping = drive.GetDampingAttr().Get()
                if (stiffness and stiffness.Get() != 0.0) or (damping and damping.Get() != 0.0):
                    stop = False
                    break
        if stop:
            return

        for drive, joint_state in zip(drives, joint_states):
            force_attr = drive.GetMaxForceAttr()
            if not force_attr.IsDefined():
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_001,
                    message=f"Drive Max Force is not set on <{prim.GetPath()}>",
                    at=force_attr,
                )
            else:
                max_force = force_attr.Get()
                if max_force <= 0:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_001,
                        message=f"Drive Max Force is zero <{force_attr.GetPath()}>",
                        at=force_attr,
                    )
                if max_force >= float("inf"):
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_001,
                        message=f"Drive Max Force is infinite <{force_attr.GetPath()}>",
                        at=force_attr,
                    )

                drive_target_position = drive.GetTargetPositionAttr()
                drive_target_velocity = drive.GetTargetVelocityAttr()

                joint_state_position = joint_state.GetPositionAttr()
                joint_state_velocity = joint_state.GetVelocityAttr()

                tolerance = 1e-2
                if drive_target_position and joint_state_position:
                    pos_diff = abs(drive_target_position.Get() - joint_state_position.Get())
                    if pos_diff > tolerance:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_001,
                            message=f"Joint state position is very different from drive target position <{drive_target_position.GetPath()}>: difference is {pos_diff}",
                            at=drive_target_position,
                        )

                if drive_target_velocity and joint_state_velocity:
                    vel_diff = abs(drive_target_velocity.Get() - joint_state_velocity.Get())
                    if vel_diff > tolerance:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_001,
                            message=f"Joint state velocity is very different from drive target velocity <{drive_target_velocity.GetPath()}>: difference is {vel_diff}",
                            at=drive_target_velocity,
                        )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_002, override=True)
class JointHasJointStateAPI(omni.asset_validator.BaseRuleChecker):
    """Validates that joints have the JointStateAPI applied.

    This rule checks that all joints (except fixed joints) have the PhysxSchema.JointStateAPI
    applied. The JointStateAPI is required for proper joint state tracking during simulation.
    """

    @classmethod
    def apply_api(cls, _: Usd.Stage, joint_prim: Usd.Prim) -> None:
        """Apply the appropriate JointStateAPI to a joint prim.

        Args:
            stage: The USD stage containing the joint.
            joint_prim: The joint prim to apply the API to.
        """
        actuator_type = None
        spec_stack = joint_prim.GetPrimStack()
        if spec_stack:
            defining_spec = spec_stack[-1]
            layer = defining_spec.layer
            edit_stage = Usd.Stage.Open(layer.identifier)

            prim = edit_stage.GetPrimAtPath(defining_spec.path)

            if prim.IsA(UsdPhysics.PrismaticJoint):
                actuator_type = "linear"
            elif prim.IsA(UsdPhysics.RevoluteJoint):
                actuator_type = "angular"

            if PhysxSchema is None:
                raise RuntimeError("PhysxSchema is not available; cannot apply JointStateAPI fix")
            PhysxSchema.JointStateAPI.Apply(prim, actuator_type)
            edit_stage.Save()

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has the required JointStateAPI applied.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check JointStateAPI")
            return
        if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
            return

        actuator_type = None
        if prim.IsA(UsdPhysics.PrismaticJoint):
            actuator_type = "linear"
        elif prim.IsA(UsdPhysics.RevoluteJoint):
            actuator_type = "angular"
        # check if the joint api has a joint state api
        if actuator_type is None:
            return
        if not PhysxSchema.JointStateAPI(prim, actuator_type):
            self._AddFailedCheck(
                requirement=DrivenJointsCapReq.DJ_002,
                message=f"{prim.GetPath()} Has no Joint State API",
                at=prim,
                suggestion=omni.asset_validator.Suggestion(
                    message="Apply Joint State API", callable=self.apply_api
                ),
            )
        else:
            return


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_003, override=True)
class JointHasCorrectTransformAndState(omni.asset_validator.BaseRuleChecker):
    """Validates that joint transforms and states are consistent with the connected bodies.

    This rule checks that the joint's transform and state values correctly define the
    relationship between the connected bodies. Inconsistencies can cause incorrect
    joint behavior during simulation.
    """

    joint_axis_map = {
        "X": Gf.Vec3d(1, 0, 0),
        "Y": Gf.Vec3d(0, 1, 0),
        "Z": Gf.Vec3d(0, 0, 1),
    }

    def CheckPrim(self, prim: Usd.Prim) -> None:
        # print(f"JointHasCorrectTransform: {prim.GetPath()}")
        joint = UsdPhysics.Joint(prim)

        if not joint:
            return

        if not (
            prim.IsA(UsdPhysics.RevoluteJoint)
            # or prim.IsA(UsdPhysics.SphericalJoint)
            or prim.IsA(UsdPhysics.PrismaticJoint)
            # or prim.IsA(UsdPhysics.FixedJoint)
        ):
            return

        stage = prim.GetStage()

        # Check if the bodies are valid
        b0paths = joint.GetBody0Rel().GetTargets()
        b1paths = joint.GetBody1Rel().GetTargets()

        if len(b0paths):
            if not stage.GetPrimAtPath(b0paths[0]).IsValid():
                return
        else:
            return

        if len(b1paths):
            if not stage.GetPrimAtPath(b1paths[0]).IsValid():
                return
        else:
            return

        # Get the expected transform
        cache = UsdGeom.XformCache()
        expected_tm_0 = get_world_body_transform(stage, cache, joint, False)
        expected_tm_1 = get_world_body_transform(stage, cache, joint, True)

        # Compute the joint state offset transform
        joint_state_transform = Gf.Transform()
        if prim.IsA(UsdPhysics.RevoluteJoint):
            jointState = PhysxSchema.JointStateAPI(prim, "angular")
            if jointState:
                revolute_joint = UsdPhysics.RevoluteJoint(prim)
                value = jointState.GetPositionAttr().Get()
                axis = revolute_joint.GetAxisAttr().Get()
                joint_state_transform.SetRotation(
                    Gf.Rotation(Gf.Vec3d(JointHasCorrectTransformAndState.joint_axis_map[str(axis)]), value)
                )
        if prim.IsA(UsdPhysics.PrismaticJoint):
            jointState = PhysxSchema.JointStateAPI(prim, "linear")
            if jointState:
                prismatic_joint = UsdPhysics.PrismaticJoint(prim)
                value = jointState.GetPositionAttr().Get()
                axis = prismatic_joint.GetAxisAttr().Get()
                joint_state_transform.SetTranslation(
                    Gf.Vec3d(JointHasCorrectTransformAndState.joint_axis_map[str(axis)]) * value
                )

        joint_state_pos_0 = joint_state_transform * expected_tm_0

        expected_state_pos_0 = joint_state_pos_0.GetTranslation()
        expected_pos_0 = expected_tm_0.GetTranslation()
        expected_pos_1 = expected_tm_1.GetTranslation()

        if not Gf.IsClose(expected_state_pos_0, expected_pos_1, 1e-4):
            if not Gf.IsClose(expected_pos_0, expected_pos_1, 1e-4):
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_003,
                    message=f"Joint {prim.GetPath()} position not well-defined ({(expected_pos_0 - expected_pos_1).GetLength()}). From body 0: {expected_pos_0}, from body 1: {expected_pos_1}",
                    at=prim,
                )
            else:
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_003,
                    message=f"Joint {prim.GetPath()} state not matching robot pose({(expected_state_pos_0 - expected_pos_1).GetLength()}). From body 0: {expected_state_pos_0}, from body 1: {expected_pos_1}",
                    at=prim,
                )

        # Check if the orientation is as expected
        expected_state_rot_0 = joint_state_pos_0.GetRotation()
        expected_rot_0 = expected_tm_0.GetRotation()
        expected_rot_1 = expected_tm_1.GetRotation()
        expected_state_rot0_as_vec4d = GfQuatToVec4d(expected_state_rot_0.GetQuat())
        expected_rot0_as_vec4d = GfQuatToVec4d(expected_rot_0.GetQuat().GetNormalized())
        expected_rot1_as_vec4d = GfQuatToVec4d(expected_rot_1.GetQuat().GetNormalized())

        if not Gf.IsClose(expected_state_rot0_as_vec4d, expected_rot1_as_vec4d, 1e-3):
            if not Gf.IsClose(expected_rot0_as_vec4d, expected_rot1_as_vec4d, 1e-3):
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_003,
                    message=f"Joint {prim.GetPath()} Rotation not well defined ({(expected_state_rot0_as_vec4d - expected_rot1_as_vec4d).GetLength()}), From body 0: {expected_rot_0}, From body 1: {expected_rot_1}",
                    at=prim,
                )
            else:
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_003,
                    message=f"Joint {prim.GetPath()} state not matching robot pose ({(expected_rot0_as_vec4d - expected_rot1_as_vec4d).GetLength()}). From body 0: {expected_state_rot_0}, from body 1: {expected_rot_1}",
                    at=prim,
                )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_004, override=True)
class PhysicsJointHasDriveOrMimicAPI(omni.asset_validator.BaseRuleChecker):
    """Validates that joints have a drive or mimic API.

    This rule ensures that all joints (except fixed joints) have either a drive API
    or a mimic API configured. Joints with both APIs are checked to ensure proper
    configuration where drive stiffness and damping are set to 0.0 when mimic is used.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has proper drive or mimic API configuration.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check drive or mimic API")
            return
        if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
            return
        drives, joint_states = GetJointDrivesAndJointStates(prim)
        has_mimic = prim.HasAPI(PhysxSchema.PhysxMimicJointAPI)
        exclude_from_articulation = UsdPhysics.Joint(prim).GetExcludeFromArticulationAttr().Get()
        if not drives and not has_mimic and not exclude_from_articulation:
            self._AddFailedCheck(
                requirement=DrivenJointsCapReq.DJ_004,
                message=f"Joint {prim.GetPath()} has no drive or mimic API",
                at=prim,
            )
        if drives and has_mimic:
            # Check if stiffness and damping are set to 0.0
            for drive in drives:
                stiffness = drive.GetStiffnessAttr().Get()
                damping = drive.GetDampingAttr().Get()
                if (stiffness and stiffness.Get() != 0.0) or (damping and damping.Get() != 0.0):
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_004,
                        message=f"Joint {prim.GetPath()} has both drive and mimic API",
                        at=prim,
                    )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_005, override=True)
class PhysicsJointMaxVelocity(omni.asset_validator.BaseRuleChecker):
    """Validates that joints have a positive max velocity set.

    This rule checks that joints with the PhysxJointAPI have a defined and positive
    max joint velocity, which is required for proper joint simulation.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has proper max joint velocity configuration.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check max joint velocity")
            return
        if prim.HasAPI(PhysxSchema.PhysxJointAPI):
            joint = PhysxSchema.PhysxJointAPI(prim)
            attr = joint.GetMaxJointVelocityAttr()
            if not attr.IsDefined():
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_005,
                    message=f"Max joint velocity is not set on <{prim.GetPath()}>",
                    at=prim,
                )
            else:
                max_joint_velocity = attr.Get()
                if max_joint_velocity <= 0:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_005,
                        message=f"Max joint velocity is zero <{attr.GetPath()}>",
                        at=attr,
                    )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_006, override=True)
class DriveJointValueReasonable(omni.asset_validator.BaseRuleChecker):
    """Validates that joint drive stiffness values are within reasonable ranges.

    This rule checks that joint drive stiffness values are within defined minimum and
    maximum limits to ensure stable simulation behavior.
    """

    DRIVE_STIFFNESS_MIN = 0.0
    DRIVE_STIFFNESS_MAX = 1000000.0  # 1e6 stiffness
    NATURAL_FREQUENCY_MIN = 0.0
    NATURAL_FREQUENCY_MAX = 500.0  # 500 Hz - warning threshold.

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has reasonable drive stiffness values.

        Args:
            prim: The USD prim to validate.
        """
        drives, joint_states = GetJointDrivesAndJointStates(prim)
        is_mimic = prim.HasAPI(PhysxSchema.PhysxMimicJointAPI)
        for drive in drives:
            stiffness = drive.GetStiffnessAttr().Get()
            if not stiffness and not is_mimic:
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_006,
                    message=f"Drive stiffness is not set on <{drive.GetPath()}>",
                    at=drive.GetStiffnessAttr(),
                )
                continue
            elif is_mimic:
                damping = drive.GetDampingAttr().Get()
                if damping:
                    if damping.Get() != 0.0:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_006,
                            message=f"joint is mimic but has damping set <{drive.GetPath()}>",
                            at=drive.GetDampingAttr(),
                        )
                if stiffness:
                    if stiffness.Get() != 0.0:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_006,
                            message=f"joint is mimic but has stiffness set <{drive.GetPath()}>",
                            at=drive.GetStiffnessAttr(),
                        )
            elif stiffness < self.DRIVE_STIFFNESS_MIN or stiffness > self.DRIVE_STIFFNESS_MAX:
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_006,
                    message=f"Drive stiffness is out of range <{drive.GetPath()}>: {stiffness}",
                    at=prim,
                )
            continue
            # TODO: Work in progress for natural frequency


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_007, override=True)
class MimicAPICheck(omni.asset_validator.BaseRuleChecker):
    """Validates proper configuration of mimic joint APIs.

    This rule checks that mimic joints have proper reference joints, gear ratios,
    natural frequencies, damping ratios, and compatible joint limits.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim with mimic API is properly configured.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check mimic joint API")
            return
        if not prim.HasAPI(PhysxSchema.PhysxMimicJointAPI):
            return
        else:
            applied_schema = prim.GetAppliedSchemas()
            list_of_mimic_apis = []
            for schema in applied_schema:
                if schema.startswith("PhysxMimicJointAPI"):
                    list_of_mimic_apis.append(schema[19:])
            for axis in list_of_mimic_apis:
                match axis:
                    case "rotX":
                        mimic_api = PhysxSchema.PhysxMimicJointAPI(prim, UsdPhysics.Tokens.rotX)

                    case "rotY":
                        mimic_api = PhysxSchema.PhysxMimicJointAPI(prim, UsdPhysics.Tokens.rotY)

                    case "rotZ":
                        mimic_api = PhysxSchema.PhysxMimicJointAPI(prim, UsdPhysics.Tokens.rotZ)
                    case _:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_007,
                            message=f"Joint {prim.GetPath()} has unknown mimic axis: {axis}, aborting checks",
                            at=prim,
                        )
                        return

                # For the mimic API, perform checks

                # reference joint check
                reference_joint = mimic_api.GetReferenceJointRel().GetTargets()
                if not reference_joint or len(reference_joint) > 1:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has incorrect number of reference joints, expected: 1, actual: {len(reference_joint)}",
                        at=prim,
                    )

                # self value checks
                gear_ratio = mimic_api.GetGearingAttr().Get()
                natural_frequency = prim.GetAttribute(f"physxMimicJoint:{axis}:naturalFrequency").Get()
                damping_ratio = prim.GetAttribute(f"physxMimicJoint:{axis}:dampingRatio").Get()

                if gear_ratio is None:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has no gear ratio",
                        at=prim,
                    )

                if natural_frequency is None:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has no natural frequency",
                        at=prim,
                    )

                if damping_ratio is None:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has no damping ratio",
                        at=prim,
                    )

                if gear_ratio == 0:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has gear ratio == 0",
                        at=prim,
                    )

                if natural_frequency == 0:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has natural frequency == 0",
                        at=prim,
                    )

                if damping_ratio == 0:
                    self._AddInfo(message=f"Joint {prim.GetPath()} has damping ratio == 0", at=prim)

                # limit checks
                self_joint_lower_limit, self_joint_upper_limit = get_prismatic_or_revolute_limits(prim)
                if self_joint_lower_limit is None or self_joint_upper_limit is None:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has no limits",
                        at=prim,
                    )
                    return

                # obtain the limits from the reference joint
                stage = prim.GetStage()
                reference_joint_prim = stage.GetPrimAtPath(reference_joint[0])
                reference_joint_lower_limit, reference_joint_upper_limit = get_prismatic_or_revolute_limits(
                    reference_joint_prim
                )
                if reference_joint_lower_limit is None or reference_joint_upper_limit is None:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Joint {prim.GetPath()} has no limits",
                        at=prim,
                    )
                    return

                # ensure the mimic joint and the reference joint are not excluded from articulation
                if reference_joint_prim.GetAttribute("physics:excludeFromArticulation").Get():
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Mimic joint {prim.GetPath()} has a reference joint {reference_joint_prim.GetPath()} that is excluded from articulation.. The mimic joint reference joint cannot be excluded from articulation.",
                        at=prim,
                    )
                    return
                if prim.GetAttribute("physics:excludeFromArticulation").Get():
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_007,
                        message=f"Mimic joint {prim.GetPath()} is excluded from articulation. The mimic joint cannot be excluded from articulation.",
                        at=prim,
                    )
                    return

                # check joint limits
                # if gear_ratio < 0:
                # We want:
                # - reference_lower * gear_ratio > self_lower
                # - self_upper > reference_upper * gear_ratio
                # else:
                # We want:
                # - reference_lower * gear_ratio < self_upper
                # - self_lower < reference_upper * gear_ratio
                if gear_ratio < 0:
                    if not reference_joint_lower_limit * gear_ratio > self_joint_lower_limit:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_007,
                            message=f"Joint {prim.GetPath()}'s lower limit ({self_joint_lower_limit}) should be > reference joint limits * gear ratio({reference_joint_lower_limit * gear_ratio})",
                            at=prim,
                        )

                    if not self_joint_upper_limit > reference_joint_upper_limit * gear_ratio:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_007,
                            message=f"Joint {prim.GetPath()}'s upper limit ({self_joint_upper_limit}) should be < reference joint limits * gear ratio({reference_joint_upper_limit * gear_ratio})",
                            at=prim,
                        )
                else:
                    if not reference_joint_lower_limit * gear_ratio < self_joint_upper_limit:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_007,
                            message=f"Joint {prim.GetPath()}'s lower limit ({self_joint_upper_limit}) should be > reference joint limits * gear ratio({reference_joint_lower_limit * gear_ratio})",
                            at=prim,
                        )

                    if not self_joint_lower_limit < reference_joint_upper_limit * gear_ratio:
                        self._AddFailedCheck(
                            requirement=DrivenJointsCapReq.DJ_007,
                            message=f"Joint {prim.GetPath()}'s upper limit ({self_joint_lower_limit}) should be < reference joint limits * gear ratio({reference_joint_upper_limit * gear_ratio})",
                            at=prim,
                        )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_008, override=True)
class JointsExist(omni.asset_validator.BaseRuleChecker):
    """Validates that robot assets contain at least one joint.

    This rule checks that robot assets have at least one prim with the JointAPI
    applied, which is typically required for articulated robots.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        for prim in stage.Traverse():
            # JW: lazy load the schema as we dont have it and its breaking workspace
            from usd.schema.isaac import robot_schema

            if prim.HasAPI(robot_schema.Classes.JOINT_API.value):
                return
        self._AddFailedCheck(
            requirement=DrivenJointsCapReq.DJ_008,
            message=f"No joints found in robot asset <{stage.GetRootLayer().realPath}>",
            at=stage,
        )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_009, override=True)
class LinksExist(omni.asset_validator.BaseRuleChecker):
    """Validates that robot assets contain at least one link.

    This rule checks that robot assets have at least one prim with the LinkAPI
    applied, which is typically required for articulated robots.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        for prim in stage.Traverse():
            # JW: lazy load the schema as we dont have it and its breaking workspace
            from usd.schema.isaac import robot_schema

            if prim.HasAPI(robot_schema.Classes.LINK_API.value):
                return
        self._AddFailedCheck(
            requirement=DrivenJointsCapReq.DJ_009,
            message=f"No links found in robot asset <{stage.GetRootLayer().realPath}>",
            at=stage,
        )


def is_relationship_prepended(relationship: Usd.Relationship) -> bool:
    """Return True when the relationship's targets are authored as prepended (non-empty prependedItems) in the strongest opinion."""
    prim = relationship.GetPrim()
    rel_name = relationship.GetName()
    for prim_spec in prim.GetPrimStack():
        rel_spec = prim_spec.relationships.get(rel_name) if hasattr(prim_spec, "relationships") else None
        if rel_spec is None:
            continue
        path_list = getattr(rel_spec, "targetPathList", None)
        if path_list is None:
            return False
        prepended = getattr(path_list, "prependedItems", None)
        return bool(prepended)
    return False


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_010, override=True)
class CheckRobotRelationships(omni.asset_validator.BaseRuleChecker):
    """Validates that robot relationships are properly defined and prepended.

    This rule checks that robot assets have the required robotLinks and robotJoints
    relationships defined and that they are prepended for proper composition.
    """

    try:
        # JW: lazy load the schema as we dont have it and its breaking workspace
        from usd.schema.isaac import robot_schema
    except ImportError:
        robot_schema = None

    @classmethod
    def create_link_relationship(cls, stage, prim):
        """Create the robotLinks relationship on a prim.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim to create the relationship on.
        """
        relationship = prim.CreateRelationship(robot_schema.Relations.ROBOT_LINKS.name)

    @classmethod
    def create_joint_relationship(cls, stage, prim):
        """Create the robotJoints relationship on a prim.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim to create the relationship on.
        """
        relationship = prim.CreateRelationship(robot_schema.Relations.ROBOT_JOINTS.name)

    @classmethod
    def make_joint_relationship_prepended(cls, stage, prim):
        """Make the robotJoints relationship prepended for composition.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim with the relationship to modify.
        """
        relationship = prim.GetRelationship(robot_schema.Relations.ROBOT_JOINTS.name)
        make_relationship_prepended(relationship)

    @classmethod
    def make_link_relationship_prepended(cls, stage, prim):
        """Make the robotLinks relationship prepended for composition.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim with the relationship to modify.
        """
        relationship = prim.GetRelationship(robot_schema.Relations.ROBOT_LINKS.name)
        make_relationship_prepended(relationship)

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check if robot relationships are properly configured.

        Args:
            stage: The USD stage to validate.
        """
        prim = stage.GetDefaultPrim()
        if not prim:
            self._AddFailedCheck(
                requirement=DrivenJointsCapReq.DJ_010,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is not set",
                at=stage,
            )
            return

        # JW: lazy load the schema as we dont have it and its breaking workspace
        from usd.schema.isaac import robot_schema

        if prim.HasAPI(robot_schema.Classes.ROBOT_API.value):
            relationship_name_list = [robot_schema.Relations.ROBOT_LINKS.name, robot_schema.Relations.ROBOT_JOINTS.name]
            fix_methods = [self.create_link_relationship, self.create_joint_relationship]
            make_methods = [self.make_link_relationship_prepended, self.make_joint_relationship_prepended]
            for relationship_name, fix_method, make_method in zip(relationship_name_list, fix_methods, make_methods):
                relationship = prim.GetRelationship(relationship_name)
                if not relationship:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_010,
                        message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a {relationship_name} relationship",
                        at=prim,
                        suggestion=omni.asset_validator.Suggestion(
                            message="Create relationship", callable=fix_method, at=AuthoringLayers(prim)
                        ),
                    )
                    continue

                # Check if the relationship is prepended
                is_prepended = is_relationship_prepended(relationship)
                if not is_prepended:
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_010,
                        message=f"Relationship {relationship_name} is not prepended",
                        at=prim,
                        suggestion=omni.asset_validator.Suggestion(
                            message="Make relationship prepended", callable=make_method
                        ),
                    )


@omni.asset_validator.register_rule("PhysicsDrivenJoints")
@omni.asset_validator.register_requirements(DrivenJointsCapReq.DJ_011, override=True)
class ArticulationNoLoopsOrMultiJoint(omni.asset_validator.BaseRuleChecker):
    """Validates that the articulation has no loops and at most one joint between any two bodies.

    Only joints that participate in the articulation (excludeFromArticulation is not true)
    are considered. Joints with physics:excludeFromArticulation = true are skipped,
    so a loop is allowed if one of its joints is excluded from the articulation.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check that the body-joint graph has no cycles and at most one joint per body pair.

        Args:
            stage: The USD stage to validate.
        """
        pair_to_joints = defaultdict(list)
        adjacency = defaultdict(list)
        joint_to_bodies = {}

        for prim in stage.Traverse():
            if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
                continue
            joint = UsdPhysics.Joint(prim)
            if joint.GetExcludeFromArticulationAttr().Get():
                continue
            b0_targets = joint.GetBody0Rel().GetTargets()
            b1_targets = joint.GetBody1Rel().GetTargets()
            if not b0_targets or not b1_targets:
                continue
            path0 = b0_targets[0]
            path1 = b1_targets[0]
            if not stage.GetPrimAtPath(path0).IsValid() or not stage.GetPrimAtPath(path1).IsValid():
                continue
            key = (min(path0, path1), max(path0, path1))
            pair_to_joints[key].append(prim)
            joint_to_bodies[prim] = (path0, path1)

        for path0, path1 in pair_to_joints:
            adjacency[path0].append(path1)
            adjacency[path1].append(path0)

        for key, joints in pair_to_joints.items():
            if len(joints) > 1:
                joint_paths = ", ".join(str(p.GetPath()) for p in joints)
                self._AddFailedCheck(
                    requirement=DrivenJointsCapReq.DJ_011,
                    message=f"Multiple joints connect the same body pair {key[0]} -- {key[1]}: {joint_paths}\nOnly one joint per body pair is allowed, remove the extra joints.",
                    at=joints[0],
                )

        visited = set()

        def dfs_find_cycle(node, parent, stack):
            visited.add(node)
            stack.append(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    cycle = dfs_find_cycle(neighbor, node, stack)
                    if cycle is not None:
                        return cycle
                elif neighbor != parent:
                    idx = stack.index(neighbor)
                    return stack[idx:] + [neighbor]
            stack.pop()
            return None

        path_to_joint = {}
        for prim, (p0, p1) in joint_to_bodies.items():
            path_to_joint[(min(p0, p1), max(p0, p1))] = prim

        for body in adjacency:
            if body not in visited:
                stack = []
                cycle_bodies = dfs_find_cycle(body, None, stack)
                if cycle_bodies is not None:
                    cycle_joints = []
                    for i in range(len(cycle_bodies) - 1):
                        a, b = cycle_bodies[i], cycle_bodies[i + 1]
                        k = (min(a, b), max(a, b))
                        if k in path_to_joint:
                            cycle_joints.append(path_to_joint[k].GetPath())
                    self._AddFailedCheck(
                        requirement=DrivenJointsCapReq.DJ_011,
                        message=f"Articulation has a loop: bodies {cycle_bodies}; joints involved: {cycle_joints}\nEnable excludeFromArticulation on one of the joints in the loop to allow for loops.",
                        at=path_to_joint[
                            (min(cycle_bodies[0], cycle_bodies[1]), max(cycle_bodies[0], cycle_bodies[1]))
                        ],
                    )

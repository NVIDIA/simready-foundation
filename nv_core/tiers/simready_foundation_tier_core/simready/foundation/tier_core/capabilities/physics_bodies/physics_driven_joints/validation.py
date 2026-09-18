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

import math
from collections import defaultdict

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Usd, UsdGeom, UsdPhysics

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None

_NEWTON_JOINT_API = "NewtonJointAPI"
_NEWTON_MIMIC_API = "NewtonMimicAPI"
_NEWTON_MIMIC_JOINT_REL = "newton:mimicJoint"
_NEWTON_MIMIC_ENABLED_ATTR = "newton:mimicEnabled"
_DRIVE_AXES = ("angular", "linear", "rotX", "rotY", "rotZ", "transX", "transY", "transZ")
# PhysxMimicJointAPI multiple-apply instance names. Rotational and translational
# tokens are accepted, plus the short X/Y/Z spelling used by prismatic couplings.
_MIMIC_AXES = frozenset(
    {
        "rotX",
        "rotY",
        "rotZ",
        "transX",
        "transY",
        "transZ",
        "X",
        "Y",
        "Z",
    }
)
# NewtonJointAPI broadcasts scalar attributes uniformly to every DOF of the joint,
# so the Newton joint tuning attributes are not axis-namespaced.
_NEWTON_JOINT_NON_NEGATIVE_ATTRS = (
    "newton:armature",
    "newton:damping",
    "newton:friction",
)
# limitStiffness/limitDamping accept the -inf (and, for stiffness, +inf) sentinels that
# defer to the engine default or request a hard limit.
_NEWTON_JOINT_LIMIT_SPRING_ATTRS = (
    "newton:limitStiffness",
    "newton:limitDamping",
)
_NEWTON_JOINT_VELOCITY_LIMIT_ATTR = "newton:velocityLimit"
_NEWTON_JOINT_ATTRS = (
    _NEWTON_JOINT_NON_NEGATIVE_ATTRS + _NEWTON_JOINT_LIMIT_SPRING_ATTRS + (_NEWTON_JOINT_VELOCITY_LIMIT_ATTR,)
)
# Newton actuator schema family (newton-usd-schemas). An actuator is a typed prim that
# targets a joint via ``newton:targets`` and carries one control-law API.
_NEWTON_ACTUATOR_TYPE = "NewtonActuator"
_NEWTON_ACTUATOR_CONTROL_APIS = (
    "NewtonActuatorControlBaseAPI",
    "NewtonPDControlAPI",
    "NewtonPIDControlAPI",
    "NewtonNeuralControlAPI",
)
_NEWTON_ACTUATOR_NON_NEGATIVE_ATTRS = (
    "newton:kp",
    "newton:kd",
    "newton:ki",
    "newton:integralMax",
    "newton:maxEffort",
    "newton:maxMotorEffort",
    "newton:saturationEffort",
)
_NEWTON_ACTUATOR_FINITE_ATTRS = ("newton:constEffort",)
_MUJOCO_JOINT_API = "MjcJointAPI"
_MUJOCO_ACTUATOR_TYPE = "MjcActuator"
_MUJOCO_JOINT_NON_NEGATIVE_ATTRS = ("mjc:armature",)
_MUJOCO_ACTUATOR_ARRAY_ATTRS = ("mjc:gainPrm", "mjc:biasPrm")
_MUJOCO_ACTUATOR_RANGE_ATTRS = (
    ("mjc:ctrlRange:min", "mjc:ctrlRange:max", "control range"),
    ("mjc:forceRange:min", "mjc:forceRange:max", "force range"),
)


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


def _as_finite_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _has_authored_attr(prim: Usd.Prim, attr_name: str) -> bool:
    attr = prim.GetAttribute(attr_name)
    return attr.IsValid() and attr.HasAuthoredValueOpinion()


def _is_non_fixed_articulation_joint(prim: Usd.Prim) -> bool:
    if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
        return False
    joint = UsdPhysics.Joint(prim)
    return not bool(joint.GetExcludeFromArticulationAttr().Get())


def _is_mujoco_actuator(prim: Usd.Prim) -> bool:
    return prim.GetTypeName() == _MUJOCO_ACTUATOR_TYPE


def _is_numeric_sequence(value) -> bool:
    if value is None or isinstance(value, (str, bytes)):
        return False
    try:
        values = list(value)
    except TypeError:
        return False
    return bool(values) and all(_as_finite_float(item) is not None for item in values)


def _joint_drive_axes(prim: Usd.Prim) -> tuple[str, ...]:
    if prim.IsA(UsdPhysics.RevoluteJoint):
        return ("angular",)
    if prim.IsA(UsdPhysics.PrismaticJoint):
        return ("linear",)
    return _DRIVE_AXES


def _has_drive_api(prim: Usd.Prim, axis: str) -> bool:
    return _has_applied_api_schema(prim, f"PhysicsDriveAPI:{axis}")


def _is_newton_mimic_follower(prim: Usd.Prim) -> bool:
    """Return True if the joint is coupled to a leader joint by NewtonMimicAPI.

    A mimic follower is actuated indirectly through the mimic constraint, so it
    does not require its own ``PhysicsDriveAPI`` or ``NewtonActuator`` -- this
    mirrors the Standard/PhysX "drive or mimic" contract (DJ.004). The coupling
    must be enabled (``newton:mimicEnabled`` is on unless explicitly authored
    False) and author a ``newton:mimicJoint`` leader target.
    """
    if _NEWTON_MIMIC_API not in _applied_api_schemas(prim):
        return False
    enabled_attr = prim.GetAttribute(_NEWTON_MIMIC_ENABLED_ATTR)
    if enabled_attr.IsValid() and enabled_attr.HasAuthoredValueOpinion() and enabled_attr.Get() is False:
        return False
    rel = prim.GetRelationship(_NEWTON_MIMIC_JOINT_REL)
    return bool(rel and rel.GetTargets())


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
    # Only collect drives that are actually applied (HasAPI guard). Without this
    # guard `UsdPhysics.DriveAPI(joint, axis)` returns a truthy wrapper even when
    # the schema is not applied, which makes `drives` never empty and neuters the
    # "has no drive or mimic API" check in PhysicsJointHasDriveOrMimicAPI.
    if joint.IsA(UsdPhysics.RevoluteJoint):
        if joint.HasAPI(UsdPhysics.DriveAPI, "angular"):
            driveAPIs.append(UsdPhysics.DriveAPI(joint, "angular"))
            joint_states.append(PhysxSchema.JointStateAPI(joint, "angular"))
    elif joint.IsA(UsdPhysics.PrismaticJoint):
        if joint.HasAPI(UsdPhysics.DriveAPI, "linear"):
            driveAPIs.append(UsdPhysics.DriveAPI(joint, "linear"))
            joint_states.append(PhysxSchema.JointStateAPI(joint, "linear"))
    else:
        for axis in (f"{prefix}{i}" for prefix in ("rot", "trans") for i in ("X", "Y", "Z")):
            if joint.HasAPI(UsdPhysics.DriveAPI, axis):
                driveAPIs.append(UsdPhysics.DriveAPI(joint, axis))
                joint_states.append(PhysxSchema.JointStateAPI(joint, axis))
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


def _rotations_match_orientation(qa: Gf.Quatd, qb: Gf.Quatd, tol: float) -> bool:
    """Return True if two quaternions represent the same orientation (double-cover safe).

    ``q`` and ``-q`` are treated as the same rotation. Uses ``abs(dot) >= 1.0 - tol``.
    Component-wise ``Gf.IsClose`` on the quaternion vec4d would false-fail on the
    antipodal representation of an identical orientation.

    Args:
        qa: First quaternion to compare.
        qb: Second quaternion to compare.
        tol: Allowed tolerance from an absolute dot product of 1.0.

    Returns:
        True if the quaternions represent the same orientation, False otherwise.
    """
    qa_n = qa.GetNormalized()
    qb_n = qb.GetNormalized()
    dot = qa_n.GetReal() * qb_n.GetReal() + Gf.Dot(qa_n.GetImaginary(), qb_n.GetImaginary())
    return abs(dot) >= 1.0 - tol


def _rotation_error_magnitude(qa: Gf.Quatd, qb: Gf.Quatd) -> float:
    """Return the orientation mismatch magnitude between two quaternions.

    Args:
        qa: First quaternion to compare.
        qb: Second quaternion to compare.

    Returns:
        The value ``1.0 - abs(dot)`` for normalized quaternions.
    """
    qa_n = qa.GetNormalized()
    qb_n = qb.GetNormalized()
    dot = qa_n.GetReal() * qb_n.GetReal() + Gf.Dot(qa_n.GetImaginary(), qb_n.GetImaginary())
    return 1.0 - abs(dot)


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


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.NEWTON_DJ_001, override=True)
class NewtonJointDriveAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates Newton driven joints using standard UsdPhysics DriveAPI schemas."""

    NEWTON_JOINT_DRIVE_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.NEWTON_DJ_001

    def _validate_authored_number(
        self,
        prim: Usd.Prim,
        attr,
        axis: str,
        description: str,
        *,
        positive: bool = False,
        non_negative: bool = False,
        required: bool = False,
    ) -> None:
        if not attr.IsDefined() or not attr.HasAuthoredValueOpinion():
            if required:
                self._AddFailedCheck(
                    requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                    message=f"Newton drive '{axis}' on joint '{prim.GetPath()}' must author {description}.",
                    at=prim,
                )
            return

        value = attr.Get()
        numeric_value = _as_finite_float(value)
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=f"Newton drive '{axis}' on joint '{prim.GetPath()}' has a non-finite {description}.",
                at=attr,
            )
            return
        if positive and numeric_value <= 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=f"Newton drive '{axis}' on joint '{prim.GetPath()}' must have positive {description}.",
                at=attr,
            )
        if non_negative and numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=f"Newton drive '{axis}' on joint '{prim.GetPath()}' must have non-negative {description}.",
                at=attr,
            )

    def _actuator_target_joints(self, stage: Usd.Stage) -> set[str]:
        cache = getattr(self, "_actuator_target_cache", None)
        if cache is not None and cache[0] is stage:
            return cache[1]
        targets: set[str] = set()
        for prim in stage.Traverse():
            if prim.GetTypeName() != _NEWTON_ACTUATOR_TYPE:
                continue
            rel = prim.GetRelationship("newton:targets")
            if not rel:
                continue
            for target in rel.GetTargets():
                targets.add(str(target))
        self._actuator_target_cache = (stage, targets)
        return targets

    def _validate_actuator_number(self, prim: Usd.Prim, attr_name: str, *, non_negative: bool = False) -> None:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return
        numeric_value = _as_finite_float(attr.Get())
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=f"NewtonActuator attribute '{attr_name}' on '{prim.GetPath()}' must be a finite number.",
                at=attr,
            )
            return
        if non_negative and numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=f"NewtonActuator attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=attr,
            )

    def _validate_newton_actuator(self, prim: Usd.Prim) -> None:
        stage = prim.GetStage()
        rel = prim.GetRelationship("newton:targets")
        targets = rel.GetTargets() if rel else []
        if not targets:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=(
                    f"NewtonActuator '{prim.GetPath()}' must author a 'newton:targets' relationship "
                    "pointing at a PhysicsRevoluteJoint or PhysicsPrismaticJoint."
                ),
                at=prim,
            )
        else:
            target_prim = stage.GetPrimAtPath(targets[0])
            if not target_prim.IsValid() or not (
                target_prim.IsA(UsdPhysics.RevoluteJoint) or target_prim.IsA(UsdPhysics.PrismaticJoint)
            ):
                self._AddFailedCheck(
                    requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                    message=(
                        f"NewtonActuator '{prim.GetPath()}' targets '{targets[0]}', which is not a "
                        "PhysicsRevoluteJoint or PhysicsPrismaticJoint."
                    ),
                    at=prim,
                )

        applied_schemas = _applied_api_schemas(prim)
        if not any(name in applied_schemas for name in _NEWTON_ACTUATOR_CONTROL_APIS):
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                message=(
                    f"NewtonActuator '{prim.GetPath()}' must apply exactly one control-law API "
                    "(NewtonPDControlAPI, NewtonPIDControlAPI, or NewtonNeuralControlAPI)."
                ),
                at=prim,
            )

        for attr_name in _NEWTON_ACTUATOR_NON_NEGATIVE_ATTRS:
            self._validate_actuator_number(prim, attr_name, non_negative=True)
        for attr_name in _NEWTON_ACTUATOR_FINITE_ATTRS:
            self._validate_actuator_number(prim, attr_name)

        delay_attr = prim.GetAttribute("newton:delaySteps")
        if delay_attr.IsValid() and delay_attr.HasAuthoredValueOpinion():
            delay_value = delay_attr.Get()
            if isinstance(delay_value, bool) or not isinstance(delay_value, int) or delay_value < 0:
                self._AddFailedCheck(
                    requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                    message=f"NewtonActuator '{prim.GetPath()}' 'newton:delaySteps' must be a non-negative integer.",
                    at=delay_attr,
                )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.GetTypeName() == _NEWTON_ACTUATOR_TYPE:
            self._validate_newton_actuator(prim)
            return

        if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
            return

        joint = UsdPhysics.Joint(prim)
        exclude_from_articulation = joint.GetExcludeFromArticulationAttr().Get()
        drive_axes = tuple(axis for axis in _joint_drive_axes(prim) if _has_drive_api(prim, axis))
        if not drive_axes:
            if (
                not exclude_from_articulation
                and str(prim.GetPath()) not in self._actuator_target_joints(prim.GetStage())
                and not _is_newton_mimic_follower(prim)
            ):
                self._AddFailedCheck(
                    requirement=self.NEWTON_JOINT_DRIVE_REQUIREMENT,
                    message=(
                        f"Newton joint '{prim.GetPath()}' has no PhysicsDriveAPI applied, is not targeted by a "
                        "NewtonActuator, and is not coupled to a leader joint by NewtonMimicAPI. Apply a "
                        "PhysicsDriveAPI:<axis> schema, add a NewtonActuator that targets the joint, couple it to a "
                        "leader with NewtonMimicAPI, or exclude the joint from articulation."
                    ),
                    at=prim,
                )
            return

        for axis in drive_axes:
            drive = UsdPhysics.DriveAPI(prim, axis)
            self._validate_authored_number(
                prim,
                drive.GetMaxForceAttr(),
                axis,
                "drive maxForce",
                positive=True,
                required=True,
            )
            self._validate_authored_number(
                prim,
                drive.GetStiffnessAttr(),
                axis,
                "drive stiffness",
                non_negative=True,
            )
            self._validate_authored_number(
                prim,
                drive.GetDampingAttr(),
                axis,
                "drive damping",
                non_negative=True,
            )
            self._validate_authored_number(
                prim,
                drive.GetTargetPositionAttr(),
                axis,
                "drive targetPosition",
            )
            self._validate_authored_number(
                prim,
                drive.GetTargetVelocityAttr(),
                axis,
                "drive targetVelocity",
            )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.NEWTON_DJ_002, override=True)
class NewtonJointAttributesChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates Newton joint resolver attributes."""

    NEWTON_JOINT_ATTRIBUTES_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.NEWTON_DJ_002

    def _validate_finite_number(self, prim: Usd.Prim, attr_name: str, *, non_negative: bool = False) -> None:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return

        value = attr.Get()
        numeric_value = _as_finite_float(value)
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                message=f"Newton joint attribute '{attr_name}' on '{prim.GetPath()}' must be a finite number.",
                at=attr,
            )
            return
        if non_negative and numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                message=f"Newton joint attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=attr,
            )

    def _validate_limit_spring(self, prim: Usd.Prim, attr_name: str) -> None:
        # limitStiffness/limitDamping default to -inf, meaning "use the engine default";
        # limitStiffness may also be +inf to request a hard limit. Both sentinels are valid.
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return
        try:
            float_value = float(attr.Get())
        except (TypeError, ValueError):
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                message=f"Newton joint attribute '{attr_name}' on '{prim.GetPath()}' must be a number.",
                at=attr,
            )
            return
        if math.isinf(float_value):
            return
        if math.isnan(float_value) or float_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton joint attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative "
                    "(or the -inf sentinel that defers to the engine default)."
                ),
                at=attr,
            )

    def _validate_velocity_limit(self, prim: Usd.Prim, attr_name: str) -> None:
        # velocityLimit defaults to +inf, meaning "no velocity clamping".
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return
        try:
            float_value = float(attr.Get())
        except (TypeError, ValueError):
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                message=f"Newton joint attribute '{attr_name}' on '{prim.GetPath()}' must be a number.",
                at=attr,
            )
            return
        if math.isinf(float_value) and float_value > 0:
            return
        if not math.isfinite(float_value) or float_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                message=f"Newton joint attribute '{attr_name}' on '{prim.GetPath()}' must be positive (or inf).",
                at=attr,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        applied_schemas = _applied_api_schemas(prim)
        has_newton_joint_api = _NEWTON_JOINT_API in applied_schemas or any(
            schema.startswith(f"{_NEWTON_JOINT_API}:") for schema in applied_schemas
        )
        authored_newton_joint_attrs = tuple(
            attr_name for attr_name in _NEWTON_JOINT_ATTRS if _has_authored_attr(prim, attr_name)
        )
        if not has_newton_joint_api and not authored_newton_joint_attrs:
            return

        if not UsdPhysics.Joint(prim):
            if has_newton_joint_api:
                self._AddFailedCheck(
                    requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' applies NewtonJointAPI but is not a UsdPhysics.Joint. "
                        "Apply Newton joint tuning only on USD physics joint prims."
                    ),
                    at=prim,
                )
            for attr_name in authored_newton_joint_attrs:
                self._AddFailedCheck(
                    requirement=self.NEWTON_JOINT_ATTRIBUTES_REQUIREMENT,
                    message=(
                        f"Newton joint attribute '{attr_name}' is authored on non-joint prim '{prim.GetPath()}'. "
                        "Author Newton joint attributes only on UsdPhysics.Joint prims."
                    ),
                    at=prim.GetAttribute(attr_name),
                )
            return

        for attr_name in _NEWTON_JOINT_NON_NEGATIVE_ATTRS:
            self._validate_finite_number(prim, attr_name, non_negative=True)
        for attr_name in _NEWTON_JOINT_LIMIT_SPRING_ATTRS:
            self._validate_limit_spring(prim, attr_name)
        self._validate_velocity_limit(prim, _NEWTON_JOINT_VELOCITY_LIMIT_ATTR)


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_001, override=True)
class MuJoCoJointAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates MuJoCo joint API placement and authored joint tuning values."""

    MUJOCO_JOINT_API_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_001

    def _validate_non_negative_number(self, prim: Usd.Prim, attr_name: str) -> None:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return

        numeric_value = _as_finite_float(attr.Get())
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=f"MuJoCo joint attribute '{attr_name}' on '{prim.GetPath()}' must be a finite number.",
                at=attr,
            )
            return
        if numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=f"MuJoCo joint attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=attr,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        has_mujoco_joint_api = _has_applied_api_schema(prim, _MUJOCO_JOINT_API)
        authored_mujoco_joint_attrs = tuple(
            attr_name for attr_name in _MUJOCO_JOINT_NON_NEGATIVE_ATTRS if _has_authored_attr(prim, attr_name)
        )

        if (has_mujoco_joint_api or authored_mujoco_joint_attrs) and not UsdPhysics.Joint(prim):
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=(
                    f"Prim '{prim.GetPath()}' authors MuJoCo joint data but is not a UsdPhysics.Joint. "
                    "Apply MjcJointAPI and mjc:* joint attributes only to USD physics joint prims."
                ),
                at=prim,
            )
            return

        if _is_non_fixed_articulation_joint(prim) and not has_mujoco_joint_api:
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=(
                    f"MuJoCo articulation joint '{prim.GetPath()}' does not apply MjcJointAPI. "
                    "Apply MjcJointAPI to every non-fixed joint that participates in the articulation."
                ),
                at=prim,
            )
            return

        if not has_mujoco_joint_api:
            return

        for attr_name in _MUJOCO_JOINT_NON_NEGATIVE_ATTRS:
            self._validate_non_negative_number(prim, attr_name)


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_002, override=True)
class MuJoCoActuatorTargetsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates MuJoCo actuator prims and their target joint relationships."""

    MUJOCO_ACTUATOR_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_002

    def _validate_range_pair(
        self,
        prim: Usd.Prim,
        min_attr_name: str,
        max_attr_name: str,
        label: str,
    ) -> None:
        min_attr = prim.GetAttribute(min_attr_name)
        max_attr = prim.GetAttribute(max_attr_name)
        has_min = min_attr.IsValid() and min_attr.HasAuthoredValueOpinion()
        has_max = max_attr.IsValid() and max_attr.HasAuthoredValueOpinion()

        if has_min != has_max:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo actuator '{prim.GetPath()}' must author both min and max values " f"for its {label}."
                ),
                at=prim,
            )
            return
        if not has_min:
            return

        min_value = _as_finite_float(min_attr.Get())
        max_value = _as_finite_float(max_attr.Get())
        if min_value is None or max_value is None:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' has a non-finite {label}.",
                at=prim,
            )
            return
        if min_value > max_value:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' has an inverted {label}.",
                at=prim,
            )

    def _validate_numeric_array(self, prim: Usd.Prim, attr_name: str) -> None:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return

        if not _is_numeric_sequence(attr.Get()):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' must author '{attr_name}' as a non-empty numeric array.",
                at=attr,
            )

    def _validate_actuator(self, stage: Usd.Stage, prim: Usd.Prim, targeted_joints: set[str]) -> None:
        target_rel = prim.GetRelationship("mjc:target")
        targets = target_rel.GetTargets() if target_rel else []
        if len(targets) != 1:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' must target exactly one joint with 'mjc:target'.",
                at=prim,
            )
            return

        target_prim = stage.GetPrimAtPath(targets[0])
        if not target_prim.IsValid() or not _is_non_fixed_articulation_joint(target_prim):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo actuator '{prim.GetPath()}' targets '{targets[0]}', "
                    "which is not a valid non-fixed USD physics articulation joint."
                ),
                at=prim,
            )
            return

        if not _has_applied_api_schema(target_prim, _MUJOCO_JOINT_API):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo actuator '{prim.GetPath()}' targets joint '{targets[0]}' without MjcJointAPI. "
                    "Apply MjcJointAPI to the target joint."
                ),
                at=target_prim,
            )
            return

        targeted_joints.add(str(targets[0]))

        for min_attr_name, max_attr_name, label in _MUJOCO_ACTUATOR_RANGE_ATTRS:
            self._validate_range_pair(prim, min_attr_name, max_attr_name, label)
        for attr_name in _MUJOCO_ACTUATOR_ARRAY_ATTRS:
            self._validate_numeric_array(prim, attr_name)

        bias_type_attr = prim.GetAttribute("mjc:biasType")
        if bias_type_attr.IsValid() and bias_type_attr.HasAuthoredValueOpinion() and not str(bias_type_attr.Get()):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' authors an empty 'mjc:biasType'.",
                at=bias_type_attr,
            )

    def CheckStage(self, stage: Usd.Stage) -> None:
        mujoco_joints = []
        mujoco_actuators = []

        for prim in stage.Traverse():
            if _is_non_fixed_articulation_joint(prim) and _has_applied_api_schema(prim, _MUJOCO_JOINT_API):
                mujoco_joints.append(prim)
            if _is_mujoco_actuator(prim):
                mujoco_actuators.append(prim)

        if mujoco_joints and not mujoco_actuators:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message="MuJoCo driven joints are present, but no MjcActuator prims target them.",
                at=stage.GetDefaultPrim() or stage.GetPseudoRoot(),
            )
            return

        targeted_joints = set()
        for actuator_prim in mujoco_actuators:
            self._validate_actuator(stage, actuator_prim, targeted_joints)

        for joint_prim in mujoco_joints:
            if str(joint_prim.GetPath()) not in targeted_joints:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo joint '{joint_prim.GetPath()}' is not targeted by any MjcActuator prim. "
                        "Author an actuator with mjc:target pointing at the joint."
                    ),
                    at=joint_prim,
                )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_001, override=True)
class PhysicsDriveAndJointState(usd_validation_nvidia.BaseRuleChecker):
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
                stiffness_attr = drive.GetStiffnessAttr()
                damping_attr = drive.GetDampingAttr()
                stiffness = stiffness_attr.Get() if stiffness_attr.IsValid() else None
                damping = damping_attr.Get() if damping_attr.IsValid() else None
                if (stiffness is not None and stiffness != 0.0) or (damping is not None and damping != 0.0):
                    stop = False
                    break
        if stop:
            return

        for drive, joint_state in zip(drives, joint_states):
            force_attr = drive.GetMaxForceAttr()
            if not force_attr.IsDefined():
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                    message=f"Drive Max Force is not set on <{prim.GetPath()}>",
                    at=force_attr,
                )
            else:
                max_force = force_attr.Get()
                if max_force <= 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                        message=f"Drive Max Force is zero <{force_attr.GetPath()}>",
                        at=force_attr,
                    )
                if max_force >= float("inf"):
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
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
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                            message=f"Joint state position is very different from drive target position <{drive_target_position.GetPath()}>: difference is {pos_diff}",
                            at=drive_target_position,
                        )

                if drive_target_velocity and joint_state_velocity:
                    vel_diff = abs(drive_target_velocity.Get() - joint_state_velocity.Get())
                    if vel_diff > tolerance:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                            message=f"Joint state velocity is very different from drive target velocity <{drive_target_velocity.GetPath()}>: difference is {vel_diff}",
                            at=drive_target_velocity,
                        )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_002, override=True)
class JointHasJointStateAPI(usd_validation_nvidia.BaseRuleChecker):
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
            from ...core.path_utils import delivered_asset_identifier

            if (
                delivered_asset_identifier(layer).lower().endswith(".usdz")
                or not layer.permissionToEdit
                or not layer.permissionToSave
            ):
                raise RuntimeError(
                    f"Cannot apply JointStateAPI fix to read-only layer '{layer.identifier}'. "
                    "Extract the package or author the correction in a writable override layer."
                )
            edit_stage = Usd.Stage.Open(layer.identifier)
            if edit_stage is None:
                raise RuntimeError(f"Could not open writable layer '{layer.identifier}' for correction")

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
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_002,
                message=f"{prim.GetPath()} Has no Joint State API",
                at=prim,
                suggestion=usd_validation_nvidia.Suggestion(message="Apply Joint State API", callable=self.apply_api),
            )
        else:
            return


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_003, override=True)
class JointHasCorrectTransformAndState(usd_validation_nvidia.BaseRuleChecker):
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
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} position not well-defined ({(expected_pos_0 - expected_pos_1).GetLength()}). From body 0: {expected_pos_0}, from body 1: {expected_pos_1}",
                    at=prim,
                )
            else:
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} state not matching robot pose({(expected_state_pos_0 - expected_pos_1).GetLength()}). From body 0: {expected_state_pos_0}, from body 1: {expected_pos_1}",
                    at=prim,
                )

        # Check if the orientation is as expected (double-cover safe: q and -q same rotation)
        _ROT_TOL = 1e-3
        expected_state_rot_0 = joint_state_pos_0.GetRotation()
        expected_rot_0 = expected_tm_0.GetRotation()
        expected_rot_1 = expected_tm_1.GetRotation()
        q_state = expected_state_rot_0.GetQuat().GetNormalized()
        q0 = expected_rot_0.GetQuat().GetNormalized()
        q1 = expected_rot_1.GetQuat().GetNormalized()

        base_rot_match = _rotations_match_orientation(q0, q1, _ROT_TOL)
        state_rot_match = _rotations_match_orientation(q_state, q1, _ROT_TOL)

        if not state_rot_match:
            if not base_rot_match:
                mag = _rotation_error_magnitude(q0, q1)
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} Rotation not well defined ({mag}), From body 0: {expected_rot_0}, From body 1: {expected_rot_1}",
                    at=prim,
                )
            else:
                mag = _rotation_error_magnitude(q_state, q1)
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} state not matching robot pose ({mag}). From body 0: {expected_state_rot_0}, from body 1: {expected_rot_1}",
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_004, override=True)
class PhysicsJointHasDriveOrMimicAPI(usd_validation_nvidia.BaseRuleChecker):
    """Validates that joints have a drive or mimic API.

    This rule ensures that all joints (except fixed joints) have either a drive API
    or a mimic API configured. When both are present, revolute (and other non-prismatic)
    followers must zero drive gains so the mimic constraint owns the DOF. Prismatic
    followers must keep non-zero drive stiffness because PhysX does not enforce
    PhysxMimicJointAPI on linear DOFs.
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
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_004,
                message=f"Joint {prim.GetPath()} has no drive or mimic API",
                at=prim,
            )
        if drives and has_mimic:
            is_prismatic = prim.IsA(UsdPhysics.PrismaticJoint)
            for drive in drives:
                stiffness_attr = drive.GetStiffnessAttr()
                damping_attr = drive.GetDampingAttr()
                stiffness = stiffness_attr.Get() if stiffness_attr.IsValid() else None
                damping = damping_attr.Get() if damping_attr.IsValid() else None
                has_nonzero_stiffness = stiffness is not None and stiffness != 0.0
                has_nonzero_gain = has_nonzero_stiffness or (damping is not None and damping != 0.0)
                if is_prismatic:
                    # PhysX does not enforce PhysxMimicJointAPI on prismatic DOFs; the
                    # follower drive is what couples the mechanism. Damping alone cannot
                    # hold a position target, so stiffness must be non-zero.
                    if not has_nonzero_stiffness:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_004,
                            message=(
                                f"Joint {prim.GetPath()} is a prismatic mimic follower without "
                                "non-zero drive stiffness; PhysX does not enforce linear mimic, "
                                "so a positive follower drive stiffness is required"
                            ),
                            at=prim,
                        )
                elif has_nonzero_gain:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_004,
                        message=f"Joint {prim.GetPath()} has both drive and mimic API",
                        at=prim,
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_005, override=True)
class PhysicsJointMaxVelocity(usd_validation_nvidia.BaseRuleChecker):
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
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_005,
                    message=f"Max joint velocity is not set on <{prim.GetPath()}>",
                    at=prim,
                )
            else:
                max_joint_velocity = attr.Get()
                if max_joint_velocity <= 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_005,
                        message=f"Max joint velocity is zero <{attr.GetPath()}>",
                        at=attr,
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_006, override=True)
class DriveJointValueReasonable(usd_validation_nvidia.BaseRuleChecker):
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
        is_mimic = PhysxSchema is not None and prim.HasAPI(PhysxSchema.PhysxMimicJointAPI)
        # PhysX does not enforce PhysxMimicJointAPI on prismatic DOFs, so prismatic
        # mimic followers keep a real drive and use the normal stiffness range checks.
        is_prismatic_mimic = is_mimic and prim.IsA(UsdPhysics.PrismaticJoint)
        for drive in drives:
            stiffness_attr = drive.GetStiffnessAttr()
            stiffness = (
                stiffness_attr.Get() if stiffness_attr.IsValid() and stiffness_attr.HasAuthoredValueOpinion() else None
            )
            if stiffness is None and (not is_mimic or is_prismatic_mimic):
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                    message=f"Drive stiffness is not set on <{drive.GetPath()}>",
                    at=stiffness_attr,
                )
                continue
            elif is_prismatic_mimic and stiffness == 0.0:
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                    message=(f"prismatic mimic joint requires non-zero drive stiffness " f"<{drive.GetPath()}>"),
                    at=stiffness_attr,
                )
            elif is_mimic and not is_prismatic_mimic:
                damping_attr = drive.GetDampingAttr()
                damping = (
                    damping_attr.Get() if damping_attr.IsValid() and damping_attr.HasAuthoredValueOpinion() else None
                )
                if damping is not None and damping != 0.0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                        message=f"joint is mimic but has damping set <{drive.GetPath()}>",
                        at=damping_attr,
                    )
                if stiffness is not None and stiffness != 0.0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                        message=f"joint is mimic but has stiffness set <{drive.GetPath()}>",
                        at=stiffness_attr,
                    )
            elif stiffness < self.DRIVE_STIFFNESS_MIN or stiffness > self.DRIVE_STIFFNESS_MAX:
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                    message=f"Drive stiffness is out of range <{drive.GetPath()}>: {stiffness}",
                    at=prim,
                )
            continue
            # TODO: Work in progress for natural frequency


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_007, override=True)
class MimicAPICheck(usd_validation_nvidia.BaseRuleChecker):
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
                if axis not in _MIMIC_AXES:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has unknown mimic axis: {axis}, aborting checks",
                        at=prim,
                    )
                    return
                mimic_api = PhysxSchema.PhysxMimicJointAPI(prim, axis)

                # For the mimic API, perform checks

                # reference joint check
                reference_joint = mimic_api.GetReferenceJointRel().GetTargets()
                if not reference_joint or len(reference_joint) > 1:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has incorrect number of reference joints, expected: 1, actual: {len(reference_joint)}",
                        at=prim,
                    )

                # self value checks
                gear_ratio = mimic_api.GetGearingAttr().Get()
                natural_frequency = prim.GetAttribute(f"physxMimicJoint:{axis}:naturalFrequency").Get()
                damping_ratio = prim.GetAttribute(f"physxMimicJoint:{axis}:dampingRatio").Get()

                if gear_ratio is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no gear ratio",
                        at=prim,
                    )

                if natural_frequency is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no natural frequency",
                        at=prim,
                    )

                if damping_ratio is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no damping ratio",
                        at=prim,
                    )

                if gear_ratio == 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has gear ratio == 0",
                        at=prim,
                    )

                if natural_frequency == 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has natural frequency == 0",
                        at=prim,
                    )

                if damping_ratio == 0:
                    self._AddInfo(message=f"Joint {prim.GetPath()} has damping ratio == 0", at=prim)

                # limit checks
                self_joint_lower_limit, self_joint_upper_limit = get_prismatic_or_revolute_limits(prim)
                if self_joint_lower_limit is None or self_joint_upper_limit is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
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
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no limits",
                        at=prim,
                    )
                    return

                # ensure the mimic joint and the reference joint are not excluded from articulation
                if reference_joint_prim.GetAttribute("physics:excludeFromArticulation").Get():
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Mimic joint {prim.GetPath()} has a reference joint {reference_joint_prim.GetPath()} that is excluded from articulation.. The mimic joint reference joint cannot be excluded from articulation.",
                        at=prim,
                    )
                    return
                if prim.GetAttribute("physics:excludeFromArticulation").Get():
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
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
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                            message=f"Joint {prim.GetPath()}'s lower limit ({self_joint_lower_limit}) should be > reference joint limits * gear ratio({reference_joint_lower_limit * gear_ratio})",
                            at=prim,
                        )

                    if not self_joint_upper_limit > reference_joint_upper_limit * gear_ratio:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                            message=f"Joint {prim.GetPath()}'s upper limit ({self_joint_upper_limit}) should be < reference joint limits * gear ratio({reference_joint_upper_limit * gear_ratio})",
                            at=prim,
                        )
                else:
                    if not reference_joint_lower_limit * gear_ratio < self_joint_upper_limit:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                            message=f"Joint {prim.GetPath()}'s lower limit ({self_joint_upper_limit}) should be > reference joint limits * gear ratio({reference_joint_lower_limit * gear_ratio})",
                            at=prim,
                        )

                    if not self_joint_lower_limit < reference_joint_upper_limit * gear_ratio:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                            message=f"Joint {prim.GetPath()}'s upper limit ({self_joint_lower_limit}) should be < reference joint limits * gear ratio({reference_joint_upper_limit * gear_ratio})",
                            at=prim,
                        )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_008, override=True)
class JointsExist(usd_validation_nvidia.BaseRuleChecker):
    """Validates that robot assets contain at least one joint.

    This rule checks that robot assets have at least one prim with the JointAPI
    applied, which is typically required for articulated robots.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Skipped on rigid-body-only assets (vehicles, non-articulated props)
        # which are not expected to carry any isaac:physics:JointAPI.
        if not any(prim.IsA(UsdPhysics.Joint) for prim in stage.Traverse()):
            return
        # JW: lazy load the schema as we dont have it and its breaking workspace
        from usd.schema.isaac import robot_schema

        for prim in stage.Traverse():
            if prim.HasAPI(robot_schema.Classes.JOINT_API.value):
                return
        self._AddFailedCheck(
            requirement=cap.PhysicsDrivenJointsRequirements.DJ_008,
            message=f"No joints found in robot asset <{stage.GetRootLayer().realPath}>",
            at=stage,
        )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_009, override=True)
class LinksExist(usd_validation_nvidia.BaseRuleChecker):
    """Validates that robot assets contain at least one link.

    This rule checks that robot assets have at least one prim with the LinkAPI
    applied, which is typically required for articulated robots.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Skipped on rigid-body-only assets (vehicles, non-articulated props)
        # which are not expected to carry any isaac:physics:LinkAPI.
        if not any(prim.IsA(UsdPhysics.Joint) for prim in stage.Traverse()):
            return
        # JW: lazy load the schema as we dont have it and its breaking workspace
        from usd.schema.isaac import robot_schema

        for prim in stage.Traverse():
            if prim.HasAPI(robot_schema.Classes.LINK_API.value):
                return
        self._AddFailedCheck(
            requirement=cap.PhysicsDrivenJointsRequirements.DJ_009,
            message=f"No links found in robot asset <{stage.GetRootLayer().realPath}>",
            at=stage,
        )


def is_relationship_prepended(relationship) -> bool:
    """Check if a relationship is prepended in the layer stack.

    Examines the property stack of the relationship to determine if it uses
    prepended items rather than explicit items in the target path list.

    Args:
        relationship: The USD relationship to check.

    Returns:
        True if the relationship is prepended, False if it uses explicit items.
    """
    rel_stack = relationship.GetPropertyStack()
    return all(not spec.targetPathList.isExplicit for spec in rel_stack)


def make_relationship_prepended(relationship) -> bool:
    """Convert a relationship to use prepended items in the layer stack.

    Modifies the relationship's property specs to use prepended items instead of
    explicit items, which allows for composition with stronger layers.

    Args:
        relationship: The USD relationship to convert.

    Returns:
        True if the operation was successful.
    """
    rel_stack = relationship.GetPropertyStack()
    for spec in rel_stack:
        if spec.targetPathList.isExplicit:
            items = list(spec.targetPathList.explicitItems)
            spec.targetPathList.prependedItems = items
            spec.targetPathList.explicitItems = []
    return True


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_010, override=True)
class CheckRobotRelationships(usd_validation_nvidia.BaseRuleChecker):
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
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
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
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
                        message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a {relationship_name} relationship",
                        at=prim,
                        suggestion=usd_validation_nvidia.Suggestion(
                            message="Create relationship",
                            callable=fix_method,
                            at=usd_validation_nvidia.AuthoringLayers(prim),
                        ),
                    )
                    continue

                # Check if the relationship is prepended
                is_prepended = is_relationship_prepended(relationship)
                if not is_prepended:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
                        message=f"Relationship {relationship_name} is not prepended",
                        at=prim,
                        suggestion=usd_validation_nvidia.Suggestion(
                            message="Make relationship prepended", callable=make_method
                        ),
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_011, override=True)
class ArticulationNoLoopsOrMultiJoint(usd_validation_nvidia.BaseRuleChecker):
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
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_011,
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
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_011,
                        message=f"Articulation has a loop: bodies {cycle_bodies}; joints involved: {cycle_joints}\nEnable excludeFromArticulation on one of the joints in the loop to allow for loops.",
                        at=path_to_joint[
                            (min(cycle_bodies[0], cycle_bodies[1]), max(cycle_bodies[0], cycle_bodies[1]))
                        ],
                    )


@usd_validation_nvidia.register_rule("NewtonMimicAPI")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.NEWTON_DJ_003, override=True)
class NewtonMimicAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """NEWTON.DJ.003 - validate NewtonMimicAPI placement, leader target, and coefficients."""

    NEWTON_MIMIC_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.NEWTON_DJ_003

    _MIMIC_JOINT_REL = "newton:mimicJoint"
    _COEF_ATTRS = ("newton:mimicCoef0", "newton:mimicCoef1")
    _ENABLED_ATTR = "newton:mimicEnabled"

    def _validate_leader(self, prim: Usd.Prim) -> None:
        rel = prim.GetRelationship(self._MIMIC_JOINT_REL)
        targets = rel.GetTargets() if rel else []
        if not targets:
            self._AddFailedCheck(
                requirement=self.NEWTON_MIMIC_REQUIREMENT,
                message=(
                    f"NewtonMimicAPI on '{prim.GetPath()}' must author a '{self._MIMIC_JOINT_REL}' "
                    "relationship targeting the leader joint."
                ),
                at=prim,
            )
            return
        if len(targets) > 1:
            self._AddFailedCheck(
                requirement=self.NEWTON_MIMIC_REQUIREMENT,
                message=(
                    f"NewtonMimicAPI on '{prim.GetPath()}' must target exactly one leader joint via "
                    f"'{self._MIMIC_JOINT_REL}', got {len(targets)}."
                ),
                at=prim,
            )
            return
        leader_path = targets[0]
        if str(leader_path) == str(prim.GetPath()):
            self._AddFailedCheck(
                requirement=self.NEWTON_MIMIC_REQUIREMENT,
                message=f"NewtonMimicAPI on '{prim.GetPath()}' must not mimic itself.",
                at=prim,
            )
            return
        leader = prim.GetStage().GetPrimAtPath(leader_path)
        if not leader.IsValid() or not UsdPhysics.Joint(leader):
            self._AddFailedCheck(
                requirement=self.NEWTON_MIMIC_REQUIREMENT,
                message=(
                    f"NewtonMimicAPI on '{prim.GetPath()}' targets '{leader_path}', which is not a " "UsdPhysics.Joint."
                ),
                at=prim,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if _NEWTON_MIMIC_API not in _applied_api_schemas(prim):
            return

        if not UsdPhysics.Joint(prim):
            self._AddFailedCheck(
                requirement=self.NEWTON_MIMIC_REQUIREMENT,
                message=(
                    f"NewtonMimicAPI is applied on '{prim.GetPath()}', which is not a UsdPhysics.Joint. "
                    "Apply NewtonMimicAPI only on physics joints."
                ),
                at=prim,
            )
            return

        self._validate_leader(prim)

        for attr_name in self._COEF_ATTRS:
            if not _has_authored_attr(prim, attr_name):
                continue
            if _as_finite_float(prim.GetAttribute(attr_name).Get()) is None:
                self._AddFailedCheck(
                    requirement=self.NEWTON_MIMIC_REQUIREMENT,
                    message=f"NewtonMimicAPI attribute '{attr_name}' on '{prim.GetPath()}' must be a finite number.",
                    at=prim.GetAttribute(attr_name),
                )

        enabled_attr = prim.GetAttribute(self._ENABLED_ATTR)
        if enabled_attr.IsValid() and enabled_attr.HasAuthoredValueOpinion():
            if not isinstance(enabled_attr.Get(), bool):
                self._AddFailedCheck(
                    requirement=self.NEWTON_MIMIC_REQUIREMENT,
                    message=f"NewtonMimicAPI attribute '{self._ENABLED_ATTR}' on '{prim.GetPath()}' must be a boolean.",
                    at=enabled_attr,
                )

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
__all__ = [
    "NewtonJointDriveAPIChecker",
    "NewtonJointAttributesChecker",
    "NewtonMimicAPIChecker",
]

import math

import simready.foundation.tier_newton.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics

from simready.foundation.tier_newton.rules_and_reqs._common import (
    _applied_api_schemas,
    _as_finite_float,
    _has_applied_api_schema,
    _has_authored_attr,
)

_NEWTON_JOINT_API = "NewtonJointAPI"
_NEWTON_MIMIC_API = "NewtonMimicAPI"
_NEWTON_MIMIC_JOINT_REL = "newton:mimicJoint"
_NEWTON_MIMIC_ENABLED_ATTR = "newton:mimicEnabled"
_DRIVE_AXES = ("angular", "linear", "rotX", "rotY", "rotZ", "transX", "transY", "transZ")
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

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
__all__ = ["PhysicsGrippersValidation"]

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdGeom

try:
    from pxr import IsaacSensorSchema
except ImportError:
    IsaacSensorSchema = None

_SOCKET_TYPE_ATTR = "simready:attachment:socketType"
_SOCKET_TYPE_VALUE = "Gripper"
_MUJOCO_SITE_API = "MjcSiteAPI"
_ISAAC_SITE_API = "IsaacSiteAPI"

# Canonical gripper_-prefixed name first, then unprefixed alternates for
# assets authored before the gripper_ convention was settled. The runtime
# benchmark harness accepts the same spellings; see
# simready_benchmark_kit_suite.articulation_phases.gripper_sites.
_FORWARD_AXIS_NAMES = ("gripper_forward_axis", "forward_axis")
_GRIP_LINE_NAMES = ("gripper_grip_line", "grip_line")
_MAX_OPENING_NAMES = ("gripper_maxOpening", "custom:maxOpening")
_MUJOCO_GR_001 = cap.PhysicsGrippersRequirements.MUJOCO_GR_001


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


def _has_mujoco_site_api(prim: Usd.Prim) -> bool:
    return _MUJOCO_SITE_API in _applied_api_schemas(prim)


def _has_isaac_site_api(prim: Usd.Prim) -> bool:
    """Return True when IsaacSiteAPI is applied to prim.

    Falls back to authored opinions because GetAppliedSchemas() drops
    IsaacSiteAPI wherever the Isaac schema plugin is not registered.
    """
    if IsaacSensorSchema is not None:
        try:
            if IsaacSensorSchema.IsaacSiteAPI(prim):
                return True
        except Exception:
            pass
    return _ISAAC_SITE_API in _applied_api_schemas(prim)


def _is_gripper_site(prim: Usd.Prim) -> bool:
    """Return True for prims that qualify as gripper sites.

    A prim is a gripper site if it has simready:attachment:socketType = "Gripper".
    This covers both the Neutral and Isaac formats without requiring a specific prim name.
    """
    attr = prim.GetAttribute(_SOCKET_TYPE_ATTR)
    if not attr or not attr.IsDefined():
        return False
    return attr.Get() == _SOCKET_TYPE_VALUE


def _first_child(prim: Usd.Prim, names: tuple[str, ...]) -> Usd.Prim | None:
    """Return the first existing child among the accepted name spellings."""
    for name in names:
        child = prim.GetChild(name)
        if child and child.IsValid():
            return child
    return None


def _first_attribute(prim: Usd.Prim, names: tuple[str, ...]):
    """Return the first defined attribute among the accepted name spellings."""
    for name in names:
        attr = prim.GetAttribute(name)
        if attr and attr.IsDefined():
            return attr
    return None


def _get_curve_points(prim: Usd.Prim):
    """Return the points array of a BasisCurves prim, or None if unavailable."""
    curves = UsdGeom.BasisCurves(prim)
    if not curves:
        return None
    attr = prim.GetAttribute("points")
    if not attr:
        return None
    return attr.Get()


@usd_validation_nvidia.register_rule("PhysicsGrippers")
@usd_validation_nvidia.register_requirements(cap.PhysicsGrippersRequirements.GR_001, override=True)
class GripperSocketType(usd_validation_nvidia.BaseRuleChecker):
    """Validates that gripper site prims are Xform and carry socketType = Gripper (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                message="Stage has no default prim.",
                at=stage,
            )
            return

        for prim in Usd.PrimRange(default_prim):
            attr = prim.GetAttribute(_SOCKET_TYPE_ATTR)
            if not attr or not attr.IsDefined():
                continue
            if attr.Get() != _SOCKET_TYPE_VALUE:
                continue
            # Prim has the attribute with "Gripper" value — must be Xform
            if not prim.IsA(UsdGeom.Xform):
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_001,
                    message=(
                        f"Prim '{prim.GetPath()}' has {_SOCKET_TYPE_ATTR} = '{_SOCKET_TYPE_VALUE}' "
                        f"but is not an Xform, got '{prim.GetTypeName()}'."
                    ),
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsGrippers")
@usd_validation_nvidia.register_requirements(cap.PhysicsGrippersRequirements.GR_002, override=True)
class GripperForwardAxis(usd_validation_nvidia.BaseRuleChecker):
    """Validates that gripper site prims contain a valid forward_axis BasisCurves child (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            forward_axis = _first_child(prim, _FORWARD_AXIS_NAMES)
            if forward_axis is None:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_002,
                    message=f"Gripper site '{prim.GetPath()}' is missing a 'gripper_forward_axis' child prim.",
                    at=prim,
                )
                continue

            if not UsdGeom.BasisCurves(forward_axis):
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_002,
                    message=f"Gripper site '{prim.GetPath()}': '{forward_axis.GetName()}' is not a BasisCurves prim.",
                    at=forward_axis,
                )
                continue

            points = _get_curve_points(forward_axis)
            if not points or len(points) < 2:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_002,
                    message=(
                        f"Gripper site '{prim.GetPath()}': '{forward_axis.GetName()}' must have at least 2 points, "
                        f"but has {len(points) if points else 0}."
                    ),
                    at=forward_axis,
                )


@usd_validation_nvidia.register_rule("PhysicsGrippers")
@usd_validation_nvidia.register_requirements(cap.PhysicsGrippersRequirements.GR_003, override=True)
class GripperGripLine(usd_validation_nvidia.BaseRuleChecker):
    """Validates that gripper site prims contain a valid grip_line BasisCurves child (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            grip_line = _first_child(prim, _GRIP_LINE_NAMES)
            if grip_line is None:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_003,
                    message=f"Gripper site '{prim.GetPath()}' is missing a 'gripper_grip_line' child prim.",
                    at=prim,
                )
                continue

            if not UsdGeom.BasisCurves(grip_line):
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_003,
                    message=f"Gripper site '{prim.GetPath()}': '{grip_line.GetName()}' is not a BasisCurves prim.",
                    at=grip_line,
                )
                continue

            points = _get_curve_points(grip_line)
            if not points or len(points) < 2:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_003,
                    message=(
                        f"Gripper site '{prim.GetPath()}': '{grip_line.GetName()}' must have at least 2 points, "
                        f"but has {len(points) if points else 0}."
                    ),
                    at=grip_line,
                )


@usd_validation_nvidia.register_rule("PhysicsGrippers")
@usd_validation_nvidia.register_requirements(cap.PhysicsGrippersRequirements.GR_004, override=True)
class GripperMaxOpening(usd_validation_nvidia.BaseRuleChecker):
    """Validates that gripper site prims declare a positive custom:maxOpening attribute (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            attr = _first_attribute(prim, _MAX_OPENING_NAMES)
            if attr is None:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_004,
                    message=f"Gripper site '{prim.GetPath()}' is missing 'gripper_maxOpening' attribute.",
                    at=prim,
                )
                continue

            value = attr.Get()
            if value is None:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_004,
                    message=f"Gripper site '{prim.GetPath()}': '{attr.GetName()}' has no value.",
                    at=attr,
                )
                continue

            if value <= 0:
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_004,
                    message=f"Gripper site '{prim.GetPath()}': '{attr.GetName()}' must be > 0, got {value}.",
                    at=attr,
                )


@usd_validation_nvidia.register_rule("PhysicsGrippers")
@usd_validation_nvidia.register_requirements(_MUJOCO_GR_001, override=True)
class MuJoCoGripperSiteAPI(usd_validation_nvidia.BaseRuleChecker):
    """Validates that gripper site prims carry MjcSiteAPI for MuJoCo."""

    MUJOCO_GRIPPER_SITE_REQUIREMENT = _MUJOCO_GR_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            if not _has_mujoco_site_api(prim):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_GRIPPER_SITE_REQUIREMENT,
                    message=f"MuJoCo gripper site '{prim.GetPath()}' is missing MjcSiteAPI.",
                    at=prim,
                )
                continue

            group_attr = prim.GetAttribute("mjc:group")
            if not group_attr.IsValid() or not group_attr.HasAuthoredValueOpinion():
                continue

            group_value = group_attr.Get()
            try:
                numeric_value = int(group_value)
            except (TypeError, ValueError):
                numeric_value = None
            if numeric_value is None or numeric_value < 0 or numeric_value != group_value:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_GRIPPER_SITE_REQUIREMENT,
                    message=f"MuJoCo gripper site '{prim.GetPath()}' must author 'mjc:group' as a non-negative integer.",
                    at=group_attr,
                )


@usd_validation_nvidia.register_rule("PhysicsGrippers")
@usd_validation_nvidia.register_requirements(cap.PhysicsGrippersRequirements.GR_ISA_001, override=True)
class IsaacGripperSiteAPI(usd_validation_nvidia.BaseRuleChecker):
    """Validates that gripper site prims carry IsaacSiteAPI and isaac:Description (Isaac format)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            if not _has_isaac_site_api(prim):
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_ISA_001,
                    message=f"Gripper site '{prim.GetPath()}' is missing IsaacSiteAPI.",
                    at=prim,
                )
                continue

            desc_attr = prim.GetAttribute("isaac:Description")
            if not desc_attr or not desc_attr.IsDefined():
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_ISA_001,
                    message=f"Gripper site '{prim.GetPath()}' has IsaacSiteAPI but is missing 'isaac:Description'.",
                    at=prim,
                )
                continue

            desc_value = desc_attr.Get()
            if not desc_value or not str(desc_value).strip():
                self._AddFailedCheck(
                    requirement=cap.PhysicsGrippersRequirements.GR_ISA_001,
                    message=f"Gripper site '{prim.GetPath()}': 'isaac:Description' must be a non-empty string.",
                    at=desc_attr,
                )

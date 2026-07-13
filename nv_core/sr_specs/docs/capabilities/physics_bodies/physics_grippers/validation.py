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

from enum import Enum

import omni.asset_validator.core
from pxr import Usd, UsdGeom

from ... import Requirement

try:
    from pxr import IsaacSensorSchema
except ImportError:
    IsaacSensorSchema = None

_SOCKET_TYPE_ATTR = "simready:attactment:socketType"
_SOCKET_TYPE_VALUE = "Gripper"


def _has_isaac_site_api(prim: Usd.Prim) -> bool:
    """Return True when IsaacSiteAPI is applied to prim."""
    if IsaacSensorSchema is not None:
        try:
            if IsaacSensorSchema.IsaacSiteAPI(prim):
                return True
        except Exception:
            pass
    for schema in prim.GetAppliedSchemas():
        if schema == "IsaacSiteAPI":
            return True
    return False


def _is_gripper_site(prim: Usd.Prim) -> bool:
    """Return True for prims that qualify as gripper sites.

    A prim is a gripper site if it has simready:attactment:socketType = "Gripper".
    This covers both the Neutral and Isaac formats without requiring a specific prim name.
    """
    attr = prim.GetAttribute(_SOCKET_TYPE_ATTR)
    if not attr or not attr.IsDefined():
        return False
    return attr.Get() == _SOCKET_TYPE_VALUE


def _get_curve_points(prim: Usd.Prim):
    """Return the points array of a BasisCurves prim, or None if unavailable."""
    curves = UsdGeom.BasisCurves(prim)
    if not curves:
        return None
    attr = prim.GetAttribute("points")
    if not attr:
        return None
    return attr.Get()


class GripperSiteCapReq(Requirement, Enum):
    # Neutral
    GR_001 = (
        "GR.001",
        "gripper-socket-type",
        "Every gripper site prim must be an Xform with simready:attactment:socketType = 'Gripper'.",
    )
    GR_002 = (
        "GR.002",
        "gripper-forward-axis",
        "Gripper site prim must contain a BasisCurves child named 'forward_axis' with at least 2 points.",
    )
    GR_003 = (
        "GR.003",
        "gripper-grip-line",
        "Gripper site prim must contain a BasisCurves child named 'grip_line' with at least 2 points.",
    )
    GR_004 = (
        "GR.004",
        "gripper-max-opening",
        "Gripper site prim must have custom:maxOpening > 0 (meters).",
    )
    # Isaac
    GR_ISA_001 = (
        "GR.ISA.001",
        "gripper-site-api",
        "Every gripper site prim must have IsaacSiteAPI applied and isaac:Description authored.",
    )


@omni.asset_validator.core.registerRule("PhysicsGrippers")
@omni.asset_validator.core.register_requirements(GripperSiteCapReq.GR_001, override=True)
class GripperSocketType(omni.asset_validator.core.BaseRuleChecker):
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
                    requirement=GripperSiteCapReq.GR_001,
                    message=(
                        f"Prim '{prim.GetPath()}' has {_SOCKET_TYPE_ATTR} = '{_SOCKET_TYPE_VALUE}' "
                        f"but is not an Xform, got '{prim.GetTypeName()}'."
                    ),
                    at=prim,
                )


@omni.asset_validator.core.registerRule("PhysicsGrippers")
@omni.asset_validator.core.register_requirements(GripperSiteCapReq.GR_002, override=True)
class GripperForwardAxis(omni.asset_validator.core.BaseRuleChecker):
    """Validates that gripper site prims contain a valid forward_axis BasisCurves child (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            forward_axis = prim.GetChild("forward_axis")
            if not forward_axis or not forward_axis.IsValid():
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_002,
                    message=f"Gripper site '{prim.GetPath()}' is missing a 'forward_axis' child prim.",
                    at=prim,
                )
                continue

            if not UsdGeom.BasisCurves(forward_axis):
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_002,
                    message=f"Gripper site '{prim.GetPath()}': 'forward_axis' is not a BasisCurves prim.",
                    at=forward_axis,
                )
                continue

            points = _get_curve_points(forward_axis)
            if not points or len(points) < 2:
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_002,
                    message=(
                        f"Gripper site '{prim.GetPath()}': 'forward_axis' must have at least 2 points, "
                        f"but has {len(points) if points else 0}."
                    ),
                    at=forward_axis,
                )


@omni.asset_validator.core.registerRule("PhysicsGrippers")
@omni.asset_validator.core.register_requirements(GripperSiteCapReq.GR_003, override=True)
class GripperGripLine(omni.asset_validator.core.BaseRuleChecker):
    """Validates that gripper site prims contain a valid grip_line BasisCurves child (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            grip_line = prim.GetChild("grip_line")
            if not grip_line or not grip_line.IsValid():
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_003,
                    message=f"Gripper site '{prim.GetPath()}' is missing a 'grip_line' child prim.",
                    at=prim,
                )
                continue

            if not UsdGeom.BasisCurves(grip_line):
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_003,
                    message=f"Gripper site '{prim.GetPath()}': 'grip_line' is not a BasisCurves prim.",
                    at=grip_line,
                )
                continue

            points = _get_curve_points(grip_line)
            if not points or len(points) < 2:
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_003,
                    message=(
                        f"Gripper site '{prim.GetPath()}': 'grip_line' must have at least 2 points, "
                        f"but has {len(points) if points else 0}."
                    ),
                    at=grip_line,
                )


@omni.asset_validator.core.registerRule("PhysicsGrippers")
@omni.asset_validator.core.register_requirements(GripperSiteCapReq.GR_004, override=True)
class GripperMaxOpening(omni.asset_validator.core.BaseRuleChecker):
    """Validates that gripper site prims declare a positive custom:maxOpening attribute (Neutral)."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        for prim in Usd.PrimRange(default_prim):
            if not _is_gripper_site(prim):
                continue

            attr = prim.GetAttribute("custom:maxOpening")
            if not attr or not attr.IsDefined():
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_004,
                    message=f"Gripper site '{prim.GetPath()}' is missing 'custom:maxOpening' attribute.",
                    at=prim,
                )
                continue

            value = attr.Get()
            if value is None:
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_004,
                    message=f"Gripper site '{prim.GetPath()}': 'custom:maxOpening' has no value.",
                    at=attr,
                )
                continue

            if value <= 0:
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_004,
                    message=f"Gripper site '{prim.GetPath()}': 'custom:maxOpening' must be > 0, got {value}.",
                    at=attr,
                )


@omni.asset_validator.core.registerRule("PhysicsGrippers")
@omni.asset_validator.core.register_requirements(GripperSiteCapReq.GR_ISA_001, override=True)
class GripperSiteAPI(omni.asset_validator.core.BaseRuleChecker):
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
                    requirement=GripperSiteCapReq.GR_ISA_001,
                    message=f"Gripper site '{prim.GetPath()}' is missing IsaacSiteAPI.",
                    at=prim,
                )
                continue

            desc_attr = prim.GetAttribute("isaac:Description")
            if not desc_attr or not desc_attr.IsDefined():
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_ISA_001,
                    message=f"Gripper site '{prim.GetPath()}' has IsaacSiteAPI but is missing 'isaac:Description'.",
                    at=prim,
                )
                continue

            desc_value = desc_attr.Get()
            if not desc_value or not str(desc_value).strip():
                self._AddFailedCheck(
                    requirement=GripperSiteCapReq.GR_ISA_001,
                    message=f"Gripper site '{prim.GetPath()}': 'isaac:Description' must be a non-empty string.",
                    at=desc_attr,
                )

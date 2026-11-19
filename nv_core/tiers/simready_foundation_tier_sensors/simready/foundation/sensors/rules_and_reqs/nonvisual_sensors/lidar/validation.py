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
    "OmniLidarChecker",
    "OmniLidarEmitterStateChecker",
    "OmniLidarScanRateChecker",
    "OmniLidarSolidStateChecker",
]

import logging

import simready.foundation.sensors.requirements as cap
from pxr import Usd, UsdGeom
from usd_validation_nvidia import BaseRuleChecker, register_requirements, register_rule

logger = logging.getLogger(__name__)

_EMITTER_STATE_PREFIX = "omni:sensor:Core:emitterState:"
_EMITTER_STATE_LENGTH_EXEMPT = "isRoiState"


def _get_applied_schemas(prim: Usd.Prim) -> frozenset:
    """Return all applied API schema names, including schemas not registered in the local runtime."""
    schemas = set(prim.GetAppliedSchemas())
    meta = prim.GetMetadata("apiSchemas")
    if meta:
        schemas.update(meta.ApplyOperations([]))
    return frozenset(schemas)


@register_rule("LidarSensor")
@register_requirements(cap.LidarRequirements.LI_001)
class OmniLidarChecker(BaseRuleChecker):
    """
    Validate that LiDARs use OmniLidar prims with OmniSensorGenericLidarCoreAPI.
    Legacy UsdGeom.Camera lidar patterns are not allowed.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        schemas = _get_applied_schemas(prim)
        type_name = prim.GetPrimTypeInfo().GetTypeName()

        is_camera = prim.IsA(UsdGeom.Camera)
        is_lidar = type_name == "OmniLidar"
        if not (is_camera or is_lidar):
            return

        if is_camera:
            self._AddFailedCheck(
                message="Lidars must be represented by an OmniLidar prim with OmniSensorGenericLidarCoreAPI; legacy Camera-based lidars are not allowed.",
                at=prim,
                requirement=cap.LidarRequirements.LI_001,
            )
            return

        if is_lidar and "OmniSensorGenericLidarCoreAPI" not in schemas:
            self._AddFailedCheck(
                message="OmniLidar prims require an OmniSensorGenericLidarCoreAPI schema.",
                at=prim,
                requirement=cap.LidarRequirements.LI_001,
            )


@register_rule("LidarSensor")
@register_requirements(cap.LidarRequirements.LI_002)
class OmniLidarEmitterStateChecker(BaseRuleChecker):
    """
    Validate array length consistency on OmniLidar prims (LI.002).

    Checks three related constraints that mirror LidarCoreSensorCheckerImpl:

    1. Every emitter state array (omni:sensor:Core:emitterState:*) must have
       exactly omni:sensor:Core:numberOfEmitters elements. The isRoiState
       attribute is exempt.

    2. If omni:sensor:Core:rangesMinM is present, its length must equal
       omni:sensor:Core:rangeCount (default 1).

    3. If omni:sensor:Core:rangesMaxM is present, its length must equal
       omni:sensor:Core:rangeCount (default 1).
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.GetPrimTypeInfo().GetTypeName() != "OmniLidar":
            return

        # --- Check 1: emitter state array lengths ---
        num_emitters_attr = prim.GetAttribute("omni:sensor:Core:numberOfEmitters")
        num_emitters = num_emitters_attr.Get() if num_emitters_attr else None
        if num_emitters is None:
            self._AddFailedCheck(
                message="OmniLidar prim is missing required attribute omni:sensor:Core:numberOfEmitters.",
                at=prim,
                requirement=cap.LidarRequirements.LI_002,
            )
        else:
            for attr in prim.GetAttributes():
                name = attr.GetName()
                if not name.startswith(_EMITTER_STATE_PREFIX):
                    continue
                if name.endswith(_EMITTER_STATE_LENGTH_EXEMPT):
                    continue
                value = attr.Get()
                if value is None or len(value) == 0:
                    continue
                if len(value) != num_emitters:
                    self._AddFailedCheck(
                        message=(
                            f"Emitter state attribute '{name}' has length {len(value)} "
                            f"but omni:sensor:Core:numberOfEmitters is {num_emitters}."
                        ),
                        at=prim,
                        requirement=cap.LidarRequirements.LI_002,
                    )

        # --- Check 2 & 3: rangeCount vs range array lengths ---
        range_count_attr = prim.GetAttribute("omni:sensor:Core:rangeCount")
        range_count = 1  # default per C++ KeyParamHelper
        if range_count_attr:
            rc = range_count_attr.Get()
            if rc is not None and rc > 0:
                range_count = int(rc)

        for array_attr_name in ("omni:sensor:Core:rangesMinM", "omni:sensor:Core:rangesMaxM"):
            arr_attr = prim.GetAttribute(array_attr_name)
            if not arr_attr:
                continue
            arr = arr_attr.Get()
            if arr is None or len(arr) == 0:
                continue
            if len(arr) != range_count:
                self._AddFailedCheck(
                    message=(
                        f"'{array_attr_name}' has length {len(arr)} "
                        f"but omni:sensor:Core:rangeCount is {range_count}."
                    ),
                    at=prim,
                    requirement=cap.LidarRequirements.LI_002,
                )


_MINIMUM_SCAN_RATE_HZ = 0.466  # signed 32-bit ns overflow limit from LidarCoreSensorCheckerImpl


@register_rule("LidarSensor")
@register_requirements(cap.LidarRequirements.LI_003)
class OmniLidarScanRateChecker(BaseRuleChecker):
    """
    Validate that omni:sensor:Core:scanRateBaseHz is at least 0.466 Hz (LI.003).

    The OmniLidar runtime stores per-point time offsets as signed 32-bit
    nanosecond integers. At scan rates below 0.466 Hz the nanosecond duration
    of one scan cycle exceeds the signed 32-bit range (~2.147 s), causing
    integer overflow in the timeOffsetNs output field.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.GetPrimTypeInfo().GetTypeName() != "OmniLidar":
            return

        rate_attr = prim.GetAttribute("omni:sensor:Core:scanRateBaseHz")
        if not rate_attr:
            return
        rate = rate_attr.Get()
        if rate is None:
            return

        rate_hz = float(rate)
        if rate_hz < _MINIMUM_SCAN_RATE_HZ:
            self._AddFailedCheck(
                message=(
                    f"omni:sensor:Core:scanRateBaseHz is {rate_hz} Hz, below the minimum "
                    f"supported rate of {_MINIMUM_SCAN_RATE_HZ} Hz. Scan rates below this "
                    f"threshold cause timeOffsetNs integer overflow (signed 32-bit nanoseconds)."
                ),
                at=prim,
                requirement=cap.LidarRequirements.LI_003,
            )


@register_rule("LidarSensor")
@register_requirements(cap.LidarRequirements.LI_004)
class OmniLidarSolidStateChecker(BaseRuleChecker):
    """
    Validate solid-state OmniLidar ray count consistency (LI.004).

    For solid-state lidars (omni:sensor:Core:scanType = "SOLID_STATE") the
    sum of all elements in omni:sensor:Core:numRaysPerLine must equal
    omni:sensor:Core:numberOfEmitters. This mirrors the validateNumRaysPerLine
    check in LidarCoreSensorCheckerImpl, which is only applied for solid-state
    scan types.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if prim.GetPrimTypeInfo().GetTypeName() != "OmniLidar":
            return

        scan_type_attr = prim.GetAttribute("omni:sensor:Core:scanType")
        if not scan_type_attr:
            return
        scan_type = scan_type_attr.Get()
        if scan_type != "SOLID_STATE":
            return

        num_emitters_attr = prim.GetAttribute("omni:sensor:Core:numberOfEmitters")
        if not num_emitters_attr:
            return
        rays_attr = prim.GetAttribute("omni:sensor:Core:numRaysPerLine")
        if not rays_attr:
            return

        num_emitters = num_emitters_attr.Get()
        rays = rays_attr.Get()
        if num_emitters is None or rays is None or len(rays) == 0:
            return

        total_rays = int(sum(rays))
        if total_rays != int(num_emitters):
            self._AddFailedCheck(
                message=(
                    f"Solid-state OmniLidar: sum of omni:sensor:Core:numRaysPerLine is {total_rays} "
                    f"but omni:sensor:Core:numberOfEmitters is {num_emitters}. "
                    f"The total ray count across all lines must equal the number of emitters."
                ),
                at=prim,
                requirement=cap.LidarRequirements.LI_004,
            )

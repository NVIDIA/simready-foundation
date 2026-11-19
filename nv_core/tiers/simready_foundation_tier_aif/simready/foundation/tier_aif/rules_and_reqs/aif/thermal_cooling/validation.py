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
from typing import Optional

import usd_validation_nvidia
import simready.foundation.tier_aif.requirements as cap
from pxr import Sdf, Usd

from .. import _stage, equipment_classes
from ..connection_points.validation import (
    _connection_point_domain,
    _cp_attribute,
    _find_connection_points_scope,
    _iter_connection_points,
    _token_value,
    _uses_property_vocabulary,
)

# Which classes have a cooling loop, and the connection point prefixes each one
# must carry, are declared in config/aif-equipment-<class>.json.


def _get_asset_class(stage: Usd.Stage) -> Optional[str]:
    """Return the normalised equipment class the asset declares."""
    raw = _stage.asset_class_value(stage)
    return equipment_classes.normalize(raw) if raw is not None else None


def _get_connection_point_names(stage: Usd.Stage):
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return []
    for child in default_prim.GetChildren():
        if child.GetName() == "ConnectionPoints" and child.GetTypeName() == "Scope":
            return [p.GetName() for p in Usd.PrimRange(child) if p != child]
    return []


@usd_validation_nvidia.register_rule("AIF-ThermalCooling")
@usd_validation_nvidia.register_requirements(cap.ThermalCoolingRequirements.TC_001, override=True)
class AIFNominalCoolingCapacityChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that cooling equipment has aif:spec:nominalCoolingCapacity."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class = _get_asset_class(stage)
        if asset_class not in equipment_classes.THERMAL_CLASSES:
            return  # Not a cooling equipment asset: skip

        prim_spec = _stage.properties_prim_spec(stage)
        if not prim_spec:
            return  # AM.001 already reported this

        if "aif:spec:nominalCoolingCapacity" not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ThermalCoolingRequirements.TC_001,
                message=f"Cooling equipment (assetClass='{asset_class}') is missing required attribute: aif:spec:nominalCoolingCapacity.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-ThermalCooling")
@usd_validation_nvidia.register_requirements(cap.ThermalCoolingRequirements.TC_002, override=True)
class AIFThermalCoolingConnectionPointsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Cross-domain check: cooling equipment must have matching piping connection points."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class = _get_asset_class(stage)
        if asset_class not in equipment_classes.THERMAL_CLASSES:
            return

        required_types = equipment_classes.THERMAL_CP_PREFIXES.get(asset_class, ())
        if not required_types:
            return

        if _uses_property_vocabulary(stage):
            scope = _find_connection_points_scope(stage)
            points = _iter_connection_points(scope) if scope is not None else []
            thermal_ports = {
                (_token_value(_cp_attribute(prim, "system")),
                 _token_value(_cp_attribute(prim, "direction")))
                for prim in points if _connection_point_domain(prim)[0] == "thermal"
            }
            missing_types = []
            for cp_type in required_types:
                system, direction = cp_type.rsplit("_", 1)
                # "liq" describes a liquid interface, not a closed system token.
                # CRAH exemplars use FWS; other authors may use LIQ.
                if not any(d == direction and (system == "liq" or s == system.upper())
                           for s, d in thermal_ports):
                    missing_types.append(cp_type)
            if missing_types:
                self._AddFailedCheck(
                    requirement=cap.ThermalCoolingRequirements.TC_002,
                    message=(
                        f"Cooling equipment (assetClass='{asset_class}') is missing connection point prims "
                        f"for: {', '.join(missing_types)}. Expected simready:connectionPoint:domain "
                        "= 'thermal' with matching direction and, for FWS/TCS loops, system properties."
                    ),
                    at=stage,
                )
            return

        cp_names = _get_connection_point_names(stage)
        missing_types = []
        for cp_type in required_types:
            if not any(cp_type in name for name in cp_names):
                missing_types.append(cp_type)

        if missing_types:
            self._AddFailedCheck(
                requirement=cap.ThermalCoolingRequirements.TC_002,
                message=(
                    f"Cooling equipment (assetClass='{asset_class}') is missing connection point prims "
                    f"for: {', '.join(missing_types)}. "
                    f"Expected prim names matching: "
                    + ", ".join(f"*_{t}_*" for t in missing_types)
                ),
                at=stage,
            )

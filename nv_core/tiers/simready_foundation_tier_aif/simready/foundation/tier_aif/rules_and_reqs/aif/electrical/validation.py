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
#
# NOTE: EL.001-003 attribute names are not harmonized across equipment classes.
# This mapping table must be updated if upstream CSV templates harmonize naming.
from typing import Optional

import usd_validation_nvidia
import simready.foundation.tier_aif.requirements as cap
from pxr import Sdf, Usd

from .. import _stage, equipment_classes
from ..connection_points.validation import (
    _connection_point_domain,
    _find_connection_points_scope,
    _iter_connection_points,
    _uses_property_vocabulary,
)

# Which classes take an AC supply, and the attribute name each one uses for the
# three AC concepts EL.001-EL.003 check, are declared in
# config/aif-equipment-<class>.json. The names differ by class.


def _get_asset_class_and_prim(stage: Usd.Stage):
    """Return the normalised equipment class and the properties prim spec."""
    prim_spec = _stage.properties_prim_spec(stage)
    raw = _stage.asset_class_value(stage)
    if raw is None:
        return None, prim_spec
    return equipment_classes.normalize(raw), prim_spec


def _get_connection_point_names(stage: Usd.Stage):
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return []
    for child in default_prim.GetChildren():
        if child.GetName() == "ConnectionPoints" and child.GetTypeName() == "Scope":
            return [p.GetName() for p in Usd.PrimRange(child) if p != child]
    return []


@usd_validation_nvidia.register_rule("AIF-Electrical")
@usd_validation_nvidia.register_requirements(cap.ElectricalRequirements.EL_001, override=True)
class AIFNominalVoltageChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that AC-powered equipment has the appropriate nominal voltage attribute."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, prim_spec = _get_asset_class_and_prim(stage)
        if asset_class not in equipment_classes.AC_CLASSES or prim_spec is None:
            return
        attr_name = equipment_classes.AC_ATTRIBUTE[asset_class]["nominalVoltage"]
        if attr_name not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_001,
                message=f"AC-powered equipment (assetClass='{asset_class}') is missing nominal voltage attribute: {attr_name}.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Electrical")
@usd_validation_nvidia.register_requirements(cap.ElectricalRequirements.EL_002, override=True)
class AIFPowerRatingChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that AC-powered equipment has the appropriate power rating attribute."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, prim_spec = _get_asset_class_and_prim(stage)
        if asset_class not in equipment_classes.AC_CLASSES or prim_spec is None:
            return
        attr_name = equipment_classes.AC_ATTRIBUTE[asset_class]["powerRating"]
        if attr_name not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_002,
                message=f"AC-powered equipment (assetClass='{asset_class}') is missing power rating attribute: {attr_name}.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Electrical")
@usd_validation_nvidia.register_requirements(cap.ElectricalRequirements.EL_003, override=True)
class AIFElectricalFrequencyChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that AC-powered equipment has the appropriate electrical frequency attribute."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, prim_spec = _get_asset_class_and_prim(stage)
        if asset_class not in equipment_classes.AC_CLASSES or prim_spec is None:
            return
        attr_name = equipment_classes.AC_ATTRIBUTE[asset_class]["frequency"]
        if attr_name not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_003,
                message=f"AC-powered equipment (assetClass='{asset_class}') is missing frequency attribute: {attr_name}.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Electrical")
@usd_validation_nvidia.register_requirements(cap.ElectricalRequirements.EL_004, override=True)
class AIFElectricalConnectionPointsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Cross-domain check: AC-powered equipment must have electrical connection points."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        asset_class, _ = _get_asset_class_and_prim(stage)
        if asset_class not in equipment_classes.AC_CLASSES:
            return

        if _uses_property_vocabulary(stage):
            scope = _find_connection_points_scope(stage)
            points = _iter_connection_points(scope) if scope is not None else []
            if not any(_connection_point_domain(prim)[0] == "electrical" for prim in points):
                self._AddFailedCheck(
                    requirement=cap.ElectricalRequirements.EL_004,
                    message=(
                        f"AC-powered equipment (assetClass='{asset_class}') is missing an electrical connection point prim. "
                        "Expected at least one prim with simready:connectionPoint:domain = 'electrical'."
                    ),
                    at=stage,
                )
            return

        cp_names = _get_connection_point_names(stage)
        if not any("electrical_nominal_voltage" in name for name in cp_names):
            self._AddFailedCheck(
                requirement=cap.ElectricalRequirements.EL_004,
                message=(
                    f"AC-powered equipment (assetClass='{asset_class}') is missing an electrical connection point prim. "
                    "Expected at least one prim matching: *_electrical_nominal_voltage_*"
                ),
                at=stage,
            )

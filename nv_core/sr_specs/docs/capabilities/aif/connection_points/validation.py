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
import re
from typing import Optional

import omni.asset_validator
import omni.capabilities as cap
from pxr import Sdf, Usd, UsdGeom

# ---------------------------------------------------------------------------
# Valid connection point type prefixes per the AIF naming convention table.
# Pattern: <vendor>_<TYPE_PREFIX>[_<suffix>]
# ---------------------------------------------------------------------------
_VALID_TYPE_PREFIXES = (
    "liq_supply",
    "liq_return",
    "fws_supply",
    "fws_return",
    "tcs_supply",
    "tcs_return",
    "electrical_nominal_voltage",
    "airvent_intake",
    "airvent_outflow",
)

# Sorted longest-first so that longer prefixes (e.g. "electrical_nominal_voltage")
# are matched before any hypothetical shorter partial overlap.
_VALID_TYPE_PREFIXES_SORTED = sorted(_VALID_TYPE_PREFIXES, key=len, reverse=True)

_VENDOR_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _find_connection_points_scope(stage: Usd.Stage) -> Optional[Usd.Prim]:
    """Return the ConnectionPoints Scope prim under the default prim, or None."""
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return None
    for child in default_prim.GetChildren():
        if child.GetName() == "ConnectionPoints" and child.GetTypeName() == "Scope":
            return child
    return None


def _find_connection_points_sublayer(stage: Usd.Stage) -> Optional[str]:
    """Return the first sublayer path whose filename contains 'connectionpoints'
    and has a USD extension (.usd, .usda, .usdc), or None."""
    root_layer = stage.GetRootLayer()
    for sublayer_path in root_layer.subLayerPaths:
        filename = sublayer_path.replace("\\", "/").split("/")[-1].lower()
        if "connectionpoints" in filename and filename.endswith((".usd", ".usda", ".usdc")):
            return sublayer_path
    return None


def _matches_cp_naming(name: str) -> bool:
    """Check whether *name* follows the <vendor>_<type_prefix>[_<suffix>] convention.

    Supports multi-word vendor names (e.g. ``johnson_controls``) by scanning for
    each known type prefix and validating that the portion before it is a valid
    vendor string (one or more underscore-separated lowercase-alphanumeric tokens).
    """
    for type_prefix in _VALID_TYPE_PREFIXES_SORTED:
        sep_marker = f"_{type_prefix}_"
        end_marker = f"_{type_prefix}"

        # Type prefix in the middle of the name (vendor + type + suffix)
        idx = name.find(sep_marker)
        if idx > 0:
            vendor = name[:idx]
            if _VENDOR_PATTERN.match(vendor):
                return True

        # Type prefix at the end of the name (vendor + type, no suffix)
        if name.endswith(end_marker) and len(name) > len(end_marker):
            vendor = name[: len(name) - len(end_marker)]
            if _VENDOR_PATTERN.match(vendor):
                return True

    return False


def _resolve_sublayer(stage: Usd.Stage, sublayer_path: str) -> Optional[Sdf.Layer]:
    """Try to resolve and open a sublayer path relative to the stage's root layer.

    Uses the same resolution strategy as _find_properties_sublayer in
    metadata/validation.py: layer stack lookup, then ComputeAssetPathRelativeToLayer,
    then FindRelativeToLayer.
    """
    root_layer = stage.GetRootLayer()

    # Check layers already in the composed stack
    target_filename = sublayer_path.replace("\\", "/").split("/")[-1].lower()
    for layer in stage.GetLayerStack():
        layer_filename = layer.identifier.replace("\\", "/").split("/")[-1].lower()
        if target_filename == layer_filename:
            return layer

    # Resolve relative to the root layer
    resolved = Sdf.ComputeAssetPathRelativeToLayer(root_layer, sublayer_path)
    layer = Sdf.Layer.FindOrOpen(resolved)
    if layer:
        return layer

    layer = Sdf.Layer.FindRelativeToLayer(root_layer, sublayer_path)
    if layer:
        return layer

    return None


# ---------------------------------------------------------------------------
# CP.001 - ConnectionPoints Scope Structure
# ---------------------------------------------------------------------------

@omni.asset_validator.register_rule("AIF-ConnectionPoints")
@omni.asset_validator.register_requirements(cap.ConnectionPointsRequirements.CP_001, override=True)
class AIFConnectionPointsScopeChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that a ConnectionPoints Scope prim exists under the default prim
    and contains at least one connection point prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_001,
                message=(
                    "Stage has no default prim. A default prim is required before "
                    "a ConnectionPoints Scope can be created under it."
                ),
                at=stage,
            )
            return

        scope = _find_connection_points_scope(stage)
        if scope is None:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_001,
                message=(
                    "Default prim has no ConnectionPoints Scope child. "
                    "Create a Scope named 'ConnectionPoints' as a direct child of "
                    f"'{default_prim.GetName()}' to organize thermal, electrical, "
                    "and airflow connection point geometry."
                ),
                at=default_prim,
            )
            return

        # Scope exists but must not be empty
        children = list(scope.GetChildren())
        if not children:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_001,
                message=(
                    "ConnectionPoints Scope is empty - connection point mesh prims "
                    "are missing. Add connection point geometry prims inside the "
                    "ConnectionPoints Scope."
                ),
                at=scope,
            )


# CP.002 (connection-point-geometry-type) - deferred to v0.2.0
# CP.003 (connection-point-purpose-guide) - deferred to v0.2.0


# ---------------------------------------------------------------------------
# CP.004 - Connection Point Naming Convention
# ---------------------------------------------------------------------------

@omni.asset_validator.register_rule("AIF-ConnectionPoints")
@omni.asset_validator.register_requirements(cap.ConnectionPointsRequirements.CP_004, override=True)
class AIFConnectionPointNamingChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that all prims under ConnectionPoints follow the
    <vendor>_<type_prefix>[_<suffix>] naming pattern with a valid AIF type prefix."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        scope = _find_connection_points_scope(stage)
        if scope is None:
            return  # CP.001 already reported this

        # Skip if scope is empty - CP.001 handles that failure
        if not list(scope.GetChildren()):
            return

        invalid = []
        for prim in Usd.PrimRange(scope):
            if prim == scope:
                continue
            name = prim.GetName()
            if not _matches_cp_naming(name):
                invalid.append(name)

        if invalid:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_004,
                message=(
                    f"{len(invalid)} connection point prim(s) do not follow the "
                    f"<vendor>_<type>_<suffix> naming convention: {', '.join(invalid[:5])}"
                    + (f" ... and {len(invalid) - 5} more" if len(invalid) > 5 else "")
                    + f". Valid type prefixes: {', '.join(_VALID_TYPE_PREFIXES)}"
                ),
                at=stage,
            )


# ---------------------------------------------------------------------------
# CP.005 - Connection Points Composition
# ---------------------------------------------------------------------------

@omni.asset_validator.register_rule("AIF-ConnectionPoints")
@omni.asset_validator.register_requirements(cap.ConnectionPointsRequirements.CP_005, override=True)
class AIFConnectionPointsCompositionChecker(omni.asset_validator.BaseRuleChecker):
    """Checks that a *_ConnectionPoints.usd/.usda/.usdc sublayer is composed
    into the stage and that the sublayer file can be resolved."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        sublayer_path = _find_connection_points_sublayer(stage)
        if sublayer_path is None:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_005,
                message=(
                    "Missing connection points sublayer. "
                    "Connection points must be saved as "
                    "<AssetName>_ConnectionPoints.usd (or .usda/.usdc) "
                    "and added as a sublayer in the main stage file."
                ),
                at=stage,
            )
            return

        # Verify the sublayer file actually resolves on disk
        layer = _resolve_sublayer(stage, sublayer_path)
        if layer is None:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_005,
                message=(
                    f"Connection points sublayer '{sublayer_path}' is listed "
                    "but cannot be resolved. Verify the file exists at the "
                    "expected path relative to the main stage file."
                ),
                at=stage,
            )


# CP.006 (connection-point-alignment) - deferred to v0.2.0+

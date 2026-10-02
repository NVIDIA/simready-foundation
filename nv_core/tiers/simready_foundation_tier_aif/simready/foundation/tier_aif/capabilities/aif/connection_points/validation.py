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

import usd_validation_nvidia
import simready.foundation.tier_aif.requirements as cap

from .. import _stage
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
# v0.2.0 connection point property vocabulary.
#
# The base namespace applies to every connection point. The domain namespace a
# connection point uses is named by its simready:connectionPoint:domain value.
# ---------------------------------------------------------------------------
_CP_NAMESPACE = "simready:connectionPoint"

# Base namespace: property suffix -> (declared type, what the property states).
_BASE_PROPERTIES = {
    "domain": (Sdf.ValueTypeNames.Token, "the physical domain of the connection"),
    "direction": (Sdf.ValueTypeNames.Token, "the flow or signal direction"),
    "system": (Sdf.ValueTypeNames.Token, "the system classification within the facility"),
    "disconnectType": (Sdf.ValueTypeNames.Token, "the physical disconnect mechanism"),
    "serviceClearance": (Sdf.ValueTypeNames.Float, "the maintenance access distance in meters"),
}

# Renamed to "domain" before v0.2.0. A connection point carrying the old name is
# warned and its value read as the domain.
_DEPRECATED_DOMAIN_ALIAS = "type"

# Domain namespace: domain -> {property suffix: declared type}. Order follows the
# tables in the requirement so reported property lists read in the same order.
_DOMAIN_PROPERTIES = {
    "thermal": {
        "portDiameter": Sdf.ValueTypeNames.Float,
        "matingDepth": Sdf.ValueTypeNames.Float,
        "designFlowRate": Sdf.ValueTypeNames.Float,
        "maxFlowRate": Sdf.ValueTypeNames.Float,
        "designTemperature": Sdf.ValueTypeNames.Float,
        "maxTemperature": Sdf.ValueTypeNames.Float,
        "operatingPressure": Sdf.ValueTypeNames.Float,
        "maxPressure": Sdf.ValueTypeNames.Float,
        "fluidType": Sdf.ValueTypeNames.Token,
        "flangeRating": Sdf.ValueTypeNames.Token,
        "flangeSize": Sdf.ValueTypeNames.Token,
    },
    "electrical": {
        "matingDepth": Sdf.ValueTypeNames.Float,
        "nominalVoltage": Sdf.ValueTypeNames.Float,
        "maxCurrent": Sdf.ValueTypeNames.Float,
        "phases": Sdf.ValueTypeNames.Int,
        "frequency": Sdf.ValueTypeNames.Float,
        "connectorType": Sdf.ValueTypeNames.Token,
        "ratedPower": Sdf.ValueTypeNames.Float,
        "breakerRating": Sdf.ValueTypeNames.Float,
        "powerFactor": Sdf.ValueTypeNames.Float,
    },
    "network": {
        "portWidth": Sdf.ValueTypeNames.Float,
        "portHeight": Sdf.ValueTypeNames.Float,
        "matingDepth": Sdf.ValueTypeNames.Float,
        "portType": Sdf.ValueTypeNames.Token,
        "protocol": Sdf.ValueTypeNames.Token,
        "dataRate": Sdf.ValueTypeNames.Token,
        "medium": Sdf.ValueTypeNames.Token,
        "fabricRole": Sdf.ValueTypeNames.Token,
        "supportedLineRates": Sdf.ValueTypeNames.TokenArray,
        "supportedConfigurations": Sdf.ValueTypeNames.TokenArray,
        "allowedTransceivers": Sdf.ValueTypeNames.TokenArray,
        "hotPlugCapable": Sdf.ValueTypeNames.Bool,
    },
    "airflow": {
        "interfaceWidth": Sdf.ValueTypeNames.Float,
        "interfaceHeight": Sdf.ValueTypeNames.Float,
        "freeAreaRatio": Sdf.ValueTypeNames.Float,
        "designAirflowRate": Sdf.ValueTypeNames.Float,
        "maxAirflowRate": Sdf.ValueTypeNames.Float,
        "designTemperature": Sdf.ValueTypeNames.Float,
        "maxTemperature": Sdf.ValueTypeNames.Float,
        "staticPressure": Sdf.ValueTypeNames.Float,
        "filterType": Sdf.ValueTypeNames.Token,
    },
}

# Example token values from the requirement tables. The sets are open: a value
# outside them is reported for authoring review and never failed.
_BASE_TOKEN_VALUES = {
    "domain": ("thermal", "electrical", "network", "airflow"),
    "direction": ("supply", "return", "input", "output", "bidirectional"),
    "system": ("FWS", "TCS", "power", "BMS", "high_speed_data", "mgmt", "equipment_cooling"),
    "disconnectType": (
        "flanged", "quick_disconnect", "hardwired", "RJ45", "OSFP", "blind_mate", "open_vent",
    ),
}

_DOMAIN_TOKEN_VALUES = {
    ("thermal", "fluidType"): (
        "water", "glycol_water_25", "glycol_water_30", "glycol_water_50",
        "refrigerant_R410A", "refrigerant_R134a", "refrigerant_R454B", "dielectric",
    ),
    ("electrical", "connectorType"): ("hardwired", "IEC_60309", "NEMA_L21_30", "dry_contact"),
    ("network", "portType"): ("RJ45", "SFP_plus", "QSFP28", "QSFP_DD", "OSFP"),
    ("network", "protocol"): ("BACnet_IP", "Modbus_TCP", "SNMP", "Ethernet"),
    ("network", "dataRate"): ("100Mbps", "25GbE", "100GbE", "400GbE", "800GbE"),
    ("network", "medium"): ("copper", "fiber", "DAC"),
    ("network", "fabricRole"): ("compute", "storage", "mgmt", "bms"),
    ("airflow", "filterType"): ("MERV_8", "none"),
}

# A dry contact is a relay output with no voltage of its own, so the three
# electrical properties that describe power distribution do not apply to it.
_DRY_CONTACT_CONNECTOR = "dry_contact"
_DRY_CONTACT_OMITTED_PROPERTIES = ("phases", "frequency", "powerFactor")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _uses_property_vocabulary(stage: Usd.Stage) -> bool:
    """Select the 0.2.0 vocabulary from AM.005's Properties-layer declaration.

    TC.002 and EL.004 are shared by both published feature versions. Their
    standalone rule invocation has no profile context, so use the asset's
    declared AIF version. Keep the legacy path for older/unversioned assets.
    """
    prim_spec = _stage.properties_prim_spec(stage)
    if not prim_spec:
        return False
    attr = prim_spec.attributes.get("aif:core:simreadyVersion")
    return attr is not None and attr.default == "0.2.0"


def _find_connection_points_scope(stage: Usd.Stage) -> Optional[Usd.Prim]:
    """Return the ConnectionPoints Scope prim under the default prim, or None."""
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return None
    for child in default_prim.GetChildren():
        if child.GetName() == "ConnectionPoints" and child.GetTypeName() == "Scope":
            return child
    return None


def _find_misplaced_scopes(stage: Usd.Stage) -> list:
    """Return every prim named ConnectionPoints that is not the one CP.001 wants.

    One scope, a direct child of the default prim. A scope deeper in the tree
    holds connection points that every connection point rule then walks past:
    CP.004 and CP.010-012 all start from the scope CP.001 located, so an asset
    that nests its scope reports nothing from any of them.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        return []
    expected = default_prim.GetPath().AppendChild("ConnectionPoints")
    return [
        prim
        for prim in Usd.PrimRange(default_prim)
        if prim.GetName() == "ConnectionPoints" and prim.GetPath() != expected
    ]


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


_resolve_sublayer = _stage.resolve_sublayer


def _split_cp_property(property_name: str) -> tuple[Optional[str], Optional[str]]:
    """Split a simready:connectionPoint: property into (namespace, suffix).

    A base property returns (None, "domain"); a domain property returns
    ("thermal", "portDiameter"). A property outside the namespace returns
    (None, None).
    """
    prefix = f"{_CP_NAMESPACE}:"
    if not property_name.startswith(prefix):
        return None, None
    parts = property_name[len(prefix):].split(":")
    if len(parts) == 1:
        return None, parts[0]
    return parts[0], ":".join(parts[1:])


def _cp_attribute(prim: Usd.Prim, suffix: str) -> Optional[Usd.Attribute]:
    """Return the simready:connectionPoint:<suffix> attribute on *prim* if it
    holds an authored value, or None.

    A property set to 0.0 counts as authored; a property that is absent, or
    declared without a value, does not.
    """
    attr = prim.GetAttribute(f"{_CP_NAMESPACE}:{suffix}")
    if not attr or not attr.HasAuthoredValue():
        return None
    return attr


def _token_value(attr: Optional[Usd.Attribute]) -> Optional[str]:
    """Return a token attribute's value as a non-empty string, or None."""
    if attr is None:
        return None
    value = attr.Get()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _domain_namespaces(prim: Usd.Prim) -> dict[str, list[str]]:
    """Return {namespace: [property suffixes]} for every
    simready:connectionPoint:<namespace>:* property on *prim*.

    Declared properties count whether or not they hold a value, so a second
    domain left behind by an edit is still visible.
    """
    namespaces: dict[str, list[str]] = {}
    for property_name in prim.GetPropertyNames():
        namespace, suffix = _split_cp_property(property_name)
        if namespace is None:
            continue
        namespaces.setdefault(namespace, []).append(suffix)
    return namespaces


def _connection_point_domain(prim: Usd.Prim) -> tuple[Optional[str], bool]:
    """Return (domain value, read from the deprecated alias) for *prim*.

    simready:connectionPoint:type is the deprecated alias for domain, so its
    value is read as the domain when domain itself is absent.
    """
    domain = _token_value(_cp_attribute(prim, "domain"))
    if domain is not None:
        return domain, False
    alias = _token_value(_cp_attribute(prim, _DEPRECATED_DOMAIN_ALIAS))
    if alias is not None:
        return alias, True
    return None, False


def _missing_base_properties(prim: Usd.Prim) -> list[str]:
    """Return the base namespace property suffixes *prim* does not carry.

    A token authored as an empty string states nothing and counts as missing;
    serviceClearance set to 0.0 is a statement and does not.
    """
    missing = []
    for suffix, (type_name, _) in _BASE_PROPERTIES.items():
        attr = _cp_attribute(prim, suffix)
        if attr is not None and (
            type_name != Sdf.ValueTypeNames.Token or _token_value(attr) is not None
        ):
            continue
        if suffix == "domain" and _connection_point_domain(prim)[0] is not None:
            continue  # carried by the deprecated alias
        missing.append(suffix)
    return missing


def _iter_connection_points(scope: Usd.Prim) -> list[Usd.Prim]:
    """Return the connection point prims under the ConnectionPoints *scope*.

    A connection point is a direct child of the scope, or a deeper descendant
    that authors a property in the simready:connectionPoint: namespace.
    """
    points = []
    for prim in Usd.PrimRange(scope):
        if prim == scope:
            continue
        if prim.GetParent() == scope:
            points.append(prim)
            continue
        if any(name.startswith(f"{_CP_NAMESPACE}:") for name in prim.GetPropertyNames()):
            points.append(prim)
    return points


# ---------------------------------------------------------------------------
# CP.001 - ConnectionPoints Scope Structure
# ---------------------------------------------------------------------------

@usd_validation_nvidia.register_rule("AIF-ConnectionPoints")
@usd_validation_nvidia.register_requirements(cap.ConnectionPointsRequirements.CP_001, override=True)
class AIFConnectionPointsScopeChecker(usd_validation_nvidia.BaseRuleChecker):
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

        for misplaced in _find_misplaced_scopes(stage):
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_001,
                message=(
                    f"ConnectionPoints scope at <{misplaced.GetPath()}> is not a direct "
                    f"child of the default prim '{default_prim.GetName()}'. Connection "
                    "points are collected from one scope directly under the default prim; "
                    "the rules that read them do not descend into a nested scope, so every "
                    "connection point under this one goes unchecked."
                ),
                at=misplaced,
            )

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


# CP.002 (connection-point-geometry-type) - v0.1.0 only, no checker. CP.010
# replaces it: v0.2.0 requires an Xform, which a Plane or Disk mesh is not.
# CP.003 (connection-point-purpose-guide) - no checker of its own. CP.010
# enforces purpose = "guide" for v0.2.0.


# ---------------------------------------------------------------------------
# CP.004 - Connection Point Naming Convention
# ---------------------------------------------------------------------------

@usd_validation_nvidia.register_rule("AIF-ConnectionPoints")
@usd_validation_nvidia.register_requirements(cap.ConnectionPointsRequirements.CP_004, override=True)
class AIFConnectionPointNamingChecker(usd_validation_nvidia.BaseRuleChecker):
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

@usd_validation_nvidia.register_rule("AIF-ConnectionPoints")
@usd_validation_nvidia.register_requirements(cap.ConnectionPointsRequirements.CP_005, override=True)
class AIFConnectionPointsCompositionChecker(usd_validation_nvidia.BaseRuleChecker):
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


# CP.006 (connection-point-alignment) - deferred. Depends on an automated
# placement workflow during CAD-to-USD export; neither feature version lists it.


# ---------------------------------------------------------------------------
# v0.2.0 property vocabulary - CP.010, CP.011 and CP.012.
#
# The v0.1.0 checkers above read geometry prims and never inspect the
# simready:connectionPoint: namespace; the three below read only that namespace.
# Two v0.1.0 requirements reject a conformant v0.2.0 asset, so the versions are
# kept apart by the feature version a profile selects rather than by any runtime
# switch in this file.
#
#   CP.004 walks every prim under the ConnectionPoints scope requiring
#   <vendor>_<type>_<suffix>, while v0.2.0 states prim names carry no meaning and
#   are not validated. Every prim name the v0.2.0 spec offers as an example
#   ("fws_supply_main", "osfp_port_01") fails _matches_cp_naming, and the network
#   domain has no valid type prefix in _VALID_TYPE_PREFIXES.
#
#   CP.002 requires Plane or Disk geometry where CP.010 requires an Xform, which
#   is not a surface at all. CP.010 supersedes it.
#
# CP.003 requires purpose = "guide", which CP.010 also requires, so it adds
# nothing to the v0.2.0 set and has no validator of its own. The loader skips
# any feature listing a requirement with no registered rule, so leaving CP.003
# in the list kept the whole feature from registering.
#
# The -0.2.0- feature JSON therefore lists none of CP.002, CP.003 or CP.004.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CP.010 - Connection Point Prim Structure
# ---------------------------------------------------------------------------

@usd_validation_nvidia.register_rule("AIF-ConnectionPoints")
@usd_validation_nvidia.register_requirements(cap.ConnectionPointsRequirements.CP_010, override=True)
class AIFConnectionPointPrimStructureChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that every connection point under the ConnectionPoints Scope is an
    Xform with purpose = "guide", carries simready:connectionPoint:domain and
    simready:connectionPoint:direction, and uses a single domain namespace."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        scope = _find_connection_points_scope(stage)
        if scope is None:
            return  # CP.001 already reported this

        for prim in _iter_connection_points(scope):
            self._CheckPrimType(prim)
            self._CheckPurpose(prim)
            self._CheckMandatoryProperties(prim)
            self._CheckSingleDomain(prim)

    def _CheckPrimType(self, prim: Usd.Prim) -> None:
        type_name = str(prim.GetTypeName()) or "typeless"
        if type_name == "Xform":
            return
        self._AddFailedCheck(
            requirement=cap.ConnectionPointsRequirements.CP_010,
            message=(
                f"Connection point '{prim.GetName()}' is a {type_name} prim. "
                "Author connection points as Xform prims: the Xform records where "
                "the interface sits and which way it faces, and the "
                "simready:connectionPoint: properties describe what it is."
            ),
            at=prim,
        )

    def _CheckPurpose(self, prim: Usd.Prim) -> None:
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            return  # the prim type failure above covers this
        purpose = imageable.ComputePurpose()
        if purpose == UsdGeom.Tokens.guide:
            return
        self._AddFailedCheck(
            requirement=cap.ConnectionPointsRequirements.CP_010,
            message=(
                f"Connection point '{prim.GetName()}' resolves to purpose "
                f"'{purpose}'. Set purpose = \"guide\" to keep connection points "
                "out of render and out of physics collision."
            ),
            at=prim,
        )

    def _CheckMandatoryProperties(self, prim: Usd.Prim) -> None:
        if _connection_point_domain(prim)[0] is None:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_010,
                message=(
                    f"Connection point '{prim.GetName()}' has no "
                    "simready:connectionPoint:domain value. Author it as a token "
                    "naming the physical domain of the connection, for example "
                    "\"thermal\" or \"electrical\". A connection point without a "
                    "domain cannot be classified by a consuming tool."
                ),
                at=prim,
            )
        if _token_value(_cp_attribute(prim, "direction")) is None:
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_010,
                message=(
                    f"Connection point '{prim.GetName()}' has no "
                    "simready:connectionPoint:direction value. Author it as a token "
                    "naming the flow or signal direction, for example \"supply\" or "
                    "\"return\"."
                ),
                at=prim,
            )

    def _CheckSingleDomain(self, prim: Usd.Prim) -> None:
        namespaces = sorted(_domain_namespaces(prim))
        if len(namespaces) < 2:
            return
        self._AddFailedCheck(
            requirement=cap.ConnectionPointsRequirements.CP_010,
            message=(
                f"Connection point '{prim.GetName()}' authors properties in "
                f"{len(namespaces)} domain namespaces: {', '.join(namespaces)}. "
                "A connection point carries exactly one domain. Model an interface "
                "that carries several services at once as co-located prims sharing "
                "a transform, one per domain."
            ),
            at=prim,
        )


# ---------------------------------------------------------------------------
# CP.011 - Connection Point Base Namespace
# ---------------------------------------------------------------------------

@usd_validation_nvidia.register_rule("AIF-ConnectionPoints")
@usd_validation_nvidia.register_requirements(cap.ConnectionPointsRequirements.CP_011, override=True)
class AIFConnectionPointBaseNamespaceChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that every connection point carries all five base namespace
    properties with their declared types, warns on the deprecated type alias,
    and reports token values outside the current example sets."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        scope = _find_connection_points_scope(stage)
        if scope is None:
            return  # CP.001 already reported this

        for prim in _iter_connection_points(scope):
            self._CheckDeprecatedAlias(prim)
            self._CheckPropertiesPresent(prim)
            self._CheckPropertyTypes(prim)
            self._CheckTokenValues(prim)
            self._CheckServiceClearance(prim)

    def _CheckDeprecatedAlias(self, prim: Usd.Prim) -> None:
        if _cp_attribute(prim, _DEPRECATED_DOMAIN_ALIAS) is None:
            return
        self._AddWarning(
            requirement=cap.ConnectionPointsRequirements.CP_011,
            message=(
                f"Connection point '{prim.GetName()}' carries "
                "simready:connectionPoint:type, a deprecated alias for "
                "simready:connectionPoint:domain, and its value is read as the "
                "domain. Rename the property; the old name will not survive "
                "schema promotion."
            ),
            at=prim,
        )

    def _CheckPropertiesPresent(self, prim: Usd.Prim) -> None:
        missing = _missing_base_properties(prim)
        if not missing:
            return
        self._AddFailedCheck(
            requirement=cap.ConnectionPointsRequirements.CP_011,
            message=(
                f"Connection point '{prim.GetName()}' is missing {len(missing)} of "
                "the five base namespace properties: "
                + ", ".join(f"{_CP_NAMESPACE}:{suffix}" for suffix in missing)
                + ". The base namespace states the semantic identity of the "
                "connection and applies to every connection point in every domain."
            ),
            at=prim,
        )

    def _CheckPropertyTypes(self, prim: Usd.Prim) -> None:
        for suffix, (type_name, _) in _BASE_PROPERTIES.items():
            attr = _cp_attribute(prim, suffix)
            if attr is None or attr.GetTypeName() == type_name:
                continue
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_011,
                message=(
                    f"Connection point '{prim.GetName()}' authors "
                    f"{_CP_NAMESPACE}:{suffix} as {attr.GetTypeName()}. The base "
                    f"namespace declares it as {type_name}."
                ),
                at=prim,
            )

    def _CheckTokenValues(self, prim: Usd.Prim) -> None:
        for suffix, expected_values in _BASE_TOKEN_VALUES.items():
            value = _token_value(_cp_attribute(prim, suffix))
            if value is None or value in expected_values:
                continue
            self._AddInfo(
                requirement=cap.ConnectionPointsRequirements.CP_011,
                message=(
                    f"Connection point '{prim.GetName()}' authors "
                    f"{_CP_NAMESPACE}:{suffix} = \"{value}\", which is outside the "
                    f"current example set ({', '.join(expected_values)}). The token "
                    "set is open, so a new equipment class may legitimately need a "
                    "new value."
                ),
                at=prim,
            )

    def _CheckServiceClearance(self, prim: Usd.Prim) -> None:
        attr = _cp_attribute(prim, "serviceClearance")
        if attr is None:
            return
        value = attr.Get()
        if not isinstance(value, float) or value >= 0.0:
            return
        self._AddFailedCheck(
            requirement=cap.ConnectionPointsRequirements.CP_011,
            message=(
                f"Connection point '{prim.GetName()}' authors "
                f"{_CP_NAMESPACE}:serviceClearance = {value}. Service clearance is "
                "the shortest distance from the interface to an obstruction, in "
                "meters, and cannot be negative."
            ),
            at=prim,
        )


# ---------------------------------------------------------------------------
# CP.012 - Connection Point Domain Namespace
# ---------------------------------------------------------------------------

@usd_validation_nvidia.register_rule("AIF-ConnectionPoints")
@usd_validation_nvidia.register_requirements(cap.ConnectionPointsRequirements.CP_012, override=True)
class AIFConnectionPointDomainNamespaceChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that a connection point's domain properties sit in the namespace
    named by its domain value, carry their declared types, and reports which of
    the stub, draft and production completeness profiles the connection meets."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        scope = _find_connection_points_scope(stage)
        if scope is None:
            return  # CP.001 already reported this

        for prim in _iter_connection_points(scope):
            domain, _ = _connection_point_domain(prim)
            if domain is None:
                continue  # CP.010 and CP.011 report the missing domain

            self._CheckForeignNamespaces(prim, domain)

            properties = _DOMAIN_PROPERTIES.get(domain)
            if properties is None:
                self._AddInfo(
                    requirement=cap.ConnectionPointsRequirements.CP_012,
                    message=(
                        f"Connection point '{prim.GetName()}' declares domain "
                        f"\"{domain}\", for which the vocabulary defines no property "
                        "table, so its completeness profile is not evaluated."
                    ),
                    at=prim,
                )
                continue

            self._CheckPropertyTypes(prim, domain, properties)
            self._CheckTokenValues(prim, domain, properties)
            self._CheckUndefinedProperties(prim, domain, properties)
            self._CheckCompleteness(prim, domain, properties)

    def _CheckForeignNamespaces(self, prim: Usd.Prim, domain: str) -> None:
        namespaces = _domain_namespaces(prim)
        for namespace in sorted(namespaces):
            if namespace == domain:
                continue
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_012,
                message=(
                    f"Connection point '{prim.GetName()}' declares domain "
                    f"\"{domain}\" but authors "
                    + ", ".join(
                        f"{_CP_NAMESPACE}:{namespace}:{suffix}"
                        for suffix in sorted(namespaces[namespace])
                    )
                    + f". Domain properties sit in the {domain} namespace, the one "
                    "named by the domain value."
                ),
                at=prim,
            )

    def _CheckPropertyTypes(self, prim: Usd.Prim, domain: str, properties: dict) -> None:
        for suffix, type_name in properties.items():
            attr = _cp_attribute(prim, f"{domain}:{suffix}")
            if attr is None or attr.GetTypeName() == type_name:
                continue
            self._AddFailedCheck(
                requirement=cap.ConnectionPointsRequirements.CP_012,
                message=(
                    f"Connection point '{prim.GetName()}' authors "
                    f"{_CP_NAMESPACE}:{domain}:{suffix} as {attr.GetTypeName()}. The "
                    f"{domain} namespace declares it as {type_name}."
                ),
                at=prim,
            )

    def _CheckTokenValues(self, prim: Usd.Prim, domain: str, properties: dict) -> None:
        for suffix in properties:
            expected_values = _DOMAIN_TOKEN_VALUES.get((domain, suffix))
            if expected_values is None:
                continue
            value = _token_value(_cp_attribute(prim, f"{domain}:{suffix}"))
            if value is None or value in expected_values:
                continue
            self._AddInfo(
                requirement=cap.ConnectionPointsRequirements.CP_012,
                message=(
                    f"Connection point '{prim.GetName()}' authors "
                    f"{_CP_NAMESPACE}:{domain}:{suffix} = \"{value}\", which is "
                    f"outside the current example set ({', '.join(expected_values)}). "
                    "The token set is open, so a new equipment class may "
                    "legitimately need a new value."
                ),
                at=prim,
            )

    def _CheckUndefinedProperties(self, prim: Usd.Prim, domain: str, properties: dict) -> None:
        undefined = sorted(
            suffix
            for suffix in _domain_namespaces(prim).get(domain, [])
            if suffix not in properties
        )
        if not undefined:
            return
        self._AddInfo(
            requirement=cap.ConnectionPointsRequirements.CP_012,
            message=(
                f"Connection point '{prim.GetName()}' authors "
                + ", ".join(f"{_CP_NAMESPACE}:{domain}:{suffix}" for suffix in undefined)
                + f", which the {domain} namespace does not define. Check the "
                "spelling against the property table."
            ),
            at=prim,
        )

    def _CheckCompleteness(self, prim: Usd.Prim, domain: str, properties: dict) -> None:
        missing_base = _missing_base_properties(prim)
        if missing_base:
            self._AddInfo(
                requirement=cap.ConnectionPointsRequirements.CP_012,
                message=(
                    f"Connection point '{prim.GetName()}' does not reach the stub "
                    "profile, so its domain completeness is not evaluated. All five "
                    "base namespace properties come first (CP.011)."
                ),
                at=prim,
            )
            return

        expected = list(properties)
        connector = _token_value(_cp_attribute(prim, f"{domain}:connectorType"))
        if domain == "electrical" and connector == _DRY_CONTACT_CONNECTOR:
            expected = [
                suffix for suffix in expected if suffix not in _DRY_CONTACT_OMITTED_PROPERTIES
            ]
            self._CheckDryContactExtras(prim, domain)

        missing = [
            suffix for suffix in expected if _cp_attribute(prim, f"{domain}:{suffix}") is None
        ]
        authored = [
            suffix
            for suffix in _domain_namespaces(prim).get(domain, [])
            if _cp_attribute(prim, f"{domain}:{suffix}") is not None
        ]

        if not authored:
            self._AddInfo(
                requirement=cap.ConnectionPointsRequirements.CP_012,
                message=(
                    f"Connection point '{prim.GetName()}' is at stub completeness: "
                    "the base namespace is complete and no "
                    f"{_CP_NAMESPACE}:{domain}: properties are authored. "
                    f"{len(expected)} {domain} properties are outstanding before it "
                    "is simulation-ready."
                ),
                at=prim,
            )
            return

        if missing:
            self._AddWarning(
                requirement=cap.ConnectionPointsRequirements.CP_012,
                message=(
                    f"Connection point '{prim.GetName()}' is at draft completeness: "
                    f"{len(missing)} of {len(expected)} {domain} properties are not "
                    "authored: "
                    + ", ".join(f"{_CP_NAMESPACE}:{domain}:{suffix}" for suffix in missing)
                    + ". Author every property the namespace defines, using an "
                    "explicit zero where the value is not physically meaningful."
                ),
                at=prim,
            )

    def _CheckDryContactExtras(self, prim: Usd.Prim, domain: str) -> None:
        authored = [
            suffix
            for suffix in _DRY_CONTACT_OMITTED_PROPERTIES
            if _cp_attribute(prim, f"{domain}:{suffix}") is not None
        ]
        if not authored:
            return
        self._AddInfo(
            requirement=cap.ConnectionPointsRequirements.CP_012,
            message=(
                f"Connection point '{prim.GetName()}' is a dry contact and authors "
                + ", ".join(f"{_CP_NAMESPACE}:{domain}:{suffix}" for suffix in authored)
                + ". A dry contact switches a circuit and has no voltage of its own, "
                "so the properties that describe power distribution do not apply."
            ),
            at=prim,
        )

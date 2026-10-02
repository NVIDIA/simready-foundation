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
"""
Validation rules for SimReady capability.
"""

import json
import re
from typing import Any, Dict, List, Optional

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd

from ..path_utils import (
    file_exists,
    read_asset_bytes,
    sidecar_json_identifiers,
    thumbnail_png_identifier,
)

SIMREADY_METADATA_KEY = "SimReady_Metadata"

QCODE_RE = re.compile(r"^Q[0-9]+$")

PROVENANCE_STRING_FIELDS = [
    "author",
    "asset_name",
    "asset_type",
    "asset_license",
    "category",
    "source_file",
    "usd_date_generated",
    "qcode",
]

PROVENANCE_REQUIRED_FIELDS = PROVENANCE_STRING_FIELDS + [
    "rigid_body_count",
    "asset_extents",
    "mass",
]


def get_metadata(stage: Usd.Stage) -> Dict[str, Any]:
    """Return flattened metadata from USD customLayerData and optional sidecar JSON.

    Neither source is required on its own. Nested ``SimReady_Metadata`` is
    unpacked into the result. When both sources define the same field, USD
    nested values win, then other USD ``customLayerData`` keys, then the sidecar.

    The sidecar is the sibling ``<usd_stem>.json`` of the root layer, located
    through ``path_utils`` so local, Nucleus, and resolver-backed URIs
    (``omniverse://``, ``https://``, ``s3://``, ``file://``) can be read when
    an appropriate USD resolver is installed.

    Raises:
        ValueError: sidecar ``<usd_stem>.json`` exists but is not a JSON object.
    """
    usd_metadata, sidecar_metadata = get_metadata_sources(stage)

    merged: Dict[str, Any] = {}
    merged.update(sidecar_metadata)
    merged.update(usd_metadata)
    return merged


def get_metadata_sources(stage: Usd.Stage) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Return the USD and sidecar metadata separately, each already flattened.

    Both dictionaries have their nested ``SimReady_Metadata`` unpacked, so a
    field authored in one storage location is visible at the top level of that
    location's dictionary.

    Raises:
        ValueError: sidecar ``<usd_stem>.json`` exists but is not a JSON object.
    """
    sidecar_obj: Dict[str, Any] = {}
    sidecar_paths = sidecar_json_identifiers(stage.GetRootLayer())
    if sidecar_paths:
        sidecar_obj = _load_sidecar_json_object(sidecar_paths[0])

    custom_layer_data: Dict[str, Any] = {}
    root_layer = stage.GetRootLayer()
    if root_layer and root_layer.customLayerData:
        custom_layer_data = dict(root_layer.customLayerData)

    return _unpack_metadata_object(custom_layer_data), _unpack_metadata_object(sidecar_obj)


def _load_sidecar_json_object(path: str) -> Dict[str, Any]:
    raw = read_asset_bytes(path)
    if raw is None:
        raise ValueError(f"Sidecar JSON file '{path}' exists but could not be read.")
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Sidecar JSON file '{path}' is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"Sidecar JSON file '{path}' must be a JSON object.")
    return loaded


def _unpack_metadata_object(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    unpacked: Dict[str, Any] = {}
    for key, value in obj.items():
        if key == SIMREADY_METADATA_KEY:
            continue
        unpacked[key] = value
    nested = _coerce_mapping(obj.get(SIMREADY_METADATA_KEY))
    if nested:
        unpacked.update(nested)
    return unpacked


def _coerce_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _is_non_empty_metadata_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _as_float3(value) -> Optional[List[float]]:
    """Return the value as a list of three floats, or None if it is not a float3."""
    try:
        sequence = list(value)
    except TypeError:
        return None
    if len(sequence) != 3:
        return None
    components: List[float] = []
    for component in sequence:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            return None
        components.append(float(component))
    return components


def _check_provenance_fields(
    checker, stage: Usd.Stage, nested: dict, requirement, missing_hint: str, empty_hint: str
) -> None:
    missing_fields = [field for field in PROVENANCE_REQUIRED_FIELDS if field not in nested]
    empty_fields = [
        field
        for field in PROVENANCE_STRING_FIELDS
        if field in nested and not _is_non_empty_metadata_value(nested.get(field))
    ]

    if missing_fields:
        checker._AddFailedCheck(
            requirement=requirement,
            message=f"Required metadata fields are missing: {', '.join(missing_fields)}. {missing_hint}",
            at=stage,
        )

    if empty_fields:
        checker._AddFailedCheck(
            requirement=requirement,
            message=f"Required metadata fields are empty: {', '.join(empty_fields)}. {empty_hint}",
            at=stage,
        )

    _check_qcode(checker, stage, nested, requirement)
    _check_rigid_body_count(checker, stage, nested, requirement)
    _check_asset_extents(checker, stage, nested, requirement)
    _check_mass(checker, stage, nested, requirement)


def _check_qcode(checker, stage: Usd.Stage, nested: dict, requirement) -> None:
    if "qcode" not in nested:
        return
    value = nested.get("qcode")
    if isinstance(value, str) and not value.strip():
        return
    if not isinstance(value, str) or QCODE_RE.match(value) is None:
        checker._AddFailedCheck(
            requirement=requirement,
            message=(
                "Metadata field 'qcode' must be a Wikidata Q-Code: a capital 'Q' "
                f"followed by one or more digits (for example 'Q42177'). Found: {value!r}"
            ),
            at=stage,
        )


def _check_rigid_body_count(checker, stage: Usd.Stage, nested: dict, requirement) -> None:
    if "rigid_body_count" not in nested:
        return
    value = nested.get("rigid_body_count")
    if isinstance(value, bool) or not isinstance(value, int):
        checker._AddFailedCheck(
            requirement=requirement,
            message=(
                "Metadata field 'rigid_body_count' must be an integer count of the "
                f"rigid bodies in the asset. Found: {value!r}"
            ),
            at=stage,
        )
        return
    if value < 0:
        checker._AddFailedCheck(
            requirement=requirement,
            message=("Metadata field 'rigid_body_count' must be a non-negative integer. " f"Found: {value}"),
            at=stage,
        )


def _check_asset_extents(checker, stage: Usd.Stage, nested: dict, requirement) -> None:
    if "asset_extents" not in nested:
        return
    value = nested.get("asset_extents")
    components = _as_float3(value)
    if components is None:
        checker._AddFailedCheck(
            requirement=requirement,
            message=(
                "Metadata field 'asset_extents' must be a float3 with three numeric "
                f"components (asset size in meters, XYZ). Found: {value!r}"
            ),
            at=stage,
        )
        return
    if any(component < 0 for component in components):
        checker._AddFailedCheck(
            requirement=requirement,
            message=(
                "Metadata field 'asset_extents' components must be non-negative meters. "
                f"Found: {tuple(components)}"
            ),
            at=stage,
        )


def _check_mass(checker, stage: Usd.Stage, nested: dict, requirement) -> None:
    if "mass" not in nested:
        return
    value = nested.get("mass")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        checker._AddFailedCheck(
            requirement=requirement,
            message=("Metadata field 'mass' must be a number (asset mass in kilograms). " f"Found: {value!r}"),
            at=stage,
        )
        return
    if value <= 0:
        checker._AddFailedCheck(
            requirement=requirement,
            message=("Metadata field 'mass' must be a positive number of kilograms. " f"Found: {value}"),
            at=stage,
        )


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_001, override=True)
class SimReadyCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checker for the original root-layer metadata contract."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check SR.001 required fields directly in root customLayerData."""
        self.check_sr001_metadata_whitelist(stage)

    def check_sr001_metadata_whitelist(self, stage: Usd.Stage) -> None:
        """Check the stable SR.001 root-layer customLayerData field set."""
        root_layer = stage.GetRootLayer()
        custom_layer_data = root_layer.customLayerData if root_layer else {}
        required_metadata_fields = (
            "SimReady_Metadata",
            "asset_name",
            "asset_type",
            "source_file",
            "usd_date_generated",
        )
        missing_fields = [field for field in required_metadata_fields if field not in custom_layer_data]
        if missing_fields:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_001,
                message=(
                    f"Required metadata fields are missing: {', '.join(missing_fields)}. "
                    "Fields must be authored directly in the root layer's customLayerData."
                ),
                at=stage,
            )


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_002, override=True)
class ThumbnailExists(usd_validation_nvidia.BaseRuleChecker):
    """Validates that SimReady assets have a thumbnail image."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        root_layer = stage.GetRootLayer()
        thumbnail_path = thumbnail_png_identifier(root_layer)
        if not thumbnail_path:
            return
        if not file_exists(thumbnail_path):
            identifier = root_layer.identifier if root_layer else ""
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_002,
                message=f"No thumbnail found at {thumbnail_path} for SimReady asset <{identifier}>",
                at=stage,
            )


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_003)
class NestedSimReadyMetadata(usd_validation_nvidia.BaseRuleChecker):
    """Checker for nested SimReady provenance metadata (SR.003)."""

    QCODE_RE = QCODE_RE
    STRING_FIELDS = PROVENANCE_STRING_FIELDS
    REQUIRED_FIELDS = PROVENANCE_REQUIRED_FIELDS

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check SR.003 nested SimReady_Metadata requirements."""
        self.check_sr003_nested_simready_metadata(stage)

    def check_sr003_nested_simready_metadata(self, stage: Usd.Stage) -> None:
        """
        Check SR.003: required provenance fields must be inside SimReady_Metadata.

        Validates that:
        1. The SimReady_Metadata dictionary is present in customLayerData
        2. Each required field is authored inside the SimReady_Metadata dictionary
        3. Each required string field value is non-empty
        4. Typed fields have the expected type and value range

        Note: Additional/unexpected metadata fields are allowed.
        """
        root_layer = stage.GetRootLayer()
        customlayerdata = root_layer.customLayerData if root_layer else {}

        if "SimReady_Metadata" not in customlayerdata:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message="Missing top level SimReady_Metadata dictionary.",
                at=stage,
            )
            return

        nested = customlayerdata.get("SimReady_Metadata")
        if not isinstance(nested, dict):
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message="SimReady_Metadata must be a dictionary containing required provenance fields.",
                at=stage,
            )
            return

        _check_provenance_fields(
            self,
            stage,
            nested,
            cap.SimReadyRequirements.SR_003,
            "Metadata should be in SimReady_Metadata dictionary.",
            "Each required SimReady_Metadata field must have a non-empty value.",
        )


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_004)
class MetadataUnion(usd_validation_nvidia.BaseRuleChecker):
    """Checker for USD/sidecar provenance metadata union (SR.004)."""

    QCODE_RE = QCODE_RE
    STRING_FIELDS = PROVENANCE_STRING_FIELDS
    REQUIRED_FIELDS = PROVENANCE_REQUIRED_FIELDS

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check SR.004 required fields against the USD/sidecar metadata union."""
        self.check_sr004_metadata_union(stage)

    def check_sr004_metadata_union(self, stage: Usd.Stage) -> None:
        """
        Check SR.004: required provenance fields exist in the USD/sidecar union.

        Neither SimReady_Metadata nor the sidecar JSON file is required on its
        own. Fields may be authored in root-layer customLayerData (including a
        nested SimReady_Metadata dictionary) and/or in ``<usd_stem>.json``.
        """
        try:
            usd_metadata, sidecar_metadata = get_metadata_sources(stage)
        except ValueError as exc:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_004,
                message=str(exc),
                at=stage,
            )
            return

        duplicate_fields = sorted(set(usd_metadata) & set(sidecar_metadata))
        if duplicate_fields:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_004,
                message=(
                    f"Metadata fields are authored in both storage locations: {', '.join(duplicate_fields)}. "
                    "Each field must be authored in root-layer customLayerData "
                    "(including SimReady_Metadata) or the sibling sidecar JSON, not both."
                ),
                at=stage,
            )

        nested: Dict[str, Any] = {}
        nested.update(sidecar_metadata)
        nested.update(usd_metadata)

        _check_provenance_fields(
            self,
            stage,
            nested,
            cap.SimReadyRequirements.SR_004,
            "Fields may be authored in root-layer customLayerData "
            "(including SimReady_Metadata) and/or the same-directory sidecar JSON.",
            "Each required field in the USD/sidecar metadata union must have a non-empty value.",
        )

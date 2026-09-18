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

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

try:
    import omni.client
except ImportError:
    omni_client = None

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Ar, Sdf, Usd


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_001, override=True)
class SimReadyCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checker for Sim Ready capability requirements."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check all SimReady requirements."""
        errors = []

        errors.extend(self.check_sr001_metadata_whitelist(stage))

        return errors

    def check_sr001_metadata_whitelist(self, stage: Usd.Stage) -> List[str]:
        """
        Check SR.001: Verify that the asset stage contains required metadata.

        Validates that:
        1. All required metadata fields are present
        2. The SimReady_Metadata dictionary has all required fields (if present)

        Note: Additional/unexpected metadata fields are allowed.
        """
        errors = []

        root_layer = stage.GetRootLayer()
        customlayerdata = root_layer.customLayerData

        # Check for required fields at top level (alternative location)
        missing_fields = []
        required_metadata_fields = {
            "SimReady_Metadata",
            "asset_name",
            "asset_type",
            "source_file",
            "usd_date_generated",
        }
        for required_field in required_metadata_fields:
            if required_field not in customlayerdata:
                missing_fields.append(required_field)

        if missing_fields:
            errors.append(
                f"Required metadata fields are missing: {', '.join(missing_fields)}. "
                f"Metadata should be in SimReady_Metadata dictionary or at top level of customLayerData."
            )

        return errors


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_002, override=True)
class ThumbnailExists(usd_validation_nvidia.BaseRuleChecker):
    """Validates that SimReady assets have a thumbnail image."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        real_path = stage.GetRootLayer().realPath
        if not real_path:
            return
        asset_path = Path(real_path)
        thumbnail_path = str(asset_path.parent / ".thumbs" / "256x256" / (asset_path.name + ".png"))
        if not Ar.GetResolver().Resolve(thumbnail_path):
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_002,
                message=f"No thumbnail found at {thumbnail_path} for SimReady asset <{real_path}>",
                at=stage,
            )


@usd_validation_nvidia.register_rule("SimReady")
@usd_validation_nvidia.register_requirements(cap.SimReadyRequirements.SR_003)
class NestedSimReadyMetadata(usd_validation_nvidia.BaseRuleChecker):
    """Checker for nested SimReady provenance metadata (SR.003)."""

    # Wikidata Q-Code: a capital "Q" followed by one or more digits.
    QCODE_RE = re.compile(r"^Q[0-9]+$")

    # Required string fields, checked for presence and non-emptiness.
    STRING_FIELDS = [
        "author",
        "asset_name",
        "asset_type",
        "asset_license",
        "category",
        "source_file",
        "usd_date_generated",
        "qcode",
    ]

    # Full required-field set, in documentation order, for the missing-field check.
    REQUIRED_FIELDS = STRING_FIELDS + [
        "rigid_body_count",
        "asset_extents",
        "mass",
    ]

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
        4. Typed fields have the expected type and value range:
           ``qcode`` (Wikidata Q-Code format), ``rigid_body_count`` (non-negative
           int), ``asset_extents`` (float3, non-negative meters), and ``mass``
           (positive float, kilograms)

        Note: Additional/unexpected metadata fields are allowed.
        """
        root_layer = stage.GetRootLayer()
        customlayerdata = root_layer.customLayerData

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

        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in nested]
        empty_fields = [
            field
            for field in self.STRING_FIELDS
            if field in nested and not self._is_non_empty_metadata_value(nested.get(field))
        ]

        if missing_fields:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=(
                    f"Required metadata fields are missing: {', '.join(missing_fields)}. "
                    "Metadata should be in SimReady_Metadata dictionary."
                ),
                at=stage,
            )

        if empty_fields:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=(
                    f"Required metadata fields are empty: {', '.join(empty_fields)}. "
                    "Each required SimReady_Metadata field must have a non-empty value."
                ),
                at=stage,
            )

        # Typed / format validation for fields that are present. Missing or
        # empty values are already reported above, so these skip those cases to
        # avoid duplicate messages.
        self._check_qcode(stage, nested)
        self._check_rigid_body_count(stage, nested)
        self._check_asset_extents(stage, nested)
        self._check_mass(stage, nested)

    def _check_qcode(self, stage: Usd.Stage, nested: dict) -> None:
        if "qcode" not in nested:
            return
        value = nested.get("qcode")
        # Empty/whitespace is already reported by the empty-field check.
        if isinstance(value, str) and not value.strip():
            return
        if not isinstance(value, str) or self.QCODE_RE.match(value) is None:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=(
                    "SimReady_Metadata 'qcode' must be a Wikidata Q-Code: a capital 'Q' "
                    f"followed by one or more digits (for example 'Q42177'). Found: {value!r}"
                ),
                at=stage,
            )

    def _check_rigid_body_count(self, stage: Usd.Stage, nested: dict) -> None:
        if "rigid_body_count" not in nested:
            return
        value = nested.get("rigid_body_count")
        if isinstance(value, bool) or not isinstance(value, int):
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=(
                    "SimReady_Metadata 'rigid_body_count' must be an integer count of the "
                    f"rigid bodies in the asset. Found: {value!r}"
                ),
                at=stage,
            )
            return
        if value < 0:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=("SimReady_Metadata 'rigid_body_count' must be a non-negative integer. " f"Found: {value}"),
                at=stage,
            )

    def _check_asset_extents(self, stage: Usd.Stage, nested: dict) -> None:
        if "asset_extents" not in nested:
            return
        value = nested.get("asset_extents")
        components = self._as_float3(value)
        if components is None:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=(
                    "SimReady_Metadata 'asset_extents' must be a float3 with three numeric "
                    f"components (asset size in meters, XYZ). Found: {value!r}"
                ),
                at=stage,
            )
            return
        if any(component < 0 for component in components):
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=(
                    "SimReady_Metadata 'asset_extents' components must be non-negative meters. "
                    f"Found: {tuple(components)}"
                ),
                at=stage,
            )

    def _check_mass(self, stage: Usd.Stage, nested: dict) -> None:
        if "mass" not in nested:
            return
        value = nested.get("mass")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=("SimReady_Metadata 'mass' must be a number (asset mass in kilograms). " f"Found: {value!r}"),
                at=stage,
            )
            return
        if value <= 0:
            self._AddFailedCheck(
                requirement=cap.SimReadyRequirements.SR_003,
                message=("SimReady_Metadata 'mass' must be a positive number of kilograms. " f"Found: {value}"),
                at=stage,
            )

    @staticmethod
    def _as_float3(value) -> Optional[List[float]]:
        """Return the value as a list of three floats, or None if it is not a float3.

        Accepts USD ``Gf.Vec3f`` / ``Gf.Vec3d`` (iterable, length 3) as well as
        plain tuples/lists. Booleans are rejected as components.
        """
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

    @staticmethod
    def _is_non_empty_metadata_value(value) -> bool:
        """Return True when a metadata value is present and non-empty."""
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

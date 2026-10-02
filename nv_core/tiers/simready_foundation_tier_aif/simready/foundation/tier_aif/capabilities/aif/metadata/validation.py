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

# Equipment class definitions live in config/aif-equipment-<class>.json.
# See capabilities/aif/equipment_classes.py.


_get_prim_spec = _stage.properties_prim_spec


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_001, override=True)
class AIFPropertiesSublayerChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that the stage has a *properties*.usda sublayer with a default prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        layer = _stage.find_sublayer(stage, "properties")
        if not layer:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_001,
                message=(
                    "Missing required sublayer: *properties*.usd[a|c]. "
                    "The stage must include a sublayer with 'properties' in its name "
                    "(e.g., AssetName_Properties.usda)."
                ),
                at=stage,
            )
            return
        if not layer.defaultPrim:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_001,
                message="properties.usda sublayer has no defaultPrim specified.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_002, override=True)
class AIFAssetClassChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that aif:core:assetClass is present on the default prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return  # AM.001 already reported this
        if "aif:core:assetClass" not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_002,
                message="Missing required attribute: aif:core:assetClass.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_003, override=True)
class AIFAssetIdentificationChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks aif:core:manufacturer, aif:core:modelNumber, aif:core:assetVersion."""

    _REQUIRED = ("aif:core:manufacturer", "aif:core:modelNumber", "aif:core:assetVersion")

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        present = set(prim_spec.attributes.keys())
        missing = sorted(a for a in self._REQUIRED if a not in present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_003,
                message=f"Missing asset identification attributes: {', '.join(missing)}",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_004, override=True)
class AIFPhysicalDimensionsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks physical dimension attributes on the default prim."""

    _REQUIRED = (
        "aif:core:height",
        "aif:core:width",
        "aif:core:depth",
        "aif:core:weight",
        "aif:core:overallGeometryDimensions",
        "aif:core:installationClearance",
        "aif:core:accessibilityRequirement",
    )

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        present = set(prim_spec.attributes.keys())
        missing = sorted(a for a in self._REQUIRED if a not in present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_004,
                message=f"Missing physical dimension attributes: {', '.join(missing)}",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_005, override=True)
class AIFSimReadyVersionChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks that aif:core:simreadyVersion is present on the default prim."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        if "aif:core:simreadyVersion" not in prim_spec.attributes:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_005,
                message="Missing required attribute: aif:core:simreadyVersion.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_006, override=True)
class AIFAssetDescriptionChecker(usd_validation_nvidia.BaseRuleChecker):
    """Checks aif:core:assetDescription and aif:core:connectsToModelDocumentation."""

    _REQUIRED = ("aif:core:assetDescription", "aif:core:connectsToModelDocumentation")

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return
        present = set(prim_spec.attributes.keys())
        missing = sorted(a for a in self._REQUIRED if a not in present)
        if missing:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_006,
                message=f"Missing asset description attributes: {', '.join(missing)}",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_007, override=True)
class AIFEquipmentTemplateChecker(usd_validation_nvidia.BaseRuleChecker):
    """Reads aif:core:assetClass and checks required aif:spec:* attributes for that equipment class."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _get_prim_spec(stage)
        if not prim_spec:
            return

        asset_class_attr = prim_spec.attributes.get("aif:core:assetClass")
        if not asset_class_attr or not asset_class_attr.default:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_007,
                message="aif:core:assetClass is missing or empty; cannot determine equipment template.",
                at=stage,
            )
            return

        asset_class = equipment_classes.normalize(str(asset_class_attr.default))
        if asset_class is None:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_007,
                message=(
                    f"No equipment class definition found for assetClass '{asset_class_attr.default}'. "
                    f"Defined classes: {', '.join(equipment_classes.RECOGNISED)}."
                ),
                at=stage,
            )
            return

        required = equipment_classes.ATTRIBUTES[asset_class]
        present = set(prim_spec.attributes.keys())
        missing = sorted(required - present)
        if missing:
            # A warning, not a failure. Only CDU.csv marks its rows Required;
            # the CRAH, UPS and Compute Rack templates leave that column blank,
            # so the source does not say these attributes are mandatory. The
            # attributes a downstream requirement actually consumes keep failing
            # through EL.001-EL.003 and TC.001-TC.002.
            self._AddWarning(
                requirement=cap.MetadataRequirements.AM_007,
                message=(
                    f"Asset class '{asset_class_attr.default}' is missing {len(missing)} aif:spec:* attribute(s): "
                    f"{', '.join(missing[:5])}"
                    + (f" ... and {len(missing) - 5} more" if len(missing) > 5 else "")
                ),
                at=stage,
            )

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AIF 0.3 equipment templates and USD metadata types."""

import usd_validation_nvidia
from pxr import Sdf, Usd

import simready.foundation.tier_aif.requirements as cap

from .. import _stage, chiller_schema, equipment_classes
from .validation import _PhysicalDimensionsChecker


_METADATA_TYPES = {
    "aif:core:assetClass": Sdf.ValueTypeNames.String,
    "aif:core:assetDescription": Sdf.ValueTypeNames.String,
    "aif:core:connectsToModelDocumentation": Sdf.ValueTypeNames.String,
    "aif:core:manufacturer": Sdf.ValueTypeNames.String,
    "aif:core:modelNumber": Sdf.ValueTypeNames.String,
    "aif:core:assetVersion": Sdf.ValueTypeNames.String,
    "aif:core:simreadyVersion": Sdf.ValueTypeNames.String,
    "aif:core:height": Sdf.ValueTypeNames.Float,
    "aif:core:width": Sdf.ValueTypeNames.Float,
    "aif:core:depth": Sdf.ValueTypeNames.Float,
    "aif:core:weight": Sdf.ValueTypeNames.Float,
    "aif:core:installationClearance": Sdf.ValueTypeNames.Float,
    "aif:core:accessibilityRequirement": Sdf.ValueTypeNames.Float,
}


@usd_validation_nvidia.register_rule("AIF-Metadata-0.3")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_009, override=True)
class AIF03PhysicalDimensionsChecker(_PhysicalDimensionsChecker):
    """Check the scalar dimensions and report obsolete dimension declarations."""

    _REQUIREMENT = cap.MetadataRequirements.AM_009

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _stage.properties_prim_spec(stage)
        self._check_required_dimensions(stage, prim_spec)

        retired = "aif:core:overallGeometryDimensions"
        root = stage.GetDefaultPrim()
        if (prim_spec and retired in prim_spec.properties) or (root and root.HasProperty(retired)):
            self._AddFailedCheck(
                requirement=self._REQUIREMENT,
                message=f"Remove {retired} from the asset. AIF 0.3 uses aif:core:width, aif:core:depth and aif:core:height.",
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-Metadata-0.3")
@usd_validation_nvidia.register_requirements(cap.MetadataRequirements.AM_008, override=True)
class AIF03EquipmentTemplateChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check the class template and the types of authored metadata."""

    def _check_types(self, stage, prim_spec):
        root = stage.GetDefaultPrim()
        for name, expected in _METADATA_TYPES.items():
            authored = prim_spec.properties.get(name)
            if authored is not None:
                actual = authored.typeName if isinstance(authored, Sdf.AttributeSpec) else "relationship"
                if actual != expected:
                    self._AddFailedCheck(
                        requirement=cap.MetadataRequirements.AM_008,
                        message=f"{name} must be a USD {expected} attribute. The Properties layer declares {actual}.",
                        at=stage,
                    )
                    continue
            composed = root.GetProperty(name) if root else None
            if composed:
                actual = composed.GetTypeName() if isinstance(composed, Usd.Attribute) else "relationship"
                if actual != expected:
                    self._AddFailedCheck(
                        requirement=cap.MetadataRequirements.AM_008,
                        message=f"{name} must be a USD {expected} attribute. The composed default prim has {actual}.",
                        at=composed,
                    )

    def _check_chiller(self, stage, prim_spec):
        attr = prim_spec.attributes.get("aif:core:assetClass")
        authored = chiller_schema.schema_for(attr.default if attr else None)
        root = stage.GetDefaultPrim()
        composed_attr = root.GetAttribute("aif:core:assetClass") if root else None
        composed = chiller_schema.schema_for(composed_attr.Get() if composed_attr else None)
        if authored is None and composed is None:
            return False
        if authored is not composed:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_008,
                message="The Properties layer and composed default prim must agree on the chiller equipment class.",
                at=stage,
            )
        else:
            for error in chiller_schema.validate_attributes(chiller_schema.properties_prim(stage)):
                self._AddFailedCheck(requirement=cap.MetadataRequirements.AM_008, message=error, at=stage)
        return True

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim_spec = _stage.properties_prim_spec(stage)
        if prim_spec is None:
            return  # AM.001 owns Properties-layer availability.
        self._check_types(stage, prim_spec)
        if self._check_chiller(stage, prim_spec):
            return
        attr = prim_spec.attributes.get("aif:core:assetClass")
        raw = str(attr.default) if attr and attr.default else ""
        key = equipment_classes.normalize_03(raw)
        if key is None:
            self._AddFailedCheck(
                requirement=cap.MetadataRequirements.AM_008,
                message=f"No AIF 0.3 equipment template for assetClass '{raw}'. Defined classes: {', '.join(equipment_classes.RECOGNISED_03)}.",
                at=stage,
            )
            return
        missing = sorted(equipment_classes.ATTRIBUTES_03[key] - set(prim_spec.attributes.keys()))
        if missing:
            self._AddWarning(
                requirement=cap.MetadataRequirements.AM_008,
                message=f"Asset class '{raw}' is missing {len(missing)} aif:spec:* attribute(s): {', '.join(missing)}",
                at=stage,
            )

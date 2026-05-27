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

__all__ = ["NonVisualMaterialsCapabilityChecker"]


import dataclasses

import omni.capabilities as cap
from omni.asset_validator import (
    BaseRuleChecker,
    register_requirements,
)
from pxr import Sdf, Usd, UsdGeom, UsdShade


# Backward compatible

_OMNI_PRIM_PATHS = {
    Sdf.Path("/OmniverseKit_Persp"),
    Sdf.Path("/OmniverseKit_Front"),
    Sdf.Path("/OmniverseKit_Top"),
    Sdf.Path("/OmniverseKit_Right"),
    Sdf.Path("/OmniKit_Viewport_LightRig"),
}
_OMNI_PRIM_NAMES = {"OmniverseKitViewportCameraMesh"}
def is_omni_path(path: Sdf.Path) -> bool:
    return path in _OMNI_PRIM_PATHS or path.name in _OMNI_PRIM_NAMES


@dataclasses.dataclass
class AttributeConstraint:
    type_names: list[Sdf.ValueTypeName]
    """Any type in this list is allowed."""

    allow_empty: bool
    """If it allows to have no value."""

    allowed_values: list[str]
    """if not empty, list of allowed values for a type."""


@register_requirements(
    cap.NonvisualMaterialsRequirements.NVM_001,
    cap.NonvisualMaterialsRequirements.NVM_002,
    cap.NonvisualMaterialsRequirements.NVM_003,
    cap.NonvisualMaterialsRequirements.NVM_004,
    cap.NonvisualMaterialsRequirements.NVM_005,  # not objectively verifiable by code
    cap.NonvisualMaterialsRequirements.NVM_006,
)
class NonVisualMaterialsCapabilityChecker(BaseRuleChecker):
    """
    Validates the following non-visual materials requirements:

    - **NVM.001**: Materials must specify additional "non-visual" material attributes
    - **NVM.002**: Materials must specify a base material type
    - **NVM.003**: Materials must specify surface coating
    - **NVM.004**: Attributes must be on bound materials
    - **NVM.006**: Properties must not be time-varying

    Every geometry prim with a computed purpose of "render" or "default" must have non-visual material attributes assigned per visual material assigned, using the 3 attributes listed below:

    - ``token omni:simready:nonvisual:base``
    - ``token omni:simready:nonvisual:coating``
    - ``token[] omni:simready:nonvisual:attributes``
    """

    # The following value list is according to AVSimReady Content Specification 0.0.5
    ATTRIBUTE_RULES = {
        "omni:simready:nonvisual:base": AttributeConstraint(
            type_names=[Sdf.ValueTypeNames.Token],
            allow_empty=False,
            allowed_values=[
                # Metals
                "aluminum",
                "steel",
                "oxidized_steel",
                "iron",
                "oxidized_iron",
                "silver",
                "brass",
                "bronze",
                "oxidized_Bronze_Patina",
                "tin",
                # Polymers
                "plastic",
                "fiberglass",
                "carbon_fiber",
                "vinyl",
                "plexiglass",
                "pvc",
                "nylon",
                "polyester",
                # Glass
                "clear_glass",
                "frosted_glass",
                "one_way_mirror",
                "mirror",
                "ceramic_glass",
                # Other
                "asphalt",
                "concrete",
                "leaf_grass",
                "dead_leaf_grass",
                "rubber",
                "wood",
                "bark",
                "cardboard",
                "paper",
                "fabric",
                "skin",
                "fur_hair",
                "leather",
                "marble",
                "brick",
                "stone",
                "gravel",
                "dirt",
                "mud",
                "water",
                "salt_water",
                "snow",
                "ice",
                "calibration_lambertian",
            ],
        ),
        "omni:simready:nonvisual:coating": AttributeConstraint(
            type_names=[Sdf.ValueTypeNames.Token],
            allow_empty=True,
            allowed_values=["none", "paint", "clearcoat", "paint_clearcoat"],
        ),
        "omni:simready:nonvisual:attributes": AttributeConstraint(
            type_names=[Sdf.ValueTypeNames.TokenArray],
            allow_empty=True,
            allowed_values=["none", "emissive", "retroreflective", "single_sided", "visually_transparent"],
        ),
    }

    # Mapping from attribute names to their corresponding requirements
    _ATTRIBUTE_TO_REQUIREMENT = {
        "omni:simready:nonvisual:base": cap.NonvisualMaterialsRequirements.NVM_002,
        "omni:simready:nonvisual:coating": cap.NonvisualMaterialsRequirements.NVM_003,
        "omni:simready:nonvisual:attributes": cap.NonvisualMaterialsRequirements.NVM_001,
    }

    def __init__(self, verbose, consumerLevelChecks, assetLevelChecks):
        super().__init__(verbose, consumerLevelChecks, assetLevelChecks)
        self.ResetCaches()

    @staticmethod
    def _is_from_default_prim(prim: Usd.Prim):
        stage: Usd.Stage = prim.GetStage()
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return False

        return prim.GetPath().HasPrefix(default_prim.GetPath())

    @staticmethod
    def _has_default_or_renderable_purpose(prim: Usd.Prim) -> bool:
        """Returns True if the prim is Imageable with default or renderable purpose."""
        if not (imageable := UsdGeom.Imageable(prim)):
            return False
        purpose = imageable.ComputePurpose()
        return purpose in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)

    def _check_unbound_materials(self, stage: Usd.Stage):
        """
        Check for NVM.004: Ensure non-visual material attributes are only on bound materials.
        This validates that materials with non-visual attributes are actually bound to geometry.
        """
        # Collect all materials that are bound to geometry
        bound_materials = set()

        for prim in stage.Traverse():
            if is_omni_path(prim.GetPath()):
                continue

            if not self._is_from_default_prim(prim):
                continue

            if not (UsdGeom.Gprim(prim) or UsdGeom.Subset(prim)):
                continue

            if not self._has_default_or_renderable_purpose(prim):
                continue

            mtl_binding_api = UsdShade.MaterialBindingAPI(prim)
            material, _ = mtl_binding_api.ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)
            if material:
                bound_materials.add(material.GetPath())

        # Now check all materials with non-visual attributes
        for prim in stage.Traverse():
            if is_omni_path(prim.GetPath()):
                continue

            if not self._is_from_default_prim(prim):
                continue

            # Check if this is a material prim
            material = UsdShade.Material(prim)
            if not material:
                continue

            # Check if it has any non-visual material attributes
            has_nonvisual_attrs = False
            for attr_name in self.ATTRIBUTE_RULES.keys():
                if prim.HasAttribute(attr_name):
                    has_nonvisual_attrs = True
                    break

            # If it has non-visual attributes but is not bound to any geometry, report error
            if has_nonvisual_attrs and material.GetPath() not in bound_materials:
                self._AddFailedCheck(
                    message="Material has non-visual material attributes but is not bound to any geometry.",
                    at=prim,
                    requirement=cap.NonvisualMaterialsRequirements.NVM_004,
                )

    def CheckStage(self, stage: Usd.Stage):
        # Validate that the stage has a valid default prim
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                message="Stage has no default prim.",
                at=stage,
            )

        # Check for NVM.004: Materials with non-visual attributes must be bound to geometry
        self._check_unbound_materials(stage)

    def CheckPrim(self, prim: Usd.Prim):
        if is_omni_path(prim.GetPath()):
            return

        if not self._is_from_default_prim(prim):
            return

        if not UsdGeom.Gprim(prim) and not UsdGeom.Subset(prim):
            return

        if not self._has_default_or_renderable_purpose(prim):
            return

        mtl_binding_api: UsdShade.MaterialBindingAPI = UsdShade.MaterialBindingAPI(prim)

        material, _ = mtl_binding_api.ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)
        if not material:
            return
        self.checkMaterial(material)

    def checkMaterial(self, material: UsdShade.Material):
        material_prim = material.GetPrim()

        if material_prim in self._checkedMaterialPrims:
            return

        for name, constraint in NonVisualMaterialsCapabilityChecker.ATTRIBUTE_RULES.items():
            allow_empty = constraint.allow_empty
            allow_values = constraint.allowed_values
            expected_typenames = constraint.type_names

            # Checks if the attribute exists.
            attr: Usd.Attribute = material.GetPrim().GetAttribute(name)
            if not attr:
                self._AddFailedCheck(
                    message=f'Required attribute "{name}" for nonvisual material doesn\'t exist.',
                    at=material_prim,
                    requirement=self._ATTRIBUTE_TO_REQUIREMENT[name],
                )
                continue

            # Checks type name then.
            typename: Sdf.ValueTypeName = attr.GetTypeName()
            if typename not in expected_typenames:
                self._AddFailedCheck(
                    message=f'Typename of attribute "{name}" for nonvisual material can only be '
                    + (
                        f"{expected_typenames[0]}."
                        if len(expected_typenames) == 1
                        else f"one of {expected_typenames!s}."
                    ),
                    at=material_prim,
                    requirement=self._ATTRIBUTE_TO_REQUIREMENT[name],
                )
                continue
            if (time_samples := attr.GetNumTimeSamples()) > 0:
                self._AddFailedCheck(
                    message=f"Attribute {name} has {time_samples} timeSamples when it should only have a default value.",
                    at=material_prim,
                    requirement=cap.NonvisualMaterialsRequirements.NVM_006,
                )

            # Lastly, checks value. It follows those rules:
            # * If allowed_values is empty, that means all values are allowed.
            # * Otherwise, it reports warnings for those values that are not in the allowed list.
            # * Lastly, if value is not given and allow_empty is False, an error is reported.
            value = attr.Get()
            if value is not None and allow_values:
                if typename.isArray:
                    if unexpected_values := list(set(value) - set(allow_values)):
                        self._AddFailedCheck(
                            message=(
                                (
                                    f"Element {unexpected_values[0]}"
                                    if len(unexpected_values) == 1
                                    else f"Elements {unexpected_values!s}"
                                )
                                + f' of array attribute "{name}" for nonvisual material not allowed.'
                            ),
                            at=material_prim,
                            requirement=self._ATTRIBUTE_TO_REQUIREMENT[name],
                        )
                elif value not in allow_values:
                    self._AddFailedCheck(
                        message=f'Value ({value}) of attribute "{name}" for nonvisual material is not in the '
                        "allowed list of values.",
                        at=material_prim,
                        requirement=self._ATTRIBUTE_TO_REQUIREMENT[name],
                    )
            elif value is None and not allow_empty:
                self._AddFailedCheck(
                    message=f'Required attribute "{name}" for nonvisual material must have a value specified.',
                    at=material_prim,
                    requirement=self._ATTRIBUTE_TO_REQUIREMENT[name],
                )

        self._checkedMaterialPrims.add(material_prim)

    def ResetCaches(self):
        self._checkedMaterialPrims = set()

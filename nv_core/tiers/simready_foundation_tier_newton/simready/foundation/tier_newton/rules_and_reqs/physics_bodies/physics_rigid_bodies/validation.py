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
    "NewtonColliderAPIChecker",
    "NewtonSDFAttributesChecker",
    "NewtonMassAttributesChecker",
]

import simready.foundation.tier_newton.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdGeom, UsdPhysics

from simready.foundation.tier_newton.rules_and_reqs._common import (
    _as_float,
    _authored_value,
    _has_applied_api_schema,
)

_NEWTON_COLLISION_API = "NewtonCollisionAPI"
_NEWTON_MESH_COLLISION_API = "NewtonMeshCollisionAPI"
_NEWTON_SDF_COLLISION_API = "NewtonSDFCollisionAPI"
_NEWTON_MASS_API = "NewtonMassAPI"


def _has_newton_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _NEWTON_COLLISION_API)


def _has_newton_mesh_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _NEWTON_MESH_COLLISION_API)


def _has_newton_sdf_collision_api(prim: Usd.Prim) -> bool:
    return _has_applied_api_schema(prim, _NEWTON_SDF_COLLISION_API)


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.NEWTON_COL_001, override=True)
class NewtonColliderAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Newton colliders must use a valid Newton collision schema representation."""

    NEWTON_COLLIDER_API_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.NEWTON_COL_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim. Unable to validate.",
                at=stage,
                requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
            )
            return

        for prim in Usd.PrimRange(default_prim, Usd.TraverseInstanceProxies()):
            has_newton_collision_api = _has_newton_collision_api(prim)
            has_newton_mesh_api = _has_newton_mesh_collision_api(prim)
            has_newton_sdf_api = _has_newton_sdf_collision_api(prim)

            if has_newton_mesh_api and has_newton_sdf_api:
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has both NewtonMeshCollisionAPI and NewtonSDFCollisionAPI. "
                        "Choose one Newton mesh collision representation."
                    ),
                    at=prim,
                )

            if has_newton_collision_api and not prim.IsA(UsdGeom.Gprim):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has NewtonCollisionAPI but is not a UsdGeom Gprim. "
                        "Apply NewtonCollisionAPI to a collider shape prim."
                    ),
                    at=prim,
                )

            if has_newton_sdf_api and not prim.IsA(UsdGeom.Gprim):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has NewtonSDFCollisionAPI but is not a UsdGeom Gprim. "
                        "Apply NewtonSDFCollisionAPI to a collider shape prim."
                    ),
                    at=prim,
                )

            if has_newton_mesh_api and not prim.IsA(UsdGeom.Mesh):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' has NewtonMeshCollisionAPI but is not a UsdGeom Mesh. "
                        "Apply NewtonMeshCollisionAPI to mesh collider prims."
                    ),
                    at=prim,
                )

            if (
                prim.IsA(UsdGeom.Mesh)
                and (prim.HasAPI(UsdPhysics.MeshCollisionAPI) or has_newton_collision_api)
                and not has_newton_mesh_api
                and not has_newton_sdf_api
            ):
                self._AddFailedCheck(
                    requirement=self.NEWTON_COLLIDER_API_REQUIREMENT,
                    message=(
                        f"Newton mesh collider '{prim.GetPath()}' must apply either NewtonMeshCollisionAPI "
                        "or NewtonSDFCollisionAPI."
                    ),
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsRigidBodies")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.NEWTON_COL_002, override=True)
class NewtonSDFAttributesChecker(usd_validation_nvidia.BaseRuleChecker):
    """Authored Newton SDF attributes must have valid values."""

    NEWTON_SDF_ATTRIBUTES_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.NEWTON_COL_002
    _NON_NEGATIVE_FLOAT_ATTRIBUTES = (
        "newton:contactMargin",
        "newton:contactGap",
        "newton:sdfPadding",
    )
    _POSITIVE_FLOAT_ATTRIBUTES = ("newton:sdfTargetVoxelSize",)
    _OPTIONAL_ATTRIBUTES = (
        *_NON_NEGATIVE_FLOAT_ATTRIBUTES,
        *_POSITIVE_FLOAT_ATTRIBUTES,
        "newton:sdfMaxResolution",
        "newton:sdfNarrowBandInner",
        "newton:sdfNarrowBandOuter",
        "newton:sdfTextureFormat",
        "newton:hydroelasticStiffness",
    )
    _SDF_TEXTURE_FORMATS = {"uint8", "uint16", "float32"}
    _HYDROELASTIC_ENABLED_ATTR = "newton:hydroelasticEnabled"
    # An authored SDF source that satisfies the "hydroelastic requires an SDF source"
    # parse-time rule. A mesh may also carry an attached mesh.sdf, which cannot be
    # detected from USD authoring, so a missing source is a warning, not a failure.
    _SDF_SOURCE_ATTRS = (
        "newton:sdfMaxResolution",
        "newton:sdfTargetVoxelSize",
    )

    def _get_authored_value(self, prim: Usd.Prim, attr_name: str):
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return None

        value = attr.Get()
        if value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF collider '{prim.GetPath()}' has no value for attribute '{attr_name}'.",
                at=attr,
            )
        return value

    def _validate_non_negative_float(self, prim: Usd.Prim, attr_name: str, value) -> None:
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_positive_float(self, prim: Usd.Prim, attr_name: str, value) -> None:
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value <= 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be positive.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_positive_integer(self, prim: Usd.Prim, attr_name: str, value) -> None:
        numeric_value = _as_float(value)
        if numeric_value is None or numeric_value < 1 or numeric_value != int(numeric_value):
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be a positive integer.",
                at=prim.GetAttribute(attr_name),
            )
            return
        if int(numeric_value) % 8 != 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be divisible by 8.",
                at=prim.GetAttribute(attr_name),
            )

    def _validate_non_empty_token(self, prim: Usd.Prim, attr_name: str, value) -> None:
        token_value = str(value)
        if not token_value:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be non-empty.",
                at=prim.GetAttribute(attr_name),
            )
            return
        if attr_name == "newton:sdfTextureFormat" and token_value not in self._SDF_TEXTURE_FORMATS:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton SDF attribute '{attr_name}' on '{prim.GetPath()}' must be one of "
                    f"{sorted(self._SDF_TEXTURE_FORMATS)}."
                ),
                at=prim.GetAttribute(attr_name),
            )

    def _validate_narrow_band(self, prim: Usd.Prim, inner, outer) -> None:
        numeric_inner = _as_float(inner)
        numeric_outer = _as_float(outer)

        if inner is not None and numeric_inner is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute 'newton:sdfNarrowBandInner' on '{prim.GetPath()}' must be numeric.",
                at=prim.GetAttribute("newton:sdfNarrowBandInner"),
            )
        if outer is not None and numeric_outer is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=f"Newton SDF attribute 'newton:sdfNarrowBandOuter' on '{prim.GetPath()}' must be numeric.",
                at=prim.GetAttribute("newton:sdfNarrowBandOuter"),
            )
        if numeric_inner is not None and numeric_outer is not None and numeric_inner >= numeric_outer:
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton SDF collider '{prim.GetPath()}' must satisfy "
                    "newton:sdfNarrowBandInner < newton:sdfNarrowBandOuter."
                ),
                at=prim,
            )

    def _validate_hydroelastic(self, prim: Usd.Prim, values: dict) -> None:
        enabled_attr = prim.GetAttribute(self._HYDROELASTIC_ENABLED_ATTR)
        if not enabled_attr.IsValid() or not enabled_attr.HasAuthoredValueOpinion():
            return
        enabled = enabled_attr.Get()
        if not isinstance(enabled, bool):
            self._AddFailedCheck(
                requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
                message=(
                    f"Newton SDF attribute '{self._HYDROELASTIC_ENABLED_ATTR}' on '{prim.GetPath()}' "
                    "must be a boolean."
                ),
                at=enabled_attr,
            )
            return
        if not enabled:
            return
        # hydroelasticEnabled = true requires an authored SDF source (or an attached
        # mesh.sdf, which USD authoring cannot express -> warn rather than fail).
        if any(values.get(attr_name) is not None for attr_name in self._SDF_SOURCE_ATTRS):
            return
        self._AddWarning(
            requirement=self.NEWTON_SDF_ATTRIBUTES_REQUIREMENT,
            message=(
                f"Newton SDF collider '{prim.GetPath()}' sets "
                f"{self._HYDROELASTIC_ENABLED_ATTR} = true but authors no SDF source "
                "(newton:sdfMaxResolution or newton:sdfTargetVoxelSize). Newton requires an SDF "
                "source at parse time unless the mesh carries an attached mesh.sdf."
            ),
            at=prim,
        )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not _has_newton_sdf_collision_api(prim) or not prim.IsA(UsdGeom.Gprim):
            return

        values = {attr_name: self._get_authored_value(prim, attr_name) for attr_name in self._OPTIONAL_ATTRIBUTES}

        for attr_name in self._NON_NEGATIVE_FLOAT_ATTRIBUTES:
            if values[attr_name] is not None:
                self._validate_non_negative_float(prim, attr_name, values[attr_name])

        for attr_name in self._POSITIVE_FLOAT_ATTRIBUTES:
            if values[attr_name] is not None:
                self._validate_positive_float(prim, attr_name, values[attr_name])

        if values["newton:sdfMaxResolution"] is not None:
            self._validate_positive_integer(prim, "newton:sdfMaxResolution", values["newton:sdfMaxResolution"])

        self._validate_narrow_band(prim, values["newton:sdfNarrowBandInner"], values["newton:sdfNarrowBandOuter"])

        texture_format = values["newton:sdfTextureFormat"]
        if texture_format is not None:
            self._validate_non_empty_token(prim, "newton:sdfTextureFormat", texture_format)

        if values["newton:hydroelasticStiffness"] is not None:
            self._validate_positive_float(
                prim,
                "newton:hydroelasticStiffness",
                values["newton:hydroelasticStiffness"],
            )

        self._validate_hydroelastic(prim, values)


@usd_validation_nvidia.register_rule("NewtonMassAttributes")
@usd_validation_nvidia.register_requirements(cap.PhysicsRigidBodiesRequirements.NEWTON_MAS_001, override=True)
class NewtonMassAttributesChecker(usd_validation_nvidia.BaseRuleChecker):
    """NEWTON.MAS.001 - validate NewtonMassAPI placement and authored mass attribute values."""

    NEWTON_MASS_REQUIREMENT = cap.PhysicsRigidBodiesRequirements.NEWTON_MAS_001

    _MASS_MODEL_ATTR = "newton:massModel"
    _INERTIA_ATTR = "newton:inertia"
    _SHELL_THICKNESS_ATTR = "newton:shellThickness"
    _ALLOWED_MASS_MODELS = ("solid", "shell")

    def _newton_mass_attrs_authored(self, prim: Usd.Prim) -> bool:
        for attr_name in (self._INERTIA_ATTR, self._MASS_MODEL_ATTR, self._SHELL_THICKNESS_ATTR):
            attr = prim.GetAttribute(attr_name)
            if attr.IsValid() and attr.HasAuthoredValueOpinion():
                return True
        return False

    def _validate_inertia(self, prim: Usd.Prim) -> None:
        value = _authored_value(prim, self._INERTIA_ATTR)
        if value is None:
            return
        elements = list(value)
        if not elements:
            # Empty array is the "no opinion" default; standard mass resolution applies.
            return
        attr = prim.GetAttribute(self._INERTIA_ATTR)
        if len(elements) != 6:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._INERTIA_ATTR}' on '{prim.GetPath()}' must have exactly 6 elements "
                    f"[Ixx, Iyy, Izz, Ixy, Ixz, Iyz], got {len(elements)}."
                ),
                at=attr,
            )
            return
        numeric = [_as_float(item) for item in elements]
        if any(value is None for value in numeric):
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=f"'{self._INERTIA_ATTR}' on '{prim.GetPath()}' must contain only finite numbers.",
                at=attr,
            )
            return
        if any(diagonal < 0 for diagonal in numeric[:3]):
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._INERTIA_ATTR}' on '{prim.GetPath()}' has a negative diagonal moment "
                    "(Ixx, Iyy, Izz must be non-negative)."
                ),
                at=attr,
            )

    def _validate_mass_model(self, prim: Usd.Prim) -> None:
        value = _authored_value(prim, self._MASS_MODEL_ATTR)
        if value is None:
            return
        if str(value) not in self._ALLOWED_MASS_MODELS:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._MASS_MODEL_ATTR}' on '{prim.GetPath()}' must be 'solid' or 'shell', " f"got '{value}'."
                ),
                at=prim.GetAttribute(self._MASS_MODEL_ATTR),
            )

    def _validate_shell_thickness(self, prim: Usd.Prim) -> None:
        value = _authored_value(prim, self._SHELL_THICKNESS_ATTR)
        if value is None:
            return
        # -inf is the sentinel that lets the active solver choose the thickness.
        if isinstance(value, float) and value == float("-inf"):
            return
        numeric_value = _as_float(value)
        attr = prim.GetAttribute(self._SHELL_THICKNESS_ATTR)
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._SHELL_THICKNESS_ATTR}' on '{prim.GetPath()}' must be a finite number "
                    "or the -inf sentinel that defers to the solver."
                ),
                at=attr,
            )
            return
        if numeric_value <= 0:
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"'{self._SHELL_THICKNESS_ATTR}' on '{prim.GetPath()}' must be greater than 0 "
                    "(or the -inf sentinel)."
                ),
                at=attr,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        has_api = _has_applied_api_schema(prim, _NEWTON_MASS_API)
        if not has_api and not self._newton_mass_attrs_authored(prim):
            return

        if not prim.IsA(UsdGeom.Xformable):
            self._AddFailedCheck(
                requirement=self.NEWTON_MASS_REQUIREMENT,
                message=(
                    f"NewtonMassAPI / Newton mass attributes on '{prim.GetPath()}' require an Xformable prim, "
                    f"got '{prim.GetTypeName()}'."
                ),
                at=prim,
            )
            return

        self._validate_inertia(prim)
        self._validate_mass_model(prim)
        self._validate_shell_thickness(prim)

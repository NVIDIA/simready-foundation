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
__all__ = ["BaseArticulationValidation"]

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics

_NEWTON_ARTICULATION_ROOT_API = "NewtonArticulationRootAPI"
_NEWTON_SELF_COLLISION_ATTR = "newton:selfCollisionEnabled"
_MUJOCO_ARTICULATION_ROOT_API = "MjcArticulationRootAPI"
_MUJOCO_ARTICULATION_ROOT_TYPE = "MjcArticulationRoot"


def _applied_api_schemas(prim: Usd.Prim) -> set[str]:
    schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
    op = prim.GetMetadata("apiSchemas")
    if op is None:
        return schemas
    for items in (
        op.explicitItems,
        op.prependedItems,
        op.appendedItems,
        op.addedItems,
        op.orderedItems,
    ):
        schemas.update(str(schema) for schema in items)
    return schemas


def _has_applied_api_schema(prim: Usd.Prim, schema_name: str) -> bool:
    return schema_name in _applied_api_schemas(prim)


# NOTE: Unusual BA_002 registration setup.
#
# The real non-adjacent collision-mesh check (formerly
# ``NonAdjacentCollisionMeshesDoNotClash``) needs a *live* PhysX simulation step
# and only runs inside Isaac Sim / Kit (carb, usdrt, omni.physics, omni.physx).
# Shipping that checker here would either hard-depend on Kit or silently pass
# in standalone USD validation, which is misleading.
#
# Features/profiles only resolve requirements that are present in
# ``RequirementsRegistry``, and today that happens via ``@register_requirements``
# on a checker class -- there is no declare-only API. So this placeholder exists
# solely to define BA_002 for ``FET_024_PHYSX`` / profile loading.
#
# Load-order handling:
# - If Isaac already registered a real BA_002 checker, skip this placeholder
#   (``override=False`` would raise rather than no-op).
# - If this tier registers first, map BA_002 to the placeholder with
#   ``override=True``. The Isaac checker also registers with ``override=True``,
#   so it replaces this mapping when its extension loads.
# - Do not add the placeholder to ``CategoryRuleRegistry``: it exists only for
#   requirement/profile resolution and is selected through the requirement
#   mapping during standalone validation.
# Standalone validation emits a warning to make clear that BA_002 was not
# evaluated; it does not invent a pass or block profile generation.


class RuntimeOnlyBA002Registration(usd_validation_nvidia.BaseRuleChecker):
    """Register BA.002 without pretending to perform its runtime-only check."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Report that the runtime-only BA.002 check was not evaluated."""
        self._AddWarning(
            requirement=cap.BaseArticulationRequirements.BA_002,
            message="BA.002 requires the Isaac Sim / Kit PhysX runtime and was not evaluated.",
            at=stage,
        )


def register_ba002_placeholder() -> bool:
    """Register the runtime-only BA_002 placeholder when no checker exists yet.

    Returns:
        True if the placeholder was registered; False if BA_002 was already
        implemented (e.g. Isaac Sim loaded its real checker first).
    """
    ba002 = cap.BaseArticulationRequirements.BA_002
    if usd_validation_nvidia.RequirementsRegistry().is_implemented(ba002):
        return False
    usd_validation_nvidia.register_requirements(ba002, override=True)(RuntimeOnlyBA002Registration)
    return True


register_ba002_placeholder()


@usd_validation_nvidia.register_rule("BaseArticulation")
@usd_validation_nvidia.register_requirements(cap.BaseArticulationRequirements.BA_001, override=True)
class HasArticulationRoot(usd_validation_nvidia.BaseRuleChecker):
    """Validates that exactly one prim in the stage has the ArticulationRootAPI.

    Skipped on rigid-body-only stages (vehicles, non-articulated props) which are
    not expected to carry ``ArticulationRootAPI`` -- the check only fires when the
    stage has joints. Fails on 0 roots (Isaac behavior) and on >1 roots (foundation
    multi-root detection).
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check if the stage has none or more than one articulation root.

        Args:
            stage: The USD stage to validate.
        """
        # Skip rigid-body-only stages: no joints means no articulation is expected.
        if not any(prim.IsA(UsdPhysics.Joint) for prim in stage.Traverse()):
            return
        roots = []
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                roots.append(prim)
        if len(roots) == 0:
            self._AddFailedCheck(
                requirement=cap.BaseArticulationRequirements.BA_001,
                message=f"Articulation Root API is not set on any prim in the stage",
                at=stage,
            )

        if len(roots) > 1:
            self._AddFailedCheck(
                requirement=cap.BaseArticulationRequirements.BA_001,
                message=f"More than one Articulation Root API is set on the stage",
                at=stage,
            )


@usd_validation_nvidia.register_rule("BaseArticulation")
@usd_validation_nvidia.register_requirements(cap.BaseArticulationRequirements.NEWTON_BA_001, override=True)
class NewtonArticulationRootConfig(usd_validation_nvidia.BaseRuleChecker):
    """Validates Newton articulation root configuration authored on the asset."""

    NEWTON_ARTICULATION_ROOT_REQUIREMENT = cap.BaseArticulationRequirements.NEWTON_BA_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        articulation_roots = []
        for prim in stage.Traverse():
            has_physics_root = prim.HasAPI(UsdPhysics.ArticulationRootAPI)
            has_newton_root_api = _has_applied_api_schema(prim, _NEWTON_ARTICULATION_ROOT_API)
            has_self_collision_attr = _has_authored_newton_self_collision_attr(prim)

            if has_physics_root:
                articulation_roots.append(prim)

            if has_newton_root_api and not has_physics_root:
                self._AddFailedCheck(
                    requirement=self.NEWTON_ARTICULATION_ROOT_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' applies NewtonArticulationRootAPI but is not a "
                        "UsdPhysics.ArticulationRootAPI prim."
                    ),
                    at=prim,
                )

            if has_self_collision_attr and not has_physics_root:
                self._AddFailedCheck(
                    requirement=self.NEWTON_ARTICULATION_ROOT_REQUIREMENT,
                    message=(
                        f"Prim '{prim.GetPath()}' authors {_NEWTON_SELF_COLLISION_ATTR} but is not the "
                        "UsdPhysics articulation root."
                    ),
                    at=prim.GetAttribute(_NEWTON_SELF_COLLISION_ATTR),
                )

        if len(articulation_roots) != 1:
            self._AddFailedCheck(
                requirement=self.NEWTON_ARTICULATION_ROOT_REQUIREMENT,
                message=(
                    "Newton articulation configuration requires exactly one "
                    f"UsdPhysics.ArticulationRootAPI prim; found {len(articulation_roots)}."
                ),
                at=stage,
            )
            return

        root = articulation_roots[0]
        self_collision_attr = root.GetAttribute(_NEWTON_SELF_COLLISION_ATTR)
        if not self_collision_attr.IsValid() or not self_collision_attr.HasAuthoredValueOpinion():
            self._AddFailedCheck(
                requirement=self.NEWTON_ARTICULATION_ROOT_REQUIREMENT,
                message=(
                    f"Newton articulation root '{root.GetPath()}' must author " f"bool {_NEWTON_SELF_COLLISION_ATTR}."
                ),
                at=root,
            )
            return

        value = self_collision_attr.Get()
        if not isinstance(value, bool):
            self._AddFailedCheck(
                requirement=self.NEWTON_ARTICULATION_ROOT_REQUIREMENT,
                message=(
                    f"Newton articulation root '{root.GetPath()}' has {_NEWTON_SELF_COLLISION_ATTR} "
                    "but it is not a boolean value."
                ),
                at=self_collision_attr,
            )


@usd_validation_nvidia.register_rule("BaseArticulation")
@usd_validation_nvidia.register_requirements(cap.BaseArticulationRequirements.MUJOCO_BA_001, override=True)
class MuJoCoStandardArticulationRoot(usd_validation_nvidia.BaseRuleChecker):
    """Validates that MuJoCo articulation authoring stays on standard USD schemas."""

    MUJOCO_ARTICULATION_ROOT_REQUIREMENT = cap.BaseArticulationRequirements.MUJOCO_BA_001

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if _has_applied_api_schema(prim, _MUJOCO_ARTICULATION_ROOT_API):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ARTICULATION_ROOT_REQUIREMENT,
                message=(
                    f"Prim '{prim.GetPath()}' applies unsupported {_MUJOCO_ARTICULATION_ROOT_API}. "
                    "Use standard UsdPhysics.ArticulationRootAPI for MuJoCo articulations."
                ),
                at=prim,
            )

        if prim.GetTypeName() == _MUJOCO_ARTICULATION_ROOT_TYPE:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ARTICULATION_ROOT_REQUIREMENT,
                message=(
                    f"Prim '{prim.GetPath()}' uses unsupported type {_MUJOCO_ARTICULATION_ROOT_TYPE}. "
                    "Use a standard USD prim type with UsdPhysics.ArticulationRootAPI."
                ),
                at=prim,
            )


def _has_authored_newton_self_collision_attr(prim: Usd.Prim) -> bool:
    attr = prim.GetAttribute(_NEWTON_SELF_COLLISION_ATTR)
    return attr.IsValid() and attr.HasAuthoredValueOpinion()

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
__all__ = ["NewtonArticulationRootConfig"]

import simready.foundation.tier_newton.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics

from simready.foundation.tier_newton.rules_and_reqs._common import _has_applied_api_schema

_NEWTON_ARTICULATION_ROOT_API = "NewtonArticulationRootAPI"
_NEWTON_SELF_COLLISION_ATTR = "newton:selfCollisionEnabled"


def _has_authored_newton_self_collision_attr(prim: Usd.Prim) -> bool:
    attr = prim.GetAttribute(_NEWTON_SELF_COLLISION_ATTR)
    return attr.IsValid() and attr.HasAuthoredValueOpinion()


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

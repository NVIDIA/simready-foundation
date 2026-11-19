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
"""Static optimization capabilities checked on one composed USD stage."""

from __future__ import annotations

import simready.foundation.tier_isaac.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics, UsdShade

from ._common import (
    inactive_render_collision_schemas,
    is_dynamic_body,
    is_joint_enabled,
    is_rigid_body,
    is_unbreakable,
    joints,
    mergeable_visual_meshes,
    needs_separate_simulation,
    resolved_joint_bodies,
)


@usd_validation_nvidia.register_rule("Optimizations")
@usd_validation_nvidia.register_requirements(cap.Requirements.OPT_001, override=True)
class MergeableBodyPairChecker(usd_validation_nvidia.BaseRuleChecker):  # type: ignore[misc]
    """OPT.001 - no two dynamic bodies remain welded by an unbreakable fixed joint."""

    REQUIREMENT = cap.Requirements.OPT_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for joint_prim in joints(stage):
            if not joint_prim.IsActive() or not UsdPhysics.FixedJoint(joint_prim):
                continue
            if not is_unbreakable(joint_prim)[0]:
                continue  # a finite break force is authored behaviour, not an oversight
            if not is_joint_enabled(joint_prim):
                continue  # the author disabled it, so it welds nothing

            body0, body1 = resolved_joint_bodies(stage, joint_prim)
            if not body0 or not body1:
                continue  # one end is the world; root fixation is a separate decision
            if body0[0] == body1[0]:
                continue  # both ends resolve to the same body

            pair = [stage.GetPrimAtPath(body0[0]), stage.GetPrimAtPath(body1[0])]
            if not all(is_dynamic_body(p) for p in pair if p):
                continue  # kinematic or disabled bodies are pinned deliberately
            if any(needs_separate_simulation(p) for p in pair if p):
                continue  # the asset says why this body has to stay

            self._AddFailedCheck(
                f"<{joint_prim.GetPath()}> is an unbreakable fixed joint between two dynamic "
                f"rigid bodies, <{body0[0]}> and <{body1[0]}>, with no supported sensor or "
                f"contact-report exclusion. Run fixed_joint_rigid_body_merge on a staged "
                f"copy; the adapter checks mass and transform preconditions before merging.",
                at=joint_prim,
                requirement=self.REQUIREMENT,
            )


@usd_validation_nvidia.register_rule("Optimizations")
@usd_validation_nvidia.register_requirements(cap.Requirements.OPT_002, override=True)
class MultipleVisualMeshesChecker(usd_validation_nvidia.BaseRuleChecker):  # type: ignore[misc]
    """OPT.002 - no body owns two or more mergeable visual meshes."""

    REQUIREMENT = cap.Requirements.OPT_002

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for body in Usd.PrimRange(
            default_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
        ):
            if not is_rigid_body(body):
                continue
            meshes = mergeable_visual_meshes(body)
            if len(meshes) < 2:
                continue
            self._AddFailedCheck(
                f"<{body.GetPath()}> owns {len(meshes)} visual meshes that can be merged: "
                f"{sorted(str(m.GetPath()) for m in meshes)}. Run rigid_body_visual_mesh_merge "
                f"on a staged copy. Collision geometry, other purposes, invisible meshes, "
                f"and instance proxies are excluded.",
                at=body,
                requirement=self.REQUIREMENT,
            )


@usd_validation_nvidia.register_rule("Optimizations")
@usd_validation_nvidia.register_requirements(cap.Requirements.OPT_003, override=True)
class InactiveRenderCollisionSchemasChecker(usd_validation_nvidia.BaseRuleChecker):  # type: ignore[misc]
    """OPT.003 - render-only prims carry no inactive collision schema stack."""

    REQUIREMENT = cap.Requirements.OPT_003

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for prim in Usd.PrimRange(
            default_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
        ):
            schemas = inactive_render_collision_schemas(prim)
            if not schemas:
                continue
            self._AddFailedCheck(
                f"<{prim.GetPath()}> is renderable but has no active collision shape, "
                f"so its collision schemas are inactive: {schemas}. Run "
                f"remove_inactive_render_collision_schemas on a staged copy. Do not enable "
                f"collision merely to silence this check.",
                at=prim,
                requirement=self.REQUIREMENT,
            )


@usd_validation_nvidia.register_rule("Optimizations")
@usd_validation_nvidia.register_requirements(cap.Requirements.OPT_004, override=True)
class MaterialXRenderContextChecker(usd_validation_nvidia.BaseRuleChecker):  # type: ignore[misc]
    """OPT.004 - MaterialX render contexts have no connected outputs."""

    REQUIREMENT = cap.Requirements.OPT_004

    def CheckStage(self, stage: Usd.Stage) -> None:
        if not stage.GetDefaultPrim():
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return
        for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
            material = UsdShade.Material(prim)
            if not material:
                continue
            outputs = [output.GetFullName() for output in material.GetOutputs()
                       if len(output.GetBaseName().split(":")) == 2
                       and output.GetBaseName().split(":")[0].lower() == "mtlx"
                       and output.GetAttr().GetConnections()]
            if outputs:
                self._AddFailedCheck(
                    f"<{prim.GetPath()}> has connected MaterialX outputs {outputs}. "
                    "Run remove_materialx_shaders on a staged copy to keep or derive "
                    "a USD Preview Surface and remove the MaterialX network.",
                    at=prim, requirement=self.REQUIREMENT,
                )

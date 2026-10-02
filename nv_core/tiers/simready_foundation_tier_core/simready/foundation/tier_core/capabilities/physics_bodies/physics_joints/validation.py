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
import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd, UsdPhysics

from ..utils import BaseRuleCheckerWCache


@usd_validation_nvidia.register_rule("PhysicsJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsJointsRequirements.JT_001, override=True)
class PhysicsJointCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """Flags joints that are not connected to anything.

    A joint is dangling when either (a) no body relationships are specified at all,
    or (b) body relationships are specified but none of the targeted prims exist in
    the scene. A joint attached to the implicit world (exactly one body specified)
    is considered connected and passes.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for prim in Usd.PrimRange(default_prim):
            if not prim.IsA(UsdPhysics.Joint):
                continue

            joint = UsdPhysics.Joint(prim)
            body0_rel = joint.GetBody0Rel()
            body1_rel = joint.GetBody1Rel()
            targets = []
            if body0_rel:
                targets.extend(body0_rel.GetTargets())
            if body1_rel:
                targets.extend(body1_rel.GetTargets())

            # (a) No connected bodies specified at all -> dangling joint.
            if not targets:
                self._AddFailedCheck(
                    requirement=cap.PhysicsJointsRequirements.JT_001,
                    message=f"Joint <{prim.GetPath()}> is not connected to any body (no body relationships specified).",
                    at=prim,
                )
                continue

            # (b) Bodies specified but none of the targeted prims exist in the scene.
            existing_targets = [t for t in targets if stage.GetPrimAtPath(t).IsValid()]
            if not existing_targets:
                missing = ", ".join(str(t) for t in targets)
                self._AddFailedCheck(
                    requirement=cap.PhysicsJointsRequirements.JT_001,
                    message=(
                        f"Joint <{prim.GetPath()}> references body targets that do not exist in the scene: [{missing}]."
                    ),
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsJoints")
@usd_validation_nvidia.register_requirements(
    cap.PhysicsJointsRequirements.JT_ART_003,
    override=True,
)
class ArticulationChecker(BaseRuleCheckerWCache):
    # The nested-articulation (JT.ART.002) and static-body (JT.ART.004) checks were removed
    # from this checker; they are covered by usd-validation-nvidia's ArticulationChecker (OMPE-99310).
    # Note: this checker previously reported the static-body check as JT.ART.003 and the
    # kinematic-body check as JT.ART.004, which was swapped relative to the requirement docs.
    # Per the docs, JT.ART.003 is the kinematic-body check.
    _ARTICULATION_ON_KINEMATIC_BODY_REQUIREMENT = cap.PhysicsJointsRequirements.JT_ART_003

    _ARTICULATION_ON_KINEMATIC_BODY_MESSAGE = "ArticulationRootAPI definition on a kinematic rigid body is not allowed."

    def CheckPrim(self, usd_prim: Usd.Prim):
        art_api = UsdPhysics.ArticulationRootAPI(usd_prim)

        if not art_api:
            return

        # Check rigid body kinematic errors
        rbo_api = UsdPhysics.RigidBodyAPI(usd_prim)
        if rbo_api:
            # Check if kinematic is enabled
            kinematic_enabled = rbo_api.GetKinematicEnabledAttr().Get()
            if kinematic_enabled:
                self._AddFailedCheck(
                    message=self._ARTICULATION_ON_KINEMATIC_BODY_MESSAGE,
                    at=usd_prim,
                    requirement=self._ARTICULATION_ON_KINEMATIC_BODY_REQUIREMENT,
                )

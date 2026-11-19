# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validate AF.001, the sole Object Forward feature requirement."""

import simready.foundation.tier_core.requirements as cap
from pxr import Usd
from usd_validation_nvidia import BaseRuleChecker, register_requirements
from simready.foundation.tier_core.asset_frame import FORWARD_DIRECTION, read_forward_direction


@register_requirements(cap.AssetFrameRequirements.AF_001)
class AssetFrameChecker(BaseRuleChecker):
    def _check(self, prim):
        try:
            read_forward_direction(prim)
        except ValueError as error:
            self._AddFailedCheck(message=str(error), at=prim, requirement=cap.AssetFrameRequirements.AF_001)

    def CheckStage(self, stage):
        root = stage.GetDefaultPrim()
        if not root:
            self._AddFailedCheck(
                message="AF.001 requires a valid defaultPrim asset root",
                at=stage.GetPseudoRoot(),
                requirement=cap.AssetFrameRequirements.AF_001,
            )
            return
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
            if prim == root or prim.HasProperty(FORWARD_DIRECTION):
                self._check(prim)

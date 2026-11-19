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

import simready.foundation.tier_template.requirements as cap
import usd_validation_nvidia
from pxr import Usd


@usd_validation_nvidia.register_rule("TemplateSmoke")
@usd_validation_nvidia.register_requirements(cap.SmokeRequirements.TMP_001, override=True)
class StageHasDefaultPrimChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates that the stage declares a defaultPrim (TMP.001)."""

    TEMPLATE_SMOKE_REQUIREMENT = cap.SmokeRequirements.TMP_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim.",
                at=stage,
                requirement=self.TEMPLATE_SMOKE_REQUIREMENT,
            )

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
import omni.capabilities as cap
from omni.asset_validator import (
    BaseRuleChecker,
    register_requirements,
    register_rule,
)
from pxr import Usd


@register_rule("Sample")
@register_requirements(cap.SampleRequirements.SAMP_001)
class SampleNameChecker(BaseRuleChecker):
    """
    The default prim must be named "Foo".
    """

    def CheckStage(self, stage: Usd.Stage):
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim.", at=stage, requirement=cap.SampleRequirements.SAMP_001)
            return
        if default_prim.GetName() != "Foo":
            self._AddFailedCheck(
                "Root prim must be named 'Foo'.", at=default_prim, requirement=cap.SampleRequirements.SAMP_001
            )
            return

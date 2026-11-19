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
"""Example adapter for the template tier smoke feature.

Ensures the output stage has a ``defaultPrim`` (``TMP.001`` / ``FET_1000_TEMPLATE``).

To pull in an external mutation package (for example the Isaac asset
transformer used by ``physx_to_isaacsim``), import it at module scope so CIP
discovery fails loudly when the dependency is missing:

    from isaacsim.asset.transformer import AssetTransformerManager, RuleProfile
"""

from omni.cip.configurable.feature_adapter import feature_adapter
from pxr import Usd

# Example of importing external transformer code (leave commented in the
# template so the module loads without Isaac Sim installed):
#
# from isaacsim.asset.transformer import AssetTransformerManager, RuleProfile


@feature_adapter(
    name="standard_to_template_smoke",
    input_feature_id="CAP000_Core.0-1-0",
    output_feature_id="CAP1000_TemplateSmoke.Template.0-1-0",
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage) -> None:
    """Ensure template smoke readiness (stage defaultPrim)."""
    if not output_stage.GetDefaultPrim():
        source_default = input_stage.GetDefaultPrim()
        if not source_default:
            raise ValueError("Input stage must have a defaultPrim for FET_1000_TEMPLATE smoke")
        output_default = output_stage.GetPrimAtPath(source_default.GetPath())
        if not output_default:
            raise ValueError(
                f"Output stage is missing input defaultPrim path: {source_default.GetPath()}"
            )
        output_stage.SetDefaultPrim(output_default)

    output_stage.GetRootLayer().Save()

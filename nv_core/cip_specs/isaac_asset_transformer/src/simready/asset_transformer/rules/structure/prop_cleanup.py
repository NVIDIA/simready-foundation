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
"""Remove Kit session artifacts from a generated prop package."""

from __future__ import annotations

import fnmatch
import os

from pxr import Sdf
from simready.asset_transformer import RuleConfigurationParam, RuleInterface

from .. import utils


class PropCleanupRule(RuleInterface):
    """Strip viewport prims and layer metadata that are not asset content."""

    def get_configuration_parameters(self) -> list[RuleConfigurationParam]:
        return [
            RuleConfigurationParam(
                name="root_prim_patterns",
                display_name="Root Prim Patterns",
                param_type=list,
                description="Root prim name patterns removed from every generated layer.",
                default_value=["Render", "OmniverseKit_*"],
            ),
            RuleConfigurationParam(
                name="custom_layer_data_keys",
                display_name="Custom Layer Data Keys",
                param_type=list,
                description="Kit session keys removed from customLayerData.",
                default_value=["cameraSettings", "omni_layer", "renderSettings"],
            ),
        ]

    def process_rule(self) -> str | None:
        params = self.args.get("params", {}) or {}
        root_patterns = params.get("root_prim_patterns") or ["Render", "OmniverseKit_*"]
        metadata_keys = params.get("custom_layer_data_keys") or [
            "cameraSettings",
            "omni_layer",
            "renderSettings",
        ]

        changed_layers = 0
        for directory, _, filenames in os.walk(self.package_root):
            for filename in sorted(filenames):
                if os.path.splitext(filename)[1].lower() not in utils.USD_EXTENSIONS:
                    continue
                layer_path = os.path.join(directory, filename)
                layer = Sdf.Layer.FindOrOpen(layer_path)
                if layer is None:
                    continue

                changed = False
                root_names = [prim.name for prim in layer.rootPrims]
                for root_name in root_names:
                    if any(fnmatch.fnmatchcase(root_name, pattern) for pattern in root_patterns):
                        del layer.pseudoRoot.nameChildren[root_name]
                        changed = True

                custom_data = dict(layer.customLayerData or {})
                for key in metadata_keys:
                    if key in custom_data:
                        del custom_data[key]
                        changed = True
                if changed:
                    layer.customLayerData = custom_data
                    layer.Save()
                    self.add_affected_stage(layer_path)
                    changed_layers += 1

        self.log_operation(f"PropCleanupRule cleaned {changed_layers} layer(s)")
        return None

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
"""Rule for applying the Isaac Sim robot schema to an asset prim."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

# Isaac Sim robot schema - requires Isaac Sim extensions to be available
import usd.schema.isaac.robot_schema as rs
from pxr import Sdf, Usd
from usd.schema.isaac.robot_schema import utils as robot_schema_utils

# Use relative imports for local transformer package
from ... import RuleConfigurationParam, RuleInterface
from . import utils


class RobotSchemaRule(RuleInterface):
    """Apply Isaac Sim robot schema to a target prim.

    Uses the default prim when no explicit prim path is provided.
    """

    def _get_destination_layer(self, destination: str, stage_name: str) -> tuple[Optional[Sdf.Layer], str]:
        destination_label = os.path.join(destination, stage_name) if stage_name else destination
        if not destination_label:
            return None, ""

        destination_path = os.path.join(self.package_root, destination_label)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        layer = Sdf.Layer.FindOrOpen(destination_path)
        if not layer:
            layer = Sdf.Layer.CreateNew(destination_path)
            utils.copy_stage_metadata(self.source_stage, layer)
        return layer, destination_label

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters.
        """
        return [
            RuleConfigurationParam(
                name="prim_path",
                display_name="Prim Path",
                param_type=str,
                description="Prim path to apply the Robot schema to. Defaults to the stage default prim.",
                default_value=None,
            ),
            RuleConfigurationParam(
                name="stage_name",
                display_name="Stage Name",
                param_type=str,
                description="Name of the output USD file for robot schema opinions.",
                default_value="robot_schema.usda",
            ),
        ]

    def process_rule(self) -> Optional[str]:
        """Apply Robot, Link, and Joint schemas and populate robot relationships.

        Returns:
            None (this rule does not change the working stage).
        """
        params = self.args.get("params", {}) or {}
        prim_path = params.get("prim_path") or ""
        stage_name = params.get("stage_name") or "robot_schema.usda"
        destination = self.destination_path or ""

        if not prim_path:
            default_prim = self.source_stage.GetDefaultPrim()
            if default_prim and default_prim.IsValid():
                prim_path = default_prim.GetPath().pathString
            else:
                self.log_operation("No default prim found, using /World")
                prim_path = "/World"

        robot_prim = self.source_stage.GetPrimAtPath(prim_path)
        if not robot_prim or not robot_prim.IsValid():
            self.log_operation(f"RobotSchemaRule skipped: invalid prim path {prim_path}")
            return None

        destination_layer, destination_label = self._get_destination_layer(destination, stage_name)
        if destination_layer:
            root_layer = self.source_stage.GetRootLayer()
            if destination_layer.identifier not in root_layer.subLayerPaths:
                root_layer.subLayerPaths.append(destination_layer.identifier)
                self.log_operation(f"Added robot schema layer as sublayer: {destination_layer.identifier}")
            edit_layer = destination_layer
            self.log_operation(f"RobotSchemaRule start prim={prim_path} destination={destination_label}")
        else:
            edit_layer = self.source_stage.GetRootLayer()
            self.log_operation(f"RobotSchemaRule start prim={prim_path} destination=source")

        with Usd.EditContext(self.source_stage, edit_layer):
            if not robot_prim.HasAPI(rs.Classes.ROBOT_API.value):
                rs.ApplyRobotAPI(robot_prim)
                self.log_operation("Applied RobotAPI to target prim")
            else:
                self.log_operation("RobotAPI already applied to target prim")

            root_link, root_joint = robot_schema_utils.PopulateRobotSchemaFromArticulation(
                self.source_stage,
                robot_prim,
                robot_prim,
            )

        if root_link:
            self.log_operation(f"Detected root link: {root_link.GetPath()}")
        else:
            self.log_operation("No articulation root link detected")

        if root_joint:
            self.log_operation(f"Detected root joint: {root_joint.GetPath()}")
        else:
            self.log_operation("No articulation root joint detected")

        if edit_layer:
            edit_prim = edit_layer.GetPrimAtPath(robot_prim.GetPath())
            self.log_operation(f"[RobotSchemaRule] edit_layer_prim_spec={bool(edit_prim)}")
            if edit_prim:
                self.log_operation(f"[RobotSchemaRule] edit_layer_apiSchemas={edit_prim.GetInfo('apiSchemas')}")

        edit_layer.Save()
        self.add_affected_stage(edit_layer.identifier)
        self.log_operation("RobotSchemaRule completed")

        return None

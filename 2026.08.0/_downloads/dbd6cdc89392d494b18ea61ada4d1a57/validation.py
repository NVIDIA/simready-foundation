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
"""Validators for Isaac Sim ROS 2 bridge OmniGraph wiring."""

from __future__ import annotations

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd

_ROS2_BRIDGE_PREFIX = "isaacsim.ros2.bridge."


def _node_type_token(prim: Usd.Prim) -> str | None:
    """Return authored OmniGraph node:type if present."""
    attr = prim.GetAttribute("node:type")
    if not attr:
        return None
    value = attr.Get()
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@usd_validation_nvidia.register_rule("RosBridge")
@usd_validation_nvidia.register_requirements(cap.RosBridgeRequirements.ROS_001, override=True)
class Ros2BridgeNodesPresent(usd_validation_nvidia.BaseRuleChecker):
    """ROS.001: at least one isaacsim.ros2.bridge.* OmniGraph node is authored."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        req = cap.RosBridgeRequirements.ROS_001
        found: list[str] = []

        for prim in stage.TraverseAll():
            node_type = _node_type_token(prim)
            if node_type and node_type.startswith(_ROS2_BRIDGE_PREFIX):
                found.append(f"{prim.GetPath()} ({node_type})")

        if not found:
            self._AddFailedCheck(
                "Stage has no OmniGraph nodes with node:type starting with "
                f"'{_ROS2_BRIDGE_PREFIX}'. Add at least one Isaac ROS 2 bridge node.",
                at=stage.GetDefaultPrim() or stage,
                requirement=req,
            )

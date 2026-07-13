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
import carb
import omni.ext
from isaacsim.asset.transformer import RuleRegistry

from .rules.flatten import FlattenRule
from .rules.geometries import GeometriesRoutingRule
from .rules.interface import InterfaceConnectionRule
from .rules.materials import MaterialsRoutingRule
from .rules.prims import PrimRoutingRule
from .rules.properties import PropertyRoutingRule
from .rules.robot_schema import RobotSchemaRule
from .rules.schemas import SchemaRoutingRule
from .rules.variants import VariantRoutingRule


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        """Register rule implementations with the global registry.

        Args:
            ext_id: Fully qualified extension identifier.
        """
        self._ext_id = ext_id
        carb.log_info(f"[isaacsim.asset.transformer.organizer] Startup: {ext_id}")
        registry = RuleRegistry()
        registry.register(FlattenRule)
        registry.register(GeometriesRoutingRule)
        registry.register(MaterialsRoutingRule)
        registry.register(PrimRoutingRule)
        registry.register(SchemaRoutingRule)
        registry.register(PropertyRoutingRule)
        registry.register(VariantRoutingRule)
        registry.register(RobotSchemaRule)
        registry.register(InterfaceConnectionRule)
        carb.log_info("[isaacsim.asset.transformer.organizer] Rules registered")

    def on_shutdown(self):
        """No-op on shutdown; rules remain registered for the session."""
        carb.log_info(f"[isaacsim.asset.transformer.organizer] Shutdown: {getattr(self, '_ext_id', '')}")

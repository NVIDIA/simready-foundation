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

from .manager import RuleRegistry


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        """Initialize the extension.

        Args:
            ext_id: Fully qualified extension identifier.

        Example:

        .. code-block:: python

            >>> import omni.ext
            >>> # Extension lifecycle is managed by Kit; this is called automatically.
        """
        self._ext_id = ext_id
        carb.log_info(f"[isaacsim.asset.transformer] Startup: {ext_id}")
        # Initialize the singleton rule registry so other modules can register rules.
        self._registry = RuleRegistry()
        carb.log_info("[isaacsim.asset.transformer] RuleRegistry initialized")

    def on_shutdown(self):
        """Tear down the extension and release resources."""
        carb.log_info(f"[isaacsim.asset.transformer] Shutdown: {getattr(self, '_ext_id', '')}")

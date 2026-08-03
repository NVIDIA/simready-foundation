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
"""
CLI entry point for simready.foundation.core.

Usage:
    python -m simready.foundation.core [options] ASSET

Registers all SimReady capabilities, features and validation rules, then
delegates to the usd_validation_nvidia CLI. All standard flags apply, e.g.:

    python -m simready.foundation.core --feature FET000_CORE asset.usda
    python -m simready.foundation.core --capability atomic_asset asset.usda
"""
from __future__ import annotations

from usd_validation_nvidia import PluginManager, cli_main

from ._plugin import SimReadyPlugin


def main() -> None:
    """Register the SimReady plugin (if not already loaded) and run the CLI."""
    plugin = None
    if not PluginManager().is_plugin_loaded("simready.foundation.core:SimReadyPlugin"):
        plugin = SimReadyPlugin()
        plugin.on_startup()
    try:
        cli_main()
    finally:
        if plugin is not None:
            plugin.on_shutdown()


if __name__ == "__main__":
    main()

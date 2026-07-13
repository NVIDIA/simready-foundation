# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
"""
CLI entry point for simready.foundation.core.

Usage:
    python -m simready.foundation.core [options] ASSET

Registers all SimReady capabilities, features and validation rules, then
delegates to the omni.asset_validator CLI. All standard flags apply, e.g.:

    python -m simready.foundation.core --feature FET000_CORE asset.usda
    python -m simready.foundation.core --capability atomic_asset asset.usda
"""
from __future__ import annotations

from omni.asset_validator import PluginManager, cli_main

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

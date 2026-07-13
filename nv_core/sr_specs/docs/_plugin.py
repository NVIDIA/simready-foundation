# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from __future__ import annotations

import sys

import omni

from omni.asset_validator import (
    register_capabilities,
    register_features,
    register_profiles,
    unregister_capabilities,
    unregister_features,
    unregister_profiles,
    unregister_requirements,
)
from omni.capabilities import Capabilities, Features, Profiles, Requirements

class SimReadyPlugin:
    """
    Plugin that registers all SimReady Foundation validation rules.

    This plugin implements the PluginProtocol required by the Asset Validator's
    entrypoint plugin system. It reuses the same setup and registration logic
    as the simready.foundation.core CLI wrapper.
    """

    def on_startup(self) -> None:
        """Ensure omni.asset_validator is resolved before importing capabilities."""
        omni.asset_validator = sys.modules["omni.asset_validator"]

        from . import capabilities  # noqa: F401
        register_capabilities(Capabilities)
        register_features(Features)
        register_profiles(Profiles)

    def on_shutdown(self) -> None:
        """Unregister requirements, capabilities, features, and profiles."""
        unregister_requirements(Requirements)
        unregister_capabilities(Capabilities)
        unregister_features(Features)
        unregister_profiles(Profiles)

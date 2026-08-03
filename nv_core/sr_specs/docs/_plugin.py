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

from __future__ import annotations

from omni.capabilities import Capabilities, Features, Profiles, Requirements
from usd_validation_nvidia import (
    register_capabilities,
    register_features,
    register_profiles,
    unregister_capabilities,
    unregister_features,
    unregister_profiles,
    unregister_requirements,
)


class SimReadyPlugin:
    """
    Plugin that registers all SimReady Foundation validation rules.

    This plugin implements the PluginProtocol required by the Asset Validator's
    entrypoint plugin system. It reuses the same setup and registration logic
    as the simready.foundation.core CLI wrapper.
    """

    def on_startup(self) -> None:
        """Ensure usd_validation_nvidia is resolved before importing capabilities."""
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

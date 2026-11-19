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
"""SimReady integration for the public Kit-free Isaac Asset Transformer."""

try:
    from isaacsim.asset.transformer import (
        AssetTransformerManager,
        ExecutionReport,
        RuleConfigurationParam,
        RuleExecutionResult,
        RuleInterface,
        RuleProfile,
        RuleRegistry,
        RuleSpec,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"isaacsim", "isaacsim.asset", "isaacsim.asset.transformer"}:
        raise
    raise ImportError(
        'Isaac transformation requires Python 3.12 and the optional dependencies; '
        'install them with pip install "simready-foundation-tier-core[isaac]".'
    ) from exc

# Register the PhysX (PhysicsJointStateAPI) and Isaac robot (IsaacRobotAPI)
# USD schemas before any stage is opened. USD builds its schema registry once
# per process, so a stage opened first would leave these applied APIs
# unregistered and hidden from Usd.Prim.GetAppliedSchemas() for the whole run.
import physx_usd_schemas  # noqa: E402, F401  # isort: skip
import usd.schema.isaac  # noqa: E402, F401  # isort: skip

from .api import load_profile, profile_transforms_dir, transform_package

__all__ = [
    "AssetTransformerManager",
    "ExecutionReport",
    "RuleConfigurationParam",
    "RuleExecutionResult",
    "RuleInterface",
    "RuleProfile",
    "RuleRegistry",
    "RuleSpec",
    "load_profile",
    "profile_transforms_dir",
    "transform_package",
]

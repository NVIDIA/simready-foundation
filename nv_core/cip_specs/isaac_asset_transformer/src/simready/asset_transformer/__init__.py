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
"""Kit-free framework for transforming USD assets into layered packages."""

from .api import load_profile, profile_transforms_dir, transform_package
from .manager import AssetTransformerManager, RuleRegistry
from .models import (
    ExecutionReport,
    RuleConfigurationParam,
    RuleExecutionResult,
    RuleProfile,
    RuleSpec,
)
from .rule_interface import RuleInterface

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

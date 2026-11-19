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

from simready.asset_transformer.rules import discover_rule_classes


def test_local_rule_catalog_contains_only_simready_specific_rules() -> None:
    names = {rule.__name__ for rule in discover_rule_classes()}
    assert names == {
        "InterfaceConnectionRule",
        "NeutralRuntimeVariantRule",
        "PropCleanupRule",
        "RuntimeInstanceRoutingRule",
        "ThumbnailCopyRule",
    }
    assert all(rule.__module__.startswith("simready.asset_transformer.rules.") for rule in discover_rule_classes())

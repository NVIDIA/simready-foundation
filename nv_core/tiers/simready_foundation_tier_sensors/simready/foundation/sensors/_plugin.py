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

# Generic tier scaffolding: identical across tiers, committed verbatim in each.

from __future__ import annotations


class SimReadyPlugin:
    """Framework plugin that registers this tier's validators.

    Discovered via the ``usd_validation_nvidia`` entry-point group. Importing the
    tier's ``capabilities`` hub imports every validator module in the tier; their
    ``@register_rule`` / ``@register_requirements`` decorators register the
    tier's rules and the requirements they enforce with ``usd_validation_nvidia``.

    Feature and profile registration is intentionally NOT performed here. Tiers
    expose their features/profiles as per-layer content sources via the
    ``simready.tier`` descriptor (see :mod:`._tier`), which the SimReady loader
    feeds into its existing layered, multi-source registration (all
    requirements, then all features, then all profiles). Keeping the plugin to
    just rules/requirements makes tiers additive and avoids every tier
    re-registering the full stack on its own.
    """

    def on_startup(self) -> None:
        # Import side-effects do the work: the capabilities hub imports each
        # validator module, whose decorators register the rules + requirements.
        from . import capabilities  # noqa: F401

    def on_shutdown(self) -> None:
        # Registry teardown is owned by the loader (it clears non-built-in
        # entries by namespace before each load), so the tier plugin has nothing
        # to unwind here.
        pass

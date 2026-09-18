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

"""SimReady validation tier package.

A self-contained, separately-publishable slice of SimReady validation content:
a profile, its features, the requirements those features reference, and the
validators (rules) that enforce them.

Two discovery surfaces are exposed:

* :class:`SimReadyPlugin` -- declared against the ``usd_validation_nvidia``
  entry-point group so the asset validator can auto-discover this tier's
  validators.
* :data:`tier` -- declared against the SimReady-owned ``simready.tier``
  entry-point group so the SimReady loader can discover this tier's per-layer
  content sources (requirements module + features/profiles dirs).

This package uses reusable tier scaffolding and derives its tier name/module
from its own package name. Each tier still configures tier-owned optional
content, such as its bundled Benchmark test package, in its descriptor.
"""

from ._plugin import SimReadyPlugin
from ._tier import tier

__all__ = ["SimReadyPlugin", "tier"]

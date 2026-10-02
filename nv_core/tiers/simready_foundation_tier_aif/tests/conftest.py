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
Session-wide pytest bootstrap for this tier's validator tests.

`conftest.py` is a special filename pytest auto-loads BEFORE collecting any
test_*.py module in this directory or below. We use that ordering to import
this tier's capabilities hub once at module level (below the imports).

Unlike the pre-Tiers framework, no separate loader call is needed: importing
`simready.foundation.tier_aif.capabilities` runs that module's own
`from .aif.connection_points import validation` (etc.) imports, which import
each domain's validation.py, whose @register_rule / @register_requirements
decorators register with usd_validation_nvidia's RequirementsRegistry at
class-definition time -- the same side effect
`_plugin.py:SimReadyPlugin.on_startup` triggers for a real validator run.
Verified live against usd_validation_nvidia 1.20.0: importing a tier's
capabilities module alone is sufficient to populate the registry; no
features/profiles registration is needed for these code-level rule tests.

This requires the tier to be installed as a built wheel (not run from source
checkout), because validation.py imports `simready.foundation.tier_aif.
requirements as cap`, a module that does not exist in the committed source
tree -- it is generated at build time from the capability markdown by
_tooling/build_hook.py and only exists once the wheel is built and installed.
"""
import simready.foundation.tier_aif.capabilities  # noqa: F401

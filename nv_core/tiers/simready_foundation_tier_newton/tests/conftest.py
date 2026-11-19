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

import sys
from importlib.util import find_spec
from pathlib import Path

_TIERS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_TIERS_ROOT / "_tooling"))
from source_tiers import select_source_tiers

select_source_tiers()
_SOURCE_TIERS = []
for _name in ("core", "newton"):
    _root = _TIERS_ROOT / ("simready_foundation_tier_" + _name)
    try:
        _spec = find_spec("simready.foundation.tier_" + _name)
    except ModuleNotFoundError:
        _spec = None
    if _spec is None:
        sys.path.insert(0, str(_root))
    _SOURCE_TIERS.append(_root)

sys.path.insert(0, str(_TIERS_ROOT / "_tooling"))
from checkout_requirements import ensure_checkout_requirements  # noqa: E402

for _root in _SOURCE_TIERS:
    ensure_checkout_requirements(_root)

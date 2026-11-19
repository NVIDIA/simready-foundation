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

"""Generate the requirement enums the validators import.

These tests import the validators straight out of the source tree, where the
generated ``requirements`` package does not exist until something generates it.
Against an installed tier wheel this does nothing.
"""

from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path

_TIER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_TIER_ROOT.parent / "_tooling"))
from source_tiers import select_source_tiers

select_source_tiers()

# repo_test.python_source_path scopes coverage; it does not add an import path.
# Keep installed-wheel qualification intact, but make filtered source tests
# independent of the nested runtime_tests conftest's collection order.
try:
    _TIER_SPEC = find_spec("simready.foundation.tier_core")
except ModuleNotFoundError:
    _TIER_SPEC = None
if _TIER_SPEC is None:
    sys.path.insert(0, str(_TIER_ROOT))

sys.path.insert(0, str(_TIER_ROOT.parent / "_tooling"))
from checkout_requirements import ensure_checkout_requirements  # noqa: E402

ensure_checkout_requirements(_TIER_ROOT)

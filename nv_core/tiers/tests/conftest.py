# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Regenerate the requirement enums of every tier checkout these tests import.

An editable install generates them into the checkout only once, at install time,
and any later wheel build removes them again.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TIERS_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(_TIERS_ROOT / "_tooling"))
from build_tiers import discover_tiers  # noqa: E402
from checkout_requirements import ensure_checkout_requirements  # noqa: E402

for _tier in discover_tiers(str(_TIERS_ROOT)):
    ensure_checkout_requirements(Path(_tier))

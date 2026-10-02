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
"""Make the tier-owned Benchmark package importable in source tests."""

import sys
from importlib.util import find_spec
from pathlib import Path

# The suite ships in the tier wheel, so only fall back to the source tree when
# no installed copy is importable. Prepending unconditionally also puts the
# sibling `simready/` source tree ahead of an installed tier, and that tree has
# no `requirements` module: it is generated into the wheel at build time.
if find_spec("simready_benchmark_kit_suite") is None:
    _TEST_PACKAGES_ROOT = Path(__file__).resolve().parents[2]
    if str(_TEST_PACKAGES_ROOT) not in sys.path:
        sys.path.insert(0, str(_TEST_PACKAGES_ROOT))

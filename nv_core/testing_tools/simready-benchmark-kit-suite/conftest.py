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
"""simready-benchmark-kit-suite workspace conftest.

Adds the package src/ to sys.path so utility tests under
packages/simready_benchmark_kit_suite/tests/unit/ can import the package as
`simready_benchmark_kit_suite.articulation_phases.*`.

The utility tests are pure-Python tests of utility code in
articulation_phases/ (joint utils, motion utils, IK solvers, etc.).
No Kit, no engine, no mocks required -- the only fixtures the tests
need are the standard pytest builtins (tmp_path, monkeypatch, ...).
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent
_SRC = _REPO_ROOT / "packages" / "simready_benchmark_kit_suite" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

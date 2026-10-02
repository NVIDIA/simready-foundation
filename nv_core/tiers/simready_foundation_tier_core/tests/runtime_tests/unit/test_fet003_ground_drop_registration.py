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
import ast
from pathlib import Path

_SOURCE = Path(__file__).parents[3] / "simready_benchmark_kit_suite" / "fet003_physics" / "ground_drop.py"


def _registration():
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != "test_ground_drop":
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == "test":
                return {keyword.arg: ast.literal_eval(keyword.value) for keyword in decorator.keywords}
    raise AssertionError("ground_drop @test registration not found")


def test_ground_drop_uses_solver_neutral_drop_height():
    registration = _registration()

    assert registration["version"] == "3.2.0"
    assert registration["max_duration"] == 300
    assert registration["config_defaults"]["drop_height_factor"] == 2.0
    assert registration["config_defaults"]["minimum_drop_distance"] == 0.1
    assert {feature["id"] for feature in registration["features"]} == {
        "FET_003_STANDARD",
        "FET_003_PHYSX",
        "FET_003_NEWTON",
    }

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import ast
from pathlib import Path


_SOURCE = (
    Path(__file__).parents[3]
    / "simready_benchmark_kit_suite"
    / "fet003_physics"
    / "ground_drop.py"
)


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

    assert registration["version"] == "3.1.0"
    assert registration["config_defaults"]["drop_height_factor"] == 2.0
    assert {feature["id"] for feature in registration["features"]} == {
        "FET_003_STANDARD",
        "FET_003_PHYSX",
        "FET_003_NEWTON",
    }

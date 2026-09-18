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
from types import SimpleNamespace

from simready_benchmark.core.feature_aggregator import aggregate_feature_pass
from simready_benchmark_kit_suite.fet028_gripper.gripper_close_lift import (
    _config_defaults_for_shape,
)

_SOURCE = Path(__file__).parents[3] / "simready_benchmark_kit_suite" / "fet028_gripper"


def _registration(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    registrations = []
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Name) or decorator.func.id != "test":
                continue
            registrations.append(
                {
                    keyword.arg: ast.literal_eval(keyword.value)
                    for keyword in decorator.keywords
                    if keyword.arg in {"features", "name", "version"}
                }
            )
    return registrations


def test_shape_tests_are_separate_isaac_registrations():
    sphere_path = _SOURCE / "gripper_close_lift_sphere.py"
    cube_path = _SOURCE / "gripper_close_lift_cube.py"

    assert _registration(sphere_path) == [
        {
            "features": [{"id": "FET_028_ISAAC", "version": ">=0.1.0"}],
            "name": "gripper_close_lift_sphere",
            "version": "1.4.0",
        }
    ]
    assert _registration(cube_path) == [
        {
            "features": [{"id": "FET_028_ISAAC", "version": ">=0.1.0"}],
            "name": "gripper_close_lift_cube",
            "version": "1.4.0",
        }
    ]
    assert _registration(_SOURCE / "gripper_close_lift.py") == []


def test_shape_payloads_are_reported_at_50_and_85_percent():
    sphere = _config_defaults_for_shape("sphere")
    cube = _config_defaults_for_shape("cube")

    assert sphere["shapes"] == ["sphere"]
    assert sphere["payload_mass_fraction"] == 0.5
    assert cube["shapes"] == ["cube"]
    assert cube["payload_mass_fraction"] == 0.85


def test_fet028_rollup_requires_both_shape_results_to_pass():
    tests = [
        SimpleNamespace(
            id=1,
            name="gripper_close_lift_sphere",
            test_file="sphere.py",
            provider="simready_benchmark_kit_suite",
            version="1.4.0",
            requirement=None,
        ),
        SimpleNamespace(
            id=2,
            name="gripper_close_lift_cube",
            test_file="cube.py",
            provider="simready_benchmark_kit_suite",
            version="1.4.0",
            requirement=None,
        ),
    ]
    plan = SimpleNamespace(
        tests=tests,
        features=[SimpleNamespace(name="FET_028_ISAAC", version="0.1.0", tests=[1, 2])],
    )

    one_failure = aggregate_feature_pass(
        plan,
        [
            {"test_name": "gripper_close_lift_sphere", "test_file": "sphere.py", "status": "pass"},
            {"test_name": "gripper_close_lift_cube", "test_file": "cube.py", "status": "fail"},
        ],
    )
    both_pass = aggregate_feature_pass(
        plan,
        [
            {"test_name": "gripper_close_lift_sphere", "test_file": "sphere.py", "status": "pass"},
            {"test_name": "gripper_close_lift_cube", "test_file": "cube.py", "status": "pass"},
        ],
    )

    assert one_failure["FET_028_ISAAC"].passed is False
    assert both_pass["FET_028_ISAAC"].passed is True

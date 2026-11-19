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
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from simready.evaluate.core.feature_aggregator import aggregate_feature_pass
from simready.foundation.tier_core.runtime_tests.fet028_gripper.gripper_close_lift import (
    _config_defaults_for_shape,
)

_SOURCE = Path(__file__).parents[3] / "simready/foundation/tier_core/runtime_tests" / "fet028_gripper"
# simready-evaluate releases before 2026.8.0 have no per-asset `asset=` filter.
_HAS_ASSET_AGGREGATION = "asset" in inspect.signature(aggregate_feature_pass).parameters


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
            "features": [{"id": "FET028_Gripper.Isaac.0-1-0", "version": "*"}],
            "name": "gripper_close_lift_sphere",
            "version": "1.4.9",
        }
    ]
    assert _registration(cube_path) == [
        {
            "features": [{"id": "FET028_Gripper.Isaac.0-1-0", "version": "*"}],
            "name": "gripper_close_lift_cube",
            "version": "1.4.9",
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


@pytest.mark.skipif(
    not _HAS_ASSET_AGGREGATION,
    reason="installed simready-evaluate lacks aggregate_feature_pass(asset=...)",
)
def test_fet028_rollup_requires_both_shape_results_to_pass():
    tests = [
        SimpleNamespace(
            id=1,
            name="gripper_close_lift_sphere",
            test_file="sphere.py",
            provider="simready.foundation.tier_core.runtime_tests",
            version="1.4.4",
            requirement=None,
        ),
        SimpleNamespace(
            id=2,
            name="gripper_close_lift_cube",
            test_file="cube.py",
            provider="simready.foundation.tier_core.runtime_tests",
            version="1.4.4",
            requirement=None,
        ),
    ]
    feature = SimpleNamespace(id=1, name="FET028_Gripper.Isaac.0-1-0", version="0.1.0", tests=[1, 2], runtime=None)
    asset = SimpleNamespace(id=1, path="gripper.usda", tests=[1, 2], profile_features=[])
    plan = SimpleNamespace(
        tests=tests,
        features=[feature],
        profiles=[],
        overrides=[],
        assets=[asset],
        engine_configs={},
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

    assert one_failure["FET028_Gripper.Isaac.0-1-0"].passed is False
    assert both_pass["FET028_Gripper.Isaac.0-1-0"].passed is True

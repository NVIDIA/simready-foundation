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
import re
from pathlib import Path

import pytest

TIERS = Path(__file__).resolve().parents[2]
PACKAGES = {"core": "simready.foundation.tier_core.runtime_tests", "newton": "simready.foundation.tier_newton.runtime_tests"}
MOTION_BUDGETS = {
    "ground_drop": 600,
    "ground_stability": 600,
    "slope_drop": 600,
    "joint_movement": 600,
    "grasp_and_lift": 1200,
    "drive_gain_validation": 600,
    "effort_limit": 1200,
    "full_range_sweep": 14400,
    "ik_target_reach": 1200,
    "jacobian_ik": 2400,
    "mimic_joint": 600,
    "multi_joint_coordination": 3600,
    "state_accuracy": 600,
    "velocity_limit": 600,
    "gripper_close_lift_cube": 600,
    "gripper_close_lift_sphere": 600,
}
FAMILIES = {"fet003_physics", "fet004_multibody", "fet005_grasp", "fet022_driven_joints", "fet028_gripper"}


def _suite(tier):
    return TIERS / ("simready_foundation_tier_" + tier) / Path(*PACKAGES[tier].split("."))


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _value(node, tree, suite):
    if isinstance(node, ast.Constant):
        return node.value
    assert isinstance(node, ast.Name)
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == node.id for target in statement.targets
        ):
            return _value(statement.value, tree, suite)
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if (alias.asname or alias.name) == node.id:
                    components = statement.module.split(".")
                    prefix = ["simready", "foundation", suite.parent.name, "runtime_tests"]
                    assert components[:4] == prefix
                    imported = _tree(suite.joinpath(*components[4:]).with_suffix(".py"))
                    return _value(ast.Name(id=alias.name), imported, suite)
    raise AssertionError("Unresolved budget constant: " + node.id)


def _registrations(tier):
    suite = _suite(tier)
    result = {}
    for folder in sorted(FAMILIES):
        for path in sorted((suite / folder).glob("*.py")):
            tree = _tree(path)
            dictionaries = {
                target.id: statement.value
                for statement in tree.body
                if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Dict)
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "test":
                    continue
                metadata = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None}
                for keyword in node.keywords:
                    if keyword.arg is None:
                        values = dictionaries[keyword.value.id]
                        metadata.update(
                            {key.value: value for key, value in zip(values.keys, values.values, strict=True)}
                        )
                name = _value(metadata["name"], tree, suite)
                result[name] = {key: _value(metadata[key], tree, suite) for key in ("version", "max_duration")}
    return result


def _default(tier, phase, key):
    tree = _tree(_suite(tier) / "articulation_phases" / (phase + ".py"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_defaults")
    value = next(node.value for node in function.body if isinstance(node, ast.Return))
    return ast.literal_eval(
        next(item for name, item in zip(value.keys, value.values, strict=True) if name.value == key)
    )


@pytest.mark.parametrize("tier", PACKAGES)
def test_all_motion_registrations_have_doubled_wall_allowances(tier):
    expected = MOTION_BUDGETS
    if tier == "newton":
        expected = {
            name + "_newton": seconds
            for name, seconds in expected.items()
            if name not in ("grasp_and_lift", "gripper_close_lift_cube", "gripper_close_lift_sphere")
        }
    actual = _registrations(tier)
    assert {name: metadata["max_duration"] for name, metadata in actual.items()} == expected


@pytest.mark.parametrize("tier", PACKAGES)
def test_internal_wall_defaults_double_without_expanding_nominal_motion(tier):
    assert _default(tier, "full_range_sweep", "max_sweep_wall_seconds") == 3360
    assert _default(tier, "full_range_sweep", "max_sweep_segment_seconds") == 60
    assert _default(tier, "full_range_sweep", "max_sweep_simulation_seconds") == 600
    assert _default(tier, "multi_joint_coordination", "max_coordination_wall_seconds") == 3360
    assert _default(tier, "multi_joint_coordination", "max_coordination_ramp_seconds") == 60
    assert _default(tier, "multi_joint_coordination", "max_coordination_simulation_seconds") == 600
    assert _default(tier, "jacobian_ik", "max_search_wall_seconds") == 1800
    assert _default(tier, "jacobian_ik", "max_solver_iterations") == 150
    assert _default(tier, "drive_gain_validation", "test_duration_seconds") == 5
    assert _default(tier, "drive_gain_validation", "physics_fps") == 240
    assert _default(tier, "state_accuracy", "test_duration_seconds") == 3
    assert _default(tier, "state_accuracy", "position_tolerance_deg") == 5


@pytest.mark.parametrize("tier", PACKAGES)
def test_published_procedure_metadata_documents_current_timeouts(tier):
    docs = _suite(tier) / "docs"
    landing = (docs / ("tests.md" if tier == "core" else "runtime-tests.md")).read_text(encoding="utf-8")
    for name, metadata in _registrations(tier).items():
        assert f"| `{name}` | {metadata['max_duration']} |" in landing
        if tier == "newton":
            assert f"| `{name}` | `{metadata['version']}` |" in landing
        else:
            pages = [path.read_text(encoding="utf-8") for path in docs.rglob("*.md")]
            matching = [
                text for text in pages if re.search(r"^\| Test name\s*\|\s*" + re.escape(name) + r"\s*\|", text, re.M)
            ]
            assert len(matching) == 1, name
            assert re.search(r"^\| Test version\s*\|\s*" + re.escape(metadata["version"]) + r"\s*\|", matching[0], re.M)
            assert f"| Wall-clock timeout | {metadata['max_duration']} seconds |" in matching[0]

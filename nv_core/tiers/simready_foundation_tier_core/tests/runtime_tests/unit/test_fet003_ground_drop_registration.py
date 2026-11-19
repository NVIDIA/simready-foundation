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

_SOURCE = Path(__file__).parents[3] / "simready/foundation/tier_core/runtime_tests" / "fet003_physics" / "ground_drop.py"


def _static_dict(node):
    """Return the statically-resolvable entries of a ``{...}`` or ``dict(...)`` node.

    Non-literal entries (for example ``config_defaults=phase.get_defaults()``)
    are skipped rather than rejecting the whole dict, so literal metadata such
    as ``version`` and ``config_defaults`` still resolves for the ``**KWARGS`` spread.
    """
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                continue
            try:
                result[ast.literal_eval(key)] = ast.literal_eval(value)
            except Exception:
                continue
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
        result = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            try:
                result[keyword.arg] = ast.literal_eval(keyword.value)
            except Exception:
                continue
        return result
    return None


def _module_dict_constants(tree):
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = _static_dict(node.value)
        if value is not None:
            constants[target.id] = value
    return constants


def _test_registration(call, tree):
    """Effective @test(...) keyword args, expanding a module-level ``**KWARGS`` dict."""
    constants = _module_dict_constants(tree)
    kwargs = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            if isinstance(keyword.value, ast.Name):
                kwargs.update(constants.get(keyword.value.id, {}))
            continue
        try:
            kwargs[keyword.arg] = ast.literal_eval(keyword.value)
        except Exception:
            continue
    return kwargs


def _registration():
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != "test_ground_drop":
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == "test":
                return _test_registration(decorator, tree)
    raise AssertionError("ground_drop @test registration not found")


def test_ground_drop_uses_solver_neutral_drop_height():
    registration = _registration()

    assert registration["version"] == "4.0.2"
    assert registration["max_duration"] == 600
    assert registration["config_defaults"]["drop_height_factor"] == 2.0
    assert registration["config_defaults"]["minimum_drop_distance"] == 0.1
    # The Newton copy of this test lives in the tier_newton benchmark suite
    # (simready.foundation.tier_newton.runtime_tests); the Core registration keeps only the
    # engine-neutral Standard + PhysX features.
    assert {feature["id"] for feature in registration["features"]} == {
        "FET003_RigidBody.0-1-0",
        "FET003_RigidBody.0-2-0",
        "FET003_RigidBody.PhysX.0-1-0",
        "FET003_RigidBody.PhysX.0-2-0",
        "FET003_RigidBody.PhysX.0-3-0",
        "FET003_RigidBody.PhysX.0-4-0",
    }

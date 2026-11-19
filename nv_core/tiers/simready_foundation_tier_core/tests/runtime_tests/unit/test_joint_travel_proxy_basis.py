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

import pytest


@pytest.mark.parametrize(
    "owner,suite", [("core", "simready.foundation.tier_core.runtime_tests"), ("newton", "simready.foundation.tier_newton.runtime_tests")]
)
@pytest.mark.parametrize(
    "joint_type,travel,rotation,translation,expected",
    [
        ("PhysicsRevoluteJoint", 180.0, 45.0, 0.0, 25.0),
        ("PhysicsRevoluteJoint", 180.0, 360.0, 0.0, 100.0),
        ("PhysicsPrismaticJoint", 1.0, 0.0, 0.2534, 25.3),
        ("PhysicsPrismaticJoint", 1.0, 0.0, 0.0, 0.0),
        ("PhysicsRevoluteJoint", 0.0, 45.0, 0.0, None),
    ],
)
@pytest.mark.parametrize("moved", [False, True])
@pytest.mark.parametrize("initial_coordinate", [0.0, 1.0])
def test_actual_legacy_ratio_preserves_value_and_verdict_with_explicit_proxy_basis(
    owner, suite, joint_type, travel, rotation, translation, expected, moved, initial_coordinate
):
    tiers = Path(__file__).resolve().parents[4]
    source = tiers / ("simready_foundation_tier_" + owner) / Path(*suite.split(".")) / "fet004_multibody" / "joint_movement.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    run = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_joint_movement"
    )
    drive = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_drive_dof_for_joint"
    )
    # Isolate the actual metric-commit loop, not a rewritten test implementation.
    loops = [
        node
        for node in run.body
        if isinstance(node, ast.For)
        and any(isinstance(item, ast.Constant) and item.value == "jm_joint_%s_pct_of_travel" for item in ast.walk(node))
    ]
    assert len(loops) == 1
    metrics = {}
    measurement = {"rotation_deg": rotation, "translation_m": translation, "moved": moved}
    joint = {
        "name": "joint",
        "type_name": joint_type,
        "_open_travel": travel,
        "initial_coordinate": initial_coordinate,
    }
    movement_flags = {"joint": False}
    namespace = {
        "ctx": SimpleNamespace(add_metric=lambda name, value: metrics.__setitem__(name, value)),
        "joints": [joint],
        "acc": {"joint": measurement},
        "joint_moved": movement_flags,
        "sanitize_metric_name": lambda name: name,
        "_publish_joint_measurements": lambda *_: None,
    }
    block = ast.Module(body=[drive, loops[0]], type_ignores=[])
    exec(compile(block, str(source), "exec"), namespace)
    assert measurement["moved"] is moved
    assert movement_flags["joint"] is moved
    if expected is None:
        assert metrics == {}
        assert "pct_of_travel" not in measurement
    else:
        assert metrics["jm_joint_joint_pct_of_travel"] == measurement["pct_of_travel"] == expected
        basis = "capped_relative_body_motion_over_authored_endpoint_magnitude"
        assert metrics["jm_joint_joint_pct_of_travel_basis"] == measurement["pct_of_travel_basis"] == basis

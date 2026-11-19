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

"""Core physics procedures reject wrong-engine routing before touching assets."""

import ast
import sys
import types
from pathlib import Path

import pytest
from simready.foundation.tier_core.runtime_tests.engine_guard import (
    PhysicsTestEngineMismatchError,
    require_physx_test_engine,
)


def _set_active_engine(monkeypatch, engine):
    physics_utils = types.ModuleType("simready.evaluate_engine_kit.physics_utils")
    physics_utils.active_physics_engine = lambda: engine
    monkeypatch.setitem(sys.modules, physics_utils.__name__, physics_utils)


def test_core_physics_guard_accepts_physx(monkeypatch):
    _set_active_engine(monkeypatch, "physx")

    require_physx_test_engine()


@pytest.mark.parametrize("engine", ["newton", "mujoco", "unknown"])
def test_core_physics_guard_reports_setup_error_not_asset_failure(monkeypatch, engine):
    _set_active_engine(monkeypatch, engine)

    with pytest.raises(PhysicsTestEngineMismatchError) as error:
        require_physx_test_engine()

    assert "setup mismatch" in str(error.value)
    assert "asset was not evaluated" in str(error.value)
    assert engine in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("relative_path", "function_name"),
    [
        ("fet003_physics/ground_drop.py", "run_ground_drop"),
        ("fet003_physics/slope_drop.py", "run_slope_drop"),
        ("fet003_physics/ground_stability.py", "run_ground_stability"),
        ("fet004_multibody/joint_movement.py", "run_joint_movement"),
        ("fet022_driven_joints/drive_gain_validation.py", "run_drive_gain_validation"),
        ("fet022_driven_joints/effort_limit.py", "run_effort_limit"),
        ("fet022_driven_joints/full_range_sweep.py", "run_full_range_sweep"),
        ("fet022_driven_joints/ik_target_reach.py", "run_ik_target_reach"),
        ("fet022_driven_joints/jacobian_ik.py", "run_jacobian_ik"),
        ("fet022_driven_joints/mimic_joint.py", "run_mimic_joint"),
        ("fet022_driven_joints/multi_joint_coordination.py", "run_multi_joint_coordination"),
        ("fet022_driven_joints/state_accuracy.py", "run_state_accuracy"),
        ("fet022_driven_joints/velocity_limit.py", "run_velocity_limit"),
    ],
)
async def test_core_physics_procedures_reject_newton_before_context_access(monkeypatch, relative_path, function_name):
    _set_active_engine(monkeypatch, "newton")
    suite_root = Path(__file__).resolve().parents[3] / "simready/foundation/tier_core/runtime_tests"
    source = suite_root / relative_path
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name)
    # Compile the production body without importing its Kit-dependent module.
    # The wrong-engine path must terminate before any of those APIs are needed.
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)

    class UntouchedContext:
        def __getattribute__(self, name):
            raise AssertionError("A misrouted procedure accessed context: " + name)

    with pytest.raises(PhysicsTestEngineMismatchError, match="setup mismatch"):
        await namespace[function_name](UntouchedContext())

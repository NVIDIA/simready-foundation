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
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SUITE = Path(__file__).resolve().parents[1] / "simready/foundation/tier_newton/runtime_tests"
TEST_NAMES = (
    "ground_drop",
    "ground_stability",
    "slope_drop",
    "joint_movement",
    "drive_gain_validation",
    "effort_limit",
    "full_range_sweep",
    "ik_target_reach",
    "jacobian_ik",
    "mimic_joint",
    "multi_joint_coordination",
    "state_accuracy",
    "velocity_limit",
)


def _module_path(name):
    relative = name.removeprefix("simready.foundation.tier_newton.runtime_tests").lstrip(".")
    path = SUITE.joinpath(*relative.split(".")) if relative else SUITE
    return path.with_suffix(".py"), path / "__init__.py"


def test_newton_suite_has_complete_import_closure_and_no_core_behavior_imports():
    violations = []
    for source in SUITE.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                if module.startswith("simready.foundation.tier_core"):
                    violations.append((str(source.relative_to(SUITE)), node.lineno, module))
                if module.startswith("omni.physx") or module.startswith("isaacsim.core.api"):
                    violations.append((str(source.relative_to(SUITE)), node.lineno, module))
                if module.startswith("simready.foundation.tier_newton.runtime_tests"):
                    assert any(path.is_file() for path in _module_path(module)), (source, node.lineno, module)
                    # from <package> import <submodule> must also resolve. Other
                    # imports bind symbols owned by the resolved module itself.
                    if isinstance(node, ast.ImportFrom) and _module_path(module)[1].is_file():
                        package_tree = ast.parse(_module_path(module)[1].read_text(encoding="utf-8"))
                        defined = {getattr(item, "name", None) for item in package_tree.body}
                        for alias in node.names:
                            if alias.name not in defined and alias.name != "*":
                                child = module + "." + alias.name
                                assert any(path.is_file() for path in _module_path(child)), (source, child)
    assert not violations, violations


@pytest.mark.parametrize("name", TEST_NAMES)
def test_newton_registration_keeps_canonical_identity_and_local_verdict(name):
    files = list(SUITE.glob("fet*/" + name + ".py"))
    assert len(files) == 1, files
    tree = ast.parse(files[0].read_text(encoding="utf-8"))
    tests = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.decorator_list]
    assert len(tests) == 1
    decorator = tests[0].decorator_list[0]
    args = {kw.arg: kw.value for kw in decorator.keywords if kw.arg is not None}
    assert ast.literal_eval(args["name"]) == name + "_newton"
    identities = ast.literal_eval(args["features"])
    assert all(".Newton." in item["id"] or ".RobotNewton." in item["id"] for item in identities)
    assert any(isinstance(node, ast.AsyncFunctionDef) and node.name == "run_" + name for node in tree.body)
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "require_newton_backend"
        for node in ast.walk(tests[0])
    )
    if name == "ground_stability":
        metadata = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "GROUND_STABILITY_KWARGS" for target in node.targets)
        )
        if isinstance(metadata, ast.Dict):
            enabled = next(
                value
                for key, value in zip(metadata.keys, metadata.values, strict=True)
                if ast.literal_eval(key) == "enabled"
            )
        else:
            assert isinstance(metadata, ast.Call) and isinstance(metadata.func, ast.Name)
            assert metadata.func.id == "dict"
            enabled = next(kw.value for kw in metadata.keywords if kw.arg == "enabled")
        assert ast.literal_eval(enabled) is True


def test_newton_backend_rejects_wrong_setup_without_asset_diagnosis(monkeypatch):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    monkeypatch.setitem(
        sys.modules,
        "simready.evaluate_engine_kit.physics_utils",
        SimpleNamespace(active_physics_engine=lambda: "newton"),
    )
    require_newton_backend()
    monkeypatch.setitem(
        sys.modules,
        "simready.evaluate_engine_kit.physics_utils",
        SimpleNamespace(active_physics_engine=lambda: "physx"),
    )
    with pytest.raises(RuntimeError, match="test setup mismatch, not an asset diagnosis"):
        require_newton_backend()


def test_newton_handle_never_constructs_or_resets_a_physx_world():
    tree = ast.parse((SUITE / "articulation_phases/robot_handle.py").read_text(encoding="utf-8"))
    handle = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "RobotHandle")
    methods = {node.name for node in handle.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "initialize_newton" in methods
    assert "initialize" not in methods
    assert "reinitialize_articulation" not in methods
    assert not any(isinstance(node, ast.Attribute) and node.attr == "_world" for node in ast.walk(handle))


def test_no_newton_gripper_contract_or_gantry_was_claimed():
    assert not list(SUITE.glob("fet028*"))
    assert not list(SUITE.rglob("gripper_close_lift*.py"))
    assert not list(SUITE.rglob("gripper_carrier.py"))


def test_direct_mjc_actuator_joint_target_is_not_silently_discarded():
    from pxr import Sdf, Usd, UsdPhysics
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.passive_joints import (
        _actuator_target_paths,
    )

    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/Robot", "Xform")
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/hinge")
    actuator = stage.DefinePrim("/Robot/actuator", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets([Sdf.Path(joint.GetPath())])
    assert str(joint.GetPath()) in _actuator_target_paths(stage, "/Robot")

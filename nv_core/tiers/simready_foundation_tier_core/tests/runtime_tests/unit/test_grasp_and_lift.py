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
import builtins
import importlib
import sys
import types

import pytest


def _import_grasp_and_lift(monkeypatch):
    decorator_module = types.ModuleType("simready_benchmark.core.decorator")
    decorator_module.test = lambda **_kwargs: lambda function: function
    monkeypatch.setitem(sys.modules, "simready_benchmark.core.decorator", decorator_module)
    return importlib.import_module("simready_benchmark_kit_suite.fet005_grasp.grasp_and_lift")


@pytest.mark.parametrize(
    ("runtime", "feature"),
    [
        ("PhysX", "FET_003_PHYSX"),
        (" newton ", "FET_003_NEWTON"),
        ("MUJOCO", "FET_003_MUJOCO"),
    ],
)
def test_runtime_dependency_uses_exact_fet003_variant(monkeypatch, runtime, feature):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)

    assert grasp_and_lift._required_physics_feature(runtime) == feature


def test_fixture_setup_failure_does_not_recommend_mass_or_friction(monkeypatch):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)

    message = grasp_and_lift._all_identifiers_failed_message(
        1,
        [
            (
                "/Asset/Grasp/grasp_identifier",
                "FixtureSetup",
                "Gripper rebuild failed: grasp body has no default-purpose geometry",
            )
        ],
    )

    assert "before grasp behavior was evaluated" in message
    assert "grasp annotation scope is valid" in message
    assert "physxRigidBody:mass" not in message
    assert "dynamicFriction" not in message


def test_behavior_failure_keeps_physics_remediation(monkeypatch):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)

    message = grasp_and_lift._all_identifiers_failed_message(
        1,
        [("/Asset/grasp_identifier", "Grasping", "pads touched (no object)")],
    )

    assert "physxRigidBody:mass" in message
    assert "dynamicFriction" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime", ["", "typo", "future_engine"])
async def test_unknown_runtime_skips_instead_of_using_standard_dependency(monkeypatch, runtime):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)
    monkeypatch.setenv("SIMREADY_PHYSICS_RUNTIME", runtime)

    class Context:
        asset_validated_features = {"FET_003_STANDARD"}

        def __init__(self):
            self.skip_message = None

        def skip(self, message):
            self.skip_message = message

    ctx = Context()

    await grasp_and_lift.test_grasp_and_lift(ctx)

    assert "Unsupported SIMREADY_PHYSICS_RUNTIME" in ctx.skip_message
    assert repr(runtime) in ctx.skip_message


@pytest.mark.asyncio
async def test_cook_skip_returns_precheck_signal_instead_of_none(monkeypatch):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)

    class Room:
        def auto_size(self, _asset):
            pass

        def set_color(self, *_rgb):
            pass

        def show_ground(self):
            pass

    class Physics:
        def __init__(self):
            self.stop_count = 0

        def stop(self):
            self.stop_count += 1

        def play(self):
            raise AssertionError("physics must not start after a cook failure")

    class Scene:
        def __init__(self):
            self.asset = object()
            self.lighting = types.SimpleNamespace(add_dome=lambda **_kwargs: None)
            self.physics = Physics()

        def add_room(self):
            return Room()

        def add_physics(self, **_kwargs):
            return self.physics

        def setup_camera_follow(self):
            pass

        async def prepare_physics(self):
            return "SKIP: collider cook timed out"

    class Context:
        def __init__(self):
            self.scene = Scene()

        async def settle(self, **_kwargs):
            pass

        def log(self, _message):
            pass

    class GraspScene:
        def __init__(self, *_args):
            pass

        def init_tracking(self):
            pass

    omni = types.ModuleType("omni")
    omni_usd = types.ModuleType("omni.usd")
    omni_usd.get_context = lambda: types.SimpleNamespace(get_stage=lambda: object())
    omni.usd = omni_usd

    stage_module = types.ModuleType("isaacsim.core.utils.stage")

    async def update_stage_async():
        pass

    stage_module.update_stage_async = update_stage_async

    physics_utils = types.ModuleType("simready_benchmark_engine_kit.physics_utils")
    physics_utils.active_physics_engine = lambda: "physx"
    physics_utils.configure_physx_determinism = lambda *_args: None
    physics_utils.cook_skip_message = lambda status: status

    grasp_scene_module = types.ModuleType("simready_benchmark_kit_suite.fet005_grasp.grasp_scene")
    grasp_scene_module.GraspScene = GraspScene

    articulation_module = types.ModuleType("simready_benchmark_kit_suite.fet005_grasp.newton_articulation")
    articulation_module.apply_temporary_newton_articulations = lambda *_args: []
    articulation_module.remove_temporary_newton_articulations = lambda *_args: None

    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", omni_usd)
    monkeypatch.setitem(sys.modules, "isaacsim.core.utils.stage", stage_module)
    monkeypatch.setitem(sys.modules, "simready_benchmark_engine_kit.physics_utils", physics_utils)
    monkeypatch.setitem(
        sys.modules,
        "simready_benchmark_kit_suite.fet005_grasp.grasp_scene",
        grasp_scene_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "simready_benchmark_kit_suite.fet005_grasp.newton_articulation",
        articulation_module,
    )
    monkeypatch.setattr(grasp_and_lift, "_place_asset_on_ground", lambda *_args, **_kwargs: None)

    ctx = Context()
    result = await grasp_and_lift._test_one_identifier(
        ctx,
        {"physics_fps": 240},
        "/Asset/grasp_identifier",
        "grasp_identifier",
        "/Asset",
    )

    assert result == {"precheck": "collider cook timed out"}
    assert ctx.scene.physics.stop_count == 1


@pytest.mark.asyncio
async def test_import_error_escapes_per_identifier_asset_failure(monkeypatch):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)

    class Context:
        asset_validated_features = None
        asset_path = "asset.usd"
        config = {"settle_frames": 1, "asset_load_timeout": 1}

        def __init__(self):
            self.scene = types.SimpleNamespace(
                asset=types.SimpleNamespace(prim_path="/Asset"),
                load_asset=lambda *_args, **_kwargs: None,
            )

        def step(self, _message):
            pass

        def set_settle_frames(self, _count):
            pass

    grasp_checks = types.ModuleType("simready_benchmark_kit_suite.fet005_grasp.grasp_checks")
    grasp_checks.run_pre_checks = lambda *_args: (None, ["/Asset/grasp_identifier"])
    monkeypatch.setitem(
        sys.modules,
        "simready_benchmark_kit_suite.fet005_grasp.grasp_checks",
        grasp_checks,
    )

    async def raise_import_error(*_args):
        raise ImportError("broken Isaac dependency")

    monkeypatch.setattr(grasp_and_lift, "_test_one_identifier", raise_import_error)
    omni_usd = sys.modules.get("omni.usd") or types.ModuleType("omni.usd")
    omni_usd.get_context = lambda: types.SimpleNamespace(get_stage=lambda: object())
    omni = sys.modules.get("omni") or types.ModuleType("omni")
    omni.usd = omni_usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", omni_usd)

    with pytest.raises(ImportError, match="broken Isaac dependency"):
        await grasp_and_lift.test_grasp_and_lift(Context())


@pytest.mark.asyncio
async def test_binary_import_value_error_becomes_runtime_dependency_error(monkeypatch):
    grasp_and_lift = _import_grasp_and_lift(monkeypatch)
    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "omni.usd":
            raise ValueError("Cython size changed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)

    with pytest.raises(
        ImportError,
        match=r"FET_005 runtime dependency import failed \(ValueError\): Cython size changed",
    ):
        await grasp_and_lift._test_one_identifier(
            object(),
            {},
            "/Asset/grasp_identifier",
            "grasp_identifier",
            "/Asset",
        )

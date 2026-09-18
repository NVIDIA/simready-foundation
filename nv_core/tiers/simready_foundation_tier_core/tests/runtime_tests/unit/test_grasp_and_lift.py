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

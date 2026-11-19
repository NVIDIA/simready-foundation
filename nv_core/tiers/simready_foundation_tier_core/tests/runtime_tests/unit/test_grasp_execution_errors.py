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
import asyncio
import importlib
import sys
import types

import pytest


@pytest.fixture
def grasp_module(monkeypatch):
    decorator = types.ModuleType("simready.evaluate.core.decorator")
    decorator.test = lambda **_kwargs: lambda function: function
    monkeypatch.setitem(sys.modules, "simready.evaluate.core.decorator", decorator)
    return importlib.import_module("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_and_lift")


def _execution_context(monkeypatch, identifiers):
    checks = types.ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_checks")
    checks.run_pre_checks = lambda *_args: (None, identifiers)
    monkeypatch.setitem(sys.modules, checks.__name__, checks)
    omni = types.ModuleType("omni")
    omni.__path__ = []
    usd = types.ModuleType("omni.usd")
    usd.get_context = lambda: types.SimpleNamespace(get_stage=lambda: object())
    omni.usd = usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    monkeypatch.setenv("SIMREADY_PHYSICS_RUNTIME", "PhysX")

    class Context:
        asset_validated_features = None
        asset_path = "asset.usd"
        config = {"settle_frames": 1, "asset_load_timeout": 1}

        def __init__(self):
            self.scene = types.SimpleNamespace(
                asset=types.SimpleNamespace(prim_path="/Asset"),
                load_asset=lambda *_args, **_kwargs: None,
                clear=lambda: None,
            )
            self.metrics = {}
            self.failures = []
            self.warnings = []

        def step(self, _message):
            pass

        def set_settle_frames(self, _count):
            pass

        def add_metric(self, name, value):
            self.metrics[name] = value

        def log(self, _message):
            pass

        def fail(self, message):
            self.failures.append(message)

        def warn(self, message):
            self.warnings.append(message)

    return Context()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [RuntimeError("Required pose missing"), ValueError("Invalid command"), asyncio.CancelledError()]
)
@pytest.mark.parametrize(
    "prior_result", [None, {"failed": False}, {"failed": True, "phase_name": "Lifting", "message": "No lift"}]
)
async def test_unexpected_identifier_error_is_never_an_asset_verdict(grasp_module, monkeypatch, error, prior_result):
    identifiers = ["/Asset/grasp_identifier_1", "/Asset/grasp_identifier_2"]
    ctx = _execution_context(monkeypatch, identifiers)
    calls = []

    async def run(*_args):
        calls.append(True)
        if prior_result is not None and len(calls) == 1:
            return prior_result
        raise error

    monkeypatch.setattr(grasp_module, "_test_one_identifier", run)
    with pytest.raises(type(error)) as captured:
        await grasp_module.test_grasp_and_lift(ctx)
    assert captured.value is error
    assert ctx.failures == []
    assert "grasp_passed" not in ctx.metrics
    assert "grasp_failed" not in ctx.metrics
    assert len(calls) == (1 if prior_result is None else 2)


@pytest.mark.asyncio
async def test_measured_identifier_results_keep_any_pass_criterion(grasp_module, monkeypatch):
    ctx = _execution_context(monkeypatch, ["/Asset/grasp_identifier_1", "/Asset/grasp_identifier_2"])
    outcomes = iter([{"failed": True, "phase_name": "Lifting", "message": "No lift"}, {"failed": False}])

    async def run(*_args):
        return next(outcomes)

    monkeypatch.setattr(grasp_module, "_test_one_identifier", run)
    await grasp_module.test_grasp_and_lift(ctx)
    assert ctx.failures == []
    assert ctx.metrics["grasp_passed"] == 1
    assert ctx.metrics["grasp_failed"] == 1
    assert len(ctx.warnings) == 1


def _cleanup_fixture(
    stop_error=None, robot_error=None, restore_error=None, update_error=None, health_error=None, robot_result=None
):
    events = []

    def stop():
        events.append("stop")
        if stop_error is not None:
            raise stop_error

    def teardown():
        events.append("teardown")
        if robot_error is not None:
            raise robot_error
        return robot_result

    def restore(*_args):
        events.append("restore")
        if restore_error is not None:
            raise restore_error

    async def update():
        events.append("update")
        if update_error is not None:
            raise update_error

    def record(reason):
        events.append(reason)
        if health_error is not None:
            raise health_error

    ctx = types.SimpleNamespace(_engine_session=types.SimpleNamespace(record_required_cleanup_failure=record))
    return events, (
        ctx,
        types.SimpleNamespace(stop=stop),
        types.SimpleNamespace(teardown=teardown),
        types.SimpleNamespace(GetPrimAtPath=lambda _path: types.SimpleNamespace(IsValid=lambda: False)),
        [object()],
        restore,
        update,
    )


@pytest.mark.asyncio
async def test_cleanup_stops_physics_before_controller_and_schema_restoration(grasp_module):
    events, args = _cleanup_fixture()
    await grasp_module._cleanup_identifier_scene(*args)
    assert events == ["stop", "teardown", "restore", "update"]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [RuntimeError("stop failed"), asyncio.CancelledError(), KeyboardInterrupt()])
async def test_failed_stop_withholds_native_and_topology_cleanup(grasp_module, error):
    events, args = _cleanup_fixture(stop_error=error)
    with pytest.raises(type(error)) as captured:
        await grasp_module._cleanup_identifier_scene(*args)
    assert captured.value is error
    assert events == ["stop", "Required FET005 physics stop failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [RuntimeError("stop failed"), asyncio.CancelledError()])
async def test_stop_failure_does_not_replace_original_error_or_cancellation(grasp_module, error):
    primary = RuntimeError("Original readback failure")
    events, args = _cleanup_fixture(stop_error=error, health_error=RuntimeError("Health sink failed"))
    await grasp_module._cleanup_identifier_scene(*args, original_error=primary)
    assert events == ["stop", "Required FET005 physics stop failed."]
    assert any("physics stop" in note for note in primary.__notes__)
    assert any("health reporting" in note for note in primary.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["robot_error", "restore_error", "update_error"])
@pytest.mark.parametrize("has_primary", [False, True])
async def test_cleanup_preserves_first_cause_and_latches_failed_required_operation(grasp_module, field, has_primary):
    error = RuntimeError("Required cleanup failed")
    primary = asyncio.CancelledError() if has_primary else None
    events, args = _cleanup_fixture(**{field: error})
    if has_primary:
        await grasp_module._cleanup_identifier_scene(*args, original_error=primary)
        assert primary.__notes__
    else:
        with pytest.raises(RuntimeError) as captured:
            await grasp_module._cleanup_identifier_scene(*args)
        assert captured.value is error
    assert events[0] == "stop"
    assert ("restore" in events) is (field != "robot_error")
    if field == "robot_error":
        assert "update" not in events
    assert any(event.startswith("Required FET005") for event in events)


@pytest.mark.asyncio
async def test_explicit_false_stop_is_not_a_successful_barrier(grasp_module):
    events, args = _cleanup_fixture()
    args = (*args[:1], types.SimpleNamespace(stop=lambda: False), *args[2:])
    with pytest.raises(RuntimeError, match="stop was rejected"):
        await grasp_module._cleanup_identifier_scene(*args)
    assert events == ["Required FET005 physics stop failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize("primary", [RuntimeError("Original setup error"), asyncio.CancelledError()])
@pytest.mark.parametrize("stop_fails", [False, True])
async def test_real_identifier_finally_preserves_setup_cause_and_stop_barrier(
    grasp_module, monkeypatch, primary, stop_fails
):
    events, cleanup_args = _cleanup_fixture(stop_error=RuntimeError("stop failed") if stop_fails else None)
    ctx, physics, robot, stage, mutations, restore, update = cleanup_args
    room = types.SimpleNamespace(auto_size=lambda *_args: None, set_color=lambda *_args: None, show_ground=lambda: None)
    ctx.scene = types.SimpleNamespace(
        asset=object(),
        add_room=lambda: room,
        lighting=types.SimpleNamespace(add_dome=lambda **_kwargs: None),
        add_physics=lambda **_kwargs: physics,
    )
    ctx.scene.clear = lambda: events.append("clear")

    class GraspScene:
        def __init__(self, *_args):
            self.robot = robot

        def init_tracking(self):
            raise primary

    omni = types.ModuleType("omni")
    omni.__path__ = []
    usd = types.ModuleType("omni.usd")
    usd.get_context = lambda: types.SimpleNamespace(get_stage=lambda: stage)
    omni.usd = usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    stage_module = types.ModuleType("isaacsim.core.utils.stage")
    stage_module.update_stage_async = update
    monkeypatch.setitem(sys.modules, stage_module.__name__, stage_module)
    physics_module = types.ModuleType("simready.evaluate_engine_kit.physics_utils")
    physics_module.active_physics_engine = lambda: "newton"
    physics_module.configure_physx_determinism = lambda *_args: None
    monkeypatch.setitem(sys.modules, physics_module.__name__, physics_module)
    scene_module = types.ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_scene")
    scene_module.GraspScene = GraspScene
    monkeypatch.setitem(sys.modules, scene_module.__name__, scene_module)
    articulation_module = types.ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.newton_articulation")
    articulation_module.apply_temporary_newton_articulations = lambda *_args: mutations
    articulation_module.remove_temporary_newton_articulations = restore
    monkeypatch.setitem(sys.modules, articulation_module.__name__, articulation_module)
    monkeypatch.setattr(grasp_module, "_place_asset_on_ground", lambda *_args, **_kwargs: None)
    ctx.log = lambda _message: None
    # The setup log uses each mutation's real public field before tracking.
    mutations[:] = [types.SimpleNamespace(path="/Asset/Body")]

    with pytest.raises(type(primary)) as captured:
        await grasp_module._test_one_identifier(ctx, {"physics_fps": 240}, "/Asset/grasp_identifier", "grasp", "/Asset")
    assert captured.value is primary
    if stop_fails:
        assert events == ["stop", "Required FET005 physics stop failed."]
        assert any("physics stop" in note for note in primary.__notes__)
    else:
        assert events == ["stop", "teardown", "restore", "update", "update"]


@pytest.mark.asyncio
async def test_each_later_identifier_reloads_the_source_before_testing(grasp_module, monkeypatch):
    ctx = _execution_context(monkeypatch, ["/Asset/grasp_identifier_1", "/Asset/grasp_identifier_2"])
    events = []
    ctx.scene.load_asset = lambda path, **_kwargs: events.append(("load", path))
    ctx.scene.clear = lambda: events.append(("clear", None))

    async def run(*_args):
        events.append(("test", None))
        return {"failed": True, "phase_name": "Lifting", "message": "No lift"}

    monkeypatch.setattr(grasp_module, "_test_one_identifier", run)
    await grasp_module.test_grasp_and_lift(ctx)
    assert events == [("load", "asset.usd"), ("test", None), ("clear", None), ("load", "asset.usd"), ("test", None)]
    assert ctx.metrics["grasp_failed"] == 2


@pytest.mark.asyncio
async def test_failed_inter_identifier_clear_is_incomplete_not_asset_failure(grasp_module, monkeypatch):
    ctx = _execution_context(monkeypatch, ["/Asset/grasp_identifier_1", "/Asset/grasp_identifier_2"])
    primary = RuntimeError("Scene clear failed")
    health = []
    ctx._engine_session = types.SimpleNamespace(record_required_cleanup_failure=health.append)

    def clear():
        raise primary

    ctx.scene.clear = clear

    async def run(*_args):
        return {"failed": False}

    monkeypatch.setattr(grasp_module, "_test_one_identifier", run)
    with pytest.raises(RuntimeError) as captured:
        await grasp_module.test_grasp_and_lift(ctx)
    assert captured.value is primary
    assert ctx.failures == []
    assert health == ["Required FET005 scene reset failed."]


@pytest.mark.asyncio
async def test_owned_generated_fixture_removal_cleans_root_and_session_layers(grasp_module):
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Cube.Define(stage, "/World/grasp_robot/pad")
    UsdGeom.Xform.Define(stage, "/World/GripperMaterial")
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        stage.OverridePrim("/World/grasp_robot").SetCustomDataByKey("temporary", True)
    events, args = _cleanup_fixture()
    args = (*args[:3], stage, [], *args[5:])
    await grasp_module._cleanup_identifier_scene(
        *args, owned_fixture_paths=("/World/grasp_robot", "/World/GripperMaterial")
    )
    assert not stage.GetPrimAtPath("/World/grasp_robot").IsValid()
    assert not stage.GetPrimAtPath("/World/GripperMaterial").IsValid()
    assert stage.GetSessionLayer().GetPrimAtPath("/World/grasp_robot") is None
    assert events == ["stop", "teardown", "update"]


@pytest.mark.asyncio
async def test_failed_stop_preserves_owned_fixture_and_first_cause(grasp_module):
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Cube.Define(stage, "/World/grasp_robot/pad")
    primary = RuntimeError("Stop failed")
    events, args = _cleanup_fixture(stop_error=primary)
    args = (*args[:3], stage, [], *args[5:])
    with pytest.raises(RuntimeError) as captured:
        await grasp_module._cleanup_identifier_scene(*args, owned_fixture_paths=("/World/grasp_robot",))
    assert captured.value is primary
    assert stage.GetPrimAtPath("/World/grasp_robot/pad").IsValid()
    assert events == ["stop", "Required FET005 physics stop failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [RuntimeError("Controller close failed"), asyncio.CancelledError(), KeyboardInterrupt()]
)
@pytest.mark.parametrize("has_primary", [False, True])
async def test_controller_cleanup_failure_withholds_every_topology_write(grasp_module, error, has_primary):
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Cube.Define(stage, "/World/grasp_robot/pad")
    events, args = _cleanup_fixture(robot_error=error)
    args = (*args[:3], stage, *args[4:])
    primary = RuntimeError("Original command failed") if has_primary else None
    if has_primary:
        await grasp_module._cleanup_identifier_scene(
            *args, original_error=primary, owned_fixture_paths=("/World/grasp_robot",)
        )
        assert any("generated controller teardown" in note for note in primary.__notes__)
    else:
        with pytest.raises(type(error)) as captured:
            await grasp_module._cleanup_identifier_scene(*args, owned_fixture_paths=("/World/grasp_robot",))
        assert captured.value is error
    assert stage.GetPrimAtPath("/World/grasp_robot/pad").IsValid()
    assert events == ["stop", "teardown", "Required FET005 generated controller teardown failed."]


@pytest.mark.asyncio
async def test_explicit_false_controller_cleanup_is_not_a_topology_barrier(grasp_module):
    events, args = _cleanup_fixture(robot_result=False)
    with pytest.raises(RuntimeError, match="controller teardown was rejected"):
        await grasp_module._cleanup_identifier_scene(*args, owned_fixture_paths=("/World/grasp_robot",))
    assert events == ["stop", "teardown", "Required FET005 generated controller teardown failed."]


@pytest.mark.parametrize(
    "paths, expected",
    [
        (["/A/grasp_identifier_1", "/B/grasp_identifier_2"], ["grasp_identifier_1", "grasp_identifier_2"]),
        (
            ["/A/grasp_identifier_1", "/B/grasp_identifier_1"],
            ["grasp_identifier_1_identifier_001", "grasp_identifier_1_identifier_002"],
        ),
        (
            ["/A/grasp.identifier", "/B/grasp_identifier"],
            ["grasp_identifier_identifier_001", "grasp_identifier_identifier_002"],
        ),
        (["/A/grasp", "/B/GRASP"], ["grasp_identifier_001", "GRASP_identifier_002"]),
        (
            ["/A/grasp", "/B/grasp", "/C/grasp_identifier_001", "/D/grasp_identifier_001_2"],
            ["grasp_identifier_001_3", "grasp_identifier_002", "grasp_identifier_001", "grasp_identifier_001_2"],
        ),
        (["/A/___", "/B/___"], ["grasp_identifier_001", "grasp_identifier_002"]),
    ],
)
def test_identifier_output_aliases_are_deterministic_and_preserve_unique_names(grasp_module, paths, expected):
    aliases = grasp_module._identifier_output_aliases(paths)
    assert aliases == expected
    assert len({alias.casefold() for alias in aliases}) == len(paths)
    assert grasp_module._identifier_output_aliases(paths) == aliases


@pytest.mark.asyncio
async def test_duplicate_identifier_outputs_keep_raw_paths_and_distinct_results(grasp_module, monkeypatch):
    paths = ["/Asset/BodyA/grasp_identifier_1", "/Asset/BodyB/grasp_identifier_1"]
    ctx = _execution_context(monkeypatch, paths)
    calls = []

    async def run(_ctx, _cfg, identifier_path, output_alias, _asset_path):
        calls.append((identifier_path, output_alias))
        return {"failed": len(calls) == 1, "phase_name": "Lifting", "message": "No lift"}

    monkeypatch.setattr(grasp_module, "_test_one_identifier", run)
    await grasp_module.test_grasp_and_lift(ctx)
    aliases = grasp_module._identifier_output_aliases(paths)
    assert calls == list(zip(paths, aliases, strict=True))
    for index, (path, alias) in enumerate(calls):
        assert ctx.metrics["grasp_%s_identifier_path" % alias] == path
        assert ctx.metrics["grasp_%s_passed" % alias] == index
    assert ctx.metrics["grasp_total"] == 2
    assert ctx.metrics["grasp_passed"] == 1
    assert ctx.failures == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rejected_operation", ["stop", "play"])
async def test_initial_physics_rejection_prevents_behavior_evaluation(grasp_module, monkeypatch, rejected_operation):
    events, cleanup_args = _cleanup_fixture()
    ctx, _physics, robot, stage, _mutations, restore, update = cleanup_args
    stops = 0

    def stop():
        nonlocal stops
        stops += 1
        events.append("initial_stop" if stops == 1 else "cleanup_stop")
        return False if stops == 1 and rejected_operation == "stop" else None

    def play():
        events.append("play")
        return False if rejected_operation == "play" else None

    physics = types.SimpleNamespace(stop=stop, play=play)
    room = types.SimpleNamespace(auto_size=lambda *_args: None, set_color=lambda *_args: None, show_ground=lambda: None)

    async def ready(*_args, **_kwargs):
        return None

    ctx.scene = types.SimpleNamespace(
        asset=object(),
        add_room=lambda: room,
        add_physics=lambda **_kwargs: physics,
        lighting=types.SimpleNamespace(add_dome=lambda **_kwargs: None),
        setup_camera_follow=lambda: None,
        prepare_physics=ready,
    )
    ctx.settle = ready
    ctx.log = lambda _message: None

    class GraspScene:
        def __init__(self, *_args):
            self.robot = robot

        def init_tracking(self):
            pass

        async def run_simulation(self, *_args):
            raise AssertionError("Required startup rejection must not evaluate grasp behavior")

    omni = types.ModuleType("omni")
    omni.__path__ = []
    usd = types.ModuleType("omni.usd")
    usd.get_context = lambda: types.SimpleNamespace(get_stage=lambda: stage)
    omni.usd = usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    stage_module = types.ModuleType("isaacsim.core.utils.stage")
    stage_module.update_stage_async = update
    monkeypatch.setitem(sys.modules, stage_module.__name__, stage_module)
    physics_module = types.ModuleType("simready.evaluate_engine_kit.physics_utils")
    physics_module.active_physics_engine = lambda: "physx"
    physics_module.configure_physx_determinism = lambda *_args: None
    physics_module.cook_skip_message = lambda value: value
    monkeypatch.setitem(sys.modules, physics_module.__name__, physics_module)
    scene_module = types.ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_scene")
    scene_module.GraspScene = GraspScene
    monkeypatch.setitem(sys.modules, scene_module.__name__, scene_module)
    articulation_module = types.ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.newton_articulation")
    articulation_module.apply_temporary_newton_articulations = lambda *_args: []
    articulation_module.remove_temporary_newton_articulations = restore
    monkeypatch.setitem(sys.modules, articulation_module.__name__, articulation_module)
    monkeypatch.setattr(grasp_module, "_place_asset_on_ground", lambda *_args, **_kwargs: None)

    expected = "initial physics stop" if rejected_operation == "stop" else "physics start"
    with pytest.raises(RuntimeError, match=expected + " was rejected"):
        await grasp_module._test_one_identifier(ctx, {"physics_fps": 240}, "/Asset/grasp_identifier", "grasp", "/Asset")
    assert "cleanup_stop" in events
    assert "teardown" in events
    assert ("play" in events) is (rejected_operation == "play")

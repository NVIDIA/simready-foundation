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
"""Real USD support isolation and actual production phase-order regressions."""

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_close_lift as phase


@pytest.mark.asyncio
async def test_carrier_cleanup_error_invalidates_otherwise_successful_trial(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_carrier

    async def failed_detach(*args, **kwargs):
        raise RuntimeError("injected pin restoration failure")

    monkeypatch.setattr(gripper_carrier, "detach_carrier", failed_detach)
    with pytest.raises(RuntimeError, match="carrier restoration failed") as failure:
        await phase._detach_trial_carrier(None, object(), SimpleNamespace())
    assert str(failure.value.__cause__) == "injected pin restoration failure"


@pytest.mark.asyncio
async def test_carrier_cleanup_preserves_primary_failure_and_records_secondary_diagnostic(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_carrier

    metrics, warnings = {}, []
    ctx = SimpleNamespace(add_metric=metrics.__setitem__, warn=warnings.append)
    original = RuntimeError("primary readback failure")

    async def failed_detach(*args, **kwargs):
        raise RuntimeError("injected pin restoration failure")

    monkeypatch.setattr(gripper_carrier, "detach_carrier", failed_detach)
    await phase._detach_trial_carrier(None, object(), ctx, original)
    assert metrics["test_carrier_restoration_incomplete"] is True
    assert warnings
    assert str(original) == "primary readback failure"


def _context(enabled=True, session=False):
    stage = Usd.Stage.CreateInMemory()
    for path in ("/World/Room/Floor", "/World/Room/Wall", "/World/GroundPlane/mesh", "/World/Asset/pad"):
        prim = UsdGeom.Cube.Define(stage, path).GetPrim()
        api = UsdPhysics.CollisionAPI.Apply(prim)
        if enabled is not None or path != "/World/Room/Floor":
            api.CreateCollisionEnabledAttr(enabled if path == "/World/Room/Floor" else True)
    if session:
        stage.SetEditTarget(stage.GetSessionLayer())
    metrics, warnings, events = {}, [], []
    floor = UsdPhysics.CollisionAPI(stage.GetPrimAtPath("/World/Room/Floor")).GetCollisionEnabledAttr()

    def show_ground(**kwargs):
        assert floor.Set(True)
        events.append("floor_enabled")

    room = SimpleNamespace(
        _stage=stage, _room_path="/World/Room", show_ground=show_ground, set_color=lambda *args: None
    )
    scene = SimpleNamespace(
        stage=stage,
        _room_handle=room,
        _ground_plane_path="/World/GroundPlane",
        asset=SimpleNamespace(prim_path="/World/Asset"),
        _asset_root_path="/World/Asset",
    )
    return (
        SimpleNamespace(scene=scene, add_metric=metrics.__setitem__, warn=warnings.append, log=lambda text: None),
        metrics,
        warnings,
        events,
    )


def _collision(ctx, path):
    return UsdPhysics.CollisionAPI(ctx.scene.stage.GetPrimAtPath(path)).GetCollisionEnabledAttr()


@pytest.mark.parametrize("enabled", [True, False, None])
@pytest.mark.parametrize("session", [True, False])
def test_support_pause_preserves_collision_opinions_and_never_touches_assets_or_walls(enabled, session):
    ctx, metrics, _, _ = _context(enabled, session)
    layer = ctx.scene.stage.GetEditTarget().GetLayer()
    paths = ["/World/Room/Floor", "/World/GroundPlane/mesh"]
    attributes = [_collision(ctx, path) for path in paths]
    before = [attribute.Get() for attribute in attributes]
    opinions = [layer.GetAttributeAtPath(attribute.GetPath()) for attribute in attributes]
    authored_defaults = [
        (spec is not None, spec.default if spec is not None and spec.HasInfo("default") else None) for spec in opinions
    ]
    pause = phase._GripperSupportPause(ctx)
    assert [attribute.Get() for attribute in attributes] == [False, False]
    assert _collision(ctx, "/World/Asset/pad").Get() is True
    assert _collision(ctx, "/World/Room/Wall").Get() is True
    assert metrics["test_support_collision_suspended"] == [
        path for path, state in zip(paths, before, strict=True) if state
    ]
    pause.restore()
    assert [attribute.Get() for attribute in attributes] == before
    after = [layer.GetAttributeAtPath(attribute.GetPath()) for attribute in attributes]
    assert [
        (spec is not None, spec.default if spec is not None and spec.HasInfo("default") else None) for spec in after
    ] == authored_defaults
    pause.restore()  # Idempotent and never creates a second collision opinion.


@pytest.mark.parametrize("support", ["/World/Asset", "/World/Asset/pad", "/World/Missing", "/World", "relative/path"])
def test_declared_support_must_be_owned_and_present_before_any_collision_changes(support):
    ctx, _, _, _ = _context()
    ctx.scene._ground_plane_path = support
    with pytest.raises(RuntimeError, match="FET028 setup"):
        phase._GripperSupportPause(ctx)
    assert _collision(ctx, "/World/Room/Floor").Get() is True
    assert _collision(ctx, "/World/Asset/pad").Get() is True


def test_untracked_ground_is_not_guessed_and_different_stage_room_is_rejected():
    ctx, _, _, _ = _context()
    ctx.scene._ground_plane_path = None
    pause = phase._GripperSupportPause(ctx)
    assert _collision(ctx, "/World/GroundPlane/mesh").Get() is True
    pause.restore()
    ctx.scene._room_handle._stage = Usd.Stage.CreateInMemory()
    with pytest.raises(RuntimeError, match="different stage"):
        phase._GripperSupportPause(ctx)
    assert _collision(ctx, "/World/Room/Floor").Get() is True


def test_animated_support_is_not_silently_converted_to_a_static_collision_policy():
    ctx, _, _, _ = _context()
    _collision(ctx, "/World/GroundPlane/mesh").Set(False, 1.0)
    with pytest.raises(RuntimeError, match="static boolean"):
        phase._GripperSupportPause(ctx)
    assert _collision(ctx, "/World/Room/Floor").Get() is True


@pytest.mark.parametrize("original_error", [None, RuntimeError("mapping failure"), asyncio.CancelledError()])
def test_restore_attempts_all_supports_and_does_not_replace_primary_error(original_error):
    ctx, metrics, warnings, _ = _context()
    pause = phase._GripperSupportPause(ctx)
    original = pause.pending[0]["attribute"]

    class FailingRestore:
        def Set(self, value):
            return False if value else original.Set(value)

        def __getattr__(self, name):
            return getattr(original, name)

    pause.pending[0]["attribute"] = FailingRestore()
    if original_error is None:
        with pytest.raises(RuntimeError, match="support collision restoration failed"):
            pause.restore()
    else:
        pause.restore(original_error)
    assert _collision(ctx, "/World/GroundPlane/mesh").Get() is True
    assert metrics["test_support_restoration_incomplete"] is True and len(warnings) == 1
    assert len(pause.pending) == 1
    pause.pending[0]["attribute"] = original
    pause.restore()
    assert _collision(ctx, "/World/Room/Floor").Get() is True


def _calls(statement, name):
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
        for node in ast.walk(statement)
    )


@pytest.mark.asyncio
async def test_successful_trial_cleanup_does_not_inherit_callers_handled_exception(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_carrier

    source_path = Path(phase.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    trial = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try) and any(_calls(statement, "_GripperSupportPause") for statement in node.body)
    )
    body = ast.Try(body=[ast.Pass()], handlers=trial.handlers, orelse=[], finalbody=trial.finalbody)
    wrapper = ast.AsyncFunctionDef(
        name="run_trial",
        args=ast.arguments(
            posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=ast.parse("trial_error = None").body + [body],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    ctx, _, _, _ = _context()
    namespace = {
        "stage": ctx.scene.stage,
        "ctx": ctx,
        "support_pause": None,
        "carrier": object(),
        "obj": None,
        "video_frames": [],
        # This extraction exercises required fixture cleanup with the
        # production-default optional contact observer disabled.
        "contact_diagnostics_enabled": False,
        "_detach_trial_carrier": phase._detach_trial_carrier,
        "_cleanup_gripper_trial": phase._cleanup_gripper_trial,
        "object_edit_target": None,
        "native_contact_collector": None,
        "metric_suffix": "",
        "video_fps_max": 20,
        "shape": "sphere",
        "winning_shape": None,
        "asyncio": asyncio,
    }
    exec(compile(module, str(source_path), "exec"), namespace)

    async def failed_detach(*args, **kwargs):
        raise RuntimeError("injected incomplete cleanup")

    monkeypatch.setattr(gripper_carrier, "detach_carrier", failed_detach)
    try:
        raise ValueError("unrelated exception handled by the caller")
    except ValueError:
        with pytest.raises(RuntimeError, match="test-owned carrier restoration failed"):
            await namespace["run_trial"]()


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("failure", [None, "mapping", "move", "settle", "spawn", "cancel_mapping", "cancel_move"])
def test_actual_trial_keeps_support_free_through_probe_and_standoff_and_restores_on_every_exit(
    enabled, failure, monkeypatch
):
    ctx, _, _, events = _context(enabled)
    stage = ctx.scene.stage
    source_path = Path(phase.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    trial = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try) and any(_calls(statement, "_GripperSupportPause") for statement in node.body)
    )
    suspend = next(statement for statement in trial.body if _calls(statement, "_GripperSupportPause"))
    mapping = next(
        node
        for node in ast.walk(trial)
        if isinstance(node, ast.Assign) and _calls(node, "_detect_open_closed_positions")
    )
    standoff = next(
        statement
        for statement in trial.body
        if isinstance(statement, ast.If)
        and _calls(statement, "linear_translate")
        and _calls(statement, "_settle_for_seconds")
    )
    restore = next(
        statement
        for statement in trial.body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and isinstance(statement.value.func.value, ast.Name)
        and statement.value.func.value.id == "support_pause"
    )
    clear_pause = next(
        statement
        for statement in trial.body
        if isinstance(statement, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "support_pause" for target in statement.targets)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is None
    )
    ground = next(statement for statement in trial.body if _calls(statement, "_prepare_gripper_ground"))
    spawn = next(
        statement
        for statement in trial.body
        if isinstance(statement, ast.Assign) and _calls(statement, "spawn_test_object")
    )
    body = ast.Try(
        body=[suspend, mapping, standoff, restore, clear_pause, ground, spawn],
        handlers=trial.handlers,
        orelse=[],
        finalbody=trial.finalbody,
    )
    initialize = ast.parse("obj = None\nsupport_pause = None\ntrial_error = None").body
    wrapper = ast.AsyncFunctionDef(
        name="run_trial",
        args=ast.arguments(
            posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=initialize + [body],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))

    def observe(name, supports_off=True):
        assert _collision(ctx, "/World/Asset/pad").Get() is True
        assert _collision(ctx, "/World/Room/Floor").Get() is (False if supports_off else True)
        assert _collision(ctx, "/World/GroundPlane/mesh").Get() is (not supports_off)
        events.append(name)
        if failure == name:
            raise RuntimeError("injected " + name)
        if failure == "cancel_" + name:
            raise asyncio.CancelledError()

    async def mapping_call(*args):
        observe("mapping")
        return 0.0, 1.0

    async def translate(**kwargs):
        observe("move")
        assert kwargs["duration_s"] == 0.6 and kwargs["delta_world"][2] == 0.3
        await kwargs["on_substep"](1)

    async def settle(*args, **kwargs):
        observe("settle")
        assert args[1] == 0.2
        await kwargs["on_step"](1)

    def spawn_call(**kwargs):
        observe("spawn", supports_off=False)
        return None

    async def detach(*args, **kwargs):
        events.append("detach")

    monkeypatch.setattr(phase, "_detach_trial_carrier", detach)

    namespace = {
        "ctx": ctx,
        "stage": stage,
        "robot": object(),
        "fingertip_set": object(),
        "probe_config": {},
        "site": SimpleNamespace(max_opening=0.1),
        "gripper_base_path": "/World/Asset",
        "support_pause": None,
        "carrier": object(),
        "obj": None,
        "required_raise": 0.3,
        "grasp_specs": [],
        "shape": "sphere",
        "object_size_m": 0.05,
        "tested_mass_kg": 0.1,
        "spawn_pose": np.eye(4),
        "video_frames": [],
        "np": np,
        "config": {"static_friction": 1.0, "dynamic_friction": 1.0, "restitution": 0.0},
        "_GripperSupportPause": phase._GripperSupportPause,
        "_detect_open_closed_positions": mapping_call,
        "linear_translate": translate,
        "_settle_for_seconds": settle,
        "_command_grasp_targets": lambda *args: None,
        "_prepare_gripper_ground": phase._prepare_gripper_ground,
        "spawn_test_object": spawn_call,
        "_detach_trial_carrier": detach,
        "contact_diagnostics_enabled": False,
        "_cleanup_gripper_trial": phase._cleanup_gripper_trial,
        "object_edit_target": None,
        "native_contact_collector": None,
        "metric_suffix": "",
        "video_fps_max": 20,
        "winning_shape": None,
        "asyncio": asyncio,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    if failure:
        with pytest.raises(asyncio.CancelledError if failure.startswith("cancel_") else RuntimeError):
            asyncio.run(namespace["run_trial"]())
    else:
        asyncio.run(namespace["run_trial"]())
        assert events == ["mapping", "move", "settle", "floor_enabled", "spawn", "detach"]
    assert events[-1] == "detach"
    assert _collision(ctx, "/World/Room/Floor").Get() is (True if failure == "spawn" or failure is None else enabled)
    assert _collision(ctx, "/World/GroundPlane/mesh").Get() is True
    assert _collision(ctx, "/World/Asset/pad").Get() is True

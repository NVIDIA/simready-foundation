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
"""Production cleanup boundaries preserve cause, stage ownership and health."""

import asyncio
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.evaluate_engine_kit.kit_engine_proxy import KitEngineProxy
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_carrier
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_close_lift as phase
from simready.foundation.tier_core.runtime_tests.articulation_phases.object_spawning import (
    spawn_test_object,
)


@pytest.fixture(autouse=True)
def independent_process_health(monkeypatch):
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)


def _context():
    stage = Usd.Stage.CreateInMemory()
    adapter = object.__new__(KitEngineProxy)
    adapter._required_cleanup_failures = []
    events = []
    ctx = SimpleNamespace(
        _engine_session=adapter,
        scene=SimpleNamespace(stage=stage),
        add_metric=lambda *args: events.append("metric"),
        warn=lambda *args: events.append("warning"),
        log=lambda *args: events.append("log"),
        encode_video=lambda *args, **kwargs: events.append("video"),
    )
    return ctx, stage, adapter, events


def _object(stage):
    return spawn_test_object(stage, "/World", "cube", 0.04, 0.1, 0.5, 0.5, 0.0, np.eye(4), physics_engine="physx")


async def _cleanup(ctx, stage, **overrides):
    options = {
        "carrier": None,
        "support_pause": None,
        "obj": None,
        "object_edit_target": stage.GetEditTarget(),
        "contact_collector": None,
        "contact_enabled": False,
        "contact_metric": "native_contact_diagnostics",
        "stop_reason": "completed",
        "video_frames": ["frame.png"],
        "video_fps": 20,
        "shape": "cube",
        "original_error": None,
    }
    options.update(overrides)
    await phase._cleanup_gripper_trial(ctx, stage, **options)


def _raise(error):
    raise error


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
async def test_carrier_stop_request_is_not_reclassified_or_bypassed_by_object_topology_edits(monkeypatch, error_type):
    ctx, stage, adapter, events = _context()
    obj = _object(stage)
    error = error_type("requested stop")

    async def fail(*args, **kwargs):
        events.append("carrier")
        raise error

    monkeypatch.setattr(gripper_carrier, "detach_carrier", fail)
    with pytest.raises(error_type) as caught:
        await _cleanup(ctx, stage, carrier=object(), obj=obj)
    assert caught.value is error
    assert stage.GetPrimAtPath(obj.root_path)
    assert "video" in events
    assert adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.asyncio
@pytest.mark.parametrize("sink", ["add_metric", "warn", "log", "encode_video"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("has_primary", [False, True])
async def test_optional_sinks_cannot_replace_required_carrier_failure(monkeypatch, sink, error_type, has_primary):
    ctx, stage, adapter, events = _context()
    obj = _object(stage)
    cause = OSError("native carrier restoration")
    original = ValueError("trial cause") if has_primary else None
    sink_error = error_type("diagnostic sink")

    async def fail(*args, **kwargs):
        raise cause

    monkeypatch.setattr(gripper_carrier, "detach_carrier", fail)
    setattr(ctx, sink, lambda *args, **kwargs: _raise(sink_error))
    if has_primary:
        await _cleanup(ctx, stage, carrier=object(), obj=obj, original_error=original)
        assert original.__notes__
    else:
        with pytest.raises(RuntimeError, match="test-owned carrier restoration failed") as caught:
            await _cleanup(ctx, stage, carrier=object(), obj=obj)
        assert caught.value.__cause__ is cause
    assert stage.GetPrimAtPath(obj.root_path)
    assert adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.asyncio
@pytest.mark.parametrize("sink", ["log", "encode_video"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt, SystemExit])
async def test_optional_only_failure_is_ordinary_warning_or_original_stop_request(sink, error_type):
    ctx, stage, adapter, _ = _context()
    obj = _object(stage)
    error = error_type("optional evidence")
    ctx.encode_video = lambda *args, **kwargs: _raise(error if sink == "encode_video" else OSError("codec"))
    if sink == "log":
        ctx.log = lambda *args: _raise(error)
    if error_type is RuntimeError:
        await _cleanup(ctx, stage, obj=obj)
    else:
        with pytest.raises(error_type) as caught:
            await _cleanup(ctx, stage, obj=obj)
        assert caught.value is error
    assert not stage.GetPrimAtPath(obj.root_path)
    assert not adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is False


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
async def test_contact_evidence_stop_precedes_later_required_failure_without_skipping_cleanup(monkeypatch, error_type):
    ctx, stage, adapter, events = _context()
    obj = _object(stage)
    error = error_type("contact sink stopped")
    collector = SimpleNamespace(
        close=lambda **kwargs: events.append("contact_closed"),
        snapshot=lambda: {"schema_version": 1, "cleanup_complete": True},
    )
    ctx.add_metric = lambda *args: _raise(error)
    support = SimpleNamespace(restore=lambda primary: events.append("support_restored"))

    async def fail(*args, **kwargs):
        events.append("carrier_failed")
        raise OSError("carrier cleanup")

    monkeypatch.setattr(gripper_carrier, "detach_carrier", fail)
    with pytest.raises(error_type) as caught:
        await _cleanup(
            ctx,
            stage,
            carrier=object(),
            support_pause=support,
            obj=obj,
            contact_enabled=True,
            contact_collector=collector,
        )
    assert caught.value is error
    assert events[:3] == ["contact_closed", "support_restored", "carrier_failed"]
    assert stage.GetPrimAtPath(obj.root_path)
    assert "video" in events
    assert adapter.required_cleanup_failures


@pytest.mark.asyncio
async def test_object_removal_uses_captured_target_preserves_current_target_and_unrelated_content():
    ctx, stage, adapter, _ = _context()
    authored = stage.GetEditTarget()
    obj = _object(stage)
    other = Sdf.Layer.CreateAnonymous("unrelated")
    stage.GetSessionLayer().subLayerPaths.append(other.identifier)
    stage.SetEditTarget(other)
    UsdGeom.Xform.Define(stage, "/Unrelated")
    await _cleanup(ctx, stage, obj=obj, object_edit_target=authored)
    assert not stage.GetPrimAtPath(obj.root_path)
    assert stage.GetPrimAtPath("/Unrelated")
    assert stage.GetEditTarget().GetLayer() == other
    assert not adapter.required_cleanup_failures


@pytest.mark.asyncio
async def test_surviving_object_opinion_is_required_cleanup_failure_not_a_successful_warning():
    ctx, stage, adapter, events = _context()
    authored = stage.GetEditTarget()
    obj = _object(stage)
    other = Sdf.Layer.CreateAnonymous("surviving")
    stage.GetSessionLayer().subLayerPaths.append(other.identifier)
    with Usd.EditContext(stage, other):
        remaining = UsdGeom.Cube.Define(stage, obj.prim_path).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(remaining)
    with pytest.raises(RuntimeError, match="test-object removal") as caught:
        await _cleanup(ctx, stage, obj=obj, object_edit_target=authored)
    assert "remains composed" in str(caught.value.__cause__)
    assert stage.GetPrimAtPath(obj.root_path)
    assert "video" in events
    assert adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.asyncio
@pytest.mark.parametrize("signal_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt, SystemExit])
async def test_failed_health_sink_cannot_replace_actual_required_failure(monkeypatch, signal_type):
    ctx, stage, adapter, _ = _context()
    cause = OSError("native detach")
    record = adapter.record_required_cleanup_failure

    def failed_signal(reason):
        record(reason)
        raise signal_type("health sink")

    adapter.record_required_cleanup_failure = failed_signal

    async def fail(*args, **kwargs):
        raise cause

    monkeypatch.setattr(gripper_carrier, "detach_carrier", fail)
    with pytest.raises(RuntimeError) as caught:
        await _cleanup(ctx, stage, carrier=object())
    assert caught.value.__cause__ is cause
    assert adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.parametrize("error_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
def test_support_pause_diagnostic_interruption_restores_real_collision_before_unwinding(error_type):
    ctx, stage, adapter, _ = _context()
    floor = UsdGeom.Cube.Define(stage, "/World/Room/Floor").GetPrim()
    collision = UsdPhysics.CollisionAPI.Apply(floor).CreateCollisionEnabledAttr(True)
    ctx.scene._room_handle = SimpleNamespace(_room_path="/World/Room", _stage=stage)
    error = error_type("support recording")
    ctx.add_metric = lambda *args: _raise(error)
    with pytest.raises(error_type) as caught:
        phase._GripperSupportPause(ctx)
    assert caught.value is error
    assert collision.Get() is True
    assert not adapter.required_cleanup_failures


@pytest.mark.asyncio
@pytest.mark.parametrize("cause_type", [OSError, asyncio.CancelledError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("sink", ["add_metric", "warn"])
@pytest.mark.parametrize("has_primary", [False, True])
async def test_real_support_restore_finishes_other_snapshots_and_preserves_first_cause(
    monkeypatch, cause_type, sink, has_primary
):
    ctx, stage, adapter, events = _context()
    floor = UsdGeom.Cube.Define(stage, "/World/Room/Floor").GetPrim()
    floor_collision = UsdPhysics.CollisionAPI.Apply(floor).CreateCollisionEnabledAttr(True)
    second = UsdGeom.Cube.Define(stage, "/World/Room/Floor/other").GetPrim()
    second_collision = UsdPhysics.CollisionAPI.Apply(second).CreateCollisionEnabledAttr(True)
    ctx.scene._room_handle = SimpleNamespace(_room_path="/World/Room", _stage=stage)
    support = phase._GripperSupportPause(ctx)
    assert floor_collision.Get() is False and second_collision.Get() is False
    cause = cause_type("support restoration")
    broken = next(
        snapshot for snapshot in support.pending if snapshot["attribute"].GetPath() == floor_collision.GetPath()
    )
    broken["attribute"] = SimpleNamespace(Set=lambda *args: _raise(cause))
    setattr(ctx, sink, lambda *args: _raise(SystemExit("optional support warning")))
    obj = _object(stage)
    original = ValueError("original trial failure") if has_primary else None
    if has_primary:
        await _cleanup(ctx, stage, support_pause=support, obj=obj, original_error=original)
        assert original.__notes__
    else:
        with pytest.raises(RuntimeError if cause_type is OSError else cause_type) as caught:
            await _cleanup(ctx, stage, support_pause=support, obj=obj)
        if cause_type is OSError:
            assert caught.value.__cause__ is cause
        else:
            assert caught.value is cause
    assert second_collision.Get() is True
    assert floor_collision.Get() is False
    assert len(support.pending) == 1
    assert not stage.GetPrimAtPath(obj.root_path)
    assert "video" in events
    assert adapter.required_cleanup_failures


@pytest.mark.asyncio
async def test_falsey_original_error_is_not_discarded_by_cleanup(monkeypatch):
    class FalseyTrialError(ValueError):
        def __bool__(self):
            return False

    ctx, stage, _, _ = _context()
    original = FalseyTrialError("first trial cause")

    async def fail(*args, **kwargs):
        raise OSError("later cleanup")

    monkeypatch.setattr(gripper_carrier, "detach_carrier", fail)
    await _cleanup(ctx, stage, carrier=object(), original_error=original)
    assert original.__notes__


@pytest.mark.parametrize("boundary", ["construct", "enter", "exit"])
@pytest.mark.parametrize("original_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
def test_support_constructor_preserves_first_stop_when_restoration_edit_context_fails(
    monkeypatch, boundary, original_type
):
    ctx, stage, adapter, _ = _context()
    floor = UsdGeom.Cube.Define(stage, "/World/Room/Floor").GetPrim()
    collision = UsdPhysics.CollisionAPI.Apply(floor).CreateCollisionEnabledAttr(True)
    ctx.scene._room_handle = SimpleNamespace(_room_path="/World/Room", _stage=stage)
    original = original_type("first constructor stop")
    original_context = Usd.EditContext

    class BrokenContext:
        def __init__(self, *args):
            self.actual = original_context(*args)
            if boundary == "construct":
                raise RuntimeError("cannot establish cleanup edit context")

        def __enter__(self):
            if boundary == "enter":
                raise RuntimeError("cannot enter cleanup edit context")
            return self.actual.__enter__()

        def __exit__(self, *args):
            result = self.actual.__exit__(*args)
            if boundary == "exit":
                raise RuntimeError("cannot confirm cleanup edit context exit")
            return result

    def fail_metric(*args):
        monkeypatch.setattr(Usd, "EditContext", BrokenContext)
        raise original

    ctx.add_metric = fail_metric
    with pytest.raises(original_type) as caught:
        phase._GripperSupportPause(ctx)
    assert caught.value is original
    assert collision.Get() is (boundary == "exit")
    assert adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.asyncio
async def test_actual_carrier_rejected_stop_leaves_owned_object_and_gantry_topology_untouched():
    ctx, stage, adapter, events = _context()
    obj = _object(stage)
    root = UsdGeom.Xform.Define(stage, "/World/_FET028_Gantry_test").GetPrim()
    before = stage.GetRootLayer().ExportToString()

    def stop():
        raise OSError("native timeline cannot stop")

    physics = SimpleNamespace(stop=stop)
    handle = SimpleNamespace(
        prebuilt=False,
        root_path=str(root.GetPath()),
        orientation_root_path="",
        robot=SimpleNamespace(prim_path="/World/Asset"),
        root_orientation_state=None,
        articulation_root_transfer=None,
        articulation_default_state=None,
        joint_default_state=None,
        world_pin_paths=(),
        world_pin_was_present=False,
        world_pin_states={},
        physics_was_playing=True,
        physics=physics,
    )
    with pytest.raises(RuntimeError, match="test-owned carrier restoration"):
        await _cleanup(ctx, stage, carrier=handle, obj=obj)
    assert stage.GetRootLayer().ExportToString() == before
    assert stage.GetPrimAtPath(obj.root_path) and stage.GetPrimAtPath(root.GetPath())
    assert "video" in events
    assert adapter.required_cleanup_failures
    assert sys._simready_evaluate_kit_engine_retired is True

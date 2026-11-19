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
from types import SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdShade
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    error_utils,
    gripper_carrier,
)
from simready.foundation.tier_core.runtime_tests.fet004_multibody import joint_movement
from simready.foundation.tier_core.runtime_tests.fet006_materials import _surface_test
from simready.foundation.tier_core.runtime_tests.fet010_standard import _probe, display_color_response

INTERRUPTS = [RuntimeError, asyncio.CancelledError, KeyboardInterrupt]


def _ctx():
    retired = []
    return SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=retired.append)), retired


@pytest.mark.parametrize("owner", [_probe, _surface_test])
@pytest.mark.parametrize("secondary_type", INTERRUPTS)
def test_every_independent_binding_purpose_is_cleaned_after_first_failure(monkeypatch, owner, secondary_type):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/World/Owned").GetPrim()
    calls = []
    secondary = secondary_type("first cleanup interrupted")

    def unbind(self, *, materialPurpose):
        calls.append(materialPurpose)
        if len(calls) == 1:
            raise secondary
        return True

    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "UnbindDirectBinding", unbind)
    with pytest.raises(secondary_type) as caught:
        (owner.unbind if owner is _probe else owner.clear)(stage, str(root.GetPath()))
    assert caught.value is secondary and calls == ["", "full", "preview"]


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", INTERRUPTS)
@pytest.mark.parametrize("primary_type", [None, RuntimeError, asyncio.CancelledError])
async def test_official_display_wrapper_preserves_primary_and_marks_uncertain_cleanup(
    monkeypatch, secondary_type, primary_type
):
    ctx, retired = _ctx()
    primary = primary_type("original capture failure") if primary_type else None
    secondary = secondary_type("required probe cleanup failed")

    async def measure(ctx, fixture):
        fixture.update(stage=None, binding_root="/World/Owned")
        if primary is not None:
            raise primary

    def cleanup(*args):
        raise secondary

    monkeypatch.setattr(display_color_response, "_measure_display_color_response", measure)
    monkeypatch.setattr(_probe, "unbind", cleanup)
    with pytest.raises(type(primary) if primary is not None else secondary_type) as caught:
        await display_color_response.test_display_color_response(ctx)
    if primary is not None:
        assert caught.value is primary
    elif not isinstance(secondary, Exception):
        assert caught.value is secondary
    else:
        assert caught.value.__cause__ is secondary
    assert retired == ["Required display-color probe cleanup failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", INTERRUPTS)
@pytest.mark.parametrize("primary_type", [None, RuntimeError, asyncio.CancelledError])
async def test_surface_context_restoration_preserves_first_cause(monkeypatch, secondary_type, primary_type):
    ctx, retired = _ctx()
    ctx.config = {}
    ctx.step = lambda *args: None
    primary = primary_type("original surface measurement failure") if primary_type else None
    secondary = secondary_type("context cleanup failed")

    async def render(*args, **kwargs):
        if primary is not None:
            raise primary
        return {"error": "pin", "effective": None}

    def restore(*args):
        raise secondary

    monkeypatch.setattr(_surface_test, "_validated_measurement_config", lambda config: {"min_material_coverage": 0.99})
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", restore)
    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test, "_fail_pass", lambda *args: None)
    with pytest.raises(type(primary) if primary is not None else secondary_type) as caught:
        await _surface_test.run_coverage_test(ctx, "", "SURF.001", "not an asset diagnosis")
    if primary is not None:
        assert caught.value is primary
    elif not isinstance(secondary, Exception):
        assert caught.value is secondary
    else:
        assert caught.value.__cause__ is secondary
    assert retired == ["Required surface render-context restoration failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", INTERRUPTS)
@pytest.mark.parametrize("primary_type", [None, RuntimeError, asyncio.CancelledError])
async def test_spherical_cleanup_requires_stop_and_preserves_original(monkeypatch, secondary_type, primary_type):
    ctx, retired = _ctx()
    stage = Usd.Stage.CreateInMemory()
    path = "/World/__SimReadyEvaluate_FET004_Driver"
    UsdGeom.Xform.Define(stage, path)
    primary = primary_type("original required native observation failed") if primary_type else None
    secondary = secondary_type("stop cleanup failed")
    calls = []

    async def settle(**kwargs):
        if primary is not None:
            raise primary

    def stop():
        calls.append("stop")
        if len(calls) == 2:
            raise secondary

    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "_create_external_spherical_driver", lambda *args: path)
    monkeypatch.setattr(joint_movement, "JointTracker", lambda *args: SimpleNamespace(finish=lambda: None))
    ctx.settle = settle
    physics = SimpleNamespace(stop=stop, play=lambda: None)
    with pytest.raises(type(primary) if primary is not None else secondary_type) as caught:
        await joint_movement._run_spherical_drive_sim(
            ctx, stage, {}, {}, physics, "rotX", 1, 1, 1, 0, 1, False, False, 1, 1
        )
    if primary is not None:
        assert caught.value is primary
    elif not isinstance(secondary, Exception):
        assert caught.value is secondary
    else:
        assert caught.value.__cause__ is secondary
    assert calls == ["stop", "stop"] and stage.GetPrimAtPath(path).IsValid()
    assert retired == ["Required spherical driver cleanup failed."]


@pytest.mark.asyncio
async def test_spherical_driver_removal_acknowledgement_is_required(monkeypatch):
    ctx, retired = _ctx()
    stage = Usd.Stage.CreateInMemory()
    path = "/World/__SimReadyEvaluate_FET004_Driver"
    UsdGeom.Xform.Define(stage, path)

    async def settle(**kwargs):
        return None

    ctx.settle = settle
    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "_create_external_spherical_driver", lambda *args: path)
    monkeypatch.setattr(joint_movement, "JointTracker", lambda *args: SimpleNamespace(finish=lambda: None))
    monkeypatch.setattr(Usd.Stage, "RemovePrim", lambda *args: False)
    with pytest.raises(RuntimeError, match="required spherical driver cleanup"):
        await joint_movement._run_spherical_drive_sim(
            ctx,
            stage,
            {},
            {},
            SimpleNamespace(stop=lambda: None, play=lambda: None),
            "rotX",
            1,
            1,
            1,
            0,
            1,
            False,
            False,
            1,
            1,
        )
    assert stage.GetPrimAtPath(path).IsValid() and retired


@pytest.mark.asyncio
@pytest.mark.parametrize("propagate_cancel", [False, True])
async def test_carrier_cleanup_attempts_remaining_safe_restoration_after_cancel(monkeypatch, propagate_cancel):
    ctx, retired = _ctx()
    calls = []
    cancelled = asyncio.CancelledError("independent gantry removal interrupted")

    def remove(*args):
        calls.append("remove")
        raise cancelled

    names = (
        "_restore_root_orientation",
        "_restore_carrier_root_transfer",
        "_restore_default_state",
        "_restore_joint_default_state",
        "_cleanup_carrier_opinions",
    )
    monkeypatch.setattr(gripper_carrier, "_remove_existing_gantry", remove)
    for name in names:
        monkeypatch.setattr(gripper_carrier, name, lambda *args, name=name: calls.append(name))

    async def initialize(ctx):
        calls.append("initialize")

    async def reset():
        calls.append("reset")

    robot = SimpleNamespace(
        prim_path="/World/Asset",
        articulation=None,
        initialize=initialize,
        _world=SimpleNamespace(reset_async=reset),
    )
    physics = SimpleNamespace(stop=lambda: calls.append("stop"), play=lambda: calls.append("play"))
    state = {
        "root_path": "/World/Owned",
        "physics_stopped": True,
        "physics_was_playing": False,
        "root_orientation_state": None,
        "articulation_default_state": None,
        "joint_default_state": None,
    }
    if propagate_cancel:
        with pytest.raises(asyncio.CancelledError) as caught:
            await gripper_carrier._finish_carrier_restore(None, robot, physics, state, ctx, propagate_cancel=True)
        assert caught.value is cancelled
    else:
        errors = await gripper_carrier._finish_carrier_restore(None, robot, physics, state, ctx, propagate_cancel=False)
        assert errors[0] is cancelled
    assert all(name in calls for name in names) and "initialize" in calls and "reset" in calls
    assert calls[-1] == "stop" and retired


def test_retirement_diagnostic_never_replaces_primary():
    primary = RuntimeError("original")

    def broken(reason):
        raise KeyboardInterrupt("optional retirement delivery interrupted")

    ctx = SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=broken))
    error_utils.record_required_cleanup_failure(ctx, "Required cleanup failed.", primary)
    assert str(primary) == "original"


@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_every_world_pin_is_restored_after_first_interruption(monkeypatch, secondary_type):
    calls = []
    secondary = secondary_type("first pin restoration interrupted")

    def restore(stage, path, state):
        calls.append(path)
        if len(calls) == 1:
            raise secondary
        return True

    monkeypatch.setattr(gripper_carrier, "_restore_world_pin", restore)
    with pytest.raises(secondary_type) as caught:
        gripper_carrier._require_world_pin_restore(None, ("/first", "/second"))
    assert caught.value is secondary and calls == ["/first", "/second"]


@pytest.mark.asyncio
async def test_actual_material_small_silhouette_is_unmeasured_not_asset_failure(monkeypatch):
    import numpy as np
    from simready.foundation.tier_core.runtime_tests.fet006_materials import preview_surface_renders

    ctx, retired = _ctx()
    ctx.config = dict(preview_surface_renders.CONFIG)
    ctx.step = lambda *args: None
    ctx.add_metric = lambda *args: None
    failures = []
    ctx.fail = failures.append
    passes = []

    async def render(*args, **kwargs):
        passes.append(True)
        return {
            "stage": None,
            "root": "/World/Asset",
            "mask": np.ones((2, 2), dtype=bool),
            "effective": [""],
        }

    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *args: None)
    monkeypatch.setattr(_surface_test._scene, "report_surface_inventory", lambda *args: {})
    monkeypatch.setattr(_surface_test, "_render_pass", render)
    with pytest.raises(RuntimeError, match="below the 5000 needed to measure"):
        await _surface_test.run_coverage_test(ctx, "", "SURF.001", "not a cause assessment")
    assert ctx.config["min_silhouette_pixels"] == 5000
    assert not failures and len(passes) == 1 and not retired

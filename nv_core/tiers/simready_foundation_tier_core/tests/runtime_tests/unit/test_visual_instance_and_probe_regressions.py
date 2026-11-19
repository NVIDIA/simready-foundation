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
"""Instance editing and two-color probe regressions using the official helpers."""

from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom
from simready.foundation.tier_core.runtime_tests.fet006_materials import _scene, _surface_test
from simready.foundation.tier_core.runtime_tests.fet011_semantics import _seg_common


def _registered_surface_definition(monkeypatch, module_name):
    import importlib

    from simready.evaluate.core import decorator

    monkeypatch.setattr(decorator, "_REGISTRY", [])
    module = importlib.import_module("simready.foundation.tier_core.runtime_tests.fet006_materials." + module_name)
    importlib.reload(module)
    return next(definition for definition in decorator.get_registered_tests() if definition.name == module_name)


def _official_surface_context(definition, overrides):
    from simready.evaluate.runner.test_context import RunContext
    from simready.evaluate_engine_kit.execution import _merge_config

    return RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir="unused-output",
        test_name=definition.name,
        test_version=definition.version,
        feature_id="FET006_Materials.0-1-0",
        engine_name="kit",
        engine_version="6.1.0",
        session_id="surface-config-regression",
        scene=None,
        config=_merge_config(definition.config_defaults, overrides),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", ["preview_surface_renders", "mdl_renders", "openpbr_renders"])
@pytest.mark.parametrize(
    ("key", "value"),
    [
        (key, value)
        for key in ("min_material_coverage", "min_silhouette_pixels", "mask_dominance_ratio", "mask_dominance_floor")
        for value in (float("nan"), float("inf"), float("-inf"), True, False, None, "1")
    ]
    + [
        ("min_material_coverage", -0.1),
        ("min_material_coverage", 1.1),
        ("mask_dominance_floor", -0.1),
        ("mask_dominance_floor", 1.1),
        ("mask_dominance_ratio", 0.0),
        ("mask_dominance_ratio", -1.0),
        ("min_silhouette_pixels", 0),
        ("min_silhouette_pixels", -1),
        ("min_silhouette_pixels", 1.5),
    ],
)
async def test_invalid_measurement_config_is_official_runtime_error_before_scene_mutation(
    monkeypatch, module_name, key, value
):
    import json
    import math

    from simready.evaluate.cli.modes import _parse_value
    from simready.evaluate_engine_kit.execution import _result_status_and_message

    definition = _registered_surface_definition(monkeypatch, module_name)
    if isinstance(value, float) and math.isnan(value):
        # Reproduce the official CLI -> saved-plan JSON -> runtime override path.
        value = json.loads(json.dumps(_parse_value("nan")))
    ctx = _official_surface_context(definition, {key: value})

    def untouched(*_args, **_kwargs):
        pytest.fail("Invalid configuration must be rejected before pinning or scene setup")

    monkeypatch.setattr(_surface_test._context, "read_order", untouched)
    monkeypatch.setattr(_surface_test, "_render_pass", untouched)
    with pytest.raises(RuntimeError, match="Invalid surface measurement configuration: " + key) as raised:
        await definition.func(ctx)
    status, message = _result_status_and_message(ctx, test_exception=raised.value)
    assert status == "error"
    assert key in message
    assert not ctx.failed
    assert not ctx.skipped
    assert ctx.metrics == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", ["preview_surface_renders", "mdl_renders", "openpbr_renders"])
@pytest.mark.parametrize(("floor", "expected_status"), [(0.0, "pass"), (1.0, "fail")])
async def test_valid_explicit_coverage_floor_keeps_the_measured_gate(monkeypatch, module_name, floor, expected_status):
    from simready.evaluate_engine_kit.execution import _result_status_and_message

    definition = _registered_surface_definition(monkeypatch, module_name)
    ctx = _official_surface_context(definition, {"min_material_coverage": floor, "min_silhouette_pixels": 1.0})
    calls = []

    async def render(_ctx, order, *_args, **_kwargs):
        calls.append(order)
        return {"mask": np.ones((2, 2), dtype=bool), "effective": order, "stage": object(), "root": "/Asset"}

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *_: None)
    monkeypatch.setattr(_surface_test._scene, "report_surface_inventory", lambda *_: {})
    # The fake stage has no materials; declare every context so the OpenPBR and MDL tests
    # measure instead of skipping.
    monkeypatch.setattr(_surface_test.surfaces, "declared_contexts", lambda *_: {"", "mdl", "mtlx"})
    monkeypatch.setattr(_surface_test, "_report_materialx", lambda *_: True)
    await definition.func(ctx)
    status, _message = _result_status_and_message(ctx)
    assert status == expected_status
    assert len(calls) == 3
    assert next(metric["value"] for name, metric in ctx.metrics.items() if name.endswith("_surface_coverage")) == 0.0


def test_measurement_config_partial_overrides_preserve_existing_defaults():
    defaults = _surface_test._validated_measurement_config({})
    assert defaults == {
        key: value
        for key, value in _scene.SCENE_DEFAULTS.items()
        if key in ("min_material_coverage", "min_silhouette_pixels", "mask_dominance_ratio", "mask_dominance_floor")
    }
    assert _surface_test._validated_measurement_config({"min_silhouette_pixels": 1.0}) == {
        **defaults,
        "min_silhouette_pixels": 1,
    }


def _probe_context(monkeypatch):
    _source, stage, _wrapper, asset, _cube, _room = _referenced_material_fixture("root")

    async def pin(_ctx, order):
        return order

    async def build(_ctx):
        return None

    async def settle(**_kwargs):
        return None

    async def capture(**_kwargs):
        return "control.png"

    monkeypatch.setattr(_surface_test._context, "pin", pin)
    monkeypatch.setattr(_surface_test._scene, "build_scene", build)
    monkeypatch.setattr(_surface_test._pixels, "dominant_mask", lambda *_args: np.ones((2, 2), dtype=bool))
    return SimpleNamespace(
        scene=SimpleNamespace(stage=stage, asset=SimpleNamespace(prim_path=str(asset.GetPath()))),
        config={"mask_dominance_ratio": 1.5, "mask_dominance_floor": 0.2},
        settle=settle,
        capture_frame=capture,
    )


@pytest.mark.parametrize("purpose", ["", "full", "preview"])
def test_rejected_required_probe_binding_retains_its_material_purpose(monkeypatch, purpose):
    from pxr import UsdShade

    _source, stage, wrapper, _asset, _cube, _room = _referenced_material_fixture("root")
    calls = []

    def bind(_material, **kwargs):
        calls.append(kwargs["materialPurpose"])
        return kwargs["materialPurpose"] != purpose

    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "Apply", lambda *_: SimpleNamespace(Bind=bind))
    with pytest.raises(RuntimeError, match="binding was rejected.*" + (purpose or "allPurpose")):
        _surface_test.paint(stage, str(wrapper.GetPath()))
    assert calls[-1] == purpose


def test_required_probe_bind_exception_preserves_original_cause(monkeypatch):
    from pxr import UsdShade

    _source, stage, wrapper, _asset, _cube, _room = _referenced_material_fixture("root")
    original = OSError("USD control binding failed")

    def bind(*_args, **_kwargs):
        raise original

    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "Apply", lambda *_: SimpleNamespace(Bind=bind))
    with pytest.raises(RuntimeError, match="Required surface probe binding failed") as raised:
        _surface_test.paint(stage, str(wrapper.GetPath()))
    assert raised.value.__cause__ is original


@pytest.mark.asyncio
async def test_render_pass_rejected_control_is_incomplete_not_missing_asset_coverage(monkeypatch):
    from pxr import UsdShade

    ctx = _probe_context(monkeypatch)
    monkeypatch.setattr(_surface_test, "paint", lambda *_args, **_kwargs: False)
    with pytest.raises(RuntimeError, match="binding was not established"):
        await _surface_test._render_pass(
            ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mask", [None, np.ones(3, dtype=bool), np.ones((0, 3), dtype=bool), np.ones((2, 2))])
async def test_render_pass_unavailable_or_invalid_mask_is_incomplete(monkeypatch, mask):
    from pxr import UsdShade

    ctx = _probe_context(monkeypatch)
    monkeypatch.setattr(_surface_test._pixels, "dominant_mask", lambda *_args: mask)
    with pytest.raises(RuntimeError, match="Required.*probe mask"):
        await _surface_test._render_pass(
            ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False
        )


@pytest.mark.asyncio
async def test_probe_cleanup_failure_cannot_replace_missing_mask_error(monkeypatch):
    from pxr import UsdShade

    ctx = _probe_context(monkeypatch)
    monkeypatch.setattr(_surface_test._pixels, "dominant_mask", lambda *_args: None)

    def cleanup(*_args):
        raise OSError("cleanup also unavailable")

    monkeypatch.setattr(_surface_test, "clear", cleanup)
    with pytest.raises(RuntimeError, match="probe mask is unavailable") as raised:
        await _surface_test._render_pass(
            ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False
        )
    assert any("cleanup also unavailable" in note for note in raised.value.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["", "full", "preview"])
@pytest.mark.parametrize("mask_available", [True, False])
async def test_rejected_probe_cleanup_retains_any_original_measurement_error(monkeypatch, purpose, mask_available):
    from pxr import UsdShade

    ctx = _probe_context(monkeypatch)
    if not mask_available:
        monkeypatch.setattr(_surface_test._pixels, "dominant_mask", lambda *_args: None)
    native_unbind = UsdShade.MaterialBindingAPI.UnbindDirectBinding

    def unbind(api, materialPurpose):
        return False if materialPurpose == purpose else native_unbind(api, materialPurpose=materialPurpose)

    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "UnbindDirectBinding", unbind)
    expected = "Required surface probe cleanup failed" if mask_available else "probe mask is unavailable"
    with pytest.raises(RuntimeError, match=expected) as raised:
        await _surface_test._render_pass(
            ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False
        )
    detail = str(raised.value.__cause__) if mask_available else "\n".join(raised.value.__notes__)
    assert "cleanup was rejected" in detail
    assert (purpose or "allPurpose") in detail


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_stage", [0, 1, 2])
@pytest.mark.parametrize("bad_mask", [None, np.ones((2, 3), dtype=bool)])
async def test_coverage_runner_does_not_turn_unmeasured_masks_into_asset_fail(monkeypatch, bad_stage, bad_mask):
    masks = [np.ones((2, 2), dtype=bool) for _ in range(3)]
    # The strong silhouette establishes image dimensions. A different valid
    # strong shape is not itself wrong; later weak shapes must match it.
    masks[bad_stage] = bad_mask
    renders, failed, restored = [], [], []

    async def render(_ctx, order, _label, _strength, **_kwargs):
        index = len(renders)
        renders.append(index)
        return {"mask": masks[index], "effective": order, "stage": object(), "root": "/Asset"}

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *_: restored.append(True))
    monkeypatch.setattr(_surface_test._scene, "report_surface_inventory", lambda *_: {})
    ctx = SimpleNamespace(
        config={"min_material_coverage": 1.0, "min_silhouette_pixels": 1},
        step=lambda *_: None,
        log=lambda *_: None,
        fail=failed.append,
        add_metric=lambda *_: None,
    )
    with pytest.raises(RuntimeError, match="Required.*probe mask"):
        await _surface_test.run_coverage_test(ctx, "", "VM.TEST", "Check source bindings")
    assert failed == []
    assert restored == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", ["pin", "root"])
async def test_coverage_setup_checks_do_not_claim_an_asset_failure(monkeypatch, error):
    failed, restored = [], []

    async def render(*_args, **_kwargs):
        return {"error": error, "effective": ["mdl"]}

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *_: restored.append(True))
    ctx = SimpleNamespace(
        config={"min_material_coverage": 1.0, "min_silhouette_pixels": 1},
        step=lambda *_: None,
        fail=failed.append,
    )
    with pytest.raises(RuntimeError):
        await _surface_test.run_coverage_test(ctx, "", "VM.TEST", "Check source bindings")
    assert failed == []
    assert restored == [True]


@pytest.mark.asyncio
async def test_insufficient_silhouette_is_a_required_measurement_error_not_an_asset_failure(monkeypatch):
    failed = []
    rendered = []

    async def render(_ctx, order, *_args, **_kwargs):
        rendered.append(order)
        return {"mask": np.zeros((2, 2), dtype=bool), "effective": order, "stage": object(), "root": "/Asset"}

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *_: None)
    monkeypatch.setattr(_surface_test._scene, "report_surface_inventory", lambda *_: {})
    ctx = SimpleNamespace(
        config={"min_material_coverage": 1.0, "min_silhouette_pixels": 1},
        step=lambda *_: None,
        fail=failed.append,
        add_metric=lambda *_: None,
    )
    with pytest.raises(RuntimeError, match="below the 1 needed to measure anything"):
        await _surface_test.run_coverage_test(ctx, "", "VM.TEST", "Check source bindings")
    assert failed == [] and rendered == [[""]]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["required_probe", "cancelled", "keyboard_interrupt", "system_exit"])
async def test_context_restoration_cannot_replace_original_error_or_cancellation(monkeypatch, kind):
    import asyncio

    original = {
        "required_probe": RuntimeError("required probe unavailable"),
        "cancelled": asyncio.CancelledError(),
        "keyboard_interrupt": KeyboardInterrupt(),
        "system_exit": SystemExit(2),
    }[kind]

    async def render(*_args, **_kwargs):
        raise original

    def restore(*_args):
        raise OSError("context restore also unavailable")

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", restore)
    ctx = SimpleNamespace(config={"min_material_coverage": 1.0}, step=lambda *_: None)
    with pytest.raises(type(original)) as raised:
        await _surface_test.run_coverage_test(ctx, "", "VM.TEST", "Check bindings")
    assert raised.value is original
    assert any("context restore also unavailable" in note for note in original.__notes__)


@pytest.mark.asyncio
async def test_context_restoration_alone_is_an_execution_error_after_measured_coverage(monkeypatch):
    masks = iter([np.ones((2, 2), dtype=bool), np.zeros((2, 2), dtype=bool), np.zeros((2, 2), dtype=bool)])
    metrics, failed = {}, []
    original = OSError("restore write rejected")

    async def render(_ctx, order, *_args, **_kwargs):
        return {"mask": next(masks), "effective": order, "stage": object(), "root": "/Asset"}

    def restore(*_args):
        raise original

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", restore)
    monkeypatch.setattr(_surface_test._scene, "report_surface_inventory", lambda *_: {})
    ctx = SimpleNamespace(
        config={"min_material_coverage": 1.0, "min_silhouette_pixels": 1},
        step=lambda *_: None,
        log=lambda *_: None,
        fail=failed.append,
        add_metric=lambda key, value: metrics.update({key: value}),
    )
    with pytest.raises(RuntimeError, match="Required surface render-context restoration failed") as raised:
        await _surface_test.run_coverage_test(ctx, "", "VM.TEST", "Check bindings")
    assert raised.value.__cause__ is original
    assert metrics["universal_surface_coverage"] == 1.0
    assert failed == []


def test_no_scoped_materialx_errors_does_not_claim_complete_shader_evaluation(monkeypatch):
    messages, metrics = [], {}
    monkeypatch.setattr(_surface_test._logs, "validation_enabled", lambda: True)
    monkeypatch.setattr(_surface_test._logs, "unresolved_materials", lambda _root: [])
    ctx = SimpleNamespace(log=messages.append, add_metric=lambda key, value: metrics.update({key: value}))
    assert _surface_test._report_materialx(ctx, "/Asset", "mtlx", "OpenPBR") is True
    assert metrics["mtlx_surface_materialx_unresolved"] == 0
    assert any("No scoped MaterialX document-build errors were captured" in message for message in messages)
    assert any("not proof that all materials evaluated" in message for message in messages)
    assert all("Kit built a MaterialX document for every material" not in message for message in messages)


@pytest.mark.parametrize("color", [_surface_test.PROBE_COLOR, _surface_test.SECOND_PROBE_COLOR])
def test_control_color_is_authored_for_every_supported_render_context(color):
    stage = Usd.Stage.CreateInMemory()
    _surface_test.build_probe(stage, color)
    for suffix, input_name in (("Preview", "diffuseColor"), ("Mdl", "diffuse_color_constant"), ("Mtlx", "base_color")):
        shader = stage.GetPrimAtPath(_surface_test.PROBE_SCOPE + "/Flat/" + suffix)
        assert tuple(shader.GetAttribute("inputs:" + input_name).Get()) == color


def _referenced_material_fixture(binding, purpose=""):
    from pxr import UsdShade

    source = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(source, "/Source").GetPrim()
    cube = UsdGeom.Cube.Define(source, "/Source/cube").GetPrim()
    material = UsdShade.Material.Define(source, "/Source/Looks/Original")
    if binding != "none":
        UsdShade.MaterialBindingAPI.Apply(root if binding == "root" else cube).Bind(material, materialPurpose=purpose)
    stage = Usd.Stage.CreateInMemory()
    wrapper = UsdGeom.Xform.Define(stage, _scene.PROBE_ASSET_PARENT).GetPrim()
    asset = stage.DefinePrim(str(wrapper.GetPath()) + "/Asset")
    asset.GetReferences().AddReference(source.GetRootLayer().identifier, "/Source")
    room = UsdGeom.Cube.Define(stage, "/World/Room").GetPrim()
    room_material = UsdShade.Material.Define(stage, "/World/RoomMaterial")
    UsdShade.MaterialBindingAPI.Apply(room).Bind(room_material)
    return source, stage, wrapper, asset, stage.GetPrimAtPath(str(asset.GetPath()) + "/cube"), room


@pytest.mark.parametrize("binding", ["root", "descendant", "none"])
@pytest.mark.parametrize("purpose", ["", "full", "preview"])
def test_inherited_controls_preserve_authored_materials_and_leave_room_untouched(binding, purpose):
    from pxr import UsdShade

    source, stage, wrapper, asset, cube, room = _referenced_material_fixture(binding, purpose)
    source_before = source.GetRootLayer().ExportToString()
    scene_before = stage.GetRootLayer().ExportToString()
    original, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial(materialPurpose=purpose)
    expected = original.GetPath() if original else None
    stage.SetEditTarget(stage.GetSessionLayer())
    for strength, color in (
        (UsdShade.Tokens.strongerThanDescendants, _surface_test.PROBE_COLOR),
        (UsdShade.Tokens.weakerThanDescendants, _surface_test.PROBE_COLOR),
        (UsdShade.Tokens.weakerThanDescendants, _surface_test.SECOND_PROBE_COLOR),
    ):
        assert _surface_test.paint(stage, str(wrapper.GetPath()), strength, color)
        resolved, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial(materialPurpose=purpose)
        if strength == UsdShade.Tokens.strongerThanDescendants or expected is None:
            assert str(resolved.GetPath()).startswith(_surface_test.PROBE_SCOPE)
        else:
            assert resolved.GetPath() == expected
        room_binding, _ = UsdShade.MaterialBindingAPI(room).ComputeBoundMaterial()
        assert str(room_binding.GetPath()) == "/World/RoomMaterial"
        _surface_test.clear(stage, str(wrapper.GetPath()))
        restored, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial(materialPurpose=purpose)
        assert (restored.GetPath() if restored else None) == expected
        assert source.GetRootLayer().ExportToString() == source_before
        assert stage.GetRootLayer().ExportToString() == scene_before
    assert not stage.GetSessionLayer().GetPropertyAtPath(asset.GetPath().AppendProperty("material:binding"))


def test_actual_scene_handle_loads_source_below_the_owned_probe_wrapper(tmp_path):
    from pxr import UsdShade
    from simready.evaluate_engine_kit.scene_handle import KitSceneHandle

    source, _fixture, _wrapper, _asset, _cube, _room = _referenced_material_fixture("root")
    source_root = source.GetPrimAtPath("/Source")
    source.SetDefaultPrim(source_root)
    UsdGeom.Xformable(source_root).AddTranslateOp().Set(Gf.Vec3d(2, 3, 4))
    source_path = tmp_path / "asset.usda"
    source.Export(str(source_path))
    unchanged = source_path.read_bytes()
    stage = Usd.Stage.CreateInMemory()
    scene = KitSceneHandle(stage)
    handle = scene.load_asset(str(source_path), parent_xform=_scene.PROBE_ASSET_PARENT)
    assert handle.prim_path == _scene.PROBE_ASSET_PARENT + "/Asset"
    loaded = stage.GetPrimAtPath(handle.prim_path)
    assert list(loaded.GetParent().GetChildren()) == [loaded]
    cube = stage.GetPrimAtPath(handle.prim_path + "/cube")
    assert UsdGeom.XformCache().GetLocalToWorldTransform(cube).ExtractTranslation() == Gf.Vec3d(2, 3, 4)
    expected, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial()
    assert str(expected.GetPath()) == handle.prim_path + "/Looks/Original"
    assert _surface_test.paint(stage, _scene.PROBE_ASSET_PARENT, UsdShade.Tokens.weakerThanDescendants)
    resolved, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial()
    assert resolved.GetPath() == expected.GetPath()
    _surface_test.clear(stage, _scene.PROBE_ASSET_PARENT)
    assert source_path.read_bytes() == unchanged


@pytest.mark.asyncio
async def test_render_pass_uses_the_fixture_ancestor_not_the_source_binding_site(monkeypatch):
    from pxr import UsdShade

    _source, stage, _wrapper, asset, cube, _room = _referenced_material_fixture("root")
    expected, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial()
    frames = []

    async def pin(_ctx, order):
        return order

    async def build(_ctx):
        return None

    async def settle(**_kwargs):
        return None

    async def capture(**_kwargs):
        actual, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial()
        frames.append(actual.GetPath())
        return "control.png"

    monkeypatch.setattr(_surface_test._context, "pin", pin)
    monkeypatch.setattr(_surface_test._scene, "build_scene", build)
    monkeypatch.setattr(_surface_test._pixels, "dominant_mask", lambda *_args: np.ones((2, 2), dtype=bool))
    ctx = SimpleNamespace(
        scene=SimpleNamespace(stage=stage, asset=SimpleNamespace(prim_path=str(asset.GetPath()))),
        config={"mask_dominance_ratio": 1.5, "mask_dominance_floor": 0.2},
        settle=settle,
        capture_frame=capture,
    )
    result = await _surface_test._render_pass(
        ctx, [""], "weak", UsdShade.Tokens.weakerThanDescendants, capture_reported=False
    )
    assert not result.get("error")
    assert frames == [expected.GetPath()]
    assert result["root"] == str(asset.GetPath())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strength", "color", "channels"),
    [
        ("strongerThanDescendants", _surface_test.PROBE_COLOR, _surface_test.MAGENTA_CHANNELS),
        ("weakerThanDescendants", _surface_test.PROBE_COLOR, _surface_test.MAGENTA_CHANNELS),
        ("weakerThanDescendants", _surface_test.SECOND_PROBE_COLOR, _surface_test.SECOND_PROBE_CHANNELS),
    ],
)
async def test_every_render_pass_requires_deinstancing_before_any_capture(monkeypatch, strength, color, channels):
    ctx = _probe_context(monkeypatch)
    calls = []
    monkeypatch.setattr(_surface_test, "deinstance", lambda *_: calls.append("deinstance") or 0)
    monkeypatch.setattr(_surface_test, "instances_under", lambda *_: 1)

    async def no_capture(*_args, **_kwargs):
        pytest.fail("An unqualified stage must not supply appearance or control evidence")

    monkeypatch.setattr(_surface_test, "_settled_frame", no_capture)
    ctx.capture_frame = no_capture
    with pytest.raises(RuntimeError, match="still has 1 instance"):
        await _surface_test._render_pass(ctx, [""], "probe", strength, probe_color=color, probe_channels=channels)
    assert calls == ["deinstance"]


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["", "full", "preview"])
async def test_all_control_passes_accept_effective_strong_descendants_and_preserve_source(monkeypatch, purpose):
    from pxr import UsdShade

    ctx = _probe_context(monkeypatch)
    stage = ctx.scene.stage
    root = ctx.scene.asset.prim_path
    cube = stage.GetPrimAtPath(root + "/cube")
    own = UsdShade.Material(stage.GetPrimAtPath(root + "/Looks/Original"))
    UsdShade.MaterialBindingAPI.Apply(cube).Bind(
        own, bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose=purpose
    )
    before = stage.GetRootLayer().ExportToString()
    stage.SetEditTarget(stage.GetSessionLayer())
    observed = []

    async def capture(**_kwargs):
        resolved, _ = UsdShade.MaterialBindingAPI(cube).ComputeBoundMaterial(materialPurpose=purpose)
        observed.append(str(resolved.GetPath()))
        return "control.png"

    ctx.capture_frame = capture
    for strength, color, channels in (
        (UsdShade.Tokens.strongerThanDescendants, _surface_test.PROBE_COLOR, _surface_test.MAGENTA_CHANNELS),
        (UsdShade.Tokens.weakerThanDescendants, _surface_test.PROBE_COLOR, _surface_test.MAGENTA_CHANNELS),
        (UsdShade.Tokens.weakerThanDescendants, _surface_test.SECOND_PROBE_COLOR, _surface_test.SECOND_PROBE_CHANNELS),
    ):
        await _surface_test._render_pass(
            ctx, [""], "probe", strength, capture_reported=False, probe_color=color, probe_channels=channels
        )
    assert observed == [_surface_test.PROBE_SCOPE + "/Flat", str(own.GetPath()), str(own.GetPath())]
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["", "full", "preview"])
async def test_unresolved_strong_probe_is_error_and_owned_bindings_are_cleaned(monkeypatch, purpose):
    from pxr import UsdShade
    from simready.evaluate_engine_kit.execution import _result_status_and_message

    definition = _registered_surface_definition(monkeypatch, "preview_surface_renders")
    official = _official_surface_context(definition, {})
    ctx = _probe_context(monkeypatch)
    stage = ctx.scene.stage
    wrapper = stage.GetPrimAtPath(_scene.PROBE_ASSET_PARENT)
    before = stage.GetRootLayer().ExportToString()
    stage.SetEditTarget(stage.GetSessionLayer())
    native_paint = _surface_test.paint

    def acknowledged_but_overridden(*args, **kwargs):
        assert native_paint(*args, **kwargs)
        own = UsdShade.Material(stage.GetPrimAtPath(ctx.scene.asset.prim_path + "/Looks/Original"))
        assert UsdShade.MaterialBindingAPI(wrapper).Bind(own, materialPurpose=purpose)
        return True

    monkeypatch.setattr(_surface_test, "paint", acknowledged_but_overridden)
    with pytest.raises(RuntimeError, match="strong surface probe does not resolve") as raised:
        await _surface_test._render_pass(
            ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False
        )
    status, message = _result_status_and_message(official, test_exception=raised.value)
    assert status == "error" and "silhouette measurement is unqualified" in message
    for material_purpose in ("", "full", "preview"):
        assert not UsdShade.MaterialBindingAPI(wrapper).GetDirectBindingRel(material_purpose).GetTargets()
    assert stage.GetRootLayer().ExportToString() == before


def test_semantics_inside_instance_are_stripped_only_in_session_layer():
    stage = Usd.Stage.CreateInMemory()
    proto = UsdGeom.Xform.Define(stage, "/Prototype")
    cube = UsdGeom.Cube.Define(stage, "/Prototype/cube").GetPrim()
    cube.AddAppliedSchema("SemanticsLabelsAPI:class")
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    instance = UsdGeom.Xform.Define(stage, "/Asset/instance").GetPrim()
    instance.GetReferences().AddInternalReference(proto.GetPath())
    instance.SetInstanceable(True)
    original = stage.GetRootLayer().ExportToString()
    assert stage.GetPrimAtPath("/Asset/instance/cube").IsInstanceProxy()
    assert _seg_common.strip_semantics(stage, asset) == 1
    assert not stage.GetPrimAtPath("/Asset/instance/cube").IsInstanceProxy()
    assert "SemanticsLabelsAPI:class" not in stage.GetPrimAtPath("/Asset/instance/cube").GetAppliedSchemas()
    assert "SemanticsLabelsAPI:class" in cube.GetAppliedSchemas()
    assert stage.GetRootLayer().ExportToString() == original


def test_unlabelled_instance_is_not_deinstanced_to_manufacture_evidence():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Cube.Define(stage, "/Prototype/cube")
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    instance = UsdGeom.Xform.Define(stage, "/Asset/instance").GetPrim()
    instance.GetReferences().AddInternalReference("/Prototype")
    instance.SetInstanceable(True)
    assert _seg_common.strip_semantics(stage, asset) == 0
    assert instance.IsInstance()
    assert stage.GetSessionLayer().empty


def test_nested_labelled_instances_are_recollected_after_each_composition_change():
    stage = Usd.Stage.CreateInMemory()
    cube = UsdGeom.Cube.Define(stage, "/Inner/cube").GetPrim()
    cube.AddAppliedSchema("SemanticsLabelsAPI:class")
    nested = UsdGeom.Xform.Define(stage, "/Outer/nested").GetPrim()
    nested.GetReferences().AddInternalReference("/Inner")
    nested.SetInstanceable(True)
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    asset.GetReferences().AddInternalReference("/Outer")
    asset.SetInstanceable(True)
    original = stage.GetRootLayer().ExportToString()
    assert stage.GetPrimAtPath("/Asset/nested/cube").IsInstanceProxy()
    assert _seg_common.strip_semantics(stage, asset) == 1
    assert not stage.GetPrimAtPath("/Asset/nested/cube").IsInstanceProxy()
    assert "SemanticsLabelsAPI:class" not in stage.GetPrimAtPath("/Asset/nested/cube").GetAppliedSchemas()
    assert "SemanticsLabelsAPI:class" in cube.GetAppliedSchemas()
    assert stage.GetRootLayer().ExportToString() == original


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first_weak", "second_weak", "coverage"),
    [
        (True, False, 1.0),  # Authored magenta: matches magenta, does not follow cyan.
        (False, True, 1.0),  # Authored cyan: matches cyan, does not follow magenta.
        (True, True, 0.0),  # Uncovered: follows both probe colors.
    ],
)
async def test_material_color_alone_does_not_establish_uncovered_surface(
    monkeypatch, first_weak, second_weak, coverage
):
    masks = iter([np.ones((2, 2), dtype=bool), np.full((2, 2), first_weak), np.full((2, 2), second_weak)])
    calls, metrics, failed = [], {}, []

    async def render(_ctx, order, _label, _strength, **kwargs):
        calls.append(kwargs)
        return {"mask": next(masks), "effective": order, "stage": object(), "root": "/Asset"}

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *_: None)
    monkeypatch.setattr(_surface_test._scene, "report_surface_inventory", lambda *_: {"/Asset/Material": [""]})
    ctx = SimpleNamespace(
        config={"min_material_coverage": 1.0, "min_silhouette_pixels": 1},
        step=lambda *_: None,
        log=lambda *_: None,
        fail=failed.append,
        add_metric=lambda name, value: metrics.update({name: value}),
    )
    await _surface_test.run_coverage_test(ctx, "", "VM.TEST", "Inspect original binding")
    assert len(calls) == 3
    assert calls[-1]["probe_color"] == (0.0, 1.0, 1.0)
    assert metrics["universal_surface_coverage"] == pytest.approx(coverage)
    assert bool(failed) == (coverage < 1.0)

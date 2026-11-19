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
"""FET010 controls preserve source materials and distinguish missing observations."""

import asyncio
import importlib
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from pxr import Sdf, Usd, UsdGeom, UsdShade
from simready.evaluate.core import decorator
from simready.evaluate.runner.test_context import RunContext
from simready.evaluate_engine_kit.execution import (
    _merge_config,
    _result_status_and_message,
)
from simready.foundation.tier_core.runtime_tests.fet006_materials import _surface_test
from simready.foundation.tier_core.runtime_tests.fet010_standard import (
    _probe,
)
from simready.foundation.tier_core.runtime_tests.fet010_standard import (
    display_color_response as response,
)

_PIXEL_READBACK = {
    name: getattr(response._pixels, name)
    for name in ("dominant_mask", "changed_pixels", "changed_pixels_in", "frame_summary")
}


def _usd_fixture():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, _probe.PROBE_ASSET_PARENT)
    root_path = _probe.PROBE_ASSET_PARENT + "/Asset"
    root = UsdGeom.Xform.Define(stage, root_path).GetPrim()
    cube = UsdGeom.Cube.Define(stage, root_path + "/mesh").GetPrim()
    UsdGeom.PrimvarsAPI(cube).CreatePrimvar("displayColor", Sdf.ValueTypeNames.Color3fArray, "constant").Set(
        [(0.2, 0.4, 0.8)]
    )
    source = UsdShade.Material.Define(stage, "/Looks/Source")
    api = UsdShade.MaterialBindingAPI.Apply(root)
    api.Bind(source)
    for purpose in ("full", "preview"):
        UsdShade.MaterialBindingAPI.Apply(cube).Bind(source, materialPurpose=purpose)
    room = UsdGeom.Cube.Define(stage, "/World/room").GetPrim()
    UsdShade.MaterialBindingAPI.Apply(room).Bind(source, materialPurpose="full")
    return stage, root, cube, room


def _nested_usd_fixture():
    """Referenced meshes/subsets inside two instance levels, with inherited color."""
    part = Usd.Stage.CreateInMemory()
    part_root = UsdGeom.Xform.Define(part, "/Part").GetPrim()
    part.SetDefaultPrim(part_root)
    colors = UsdGeom.Scope.Define(part, "/Part/Colors").GetPrim()
    UsdGeom.PrimvarsAPI(colors).CreatePrimvar("displayColor", Sdf.ValueTypeNames.Color3fArray, "constant").Set(
        [(0.2, 0.4, 0.8)]
    )
    mesh = UsdGeom.Mesh.Define(part, "/Part/Colors/mesh")
    mesh.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)])
    mesh.CreateFaceVertexCountsAttr([3, 3])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 0, 2, 3])
    material = UsdShade.Material.Define(part, "/Part/Looks/Source")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material, materialPurpose="preview")
    subset = UsdGeom.Subset.CreateGeomSubset(
        mesh, "faces", UsdGeom.Tokens.face, [0, 1], "materialBind", UsdGeom.Tokens.partition
    )
    api = UsdShade.MaterialBindingAPI.Apply(subset.GetPrim())
    for purpose in ("", "full", "preview"):
        api.Bind(material, materialPurpose=purpose)

    assembly = Usd.Stage.CreateInMemory()
    assembly_root = UsdGeom.Xform.Define(assembly, "/Assembly").GetPrim()
    assembly.SetDefaultPrim(assembly_root)
    inner = assembly.DefinePrim("/Assembly/Inner")
    inner.GetReferences().AddReference(part.GetRootLayer().identifier)
    inner.SetInstanceable(True)

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, _probe.PROBE_ASSET_PARENT)
    root_path = _probe.PROBE_ASSET_PARENT + "/Asset"
    root = stage.DefinePrim(root_path)
    root.GetReferences().AddReference(assembly.GetRootLayer().identifier)
    root.SetInstanceable(True)
    return stage, root_path, (part.GetRootLayer(), assembly.GetRootLayer())


def test_strong_controls_cover_all_purposes_and_cleanup_preserves_source_opinions():
    stage, root, cube, room = _usd_fixture()
    original = {
        str(prim.GetPath()): str(
            UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=purpose)[0].GetPath()
        )
        for prim, purpose in ((root, ""), (cube, "full"), (cube, "preview"), (room, "full"))
    }
    root_binding = list(root.GetRelationship("material:binding").GetTargets())
    cube_full = list(cube.GetRelationship("material:binding:full").GetTargets())
    probes = _probe.build(stage)
    for name in (_probe.READ, _probe.READ_CONTROL, _probe.REMOVED, _probe.OPACITY):
        _probe.bind(stage, _probe.PROBE_ASSET_PARENT, probes[name])
        assert all(_probe.bound_probe(cube, purpose) == name for purpose in ("", "full", "preview"))
    assert list(root.GetRelationship("material:binding").GetTargets()) == root_binding
    assert list(cube.GetRelationship("material:binding:full").GetTargets()) == cube_full
    _probe.unbind(stage, _probe.PROBE_ASSET_PARENT)
    after = {
        str(prim.GetPath()): str(
            UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=purpose)[0].GetPath()
        )
        for prim, purpose in ((root, ""), (cube, "full"), (cube, "preview"), (room, "full"))
    }
    assert after == original


@pytest.fixture
def official_context(monkeypatch):
    monkeypatch.setattr(decorator, "_REGISTRY", [])
    importlib.reload(response)
    definition = decorator.get_registered_tests()[-1]
    stage, root, cube, _room = _usd_fixture()

    def noop(*args, **kwargs):
        return None

    room = SimpleNamespace(auto_size=noop, set_color=noop, hide_ground=noop)
    scene = SimpleNamespace(
        stage=stage,
        asset=SimpleNamespace(prim_path=str(root.GetPath())),
        load_asset=lambda *args, **kwargs: (
            None if kwargs.get("parent_xform") == _probe.PROBE_ASSET_PARENT else pytest.fail("missing owned parent")
        ),
        add_room=lambda: room,
        lighting=SimpleNamespace(add_dome=noop),
        auto_frame_camera=noop,
        hide_asset=noop,
        show_asset=noop,
    )
    ctx = RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir="unused-output",
        test_name=definition.name,
        test_version=definition.version,
        feature_id=definition.features[0].id,
        engine_name="kit",
        engine_version="6.1.0",
        session_id="display-probe-regression",
        scene=scene,
        config=_merge_config(definition.config_defaults, {"min_silhouette_pixels": 1}),
    )

    async def step(*args, **kwargs):
        return None

    async def capture(*args, **kwargs):
        return kwargs["label"]

    monkeypatch.setattr(ctx, "set_settle_frames", noop)
    monkeypatch.setattr(ctx, "settle", step)
    monkeypatch.setattr(ctx, "capture_frame", capture)
    monkeypatch.setattr(ctx, "encode_video", noop)
    monkeypatch.setattr(response._context, "read_order", lambda: ["mtlx"])

    async def pin(_ctx, order):
        return list(order)

    monkeypatch.setattr(response._context, "pin", pin)
    monkeypatch.setattr(response._context, "restore", noop)
    monkeypatch.setattr(response._pixels, "dominant_mask", lambda *args: np.ones((2, 2), dtype=bool))
    monkeypatch.setattr(response._pixels, "changed_pixels", lambda *args: 4)
    monkeypatch.setattr(response._pixels, "frame_summary", lambda *args: (0.2, 0.4, 0.8))

    def changed(first, second, *args):
        if first == "display_color_read" and second == "display_color_read_control":
            return 0
        return 4

    monkeypatch.setattr(response._pixels, "changed_pixels_in", changed)
    return definition, ctx, stage, root, cube


@pytest.fixture
def nested_context(official_context, monkeypatch):
    definition, ctx, _stage, _root, _cube = official_context
    stage, root_path, sources = _nested_usd_fixture()
    ctx.scene.stage = stage
    ctx.scene.asset.prim_path = root_path
    snapshots = [layer.ExportToString() for layer in sources]
    root_spec = stage.GetRootLayer().GetPrimAtPath(root_path).GetAsText()
    restored = []
    monkeypatch.setattr(response._context, "restore", lambda _ctx, value: restored.append(value))
    return SimpleNamespace(
        definition=definition,
        ctx=ctx,
        stage=stage,
        root_path=root_path,
        mesh_path=root_path + "/Inner/Colors/mesh",
        sources=sources,
        snapshots=snapshots,
        root_spec=root_spec,
        restored=restored,
    )


def _assert_source_preserved(fixture):
    assert [layer.ExportToString() for layer in fixture.sources] == fixture.snapshots
    assert fixture.stage.GetRootLayer().GetPrimAtPath(fixture.root_path).GetAsText() == fixture.root_spec


@pytest.mark.asyncio
async def test_official_entry_expands_nested_references_in_session_before_inventory(nested_context, monkeypatch):
    fixture = nested_context
    assert _surface_test.instances_under(fixture.stage, fixture.root_path) == 2
    inventory_proxies = []
    renderable = response.surfaces.renderable_geometry

    def inventory(stage, root):
        prims = list(renderable(stage, root))
        inventory_proxies.extend(prim.IsInstanceProxy() for prim in prims)
        return iter(prims)

    monkeypatch.setattr(response.surfaces, "renderable_geometry", inventory)
    await fixture.definition.func(fixture.ctx)
    assert inventory_proxies == [False]
    assert _surface_test.instances_under(fixture.stage, fixture.root_path) == 0
    assert fixture.ctx.metrics["display_color_test_scene_deinstanced_prims"]["value"] == 2
    assert fixture.ctx.metrics["display_color_test_scene_instances_remaining"]["value"] == 0
    assert fixture.ctx.metrics["display_color_renderable_gprims"]["value"] == 1
    assert fixture.ctx.metrics["display_color_gprims_without_displaycolor"]["value"] == 0
    mesh = fixture.stage.GetPrimAtPath(fixture.mesh_path)
    assert tuple(UsdGeom.PrimvarsAPI(mesh).FindPrimvarWithInheritance("displayColor").Get()[0]) == pytest.approx(
        (0.2, 0.4, 0.8)
    )
    for path in (fixture.root_path, fixture.root_path + "/Inner"):
        assert fixture.stage.GetSessionLayer().GetPrimAtPath(path).instanceable is False
    for path in (fixture.mesh_path, fixture.mesh_path + "/faces"):
        prim = fixture.stage.GetPrimAtPath(path)
        assert not prim.IsInstanceProxy()
        assert _probe.bound_probe(prim) is None
    assert fixture.stage.GetEditTarget().GetLayer() == fixture.stage.GetRootLayer()
    assert _result_status_and_message(fixture.ctx, test_exception=None)[0] == "pass"
    assert fixture.restored == [["mtlx"]]
    _assert_source_preserved(fixture)


@pytest.mark.asyncio
async def test_official_entry_primes_both_read_materials_before_measuring_and_video(
    nested_context, monkeypatch, tmp_path
):
    fixture = nested_context
    captures = []
    analysed = []
    videos = []
    expected = [
        ("background", _probe.READ),
        ("warmup_read", _probe.READ),
        ("warmup_read_control", _probe.READ_CONTROL),
        ("read", _probe.READ),
        ("read_control", _probe.READ_CONTROL),
        ("removed", _probe.REMOVED),
        ("opacity", _probe.OPACITY),
    ]
    colors = {
        "background": (0, 0, 0),
        "warmup_read": (255, 0, 255),
        "warmup_read_control": (255, 0, 0),
        "read": (51, 102, 204),
        "read_control": (51, 102, 204),
        "removed": (255, 0, 255),
        "opacity": (0, 0, 0),
    }

    async def capture(*args, label, role="normal", **kwargs):
        short = label.removeprefix("display_color_")
        mesh = fixture.stage.GetPrimAtPath(fixture.mesh_path)
        subset = fixture.stage.GetPrimAtPath(fixture.mesh_path + "/faces")
        captures.append((short, _probe.bound_probe(mesh), role))
        # Real USD resolution on material subsets must follow each probe swap.
        assert all(
            _probe.bound_probe(subset, purpose) == _probe.bound_probe(mesh) for purpose in ("", "full", "preview")
        )
        path = tmp_path / (label + ".png")
        Image.new("RGB", (4, 4), colors[short]).save(path)
        return str(path)

    for name, original in _PIXEL_READBACK.items():

        def readback(*args, _name=name, _original=original, **kwargs):
            analysed.append((_name, args[:2] if _name.startswith("changed") else args[:1]))
            return _original(*args, **kwargs)

        monkeypatch.setattr(response._pixels, name, readback)
    monkeypatch.setattr(fixture.ctx, "capture_frame", capture)
    monkeypatch.setattr(fixture.ctx, "encode_video", lambda frames, **kwargs: videos.append((frames, kwargs)))
    await fixture.definition.func(fixture.ctx)
    assert [(label, material) for label, material, _role in captures] == expected
    assert [label for label, _material, role in captures if role == "summary"] == ["read"]
    assert all("warmup" not in str(paths) for _name, paths in analysed)
    assert videos == [
        (
            [str(tmp_path / ("display_color_" + label + ".png")) for label in ("read", "removed", "opacity")],
            {"fps": 1, "delete_frames": False, "label": "display_color_response", "role": "summary"},
        )
    ]
    assert fixture.ctx.metrics["display_color_probe_warmup_captures"]["value"] == 2
    assert fixture.ctx.metrics["display_color_probe_warmup_sequence"]["value"] == [
        "display_color_warmup_read",
        "display_color_warmup_read_control",
    ]
    assert fixture.ctx.metrics["display_color_control_ratio"]["value"] == 0.0
    assert fixture.ctx.metrics["display_color_response_ratio"]["value"] == 1.0
    assert fixture.ctx.metrics["display_color_opacity_ratio"]["value"] == 1.0
    assert _result_status_and_message(fixture.ctx, test_exception=None)[0] == "pass"
    _assert_source_preserved(fixture)


@pytest.mark.asyncio
async def test_remaining_instances_are_setup_error_before_inventory_or_capture(nested_context, monkeypatch):
    fixture = nested_context
    # Simulate an acknowledged but ineffective helper; inspect the real composed instances afterwards.
    monkeypatch.setattr(_surface_test, "deinstance", lambda *args: 0)
    monkeypatch.setattr(response.surfaces, "renderable_geometry", lambda *args: pytest.fail("unqualified inventory"))
    monkeypatch.setattr(fixture.ctx, "capture_frame", lambda *args, **kwargs: pytest.fail("unqualified capture"))
    with pytest.raises(RuntimeError, match="still has 2 instance") as caught:
        await fixture.definition.func(fixture.ctx)
    assert not fixture.ctx.failed and not fixture.ctx.skipped
    assert _result_status_and_message(fixture.ctx, test_exception=caught.value)[0] == "error"
    assert fixture.ctx.metrics["display_color_test_scene_deinstanced_prims"]["value"] == 0
    assert fixture.ctx.metrics["display_color_test_scene_instances_remaining"]["value"] == 2
    assert fixture.restored == [["mtlx"]]
    _assert_source_preserved(fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize("label", ["display_color_warmup_read", "display_color_warmup_read_control"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_warmup_error_or_cancellation_cleans_probe_and_context(nested_context, monkeypatch, label, error_type):
    fixture = nested_context
    primary = error_type("warmup interrupted")

    async def capture(*args, **kwargs):
        if kwargs["label"] == label:
            raise primary
        return kwargs["label"]

    monkeypatch.setattr(fixture.ctx, "capture_frame", capture)
    with pytest.raises(error_type) as caught:
        await fixture.definition.func(fixture.ctx)
    assert caught.value is primary
    assert not fixture.ctx.failed and not fixture.ctx.skipped
    assert fixture.restored == [["mtlx"]]
    assert _probe.bound_probe(fixture.stage.GetPrimAtPath(fixture.mesh_path + "/faces")) is None
    _assert_source_preserved(fixture)


@pytest.mark.asyncio
async def test_official_entry_restores_authored_binding_after_measured_success(official_context):
    definition, ctx, stage, root, cube = official_context
    await definition.func(ctx)
    assert _result_status_and_message(ctx, test_exception=None)[0] == "pass"
    assert _probe.bound_probe(cube) is None
    assert root.GetRelationship("material:binding").GetTargets() == [Sdf.Path("/Looks/Source")]
    assert cube.GetRelationship("material:binding:full").GetTargets() == [Sdf.Path("/Looks/Source")]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [None, "/Missing"])
async def test_missing_loaded_asset_root_is_error_not_inapplicable_skip(official_context, path):
    definition, ctx, _stage, _root, _cube = official_context
    ctx.scene.asset.prim_path = path
    with pytest.raises(RuntimeError, match="asset's stage path could not be determined") as caught:
        await definition.func(ctx)
    assert not ctx.failed and _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"


@pytest.mark.asyncio
@pytest.mark.parametrize("mask", [None, np.ones((2, 2), dtype=np.uint8), np.zeros((0, 2), dtype=bool)])
async def test_missing_or_invalid_required_mask_is_error_not_asset_fail(official_context, monkeypatch, mask):
    definition, ctx, _stage, _root, cube = official_context
    monkeypatch.setattr(response._pixels, "dominant_mask", lambda *args: mask)
    with pytest.raises(RuntimeError, match="Required display-color silhouette") as caught:
        await definition.func(ctx)
    assert not ctx.failed
    assert _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
    assert _probe.bound_probe(cube) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_notes", [True, False])
async def test_cleanup_diagnostic_never_replaces_primary_error(official_context, monkeypatch, missing_notes):
    definition, ctx, _stage, _root, _cube = official_context

    class OriginalError(RuntimeError):
        if missing_notes:
            add_note = None
        else:

            def add_note(self, note):
                raise RuntimeError("note failed")

    async def fail(*args, **kwargs):
        raise OriginalError("primary capture failure")

    monkeypatch.setattr(ctx, "capture_frame", fail)
    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "UnbindDirectBinding", lambda *args, **kwargs: False)
    with pytest.raises(OriginalError, match="primary capture failure"):
        await definition.func(ctx)


@pytest.mark.asyncio
async def test_too_small_required_silhouette_is_incomplete_not_asset_failure(official_context, monkeypatch):
    definition, ctx, _stage, _root, cube = official_context
    monkeypatch.setattr(response._pixels, "dominant_mask", lambda *args: np.zeros((2, 2), dtype=bool))
    with pytest.raises(RuntimeError, match="below the 1 needed to measure anything") as caught:
        await definition.func(ctx)
    assert not ctx.failed and _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
    assert _probe.bound_probe(cube) is None


@pytest.mark.asyncio
async def test_unqualified_control_preserves_evidence_and_requires_fixture_investigation(official_context, monkeypatch):
    definition, ctx, _stage, _root, cube = official_context
    monkeypatch.setattr(response._pixels, "changed_pixels_in", lambda *args: 4)
    with pytest.raises(RuntimeError) as caught:
        await definition.func(ctx)
    assert not ctx.failed and not ctx.skipped
    assert _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
    assert ctx.metrics["display_color_silhouette_pixels"]["value"] == 4
    assert ctx.metrics["display_color_control_ratio"]["value"] == 1.0
    assert ctx.metrics["display_color_response_ratio"]["value"] == 1.0
    assert ctx.metrics["display_color_opacity_ratio"]["value"] == 1.0
    message = str(caught.value).lower()
    assert "unqualified" in message
    assert "100.00%" in message and "4 silhouette pixels" in message and "2%" in message
    assert all(
        topic in message
        for topic in ("read", "readcontrol", "provider", "version", "warmup", "native captures", "renderer", "settling")
    )
    assert "does not establish its cause" in message and "not a proven cure" in message
    assert "do not select favorable frames or adjust thresholds" in message
    assert _probe.bound_probe(cube) is None


@pytest.mark.asyncio
async def test_incompatible_required_images_are_error_with_source_binding_preserved(official_context, monkeypatch):
    definition, ctx, _stage, _root, cube = official_context
    monkeypatch.setattr(response._pixels, "changed_pixels_in", lambda *args: -1)
    with pytest.raises(RuntimeError, match="Required display-color captures"):
        await definition.func(ctx)
    assert not ctx.failed and _probe.bound_probe(cube) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "noise,color,opacity,authored_opacity,expected",
    [
        (100, 60, 0, True, "error"),
        (100, 100, 0, True, "error"),
        (100, 40, 0, True, "error"),
        (50, 50, 0, True, "error"),
        (100, 1000, 60, False, "error"),
        (100, 1000, 40, False, "error"),
        (10, 20, 1000, False, "fail"),
        (0, 0, 1000, False, "fail"),
        (10, 1000, 20, False, "fail"),
        (100, 101, 0, True, "pass"),
        (100, 1000, 101, False, "pass"),
    ],
)
async def test_presence_comparison_requires_signal_qualified_against_swap_noise(
    official_context, monkeypatch, noise, color, opacity, authored_opacity, expected
):
    definition, ctx, _stage, _root, cube = official_context
    if authored_opacity:
        UsdGeom.PrimvarsAPI(cube).CreatePrimvar("displayOpacity", Sdf.ValueTypeNames.FloatArray, "constant").Set([1.0])
    monkeypatch.setattr(response._pixels, "dominant_mask", lambda *args: np.ones((100, 100), dtype=bool))
    counts = {
        "display_color_read_control": noise,
        "display_color_removed": color,
        "display_color_opacity": opacity,
    }
    monkeypatch.setattr(response._pixels, "changed_pixels_in", lambda _first, second, *args: counts[second])
    if expected == "error":
        with pytest.raises(RuntimeError, match="comparison is inconclusive") as caught:
            await definition.func(ctx)
        assert not ctx.failed and not ctx.skipped
        assert _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
    else:
        await definition.func(ctx)
        assert _result_status_and_message(ctx, test_exception=None)[0] == expected
    assert ctx.metrics["display_color_control_ratio"]["value"] == noise / 10000
    assert ctx.metrics["display_color_response_ratio"]["value"] == color / 10000
    assert _probe.bound_probe(cube) is None


@pytest.mark.asyncio
async def test_explicit_zero_presence_floors_retain_zero_noise_policy(official_context, monkeypatch):
    definition, ctx, _stage, _root, cube = official_context
    ctx.config.update(min_response_ratio=0.0, min_opacity_response_ratio=0.0)
    monkeypatch.setattr(response._pixels, "changed_pixels_in", lambda *args: 0)
    await definition.func(ctx)
    assert _result_status_and_message(ctx, test_exception=None)[0] == "pass"
    assert _probe.bound_probe(cube) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("order", [None, [], ["mdl", ""]])
async def test_unresolved_required_context_is_error_before_probe_bind(official_context, monkeypatch, order):
    definition, ctx, _stage, _root, cube = official_context

    async def rejected_pin(_ctx, requested):
        return order

    monkeypatch.setattr(response._context, "pin", rejected_pin)
    with pytest.raises(RuntimeError, match="render-context list"):
        await definition.func(ctx)
    assert not ctx.failed and _probe.bound_probe(cube) is None


@pytest.mark.asyncio
async def test_rejected_binding_preserves_primary_error_when_cleanup_also_fails(official_context, monkeypatch):
    definition, ctx, _stage, _root, _cube = official_context
    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "Bind", lambda *args, **kwargs: False)
    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "UnbindDirectBinding", lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="probe binding was rejected") as caught:
        await definition.func(ctx)
    assert not ctx.failed
    assert any("cleanup also failed" in note for note in caught.value.__notes__)


@pytest.mark.asyncio
async def test_cancelled_capture_keeps_cancellation_after_cleanup_error(official_context, monkeypatch):
    definition, ctx, _stage, _root, _cube = official_context

    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError("capture cancelled")

    monkeypatch.setattr(ctx, "capture_frame", cancel)
    monkeypatch.setattr(UsdShade.MaterialBindingAPI, "UnbindDirectBinding", lambda *args, **kwargs: False)
    with pytest.raises(asyncio.CancelledError, match="capture cancelled") as caught:
        await definition.func(ctx)
    assert any("cleanup also failed" in note for note in caught.value.__notes__)


@pytest.mark.asyncio
async def test_observed_low_response_keeps_existing_behavioural_failure(official_context, monkeypatch):
    definition, ctx, _stage, _root, cube = official_context
    monkeypatch.setattr(response._pixels, "changed_pixels_in", lambda *args: 0)
    await definition.func(ctx)
    assert ctx.failed and _result_status_and_message(ctx, test_exception=None)[0] == "fail"
    assert _probe.bound_probe(cube) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, [], ["mdl"], ["mdl", "mtlx", ""]])
async def test_scoped_context_is_pinned_before_loading_and_restores_incoming_value(
    official_context, monkeypatch, previous
):
    definition, ctx, _stage, _root, cube = official_context
    calls = []
    original_load = ctx.scene.load_asset
    monkeypatch.setattr(response._context, "read_order", lambda: previous)

    async def pin(_ctx, requested):
        calls.append(("pin", list(requested)))
        return list(requested)

    def load(*args, **kwargs):
        calls.append(("load", None))
        return original_load(*args, **kwargs)

    def restore(_ctx, original):
        calls.append(("restore", original))

    monkeypatch.setattr(response._context, "pin", pin)
    monkeypatch.setattr(response._context, "restore", restore)
    monkeypatch.setattr(ctx.scene, "load_asset", load)
    await definition.func(ctx)
    assert calls == [("pin", ["mtlx"]), ("load", None), ("restore", previous)]
    assert _result_status_and_message(ctx, test_exception=None)[0] == "pass"
    assert _probe.bound_probe(cube) is None
    assert ctx.metrics["display_color_render_context_order"]["value"] == "mtlx"


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt])
async def test_interrupted_pin_restores_context_without_loading_or_binding(official_context, monkeypatch, error_type):
    definition, ctx, _stage, _root, cube = official_context
    previous = ["mdl"]
    restored = []
    original = error_type("pin interrupted")
    monkeypatch.setattr(response._context, "read_order", lambda: previous)

    async def pin(*args):
        raise original

    monkeypatch.setattr(response._context, "pin", pin)
    monkeypatch.setattr(response._context, "restore", lambda _ctx, value: restored.append(value))
    monkeypatch.setattr(ctx.scene, "load_asset", lambda *args, **kwargs: pytest.fail("load preceded qualified pin"))
    with pytest.raises(error_type) as caught:
        await definition.func(ctx)
    assert caught.value is original and restored == [previous]
    assert not ctx.failed and _probe.bound_probe(cube) is None
    assert ctx.metrics["display_color_render_context_previous"]["value"] == "mdl"
    assert ctx.metrics["display_color_render_context_requested"]["value"] == "mtlx"
    assert "display_color_render_context_order" not in ctx.metrics


@pytest.mark.parametrize("previous", [None, [], ["mdl"], ["mdl", "mtlx", ""]])
def test_real_context_restore_preserves_explicit_empty_list(previous):
    calls = []
    ctx = SimpleNamespace(override_render_settings=calls.append)
    response._context.restore(ctx, previous)
    expected = response._context.SHIPPED_ORDER if previous is None else previous
    assert calls == [{response._context.RENDER_CONTEXTS_SETTING: expected}]
    assert calls[0][response._context.RENDER_CONTEXTS_SETTING] is not expected


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_type", [None, RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("cleanup_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt])
async def test_context_cleanup_attempted_after_binding_cleanup_failure(
    official_context, monkeypatch, primary_type, cleanup_type
):
    definition, ctx, _stage, _root, _cube = official_context
    primary = primary_type("original measurement error") if primary_type else None
    first = cleanup_type("binding cleanup error")
    calls = []
    retired = []
    ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=retired.append)

    async def measure(_ctx, fixture):
        fixture.update(stage=None, binding_root="/World/Owned", render_context_previous=["mdl"])
        if primary is not None:
            raise primary

    def unbind(*args):
        calls.append("unbind")
        raise first

    def restore(*args):
        calls.append("restore")
        raise RuntimeError("context cleanup error")

    monkeypatch.setattr(response, "_measure_display_color_response", measure)
    monkeypatch.setattr(response._probe, "unbind", unbind)
    monkeypatch.setattr(response._context, "restore", restore)
    with pytest.raises(primary_type if primary_type else cleanup_type) as caught:
        await definition.func(ctx)
    assert calls == ["unbind", "restore"]
    if primary is not None:
        assert caught.value is primary
    elif isinstance(first, Exception):
        assert caught.value.__cause__ is first
    else:
        assert caught.value is first
    assert retired == [
        "Required display-color probe cleanup failed.",
        "Required display-color render-context restoration failed.",
    ]

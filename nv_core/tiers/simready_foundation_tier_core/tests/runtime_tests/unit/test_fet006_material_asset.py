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

"""Host regressions for a material published on its own, rendered on test spheres.

The scene is built with the engine's scene handle on a host stage, and only the
captures are faked. These tests do not qualify native rendering.
"""

import asyncio

import pytest

pytest.importorskip("pxr")

from pxr import Gf, Usd, UsdGeom, UsdShade  # noqa: E402
from simready.foundation.tier_core.runtime_tests.fet006_materials import (  # noqa: E402
    _scene,
    _surface_test,
    surfaces,
)

# One material with a UsdPreviewSurface and an OpenPBR surface, as a library package publishes it.
_MATERIAL = """#usda 1.0
(
    defaultPrim = "Copper"
)

def Material "Copper"
{
    token outputs:surface.connect = </Copper/Preview.outputs:surface>
    token outputs:mtlx:surface.connect = </Copper/OpenPBR.outputs:out>

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.72, 0.45, 0.2)
        token outputs:surface
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color = (0.72, 0.45, 0.2)
        token outputs:out
    }
}
"""

# Two materials under a scope. Copper's network holds a Material of its own, which is not
# published beside it.
_LIBRARY = """#usda 1.0
(
    defaultPrim = "Library"
)

def Scope "Library"
{
    def Material "Copper"
    {
        token outputs:surface.connect = </Library/Copper/Preview.outputs:surface>

        def Shader "Preview"
        {
            uniform token info:id = "UsdPreviewSurface"
            token outputs:surface
        }

        def Material "Inner"
        {
        }
    }

    def Material "Rubber"
    {
        token outputs:mtlx:surface.connect = </Library/Rubber/OpenPBR.outputs:out>

        def Shader "OpenPBR"
        {
            uniform token info:id = "ND_open_pbr_surface_surfaceshader"
            token outputs:out
        }
    }
}
"""

# A prop: a cube bound to its own material.
_PROP = """#usda 1.0
(
    defaultPrim = "Prop"
)

def Xform "Prop"
{
    def Cube "Body" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding = </Prop/Looks/Paint>
    }

    def Scope "Looks"
    {
        def Material "Paint"
        {
            token outputs:surface.connect = </Prop/Looks/Paint/Preview.outputs:surface>

            def Shader "Preview"
            {
                uniform token info:id = "UsdPreviewSurface"
                token outputs:surface
            }
        }
    }
}
"""

_EMPTY = """#usda 1.0
(
    defaultPrim = "Empty"
)

def Xform "Empty"
{
}
"""


class _SceneCtx:
    """What ``build_scene`` asks of the test context, with the engine's own scene handle."""

    def __init__(self, asset_path):
        from simready.evaluate_engine_kit.scene_handle import KitSceneHandle

        self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(self.stage, 1.0)
        self.scene = KitSceneHandle(self.stage)
        self.asset_path = str(asset_path)
        self.config = dict(_scene.SCENE_DEFAULTS)

    def set_settle_frames(self, _count):
        pass

    async def settle(self, count=1):
        pass


def _built(tmp_path, text):
    """Write ``text`` as the asset, build the shared scene around it, and return the context and sphere count."""
    path = tmp_path / "asset.usda"
    path.write_text(text)
    ctx = _SceneCtx(path)
    return ctx, asyncio.run(_scene.build_scene(ctx))


def test_published_materials_lists_each_material_and_not_one_inside_a_network(tmp_path):
    path = tmp_path / "library.usda"
    path.write_text(_LIBRARY)
    stage = Usd.Stage.Open(str(path))

    assert [prim.GetName() for prim in surfaces.published_materials(stage, "/Library")] == ["Copper", "Rubber"]


def test_a_material_asset_gets_one_bound_sphere_per_material(tmp_path):
    ctx, spheres = _built(tmp_path, _LIBRARY)
    stage, root = ctx.stage, _scene.asset_root(ctx)

    assert spheres == 2
    wrapper = stage.GetPrimAtPath(_scene.PROBE_ASSET_PARENT)
    assert [prim.GetPath() for prim in wrapper.GetChildren()] == [root, _scene.TEST_SPHERES]
    assert next(surfaces.renderable_geometry(stage, root), None) is None
    assert len(list(surfaces.renderable_geometry(stage, _scene.TEST_SPHERES))) == 2
    assert [str(prim.GetPath()) for prim in surfaces.full_bound_materials(stage, _scene.TEST_SPHERES)] == [
        root + "/Copper",
        root + "/Rubber",
    ]
    assert surfaces.declared_contexts(stage, _scene.TEST_SPHERES) == {"", "mtlx"}


def test_the_root_material_is_bound_where_the_asset_is_the_material(tmp_path):
    ctx, spheres = _built(tmp_path, _MATERIAL)
    root = _scene.asset_root(ctx)

    assert spheres == 1
    assert ctx.stage.GetPrimAtPath(root).IsA(UsdShade.Material)
    sphere = ctx.stage.GetPrimAtPath(_scene.TEST_SPHERES + "/Sphere_0")
    material, _ = UsdShade.MaterialBindingAPI(sphere).ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)
    assert str(material.GetPath()) == root


def test_the_source_layer_is_not_edited(tmp_path):
    ctx, _ = _built(tmp_path, _MATERIAL)

    assert (tmp_path / "asset.usda").read_text() == _MATERIAL
    assert not ctx.stage.GetRootLayer().GetPrimAtPath(_scene.asset_root(ctx) + "/Preview")


def test_an_asset_with_geometry_does_not_get_test_spheres(tmp_path):
    ctx, spheres = _built(tmp_path, _PROP)

    assert spheres == 0
    assert not ctx.stage.GetPrimAtPath(_scene.TEST_SPHERES)


def test_an_empty_asset_without_materials_does_not_get_test_spheres():
    # No subject exists to frame; test the probe-generation rule independently
    # of whether the installed engine rejects an empty camera bound.
    stage = Usd.Stage.CreateInMemory()
    assert stage.GetRootLayer().ImportFromString(_EMPTY)

    assert _scene.add_test_spheres(stage, str(stage.GetDefaultPrim().GetPath())) is None
    assert not stage.GetPrimAtPath(_scene.TEST_SPHERES)


def test_the_camera_looks_at_the_spheres_from_the_asset_framing_direction(tmp_path):
    ctx, _ = _built(tmp_path, _LIBRARY)
    camera = ctx.stage.GetPrimAtPath("/World/Camera")
    eye = UsdGeom.Xformable(camera).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).ExtractTranslation()
    # Two spheres in one row: x in [-1.125, 1.125], y in [-0.5, 0.5], z in [0, 1].
    center = Gf.Vec3d(0.0, 0.0, 0.5)

    offset = eye - center
    assert offset.GetLength() > 2.0
    assert Gf.IsClose(offset.GetNormalized(), Gf.Vec3d(0.3, 0.8, 0.4).GetNormalized(), 1e-6)


def test_every_sphere_face_points_outward_and_st_spans_the_unit_square():
    stage = Usd.Stage.CreateInMemory()
    mesh = _scene._sphere(stage, "/Sphere", (0.0, 0.0, 0.0))
    points = [Gf.Vec3d(p) for p in mesh.GetPointsAttr().Get()]
    indices = mesh.GetFaceVertexIndicesAttr().Get()
    counts = mesh.GetFaceVertexCountsAttr().Get()
    st = UsdGeom.PrimvarsAPI(mesh).GetPrimvar("st")

    assert len(counts) == _scene.TEST_SPHERE_BANDS * _scene.TEST_SPHERE_SEGMENTS
    assert st.GetInterpolation() == UsdGeom.Tokens.vertex
    values = st.Get()
    assert len(values) == len(points)
    assert min(c for v in values for c in v) == 0.0
    assert max(c for v in values for c in v) == 1.0
    for face in range(len(counts)):
        a, b, c, d = (points[i] for i in indices[4 * face : 4 * face + 4])
        # The diagonals' cross product is the quad's normal, and survives the edge a pole collapses.
        normal = Gf.Cross(c - a, d - b)
        assert Gf.Dot(normal, (a + b + c + d) * 0.25) > 0.0


def test_the_strong_probe_reaches_the_spheres_and_clears_back_to_the_material(tmp_path):
    ctx, _ = _built(tmp_path, _MATERIAL)
    stage = ctx.stage
    sphere = stage.GetPrimAtPath(_scene.TEST_SPHERES + "/Sphere_0")

    assert _surface_test.paint(stage, _scene.PROBE_ASSET_PARENT)
    _surface_test._require_strong_probe(stage, _scene.TEST_SPHERES)
    _surface_test.clear(stage, _scene.PROBE_ASSET_PARENT)
    material, _ = UsdShade.MaterialBindingAPI(sphere).ComputeBoundMaterial()
    assert str(material.GetPath()) == _scene.asset_root(ctx)


def _render_pass_ctx(monkeypatch, scene_ctx, spheres):
    """Drive ``_render_pass`` on an already built scene; only the pin, capture and mask are faked."""
    np = pytest.importorskip("numpy")

    async def pin(_ctx, order):
        return order

    async def build(_ctx):
        return spheres

    async def capture(**_kwargs):
        return "frame.png"

    monkeypatch.setattr(_surface_test._context, "pin", pin)
    monkeypatch.setattr(_surface_test._scene, "build_scene", build)
    monkeypatch.setattr(_surface_test._pixels, "dominant_mask", lambda *_args: np.ones((2, 2), dtype=bool))
    scene_ctx.capture_frame = capture
    return scene_ctx


def test_the_render_pass_reports_the_spheres_and_their_scope(monkeypatch, tmp_path):
    scene_ctx, spheres = _built(tmp_path, _MATERIAL)
    ctx = _render_pass_ctx(monkeypatch, scene_ctx, spheres)

    result = asyncio.run(
        _surface_test._render_pass(ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False)
    )

    assert not result.get("error")
    assert result["spheres"] == 1
    assert result["scope"] == _scene.TEST_SPHERES
    assert result["root"] == _scene.asset_root(scene_ctx)


def test_the_render_pass_rejects_a_wrapper_that_holds_something_else(monkeypatch, tmp_path):
    scene_ctx, _ = _built(tmp_path, _MATERIAL)
    # Spheres built, but the pass is told the asset has geometry of its own.
    ctx = _render_pass_ctx(monkeypatch, scene_ctx, 0)

    result = asyncio.run(
        _surface_test._render_pass(ctx, [""], "probe", UsdShade.Tokens.strongerThanDescendants, capture_reported=False)
    )

    assert result["error"] == "root"


class _Recorder:
    """The calls ``run_coverage_test`` makes, recorded."""

    def __init__(self):
        self.config = {"min_silhouette_pixels": 1}
        self.metrics = {}
        self.logs = []
        self.failed = None
        self.skipped = None

    def step(self, message):
        pass

    def log(self, message):
        self.logs.append(message)

    def add_metric(self, name, value):
        self.metrics[name] = value

    def fail(self, message):
        self.failed = message

    def skip(self, reason):
        self.skipped = reason


def _run(monkeypatch, tmp_path, context, owning_feature=None, read_materialx_log=False, materialx_clean=True):
    """Run the coverage test on a built material-asset scene with faked renders."""
    np = pytest.importorskip("numpy")
    scene_ctx, spheres = _built(tmp_path, _MATERIAL)
    stage, root = scene_ctx.stage, _scene.asset_root(scene_ctx)
    passes, read = [], []

    async def render(_ctx, order, *_args, **_kwargs):
        passes.append(order)
        return {
            "mask": np.ones((2, 2), dtype=bool),
            "effective": order,
            "stage": stage,
            "root": root,
            "scope": _scene.TEST_SPHERES,
            "spheres": spheres,
        }

    def report_materialx(_ctx, scoped_root, *_args):
        read.append(scoped_root)
        return materialx_clean

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda *_args: None)
    monkeypatch.setattr(_surface_test, "_report_materialx", report_materialx)
    ctx = _Recorder()
    asyncio.run(
        _surface_test.run_coverage_test(
            ctx,
            context=context,
            requirement="VM.MAT.001",
            fix_hint="- hint",
            read_materialx_log=read_materialx_log,
            owning_feature=owning_feature,
        )
    )
    return ctx, passes, read, root


def test_a_material_asset_is_rendered_by_the_strong_pass_alone(monkeypatch, tmp_path):
    ctx, passes, _, _ = _run(monkeypatch, tmp_path, "")

    assert passes == [[""]]
    assert ctx.failed is None and ctx.skipped is None
    assert ctx.metrics["universal_surface_test_spheres"] == 1
    assert ctx.metrics["universal_surface_materials_total"] == 1
    assert ctx.metrics["universal_surface_contexts_present"] == "mtlx, universal"
    assert "universal_surface_coverage" not in ctx.metrics
    assert "test spheres" in ctx.logs[-1]


def test_openpbr_reads_the_materialx_log_under_the_asset_root(monkeypatch, tmp_path):
    ctx, passes, read, root = _run(
        monkeypatch, tmp_path, "mtlx", owning_feature="FET006_Materials.Openpbr", read_materialx_log=True
    )

    assert passes == [["mtlx"]]
    assert read == [root]
    assert ctx.skipped is None
    assert ctx.metrics["mtlx_surface_contexts_declared"] == "mtlx, universal"


def test_a_materialx_error_ends_the_material_asset_run_without_the_rendered_log(monkeypatch, tmp_path):
    ctx, _, read, _ = _run(
        monkeypatch,
        tmp_path,
        "mtlx",
        owning_feature="FET006_Materials.Openpbr",
        read_materialx_log=True,
        materialx_clean=False,
    )

    assert read
    assert not any("test spheres" in message for message in ctx.logs)


def test_a_context_no_published_material_declares_skips_in_material_wording(monkeypatch, tmp_path):
    ctx, passes, _, _ = _run(monkeypatch, tmp_path, "mdl", owning_feature="FET006_Materials.MDL")

    assert passes == [["mdl"]]
    assert ctx.skipped.startswith("None of the materials the asset publishes declares a surface for the mdl")
    assert "The asset has a surface on: mtlx, universal." in ctx.skipped

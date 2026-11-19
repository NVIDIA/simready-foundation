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
"""FET009_MaterialCoverage: the FET006 render tests it shares, and when two of them skip.

FET009 has no tests of its own. Each FET006 render test registers under its FET006 feature
and FET009_MaterialCoverage, and one run counts toward both. The OpenPBR and MDL tests
skip an asset whose materials have no surface on their context: Kit would render the
universal surfaces in its place, and the run would measure them again.
"""

import ast
import asyncio
import json
from pathlib import Path

import pytest

_TIER = Path(__file__).parents[3]
_SUITE = _TIER / "simready" / "foundation" / "tier_core" / "runtime_tests"
_MANIFEST = _TIER / "simready" / "foundation" / "tier_core" / "features" / "FET009_MaterialCoverage.0-1-0.json"
_PROVIDER = "simready.foundation.tier_core.runtime_tests"
_COVERAGE = "FET009_MaterialCoverage.0-1-0"

# Only the keywords that are literals. `config_defaults=dict(_scene.SCENE_DEFAULTS)`
# is a call, and ast.literal_eval raises on it.
_LITERAL_KEYWORDS = {"features", "name", "version"}

# Test name: (module under the suite, coroutine, the FET006 contract it also serves,
# the owning_feature it passes).
_SHARED_TESTS = {
    "preview_surface_renders": (
        "fet006_materials/preview_surface_renders.py",
        "test_preview_surface_renders",
        "FET006_Materials",
        None,
    ),
    "openpbr_renders": (
        "fet006_materials/openpbr_renders.py",
        "test_openpbr_renders",
        "FET006_Materials.Openpbr",
        "FET006_Materials.Openpbr",
    ),
    "mdl_renders": (
        "fet006_materials/mdl_renders.py",
        "test_mdl_renders",
        "FET006_Materials.MDL",
        "FET006_Materials.MDL",
    ),
}


def _function(module, function):
    tree = ast.parse((_SUITE / module).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function:
            return node
    raise AssertionError(f"{function} not found in {module}")


def _registration(module, function):
    for decorator in _function(module, function).decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == "test":
            return {
                keyword.arg: ast.literal_eval(keyword.value)
                for keyword in decorator.keywords
                if keyword.arg in _LITERAL_KEYWORDS
            }
    raise AssertionError(f"{function} has no @test registration in {module}")


def _coverage_call(module, function):
    """The ``run_coverage_test`` call in ``function``."""
    for call in ast.walk(_function(module, function)):
        if isinstance(call, ast.Call) and getattr(call.func, "attr", None) == "run_coverage_test":
            return call
    raise AssertionError(f"no run_coverage_test call in {function}")


def _coverage_call_keywords(module, function):
    """The constant keyword arguments of the ``run_coverage_test`` call in ``function``."""
    call = _coverage_call(module, function)
    return {keyword.arg: keyword.value.value for keyword in call.keywords if isinstance(keyword.value, ast.Constant)}


@pytest.mark.parametrize("name", sorted(_SHARED_TESTS))
def test_shared_tests_register_under_their_fet006_feature_and_fet009(name):
    module, function, fet006_contract, _ = _SHARED_TESTS[name]
    registration = _registration(module, function)
    feature_ids = [feature["id"] for feature in registration["features"]]

    assert registration["name"] == name
    assert feature_ids.count(_COVERAGE) == 1
    others = [feature_id for feature_id in feature_ids if feature_id != _COVERAGE]
    assert others
    assert all(feature_id.startswith(fet006_contract + ".") for feature_id in others)


def test_manifest_binds_exactly_the_shared_tests():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["id"] == _COVERAGE
    assert sorted(manifest["runtime_tests"]) == sorted(f"{_PROVIDER}:{name}" for name in _SHARED_TESTS)


def test_fet009_has_no_test_package_of_its_own():
    assert not list(_SUITE.glob("fet009_*"))


def test_manifest_adapter_is_a_conform_skill_for_this_feature():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    skills = _TIER / "simready" / "foundation" / "tier_core" / "skills"

    assert manifest["adapters"]
    for adapter in manifest["adapters"]:
        kind, _, name = adapter.partition(":")
        assert kind == "skill"
        text = (skills / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {name}\n" in text
        assert "FET009_MaterialCoverage" in text


@pytest.mark.parametrize("name", sorted(_SHARED_TESTS))
def test_optional_context_tests_name_the_feature_that_owns_their_surface(name):
    module, function, _, owning_feature = _SHARED_TESTS[name]

    assert _coverage_call_keywords(module, function).get("owning_feature") == owning_feature


@pytest.mark.parametrize("name", sorted(_SHARED_TESTS))
def test_a_coverage_failure_names_the_binding_requirement_and_fix(name):
    """Coverage is low only where geometry resolves no material, whatever the context."""
    module, function, _, _ = _SHARED_TESTS[name]
    call = _coverage_call(module, function)
    fix_hint = next(keyword.value for keyword in call.keywords if keyword.arg == "fix_hint")

    assert _coverage_call_keywords(module, function)["requirement"] == "VM.MAT.001"
    assert isinstance(fix_hint, ast.Attribute) and fix_hint.attr == "BINDING_FIX_HINT"


def test_skip_is_not_delegated_to_precheck_failure():
    """``ctx.precheck_failure`` fails the run when the asset claims a feature the test registers under.

    An asset claims FET009_MaterialCoverage while declining OpenPBR or MDL, so a
    claim-based branch would fail the assets the skip exists for.
    """
    tree = ast.parse((_SUITE / "fet006_materials" / "_surface_test.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "precheck_failure"
    ]
    assert calls == []


class _Ctx:
    """The calls ``run_coverage_test`` makes, recorded."""

    def __init__(self, validated=None):
        self.config = {"min_silhouette_pixels": 1}
        self.asset_validated_features = validated
        self.test_feature_names = [_COVERAGE]
        self.metrics = {}
        self.failed = None
        self.skipped = None

    def step(self, message):
        pass

    def log(self, message):
        pass

    def add_metric(self, name, value):
        self.metrics[name] = value

    def fail(self, message):
        self.failed = message

    def skip(self, reason):
        self.skipped = reason


# Shader ids per render context. Only the connection decides what a material declares.
_SHADER_IDS = {"": "UsdPreviewSurface", "mdl": "OmniPBR", "mtlx": "ND_open_pbr_surface_surfaceshader"}


def _asset(materials, meshes):
    """An in-memory stage with the asset at ``/Asset``.

    ``materials`` maps a material path to the render contexts it has a surface for.
    ``meshes`` maps a mesh path to ``{purpose: material path}``, where purpose is ``""``
    (all-purpose), ``"full"`` or ``"preview"``. A ``"subsets"`` entry maps a subset name to
    ``(family name, material path)``.
    """
    pytest.importorskip("pxr")
    from pxr import Usd, UsdGeom, UsdShade, Vt

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    for path, contexts in materials.items():
        material = UsdShade.Material.Define(stage, path)
        for context in contexts:
            shader = UsdShade.Shader.Define(stage, f"{path}/{context or 'preview'}")
            shader.CreateIdAttr(_SHADER_IDS[context])
            output = material.CreateSurfaceOutput(context) if context else material.CreateSurfaceOutput()
            output.ConnectToSource(shader.ConnectableAPI(), "out")

    def bind(prim, material_path, purpose):
        material = UsdShade.Material(stage.GetPrimAtPath(material_path))
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material, materialPurpose=purpose)

    for path, bindings in meshes.items():
        mesh = UsdGeom.Mesh.Define(stage, path)
        for purpose, material_path in bindings.items():
            if purpose == "subsets":
                continue
            bind(mesh.GetPrim(), material_path, purpose)
        for name, (family, material_path) in bindings.get("subsets", {}).items():
            subset = UsdGeom.Subset.CreateGeomSubset(
                UsdGeom.Imageable(mesh), name, UsdGeom.Tokens.face, Vt.IntArray([0]), family
            )
            bind(subset.GetPrim(), material_path, "")
    return stage


# The "Valid: separate preview and fidelity materials" example from the VM.MAT.001 page
# (material-assignment.md). Both meshes bind only through material:binding:full.
_FULL_ONLY_EXAMPLE = """#usda 1.0
def Xform "Asset" ( prepend apiSchemas = ["MaterialBindingAPI"] )
{
    rel material:binding:preview = </Asset/Looks/mtl_shared>

    def Scope "Looks"
    {
        def Material "mtl_shared"
        {
            token outputs:surface.connect = </Asset/Looks/mtl_shared/Preview.outputs:surface>
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_shared/OpenPBR.outputs:out>

            def Shader "Preview"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0.18, 0.18, 0.18)
                token outputs:surface
            }

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.18, 0.18, 0.18)
                token outputs:out
            }
        }

        def Material "mtl_steel"
        {
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_steel/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.35, 0.36, 0.38)
                float inputs:base_metalness = 1
                float inputs:specular_roughness = 0.25
                token outputs:out
            }
        }

        def Material "mtl_rubber"
        {
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_rubber/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.05, 0.05, 0.05)
                float inputs:specular_roughness = 0.8
                token outputs:out
            }
        }
    }

    def Mesh "part_steel" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding:full = </Asset/Looks/mtl_steel>
    }

    def Mesh "part_rubber" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding:full = </Asset/Looks/mtl_rubber>
    }
}
"""


def _full_only_example():
    pytest.importorskip("pxr")
    from pxr import Usd

    stage = Usd.Stage.CreateInMemory()
    assert stage.GetRootLayer().ImportFromString(_FULL_ONLY_EXAMPLE)
    return stage


def _run(monkeypatch, context, owning_feature, stage, validated=None):
    """Drive ``run_coverage_test`` on ``stage`` with fake render passes; return the context, passes and restores.

    Only the renders are faked. The surface inventory and the skip decision run on the stage.
    """
    pytest.importorskip("pxr")
    np = pytest.importorskip("numpy")
    from simready.foundation.tier_core.runtime_tests.fet006_materials import (
        _surface_test,
    )

    passes, restored = [], []

    async def render(_ctx, order, *_args, **_kwargs):
        passes.append(order)
        # Every pixel follows every control: the silhouette and the uncovered set are the whole frame.
        return {"mask": np.ones((2, 2), dtype=bool), "effective": order, "stage": stage, "root": "/Asset"}

    monkeypatch.setattr(_surface_test, "_render_pass", render)
    monkeypatch.setattr(_surface_test._context, "read_order", lambda: [""])
    monkeypatch.setattr(_surface_test._context, "restore", lambda _ctx, previous: restored.append(previous))
    monkeypatch.setattr(_surface_test, "_report_materialx", lambda *_: True)

    ctx = _Ctx(validated)
    asyncio.run(
        _surface_test.run_coverage_test(
            ctx, context=context, requirement="VM.MAT.001", fix_hint="- hint", owning_feature=owning_feature
        )
    )
    return ctx, passes, restored


def _body_and_trim(body, trim):
    """Two meshes, each bound all-purpose to its own material with the given contexts."""
    return _asset(
        {"/Asset/Looks/Body": body, "/Asset/Looks/Trim": trim},
        {"/Asset/Body": {"": "/Asset/Looks/Body"}, "/Asset/Trim": {"": "/Asset/Looks/Trim"}},
    )


def test_declined_openpbr_skips_after_the_first_pass(monkeypatch):
    ctx, passes, restored = _run(monkeypatch, "mtlx", "FET006_Materials.Openpbr", _body_and_trim([""], ["", "mdl"]))

    assert ctx.failed is None
    assert "FET006_Materials.Openpbr" in ctx.skipped
    assert "VM.PBR.001" in ctx.skipped
    assert passes == [["mtlx"]]
    assert restored == [[""]]
    assert ctx.metrics["mtlx_surface_contexts_declared"] == "mdl, universal"
    assert ctx.metrics["mtlx_surface_contexts_present"] == "mdl, universal"


def test_declined_mdl_skips_and_names_its_presence_requirement(monkeypatch):
    ctx, passes, _ = _run(monkeypatch, "mdl", "FET006_Materials.MDL", _body_and_trim(["", "mtlx"], [""]))

    assert ctx.failed is None
    assert "VM.MDL.003" in ctx.skipped
    assert "VM.MDL.001" not in ctx.skipped
    assert passes == [["mdl"]]


def test_an_asset_with_no_material_skips_the_optional_contexts(monkeypatch):
    stage = _asset({}, {"/Asset/Body": {}})
    ctx, _, _ = _run(monkeypatch, "mtlx", "FET006_Materials.Openpbr", stage)

    assert ctx.failed is None
    assert "no context at all" in ctx.skipped
    assert ctx.metrics["mtlx_surface_contexts_declared"] == "none"


def test_a_declared_context_is_measured(monkeypatch):
    ctx, passes, _ = _run(monkeypatch, "mtlx", "FET006_Materials.Openpbr", _body_and_trim(["", "mtlx"], [""]))

    assert ctx.skipped is None
    assert passes == [["mtlx"]] * 3
    assert ctx.metrics["mtlx_surface_coverage"] == 0.0
    assert ctx.failed is not None


def test_without_an_owning_feature_an_absent_context_is_measured(monkeypatch):
    """The FET006 tests and the universal FET009 test pass no owning feature."""
    ctx, passes, _ = _run(monkeypatch, "mtlx", None, _body_and_trim([""], [""]))

    assert ctx.skipped is None
    assert len(passes) == 3
    assert "mtlx_surface_contexts_declared" not in ctx.metrics


@pytest.mark.parametrize(
    "validated",
    [None, [], [_COVERAGE], [_COVERAGE, "FET006_Materials.Openpbr.0-2-0"]],
)
def test_the_skip_does_not_depend_on_the_validation_claim(monkeypatch, validated):
    ctx, _, _ = _run(monkeypatch, "mtlx", "FET006_Materials.Openpbr", _body_and_trim([""], [""]), validated)

    assert ctx.failed is None
    assert ctx.skipped is not None


def test_materials_bound_only_for_the_full_purpose_are_measured(monkeypatch):
    """The VM.MAT.001 page's full-only example has OpenPBR on both meshes at ``full``."""
    ctx, passes, _ = _run(monkeypatch, "mtlx", "FET006_Materials.Openpbr", _full_only_example())

    assert ctx.skipped is None
    assert passes == [["mtlx"]] * 3
    assert ctx.metrics["mtlx_surface_contexts_declared"] == "mtlx"


def test_the_full_only_example_declares_no_mdl_surface(monkeypatch):
    ctx, passes, _ = _run(monkeypatch, "mdl", "FET006_Materials.MDL", _full_only_example())

    assert "VM.MDL.003" in ctx.skipped
    assert passes == [["mdl"]]


def test_full_purpose_resolution_matches_the_static_gate():
    """``mtl_shared`` is bound only for preview, so a ``full`` resolution never returns it."""
    from simready.foundation.tier_core.runtime_tests.fet006_materials import surfaces

    stage = _full_only_example()
    paths = sorted(str(prim.GetPath()) for prim in surfaces.full_bound_materials(stage, "/Asset"))

    assert paths == ["/Asset/Looks/mtl_rubber", "/Asset/Looks/mtl_steel"]
    assert surfaces.declared_contexts(stage, "/Asset") == {surfaces.MTLX}


def test_a_preview_only_binding_declares_nothing():
    from simready.foundation.tier_core.runtime_tests.fet006_materials import surfaces

    stage = _asset(
        {"/Asset/Looks/Fidelity": ["mtlx"], "/Asset/Looks/Preview": [""]},
        {"/Asset/Body": {"preview": "/Asset/Looks/Fidelity"}, "/Asset/Trim": {"": "/Asset/Looks/Preview"}},
    )

    assert surfaces.declared_contexts(stage, "/Asset") == {surfaces.UNIVERSAL}


@pytest.mark.parametrize("order", [("Body", "Trim"), ("Trim", "Body")])
def test_materials_that_share_a_name_stay_apart(monkeypatch, order):
    """Two bound materials named ``Steel`` in different scopes: one has OpenPBR, one does not."""
    contexts = {"Body": ["", "mtlx"], "Trim": [""]}
    stage = _asset(
        {f"/Asset/{part}/Looks/Steel": contexts[part] for part in order},
        {f"/Asset/{part}/Mesh": {"": f"/Asset/{part}/Looks/Steel"} for part in order},
    )
    ctx, passes, _ = _run(monkeypatch, "mtlx", "FET006_Materials.Openpbr", stage)

    assert ctx.skipped is None
    assert len(passes) == 3


def test_material_bind_subsets_are_resolved_and_other_families_are_not():
    from simready.foundation.tier_core.runtime_tests.fet006_materials import surfaces

    stage = _asset(
        {"/Asset/Looks/Base": [""], "/Asset/Looks/Rubber": ["mdl"], "/Asset/Looks/Label": ["mtlx"]},
        {
            "/Asset/Body": {
                "": "/Asset/Looks/Base",
                "subsets": {"grip": ("materialBind", "/Asset/Looks/Rubber"), "decal": ("other", "/Asset/Looks/Label")},
            }
        },
    )

    assert surfaces.declared_contexts(stage, "/Asset") == {surfaces.UNIVERSAL, surfaces.MDL}

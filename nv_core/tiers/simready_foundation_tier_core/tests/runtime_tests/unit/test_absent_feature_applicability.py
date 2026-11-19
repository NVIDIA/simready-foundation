# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A clean absence is N/A; an unavailable asset root is an execution error."""

import importlib
import sys
import types

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdShade
from simready.foundation.tier_core.runtime_tests.fet005_grasp import grasp_checks
from simready.foundation.tier_core.runtime_tests.fet006_materials import (
    _scene,
    _surface_test,
    surfaces,
)


def test_grasp_precheck_requires_loaded_asset_root():
    stage = Usd.Stage.CreateInMemory()
    with pytest.raises(RuntimeError, match="asset root"):
        grasp_checks.run_pre_checks(stage, "/Missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("unsupported_named_prim", [False, True])
async def test_absent_grasp_identifiers_are_marked_not_applicable(monkeypatch, unsupported_named_prim):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    if unsupported_named_prim:
        UsdGeom.Mesh.Define(stage, "/Asset/grasp_identifier_mesh")
    decorator = types.ModuleType("simready.evaluate.core.decorator")
    decorator.test = lambda **_kwargs: lambda function: function
    monkeypatch.setitem(sys.modules, "simready.evaluate.core.decorator", decorator)
    grasp = importlib.import_module("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_and_lift")
    omni = types.ModuleType("omni")
    omni_usd = types.ModuleType("omni.usd")
    omni_usd.get_context = lambda: types.SimpleNamespace(get_stage=lambda: stage)
    omni.usd = omni_usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", omni_usd)

    class Context:
        asset_path = "asset.usd"
        asset_validated_features = None
        config = {"settle_frames": 1, "asset_load_timeout": 1}
        scene = types.SimpleNamespace(
            asset=types.SimpleNamespace(prim_path="/Asset"),
            load_asset=lambda *_args, **_kwargs: None,
        )

        def __init__(self):
            self.events = []

        def set_settle_frames(self, _value):
            pass

        def step(self, _message):
            pass

        def add_metric(self, name, value):
            self.events.append(("metric", name, value))

        def skip(self, message):
            self.events.append(("skip", message))

    ctx = Context()
    await grasp.test_grasp_and_lift(ctx)
    if unsupported_named_prim:
        assert len(ctx.events) == 1
        assert ctx.events[0][0] == "skip"
        assert "unsupported" in ctx.events[0][1]
    else:
        marker, skip = ctx.events
        assert marker[0:2] == ("metric", "assessment_applicability")
        assert marker[2] == {
            "status": "not_applicable",
            "reason_code": "no_grasp_identifiers",
            "reason": skip[1],
        }
        assert skip[0] == "skip"


def test_missing_surface_context_is_marked_not_applicable_before_skip():
    events = []

    class Context:
        def add_metric(self, name, value):
            events.append(("metric", name, value))

        def skip(self, message):
            events.append(("skip", message))

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    _surface_test._absent_context(
        Context(),
        surfaces.MDL,
        "FET006_Materials.MDL",
        ["universal"],
        stage=stage,
        asset_root="/Asset",
    )
    marker, skip = events
    assert marker[0:2] == ("metric", "assessment_applicability")
    assert marker[2] == {
        "status": "not_applicable",
        "reason_code": "no_resolved_surface_for_context",
        "reason": skip[1],
    }
    assert skip[0] == "skip"


def test_incomplete_surface_inventory_stays_unassessed():
    events = []

    class Context:
        def add_metric(self, name, value):
            events.append(("metric", name, value))

        def skip(self, message):
            events.append(("skip", message))

    stage = Usd.Stage.CreateInMemory()
    _surface_test._absent_context(
        Context(),
        surfaces.MDL,
        "FET006_Materials.MDL",
        [],
        stage=stage,
        asset_root="/Missing",
    )
    assert len(events) == 1
    assert events[0][0] == "skip"


def test_missing_external_material_binding_keeps_surface_unassessed():
    events = []

    class Context:
        def add_metric(self, name, value):
            events.append(("metric", name, value))

        def skip(self, message):
            events.append(("skip", message))

    stage = Usd.Stage.CreateInMemory()
    cube = UsdGeom.Cube.Define(stage, "/Asset/Cube")
    UsdShade.MaterialBindingAPI.Apply(cube.GetPrim())
    cube.GetPrim().GetRelationship("material:binding").SetTargets([Sdf.Path("/External/Material")])
    _surface_test._absent_context(
        Context(),
        surfaces.MDL,
        "FET006_Materials.MDL",
        [],
        stage=stage,
        asset_root="/Asset",
    )
    assert len(events) == 1
    assert events[0][0] == "skip"
    assert "incomplete" in events[0][1]


def test_instance_proxy_material_is_in_published_inventory():
    layer = Sdf.Layer.CreateAnonymous()
    prototype = Usd.Stage.Open(layer)
    UsdGeom.Xform.Define(prototype, "/Prototype")
    material = UsdShade.Material.Define(prototype, "/Prototype/Material")
    shader = UsdShade.Shader.Define(prototype, "/Prototype/Material/Shader")
    shader.CreateIdAttr("OmniPBR")
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput("mdl").ConnectToSource(shader.ConnectableAPI(), "surface")
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    instance = UsdGeom.Xform.Define(stage, "/Asset/Instance").GetPrim()
    instance.GetReferences().AddReference(layer.identifier, "/Prototype")
    instance.SetInstanceable(True)
    assert [str(prim.GetPath()) for prim in surfaces.published_materials(stage, "/Asset")] == [
        "/Asset/Instance/Material"
    ]
    assert _scene.add_test_spheres(stage, "/Asset")[0] == 1
    _surface_test.deinstance(stage, "/Asset")
    assert surfaces.declared_contexts(stage, _scene.TEST_SPHERES) == {"mdl"}


def test_material_sphere_inventory_mismatch_keeps_surface_unassessed():
    events = []

    class Context:
        def add_metric(self, name, value):
            events.append(("metric", name, value))

        def skip(self, message):
            events.append(("skip", message))

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    UsdShade.Material.Define(stage, "/Asset/Material")
    _surface_test._absent_context(
        Context(),
        surfaces.MDL,
        "FET006_Materials.MDL",
        [],
        stage=stage,
        asset_root="/Asset",
        sphere_count=0,
    )
    assert len(events) == 1
    assert events[0][0] == "skip"
    assert "inventory" in events[0][1]


def test_unresolved_material_surface_source_stays_unassessed():
    events = []

    class Context:
        def add_metric(self, name, value):
            events.append(("metric", name, value))

        def skip(self, message):
            events.append(("skip", message))

    stage = Usd.Stage.CreateInMemory()
    cube = UsdGeom.Cube.Define(stage, "/Asset/Cube")
    material = UsdShade.Material.Define(stage, "/Asset/Material")
    output = material.CreateSurfaceOutput("mdl")
    output.GetAttr().SetConnections([Sdf.Path("/External/Shader.outputs:surface")])
    UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(material)
    assert not stage.GetCompositionErrors()
    assert surfaces.surface_output(material.GetPrim(), surfaces.MDL) is None
    _surface_test._absent_context(
        Context(),
        surfaces.MDL,
        "FET006_Materials.MDL",
        [],
        stage=stage,
        asset_root="/Asset",
    )
    assert len(events) == 1
    assert events[0][0] == "skip"
    assert "source" in events[0][1]

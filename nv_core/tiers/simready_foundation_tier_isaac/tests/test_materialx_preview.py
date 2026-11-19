# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Material conversion must preserve surviving shading and USD composition."""

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import materialx_preview


def _material(stage, path="/Asset/Material", context="mtlx", shader_id="ND_open_pbr_surface_surfaceshader"):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/OpenPBR")
    shader.CreateIdAttr(shader_id)
    material.CreateSurfaceOutput(context).ConnectToSource(shader.CreateOutput("out", Sdf.ValueTypeNames.Token))
    return material, shader


def _attributes(prim):
    return {a.GetName(): (a.GetTypeName(), a.Get(), a.GetConnections(), a.GetAllMetadata())
            for a in prim.GetAttributes()}


@pytest.mark.parametrize("context", ["mtlx", "MTLX"])
def test_exchange_preview_mdl_bindings_and_shared_inputs_survive(context):
    usdex = pytest.importorskip("usdex.core")
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset")
    stage.SetDefaultPrim(root.GetPrim())
    material = usdex.definePbrMaterial(stage, Sdf.Path("/Asset/Material"), Gf.Vec3f(0.2, 0.4, 0.6), roughness=0.7)
    assert usdex.addColorTextureToPbrMaterial(material, Sdf.AssetPath("albedo.png"))
    UsdShade.Shader.Define(stage, "/Asset/Material/UnusedMaterialX").CreateIdAttr("ND_noise3d_float")
    if context != "mtlx":
        material.CreateSurfaceOutput(context).GetAttr().SetConnections(material.GetSurfaceOutput("mtlx").GetAttr().GetConnections())
        material.GetPrim().RemoveProperty("outputs:mtlx:surface")
    mdl = UsdShade.Shader.Define(stage, "/Asset/Material/MDL")
    mdl.CreateIdAttr("OmniPBR")
    material.CreateSurfaceOutput("mdl").ConnectToSource(mdl.CreateOutput("out", Sdf.ValueTypeNames.Token))
    mesh = UsdGeom.Cube.Define(stage, "/Asset/Cube")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    before = {p.GetPath(): _attributes(p) for p in stage.Traverse()
              if UsdShade.Shader(p) and not str(UsdShade.Shader(p).GetIdAttr().Get()).startswith("ND_")}
    inputs = {i.GetFullName(): (i.Get(), i.GetAttr().GetConnections()) for i in material.GetInputs()}
    assert materialx_preview.cook_stage(stage) == 1
    assert not materialx_preview.materialx_outputs(material)
    for path, attrs in before.items():
        assert _attributes(stage.GetPrimAtPath(path)) == attrs
    assert {i.GetFullName(): (i.Get(), i.GetAttr().GetConnections()) for i in material.GetInputs()} == inputs
    assert UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()[0].GetPath() == material.GetPath()
    assert not any(str(UsdShade.Shader(p).GetIdAttr().Get()).startswith("ND_")
                   for p in stage.Traverse() if UsdShade.Shader(p))
    assert materialx_preview.cook_stage(stage) == 0


@pytest.mark.parametrize("shader_id,metal_name", [
    ("ND_open_pbr_surface_surfaceshader", "base_metalness"),
    ("ND_standard_surface_surfaceshader", "metalness"),
])
def test_parameter_fallback_uses_authored_values(shader_id, metal_name):
    stage = Usd.Stage.CreateInMemory()
    material, surface = _material(stage, shader_id=shader_id)
    surface.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.1, 0.2, 0.3))
    surface.CreateInput(metal_name, Sdf.ValueTypeNames.Float).Set(0.8)
    surface.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.42)
    surface.CreateInput("transmission_weight", Sdf.ValueTypeNames.Float).Set(0.9)
    assert materialx_preview.cook_stage(stage) == 1
    preview, _, _ = material.ComputeSurfaceSource()
    assert preview.GetIdAttr().Get() == "UsdPreviewSurface"
    assert preview.GetInput("diffuseColor").Get() == Gf.Vec3f(0.1, 0.2, 0.3)
    assert preview.GetInput("metallic").Get() == pytest.approx(0.8)
    assert preview.GetInput("roughness").Get() == pytest.approx(0.42)
    assert preview.GetInput("opacity").Get() == 1.0
    assert preview.GetInput("emissiveColor").Get() == Gf.Vec3f(0)


def test_reference_cleanup_overrides_only_staged_layer(tmp_path):
    source_path = tmp_path / "source.usda"
    source = Usd.Stage.CreateNew(str(source_path))
    material, _ = _material(source, path="/Material")
    source.SetDefaultPrim(material.GetPrim())
    source.GetRootLayer().Save()
    source_bytes = source_path.read_bytes()
    output_path = tmp_path / "optimized.usda"
    output = Usd.Stage.CreateNew(str(output_path))
    prim = output.DefinePrim("/Material")
    prim.GetReferences().AddReference(str(source_path))
    output.SetDefaultPrim(prim)
    assert materialx_preview.cook_stage(output) == 1
    output.GetRootLayer().Save()
    reopened = Usd.Stage.Open(str(output_path))
    assert not materialx_preview.materialx_outputs(UsdShade.Material(reopened.GetDefaultPrim()))
    assert not reopened.GetPrimAtPath("/Material/OpenPBR").IsActive()
    assert source_path.read_bytes() == source_bytes
    assert materialx_preview.cook_stage(reopened) == 0


def test_shared_materialx_node_blocks_removal_without_damaging_mdl():
    stage = Usd.Stage.CreateInMemory()
    material, surface = _material(stage)
    mdl = UsdShade.Shader.Define(stage, "/Asset/Material/MDL")
    mdl.CreateIdAttr("OmniPBR")
    mdl.CreateInput("shared", Sdf.ValueTypeNames.Color3f).ConnectToSource(surface.GetOutput("out"))
    material.CreateSurfaceOutput("mdl").ConnectToSource(mdl.CreateOutput("out", Sdf.ValueTypeNames.Token))
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(ValueError, match="shared with a surviving network"):
        materialx_preview.cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before


def test_universal_mdl_surface_is_not_overwritten_by_generated_preview():
    stage = Usd.Stage.CreateInMemory()
    material, _ = _material(stage)
    mdl = UsdShade.Shader.Define(stage, "/Asset/Material/MDL")
    mdl.CreateIdAttr("OmniPBR")
    material.CreateSurfaceOutput().ConnectToSource(mdl.CreateOutput("out", Sdf.ValueTypeNames.Token))
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(ValueError, match="different universal surface"):
        materialx_preview.cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before


def test_universal_and_materialx_outputs_can_share_the_replaced_surface():
    stage = Usd.Stage.CreateInMemory()
    material, surface = _material(stage)
    material.CreateSurfaceOutput().ConnectToSource(surface.GetOutput("out"))
    assert materialx_preview.cook_stage(stage) == 1
    assert material.ComputeSurfaceSource()[0].GetIdAttr().Get() == "UsdPreviewSurface"
    assert not materialx_preview.materialx_outputs(material)
    assert not stage.GetPrimAtPath("/Asset/Material/OpenPBR")


def test_unsupported_second_material_leaves_the_entire_edit_layer_unchanged():
    stage = Usd.Stage.CreateInMemory()
    _material(stage, path="/Asset/First")
    _material(stage, path="/Asset/Second", shader_id="ND_procedural_surface")
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(ValueError, match="unsupported MaterialX surface"):
        materialx_preview.cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before


def test_authoring_failure_restores_already_converted_material(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    _material(stage, path="/Asset/First")
    _material(stage, path="/Asset/Second")
    before = stage.GetRootLayer().ExportToString()
    write = materialx_preview._write_preview

    def fail_second(material, values):
        if material.GetPath() == Sdf.Path("/Asset/Second"):
            raise RuntimeError("authoring failed")
        write(material, values)

    monkeypatch.setattr(materialx_preview, "_write_preview", fail_second)
    with pytest.raises(RuntimeError, match="authoring failed"):
        materialx_preview.cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before

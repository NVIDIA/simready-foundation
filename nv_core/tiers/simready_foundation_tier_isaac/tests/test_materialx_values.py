# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Composed texture interfaces and the SimReady library's normal-map pattern."""
import shutil

import pytest
from pxr import Gf, Sdf, Usd, UsdShade

from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization._materialx_values import Texture, resolve_input


def _node(stage, name, shader_id, output_type=Sdf.ValueTypeNames.Float3):
    shader = UsdShade.Shader.Define(stage, f"/Base/{name}")
    shader.CreateIdAttr(shader_id)
    shader.CreateOutput("out", output_type)
    return shader


@pytest.fixture
def material(tmp_path):
    # The public NVIDIA PhysicalAI-SimReady-Materials v0.2.0 library uses an
    # inherited class and material interface inputs, including texture metadata.
    source_dir = tmp_path / "library"
    source_dir.mkdir()
    texture = source_dir / "texture.png"
    texture.write_bytes(b"test resolver only")
    stage = Usd.Stage.CreateNew(str(source_dir / "material.usda"))
    base = UsdShade.Material(stage.CreateClassPrim("/Base"))
    base.GetPrim().SetTypeName("Material")
    file = base.CreateInput("texture", Sdf.ValueTypeNames.Asset)
    file.Set(Sdf.AssetPath("texture.png"))
    file.GetAttr().SetColorSpace("sRGB")
    base.CreateInput("color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.2, .4, .6))
    base.CreateInput("tiling", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(3, 2))
    base.CreateInput("offset", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(.25, -.5))
    texcoord = _node(stage, "uv", "ND_texcoord_vector2", Sdf.ValueTypeNames.Float2)
    texcoord.CreateInput("index", Sdf.ValueTypeNames.Int).Set(0)
    image = _node(stage, "image", "ND_tiledimage_color3", Sdf.ValueTypeNames.Color3f)
    for target, source, kind in (("file", "texture", Sdf.ValueTypeNames.Asset),
                                 ("default", "color", Sdf.ValueTypeNames.Color3f),
                                 ("uvtiling", "tiling", Sdf.ValueTypeNames.Float2),
                                 ("uvoffset", "offset", Sdf.ValueTypeNames.Float2)):
        image.CreateInput(target, kind).ConnectToSource(base.GetInput(source))
    image.CreateInput("texcoord", Sdf.ValueTypeNames.Float2).ConnectToSource(texcoord.GetOutput("out"))
    surface = _node(stage, "surface", "ND_open_pbr_surface_surfaceshader", Sdf.ValueTypeNames.Token)
    surface.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).ConnectToSource(image.GetOutput("out"))
    instance = UsdShade.Material.Define(stage, "/Material")
    instance.GetPrim().GetInherits().AddInherit(base.GetPath())
    stage.SetDefaultPrim(instance.GetPrim())
    stage.GetRootLayer().Save()
    outer = Usd.Stage.CreateNew(str(tmp_path / "entry.usda"))
    outer.DefinePrim("/Looks", "Scope")
    outer.OverridePrim("/Looks/Material").GetReferences().AddReference(str(source_dir / "material.usda"))
    return outer, texture


def test_inherited_file_color_space_and_uv_transform(material):
    stage, path = material
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    texture = resolve_input(surface.GetInput("base_color"))
    assert isinstance(texture, Texture)
    assert texture.file.path.replace("\\", "/") == path.as_posix()
    assert texture.colorspace == "sRGB"
    assert texture.fallback == pytest.approx((.2, .4, .6, 1))
    # MaterialX: UV * tiling - offset. Preview Surface: UV * scale + translation.
    uv = (.1, .3)
    actual = tuple(x * scale + offset for x, scale, offset in zip(uv, texture.uvscale, texture.uvoffset))
    assert actual == pytest.approx((.05, 1.1))
    image = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/image"))
    image.CreateInput("realworldimagesize", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(2, 4))
    image.CreateInput("realworldtilesize", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(1, 2))
    scaled = resolve_input(surface.GetInput("base_color"))
    assert scaled.uvscale == pytest.approx((1.5, 1))
    assert scaled.uvoffset == pytest.approx((-.125, .25))


def test_empty_file_uses_inherited_default_without_loading_texture(material):
    stage, _ = material
    material = UsdShade.Material(stage.GetPrimAtPath("/Looks/Material"))
    material.GetInput("texture").Set(Sdf.AssetPath())
    material.GetInput("color").Set(Gf.Vec3f(.9, .7, .1))
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    assert resolve_input(surface.GetInput("base_color")) == Gf.Vec3f(.9, .7, .1)


def test_composed_fallback_retains_resolved_texture_after_save_and_reopen(material):
    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization.materialx_preview import cook_stage

    stage, texture_path = material
    mat = UsdShade.Material(stage.GetPrimAtPath("/Looks/Material"))
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    mat.CreateSurfaceOutput("MTLX").ConnectToSource(surface.GetOutput("out"))
    source_path = texture_path.parent / "material.usda"
    source_bytes = source_path.read_bytes()
    assert cook_stage(stage) == 1
    stage.GetRootLayer().Save()
    reopened = Usd.Stage.Open(stage.GetRootLayer().identifier)
    mat = UsdShade.Material(reopened.GetPrimAtPath("/Looks/Material"))
    preview, _, _ = mat.ComputeSurfaceSource()
    tex_source, _, _ = preview.GetInput("diffuseColor").GetConnectedSource()
    texture = UsdShade.Shader(tex_source.GetPrim())
    assert texture.GetInput("file").Get().resolvedPath.replace("\\", "/") == texture_path.as_posix()
    assert texture.GetInput("sourceColorSpace").Get() == "sRGB"
    assert tuple(texture.GetInput("fallback").Get()) == pytest.approx((.2, .4, .6, 1))
    transform_source, _, _ = texture.GetInput("st").GetConnectedSource()
    transform = UsdShade.Shader(transform_source.GetPrim())
    assert transform.GetInput("scale").Get() == Gf.Vec2f(3, 2)
    assert transform.GetInput("translation").Get() == Gf.Vec2f(-.25, .5)
    output = mat.GetSurfaceOutput("MTLX")
    assert not output or not output.GetAttr().GetConnections()
    assert not reopened.GetPrimAtPath("/Looks/Material/surface").IsActive()
    assert source_path.read_bytes() == source_bytes
    assert cook_stage(reopened) == 0


@pytest.mark.parametrize("flips", [(True, False, True), (False, True, False)])
def test_normal_channel_flips_match_decoded_sample(material, flips):
    stage, _ = material
    material = UsdShade.Material(stage.GetPrimAtPath("/Looks/Material"))
    material.GetInput("texture").GetAttr().SetColorSpace("raw")
    # Use the same invert/separate/conditional/combine topology as the public
    # library, but author it locally so changing each flip is independently seen.
    def node(name, shader_id):
        return _node(stage, name, shader_id)
    image = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/image"))
    invert = node("invert", "ND_invert_vector3")
    invert.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(image.GetOutput("out"))
    direct = node("separate", "ND_separate3_vector3")
    direct.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(image.GetOutput("out"))
    reverse = node("separate_inverted", "ND_separate3_vector3")
    reverse.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(invert.GetOutput("out"))
    combine = node("combine", "ND_combine3_vector3")
    for index, (axis, flip) in enumerate(zip("xyz", flips)):
        output = "out" + axis
        direct.CreateOutput(output, Sdf.ValueTypeNames.Float)
        reverse.CreateOutput(output, Sdf.ValueTypeNames.Float)
        choose = node("flip_" + axis, "ND_ifequal_floatB")
        choose.CreateInput("value1", Sdf.ValueTypeNames.Bool).Set(flip)
        choose.CreateInput("value2", Sdf.ValueTypeNames.Bool).Set(True)
        choose.CreateInput("in1", Sdf.ValueTypeNames.Float).ConnectToSource(reverse.GetOutput(output))
        choose.CreateInput("in2", Sdf.ValueTypeNames.Float).ConnectToSource(direct.GetOutput(output))
        combine.CreateInput(f"in{index + 1}", Sdf.ValueTypeNames.Float).ConnectToSource(choose.GetOutput("out"))
    normal = node("normal", "ND_normalmap")
    normal.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(combine.GetOutput("out"))
    normal.CreateInput("scale", Sdf.ValueTypeNames.Float).Set(.4)
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    surface.CreateInput("geometry_normal", Sdf.ValueTypeNames.Float3).ConnectToSource(normal.GetOutput("out"))
    result = resolve_input(surface.GetInput("geometry_normal"))
    sample = (.1, .7, .9)
    expected = [(2 * (1 - value if flip else value) - 1) * strength
                for value, flip, strength in zip(sample, flips, (.4, .4, 1))]
    actual = [sample[i] * result.scale[i] + result.bias[i] for i in range(3)]
    assert actual == pytest.approx(expected)
    assert result.channel == "rgb" and result.colorspace == "raw"
    assert result.uvscale == (3, 2) and result.uvoffset == (-.25, .5)


def test_material_interface_cannot_hide_unsupported_or_animated_inputs(material):
    stage, _ = material
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    material = UsdShade.Material(stage.GetPrimAtPath("/Looks/Material"))
    before = stage.GetRootLayer().ExportToString()
    texture_input = material.GetInput("texture")
    texture_input.Set(Sdf.AssetPath("animated.png"), 2)
    with pytest.raises(ValueError, match="animated material input"):
        resolve_input(surface.GetInput("base_color"))
    texture_input.GetAttr().ClearAtTime(2)
    material.GetInput("texture").GetAttr().SetColorSpace("acescg")
    with pytest.raises(ValueError, match="unsupported texture color space"):
        resolve_input(surface.GetInput("base_color"))
    stage.GetRootLayer().ImportFromString(before)
    image = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/image"))
    image.CreateIdAttr("ND_noise3d_color3")
    with pytest.raises(ValueError, match="requires baking|bake it"):
        resolve_input(surface.GetInput("base_color"))


def test_colored_opacity_texture_is_refused_without_authored_changes(material):
    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization.materialx_preview import cook_stage

    stage, _ = material
    mat = UsdShade.Material(stage.GetPrimAtPath("/Looks/Material"))
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    image = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/image"))
    surface.CreateIdAttr("ND_standard_surface_surfaceshader")
    surface.CreateInput("opacity", Sdf.ValueTypeNames.Color3f).ConnectToSource(image.GetOutput("out"))
    mat.CreateSurfaceOutput("mtlx").ConnectToSource(surface.GetOutput("out"))
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(ValueError, match="opacity|scalar"):
        cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before


def test_image_constant_border_is_not_replaced_with_black(material):
    stage, _ = material
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    image = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/image"))
    image.CreateIdAttr("ND_image_color3")
    image.CreateInput("uaddressmode", Sdf.ValueTypeNames.String).Set("constant")
    with pytest.raises(ValueError, match="address mode"):
        resolve_input(surface.GetInput("base_color"))


def test_legacy_object_space_normal_is_refused_atomically(material):
    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization.materialx_preview import cook_stage

    stage, _ = material
    mat = UsdShade.Material(stage.GetPrimAtPath("/Looks/Material"))
    surface = UsdShade.Shader(stage.GetPrimAtPath("/Looks/Material/surface"))
    normal = UsdShade.Shader.Define(stage, "/Looks/Material/Normal")
    normal.CreateIdAttr("ND_normalmap")
    normal.CreateInput("in", Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(.2, .4, 1))
    space = mat.CreateInput("normalSpace", Sdf.ValueTypeNames.String)
    space.Set("object")
    normal.CreateInput("space", Sdf.ValueTypeNames.String).ConnectToSource(space)
    surface.CreateInput("geometry_normal", Sdf.ValueTypeNames.Float3).ConnectToSource(
        normal.CreateOutput("out", Sdf.ValueTypeNames.Float3))
    mat.CreateSurfaceOutput("mtlx").ConnectToSource(surface.GetOutput("out"))
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(ValueError, match="object-space normal map"):
        cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before
    # The newer definition has no space port; an unused custom property does
    # not turn its tangent-space normal mapping into object-space mapping.
    normal.CreateIdAttr("ND_normalmap_float")
    assert cook_stage(stage) == 1


def test_generated_texture_paths_follow_the_edit_layer_and_relocated_package(tmp_path):
    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization.materialx_preview import cook_stage

    package = tmp_path / "original"
    for name in ("assets", "overrides", "textures"):
        (package / name).mkdir(parents=True)
    (package / "textures" / "color.png").write_bytes(b"test resolver only")
    source = Usd.Stage.CreateNew(str(package / "assets" / "material.usda"))
    mat = UsdShade.Material.Define(source, "/Material")
    image = UsdShade.Shader.Define(source, "/Material/Image")
    image.CreateIdAttr("ND_image_color3")
    image.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath("../textures/color.png"))
    surface = UsdShade.Shader.Define(source, "/Material/OpenPBR")
    surface.CreateIdAttr("ND_open_pbr_surface_surfaceshader")
    surface.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        image.CreateOutput("out", Sdf.ValueTypeNames.Color3f))
    mat.CreateSurfaceOutput("mtlx").ConnectToSource(surface.CreateOutput("out", Sdf.ValueTypeNames.Token))
    source.GetRootLayer().Save()
    edits = Sdf.Layer.CreateNew(str(package / "overrides" / "optimized.usda"))
    stage = Usd.Stage.CreateNew(str(package / "scene.usda"))
    stage.GetRootLayer().subLayerPaths = ["overrides/optimized.usda", "assets/material.usda"]
    stage.SetEditTarget(edits)
    assert cook_stage(stage) == 1
    edits.Save()
    stage.GetRootLayer().Save()

    relocated = tmp_path / "relocated"
    shutil.copytree(package, relocated)
    reopened = Usd.Stage.Open(str(relocated / "scene.usda"))
    preview, _, _ = UsdShade.Material(reopened.GetPrimAtPath("/Material")).ComputeSurfaceSource()
    texture_source, _, _ = preview.GetInput("diffuseColor").GetConnectedSource()
    file = UsdShade.Shader(texture_source.GetPrim()).GetInput("file").Get()
    assert file.path == "../textures/color.png"
    assert file.resolvedPath.replace("\\", "/") == (relocated / "textures" / "color.png").as_posix()

    anonymous = Usd.Stage.CreateInMemory()
    anonymous.OverridePrim("/Material").GetReferences().AddReference(
        str(package / "assets" / "material.usda"), "/Material")
    assert cook_stage(anonymous) == 1
    preview, _, _ = UsdShade.Material(anonymous.GetPrimAtPath("/Material")).ComputeSurfaceSource()
    texture_source, _, _ = preview.GetInput("diffuseColor").GetConnectedSource()
    file = UsdShade.Shader(texture_source.GetPrim()).GetInput("file").Get()
    assert file.path.replace("\\", "/") == (package / "textures" / "color.png").as_posix()

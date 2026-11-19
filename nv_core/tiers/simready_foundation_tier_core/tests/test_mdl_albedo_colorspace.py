# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""MDL albedo encoding does not weaken normal/data or other-color validation."""

import pytest
from pxr import Sdf, Usd, UsdShade
from simready.foundation.tier_core.rules_and_reqs.visualization.materials.validation import (
    VisualMaterialsCapabilityChecker,
)


def mdl_stage(name, colorspace, path="./texture.png"):
    stage = Usd.Stage.CreateInMemory()
    shader = UsdShade.Shader.Define(stage, "/Asset/Material/Shader")
    shader.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
    shader.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    attr = shader.CreateInput(name, Sdf.ValueTypeNames.Asset).GetAttr()
    attr.Set(Sdf.AssetPath(str(path)))
    if colorspace is not None:
        attr.SetColorSpace(colorspace)
    return stage, shader


def errors(stage, shader, method):
    checker = VisualMaterialsCapabilityChecker(False, False, False)
    return getattr(checker, method)(stage, shader.GetPath())


@pytest.fixture(params=["check_vm_tex_002_colorspace", "check_vm_tex_005_colorspace"])
def method(request):
    return request.param


@pytest.mark.parametrize(
    "value", ["raw", "sRGB", "auto", None, "none", "srgb_rec709_scene"]
)
def test_albedo_accepts_valid_authored_encoding(method, value):
    stage, shader = mdl_stage("diffuse_texture", value)
    assert not errors(stage, shader, method)


def test_albedo_rejects_unknown_encoding(method):
    stage, shader = mdl_stage("diffuse_texture", "not_a_colorspace")
    assert errors(stage, shader, method)


@pytest.mark.parametrize(
    "name",
    [
        "normalmap_texture",
        "reflectionroughness_texture",
        "metallic_texture",
        "ORM_texture",
    ],
)
@pytest.mark.parametrize("value,failed", [("raw", False), ("sRGB", True)])
def test_data_checks_are_preserved(method, name, value, failed):
    stage, shader = mdl_stage(name, value)
    assert bool(errors(stage, shader, method)) == failed


@pytest.mark.parametrize(
    "name",
    ["emissive_color_texture", "glass_color_texture", "reflection_color_texture"],
)
def test_other_color_inputs_remain_srgb(method, name):
    stage, shader = mdl_stage(name, "raw")
    assert errors(stage, shader, method)


@pytest.mark.parametrize("value", [None, "auto"])
def test_legacy_and_current_unauthored_data_behavior(tmp_path, value):
    from PIL import Image

    path = tmp_path / "normal.png"
    Image.new("RGB", (2, 2), (128, 128, 255)).save(path)
    stage, shader = mdl_stage("normalmap_texture", value, path)
    assert not errors(stage, shader, "check_vm_tex_002_colorspace")
    assert errors(stage, shader, "check_vm_tex_005_colorspace")


def test_non_mdl_shader_is_out_of_scope(method):
    stage, shader = mdl_stage("normalmap_texture", "sRGB")
    shader.GetPrim().RemoveProperty("info:mdl:sourceAsset")
    shader.GetPrim().RemoveProperty("info:mdl:sourceAsset:subIdentifier")
    shader.CreateImplementationSourceAttr().Set("id")
    shader.CreateIdAttr("UsdPreviewSurface")
    assert not errors(stage, shader, method)

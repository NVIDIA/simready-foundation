# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Release regressions: guide curves, linear albedo and visual-only semantics."""

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics, UsdShade
from usd_validation_nvidia._compliance_checker import ComplianceChecker
from simready.foundation.tier_core import requirements as cap
from simready.foundation.tier_core.rules_and_reqs.semantic_labels.validation import (
    SemanticLabelsMaterialChecker,
)
from simready.foundation.tier_core.rules_and_reqs.visualization.materials.validation import (
    VisualMaterialsCapabilityChecker,
)


def stage_and_mesh():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Asset/Mesh")
    return stage, mesh


def visual(stage, path="/Asset/Looks/Visual"):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Surface")
    shader.CreateIdAttr("UsdPreviewSurface")
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material, shader


def issues(stage, checker_type, code):
    engine = ComplianceChecker()
    engine.AddRule(checker_type)
    assert len(engine.rules) == 1, [i.message for i in engine.issues]
    assert not engine.issues
    engine.check(stage)
    assert not [i for i in engine.issues if i.requirement is None]
    return [i for i in engine.issues if i.requirement == code]


@pytest.mark.parametrize(
    "label_state,expected_codes",
    [
        ("missing", {cap.SemanticLabelsRequirements.SL_MAT_001}),
        ("sampled", {cap.SemanticLabelsRequirements.SL_TIME_001}),
        ("static", set()),
    ],
)
def test_material_semantics_through_engine(label_state, expected_codes):
    """A checker that cannot initialize must never look like a semantic pass."""
    stage, mesh = stage_and_mesh()
    material, _ = visual(stage)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    if label_state != "missing":
        material.GetPrim().AddAppliedSchema("SemanticsLabelsAPI:material")
        attr = material.GetPrim().CreateAttribute(
            "semantics:labels:material", Sdf.ValueTypeNames.TokenArray
        )
        attr.Set(["metal"])
        if label_state == "sampled":
            attr.Set(["metal"], Usd.TimeCode(1))
            attr.Set(["plastic"], Usd.TimeCode(2))

    engine = ComplianceChecker()
    engine.AddRule(SemanticLabelsMaterialChecker)
    assert len(engine.rules) == 1, [i.message for i in engine.issues]
    assert not engine.issues
    engine.check(stage)
    assert {i.requirement for i in engine.issues} == expected_codes


@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize(
    "purpose,should_fail",
    [("guide", False), ("proxy", False), ("default", True), ("render", True)],
)
def test_unbound_curves_use_computed_purpose(inherited, purpose, should_fail):
    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/Asset")
    curve = UsdGeom.BasisCurves.Define(stage, "/Asset/Grasp")
    (parent if inherited else curve).CreatePurposeAttr(purpose)
    assert (
        bool(
            issues(
                stage,
                VisualMaterialsCapabilityChecker,
                cap.MaterialsRequirements.VM_MAT_001,
            )
        )
        == should_fail
    )


@pytest.mark.parametrize(
    "token,should_fail",
    [
        ("raw", False),
        ("sRGB", False),
        ("auto", False),
        (None, False),
        ("linear", True),
        ("srgb_rec709_scene", True),
    ],
)
def test_preview_albedo_encoding(token, should_fail):
    stage, _ = texture_stage(token, ["diffuseColor"])
    assert (
        bool(
            issues(
                stage,
                VisualMaterialsCapabilityChecker,
                cap.MaterialsRequirements.VM_TEX_003,
            )
        )
        == should_fail
    )


def texture_stage(token, roles):
    stage, _ = stage_and_mesh()
    material, surface = visual(stage)
    reader = UsdShade.Shader.Define(stage, str(material.GetPath()) + "/Texture")
    reader.CreateIdAttr("UsdUVTexture")
    reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set("./texture.png")
    if token is not None:
        reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(token)
    reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
    for role in roles:
        vector = role in ("diffuseColor", "emissiveColor", "specularColor", "normal")
        surface.CreateInput(
            role, Sdf.ValueTypeNames.Float3 if vector else Sdf.ValueTypeNames.Float
        ).ConnectToSource(reader.ConnectableAPI(), "rgb" if vector else "r")
    return stage, reader


@pytest.mark.parametrize("role", ["normal", "roughness", "metallic", "opacity"])
@pytest.mark.parametrize("token,should_fail", [("raw", False), ("sRGB", True)])
def test_data_texture_checks_remain(role, token, should_fail):
    stage, _ = texture_stage(token, [role])
    assert (
        bool(
            issues(
                stage,
                VisualMaterialsCapabilityChecker,
                cap.MaterialsRequirements.VM_TEX_003,
            )
        )
        == should_fail
    )


@pytest.mark.parametrize("token,should_fail", [("raw", False), ("sRGB", True)])
def test_shared_albedo_and_data_reader(token, should_fail):
    stage, _ = texture_stage(token, ["diffuseColor", "roughness", "metallic"])
    assert (
        bool(
            issues(
                stage,
                VisualMaterialsCapabilityChecker,
                cap.MaterialsRequirements.VM_TEX_003,
            )
        )
        == should_fail
    )


@pytest.mark.parametrize("role", ["emissiveColor", "specularColor"])
def test_raw_albedo_allowance_does_not_relax_other_colors(role):
    stage, _ = texture_stage("raw", ["diffuseColor", role])
    assert issues(
        stage, VisualMaterialsCapabilityChecker, cap.MaterialsRequirements.VM_TEX_003
    )


def test_auto_rgb_normal_still_fails(tmp_path):
    from PIL import Image

    path = tmp_path / "normal.png"
    Image.new("RGB", (2, 2), (128, 128, 255)).save(path)
    stage, reader = texture_stage("auto", ["normal"])
    reader.GetInput("file").Set(str(path))
    assert issues(
        stage, VisualMaterialsCapabilityChecker, cap.MaterialsRequirements.VM_TEX_003
    )


def test_physics_only_and_unused_materials_need_no_label():
    stage, mesh = stage_and_mesh()
    material = UsdShade.Material.Define(stage, "/Asset/PhysicsMaterial")
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(
        material, materialPurpose="physics"
    )
    visual(stage)  # unused visual library material
    assert not issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_MAT_001
    )


@pytest.mark.parametrize("purpose", ["", "full", "preview"])
def test_render_binding_requires_label_even_with_physics_api(purpose):
    stage, mesh = stage_and_mesh()
    material, _ = visual(stage)
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(
        material, materialPurpose=purpose
    )
    assert issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_MAT_001
    )
    material.GetPrim().AddAppliedSchema("SemanticsLabelsAPI:material")
    material.GetPrim().CreateAttribute(
        "semantics:labels:material", Sdf.ValueTypeNames.TokenArray
    ).Set(["metal"])
    assert not issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_MAT_001
    )


@pytest.mark.parametrize("purpose", ["guide", "proxy"])
def test_nonrendered_geometry_materials_need_no_label(purpose):
    stage, mesh = stage_and_mesh()
    material, _ = visual(stage)
    UsdGeom.Imageable(stage.GetDefaultPrim()).CreatePurposeAttr(purpose)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    assert not issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_MAT_001
    )


def test_material_bind_subset_requires_label():
    stage, mesh = stage_and_mesh()
    material, _ = visual(stage)
    binding = UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim())
    subset = binding.CreateMaterialBindSubset("Faces", [0])
    UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(material)
    assert issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_MAT_001
    )


def test_instance_proxy_geometry_is_in_scope():
    stage, _ = stage_and_mesh()
    stage.RemovePrim("/Asset/Mesh")
    source = UsdGeom.Xform.Define(stage, "/Library")
    mesh = UsdGeom.Mesh.Define(stage, "/Library/Mesh")
    material, _ = visual(stage)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    instance = stage.DefinePrim("/Asset/Part", "Xform")
    instance.GetReferences().AddInternalReference(source.GetPath())
    instance.SetInstanceable(True)
    assert stage.GetPrimAtPath("/Asset/Part/Mesh").IsInstanceProxy()
    assert issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_MAT_001
    )


def test_material_scope_cache_resets_after_purpose_change():
    stage, mesh = stage_and_mesh()
    material, _ = visual(stage)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    checker = SemanticLabelsMaterialChecker(False, False, False)
    checker.CheckStage(stage)
    assert checker._is_visual_material(material.GetPrim())
    mesh.CreatePurposeAttr("guide")
    checker.ResetCaches()
    assert not checker._is_visual_material(material.GetPrim())


def test_static_label_rule_still_applies_to_physics_material():
    stage, _ = stage_and_mesh()
    material = UsdShade.Material.Define(stage, "/Asset/PhysicsMaterial")
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    material.GetPrim().AddAppliedSchema("SemanticsLabelsAPI:material")
    attr = material.GetPrim().CreateAttribute(
        "semantics:labels:material", Sdf.ValueTypeNames.TokenArray
    )
    attr.Set(["metal"], Usd.TimeCode(1))
    assert issues(
        stage, SemanticLabelsMaterialChecker, cap.SemanticLabelsRequirements.SL_TIME_001
    )


@pytest.mark.parametrize(
    "api", [UsdPhysics.RigidBodyAPI, UsdPhysics.CollisionAPI, UsdPhysics.MassAPI]
)
@pytest.mark.parametrize("units", [None, 1.0, 0.001])
def test_physics_units_must_be_authored(api, units):
    from simready.foundation.tier_core.rules_and_reqs.core.units.validation import (
        KilogramsPerUnitChecker,
    )

    stage, mesh = stage_and_mesh()
    api.Apply(mesh.GetPrim())
    if units is not None:
        UsdPhysics.SetStageKilogramsPerUnit(stage, units)
    checker = KilogramsPerUnitChecker(False, False, False)
    checker.CheckStage(stage)
    assert bool(checker.GetIssues()) == (units is None)


def test_nonphysics_stage_does_not_require_mass_units():
    from simready.foundation.tier_core.rules_and_reqs.core.units.validation import (
        KilogramsPerUnitChecker,
    )

    stage, _ = stage_and_mesh()
    checker = KilogramsPerUnitChecker(False, False, False)
    checker.CheckStage(stage)
    assert not checker.GetIssues()

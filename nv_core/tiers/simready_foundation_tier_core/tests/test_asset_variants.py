# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the AssetVariants contract (AV.001-AV.010) against real composed USD.

The asset is built the way the conform skills author one: a per-part
``Representation_body`` variant set on the default prim whose options each bring
their representation in through an isolated payload, plus discovery metadata
under ``customLayerData.SimReady_Metadata``. Each test then mutates one aspect to
prove the matching checker fails.
"""

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from simready.foundation.tier_core import asset_variants as av
from simready.foundation.tier_core.rules_and_reqs.core.asset_variants.validation import (
    AuthoredPhysicalPropertiesChecker,
    CollisionEnvelopeInvariantChecker,
    ConditionalPresenceChecker,
    ImpactClassHonestyChecker,
    VariationDiscoveryMetadataChecker,
    VariationOptionComposabilityChecker,
    VariationSectionPurityChecker,
    VariationStabilityChecker,
    VariationVariantSetChecker,
    VisualEnvelopeInvariantChecker,
)


def _payload_layer(path: Path, size: float, *, geo_type: str = "Cube",
                   content_translate=None) -> str:
    """Write a payload layer whose default prim holds a geometry child.

    ``geo_type`` selects the child prim's type (``Cube`` or ``Sphere``) and
    ``content_translate`` optionally authors a translate on the default prim, so a
    test can make one option change the varied prim's type or transform (AV.010).
    """
    layer = Sdf.Layer.CreateNew(str(path))
    stage = Usd.Stage.Open(layer)
    content = UsdGeom.Xform.Define(stage, "/Content")
    stage.SetDefaultPrim(content.GetPrim())
    if content_translate is not None:
        content.AddTranslateOp().Set(content_translate)
    if geo_type == "Sphere":
        sphere = UsdGeom.Sphere.Define(stage, "/Content/Geo")
        sphere.GetRadiusAttr().Set(size / 2.0)
    else:
        cube = UsdGeom.Cube.Define(stage, "/Content/Geo")
        cube.GetSizeAttr().Set(size)
    stage.GetRootLayer().Save()
    return str(path)


def _make_representation_asset(tmp_path: Path, *, sizes=(2.0, 2.0), impact="visual-only",
                               category="Representation", set_name="Representation_body",
                               default="Mesh", declare_metadata=True,
                               splat_geo_type="Cube", splat_translate=None):
    """A conformant per-part Representation asset, parameterized for negative tests."""
    mesh_payload = _payload_layer(tmp_path / "rep_mesh.usda", sizes[0])
    splat_payload = _payload_layer(tmp_path / "rep_splat.usda", sizes[1],
                                   geo_type=splat_geo_type, content_translate=splat_translate)

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    vset = root.GetVariantSets().AddVariantSet(set_name)
    for option, payload in (("Mesh", mesh_payload), ("Splat", splat_payload)):
        vset.AddVariant(option)
        vset.SetVariantSelection(option)
        with vset.GetVariantEditContext():
            root.GetPayloads().AddPayload(payload)
    vset.SetVariantSelection(default)

    if declare_metadata:
        stage.GetRootLayer().customLayerData = {
            av.SIMREADY_METADATA_KEY: {
                av.VARIANTS_KEY: {
                    category: {
                        set_name: {
                            "prim": "/Asset",
                            "variantSetName": set_name,
                            "category": category,
                            "default": default,
                            "impactClass": impact,
                        }
                    }
                }
            }
        }
    return stage, root


def _issues(checker_cls, stage):
    checker = checker_cls()
    checker.CheckStage(stage)
    return checker.GetIssues()


ALL_CHECKERS = [
    VariationDiscoveryMetadataChecker,
    VariationVariantSetChecker,
    VariationOptionComposabilityChecker,
    VariationSectionPurityChecker,
    VisualEnvelopeInvariantChecker,
    CollisionEnvelopeInvariantChecker,
    ImpactClassHonestyChecker,
    ConditionalPresenceChecker,
    AuthoredPhysicalPropertiesChecker,
    VariationStabilityChecker,
]


def test_conformant_representation_passes_every_checker(tmp_path):
    stage, _ = _make_representation_asset(tmp_path)
    for checker_cls in ALL_CHECKERS:
        assert not _issues(checker_cls, stage), f"{checker_cls.__name__} should pass a conformant asset"


def test_empty_asset_passes_every_checker():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    for checker_cls in ALL_CHECKERS:
        assert not _issues(checker_cls, stage), f"{checker_cls.__name__} must not flag an asset with no variations"


def test_variant_set_without_metadata_fails_discovery(tmp_path):
    stage, _ = _make_representation_asset(tmp_path, declare_metadata=False)
    assert _issues(VariationDiscoveryMetadataChecker, stage)


def test_default_selection_not_an_option_fails_discovery(tmp_path):
    stage, _ = _make_representation_asset(tmp_path, default="Mesh")
    data = stage.GetRootLayer().customLayerData
    data[av.SIMREADY_METADATA_KEY][av.VARIANTS_KEY]["Representation"]["Representation_body"]["default"] = "Nonexistent"
    stage.GetRootLayer().customLayerData = data
    assert _issues(VariationDiscoveryMetadataChecker, stage)


def test_reserved_physics_bucket_is_ignored(tmp_path):
    # Physics is owned by runtime_variants; the asset-variation reader excludes it,
    # so a Physics bucket alongside a conformant Representation must not trip AV.001.
    stage, _ = _make_representation_asset(tmp_path)
    data = stage.GetRootLayer().customLayerData
    data[av.SIMREADY_METADATA_KEY][av.VARIANTS_KEY][av.RESERVED_CATEGORY] = {
        "Physics": {"prim": "/Asset", "variantSetName": "Physics", "category": "Physics",
                    "default": "Disabled", "impactClass": "simulation-affecting"}
    }
    stage.GetRootLayer().customLayerData = data
    assert not _issues(VariationDiscoveryMetadataChecker, stage)


def test_envelope_breaking_option_fails_visual_invariant(tmp_path):
    stage, _ = _make_representation_asset(tmp_path, sizes=(2.0, 4.0))
    assert _issues(VisualEnvelopeInvariantChecker, stage)


def test_single_option_set_fails_conditional_presence(tmp_path):
    # A variation set with a single option must be flagged (AV.008).
    stage2 = Usd.Stage.CreateInMemory()
    r2 = UsdGeom.Xform.Define(stage2, "/Asset").GetPrim()
    stage2.SetDefaultPrim(r2)
    payload = _payload_layer(tmp_path / "solo.usda", 2.0)
    vs = r2.GetVariantSets().AddVariantSet("Representation_body")
    vs.AddVariant("Only")
    vs.SetVariantSelection("Only")
    with vs.GetVariantEditContext():
        r2.GetPayloads().AddPayload(payload)
    stage2.GetRootLayer().customLayerData = {
        av.SIMREADY_METADATA_KEY: {av.VARIANTS_KEY: {"Representation": {
            "Representation_body": {"prim": "/Asset", "variantSetName": "Representation_body",
                                     "category": "Representation", "default": "Only",
                                     "impactClass": "visual-only"}}}}}
    assert _issues(ConditionalPresenceChecker, stage2)


def test_visual_only_that_changes_collision_fails_impact_honesty(tmp_path):
    # Mesh option applies a real UsdPhysics.CollisionAPI, Splat does not: the physics
    # fingerprint differs across options, so a visual-only declaration is dishonest.
    big = tmp_path / "with_collider.usda"
    layer = Sdf.Layer.CreateNew(str(big))
    s = Usd.Stage.Open(layer)
    content = UsdGeom.Xform.Define(s, "/Content")
    s.SetDefaultPrim(content.GetPrim())
    geo = UsdGeom.Cube.Define(s, "/Content/Geo")
    geo.GetSizeAttr().Set(2.0)
    UsdPhysics.CollisionAPI.Apply(geo.GetPrim())
    s.GetRootLayer().Save()
    plain = _payload_layer(tmp_path / "plain.usda", 2.0)

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    vset = root.GetVariantSets().AddVariantSet("Representation_body")
    for option, payload in (("Mesh", str(big)), ("Splat", plain)):
        vset.AddVariant(option)
        vset.SetVariantSelection(option)
        with vset.GetVariantEditContext():
            root.GetPayloads().AddPayload(payload)
    vset.SetVariantSelection("Mesh")
    stage.GetRootLayer().customLayerData = {
        av.SIMREADY_METADATA_KEY: {av.VARIANTS_KEY: {"Representation": {
            "Representation_body": {"prim": "/Asset", "variantSetName": "Representation_body",
                                     "category": "Representation", "default": "Mesh",
                                     "impactClass": "visual-only"}}}}}
    assert _issues(ImpactClassHonestyChecker, stage)


def test_type_change_across_options_fails_stability(tmp_path):
    # One option composes /Asset/Geo as a Cube, the other as a Sphere: a shared
    # prim changes its type across the set's options (the renderer-ghost hazard).
    stage, _ = _make_representation_asset(tmp_path, splat_geo_type="Sphere")
    assert _issues(VariationStabilityChecker, stage)


def test_transform_change_across_options_fails_stability(tmp_path):
    # One option authors a translate on the varied prim and the other does not, so
    # the part's composed transform differs across options (a dropped pose).
    stage, _ = _make_representation_asset(tmp_path, splat_translate=(0.0, 0.0, 1.0))
    assert _issues(VariationStabilityChecker, stage)

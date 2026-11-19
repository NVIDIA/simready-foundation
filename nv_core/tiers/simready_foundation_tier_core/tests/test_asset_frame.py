# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise facing contracts against real composed USD data."""

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom
from simready.foundation.tier_core.asset_frame import (
    FORWARD_DIRECTION as NAME,
    author_forward_direction,
    read_forward_direction,
    world_forward_direction,
    facing_camera_transform,
)
from simready.foundation.tier_core.rules_and_reqs.core.asset_frame.validation import AssetFrameChecker


def asset():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    return stage, root


def issues(stage):
    checker = AssetFrameChecker()
    checker.CheckStage(stage)
    for prim in stage.Traverse():
        checker.CheckPrim(prim)
    return checker.GetIssues()


def test_valid_direction_needs_no_custom_up():
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    assert not root.HasProperty("simready:assetFrame:upDirection")
    assert not issues(stage)


@pytest.mark.parametrize("vector", [(0, 0, 0), (2, 0, 0), (0.99, 0, 0), (float("nan"), 0, 0), (float("inf"), 0, 0)])
def test_reject_invalid_authored_vector(vector):
    stage, root = asset()
    root.CreateAttribute(NAME, Sdf.ValueTypeNames.Vector3f, custom=True, variability=Sdf.VariabilityUniform).Set(
        Gf.Vec3f(vector)
    )
    assert issues(stage)[0].requirement.code == "com.nvidia.simready.AF.001"


@pytest.mark.parametrize(
    "kind", ["missing", "blocked", "wrong_type", "varying", "sampled", "connected", "relationship", "not_custom"]
)
def test_reject_invalid_property(kind):
    stage, root = asset()
    if kind == "relationship":
        root.CreateRelationship(NAME)
    elif kind != "missing":
        attr = root.CreateAttribute(
            NAME,
            Sdf.ValueTypeNames.Float3 if kind == "wrong_type" else Sdf.ValueTypeNames.Vector3f,
            custom=kind != "not_custom",
            variability=Sdf.VariabilityVarying if kind == "varying" else Sdf.VariabilityUniform,
        )
        attr.Set(Gf.Vec3f(1, 0, 0))
        if kind == "blocked":
            attr.Block()
        if kind == "sampled":
            attr.Set(Gf.Vec3f(0, 1, 0), 1)
        if kind == "connected":
            attr.SetConnections([Sdf.Path("/Asset.other")])
    assert issues(stage)


def test_missing_default_prim_fails():
    stage, root = asset()
    stage.ClearDefaultPrim()
    assert issues(stage)


def test_no_namespace_inheritance_and_component_override():
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    child = UsdGeom.Xform.Define(stage, "/Asset/Part").GetPrim()
    with pytest.raises(ValueError):
        read_forward_direction(child)
    author_forward_direction(child, (0, 1, 0))
    assert read_forward_direction(root) == Gf.Vec3f(1, 0, 0)
    assert read_forward_direction(child) == Gf.Vec3f(0, 1, 0)
    assert not issues(stage)
    child.GetAttribute(NAME).Set(Gf.Vec3f(3, 0, 0))
    assert len(issues(stage)) == 1


def test_reference_and_instance_composition():
    source, root = asset()
    author_forward_direction(root, (1, 0, 0))
    part = UsdGeom.Xform.Define(source, "/Asset/Part").GetPrim()
    author_forward_direction(part, (0, 1, 0))
    stage, target = asset()
    target.GetReferences().AddReference(source.GetRootLayer().identifier)
    target.SetInstanceable(True)
    assert read_forward_direction(target) == Gf.Vec3f(1, 0, 0)
    proxy = stage.GetPrimAtPath("/Asset/Part")
    assert proxy.IsInstanceProxy()
    assert read_forward_direction(proxy) == Gf.Vec3f(0, 1, 0)


def test_world_rotation_translation_and_nonuniform_scale():
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    x = UsdGeom.Xformable(root)
    x.AddTranslateOp().Set((10, 20, 30))
    x.AddRotateZOp().Set(90)
    x.AddScaleOp().Set((3, 2, 1))
    assert world_forward_direction(root) == pytest.approx((0, 1, 0), abs=1e-6)
    camera = facing_camera_transform(root, 2)
    assert camera.ExtractTranslation() == pytest.approx((10, 22, 30), abs=1e-6)
    assert camera.TransformDir(Gf.Vec3d(0, 0, -1)) == pytest.approx((0, -1, 0), abs=1e-6)


def test_reset_stack_and_reflection():
    stage, root = asset()
    UsdGeom.Xformable(root).AddRotateZOp().Set(90)
    part = UsdGeom.Xform.Define(stage, "/Asset/Part")
    part.SetResetXformStack(True)
    part.AddScaleOp().Set((-1, 1, 1))
    author_forward_direction(part.GetPrim(), (1, 0, 0))
    assert world_forward_direction(part.GetPrim()) == Gf.Vec3d(-1, 0, 0)


def test_degenerate_transform_fails():
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    UsdGeom.Xformable(root).AddScaleOp().Set((0, 1, 1))
    with pytest.raises(ValueError, match="degenerate"):
        world_forward_direction(root)


def test_vertical_facing_is_valid_but_camera_roll_requires_intent():
    stage, root = asset()
    author_forward_direction(root, (0, 0, 1))
    assert not issues(stage)
    with pytest.raises(ValueError, match="parallel"):
        facing_camera_transform(root, 2)


@pytest.mark.parametrize("distance", [0, -1, float("nan"), float("inf")])
def test_invalid_camera_distance(distance):
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    with pytest.raises(ValueError):
        facing_camera_transform(root, distance)


def test_y_up_camera():
    stage, root = asset()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    author_forward_direction(root, (0, 0, 1))
    camera = facing_camera_transform(root, 2)
    assert camera.ExtractTranslation() == Gf.Vec3d(0, 0, 2)
    assert camera.TransformDir(Gf.Vec3d(0, 1, 0)) == Gf.Vec3d(0, 1, 0)


@pytest.mark.parametrize("extension", ["usda", "usdc"])
def test_facing_survives_layer_round_trip(tmp_path, extension):
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    path = tmp_path / f"facing.{extension}"
    stage.GetRootLayer().Export(str(path))
    reopened = Usd.Stage.Open(str(path))
    assert read_forward_direction(reopened.GetDefaultPrim()) == Gf.Vec3f(1, 0, 0)
    assert not issues(reopened)


def test_checker_validates_instance_proxy_declarations():
    source, root = asset()
    author_forward_direction(root, (1, 0, 0))
    part = UsdGeom.Xform.Define(source, "/Asset/Part").GetPrim()
    author_forward_direction(part, (0, 1, 0))
    part.GetAttribute(NAME).Set(Gf.Vec3f(3, 0, 0))
    stage, target = asset()
    target.GetReferences().AddReference(source.GetRootLayer().identifier)
    target.SetInstanceable(True)
    assert len(issues(stage)) == 1


def test_nonfinite_camera_origin_fails():
    stage, root = asset()
    author_forward_direction(root, (1, 0, 0))
    UsdGeom.Xformable(root).AddTranslateOp().Set((float("nan"), 0, 0))
    with pytest.raises(ValueError):
        facing_camera_transform(root, 2)

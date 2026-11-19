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
import importlib
import sys
import types

import pytest
from pxr import Gf, Usd, UsdGeom


@pytest.fixture
def grasp_module(monkeypatch):
    decorator = types.ModuleType("simready.evaluate.core.decorator")
    decorator.test = lambda **_kwargs: lambda function: function
    monkeypatch.setitem(sys.modules, "simready.evaluate.core.decorator", decorator)
    return importlib.import_module("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_and_lift")


def _asset_stage():
    stage = Usd.Stage.CreateInMemory()
    mount = UsdGeom.Xform.Define(stage, "/World/Asset")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset/Body")
    asset.AddScaleOp().Set(Gf.Vec3f(0.5))
    cube = UsdGeom.Cube.Define(stage, "/World/Asset/Body/Geometry")
    cube.CreateSizeAttr(2.0)
    return stage, mount, asset


@pytest.mark.parametrize("purpose", [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
def test_ground_placement_preserves_child_scale_and_existing_offset_formula(grasp_module, purpose):
    stage, mount, asset = _asset_stage()
    stage.GetPrimAtPath("/World/Asset/Body/Geometry").GetAttribute("purpose").Set(purpose)
    scale_before = asset.GetPrim().GetAttribute("xformOp:scale").Get()
    grasp_module._place_asset_on_ground(stage, "/World/Asset/Body", margin=0.01)
    ordered = mount.GetOrderedXformOps()
    assert len(ordered) == 1
    assert ordered[0].Get() == Gf.Vec3d(0, 0, 0.51)
    assert asset.GetPrim().GetAttribute("xformOp:scale").Get() == scale_before
    bound = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [purpose]).ComputeWorldBound(asset.GetPrim()).ComputeAlignedBox()
    assert bound.GetMin()[2] == pytest.approx(0.01)


@pytest.mark.parametrize("path", ["/Missing", "/World/Empty"])
def test_missing_or_empty_ground_placement_geometry_is_a_setup_error(grasp_module, path):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World/Empty")
    with pytest.raises(RuntimeError, match="ground-placement asset"):
        grasp_module._place_asset_on_ground(stage, path)


@pytest.mark.parametrize(
    "minimum, maximum",
    [
        ((0.0, 0.0, float("nan")), (1.0, 1.0, 1.0)),
        ((0.0, 0.0, 0.0), (1.0, float("inf"), 1.0)),
        ((False, 0.0, 0.0), (1.0, 1.0, 1.0)),
        (("0", 0.0, 0.0), (1.0, 1.0, 1.0)),
        ((0.0j, 0.0, 0.0), (1.0, 1.0, 1.0)),
        ((0.0, 0.0), (1.0, 1.0, 1.0)),
        ((2.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
    ],
)
def test_malformed_bounds_cannot_be_coerced_into_ground_placement(grasp_module, monkeypatch, minimum, maximum):
    stage, mount, _asset = _asset_stage()
    aligned = types.SimpleNamespace(IsEmpty=lambda: False, GetMin=lambda: minimum, GetMax=lambda: maximum)
    monkeypatch.setattr(
        UsdGeom,
        "BBoxCache",
        lambda *_args: types.SimpleNamespace(
            ComputeWorldBound=lambda _prim: types.SimpleNamespace(ComputeAlignedBox=lambda: aligned)
        ),
    )
    with pytest.raises(ValueError):
        grasp_module._place_asset_on_ground(stage, "/World/Asset/Body")
    assert mount.GetOrderedXformOps() == []


@pytest.mark.parametrize("margin", [False, "0.01", 0.01j, float("inf"), float("nan")])
def test_invalid_ground_margin_is_not_silently_coerced(grasp_module, margin):
    stage, mount, _asset = _asset_stage()
    with pytest.raises(ValueError, match="Ground placement margin"):
        grasp_module._place_asset_on_ground(stage, "/World/Asset/Body", margin=margin)
    assert mount.GetOrderedXformOps() == []


@pytest.mark.parametrize("rejection", ["clear", "set", "stale_translation", "stale_order"])
def test_ground_placement_requires_authoring_acknowledgment(grasp_module, monkeypatch, rejection):
    stage, _mount, _asset = _asset_stage()
    events = []
    operation = types.SimpleNamespace(GetOpName=lambda: "xformOp:translate")
    authored = []

    def set_translation(value):
        events.append("set")
        authored.append(value)
        return rejection != "set"

    operation.Set = set_translation
    operation.Get = lambda: Gf.Vec3d(0) if rejection == "stale_translation" else authored[-1]

    def ordered():
        if not authored:
            return []
        return [] if rejection == "stale_order" else [operation]

    xformable = types.SimpleNamespace(
        ClearXformOpOrder=lambda: rejection != "clear",
        GetOrderedXformOps=ordered,
        AddTranslateOp=lambda: operation,
    )
    monkeypatch.setattr(UsdGeom, "Xformable", lambda _prim: xformable)
    with pytest.raises(RuntimeError, match="ground-placement"):
        grasp_module._place_asset_on_ground(stage, "/World/Asset/Body")
    assert ("set" in events) is (rejection != "clear")


def test_ground_placement_rejects_an_untransformable_selected_root(grasp_module):
    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/Root", "Scope")
    UsdGeom.Cube.Define(stage, "/Root/Body")
    with pytest.raises(RuntimeError, match="root is not transformable"):
        grasp_module._place_asset_on_ground(stage, "/Root/Body")


def test_ground_placement_rejects_offset_overflow_before_writing(grasp_module, monkeypatch):
    stage, mount, _asset = _asset_stage()
    aligned = types.SimpleNamespace(
        IsEmpty=lambda: False, GetMin=lambda: (0.0, 0.0, -1.7e308), GetMax=lambda: (1.0, 1.0, -1.6e308)
    )
    monkeypatch.setattr(
        UsdGeom,
        "BBoxCache",
        lambda *_args: types.SimpleNamespace(
            ComputeWorldBound=lambda _prim: types.SimpleNamespace(ComputeAlignedBox=lambda: aligned)
        ),
    )
    with pytest.raises(ValueError, match="Ground placement offset"):
        grasp_module._place_asset_on_ground(stage, "/World/Asset/Body", margin=1.7e308)
    assert mount.GetOrderedXformOps() == []

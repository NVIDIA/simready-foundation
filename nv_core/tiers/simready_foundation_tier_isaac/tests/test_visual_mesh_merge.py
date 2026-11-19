# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Behaviour of the visual mesh merge adapter."""

from __future__ import annotations

import shutil

import pytest
from conftest import _body, _mesh, _new_stage
from pxr import Sdf, Usd, UsdGeom, UsdShade
from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
    visual_mesh_merge,
)


@pytest.fixture
def scene_optimizer():
    """Use the adapter's actual usd-optimize backend for real merges."""
    try:
        visual_mesh_merge._optimizer()
    except ModuleNotFoundError as error:
        if error.name != "usd_optimize":
            raise
        pytest.skip("real visual merge requires usd-optimize >=1.4.0")


@pytest.fixture
def two_materials(tmp_path):
    """One body, two visual meshes, each bound to a different material.

    The common shape in real assets, and the one the adapter used to refuse.
    """
    path = tmp_path / "materials.usda"
    stage = _new_stage(path)
    _body(stage, "/Asset/Geometry/base")
    materials = {
        name: UsdShade.Material.Define(stage, f"/Asset/Looks/{name}")
        for name in ("red", "blue")
    }
    for name, material in (("m0", "red"), ("m1", "blue")):
        mesh = _mesh(stage, f"/Asset/Geometry/base/{name}")
        UsdShade.MaterialBindingAPI.Apply(mesh).Bind(materials[material])
    stage.GetRootLayer().Save()

    destination = tmp_path / "out.usda"
    shutil.copy(path, destination)
    return Usd.Stage.Open(str(path)), Usd.Stage.Open(str(destination))


def test_meshes_with_different_materials_merge(two_materials, scene_optimizer):
    """`considerMaterials=True` refused these, and the adapter then raised."""
    input_stage, output_stage = two_materials
    assert visual_mesh_merge.cook_stage(input_stage, output_stage) == 1


def test_both_materials_survive_as_face_subsets(two_materials, scene_optimizer):
    """Merging must not silently drop one mesh's material."""
    input_stage, output_stage = two_materials
    visual_mesh_merge.cook_stage(input_stage, output_stage)

    survivors = [
        prim
        for prim in Usd.PrimRange(
            output_stage.GetDefaultPrim(),
            Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate),
        )
        if prim.IsA(UsdGeom.Mesh)
    ]
    assert len(survivors) == 1
    bound = {
        str(
            UsdShade.MaterialBindingAPI(subset.GetPrim())
            .GetDirectBinding()
            .GetMaterialPath()
        )
        for subset in UsdGeom.Subset.GetAllGeomSubsets(UsdGeom.Imageable(survivors[0]))
    }
    assert bound == {"/Asset/Looks/red", "/Asset/Looks/blue"}


def _authored(tmp_path, name, m1_label, m1_provenance, extra=False):
    """One body, two meshes, with metadata that may or may not agree."""
    path = tmp_path / f"{name}.usda"
    stage = _new_stage(path)
    _body(stage, "/Asset/Geometry/base")
    for mesh_name in ("m0", "m1"):
        mesh = _mesh(stage, f"/Asset/Geometry/base/{mesh_name}")
        if mesh_name == "m0":
            mesh.SetCustomDataByKey("provenance", "on-m0")
            mesh.CreateAttribute("semantic:label", Sdf.ValueTypeNames.String).Set("label-m0")
            if extra:
                mesh.CreateAttribute("only:onM0", Sdf.ValueTypeNames.String).Set("kept")
        else:
            if m1_provenance:
                mesh.SetCustomDataByKey("provenance", m1_provenance)
            if m1_label:
                mesh.CreateAttribute("semantic:label", Sdf.ValueTypeNames.String).Set(m1_label)
    stage.GetRootLayer().Save()
    destination = tmp_path / f"{name}_out.usda"
    shutil.copy(path, destination)
    input_stage, output_stage = Usd.Stage.Open(str(path)), Usd.Stage.Open(str(destination))
    visual_mesh_merge.cook_stage(input_stage, output_stage)
    # Return the stage too: dropping the last reference expires every prim on it.
    return output_stage, output_stage.GetPrimAtPath("/Asset/Geometry/base/m0")


def test_survivor_keeps_its_own_metadata(tmp_path, scene_optimizer):
    _stage, survivor = _authored(tmp_path, "keeps", m1_label=None, m1_provenance=None, extra=True)
    assert survivor.GetCustomDataByKey("provenance") == "on-m0"
    assert survivor.GetAttribute("semantic:label").Get() == "label-m0"
    assert survivor.GetAttribute("only:onM0").Get() == "kept"


def test_agreeing_metadata_is_kept(tmp_path, scene_optimizer):
    _stage, survivor = _authored(tmp_path, "agree", m1_label="label-m0", m1_provenance="on-m0")
    assert survivor.GetCustomDataByKey("provenance") == "on-m0"
    assert survivor.GetAttribute("semantic:label").Get() == "label-m0"


def test_conflicting_metadata_is_dropped_not_inherited(tmp_path, scene_optimizer):
    """The survivor must not end up asserting a source's value over both.

    Skipping the re-author is not enough: Sdf.CopySpec has already written
    whatever the optimizer's output carried, so the opinion has to be removed.
    """
    _stage, survivor = _authored(tmp_path, "conflict", m1_label="label-m1", m1_provenance="on-m1")
    label = survivor.GetAttribute("semantic:label")
    assert not (label and label.HasAuthoredValue())
    assert "provenance" not in survivor.GetCustomData()


def test_geometry_still_merges_when_metadata_is_dropped(tmp_path, scene_optimizer):
    _stage, survivor = _authored(tmp_path, "geom", m1_label="label-m1", m1_provenance="on-m1")
    assert len(UsdGeom.Mesh(survivor).GetFaceVertexCountsAttr().Get()) == 2


class _FakeContext:
    def set_stage(self, stage):
        self.stage = stage


class _FakeCore:
    def __init__(self, operation):
        self._operation = operation

    def executeOperation(self, _name, context, _options):
        return self._operation(context.stage)


def _install_fake_optimizer(monkeypatch, operation):
    context = _FakeContext()
    core = _FakeCore(operation)
    monkeypatch.setattr(visual_mesh_merge, "_optimizer", lambda: (core, context))


def _merged_mesh(stage, path="/Merged"):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr().Set(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
        ]
    )
    mesh.CreateFaceVertexCountsAttr().Set([3, 3])
    mesh.CreateFaceVertexIndicesAttr().Set([0, 1, 2, 1, 3, 2])
    return mesh.GetPrim()


def test_unreported_merge_uses_only_a_new_mesh(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    _mesh(stage, "/Asset/body/m0")
    _mesh(stage, "/Asset/body/m1")
    _mesh(stage, "/Asset/unrelated")

    def operation(scratch):
        _merged_mesh(scratch)
        return True, "", None

    _install_fake_optimizer(monkeypatch, operation)
    assert visual_mesh_merge._run_merge(
        stage, "/Asset/body/m0", ["/Asset/body/m1"]
    ) == "/Merged"


def test_optimizer_failure_preserves_the_reported_reason(monkeypatch):
    stage = Usd.Stage.CreateInMemory()

    def operation(_scratch):
        return False, "Stage id mismatch", None

    _install_fake_optimizer(monkeypatch, operation)
    with pytest.raises(visual_mesh_merge.MergeFailed, match="Stage id mismatch"):
        visual_mesh_merge._run_merge(stage, "/Asset/body/m0", ["/Asset/body/m1"])


def test_survivor_preserves_relationships_connections_and_time_samples(
    tmp_path, monkeypatch
):
    path = tmp_path / "authored-specs.usda"
    stage = _new_stage(path)
    _body(stage, "/Asset/Geometry/base")
    survivor = _mesh(stage, "/Asset/Geometry/base/m0")
    _mesh(stage, "/Asset/Geometry/base/m1")
    target = stage.DefinePrim("/Asset/semantic_target", "Scope")
    output_attr = target.CreateAttribute(
        "outputs:value", Sdf.ValueTypeNames.Float, custom=True
    )
    output_attr.Set(3.0)

    score = survivor.CreateAttribute(
        "semantic:score", Sdf.ValueTypeNames.Float, custom=True
    )
    score.SetMetadata("documentation", "preserve this metadata")
    score.Set(1.0, Usd.TimeCode(1.0))
    score.Set(2.0, Usd.TimeCode(2.0))
    score.AddConnection(output_attr.GetPath())
    survivor.CreateRelationship("semantic:target", custom=True).SetTargets(
        [target.GetPath()]
    )
    stage.GetRootLayer().Save()

    destination = tmp_path / "authored-specs-out.usda"
    shutil.copy(path, destination)
    input_stage = Usd.Stage.Open(str(path))
    output_stage = Usd.Stage.Open(str(destination))

    def operation(scratch):
        _merged_mesh(scratch)
        return True, "", "/Merged"

    _install_fake_optimizer(monkeypatch, operation)
    assert visual_mesh_merge.cook_stage(input_stage, output_stage) == 1

    merged = output_stage.GetPrimAtPath("/Asset/Geometry/base/m0")
    restored_score = merged.GetAttribute("semantic:score")
    assert restored_score.GetTimeSamples() == [1.0, 2.0]
    assert restored_score.Get(Usd.TimeCode(1.0)) == pytest.approx(1.0)
    assert restored_score.GetMetadata("documentation") == "preserve this metadata"
    assert restored_score.GetConnections() == [output_attr.GetPath()]
    assert merged.GetRelationship("semantic:target").GetTargets() == [target.GetPath()]

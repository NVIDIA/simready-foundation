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

"""AV.007 (OMPE-119277): a visual-only set must not swap collider geometry.

The physics fingerprint compared only applied schemas and physics-namespaced
property values, so a visual-only variation whose options replace the collider
mesh with a different same-extent shape (a cube hull swapped for an octahedron
hull) kept every physics value and the collision envelope invariant and passed
AV.007. The contact behavior changes, so it must fail. A same-type,
same-transform topology swap is also invisible to AV.010, so AV.007 owns it.
"""

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core import asset_variants as av
from simready.foundation.tier_core.rules_and_reqs.core.asset_variants.validation import (
    ImpactClassHonestyChecker,
)

# Two convex hulls with the SAME extent (+-0.1 m) but different topology.
_EXTENT = [(-0.1, -0.1, -0.1), (0.1, 0.1, 0.1)]
_CUBE_POINTS = [
    (-0.1, -0.1, -0.1), (0.1, -0.1, -0.1), (0.1, 0.1, -0.1), (-0.1, 0.1, -0.1),
    (-0.1, -0.1, 0.1), (0.1, -0.1, 0.1), (0.1, 0.1, 0.1), (-0.1, 0.1, 0.1),
]
_CUBE_COUNTS = [4, 4, 4, 4, 4, 4]
_CUBE_INDICES = [0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 5, 4, 2, 3, 7, 6, 0, 3, 7, 4, 1, 2, 6, 5]
_OCTA_POINTS = [(0.1, 0, 0), (-0.1, 0, 0), (0, 0.1, 0), (0, -0.1, 0), (0, 0, 0.1), (0, 0, -0.1)]
_OCTA_COUNTS = [3, 3, 3, 3, 3, 3, 3, 3]
_OCTA_INDICES = [0, 2, 4, 2, 1, 4, 1, 3, 4, 3, 0, 4, 2, 0, 5, 1, 2, 5, 3, 1, 5, 0, 3, 5]


def _collider_payload(path: Path, points, counts, indices) -> str:
    """A payload whose default prim carries a guide-purpose convexHull collider."""
    layer = Sdf.Layer.CreateNew(str(path))
    stage = Usd.Stage.Open(layer)
    content = UsdGeom.Xform.Define(stage, "/Content")
    stage.SetDefaultPrim(content.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Content/Collider")
    mesh.GetPointsAttr().Set(points)
    mesh.GetFaceVertexCountsAttr().Set(counts)
    mesh.GetFaceVertexIndicesAttr().Set(indices)
    mesh.GetExtentAttr().Set(_EXTENT)
    UsdGeom.Imageable(mesh).CreatePurposeAttr(UsdGeom.Tokens.guide)
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    mesh_col = UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())
    mesh_col.CreateApproximationAttr(UsdPhysics.Tokens.convexHull)
    stage.GetRootLayer().Save()
    return str(path)


def _variant_asset(tmp_path, option_payloads, *, category="MeshVariant",
                   set_name="MeshVariant_body", impact="visual-only"):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    vset = root.GetVariantSets().AddVariantSet(set_name)
    first = None
    for option, payload in option_payloads:
        first = first or option
        vset.AddVariant(option)
        vset.SetVariantSelection(option)
        with vset.GetVariantEditContext():
            root.GetPayloads().AddPayload(payload)
    vset.SetVariantSelection(first)
    stage.GetRootLayer().customLayerData = {
        av.SIMREADY_METADATA_KEY: {av.VARIANTS_KEY: {category: {
            set_name: {"prim": "/Asset", "variantSetName": set_name, "category": category,
                       "default": first, "impactClass": impact}}}}}
    return stage


def _issues(stage):
    checker = ImpactClassHonestyChecker()
    checker.CheckStage(stage)
    return [i.message for i in checker.GetIssues()]


def test_visual_only_collider_shape_swap_fails(tmp_path):
    """Cube hull vs octahedron hull, same extent and physics values -> fail AV.007."""
    cube = _collider_payload(tmp_path / "hull_a.usda", _CUBE_POINTS, _CUBE_COUNTS, _CUBE_INDICES)
    octa = _collider_payload(tmp_path / "hull_b.usda", _OCTA_POINTS, _OCTA_COUNTS, _OCTA_INDICES)
    messages = _issues(_variant_asset(tmp_path, [("Cube", cube), ("Octa", octa)]))
    assert any("collider geometry" in m for m in messages), messages


def test_visual_only_identical_collider_passes(tmp_path):
    """Both options carry the same collider mesh -> no AV.007 collider-geometry issue."""
    a = _collider_payload(tmp_path / "same_a.usda", _CUBE_POINTS, _CUBE_COUNTS, _CUBE_INDICES)
    b = _collider_payload(tmp_path / "same_b.usda", _CUBE_POINTS, _CUBE_COUNTS, _CUBE_INDICES)
    messages = _issues(_variant_asset(tmp_path, [("A", a), ("B", b)]))
    assert not any("collider geometry" in m for m in messages), messages


def test_collision_category_declared_visual_only_fails(tmp_path):
    """The Collision category is simulation-affecting; visual-only is dishonest."""
    a = _collider_payload(tmp_path / "col_a.usda", _CUBE_POINTS, _CUBE_COUNTS, _CUBE_INDICES)
    b = _collider_payload(tmp_path / "col_b.usda", _CUBE_POINTS, _CUBE_COUNTS, _CUBE_INDICES)
    stage = _variant_asset(tmp_path, [("A", a), ("B", b)], category="Collision",
                           set_name="Collision_body", impact="visual-only")
    messages = _issues(stage)
    assert any("Collision category" in m for m in messages), messages

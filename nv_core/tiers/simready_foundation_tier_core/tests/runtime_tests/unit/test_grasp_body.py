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
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.fet005_grasp.grasp_body import resolve_grasp_body


def _stage_with_annotation_scope():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    UsdGeom.Scope.Define(stage, "/Asset/Grasp")
    UsdGeom.Xform.Define(stage, "/Asset/Grasp/grasp_identifier")
    UsdGeom.Scope.Define(stage, "/Asset/Geometry")
    body = UsdGeom.Cube.Define(stage, "/Asset/Geometry/Body")
    body.CreateSizeAttr(2.0)
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    other = UsdGeom.Cube.Define(stage, "/Asset/Geometry/Other")
    other.CreateSizeAttr(2.0)
    other.AddTranslateOp().Set(Gf.Vec3d(0.0, 5.0, 0.0))
    UsdPhysics.RigidBodyAPI.Apply(other.GetPrim())
    return stage


def test_resolve_grasp_body_crossed_by_identifier_in_sibling_scope():
    stage = _stage_with_annotation_scope()

    body = resolve_grasp_body(
        stage,
        "/Asset/Grasp/grasp_identifier",
        "/Asset",
        Gf.Vec3d(-2.0, 0.0, 0.0),
        Gf.Vec3d(2.0, 0.0, 0.0),
    )

    assert body == "/Asset/Geometry/Body"


def test_resolve_grasp_body_prefers_nearest_rigid_body_ancestor():
    stage = _stage_with_annotation_scope()
    UsdGeom.Xform.Define(stage, "/Asset/Geometry/Body/grasp_identifier")

    body = resolve_grasp_body(
        stage,
        "/Asset/Geometry/Body/grasp_identifier",
        "/Asset",
        Gf.Vec3d(100.0, 100.0, 100.0),
        Gf.Vec3d(101.0, 100.0, 100.0),
    )

    assert body == "/Asset/Geometry/Body"


def test_resolve_grasp_body_falls_back_to_mounted_asset_root():
    stage = _stage_with_annotation_scope()

    body = resolve_grasp_body(
        stage,
        "/Asset/Grasp/grasp_identifier",
        "/Asset",
        Gf.Vec3d(100.0, 100.0, 100.0),
        Gf.Vec3d(101.0, 100.0, 100.0),
    )

    assert body == "/Asset"

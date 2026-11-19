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
"""Fixtures for the Isaac optimization capability.

Stages are built in code rather than checked in, so a fixture cannot drift from
the rule it exercises without the test that reads it changing too.
"""

from __future__ import annotations

import shutil

import pytest

pytest.importorskip("pxr")
pytest.importorskip("usd_validation_nvidia")
pytest.importorskip("simready.foundation.tier_isaac.requirements")

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402

INFINITE = float("inf")


def _body(stage, path, translate=(0.0, 0.0, 0.0), mass=1.0, dynamic=True):
    prim = UsdGeom.Xform.Define(stage, path).GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(prim)
    if not dynamic:
        UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr().Set(True)
    UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(*translate))
    mass_api = UsdPhysics.MassAPI.Apply(prim)
    mass_api.CreateMassAttr().Set(mass)
    mass_api.CreateCenterOfMassAttr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(0.01, 0.01, 0.01))
    mass_api.CreatePrincipalAxesAttr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    return prim


def _collider(stage, path, size=0.2):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr().Set(size)
    UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
    return cube.GetPrim()


def _mesh(stage, path):
    """A visual mesh: no collider, default purpose, so it is mergeable."""
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr().Set([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)])
    mesh.CreateFaceVertexCountsAttr().Set([3])
    mesh.CreateFaceVertexIndicesAttr().Set([0, 1, 2])
    return mesh.GetPrim()


def _fixed_joint(stage, path, body0, body1, break_force=INFINITE):
    joint = UsdPhysics.FixedJoint.Define(stage, path)
    joint.CreateBody0Rel().SetTargets([Sdf.Path(body0)])
    joint.CreateBody1Rel().SetTargets([Sdf.Path(body1)])
    joint.CreateBreakForceAttr().Set(break_force)
    joint.CreateBreakTorqueAttr().Set(break_force)
    return joint.GetPrim()


def _new_stage(path):
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    return stage


@pytest.fixture
def welded_pair(tmp_path):
    """Two dynamic bodies welded by an unbreakable fixed joint.

    ``base`` is the body the merge retains and ``tip`` the one it dissolves: the
    rule keeps whichever is closest to the stage root, tie-broken by path, and
    both sit at the same depth here. ``tip`` carries a child mesh, a collider, an
    applied schema and custom data, so a move that drops any of them is visible.
    An outside body is joined to ``tip`` by a revolute joint, which must end up
    naming ``base``.
    """
    path = tmp_path / "welded.usda"
    stage = _new_stage(path)
    retained = _body(stage, "/Asset/Geometry/base", translate=(0.0, 0.0, 0.3), mass=2.0)
    tip = _body(stage, "/Asset/Geometry/tip", translate=(0.0, 0.0, 0.5), mass=1.0)
    outside = _body(stage, "/Asset/Geometry/outside", translate=(0.0, 0.0, 0.9), mass=0.5)
    _collider(stage, "/Asset/Geometry/base/collider")
    _collider(stage, "/Asset/Geometry/tip/collider")
    _mesh(stage, "/Asset/Geometry/tip/render")
    tip.SetCustomDataByKey("provenance", "authored-on-dissolved")
    UsdPhysics.FilteredPairsAPI.Apply(tip)  # a schema the merge must carry over

    # Relationships that mean "a rigid body" and name the body being dissolved.
    # NamespaceEditor moves these to the new path, which stops being a body.
    outside_pairs = UsdPhysics.FilteredPairsAPI.Apply(outside).CreateFilteredPairsRel()
    outside_pairs.SetTargets([Sdf.Path("/Asset/Geometry/tip"),
                              Sdf.Path("/Asset/Geometry/tip/collider")])
    UsdPhysics.FilteredPairsAPI(tip).CreateFilteredPairsRel().SetTargets(
        [Sdf.Path("/Asset/Geometry/outside")])
    UsdPhysics.FilteredPairsAPI.Apply(retained).CreateFilteredPairsRel().SetTargets(
        [Sdf.Path("/Asset/Geometry/tip")])
    stage.GetPrimAtPath("/Asset").CreateRelationship(
        "isaac:physics:robotLinks"
    ).SetTargets([Sdf.Path("/Asset/Geometry/base"), Sdf.Path("/Asset/Geometry/tip")])

    _fixed_joint(stage, "/Asset/Joints/weld", "/Asset/Geometry/base",
                 "/Asset/Geometry/tip")
    hinge = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Joints/hinge")
    hinge.CreateBody0Rel().SetTargets([Sdf.Path("/Asset/Geometry/tip")])
    hinge.CreateBody1Rel().SetTargets([Sdf.Path("/Asset/Geometry/outside")])
    stage.GetRootLayer().Save()
    return path


@pytest.fixture
def welded_pair_referenced(tmp_path, welded_pair):
    """The same content, reached through a payload.

    Exercises the other half of ``Usd.NamespaceEditor``: the prim to move is not
    authored in the layer being edited, so it can only move by ``relocates``.
    """
    path = tmp_path / "entry.usda"
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    root.GetPayloads().AddPayload(str(welded_pair), Sdf.Path("/Asset"))
    stage.SetDefaultPrim(root)
    stage.GetRootLayer().Save()
    return path


@pytest.fixture
def copy_for_output(tmp_path):
    """Open a source read-only and a writable copy, the way the adapter is driven."""
    def _copy(source):
        destination = tmp_path / "out" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        for item in source.parent.iterdir():
            if item.is_file():
                shutil.copy2(item, destination.parent / item.name)
        return Usd.Stage.Open(str(source)), Usd.Stage.Open(str(destination))
    return _copy

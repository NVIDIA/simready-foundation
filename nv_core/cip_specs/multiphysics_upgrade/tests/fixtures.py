# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared USD fixtures for multiphysics upgrade tests."""

from __future__ import annotations

from pathlib import Path

from pxr import Gf, Usd, UsdGeom, UsdPhysics, UsdShade


def write_neutral_package(package: Path, usd_name: str = "sm_test_neutral_01.usda") -> Path:
    """Write a minimal neutral unibody prop package and return its root USD."""
    package.mkdir(parents=True, exist_ok=True)
    usd_path = package / usd_name
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())

    mesh = UsdGeom.Mesh.Define(stage, "/RootNode/Geometry/mesh")
    mesh.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)])
    mesh.CreateFaceVertexCountsAttr([3])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
    mesh.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 3)
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    UsdPhysics.MassAPI.Apply(root.GetPrim())
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())

    material = UsdShade.Material.Define(stage, "/RootNode/Looks/PhysMat")
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())

    stage.GetRootLayer().Save()
    return usd_path


def write_non_mesh_package(package: Path, usd_name: str = "sm_bad_prop_01.usda") -> Path:
    """Write a package the upgrade must refuse: visible non-mesh geometry."""
    package.mkdir(parents=True, exist_ok=True)
    usd_path = package / usd_name
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Cube.Define(stage, "/RootNode/Cube")
    stage.GetRootLayer().Save()
    return usd_path

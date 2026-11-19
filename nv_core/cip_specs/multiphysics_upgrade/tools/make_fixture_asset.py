# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Write a minimal neutral prop package for wheelhouse verification.

Imports only ``pxr`` and the standard library so it can run inside an isolated
wheelhouse install with no repository on ``sys.path``.

The fixture carries an authored mass and a Wikidata Q-Code semantic so the same
package can also exercise the metadata sidecar, which derives those values from
the asset and refuses to invent them.

Usage::

    python make_fixture_asset.py <package_dir> [usd_name]
"""

from __future__ import annotations

import sys
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

FIXTURE_MASS_KG = 2.5
FIXTURE_QCODE = "Q42177"


def write_neutral_package(package: Path, usd_name: str = "sm_fixture_prop_01.usda") -> Path:
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
    UsdPhysics.MassAPI.Apply(root.GetPrim()).CreateMassAttr(FIXTURE_MASS_KG)
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())

    qcode = root.GetPrim().CreateAttribute(
        "semantics:labels:wikidata_qcode", Sdf.ValueTypeNames.TokenArray, custom=False
    )
    qcode.Set([FIXTURE_QCODE])

    material = UsdShade.Material.Define(stage, "/RootNode/Looks/PhysMat")
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())

    stage.GetRootLayer().Save()
    return usd_path


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: make_fixture_asset.py <package_dir> [usd_name]", file=sys.stderr)
        return 2
    package = Path(argv[0])
    usd_name = argv[1] if len(argv) > 1 else "sm_fixture_prop_01.usda"
    print(write_neutral_package(package, usd_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

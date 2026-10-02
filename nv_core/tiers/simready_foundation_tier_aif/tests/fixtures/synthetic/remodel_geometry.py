# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Remodel in-house exemplars as component boxes for synthetic AIF fixtures.

Run with a USD Python runtime. Inputs are extracted cracunit_01.usd and
ups_cabinet_01.usd; output is the synthetic fixture directory. Source mesh
names, materials and CAD metadata are intentionally not copied. Each mesh's
local bound becomes an eight-vertex box transformed into fixture coordinates.
"""
import argparse
import json
from pathlib import Path

from pxr import Gf, Usd, UsdGeom


FACES = [0, 3, 2, 1, 4, 5, 6, 7, 0, 1, 5, 4,
         1, 2, 6, 5, 2, 3, 7, 6, 3, 0, 4, 7]


def remodel(source, output, name, dimensions):
    source_stage = Usd.Stage.Open(str(source))
    up = UsdGeom.GetStageUpAxis(source_stage)
    if up not in ('Y', 'Z'):
        raise ValueError(f'Unsupported source axis: {up}')
    cache = UsdGeom.XformCache()
    parts = []
    for prim in Usd.PrimRange(source_stage.GetPseudoRoot(), Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        points = UsdGeom.Mesh(prim).GetPointsAttr().Get()
        if not points:
            continue
        lo = [min(p[i] for p in points) for i in range(3)]
        hi = [max(p[i] for p in points) for i in range(3)]
        # Retain a closed volume even for sheet-metal source surfaces.
        for i in range(3):
            if hi[i] - lo[i] < 1e-5:
                hi[i] = lo[i] + 1e-5
        corners = [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]),
                   (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                   (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]),
                   (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])]
        transform = cache.GetLocalToWorldTransform(prim)
        world = [transform.Transform(Gf.Vec3d(*p)) for p in corners]
        points = [(p[0], -p[2], p[1]) if up == 'Y' else tuple(p) for p in world]
        # Reflections reverse winding; baking must preserve outward faces.
        indices = FACES if transform.GetDeterminant() > 0 else [
            v for i in range(0, len(FACES), 4) for v in reversed(FACES[i:i+4])]
        parts.append((points, indices))
    all_points = [p for points, _ in parts for p in points]
    low = [min(p[i] for p in all_points) for i in range(3)]
    high = [max(p[i] for p in all_points) for i in range(3)]
    target = output / name / 'asset' / 'layers' / f'{name}_Geometry.usda'
    stage = Usd.Stage.CreateNew(str(target))
    root = UsdGeom.Xform.Define(stage, '/' + name)
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(stage, 'Z')
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.Scope.Define(stage, f'/{name}/Geometry')
    for index, (points, indices) in enumerate(parts):
        points = [Gf.Vec3f(*[(p[i] - low[i]) / (high[i] - low[i]) * dimensions[i]
                            - (dimensions[i] / 2 if i < 2 else 0)
                            for i in range(3)]) for p in points]
        mesh = UsdGeom.Mesh.Define(stage, f'/{name}/Geometry/Part_{index:04d}')
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([4] * 6)
        mesh.CreateFaceVertexIndicesAttr(indices)
        mesh.CreateSubdivisionSchemeAttr('none')
        normals = []
        for face in range(6):
            a, b, c = [Gf.Vec3d(points[v]) for v in indices[face*4:face*4+3]]
            normal = Gf.Cross(b - a, c - a)
            if normal.GetLength() == 0:
                raise ValueError(f'Degenerate box face in part {index}')
            normals.extend([Gf.Vec3f(normal.GetNormalized())] * 4)
        mesh.CreateNormalsAttr(normals)
        mesh.SetNormalsInterpolation('faceVarying')
        mesh.CreateExtentAttr(UsdGeom.PointBased(mesh).ComputeExtent(points))
        mesh.CreateDisplayColorAttr([Gf.Vec3f(.6, .65, .7)])
    stage.GetRootLayer().Save()
    print(f'{name}: {len(parts)} boxes, {len(parts)*8} vertices, {target.stat().st_size} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('crah', type=Path)
    parser.add_argument('ups', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    for kind, source in [('crah', args.crah), ('ups', args.ups)]:
        values = json.loads((args.output / 'sources' / f'generic_{kind}.json').read_text())
        dimensions = [v / 1000 for v in values['aif:core:overallGeometryDimensions'][1]]
        remodel(source, args.output, f'Synthetic_{kind.upper()}', dimensions)

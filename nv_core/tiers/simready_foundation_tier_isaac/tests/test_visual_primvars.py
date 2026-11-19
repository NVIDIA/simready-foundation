# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Opaque primvar values must survive the real mesh optimizer."""
from collections import Counter

import pytest
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom
from conftest import _body, _new_stage
from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import visual_mesh_merge


def _value(kind, index):
    if kind == 'FloatArray':
        return float(index) + .25
    if kind == 'StringArray':
        return f'label-{index}'
    if kind == 'Matrix4dArray':
        return Gf.Matrix4d(index + 1.)
    if kind == 'QuatfArray':
        return Gf.Quatf(1., Gf.Vec3f(index, 2., 3.))
    cls = {'Float4Array': Gf.Vec4f, 'Color4fArray': Gf.Vec4f,
           'Double4Array': Gf.Vec4d, 'Int4Array': Gf.Vec4i}[kind]
    return cls(index, index + 1, index + 2, index + 3)


def _scene(tmp_path, kind, interpolation, indexed=False, inherited=False):
    stage = _new_stage(tmp_path / 'primvars.usda')
    _body(stage, '/Asset/body')
    for i in range(2):
        parent = UsdGeom.Xform.Define(stage, f'/Asset/body/part{i}')
        parent.AddTranslateOp().Set(Gf.Vec3d(i * 2, 0, 0))
        mesh = UsdGeom.Mesh.Define(stage, parent.GetPath().AppendChild('visual'))
        mesh.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)])
        mesh.CreateFaceVertexCountsAttr([3, 3])
        mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 0, 2, 3])
        mesh.CreateSubdivisionSchemeAttr('none')
        holder = parent.GetPrim() if inherited else mesh.GetPrim()
        primvar = UsdGeom.PrimvarsAPI(holder).CreatePrimvar('payload', getattr(Sdf.ValueTypeNames, kind), interpolation)
        count = {'constant': 1, 'uniform': 2, 'vertex': 4, 'varying': 4, 'faceVarying': 6}[interpolation]
        values = [_value(kind, i * 20 + j) for j in range(count)]
        primvar.Set(values[::-1] if indexed else values)
        if indexed:
            primvar.SetIndices(list(reversed(range(count))))
        primvar.GetAttr().SetCustomDataByKey('provenance', 'preserved')
    return stage


def _samples(stage):
    result = Counter()
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        pv = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance('payload')
        assert pv and pv.HasValue(), f'{prim.GetPath()}: payload was dropped'
        raw = list(pv.Get()) if pv.GetTypeName().isArray else [pv.Get()]
        size = pv.GetElementSize()
        lookup = pv.GetIndices() if pv.IsIndexed() else range(len(raw) // size)
        values = [tuple(str(v) for v in raw[i * size:(i + 1) * size]) for i in lookup]
        interp = pv.GetInterpolation()
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
        points = mesh.GetPointsAttr().Get()
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        offset = 0
        for face, count in enumerate(mesh.GetFaceVertexCountsAttr().Get()):
            corners = []
            for corner in range(offset, offset + count):
                vertex = indices[corner]
                index = {'constant': 0, 'uniform': face, 'vertex': vertex, 'varying': vertex, 'faceVarying': corner}[interp]
                corners.append((tuple(matrix.Transform(Gf.Vec3d(points[vertex]))), values[index]))
            if (mesh.GetOrientationAttr().Get() == 'leftHanded') != (matrix.GetDeterminant() < 0):
                corners.reverse()
            result[min(tuple(corners[i:] + corners[:i]) for i in range(count))] += 1
            offset += count
    return result


@pytest.mark.parametrize('kind', ['Float4Array', 'Color4fArray', 'Double4Array', 'Int4Array', 'StringArray', 'Matrix4dArray', 'QuatfArray'])
@pytest.mark.parametrize('interpolation', ['constant', 'uniform', 'vertex', 'varying', 'faceVarying'])
@pytest.mark.parametrize('indexed', [False, True])
def test_typed_primvars_survive_actual_merge(tmp_path, kind, interpolation, indexed):
    stage = _scene(tmp_path, kind, interpolation, indexed)
    original = stage.GetRootLayer().ExportToString()
    expected = _samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    assert visual_mesh_merge.cook_stage(stage, work) == 1
    reopened = Usd.Stage.Open(work.Flatten())
    assert _samples(reopened) == expected
    for prim in reopened.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            pv = UsdGeom.PrimvarsAPI(prim).GetPrimvar('payload')
            assert pv.GetTypeName() == getattr(Sdf.ValueTypeNames, kind)
            assert pv.GetAttr().GetCustomDataByKey('provenance') == 'preserved'
    assert stage.GetRootLayer().ExportToString() == original


def test_inherited_constant_primvars_survive_actual_merge(tmp_path):
    stage = _scene(tmp_path, 'Float4Array', 'constant', inherited=True)
    expected = _samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    assert visual_mesh_merge.cook_stage(stage, work) == 1
    assert _samples(Usd.Stage.Open(work.Flatten())) == expected


@pytest.mark.parametrize('kind', ['Float4Array', 'StringArray'])
def test_scalar_constant_primvars_can_vary_between_source_meshes(tmp_path, kind):
    stage = _scene(tmp_path, kind, 'constant')
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            pv = UsdGeom.PrimvarsAPI(prim).GetPrimvar('payload')
            value = pv.Get()[0]
            pv.GetAttr().SetTypeName(pv.GetTypeName().scalarType)
            pv.Set(value)
    expected = _samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    visual_mesh_merge.cook_stage(stage, work)
    assert _samples(Usd.Stage.Open(work.Flatten())) == expected


def test_opaque_values_stay_distinct_on_coincident_geometry(tmp_path):
    stage = _scene(tmp_path, 'Float4Array', 'faceVarying', indexed=True)
    UsdGeom.Xformable(stage.GetPrimAtPath('/Asset/body/part1')).GetOrderedXformOps()[0].Set(Gf.Vec3d(0))
    expected = _samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    visual_mesh_merge.cook_stage(stage, work)
    assert _samples(Usd.Stage.Open(work.Flatten())) == expected


@pytest.mark.parametrize('kind', ['Float4Array', 'FloatArray'])
@pytest.mark.parametrize('indexed', [False, True])
@pytest.mark.parametrize('interpolation', ['vertex', 'faceVarying'])
def test_opaque_primvar_element_size_is_preserved(tmp_path, indexed, kind, interpolation):
    stage = _scene(tmp_path, kind, interpolation)
    UsdGeom.Xformable(stage.GetPrimAtPath('/Asset/body/part0')).AddScaleOp().Set((-1., 1., 1.))
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            pv = UsdGeom.PrimvarsAPI(prim).GetPrimvar('payload')
            values = [v for value in pv.Get() for v in [value, value + type(value)(10)]]
            pv.Set(values);pv.SetElementSize(2)
            if indexed:
                pv.SetIndices(list(reversed(range(len(values) // 2))))
    expected = _samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    visual_mesh_merge.cook_stage(stage, work)
    assert _samples(Usd.Stage.Open(work.Flatten())) == expected


@pytest.mark.parametrize('interpolation', ['vertex', 'varying'])
def test_subdivision_primvars_keep_their_interpolation(tmp_path, interpolation):
    stage = _scene(tmp_path, 'Float4Array', interpolation, indexed=True)
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            UsdGeom.Mesh(prim).CreateSubdivisionSchemeAttr('catmullClark')
    expected = _samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    visual_mesh_merge.cook_stage(stage, work)
    assert _samples(Usd.Stage.Open(work.Flatten())) == expected
    for prim in work.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            assert UsdGeom.PrimvarsAPI(prim).GetPrimvar('payload').GetInterpolation() == interpolation


@pytest.mark.parametrize('inherited', [False, True])
@pytest.mark.parametrize('type_name', ['Float3Array', 'Normal3fArray'])
def test_mirrored_authored_and_inherited_normal_primvars(tmp_path, inherited, type_name):
    stage = _scene(tmp_path, 'Float4Array', 'constant')
    for i in range(2):
        parent = stage.GetPrimAtPath(f'/Asset/body/part{i}')
        UsdGeom.Xformable(parent).AddScaleOp().Set(Gf.Vec3f(-1, 2, 1))
        holder = parent if inherited else stage.GetPrimAtPath(parent.GetPath().AppendChild('visual'))
        pv = UsdGeom.PrimvarsAPI(holder).CreatePrimvar('normals', getattr(Sdf.ValueTypeNames, type_name), 'constant')
        pv.Set([Gf.Vec3f(.6, 0, .8)])

    def samples(on):
        values = []
        for prim in on.Traverse():
            if not prim.IsA(UsdGeom.Mesh):continue
            mesh = UsdGeom.Mesh(prim)
            pv = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance('normals')
            normals = pv.ComputeFlattened() if pv and pv.HasValue() else mesh.GetNormalsAttr().Get()
            interpolation = pv.GetInterpolation() if pv and pv.HasValue() else mesh.GetNormalsInterpolation()
            matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
            normal_matrix = matrix.GetInverse().GetTranspose()
            points = mesh.GetPointsAttr().Get();indices = mesh.GetFaceVertexIndicesAttr().Get();offset = 0
            for face, count in enumerate(mesh.GetFaceVertexCountsAttr().Get()):
                for corner in range(offset, offset + count):
                    vertex = indices[corner]
                    index = {'constant': 0, 'uniform': face, 'vertex': vertex, 'varying': vertex, 'faceVarying': corner}[interpolation]
                    values.append((tuple(matrix.Transform(Gf.Vec3d(points[vertex]))),
                                   tuple(normal_matrix.TransformDir(Gf.Vec3d(normals[index])).GetNormalized())))
                offset += count
        return sorted(values)

    before = samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    visual_mesh_merge.cook_stage(stage, work)
    np.testing.assert_allclose(samples(Usd.Stage.Open(work.Flatten())), before, atol=1e-6)


@pytest.mark.parametrize('mirror', [False, True])
def test_geometric_primvar_roles_preserve_world_values(tmp_path, mirror):
    """1.4 transforms points, vectors and normals according to their USD roles."""
    stage = _scene(tmp_path, 'Float4Array', 'constant')
    stage.GetPrimAtPath('/Asset/body').GetAttribute('xformOp:translate').Set((7., -3., 2.))
    types = {
        'samplePosition': Sdf.ValueTypeNames.Point3fArray,
        'sampleDirection': Sdf.ValueTypeNames.Vector3fArray,
        'sampleNormal': Sdf.ValueTypeNames.Normal3fArray,
    }
    for i in range(2):
        parent = UsdGeom.Xformable(stage.GetPrimAtPath(f'/Asset/body/part{i}'))
        parent.AddRotateXYZOp().Set((13., 31., 47.))
        parent.AddScaleOp().Set((-2. if mirror else 2., .7, 1.3))
        prim = stage.GetPrimAtPath(f'/Asset/body/part{i}/visual')
        UsdGeom.Xformable(prim).AddRotateXYZOp().Set((19., -23., 17.))
        for name, type_name in types.items():
            pv = UsdGeom.PrimvarsAPI(prim).CreatePrimvar(name, type_name, 'vertex')
            pv.Set([(j + .2, .4 - j, .8) for j in range(4)])
            pv.SetIndices([2, 0, 3, 1])

    def samples(on):
        result = []
        for prim in on.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue
            mesh = UsdGeom.Mesh(prim)
            matrix = mesh.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            points = mesh.GetPointsAttr().Get()
            primvars = [UsdGeom.PrimvarsAPI(prim).GetPrimvar(name) for name in types]
            assert [pv.GetTypeName() for pv in primvars] == list(types.values())
            values = [pv.ComputeFlattened() for pv in primvars]
            for corner, vertex in enumerate(mesh.GetFaceVertexIndicesAttr().Get()):
                sample = [tuple(matrix.Transform(Gf.Vec3d(points[vertex])))]
                for pv, array in zip(primvars, values):
                    index = vertex if pv.GetInterpolation() == 'vertex' else corner
                    value = Gf.Vec3d(array[index])
                    role = pv.GetTypeName().role
                    if role == 'Point':
                        value = matrix.Transform(value)
                    elif role == 'Normal':
                        value = matrix.GetInverse().GetTranspose().TransformDir(value).GetNormalized()
                    else:
                        value = matrix.TransformDir(value)
                    sample.append(tuple(value))
                result.append(sample)
        return sorted(result)

    original = stage.GetRootLayer().ExportToString()
    expected = samples(stage)
    work = Usd.Stage.Open(stage.Flatten())
    assert visual_mesh_merge.cook_stage(stage, work) == 1
    np.testing.assert_allclose(samples(Usd.Stage.Open(work.Flatten())), expected, atol=3e-6)
    assert stage.GetRootLayer().ExportToString() == original


@pytest.mark.parametrize('case', ['missing', 'type', 'metadata', 'unauthored', 'inherited_animation', 'inherited_index_animation'])
def test_unrepresentable_primvars_refuse_atomically(tmp_path, case):
    stage = _scene(tmp_path, 'Float4Array', 'constant', inherited=case.startswith('inherited_'))
    second = stage.GetPrimAtPath('/Asset/body/part1/visual')
    pv = UsdGeom.PrimvarsAPI(second).GetPrimvar('payload')
    if case == 'missing':
        second.RemoveProperty('primvars:payload')
    elif case == 'type':
        pv.GetAttr().SetTypeName(Sdf.ValueTypeNames.FloatArray);pv.Set([1.])
    elif case == 'metadata':
        pv.GetAttr().SetCustomDataByKey('provenance', 'different')
    elif case == 'unauthored':
        pv.SetIndices([0]);pv.SetUnauthoredValuesIndex(0)
    else:
        pv = UsdGeom.PrimvarsAPI(second.GetParent()).GetPrimvar('payload')
        if case == 'inherited_index_animation':
            pv.Set([Gf.Vec4f(1), Gf.Vec4f(2)])
            pv.SetIndices([0]);pv.SetIndices([1], 1.)
        else:
            pv.Set([Gf.Vec4f(1)], 1.)
    work = Usd.Stage.Open(stage.Flatten())
    before = work.GetRootLayer().ExportToString()
    with pytest.raises(visual_mesh_merge.MergeFailed):
        visual_mesh_merge.cook_stage(stage, work)
    assert work.GetRootLayer().ExportToString() == before

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Merged geometry must mask obsolete opinions in weaker source layers."""

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from conftest import _body, _new_stage
from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import visual_mesh_merge


def _scene(tmp_path, composition, second_bound=True, subsets=False, labels=True, label_type='StringArray'):
    source_path = tmp_path / 'source.usda'
    source = _new_stage(source_path)
    _body(source, '/Asset/body')
    red = UsdShade.Material.Define(source, '/Asset/Looks/Red')
    blue = UsdShade.Material.Define(source, '/Asset/Looks/Blue')
    for name, count, offset in [('first', 4, 0), ('second', 2, 10)]:
        mesh = UsdGeom.Mesh.Define(source, f'/Asset/body/{name}')
        points = [(offset + i * 2 + x, y, 0) for i in range(count)
                  for x, y in [(0, 0), (1, 0), (0, 1)]]
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([3] * count)
        mesh.CreateFaceVertexIndicesAttr(list(range(3 * count)))
        mesh.CreateSubdivisionSchemeAttr('none')
        if labels:
            part = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('part', getattr(Sdf.ValueTypeNames, label_type), 'uniform')
            values = [f'{name}_even', f'{name}_odd'] if label_type == 'StringArray' else [offset + 3, offset + 7]
            part.Set([False, True] if label_type == 'BoolArray' else values)
            part.SetIndices([i % 2 for i in range(count)])
        binding = UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim())
        if name == 'first':
            binding.Bind(red)
            if subsets:
                subset = binding.CreateMaterialBindSubset('originalBlue', [1])
                UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(blue)
        elif second_bound:
            binding.Bind(blue)
    source.GetRootLayer().Save()
    output = _new_stage(tmp_path / 'output.usda')
    if composition == 'sublayer':
        output.GetRootLayer().subLayerPaths = ['source.usda']
    else:
        output.GetDefaultPrim().GetReferences().AddReference('source.usda', '/Asset')
    return source, output, source_path


def _samples(stage, purpose=''):
    samples = {}
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        points = mesh.GetPointsAttr().Get()
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        matrix = mesh.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        labels = UsdGeom.PrimvarsAPI(mesh).GetPrimvar('part')
        values = list(labels.Get()) if labels else None
        if labels and labels.IsIndexed():
            values = [values[index] for index in labels.GetIndices()]
        bound, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=purpose)
        materials = [str(bound.GetPath()) if bound else ''] * len(counts)
        for subset in UsdShade.MaterialBindingAPI(prim).GetMaterialBindSubsets():
            bound, _ = UsdShade.MaterialBindingAPI(subset.GetPrim()).ComputeBoundMaterial(materialPurpose=purpose)
            for face in subset.GetIndicesAttr().Get():
                materials[face] = str(bound.GetPath()) if bound else ''
        offset = 0
        for face, count in enumerate(counts):
            vertices = indices[offset:offset + count]
            center = sum((matrix.Transform(Gf.Vec3d(points[index])) for index in vertices), Gf.Vec3d(0)) / count
            label_index = {'uniform': face, 'faceVarying': offset, 'vertex': vertices[0], 'constant': 0}[labels.GetInterpolation()] if labels else 0
            samples[tuple(round(value, 5) for value in center)] = (values[label_index] if labels else None, materials[face])
            offset += count
    return samples


@pytest.mark.parametrize('composition', ['sublayer', 'reference'])
def test_composed_merge_replaces_obsolete_primvar_indices(tmp_path, composition):
    source, output, path = _scene(tmp_path, composition)
    expected = _samples(source)
    source_bytes = path.read_bytes()
    assert visual_mesh_merge.cook_stage(source, output) == 1
    survivor = output.GetPrimAtPath('/Asset/body/first')
    labels = UsdGeom.PrimvarsAPI(survivor).GetPrimvar('part')
    assert not labels.IsIndexed()
    assert _samples(output) == expected
    assert not survivor.GetRelationship('material:binding').GetTargets()
    output.GetRootLayer().Save()
    assert _samples(Usd.Stage.Open(output.GetRootLayer().identifier)) == expected
    assert path.read_bytes() == source_bytes


@pytest.mark.parametrize('composition', ['sublayer', 'reference'])
def test_composed_merge_replaces_original_material_subsets(tmp_path, composition):
    source, output, path = _scene(tmp_path, composition, subsets=True, labels=False)
    expected = _samples(source)
    source_bytes = path.read_bytes()
    flat = Usd.Stage.Open(source.Flatten())
    assert visual_mesh_merge.cook_stage(source, flat) == 1
    assert _samples(flat) == expected
    assert visual_mesh_merge.cook_stage(source, output) == 1
    original_subset = output.GetPrimAtPath('/Asset/body/first/originalBlue')
    assert not original_subset or not original_subset.IsActive()
    assert _samples(output) == expected
    output.GetRootLayer().Save()
    assert _samples(Usd.Stage.Open(output.GetRootLayer().identifier)) == expected
    assert path.read_bytes() == source_bytes


@pytest.mark.parametrize('subsets', [False, True])
def test_composed_merge_does_not_bind_previously_unbound_faces(tmp_path, subsets):
    source, output, path = _scene(tmp_path, 'sublayer', second_bound=False, subsets=subsets)
    if subsets:
        # A subset without its own binding still uses the mesh's default.
        UsdShade.MaterialBindingAPI(source.GetPrimAtPath('/Asset/body/first')).CreateMaterialBindSubset('inheritsDefault', [2])
        source.GetRootLayer().Save()
    expected = _samples(source)
    # Check the optimizer's fresh output independently of layering first.
    flat = Usd.Stage.Open(source.Flatten())
    assert visual_mesh_merge.cook_stage(source, flat) == 1
    assert _samples(flat) == expected
    source_bytes = path.read_bytes()
    assert visual_mesh_merge.cook_stage(source, output) == 1
    assert _samples(output) == expected
    assert path.read_bytes() == source_bytes


@pytest.mark.parametrize('label_type', ['StringArray', 'IntArray', 'BoolArray', 'FloatArray', 'DoubleArray'])
def test_material_subset_slicing_preserves_per_face_primvar_values(tmp_path, label_type):
    source, output, path = _scene(tmp_path, 'sublayer', subsets=True, label_type=label_type)
    expected = _samples(source)
    source_bytes = path.read_bytes()
    assert visual_mesh_merge.cook_stage(source, output) == 1
    assert _samples(output) == expected
    assert UsdGeom.PrimvarsAPI(output.GetPrimAtPath('/Asset/body/first')).GetPrimvar('part').GetTypeName() == getattr(Sdf.ValueTypeNames, label_type)
    assert path.read_bytes() == source_bytes


def test_mixed_binding_partition_refuses_an_inherited_default_atomically(tmp_path):
    source, output, path = _scene(tmp_path, 'reference', second_bound=False, subsets=True)
    parent = source.DefinePrim('/Asset/body/Bound', 'Xform')
    UsdShade.MaterialBindingAPI.Apply(parent).Bind(UsdShade.Material(source.GetPrimAtPath('/Asset/Looks/Red')))
    editor = Usd.NamespaceEditor(source)
    editor.MovePrimAtPath('/Asset/body/first', '/Asset/body/Bound/first')
    assert editor.ApplyEdits()
    source.GetRootLayer().Save()
    source_bytes = path.read_bytes()
    before = output.GetRootLayer().ExportToString()
    with pytest.raises(visual_mesh_merge.MergeFailed, match='inherited or collection material binding'):
        visual_mesh_merge.cook_stage(source, output)
    assert output.GetRootLayer().ExportToString() == before
    assert path.read_bytes() == source_bytes


def test_failure_after_composed_copy_restores_all_output_opinions(tmp_path, monkeypatch):
    source, output, path = _scene(tmp_path, 'sublayer', subsets=True)
    source_bytes = path.read_bytes()
    before = output.GetRootLayer().ExportToString()
    restore = visual_mesh_merge._restore

    def fail_after_copy(*args):
        restore(*args)
        raise RuntimeError('failure after composition masking')

    monkeypatch.setattr(visual_mesh_merge, '_restore', fail_after_copy)
    with pytest.raises(RuntimeError, match='failure after composition masking'):
        visual_mesh_merge.cook_stage(source, output)
    assert output.GetRootLayer().ExportToString() == before
    assert _samples(output) == _samples(source)
    assert path.read_bytes() == source_bytes


@pytest.mark.parametrize('active', [True, False])
def test_generated_subset_binding_replaces_weaker_targets_on_name_collision(tmp_path, active):
    source, output, path = _scene(tmp_path, 'reference', subsets=True, labels=False)
    editor = Usd.NamespaceEditor(source)
    editor.MovePrimAtPath('/Asset/body/first/originalBlue', '/Asset/body/first/Blue')
    assert editor.ApplyEdits()
    subset = source.GetPrimAtPath('/Asset/body/first/Blue')
    UsdShade.MaterialBindingAPI(subset).Bind(UsdShade.Material(source.GetPrimAtPath('/Asset/Looks/Red')))
    subset.SetActive(active)
    source.GetRootLayer().Save()
    source_bytes = path.read_bytes()
    expected = _samples(source)
    flat = Usd.Stage.Open(source.Flatten())
    assert visual_mesh_merge.cook_stage(source, flat) == 1
    assert _samples(flat) == expected
    assert visual_mesh_merge.cook_stage(source, output) == 1
    assert _samples(output) == expected
    assert path.read_bytes() == source_bytes


@pytest.mark.parametrize('purpose,holder', [('preview', 'first'), ('full', 'first/originalBlue')])
def test_purpose_specific_material_binding_refuses_atomically(tmp_path, purpose, holder):
    source, output, path = _scene(tmp_path, 'sublayer', subsets=True, labels=False, second_bound=False)
    material = UsdShade.Material(source.GetPrimAtPath('/Asset/Looks/Blue' if purpose == 'preview' else '/Asset/Looks/Red'))
    UsdShade.MaterialBindingAPI.Apply(source.GetPrimAtPath('/Asset/body/' + holder)).Bind(material, materialPurpose=purpose)
    source.GetRootLayer().Save()
    before = output.GetRootLayer().ExportToString()
    source_bytes = path.read_bytes()
    with pytest.raises(visual_mesh_merge.MergeFailed, match='purpose-specific material bindings'):
        visual_mesh_merge.cook_stage(source, output)
    assert output.GetRootLayer().ExportToString() == before
    assert path.read_bytes() == source_bytes

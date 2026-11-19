# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Independent geometry and dynamics oracles for the optimization adapters."""

import math

import numpy as np
import pytest
from conftest import _body, _collider, _fixed_joint, _mesh, _new_stage
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
    _massinfo, _massprops, fixed_joint_merge, render_collision_separation, visual_mesh_merge,
)


def clone(stage):
    return Usd.Stage.Open(stage.Flatten())


def filtered_shape_pairs(stage):
    def shapes(prim):
        if not prim:
            return []
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            found = []
            for child in Usd.PrimRange(prim):
                if not child.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                owner = child
                while owner and not owner.HasAPI(UsdPhysics.RigidBodyAPI):
                    owner = owner.GetParent()
                if owner == prim:
                    found.append(child.GetName())
            return found
        return [prim.GetName()] if prim.HasAPI(UsdPhysics.CollisionAPI) else []
    pairs = set()
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.FilteredPairsAPI):
            for target in UsdPhysics.FilteredPairsAPI(prim).GetFilteredPairsRel().GetTargets():
                for a in shapes(prim):
                    for b in shapes(stage.GetPrimAtPath(target)):
                        pairs.add(tuple(sorted((a, b))))
    return pairs


@pytest.mark.parametrize('filtered_body', ['a', 'b'])
@pytest.mark.parametrize('direction', ['incoming', 'outgoing', 'both'])
def test_collapse_preserves_exact_filtered_shape_pairs(tmp_path, filtered_body, direction):
    stage = _new_stage(tmp_path / 'filters.usda')
    for name in ['a', 'b', 'outside']:
        _body(stage, '/Asset/' + name)
        _collider(stage, f'/Asset/{name}/shape_{name}')
    _collider(stage, '/Asset/' + filtered_body + '/second_shape')
    nested = _body(stage, '/Asset/' + filtered_body + '/nested')
    UsdGeom.Xformable(nested).SetResetXformStack(True)
    _collider(stage, '/Asset/' + filtered_body + '/nested/shape_nested')
    _fixed_joint(stage, '/Asset/weld', '/Asset/a', '/Asset/b')
    body = stage.GetPrimAtPath('/Asset/' + filtered_body)
    outside = stage.GetPrimAtPath('/Asset/outside')
    if direction in ['incoming', 'both']:
        UsdPhysics.FilteredPairsAPI.Apply(outside).CreateFilteredPairsRel().SetTargets([body.GetPath()])
    if direction in ['outgoing', 'both']:
        UsdPhysics.FilteredPairsAPI.Apply(body).CreateFilteredPairsRel().SetTargets([outside.GetPath()])
    # Collider-local exclusions must survive expansion of the body's filters.
    shape = stage.GetPrimAtPath(f'/Asset/{filtered_body}/shape_{filtered_body}')
    UsdPhysics.FilteredPairsAPI.Apply(shape).CreateFilteredPairsRel().SetTargets(['/Asset/outside/shape_outside'])
    before = filtered_shape_pairs(stage)
    work = clone(stage)
    fixed_joint_merge.cook_stage(stage, work)
    assert filtered_shape_pairs(work) == before


@pytest.mark.parametrize('kind', ['body_is_collider', 'instanced_collider'])
def test_unsplittable_collision_filters_refuse_without_changes(tmp_path, kind):
    stage = _new_stage(tmp_path / 'filter_refusal.usda')
    body = _body(stage, '/Asset/a')
    _body(stage, '/Asset/b')
    _collider(stage, '/Asset/b/shape_b')
    _collider(stage, '/Asset/outside')
    if kind == 'body_is_collider':
        UsdGeom.Cube.Define(stage, '/Asset/a')
        UsdPhysics.CollisionAPI.Apply(body)
    else:
        source = _new_stage(tmp_path / 'prototype.usda')
        _collider(source, '/Asset/shape_a')
        source.GetRootLayer().Save()
        instance = stage.DefinePrim('/Asset/a/instance', 'Xform')
        instance.GetReferences().AddReference(str(tmp_path / 'prototype.usda'), '/Asset')
        instance.SetInstanceable(True)
    UsdPhysics.FilteredPairsAPI.Apply(body).CreateFilteredPairsRel().SetTargets(['/Asset/outside'])
    _fixed_joint(stage, '/Asset/weld', '/Asset/a', '/Asset/b')
    work = clone(stage)
    before = work.GetRootLayer().ExportToString()
    with pytest.raises(fixed_joint_merge.MergeRefused, match='filter'):
        fixed_joint_merge.cook_stage(stage, work)
    assert work.GetRootLayer().ExportToString() == before


def world_points(stage):
    points = []
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            world = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            points.extend(tuple(world.Transform(Gf.Vec3d(p))) for p in UsdGeom.Mesh(prim).GetPointsAttr().Get())
    return np.asarray(sorted(points))


@pytest.mark.parametrize("angle", [17., 30., -57., 113.])
def test_rotated_anisotropic_inertia_matches_analytic_tensor(angle):
    # Independent column-vector rotation, not the adapter's reconstruction helper.
    radians = math.radians(angle)
    c, s = math.cos(radians), math.sin(radians)
    rotation = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    diagonal = np.array([2., 3., 4.])
    body = _massprops.BodyMass('/body', 2., np.zeros(3), np.diag(diagonal))
    transform = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), angle))
    result = _massprops.aggregate([(body, transform)], Gf.Matrix4d(1.))
    expected = rotation @ np.diag(diagonal) @ rotation.T
    np.testing.assert_allclose(result.inertia, expected, atol=1e-12)
    # Read the authored quaternion using transformed basis vectors.
    q = result.principal_axes
    columns = [Gf.Rotation(Gf.Quatd(q)).TransformDir(Gf.Vec3d(*axis)) for axis in np.eye(3)]
    authored = np.array(columns).T
    np.testing.assert_allclose(authored @ np.diag(result.diagonal_inertia) @ authored.T, expected, atol=1e-6)


@pytest.mark.parametrize('seed', range(8))
def test_aggregate_random_three_dimensional_frames(seed):
    rng = np.random.default_rng(seed)
    def rotation():
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        q[:, 0] *= np.linalg.det(q)
        return q
    retained_rotation = rotation()
    retained_position = rng.normal(size=3)
    retained = Gf.Matrix4d(Gf.Matrix3d(*retained_rotation.T.ravel()), Gf.Vec3d(*retained_position))
    bodies, centers, tensors, masses = [], [], [], []
    for i in range(5):
        mass = rng.uniform(.1, 10.)
        axes = rotation()
        # Physical box principal moments, not arbitrary invalid inertia values.
        dims = rng.uniform(.1, 2., 3)
        diagonal = mass / 12. * (np.sum(dims ** 2) - dims ** 2)
        inertia = axes @ np.diag(diagonal) @ axes.T
        local_com = rng.normal(size=3)
        world_rotation, position = rotation(), rng.normal(size=3)
        transform = Gf.Matrix4d(Gf.Matrix3d(*world_rotation.T.ravel()), Gf.Vec3d(*position))
        bodies.append((_massprops.BodyMass(f'/body{i}', mass, local_com, inertia), transform))
        centers.append(retained_rotation.T @ (world_rotation @ local_com + position - retained_position))
        relative = retained_rotation.T @ world_rotation
        tensors.append(relative @ inertia @ relative.T)
        masses.append(mass)
    center = np.average(centers, axis=0, weights=masses)
    expected = sum(tensor + mass * (np.dot(delta := c - center, delta) * np.eye(3) - np.outer(delta, delta))
                   for mass, c, tensor in zip(masses, centers, tensors))
    result = _massprops.aggregate(bodies, retained)
    np.testing.assert_allclose(result.center_of_mass, center, atol=1e-12)
    np.testing.assert_allclose(result.inertia, expected, atol=1e-10)
    assert result.mass == pytest.approx(sum(masses))


@pytest.mark.parametrize('seed', range(12))
@pytest.mark.parametrize('referenced', [False, True])
def test_real_mesh_merge_preserves_world_geometry(tmp_path, seed, referenced):
    rng = np.random.default_rng(seed)
    stage = _new_stage(tmp_path / 'source.usda')
    root = UsdGeom.Xformable(stage.GetDefaultPrim())
    root.AddTranslateOp().Set(Gf.Vec3d(*rng.uniform(-3, 3, 3)))
    root.AddRotateXYZOp().Set(Gf.Vec3f(*rng.uniform(-150, 150, 3)))
    for body_index in range(2):
        path = f'/Asset/body{body_index}'
        body = _body(stage, path, translate=tuple(rng.uniform(-2, 2, 3)))
        UsdGeom.Xformable(body).AddRotateXYZOp().Set(Gf.Vec3f(*rng.uniform(-90, 90, 3)))
        _collider(stage, path + '/collider')
        for index in range(3):
            parent = UsdGeom.Xform.Define(stage, path + f'/part{index}')
            parent.AddTranslateOp().Set(Gf.Vec3d(*rng.uniform(-1, 1, 3)))
            parent.AddRotateXYZOp().Set(Gf.Vec3f(*rng.uniform(-90, 90, 3)))
            parent.AddScaleOp().Set(Gf.Vec3f(*rng.uniform(.4, 2, 3)))
            mesh = _mesh(stage, str(parent.GetPath()) + '/visual')
            UsdGeom.Xformable(mesh).AddTranslateOp().Set(Gf.Vec3d(.3, -.4, .2))
    stage.GetRootLayer().Save()
    if referenced:
        ref = _new_stage(tmp_path / 'reference.usda')
        ref.GetDefaultPrim().GetReferences().AddReference(str(tmp_path / 'source.usda'))
        stage = ref
    before = world_points(stage)
    work = clone(stage)
    assert visual_mesh_merge.cook_stage(stage, work) == 2
    # Reopen the cooked result, as a consumer does.
    work = clone(work)
    np.testing.assert_allclose(world_points(work), before, atol=3e-6, rtol=1e-6)
    assert visual_mesh_merge.cook_stage(work, work) == 0


def test_rotating_weld_preserves_aggregate_com_velocity(tmp_path):
    stage = _new_stage(tmp_path / 'motion.usda')
    for name, x, mass in [('a', 0., 2.), ('b', 2., 1.)]:
        body = _body(stage, '/Asset/' + name, translate=(x, 0., 0.), mass=mass)
        _collider(stage, '/Asset/' + name + '/collider')
        api = UsdPhysics.RigidBodyAPI(body)
        api.CreateAngularVelocityAttr().Set(Gf.Vec3f(0., 0., 90.))
        api.CreateVelocityAttr().Set(Gf.Vec3f(0., math.pi / 2 * x, 0.))
    _fixed_joint(stage, '/Asset/weld', '/Asset/a', '/Asset/b')
    work = clone(stage)
    fixed_joint_merge.cook_stage(stage, work)
    merged = UsdPhysics.RigidBodyAPI(work.GetPrimAtPath('/Asset/a'))
    np.testing.assert_allclose(merged.GetVelocityAttr().Get(), [0., math.pi / 3, 0.], atol=1e-6)
    np.testing.assert_allclose(merged.GetAngularVelocityAttr().Get(), [0., 0., 90.], atol=1e-6)


@pytest.mark.parametrize('name,typename,first,second', [
    ('physxRigidBody:disableGravity', Sdf.ValueTypeNames.Bool, False, True),
    ('physxRigidBody:linearDamping', Sdf.ValueTypeNames.Float, .1, .5),
    ('physxRigidBody:solverPositionIterationCount', Sdf.ValueTypeNames.Int, 4, 16),
    ('physics:startsAsleep', Sdf.ValueTypeNames.Bool, False, True),
])
def test_incompatible_body_settings_refused_without_partial_edit(tmp_path, name, typename, first, second):
    stage = _new_stage(tmp_path / 'settings.usda')
    for part, value in [('a', first), ('b', second)]:
        body = _body(stage, '/Asset/' + part)
        _collider(stage, '/Asset/' + part + '/collider')
        body.CreateAttribute(name, typename, custom=False).Set(value)
    _fixed_joint(stage, '/Asset/weld', '/Asset/a', '/Asset/b')
    work = clone(stage)
    before = work.GetRootLayer().ExportToString()
    with pytest.raises(fixed_joint_merge.MergeRefused, match=name):
        fixed_joint_merge.cook_stage(stage, work)
    assert work.GetRootLayer().ExportToString() == before


def test_namespace_collision_refused_without_partial_edit(tmp_path):
    stage = _new_stage(tmp_path / 'paths.usda')
    _body(stage, '/Asset/a')
    _body(stage, '/Asset/b')
    _mesh(stage, '/Asset/a/b')
    _fixed_joint(stage, '/Asset/weld', '/Asset/a', '/Asset/b')
    work = clone(stage)
    before = work.GetRootLayer().ExportToString()
    with pytest.raises(fixed_joint_merge.MergeRefused):
        fixed_joint_merge.cook_stage(stage, work)
    assert work.GetRootLayer().ExportToString() == before


def test_cleanup_instance_proxy_refuses_before_editing_other_candidates(tmp_path):
    source = _new_stage(tmp_path / 'prototype.usda')
    mesh = _mesh(source, '/Asset/visual')
    UsdPhysics.CollisionAPI.Apply(mesh).CreateCollisionEnabledAttr().Set(False)
    source.GetRootLayer().Save()
    stage = _new_stage(tmp_path / 'instances.usda')
    editable = _mesh(stage, '/Asset/a_editable')
    UsdPhysics.CollisionAPI.Apply(editable).CreateCollisionEnabledAttr().Set(False)
    instance = UsdGeom.Xform.Define(stage, '/Asset/z_instance').GetPrim()
    instance.GetReferences().AddReference(str(tmp_path / 'prototype.usda'))
    instance.SetInstanceable(True)
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(render_collision_separation.SeparationRefused, match='instance proxies'):
        render_collision_separation.cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before


def surface_samples(stage):
    """Per-corner world position, normal, UV and resolved face material."""
    result = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        normal_matrix = matrix.GetInverse().GetTranspose()
        points = mesh.GetPointsAttr().Get()
        uv = UsdGeom.PrimvarsAPI(prim).GetPrimvar('st').ComputeFlattened()
        normals = mesh.GetNormalsAttr().Get()
        interpolation = mesh.GetNormalsInterpolation()
        normal_primvar = UsdGeom.PrimvarsAPI(prim).GetPrimvar('normals')
        if normal_primvar and normal_primvar.HasValue():
            normals = normal_primvar.ComputeFlattened()
            interpolation = normal_primvar.GetInterpolation()
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        materials = [str(material.GetPath())] * len(mesh.GetFaceVertexCountsAttr().Get())
        for subset in UsdShade.MaterialBindingAPI(prim).GetMaterialBindSubsets():
            bound, _ = UsdShade.MaterialBindingAPI(subset.GetPrim()).ComputeBoundMaterial()
            for face in subset.GetIndicesAttr().Get():
                materials[face] = str(bound.GetPath())
        offset = 0
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        for face, count in enumerate(mesh.GetFaceVertexCountsAttr().Get()):
            for corner in range(offset, offset + count):
                vertex = indices[corner]
                n_index = {'constant': 0, 'uniform': face, 'vertex': vertex, 'varying': vertex, 'faceVarying': corner}[interpolation]
                normal = normal_matrix.TransformDir(Gf.Vec3d(normals[n_index])).GetNormalized()
                result.append((tuple(round(float(v), 5) for v in matrix.Transform(Gf.Vec3d(points[vertex]))),
                               tuple(round(float(v), 5) for v in normal), tuple(uv[corner]), materials[face]))
            offset += count
    return sorted(result)


@pytest.mark.parametrize('mirror', ['none', 'first', 'both'])
@pytest.mark.parametrize('reset', [False, True])
@pytest.mark.parametrize('orientation', ['leftHanded', 'rightHanded'])
def test_real_merge_preserves_normals_uvs_and_face_materials(tmp_path, mirror, reset, orientation):
    stage = _new_stage(tmp_path / 'shading.usda')
    body = _body(stage, '/Asset/body', translate=(1., 2., 3.))
    UsdGeom.Xformable(body).AddRotateXYZOp().Set(Gf.Vec3f(13., 27., 49.))
    for i in range(2):
        prim = _mesh(stage, f'/Asset/body/mesh{i}')
        mesh = UsdGeom.Mesh(prim)
        mesh.CreateSubdivisionSchemeAttr().Set('none')
        mesh.CreateOrientationAttr().Set(orientation)
        mesh.AddTranslateOp().Set(Gf.Vec3d(i, .4, -.3))
        mesh.AddRotateXYZOp().Set(Gf.Vec3f(30., 10. + i * 40., 11.))
        mirrored = mirror == 'both' or (mirror == 'first' and i == 0)
        mesh.AddScaleOp().Set(Gf.Vec3f(-2. if mirrored else 2., .7, 1.3))
        mesh.SetResetXformStack(reset)
        mesh.CreateNormalsAttr().Set([Gf.Vec3f(0, 0, 1)] * 3)
        mesh.SetNormalsInterpolation('faceVarying')
        uv = UsdGeom.PrimvarsAPI(prim).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'faceVarying')
        uv.Set([(0., 0.), (1., 0.), (0., 1.)])
        uv.SetIndices([2, 0, 1])
        material = UsdShade.Material.Define(stage, f'/Asset/material{i}')
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)

    def oriented_faces(on):
        faces = []
        for prim in on.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue
            mesh = UsdGeom.Mesh(prim)
            matrix = mesh.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            points = mesh.GetPointsAttr().Get()
            indices = mesh.GetFaceVertexIndicesAttr().Get()
            assert all(count == 3 for count in mesh.GetFaceVertexCountsAttr().Get())
            for start in range(0, len(indices), 3):
                a, b, c = [Gf.Vec3d(points[v]) for v in indices[start:start + 3]]
                normal = Gf.Cross(b - a, c - a)
                if mesh.GetOrientationAttr().Get() == 'leftHanded':
                    normal = -normal
                normal = matrix.GetInverse().GetTranspose().TransformDir(normal).GetNormalized()
                faces.append((tuple(matrix.Transform((a + b + c) / 3.)), tuple(normal)))
        return sorted(faces)

    expected = surface_samples(stage)
    expected_faces = oriented_faces(stage)
    work = clone(stage)
    visual_mesh_merge.cook_stage(stage, work)
    actual = surface_samples(clone(work))
    np.testing.assert_allclose(oriented_faces(clone(work)), expected_faces, atol=1e-6)
    assert len(actual) == len(expected)
    for before, after in zip(expected, actual):
        np.testing.assert_allclose(after[:3][0], before[:3][0], atol=1.1e-5)
        np.testing.assert_allclose(after[1], before[1], atol=1e-5)
        np.testing.assert_allclose(after[2], before[2], atol=1e-6)
        assert after[3] == before[3]


def test_merge_preserves_faces_with_repeated_subset_materials(tmp_path):
    """Repeated subsets and the remaining faces can share one material."""
    stage = _new_stage(tmp_path / 'subsets.usda')
    _body(stage, '/Asset/body')
    red = UsdShade.Material.Define(stage, '/Asset/red')
    blue = UsdShade.Material.Define(stage, '/Asset/blue')
    for i in range(2):
        mesh = UsdGeom.Mesh(_mesh(stage, f'/Asset/body/mesh{i}'))
        points = [(3. * face + x, 2. * i + y, 0.)
                  for face in range(4) for x, y in [(0., 0.), (1., 0.), (0., 1.)]]
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([3] * 4)
        mesh.CreateFaceVertexIndicesAttr(list(range(12)))
        mesh.CreateSubdivisionSchemeAttr('none')
        mesh.CreateNormalsAttr([(0., 0., 1.)] * 12)
        mesh.SetNormalsInterpolation('faceVarying')
        UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray,
                                              'faceVarying').Set([(0., 0.)] * 12)
        binding = UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim())
        binding.Bind(red)
        for name, face, material in [('red0', 0, red), ('red1', 1, red), ('blue', 2, blue)]:
            subset = binding.CreateMaterialBindSubset(name, [face])
            UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(material)
    expected = surface_samples(stage)
    original = stage.GetRootLayer().ExportToString()
    work = clone(stage)
    assert visual_mesh_merge.cook_stage(stage, work) == 1
    assert surface_samples(clone(work)) == expected
    assert len(expected) == 24
    assert stage.GetRootLayer().ExportToString() == original


def test_nested_reset_body_follows_retained_body_after_collapse(tmp_path):
    stage = _new_stage(tmp_path / 'nested.usda')
    parent = _body(stage, '/Asset/a', translate=(2., 0., 0.))
    child = _body(stage, '/Asset/a/b', translate=(4., 0., 0.))
    UsdGeom.Xformable(child).SetResetXformStack(True)
    _collider(stage, '/Asset/a/collider')
    _collider(stage, '/Asset/a/b/collider')
    _fixed_joint(stage, '/Asset/weld', '/Asset/a', '/Asset/a/b')
    work = clone(stage)
    fixed_joint_merge.cook_stage(stage, work)
    child = UsdGeom.Xformable(work.GetPrimAtPath('/Asset/a/b'))
    assert not child.GetResetXformStack()
    np.testing.assert_allclose(child.ComputeLocalToWorldTransform(0).ExtractTranslation(), [4., 0., 0.])
    UsdGeom.Xformable(work.GetPrimAtPath('/Asset/a')).GetOrderedXformOps()[0].Set(Gf.Vec3d(3., 0., 0.))
    np.testing.assert_allclose(child.ComputeLocalToWorldTransform(0).ExtractTranslation(), [5., 0., 0.])


def test_nested_weld_component_and_joint_holder_are_remapped(tmp_path):
    stage = _new_stage(tmp_path / 'nested_component.usda')
    for path, x in [('/Asset/a', 1.), ('/Asset/b', 2.), ('/Asset/b/c', 3.), ('/Asset/outside', 6.)]:
        prim = _body(stage, path, translate=(x, 0., 0.))
        if path == '/Asset/b/c':
            UsdGeom.Xformable(prim).SetResetXformStack(True)
        _collider(stage, path + '/collider')
    _fixed_joint(stage, '/Asset/weld1', '/Asset/a', '/Asset/b')
    _fixed_joint(stage, '/Asset/weld2', '/Asset/b', '/Asset/b/c')
    hinge = UsdPhysics.RevoluteJoint.Define(stage, '/Asset/b/hinge')
    hinge.CreateBody0Rel().SetTargets(['/Asset/b/c'])
    hinge.CreateBody1Rel().SetTargets(['/Asset/outside'])
    hinge.CreateLocalPos0Attr().Set(Gf.Vec3f(.5, 0., 0.))
    work = clone(stage)
    assert fixed_joint_merge.cook_stage(stage, work) == 1
    assert not work.GetPrimAtPath('/Asset/b')
    for path, x in [('/Asset/a/b', 2.), ('/Asset/a/b/c', 3.)]:
        prim = work.GetPrimAtPath(path)
        assert prim and not prim.HasAPI(UsdPhysics.RigidBodyAPI)
        np.testing.assert_allclose(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0).ExtractTranslation(), [x, 0., 0.])
    joint = UsdPhysics.Joint(work.GetPrimAtPath('/Asset/a/b/hinge'))
    assert joint.GetBody0Rel().GetTargets() == [Sdf.Path('/Asset/a')]
    np.testing.assert_allclose(joint.GetLocalPos0Attr().Get(), [2.5, 0., 0.])


@pytest.mark.parametrize('holder', ['b', 'd'])
def test_joint_between_two_collapsed_groups_keeps_both_anchors(tmp_path, holder):
    stage = _new_stage(tmp_path / 'two_components.usda')
    for index, name in enumerate('abcd'):
        _body(stage, '/Asset/' + name, translate=(float(index), 0., 0.))
        _collider(stage, '/Asset/' + name + '/collider')
    _fixed_joint(stage, '/Asset/weld1', '/Asset/a', '/Asset/b')
    _fixed_joint(stage, '/Asset/weld2', '/Asset/c', '/Asset/d')
    hinge = UsdPhysics.RevoluteJoint.Define(stage, f'/Asset/{holder}/hinge')
    hinge.CreateBody0Rel().SetTargets(['/Asset/b'])
    hinge.CreateBody1Rel().SetTargets(['/Asset/d'])
    hinge.CreateLocalPos0Attr().Set(Gf.Vec3f(.3, 0., 0.))
    hinge.CreateLocalPos1Attr().Set(Gf.Vec3f(.4, 0., 0.))
    stage.GetPrimAtPath(f'/Asset/{holder}').CreateRelationship('isaac:physics:robotLinks').SetTargets(['/Asset/b', '/Asset/d'])
    work = clone(stage)
    assert fixed_joint_merge.cook_stage(stage, work) == 2
    parent = f'/Asset/{"a" if holder == "b" else "c"}/{holder}'
    joint = UsdPhysics.Joint(work.GetPrimAtPath(parent + '/hinge'))
    assert joint.GetBody0Rel().GetTargets() == [Sdf.Path('/Asset/a')]
    assert joint.GetBody1Rel().GetTargets() == [Sdf.Path('/Asset/c')]
    np.testing.assert_allclose(joint.GetLocalPos0Attr().Get(), [1.3, 0., 0.])
    np.testing.assert_allclose(joint.GetLocalPos1Attr().Get(), [1.4, 0., 0.])
    assert not work.GetPrimAtPath('/Asset/b')
    assert not work.GetPrimAtPath('/Asset/d')
    assert work.GetPrimAtPath(parent).GetRelationship('isaac:physics:robotLinks').GetTargets() == [Sdf.Path('/Asset/a'), Sdf.Path('/Asset/c')]


@pytest.mark.parametrize('outer, moved', [('a', 'b'), ('z', 'deep/b')])
def test_nested_separate_merge_groups_preserve_frames_in_either_order(tmp_path, outer, moved):
    stage = _new_stage(tmp_path / 'nested_groups.usda')
    paths = ['/Asset/' + outer, '/Asset/' + moved,
             '/Asset/' + moved + '/c', '/Asset/' + moved + '/d']
    for index, path in enumerate(paths):
        body = _body(stage, path, translate=(float(index), 0., 0.))
        UsdGeom.Xformable(body).SetResetXformStack(True)
        _collider(stage, path + '/collider')
    _fixed_joint(stage, '/Asset/weld1', *paths[:2])
    _fixed_joint(stage, '/Asset/weld2', *paths[2:])
    hinge = UsdPhysics.RevoluteJoint.Define(stage, paths[3] + '/hinge')
    hinge.CreateBody0Rel().SetTargets([paths[1]])
    hinge.CreateBody1Rel().SetTargets([paths[3]])
    hinge.CreateLocalPos0Attr().Set(Gf.Vec3f(.3, 0., 0.))
    hinge.CreateLocalPos1Attr().Set(Gf.Vec3f(.4, 0., 0.))
    work = clone(stage)
    assert fixed_joint_merge.cook_stage(stage, work) == 2
    final_paths = [paths[0], paths[0] + '/b', paths[0] + '/b/c', paths[0] + '/b/c/d']
    for index, path in enumerate(final_paths):
        prim = work.GetPrimAtPath(path)
        assert prim
        np.testing.assert_allclose(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0).ExtractTranslation(), [float(index), 0., 0.])
        assert prim.HasAPI(UsdPhysics.RigidBodyAPI) == (index in (0, 2))
    assert not work.GetPrimAtPath(paths[1])
    joint = UsdPhysics.Joint(work.GetPrimAtPath(final_paths[3] + '/hinge'))
    assert joint.GetBody0Rel().GetTargets() == [Sdf.Path(final_paths[0])]
    assert joint.GetBody1Rel().GetTargets() == [Sdf.Path(final_paths[2])]
    np.testing.assert_allclose(joint.GetLocalPos0Attr().Get(), [1.3, 0., 0.])
    np.testing.assert_allclose(joint.GetLocalPos1Attr().Get(), [1.4, 0., 0.])


@pytest.mark.parametrize('kind', ['points', 'transform', 'visibility', 'skinning', 'inherited_skinning', 'child_collider'])
def test_visual_merge_refuses_unsupported_content_atomically(tmp_path, kind):
    stage = _new_stage(tmp_path / 'unsupported.usda')
    _body(stage, '/Asset/body')
    first = _mesh(stage, '/Asset/body/a')
    _mesh(stage, '/Asset/body/b')
    if kind == 'points':
        UsdGeom.Mesh(first).GetPointsAttr().Set([(0, 0, 0), (1, 0, 0), (0, 1, 1)], 1.)
    elif kind == 'transform':
        UsdGeom.Xformable(first).AddTranslateOp().Set(Gf.Vec3d(1, 0, 0), 1.)
    elif kind == 'visibility':
        UsdGeom.Imageable(first).CreateVisibilityAttr().Set('invisible', 1.)
    elif kind in ('skinning', 'inherited_skinning'):
        binding = first if kind == 'skinning' else first.GetParent()
        binding.AddAppliedSchema('SkelBindingAPI')
    else:
        _collider(stage, '/Asset/body/a/collider')
    work = clone(stage)
    before = work.GetRootLayer().ExportToString()
    with pytest.raises(visual_mesh_merge.MergeFailed):
        visual_mesh_merge.cook_stage(stage, work)
    assert work.GetRootLayer().ExportToString() == before


def test_cleanup_preserves_collision_enabled_later(tmp_path):
    stage = _new_stage(tmp_path / 'animated_collision.usda')
    mesh = _mesh(stage, '/Asset/render')
    enabled = UsdPhysics.CollisionAPI.Apply(mesh).CreateCollisionEnabledAttr()
    enabled.Set(False)
    enabled.Set(True, 10.)
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(render_collision_separation.SeparationRefused, match='time-sampled'):
        render_collision_separation.cook_stage(stage)
    assert stage.GetRootLayer().ExportToString() == before


def test_failure_in_second_visual_group_leaves_output_unchanged(tmp_path, monkeypatch):
    stage = _new_stage(tmp_path / 'two_groups.usda')
    for body in ['a', 'b']:
        _body(stage, '/Asset/' + body)
        _mesh(stage, '/Asset/' + body + '/one')
        _mesh(stage, '/Asset/' + body + '/two')
    original_merge = visual_mesh_merge._run_merge
    def fail_second(scratch, survivor, sources):
        if survivor.startswith('/Asset/b/'):
            raise visual_mesh_merge.MergeFailed('second group failed')
        return original_merge(scratch, survivor, sources)
    monkeypatch.setattr(visual_mesh_merge, '_run_merge', fail_second)
    work = clone(stage)
    before = work.GetRootLayer().ExportToString()
    with pytest.raises(visual_mesh_merge.MergeFailed, match='second group'):
        visual_mesh_merge.cook_stage(stage, work)
    assert work.GetRootLayer().ExportToString() == before


def test_visual_merge_retains_small_detail_far_from_world_origin(tmp_path):
    stage = _new_stage(tmp_path / 'large_coordinates.usda')
    _body(stage, '/Asset/body', translate=(1.e6, -1.e6, 1.e6))
    for index in range(2):
        prim = _mesh(stage, f'/Asset/body/m{index}')
        mesh = UsdGeom.Mesh(prim)
        mesh.CreatePointsAttr().Set([(0., 0., 0.), (.013, 0., 0.), (0., .027, 0.)])
        mesh.AddTranslateOp().Set(Gf.Vec3d(.037 * index, .019 * index, 0.))
    before = world_points(stage)
    work = clone(stage)
    visual_mesh_merge.cook_stage(stage, work)
    np.testing.assert_allclose(world_points(work), before, atol=1e-6, rtol=0)


@pytest.mark.parametrize('height', [0., .7, 2.])
@pytest.mark.parametrize('axis', ['X', 'Y', 'Z'])
def test_capsule_mass_matches_cylinder_and_hemisphere_integrals(tmp_path, height, axis):
    stage = _new_stage(tmp_path / 'capsule.usda')
    body = _body(stage, '/Asset/body')
    capsule = UsdGeom.Capsule.Define(stage, '/Asset/body/shape')
    radius = .3
    capsule.CreateRadiusAttr().Set(radius)
    capsule.CreateHeightAttr().Set(height)
    capsule.CreateAxisAttr().Set(axis)
    info = _massinfo.make_mass_information_fn(body)(capsule.GetPrim())
    cylinder = math.pi * radius ** 2 * height
    sphere = 4. / 3. * math.pi * radius ** 3
    along = cylinder * radius ** 2 / 2. + sphere * 2. * radius ** 2 / 5.
    across = cylinder * (3. * radius ** 2 + height ** 2) / 12. + sphere * (
        2. * radius ** 2 / 5. + height ** 2 / 4. + 3. * height * radius / 8.)
    diagonal = np.full(3, across)
    diagonal['XYZ'.index(axis)] = along
    assert info.volume == pytest.approx(cylinder + sphere)
    np.testing.assert_allclose(np.asarray(info.inertia), np.diag(diagonal), rtol=1e-6, atol=1e-8)


@pytest.mark.parametrize('axis', ['X', 'Y', 'Z'])
def test_cone_mass_uses_its_centroid(tmp_path, axis):
    stage = _new_stage(tmp_path / 'cone.usda')
    body = _body(stage, '/Asset/body')
    cone = UsdGeom.Cone.Define(stage, '/Asset/body/shape')
    cone.CreateHeightAttr().Set(2.)
    cone.CreateRadiusAttr().Set(.5)
    cone.CreateAxisAttr().Set(axis)
    info = _massinfo.make_mass_information_fn(body)(cone.GetPrim())
    expected = np.zeros(3)
    expected['XYZ'.index(axis)] = -.5
    np.testing.assert_allclose(info.centerOfMass, expected)


@pytest.mark.parametrize('schema', [UsdGeom.Cylinder, UsdGeom.Cone])
def test_zero_sized_shape_is_not_replaced_with_default_geometry(tmp_path, schema):
    stage = _new_stage(tmp_path / 'empty.usda')
    body = _body(stage, '/Asset/body')
    shape = schema.Define(stage, '/Asset/body/shape')
    shape.CreateRadiusAttr().Set(0.)
    info = _massinfo.make_mass_information_fn(body)(shape.GetPrim())
    assert info.volume <= 0.


def test_nonuniform_sphere_mass_is_not_guessed_from_mean_radius(tmp_path):
    stage = _new_stage(tmp_path / 'scaled_sphere.usda')
    body = UsdGeom.Xform.Define(stage, '/Asset/body').GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    sphere = UsdGeom.Sphere.Define(stage, '/Asset/body/shape')
    sphere.AddScaleOp().Set(Gf.Vec3f(2., 1., 1.))
    UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
    with pytest.raises(_massprops.MassResolutionError, match='non-uniform'):
        _massprops.resolve_body_mass(body)
    # Complete authored runtime measurements remain usable without estimating
    # the unsupported implicit collider shape.
    mass = UsdPhysics.MassAPI.Apply(body)
    mass.CreateMassAttr().Set(2.)
    mass.CreateCenterOfMassAttr().Set(Gf.Vec3f(.1, .2, .3))
    mass.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(.2, .3, .4))
    mass.CreatePrincipalAxesAttr().Set(Gf.Quatf(1.))
    resolved = _massprops.resolve_body_mass(body)
    assert resolved.mass == 2.
    np.testing.assert_allclose(resolved.center_of_mass, [.1, .2, .3])
    np.testing.assert_allclose(resolved.inertia, np.diag([.2, .3, .4]))


@pytest.mark.parametrize('missing', ['physics:centerOfMass', 'physics:principalAxes', None])
def test_approximated_mesh_requires_complete_authored_mass_frame(tmp_path, missing):
    stage = _new_stage(tmp_path / 'partial_mass.usda')
    body = _body(stage, '/Asset/body')
    if missing:
        body.RemoveProperty(missing)
    mesh = _mesh(stage, '/Asset/body/shape')
    UsdPhysics.CollisionAPI.Apply(mesh)
    UsdPhysics.MeshCollisionAPI.Apply(mesh).CreateApproximationAttr().Set('convexHull')
    if missing:
        with pytest.raises(_massprops.MassResolutionError, match='convexHull'):
            _massprops.resolve_body_mass(body)
    else:
        resolved = _massprops.resolve_body_mass(body)
        assert resolved.mass == pytest.approx(1.)
        np.testing.assert_allclose(resolved.center_of_mass, [0., 0., 0.])
        np.testing.assert_allclose(resolved.inertia, np.eye(3) * .01)


def test_collapse_accepts_one_staged_stage_for_input_and_output(welded_pair, copy_for_output):
    _source, work = copy_for_output(welded_pair)
    assert fixed_joint_merge.cook_stage(work, work) == 1
    dissolved = work.GetPrimAtPath('/Asset/Geometry/base/tip')
    assert not dissolved.HasAPI(UsdPhysics.MassAPI)
    hinge = UsdPhysics.Joint(work.GetPrimAtPath('/Asset/Joints/hinge'))
    assert hinge.GetBody0Rel().GetTargets() == [Sdf.Path('/Asset/Geometry/base')]
    np.testing.assert_allclose(hinge.GetLocalPos0Attr().Get(), [0., 0., .2], atol=1e-6)


def test_open_collision_surface_cannot_supply_a_solid_mass(tmp_path):
    stage = _new_stage(tmp_path / 'open_surface.usda')
    body = UsdGeom.Xform.Define(stage, '/Asset/body').GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    mesh = UsdGeom.Mesh.Define(stage, '/Asset/body/collider')
    mesh.CreatePointsAttr().Set([(1., 0., 0.), (0., 1., 0.), (0., 0., 1.)])
    mesh.CreateFaceVertexCountsAttr().Set([3])
    mesh.CreateFaceVertexIndicesAttr().Set([0, 1, 2])
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    with pytest.raises(_massprops.MassResolutionError, match='closed'):
        _massprops.resolve_body_mass(body)


@pytest.mark.parametrize('split_vertices', [False, True])
def test_closed_tetrahedron_mass_including_vertex_seams(tmp_path, split_vertices):
    stage = _new_stage(tmp_path / 'tetrahedron.usda')
    body = UsdGeom.Xform.Define(stage, '/Asset/body').GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    mesh = UsdGeom.Mesh.Define(stage, '/Asset/body/collider')
    points = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)]
    indices = [1, 2, 3, 0, 2, 1, 0, 1, 3, 0, 3, 2]
    if split_vertices:
        points = [points[i] for i in indices]
        indices = list(range(12))
    mesh.CreatePointsAttr().Set(points)
    mesh.CreateFaceVertexCountsAttr().Set([3] * 4)
    mesh.CreateFaceVertexIndicesAttr().Set(indices)
    info = _massinfo.make_mass_information_fn(body)(mesh.GetPrim())
    assert info.volume == pytest.approx(1. / 6.)
    np.testing.assert_allclose(info.centerOfMass, [.25] * 3)
    inertia = np.full((3, 3), 1. / 480.)
    np.fill_diagonal(inertia, 1. / 80.)
    np.testing.assert_allclose(info.inertia, inertia, atol=1e-8)

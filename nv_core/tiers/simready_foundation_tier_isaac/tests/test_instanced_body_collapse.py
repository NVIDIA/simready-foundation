# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Collapse shared geometry without editing or expanding its prototypes."""
import hashlib

import numpy as np
import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from conftest import _body, _collider, _fixed_joint, _mesh, _new_stage
from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
    fixed_joint_merge, render_collision_separation, visual_mesh_merge,
)
from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations import validation
from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations._common import (
    applied_schemas, rigid_body_owner, traverse, world_transform,
)
from test_optimization_validators import issues


def _scene(tmp_path, composition="direct", reset=False):
    prototype = _new_stage(tmp_path / "prototype.usda")
    _collider(prototype, "/Asset/collider")
    _mesh(prototype, "/Asset/visual")
    prototype.GetRootLayer().Save()
    stage = _new_stage(tmp_path / "source.usda")
    parent = UsdGeom.Xform.Define(stage, "/Asset/parts")
    parent.AddTranslateOp().Set(Gf.Vec3d(3, -5, 2))
    parent.AddRotateXYZOp().Set(Gf.Vec3f(17, 31, -23))
    material = UsdShade.Material.Define(stage, "/Asset/Looks/material")
    for name, offset, mass in [("a", (1, 0, 0), 2), ("b", (0, 2, 0), 1), ("outside", (0, 0, 3), 4)]:
        prim = _body(stage, "/Asset/parts/" + name, translate=offset, mass=mass)
        prim.GetReferences().AddReference("prototype.usda", "/Asset")
        prim.SetInstanceable(True)
        UsdGeom.Xformable(prim).AddRotateXYZOp().Set(
            Gf.Vec3f(23, -41, 12) if name == "a" else Gf.Vec3f(-19, 14, 53))
        mass_api = UsdPhysics.MassAPI(prim)
        mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(.01, .02, .025))
        mass_api.CreatePrincipalAxesAttr().Set(Gf.Quatf(Gf.Rotation(Gf.Vec3d(1, 2, 3), 47).GetQuat()))
        UsdGeom.Xformable(prim).SetResetXformStack(reset)
        prim.SetCustomDataByKey("part", name)
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)
        prim.AddAppliedSchema("PhysxRigidBodyAPI")
        prim.CreateAttribute("physxRigidBody:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(8)
        UsdPhysics.RigidBodyAPI(prim).CreateSimulationOwnerRel().SetTargets(["/Asset/scene"])
        assert prim.IsInstance()
    UsdPhysics.Scene.Define(stage, "/Asset/scene")
    _fixed_joint(stage, "/Asset/weld", "/Asset/parts/a", "/Asset/parts/b")
    hinge = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/hinge")
    hinge.CreateBody0Rel().SetTargets(["/Asset/parts/b/collider"])
    hinge.CreateBody1Rel().SetTargets(["/Asset/parts/outside"])
    hinge.CreateLocalPos0Attr().Set(Gf.Vec3f(.1, .2, .3))
    hinge.CreateLocalRot0Attr().Set(Gf.Quatf(.5, .5, .5, .5))
    stage.GetDefaultPrim().CreateRelationship("isaac:physics:robotLinks").SetTargets(
        ["/Asset/parts/a", "/Asset/parts/b", "/Asset/parts/outside"])
    stage.GetDefaultPrim().CreateRelationship("custom:visual").SetTargets(["/Asset/parts/b/visual"])
    stage.GetRootLayer().Save()
    if composition in ("reference", "payload"):
        entry = _new_stage(tmp_path / "entry.usda")
        root = entry.GetDefaultPrim()
        arc = root.GetReferences() if composition == "reference" else root.GetPayloads()
        arc.AddReference("source.usda", "/Asset") if composition == "reference" else arc.AddPayload("source.usda", "/Asset")
        entry.GetRootLayer().Save()
        stage = entry
    elif composition == "flattened":
        stage = Usd.Stage.Open(stage.Flatten())
    return stage


def _snapshot(stage):
    records = {}
    for prim in traverse(stage.GetDefaultPrim()):
        if not prim.IsInstance():
            continue
        name = prim.GetCustomDataByKey("part")
        children = {}
        for child in traverse(prim):
            if child == prim:
                continue
            children[str(child.GetPath().MakeRelativePath(prim.GetPath()))] = (
                child.GetTypeName(),
                tuple((attr.GetName(), str(attr.Get())) for attr in child.GetAttributes()
                      if not attr.GetName().startswith("xformOp")),
                str(UsdShade.MaterialBindingAPI(child).ComputeBoundMaterial()[0].GetPath()),
            )
        records[name] = (np.asarray(world_transform(prim)), children)
    return records


def _world_mass(prim):
    api = UsdPhysics.MassAPI(prim)
    transform = world_transform(prim)
    rotation = np.asarray(transform)[:3, :3].T
    axes = np.asarray(Gf.Matrix3d(Gf.Quatd(api.GetPrincipalAxesAttr().Get()))).T
    inertia = rotation @ axes @ np.diag(api.GetDiagonalInertiaAttr().Get()) @ axes.T @ rotation.T
    return api.GetMassAttr().Get(), np.asarray(transform.Transform(Gf.Vec3d(api.GetCenterOfMassAttr().Get()))), inertia


@pytest.mark.parametrize("composition", ["direct", "reference", "payload", "flattened"])
@pytest.mark.parametrize("reset", [False, True])
def test_instanced_weld_preserves_geometry_physics_and_references(tmp_path, composition, reset):
    source = _scene(tmp_path, composition, reset)
    original_files = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in tmp_path.glob("*.usda")}
    before = _snapshot(source)
    prototype_count = len({prim.GetPrototype().GetPath() for prim in traverse(source.GetDefaultPrim()) if prim.IsInstance()})
    # Copy the editable root while preserving its reference and payload arcs.
    output = Usd.Stage.CreateNew(str(tmp_path / "output.usda"))
    output.GetRootLayer().TransferContent(source.GetRootLayer())
    expected_anchor = world_transform(source.GetPrimAtPath("/Asset/parts/b")).Transform(Gf.Vec3d(.1, .2, .3))
    expected_rotation = (np.asarray(world_transform(source.GetPrimAtPath("/Asset/parts/b")))[:3, :3].T
                         @ np.asarray(Gf.Matrix3d(Gf.Quatd(.5, .5, .5, .5))).T)
    mass_parts = [_world_mass(source.GetPrimAtPath("/Asset/parts/" + name)) for name in ("a", "b")]
    total_mass = sum(m for m, _, _ in mass_parts)
    center = sum(m * c for m, c, _ in mass_parts) / total_mass
    inertia = sum(tensor + m * (np.dot(c - center, c - center) * np.eye(3)
                               - np.outer(c - center, c - center)) for m, c, tensor in mass_parts)
    assert len(issues(validation.MergeableBodyPairChecker, source)) == 1
    assert fixed_joint_merge.cook_stage(source, output) == 1
    assert render_collision_separation.cook_stage(output) == 0
    assert visual_mesh_merge.cook_stage(Usd.Stage.Open(output.Flatten()), output) == 0
    output.GetRootLayer().Save()
    output = Usd.Stage.Open(output.GetRootLayer().realPath)

    after = _snapshot(output)
    assert after.keys() == before.keys()
    for name in before:
        np.testing.assert_allclose(after[name][0], before[name][0], atol=1e-6)
        assert after[name][1] == before[name][1]
    instances = [prim for prim in traverse(output.GetDefaultPrim()) if prim.IsInstance()]
    assert len(instances) == 3
    if composition in ("direct", "flattened"):
        assert len({prim.GetPrototype().GetPath() for prim in instances}) == prototype_count
    # USD relocates can partition prototypes across reference/payload contexts.
    # Each part must still be instanced with the same composed geometry.
    compound = output.GetPrimAtPath("/Asset/parts/a_compound")
    assert compound.HasAPI(UsdPhysics.RigidBodyAPI) and not compound.IsInstance()
    assert "PhysxRigidBodyAPI" in applied_schemas(compound)
    assert UsdPhysics.MassAPI(compound).GetMassAttr().Get() == pytest.approx(3.)
    mass_after, center_after, inertia_after = _world_mass(compound)
    assert mass_after == pytest.approx(total_mass)
    np.testing.assert_allclose(center_after, center, atol=1e-6)
    np.testing.assert_allclose(inertia_after, inertia, atol=2e-6)
    assert compound.GetAttribute("physxRigidBody:solverPositionIterationCount").Get() == 8
    assert UsdPhysics.RigidBodyAPI(compound).GetSimulationOwnerRel().GetTargets() == [Sdf.Path("/Asset/scene")]
    for name in ("a", "b"):
        part = output.GetPrimAtPath(compound.GetPath().AppendChild(name))
        assert not part.HasAPI(UsdPhysics.RigidBodyAPI)
        assert not part.HasAPI(UsdPhysics.MassAPI)
        assert "PhysxRigidBodyAPI" not in applied_schemas(part)
        assert rigid_body_owner(output.GetPrimAtPath(part.GetPath().AppendChild("collider"))) == compound
    hinge = UsdPhysics.RevoluteJoint(output.GetPrimAtPath("/Asset/hinge"))
    assert hinge.GetBody0Rel().GetTargets() == [compound.GetPath()]
    np.testing.assert_allclose(world_transform(compound).Transform(Gf.Vec3d(hinge.GetLocalPos0Attr().Get())), expected_anchor, atol=1e-6)
    actual_rotation = (np.asarray(world_transform(compound))[:3, :3].T
                       @ np.asarray(Gf.Matrix3d(Gf.Quatd(hinge.GetLocalRot0Attr().Get()))).T)
    np.testing.assert_allclose(actual_rotation, expected_rotation, atol=1e-6)
    assert output.GetDefaultPrim().GetRelationship("isaac:physics:robotLinks").GetTargets() == [compound.GetPath(), Sdf.Path("/Asset/parts/outside")]
    visual_target, = output.GetDefaultPrim().GetRelationship("custom:visual").GetTargets()
    assert output.GetPrimAtPath(visual_target).IsInstanceProxy()
    for checker in (validation.MergeableBodyPairChecker, validation.MultipleVisualMeshesChecker,
                    validation.InactiveRenderCollisionSchemasChecker):
        assert issues(checker, output) == []
    saved = output.GetRootLayer().ExportToString()
    assert fixed_joint_merge.cook_stage(output, output) == 0
    assert output.GetRootLayer().ExportToString() == saved
    for path, digest in original_files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_compound_name_avoids_existing_prims(tmp_path):
    stage = _scene(tmp_path)
    sentinel = UsdGeom.Xform.Define(stage, "/Asset/parts/a_compound").GetPrim()
    sentinel.SetCustomDataByKey("keep", "unrelated")
    work = Usd.Stage.Open(stage.Flatten())
    assert fixed_joint_merge.cook_stage(stage, work) == 1
    assert work.GetPrimAtPath("/Asset/parts/a_compound").GetCustomDataByKey("keep") == "unrelated"
    assert work.GetPrimAtPath("/Asset/parts/a_compound_1").HasAPI(UsdPhysics.RigidBodyAPI)


@pytest.mark.parametrize("nested_model", [False, True])
def test_default_instance_body_and_plain_sibling_keep_referenceable_asset(tmp_path, nested_model):
    prototype = _new_stage(tmp_path / "prototype.usda")
    _collider(prototype, "/Asset/collider")
    prototype.Save()
    source = _new_stage(tmp_path / "source.usda")
    body = _body(source, "/Asset", translate=(1, 2, 3), mass=2)
    body.GetReferences().AddReference("prototype.usda", "/Asset")
    body.SetInstanceable(True)
    Usd.ModelAPI(body).SetKind("component")
    body.SetAssetInfoByKey("name", "OriginalAsset")
    body.SetDisplayName("Original asset")
    body.SetCustomDataByKey("catalogue", "fixture")
    sibling = _body(source, "/AAA", translate=(4, 5, 6))
    Usd.ModelAPI(sibling).SetKind("assembly" if nested_model else "component")
    if nested_model:
        nested = UsdGeom.Xform.Define(source, "/AAA/Model").GetPrim()
        Usd.ModelAPI(nested).SetKind("component")
    _collider(source, "/AAA/collider")
    _fixed_joint(source, "/Weld", "/Asset", "/AAA")
    work = Usd.Stage.Open(source.Flatten())
    if nested_model:
        before = work.GetRootLayer().ExportToString()
        with pytest.raises(fixed_joint_merge.MergeRefused, match="nested models"):
            fixed_joint_merge.cook_stage(source, work)
        assert work.GetRootLayer().ExportToString() == before
        return
    assert fixed_joint_merge.cook_stage(source, work) == 1
    assert work.GetDefaultPrim().GetPath() == Sdf.Path("/Asset_compound")
    assert work.GetPrimAtPath("/Asset_compound/Asset").IsInstance()
    assert Usd.ModelAPI(work.GetDefaultPrim()).GetKind() == "component"
    assert Usd.ModelAPI(work.GetPrimAtPath("/Asset_compound/Asset")).GetKind() == "subcomponent"
    assert Usd.ModelAPI(work.GetPrimAtPath("/Asset_compound/AAA")).GetKind() == "subcomponent"
    assert work.GetDefaultPrim().GetAssetInfoByKey("name") == "OriginalAsset"
    assert work.GetDefaultPrim().GetDisplayName() == "Original asset"
    assert work.GetDefaultPrim().GetCustomDataByKey("catalogue") == "fixture"
    assert UsdPhysics.MassAPI(work.GetDefaultPrim()).GetMassAttr().Get() == pytest.approx(3.)
    work.GetRootLayer().Export(str(tmp_path / "optimized.usda"))
    consumer = _new_stage(tmp_path / "consumer.usda")
    consumer.GetDefaultPrim().GetReferences().AddReference("optimized.usda")
    assert consumer.GetPrimAtPath("/Asset/Asset/collider")
    assert consumer.GetPrimAtPath("/Asset/AAA/collider")
    assert Usd.ModelAPI(consumer.GetDefaultPrim()).GetKind() == "component"
    assert consumer.GetDefaultPrim().GetAssetInfoByKey("name") == "OriginalAsset"
    assert len(issues(validation.MergeableBodyPairChecker, consumer)) == 0


def test_same_named_instance_parts_keep_distinct_geometry_and_targets(tmp_path):
    source = _scene(tmp_path)
    for old, new in (("a", "left/part"), ("b", "right/part")):
        UsdGeom.Xform.Define(source, "/Asset/parts/" + new.split("/")[0])
        editor = Usd.NamespaceEditor(source)
        editor.MovePrimAtPath("/Asset/parts/" + old, "/Asset/parts/" + new)
        assert editor.ApplyEdits()
    before = _snapshot(source)
    output = Usd.Stage.Open(source.Flatten())
    assert fixed_joint_merge.cook_stage(source, output) == 1
    after = _snapshot(output)
    assert before.keys() == after.keys()
    for name in before:
        np.testing.assert_allclose(after[name][0], before[name][0], atol=1e-6)
        assert after[name][1] == before[name][1]
    parent = "/Asset/parts/left/part_compound"
    assert output.GetPrimAtPath(parent + "/part").GetCustomDataByKey("part") == "a"
    assert output.GetPrimAtPath(parent + "/part_1").GetCustomDataByKey("part") == "b"
    hinge = UsdPhysics.RevoluteJoint(output.GetPrimAtPath("/Asset/hinge"))
    assert hinge.GetBody0Rel().GetTargets() == [Sdf.Path(parent)]


def test_instance_components_remain_models_beneath_an_assembly(tmp_path):
    source = _scene(tmp_path)
    Usd.ModelAPI(source.GetDefaultPrim()).SetKind("assembly")
    Usd.ModelAPI(source.GetPrimAtPath("/Asset/parts")).SetKind("group")
    for name in ("a", "b", "outside"):
        part = source.GetPrimAtPath("/Asset/parts/" + name)
        Usd.ModelAPI(part).SetKind("component")
        assert part.IsModel()
    output = Usd.Stage.Open(source.Flatten())
    assert fixed_joint_merge.cook_stage(source, output) == 1
    compound = output.GetPrimAtPath("/Asset/parts/a_compound")
    assert compound.IsModel() and Usd.ModelAPI(compound).GetKind() == "group"
    for name in ("a", "b"):
        part = output.GetPrimAtPath(compound.GetPath().AppendChild(name))
        assert part.IsInstance() and part.IsModel()
        assert Usd.ModelAPI(part).GetKind() == "component"


def _layered_scene(tmp_path):
    _scene(tmp_path)
    opinions = Usd.Stage.CreateNew(str(tmp_path / "opinions.usda"))
    opinions.OverridePrim("/Asset/parts/b").SetCustomDataByKey("layer", "independent opinion")
    opinions.GetRootLayer().Save()
    entry = _new_stage(tmp_path / "layered.usda")
    entry.GetRootLayer().subLayerPaths = ["opinions.usda", "source.usda"]
    entry.GetRootLayer().Save()
    return entry


def test_failed_namespace_edit_restores_all_output_layers_and_source(tmp_path, copy_for_output, monkeypatch):
    source = _layered_scene(tmp_path)
    source_layers = {layer: layer.ExportToString() for layer in source.GetLayerStack()}
    source_files = {path: path.read_bytes() for path in tmp_path.glob("*.usda")}
    _, output = copy_for_output(tmp_path / "layered.usda")
    output_layers = {layer: layer.ExportToString() for layer in output.GetLayerStack()}

    def fail_after_moves(*args):
        assert output.GetPrimAtPath("/Asset/parts/a_compound/b").IsInstance()
        assert any(layer != output.GetRootLayer() and layer.ExportToString() != before
                   for layer, before in output_layers.items())
        raise RuntimeError("injected failure after namespace edits")

    monkeypatch.setattr(fixed_joint_merge, "_remap_joint_targets", fail_after_moves)
    with pytest.raises(RuntimeError, match="injected failure after namespace edits"):
        fixed_joint_merge.cook_stage(source, output)
    assert {layer: layer.ExportToString() for layer in output.GetLayerStack()} == output_layers
    assert {layer: layer.ExportToString() for layer in source.GetLayerStack()} == source_layers
    assert {path: path.read_bytes() for path in source_files} == source_files


def test_shared_local_sublayers_are_refused_before_mutation(tmp_path, monkeypatch):
    source = _layered_scene(tmp_path)
    output = Usd.Stage.CreateNew(str(tmp_path / "shared_output.usda"))
    output.GetRootLayer().TransferContent(source.GetRootLayer())
    layers = set(source.GetLayerStack()) | set(output.GetLayerStack())
    before = {layer: layer.ExportToString() for layer in layers}
    source_files = {path: path.read_bytes() for path in tmp_path.glob("*.usda")}

    def unexpected_move(*args):
        pytest.fail("shared source layers must be refused before namespace editing")

    monkeypatch.setattr(fixed_joint_merge, "_move_under_retained", unexpected_move)
    with pytest.raises(fixed_joint_merge.MergeRefused, match="share local layers"):
        fixed_joint_merge.cook_stage(source, output)
    assert {layer: layer.ExportToString() for layer in layers} == before
    assert {path: path.read_bytes() for path in source_files} == source_files

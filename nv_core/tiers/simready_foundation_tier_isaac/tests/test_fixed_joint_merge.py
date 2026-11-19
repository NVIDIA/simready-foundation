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
"""Behaviour of the fixed-joint rigid body merge adapter.

Most of these guard against loss that the validators cannot see. The rules ask
whether an asset is optimized; they do not ask whether it still holds everything
it started with, so a merge can destroy geometry or annotation and still report
PASSED. Each such case below was a real defect first.
"""

from __future__ import annotations

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
    fixed_joint_merge,
)

MOVED = "/Asset/Geometry/base/tip"
SOURCE = "/Asset/Geometry/tip"
RETAINED = "/Asset/Geometry/base"


@pytest.fixture(params=["flat", "referenced"])
def merged(request, welded_pair, welded_pair_referenced, copy_for_output):
    """Run the adapter over both asset shapes.

    ``Usd.NamespaceEditor`` moves a locally authored prim by spec and a payloaded
    one by ``relocates``. Both paths ship, so both are tested; the flat case is
    the one where a hand-written relocate silently drops the subtree.
    """
    source = welded_pair if request.param == "flat" else welded_pair_referenced
    input_stage, output_stage = copy_for_output(source)
    count = fixed_joint_merge.cook_stage(input_stage, output_stage)
    assert count == 1
    return output_stage


def test_retained_body_is_the_one_closest_to_the_root(merged):
    """Stated explicitly: the rest of this file reads as nonsense if it flips."""
    assert merged.GetPrimAtPath(RETAINED).HasAPI(UsdPhysics.RigidBodyAPI)
    assert not merged.GetPrimAtPath(SOURCE)


def test_dissolved_body_moves_under_the_retained_body(merged):
    assert merged.GetPrimAtPath(MOVED)


def test_no_husk_is_left_at_the_old_path(merged):
    """An earlier version left an empty Xform holding the semantic labels."""
    assert not merged.GetPrimAtPath(SOURCE)


def test_children_travel_with_the_move(merged):
    names = {child.GetName() for child in merged.GetPrimAtPath(MOVED).GetChildren()}
    assert {"collider", "render"} <= names


def test_applied_schemas_travel_with_the_move(merged):
    """A relocate authored over a locally authored prim drops these silently."""
    applied = set(merged.GetPrimAtPath(MOVED).GetAppliedSchemas())
    assert "PhysicsFilteredPairsAPI" in applied


def test_custom_data_travels_with_the_move(merged):
    moved = merged.GetPrimAtPath(MOVED)
    assert moved.GetCustomDataByKey("provenance") == "authored-on-dissolved"


def test_world_pose_is_preserved(merged):
    """NamespaceEditor is a namespace edit only; the local transform is rebased."""
    world = UsdGeom.Xformable(merged.GetPrimAtPath(MOVED)).ComputeLocalToWorldTransform(0)
    assert Gf.IsClose(world.ExtractTranslation(), Gf.Vec3d(0.0, 0.0, 0.5), 1e-6)


def test_collision_geometry_survives(merged):
    """Forcing a specifier on the survivor once removed every collider."""
    colliders = [
        prim
        for prim in Usd.PrimRange(
            merged.GetDefaultPrim(), Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
        )
        if prim.HasAPI(UsdPhysics.CollisionAPI) and prim.IsActive()
    ]
    assert len(colliders) == 2


def test_dissolved_body_loses_its_body_schemas(merged):
    applied = set(merged.GetPrimAtPath(MOVED).GetAppliedSchemas())
    assert "PhysicsRigidBodyAPI" not in applied
    assert "PhysicsMassAPI" not in applied


def test_retained_body_keeps_its_rigid_body(merged):
    assert merged.GetPrimAtPath(RETAINED).HasAPI(UsdPhysics.RigidBodyAPI)


def test_mass_is_aggregated_onto_the_retained_body(merged):
    mass = UsdPhysics.MassAPI(merged.GetPrimAtPath(RETAINED)).GetMassAttr().Get()
    assert mass == pytest.approx(3.0)


def test_welding_joint_is_deactivated(merged):
    assert not merged.GetPrimAtPath("/Asset/Joints/weld").IsActive()


def test_outside_joint_names_the_retained_body(merged):
    """NamespaceEditor repoints this to the moved child, which is no longer a body.

    The adapter has to override that with the retained body, or the joint names a
    prim with no PhysicsRigidBodyAPI and the articulation quietly breaks.
    """
    hinge = UsdPhysics.Joint(merged.GetPrimAtPath("/Asset/Joints/hinge"))
    targets = [str(t) for t in hinge.GetBody0Rel().GetTargets()]
    assert targets == [RETAINED]
    assert merged.GetPrimAtPath(targets[0]).HasAPI(UsdPhysics.RigidBodyAPI)


def test_every_active_joint_still_resolves_a_rigid_body(merged):
    for prim in Usd.PrimRange(
        merged.GetDefaultPrim(), Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    ):
        if not (prim.IsA(UsdPhysics.Joint) and prim.IsActive()):
            continue
        joint = UsdPhysics.Joint(prim)
        for rel in (joint.GetBody0Rel(), joint.GetBody1Rel()):
            for target in rel.GetTargets() if rel else []:
                body = merged.GetPrimAtPath(target)
                assert body and body.HasAPI(UsdPhysics.RigidBodyAPI), (
                    f"{prim.GetPath()} names {target}, which is not a rigid body"
                )


def test_no_collider_loses_its_rigid_body_owner(merged):
    """Check collider-owner preservation where before/after state is available.

    A collider with no rigid body ancestor is valid static collision geometry,
    so a single-stage rule would incorrectly fail floors and
    walls for being floors and walls, and nothing in the composed stage separates
    that from an accident. Here the before state is available, so the question is
    answerable: the merge must not take an owner away from a collider that had one.
    """
    def owner(prim):
        node = prim
        while node and node.IsValid() and not node.IsPseudoRoot():
            if node.HasAPI(UsdPhysics.RigidBodyAPI):
                return node
            node = node.GetParent()
        return None

    for prim in Usd.PrimRange(
        merged.GetDefaultPrim(), Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    ):
        if prim.HasAPI(UsdPhysics.CollisionAPI) and prim.IsActive():
            assert owner(prim) is not None, f"{prim.GetPath()} was orphaned by the merge"


def _filtered_pairs(stage, path):
    prim = stage.GetPrimAtPath(path)
    rel = UsdPhysics.FilteredPairsAPI(prim).GetFilteredPairsRel() if prim else None
    return [str(target) for target in rel.GetTargets()] if rel else []


def test_filtered_pairs_retain_the_original_shape_scope(merged):
    """A filter for the tip must not exclude every shape on the merged body."""
    assert _filtered_pairs(merged, "/Asset/Geometry/outside") == [f"{MOVED}/collider"]


def test_remapped_relationships_leave_no_dangling_targets(merged):
    """Authoring an explicit target list must not undo the editor's own fixup."""
    for path in ("/Asset/Geometry/outside", RETAINED, MOVED):
        for target in _filtered_pairs(merged, path):
            assert merged.GetPrimAtPath(target), f"{path} names missing {target}"


def test_self_pair_is_dropped(merged):
    """The retained body filtered against the body it absorbs means nothing."""
    assert _filtered_pairs(merged, RETAINED) == []


def test_a_moved_body_keeps_its_filters_on_its_colliders(merged):
    assert _filtered_pairs(merged, MOVED) == []
    assert _filtered_pairs(merged, f"{MOVED}/collider") == ["/Asset/Geometry/outside"]


def test_robot_links_drops_the_dissolved_body(merged):
    """Repoint plus de-duplicate collapses [base, tip] to [base]."""
    targets = [
        str(t)
        for t in merged.GetPrimAtPath("/Asset").GetRelationship(
            "isaac:physics:robotLinks"
        ).GetTargets()
    ]
    assert targets == [RETAINED]
    assert all(
        merged.GetPrimAtPath(t).HasAPI(UsdPhysics.RigidBodyAPI) for t in targets
    )


def test_merge_is_idempotent(welded_pair, copy_for_output):
    """Re-running over an already merged asset must find nothing left to do."""
    input_stage, output_stage = copy_for_output(welded_pair)
    assert fixed_joint_merge.cook_stage(input_stage, output_stage) == 1
    assert fixed_joint_merge.cook_stage(output_stage, output_stage) == 0


def test_nothing_is_merged_when_nothing_is_eligible(tmp_path, copy_for_output):
    from conftest import _body, _fixed_joint, _new_stage
    path = tmp_path / "breakable.usda"
    stage = _new_stage(path)
    _body(stage, "/Asset/a")
    _body(stage, "/Asset/b", translate=(0.0, 0.0, 0.2))
    _fixed_joint(stage, "/Asset/weld", "/Asset/a", "/Asset/b", break_force=500.0)
    stage.GetRootLayer().Save()
    input_stage, output_stage = copy_for_output(path)
    assert fixed_joint_merge.cook_stage(input_stage, output_stage) == 0


def test_adapters_declare_independent_contracts_and_their_order():
    """Each mutation has a contract path; collapse runs first when both are used."""
    from simready.foundation.tier_isaac.asset_handler_modules import isaac_optimization

    definitions = isaac_optimization.feature_adapters()
    by_name = {definition.name: definition for definition in definitions}
    assert len(definitions) == 4
    assert set(by_name) == {
        "fixed_joint_rigid_body_merge",
        "remove_inactive_render_collision_schemas",
        "rigid_body_visual_mesh_merge",
        "remove_materialx_shaders",
    }
    expected_outputs = {
        "fixed_joint_rigid_body_merge": "CAP102_RigidBodyCollapse.Isaac.0-1-0",
        "remove_inactive_render_collision_schemas": "CAP104_RenderCollisionSeparation.Isaac.0-1-0",
        "rigid_body_visual_mesh_merge": "CAP103_VisualMeshMerge.Isaac.0-1-0",
        "remove_materialx_shaders": "CAP105_MaterialXRemoval.Isaac.0-1-0",
    }
    expected_priorities = {
        "fixed_joint_rigid_body_merge": 200,
        "remove_inactive_render_collision_schemas": 150,
        "rigid_body_visual_mesh_merge": 100,
        "remove_materialx_shaders": 50,
    }
    for name, definition in by_name.items():
        expected_source = ("FET006_Materials.Openpbr.0-2-0" if name == "remove_materialx_shaders"
                           else "FET003_RigidBody.0-2-0")
        assert definition.input_feature == expected_source
        assert definition.input_feature_version == "0.0.0"
        assert definition.output_feature == expected_outputs[name]
        assert definition.output_feature_version == "0.0.0"
        assert definition.priority == expected_priorities[name]
        assert definition.callback is getattr(isaac_optimization, name)
    assert [d.name for d in sorted(definitions, key=lambda d: -d.priority)] == [
        "fixed_joint_rigid_body_merge",
        "remove_inactive_render_collision_schemas",
        "rigid_body_visual_mesh_merge",
        "remove_materialx_shaders",
    ]


def test_installed_tier_advertises_the_adapter_inventory():
    from importlib.metadata import entry_points

    from simready.foundation.contracts import load_capability_definitions
    from simready.foundation.tier_isaac import tier
    from simready.foundation.tier_isaac.asset_handler_modules import isaac_optimization

    providers = [
        provider
        for provider in entry_points(group="simready.feature_adapters")
        if provider.dist is not None
        and provider.dist.name == "simready-foundation-tier-isaac"
    ]
    if not providers:
        pytest.skip("installed Isaac tier wheel not present")
    assert [provider.load() for provider in providers] == [
        isaac_optimization.feature_adapters
    ]
    definitions = providers[0].load()()
    capabilities = load_capability_definitions([tier.capability_contracts_path])
    assert {definition.output_feature for definition in definitions} == set(capabilities)
    assert all(callable(definition.callback) for definition in definitions)


def test_adapter_functions_do_not_shadow_their_modules():
    """An adapter named after its module makes the module unreachable.

    ``from . import x`` binds the submodule as a package attribute, and a later
    ``def x`` in the package __init__ rebinds it to the function. Importers then
    get the adapter instead of the implementation, and only at the point they
    reach for something on it.
    """
    from simready.foundation.tier_isaac.asset_handler_modules import isaac_optimization

    for name in ("fixed_joint_merge", "visual_mesh_merge"):
        module = getattr(isaac_optimization, name)
        assert hasattr(module, "cook_stage"), f"{name} is shadowed by {module!r}"


def test_explicit_api_schema_list_preserves_unrelated_schemas(
    welded_pair, copy_for_output
):
    """Flattened explicit schema lists must not lose unrelated APIs."""
    source_stage = Usd.Stage.Open(str(welded_pair))
    source = source_stage.GetPrimAtPath(SOURCE)
    explicit = Sdf.TokenListOp()
    explicit.explicitItems = list(source.GetAppliedSchemas())
    source_stage.GetRootLayer().GetPrimAtPath(
        Sdf.Path(SOURCE)
    ).SetInfo("apiSchemas", explicit)
    source_stage.GetRootLayer().Save()

    input_stage, output_stage = copy_for_output(welded_pair)
    assert fixed_joint_merge.cook_stage(input_stage, output_stage) == 1
    applied = set(output_stage.GetPrimAtPath(MOVED).GetAppliedSchemas())
    assert "PhysicsFilteredPairsAPI" in applied
    assert "PhysicsRigidBodyAPI" not in applied
    assert "PhysicsMassAPI" not in applied


def test_joint_outside_default_prim_is_remapped(tmp_path, copy_for_output):
    from conftest import _body, _fixed_joint, _new_stage

    path = tmp_path / "external-joint.usda"
    stage = _new_stage(path)
    _body(stage, "/Asset/base", mass=2.0)
    _body(stage, "/Asset/tip", mass=1.0)
    _body(stage, "/Asset/outside", mass=0.5)
    _fixed_joint(stage, "/Asset/weld", "/Asset/base", "/Asset/tip")
    hinge = UsdPhysics.RevoluteJoint.Define(stage, "/Rig/hinge")
    hinge.CreateBody0Rel().SetTargets([Sdf.Path("/Asset/tip")])
    hinge.CreateBody1Rel().SetTargets([Sdf.Path("/Asset/outside")])
    stage.GetRootLayer().Save()

    input_stage, output_stage = copy_for_output(path)
    assert fixed_joint_merge.cook_stage(input_stage, output_stage) == 1
    targets = [
        str(target)
        for target in UsdPhysics.Joint(
            output_stage.GetPrimAtPath("/Rig/hinge")
        ).GetBody0Rel().GetTargets()
    ]
    assert targets == ["/Asset/base"]


def _mesh_collision_body(
    stage: Usd.Stage, path: str, approximation: str, mass: float | None = None
) -> Usd.Prim:
    body = UsdGeom.Xform.Define(stage, path).GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    mesh = UsdGeom.Mesh.Define(stage, f"{path}/collider")
    mesh.CreatePointsAttr().Set(
        [
            Gf.Vec3f(0.0, 0.0, 0.0),
            Gf.Vec3f(1.0, 0.0, 0.0),
            Gf.Vec3f(0.0, 1.0, 0.0),
            Gf.Vec3f(0.0, 0.0, 1.0),
        ]
    )
    mesh.CreateFaceVertexCountsAttr().Set([3, 3, 3, 3])
    mesh.CreateFaceVertexIndicesAttr().Set(
        [0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3]
    )
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(
        mesh.GetPrim()
    ).CreateApproximationAttr().Set(approximation)
    if mass is not None:
        # The tetrahedron volume is 1/6, so this density resolves to the mass.
        UsdPhysics.MassAPI.Apply(mesh.GetPrim()).CreateDensityAttr().Set(mass * 6.0)
    return body


def test_shape_changing_mesh_mass_requires_authored_body_inertia():
    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
        _massprops,
    )

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    body = _mesh_collision_body(stage, "/Asset/body", "convexHull")

    with pytest.raises(_massprops.MassResolutionError, match="convexHull"):
        _massprops.resolve_body_mass(body)


def test_sdf_colliders_preserve_beer_bottle_reference_mass():
    """Pin the headline beer bottle's SDF-derived aggregate mass."""
    # Reference from the published POC: glass body plus metal cap.
    reference_mass = 0.9302058815956116
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    _mesh_collision_body(stage, "/Asset/body", "sdf", mass=0.9291352671)
    _mesh_collision_body(stage, "/Asset/cap", "sdf", mass=0.0010706244)
    joint = UsdPhysics.FixedJoint.Define(stage, "/Asset/weld")
    joint.CreateBody0Rel().SetTargets([Sdf.Path("/Asset/body")])
    joint.CreateBody1Rel().SetTargets([Sdf.Path("/Asset/cap")])

    assert fixed_joint_merge.cook_stage(stage, stage) == 1
    merged_mass = (
        UsdPhysics.MassAPI(stage.GetPrimAtPath("/Asset/body")).GetMassAttr().Get()
    )
    assert merged_mass == pytest.approx(reference_mass, rel=0.0, abs=1e-8)


def test_adapter_entrypoints_chain_input_to_output_and_save(monkeypatch):
    from simready.foundation.tier_isaac.asset_handler_modules import isaac_optimization

    calls = []

    class OutputStage:
        def __init__(self):
            self.saved = 0

        def Save(self):
            self.saved += 1

    input_stage = object()
    fixed_output = OutputStage()
    separation_output = OutputStage()
    visual_output = OutputStage()
    monkeypatch.setattr(
        isaac_optimization,
        "_merge_fixed_joint_bodies",
        lambda source, destination: calls.append(("fixed", source, destination)),
    )
    monkeypatch.setattr(
        isaac_optimization,
        "_separate_render_collision",
        lambda stage: calls.append(("separation", stage)),
    )
    monkeypatch.setattr(
        isaac_optimization,
        "_merge_visual_meshes",
        lambda source, destination: calls.append(("visual", source, destination)),
    )
    isaac_optimization.fixed_joint_rigid_body_merge(input_stage, fixed_output)
    isaac_optimization.remove_inactive_render_collision_schemas(
        input_stage, separation_output
    )
    isaac_optimization.rigid_body_visual_mesh_merge(input_stage, visual_output)

    assert calls == [
        ("fixed", input_stage, fixed_output),
        ("separation", separation_output),
        ("visual", input_stage, visual_output),
    ]
    assert fixed_output.saved == 1
    assert separation_output.saved == 1
    assert visual_output.saved == 1

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
"""Merge rigid bodies welded by unbreakable fixed joints.

Eligibility is shared with validation through :mod:`._eligible`. Whole subtrees
move under the retained body, preserving geometry, colliders and annotations.
The adapter aggregates mass and motion, then remaps joints and collision filters.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdPhysics

from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations._common import (
    BODY_RELATIONSHIPS,
    DISSOLVED_BODY_SCHEMAS,
    TRANSFORM_TOLERANCE,
    active_joints,
    applied_schemas,
    is_joint_enabled,
    resolved_joint_bodies,
    rigid_body_owner,
    traverse,
    world_transform,
)

from . import _eligible, _massprops

ADAPTER_NAME = "fixed_joint_rigid_body_merge"
ADAPTER_VERSION = "1.0.2"


@dataclass(frozen=True)
class GroupResult:
    retained: str
    frame_body: str
    dissolved: list[str]
    mass: float
    center_of_mass: tuple[float, float, float]
    diagonal_inertia: tuple[float, float, float]
    principal_axes: Gf.Quatf
    velocity: Gf.Vec3f
    angular_velocity: Gf.Vec3f


def _without_schemas(existing: Sdf.TokenListOp, stale: list[str]) -> Sdf.TokenListOp:
    """Remove stale schemas without changing unrelated list-op opinions."""
    stale_set = set(stale)
    op = Sdf.TokenListOp()
    if existing.isExplicit:
        op.explicitItems = [
            token for token in existing.explicitItems if token not in stale_set
        ]
        return op

    for field_name in (
        "addedItems",
        "prependedItems",
        "appendedItems",
        "orderedItems",
    ):
        setattr(
            op,
            field_name,
            [token for token in getattr(existing, field_name) if token not in stale_set],
        )
    op.deletedItems = list(existing.deletedItems) + [
        token for token in stale if token not in existing.deletedItems
    ]
    return op


def _aggregate(
    stage: Usd.Stage, retained: str, members: list[str]
) -> GroupResult:
    bodies = [
        (_massprops.resolve_body_mass(stage.GetPrimAtPath(p)),
         world_transform(stage.GetPrimAtPath(p)))
        for p in members
    ]
    agg = _massprops.aggregate(bodies, world_transform(stage.GetPrimAtPath(retained)))
    velocities = []
    angular_velocities = []
    centers = []
    for body, transform in bodies:
        api = UsdPhysics.RigidBodyAPI(stage.GetPrimAtPath(body.path))
        velocities.append(np.array(api.GetVelocityAttr().Get(), dtype=float))
        angular_velocities.append(np.array(api.GetAngularVelocityAttr().Get(), dtype=float))
        centers.append(np.array(transform.Transform(Gf.Vec3d(*body.center_of_mass))))
    masses = np.array([body.mass for body, _ in bodies])
    velocity = np.average(velocities, axis=0, weights=masses)
    center = np.average(centers, axis=0, weights=masses)
    omega = angular_velocities[0]
    # One rigid body can represent only one coherent rigid velocity field.
    # USD linear velocity is at the COM in world space; angular velocity uses
    # degrees per second. Preserve the field at the aggregate COM.
    for (body, _), v, w, c in zip(bodies, velocities, angular_velocities, centers):
        expected = velocity + np.cross(np.deg2rad(omega), c - center)
        if not np.allclose(w, omega, atol=1e-5) or not np.allclose(v, expected, atol=1e-5):
            raise MergeRefused(f"<{body.path}>: physics:velocity / physics:angularVelocity do not describe one rigid motion")
    destination = _retained_path(stage, retained)
    return GroupResult(
        retained=destination,
        frame_body=retained,
        dissolved=[m for m in members if m != destination],
        mass=float(agg.mass),
        center_of_mass=(
            float(agg.center_of_mass[0]),
            float(agg.center_of_mass[1]),
            float(agg.center_of_mass[2]),
        ),
        diagonal_inertia=(
            float(agg.diagonal_inertia[0]),
            float(agg.diagonal_inertia[1]),
            float(agg.diagonal_inertia[2]),
        ),
        principal_axes=agg.principal_axes,
        velocity=Gf.Vec3f(*velocity),
        angular_velocity=Gf.Vec3f(*omega),
    )


def _preflight(stage: Usd.Stage, groups: dict[str, list[str]]) -> None:
    """Reject unsupported authored behavior before changing any joint or prim."""
    group_for_body = {body: retained for retained, members in groups.items() for body in members}
    dissolved = set(_eligible.dissolved_joints(stage))
    for joint in active_joints(stage):
        if str(joint.GetPath()) in dissolved:
            for attr in joint.GetAuthoredAttributes():
                if attr.GetName().startswith("physics:") and attr.GetNumTimeSamples():
                    raise MergeRefused(f"<{joint.GetPath()}>: time-sampled {attr.GetName()} cannot be collapsed")
            continue
        if (not is_joint_enabled(joint)
                and not UsdPhysics.Joint(joint).GetJointEnabledAttr().GetNumTimeSamples()):
            continue
        body0, body1 = resolved_joint_bodies(stage, joint)
        if (body0 and body1 and body0[0] in group_for_body
                and group_for_body[body0[0]] == group_for_body.get(body1[0])):
            raise MergeRefused(f"<{joint.GetPath()}>: surviving joint would connect the same rigid body")
    for retained, members in groups.items():
        destination = _retained_path(stage, retained)
        prims = [stage.GetPrimAtPath(path) for path in members]
        if destination != retained and any(prim.IsModel() for prim in prims) and not stage.GetPrimAtPath(retained).IsModel():
            raise MergeRefused(f"<{retained}>: model parts require a retained model hierarchy")
        component_root = (destination != retained and stage.GetDefaultPrim() == stage.GetPrimAtPath(retained)
                          and Usd.ModelAPI(stage.GetDefaultPrim()).GetKind() == "component")
        names = {a.GetName() for prim in prims for a in prim.GetAuthoredAttributes()
                 if a.GetName().startswith('physxRigidBody:') or a.GetName() == 'physics:startsAsleep'}
        for name in sorted(names):
            values = [prim.GetAttribute(name).Get() for prim in prims]
            if any(value != values[0] for value in values[1:]):
                raise MergeRefused(f"<{retained}>: incompatible {name} across {members}")
        owners = [tuple(UsdPhysics.RigidBodyAPI(prim).GetSimulationOwnerRel().GetTargets()) for prim in prims]
        if any(owner != owners[0] for owner in owners[1:]):
            raise MergeRefused(f"<{retained}>: incompatible physics:simulationOwner")
        targets = set()
        for prim in prims:
            path = str(prim.GetPath())
            api = UsdPhysics.RigidBodyAPI(prim)
            if prim.GetCustomDataByKey("physics:localSpaceVelocities") and any(
                    value != 0 for velocity in (api.GetVelocityAttr().Get(), api.GetAngularVelocityAttr().Get())
                    for value in velocity):
                raise MergeRefused(f"<{path}>: nonzero local-space velocities require conversion to world space before collapse")
            if component_root and any(
                    child != prim and Kind.Registry.IsA(Usd.ModelAPI(child).GetKind(), "model")
                    for child in traverse(prim)):
                raise MergeRefused(f"<{path}>: nested models require a separate component hierarchy authoring step")
            if prim.IsInstanceProxy():
                raise MergeRefused(f"<{path}>: a rigid body inside an instance is not editable")
            if path != destination and prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                raise MergeRefused(f"<{path}>: an articulation root cannot be dissolved")
            for attr in prim.GetAttributes():
                if attr.GetName().startswith(('physics:', 'physxRigidBody:')) and attr.GetNumTimeSamples():
                    raise MergeRefused(f"<{path}>: time-sampled {attr.GetName()} cannot be collapsed")
            ancestor = prim
            while ancestor and not ancestor.IsPseudoRoot():
                if UsdGeom.Xformable(ancestor) and UsdGeom.Xformable(ancestor).TransformMightBeTimeVarying():
                    raise MergeRefused(f"<{path}>: time-varying transform cannot be collapsed")
                ancestor = ancestor.GetParent()
            if path != destination:
                target = _final_path(path, destination, members, destination != retained)
                if target in targets or (target != path and stage.GetPrimAtPath(target)):
                    raise MergeRefused(f"<{path}>: destination <{target}> already exists")
                targets.add(target)


def cook_stage(input_stage: Usd.Stage, output_stage: Usd.Stage) -> int:
    """Apply the merge transactionally across the staged output's local layers."""
    if input_stage == output_stage:
        input_stage = Usd.Stage.Open(input_stage.Flatten())
    layers = output_stage.GetLayerStack()
    if set(layers) & set(input_stage.GetLayerStack()):
        if not _eligible.merge_groups(input_stage):
            return 0
        raise MergeRefused("Input and output share local layers; stage writable copies of the sublayers before collapsing")
    before = {layer: layer.ExportToString() for layer in layers}
    try:
        return _cook_stage(input_stage, output_stage)
    except Exception:
        for layer, content in before.items():
            layer.ImportFromString(content)
        raise


def _cook_stage(input_stage: Usd.Stage, output_stage: Usd.Stage) -> int:
    """Merge every eligible assembly on ``output_stage``.

    Returns the number of assemblies merged, zero when none are eligible.
    """
    groups = _eligible.merge_groups(input_stage)
    if not groups:
        return 0

    _preflight(input_stage, groups)
    results = [_aggregate(input_stage, r, m) for r, m in sorted(groups.items())]

    for joint_path in _eligible.dissolved_joints(input_stage):
        output_stage.OverridePrim(Sdf.Path(joint_path)).SetActive(False)
    moves: list[tuple[Sdf.Path, Sdf.Path]] = []
    for result in results:
        if result.retained != result.frame_body:
            _create_compound_body(
                output_stage,
                _after_moves(Sdf.Path(result.frame_body), moves),
                _after_moves(Sdf.Path(result.retained), moves),
            )
        for dissolved in result.dissolved:
            source_path = _after_moves(Sdf.Path(dissolved), moves)
            target_path = _after_moves(Sdf.Path(_final_path(
                dissolved, result.retained, result.dissolved, result.retained != result.frame_body)), moves)
            _move_under_retained(output_stage, source_path, target_path)
            if source_path != target_path:
                moves.append((source_path, target_path))
            prim = output_stage.OverridePrim(target_path)
            root = output_stage.GetDefaultPrim()
            if (result.retained != result.frame_body and root
                    and root.GetPath() == _after_moves(Sdf.Path(result.retained), moves)
                    and Usd.ModelAPI(root).GetKind() == "component"
                    and Kind.Registry.IsA(Usd.ModelAPI(prim).GetKind(), "model")):
                Usd.ModelAPI(prim).SetKind("subcomponent")
            prim.RemoveAPI(UsdPhysics.RigidBodyAPI)
            # Delete list ops remove body-only schemas across weaker layers.
            source = input_stage.GetPrimAtPath(Sdf.Path(dissolved))
            applied = set(applied_schemas(source))
            stale = [s for s in DISSOLVED_BODY_SCHEMAS if s in applied]
            if stale:
                spec = output_stage.GetEditTarget().GetLayer().GetPrimAtPath(
                    target_path
                )
                existing = (
                    spec.GetInfo("apiSchemas")
                    if spec and spec.HasInfo("apiSchemas")
                    else Sdf.TokenListOp()
                )
                # Flattened assets can use explicit schema lists.
                spec.SetInfo("apiSchemas", _without_schemas(existing, stale))

    for result in results:
        prim = output_stage.OverridePrim(_after_moves(Sdf.Path(result.retained), moves))
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr().Set(result.mass)
        mass_api.CreateCenterOfMassAttr().Set(Gf.Vec3f(*result.center_of_mass))
        mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(*result.diagonal_inertia))
        mass_api.CreatePrincipalAxesAttr().Set(result.principal_axes)
        body_api = UsdPhysics.RigidBodyAPI(prim)
        body_api.CreateVelocityAttr().Set(result.velocity)
        body_api.CreateAngularVelocityAttr().Set(result.angular_velocity)
        _remap_joint_targets(output_stage, input_stage, result, moves)
        _remap_body_relationships(output_stage, input_stage, result, moves)
    _preserve_filtered_pairs(output_stage, input_stage, results, moves)
    return len(results)


class MergeRefused(RuntimeError):
    """The merge cannot be performed without losing data."""


def _retained_path(stage: Usd.Stage, retained: str) -> str:
    """An instance keeps its shared children under a new, editable body parent."""
    if not stage.GetPrimAtPath(retained).IsInstance():
        return retained
    candidate = retained + "_compound"
    suffix = 1
    while stage.GetPrimAtPath(candidate):
        candidate = f"{retained}_compound_{suffix}"
        suffix += 1
    return candidate


def _create_compound_body(stage: Usd.Stage, source: Sdf.Path, target: Sdf.Path) -> None:
    """Carry the retained body's frame and solver settings onto a plain Xform.

    Instance roots can move whole, but cannot acquire new children. Their
    references, materials and geometry stay on those roots; only body settings
    belong on this new parent. Collision filters are handled at shape scope.
    """
    prim = stage.GetPrimAtPath(source)
    original = UsdGeom.Xformable(prim)
    flattened = stage.Flatten()
    body = UsdGeom.Xform.Define(stage, target)
    if stage.GetDefaultPrim() == prim:
        # Preserve published asset identity on the replacement root.
        for name in ("kind", "assetInfo", "displayName", "customData"):
            if prim.HasAuthoredMetadata(name):
                body.GetPrim().SetMetadata(name, prim.GetMetadata(name))
        stage.SetDefaultPrim(body.GetPrim())
    elif prim.IsModel():
        # Keep the existing parts as models within their assembly hierarchy.
        Usd.ModelAPI(body.GetPrim()).SetKind("group")
    body.AddTransformOp().Set(original.GetLocalTransformation())
    body.SetResetXformStack(original.GetResetXformStack())
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    if "PhysxRigidBodyAPI" in applied_schemas(prim):
        body.GetPrim().AddAppliedSchema("PhysxRigidBodyAPI")
    names = set(UsdPhysics.RigidBodyAPI.GetSchemaAttributeNames())
    for prop in prim.GetAuthoredProperties():
        if prop.GetName() in names or prop.GetName().startswith("physxRigidBody:") or prop.GetName() == "physics:simulationOwner":
            Sdf.CopySpec(flattened, prop.GetPath(), stage.GetEditTarget().GetLayer(),
                         target.AppendProperty(prop.GetName()))


def _final_path(dissolved: str, retained: str, members: Sequence[str] = (), unique_children: bool = False) -> str:
    """Where a dissolved body ends up: unchanged if already inside the retained body."""
    path = Sdf.Path(dissolved)
    if path.HasPrefix(Sdf.Path(retained)):
        return dissolved
    ancestors = [Sdf.Path(p) for p in members if p != retained and path.HasPrefix(Sdf.Path(p))]
    source = min(ancestors, key=lambda p: p.pathElementCount) if ancestors else path
    name = source.name
    if unique_children:
        # A new compound has no children yet. Give independent part roots unique
        # deterministic names; nested members travel with their ancestor.
        paths = [Sdf.Path(p) for p in members]
        roots = sorted(p for p in paths if not any(p != q and p.HasPrefix(q) for q in paths))
        used = set()
        for root in roots:
            name, suffix = root.name, 1
            while name in used:
                name = f"{root.name}_{suffix}"
                suffix += 1
            used.add(name)
            if root == source:
                break
    return str(path.ReplacePrefix(source, Sdf.Path(retained).AppendChild(name)))


def _move_under_retained(work: Usd.Stage, source: Sdf.Path, target: Sdf.Path) -> None:
    """Move the whole body subtree while preserving its world pose.

    NamespaceEditor moves local specs or authors relocates for referenced prims,
    and updates relationship paths. Recompute the local transform for the new parent.
    """
    if source == target and not UsdGeom.Xformable(work.GetPrimAtPath(source)).GetResetXformStack():
        return  # already inherits the retained body's motion

    local = world_transform(work.GetPrimAtPath(source)) * world_transform(
        work.GetPrimAtPath(target.GetParentPath())
    ).GetInverse()

    if source != target:
        editor = Usd.NamespaceEditor(work)
        editor.MovePrimAtPath(source, target)
        allowed = editor.CanApplyEdits()
        if not allowed:
            raise MergeRefused(
                f"<{source}> cannot be moved to <{target}>: {allowed.whyNot}"
            )
        if not editor.ApplyEdits():
            raise MergeRefused(f"<{source}>: namespace edit failed")

    xformable = UsdGeom.Xformable(work.GetPrimAtPath(target))
    xformable.ClearXformOpOrder()
    xformable.AddTransformOp().Set(local)


def _rebase_joint_anchor(
    work: Usd.Stage, on: Usd.Stage, joint_prim: Usd.Prim, body_rel: str,
    was: Sdf.Path, now: str, joint_path: Sdf.Path,
) -> None:
    """Preserve the joint anchor's world pose when changing its body frame."""
    index = body_rel[-1]
    joint = UsdPhysics.Joint(joint_prim)
    pos_attr = joint.GetLocalPos0Attr() if index == "0" else joint.GetLocalPos1Attr()
    rot_attr = joint.GetLocalRot0Attr() if index == "0" else joint.GetLocalRot1Attr()

    old_body = on.GetPrimAtPath(was)
    new_body = on.GetPrimAtPath(Sdf.Path(now))
    if not old_body or not new_body:
        return

    old_world = world_transform(old_body)
    new_inverse = world_transform(new_body).GetInverse()
    if Gf.IsClose(old_world * new_inverse, Gf.Matrix4d(1.0), TRANSFORM_TOLERANCE):
        return  # frames coincide; rewriting would only add noise

    override = work.OverridePrim(joint_path)
    rebased = UsdPhysics.Joint(override)

    position = pos_attr.Get() if pos_attr else Gf.Vec3f(0.0)
    world_point = old_world.Transform(Gf.Vec3d(*position))
    target = rebased.CreateLocalPos0Attr() if index == "0" else rebased.CreateLocalPos1Attr()
    target.Set(Gf.Vec3f(*new_inverse.Transform(world_point)))

    rotation = rot_attr.Get() if rot_attr else Gf.Quatf(1.0)
    delta = (old_world * new_inverse).ExtractRotationQuat()
    combined = delta * Gf.Quatd(rotation.GetReal(), Gf.Vec3d(*rotation.GetImaginary()))
    target_rot = rebased.CreateLocalRot0Attr() if index == "0" else rebased.CreateLocalRot1Attr()
    target_rot.Set(Gf.Quatf(float(combined.GetReal()), Gf.Vec3f(*combined.GetImaginary())))


def _remap_joint_targets(
    work: Usd.Stage, on: Usd.Stage, result: GroupResult,
    moves: Sequence[tuple[Sdf.Path, Sdf.Path]],
) -> None:
    """Repoint joint endpoints at the retained body and preserve their anchors.

    NamespaceEditor updates paths; dissolved bodies also need ownership remapping.
    """
    dissolved = {Sdf.Path(d) for d in result.dissolved}
    if not dissolved:
        return

    def lands_on_dissolved(target: Sdf.Path) -> bool:
        owner = rigid_body_owner(on.GetPrimAtPath(target))
        return owner is not None and owner.GetPath() in dissolved

    # Read source composition; a destination overlay may not contain the joints.
    for joint_prim in active_joints(on):
        joint = UsdPhysics.Joint(joint_prim)
        if not joint:
            continue
        for name, rel in (("physics:body0", joint.GetBody0Rel()),
                          ("physics:body1", joint.GetBody1Rel())):
            targets = list(rel.GetTargets()) if rel else []
            if not targets or not any(lands_on_dissolved(t) for t in targets):
                continue
            joint_path = _after_moves(joint_prim.GetPath(), moves)
            override = work.OverridePrim(joint_path)
            override.CreateRelationship(name, custom=False).SetTargets([
                _after_moves(Sdf.Path(result.retained) if lands_on_dissolved(t) else t, moves)
                for t in targets
            ])

            # Preserve the anchor when replacing its body's coordinate frame.
            moved = next(t for t in targets if lands_on_dissolved(t))
            _rebase_joint_anchor(work, on, joint_prim, name, moved, result.frame_body, joint_path)


def _after_moves(path: Sdf.Path, moves: Sequence[tuple[Sdf.Path, Sdf.Path]]) -> Sdf.Path:
    """Replay namespace moves, including ancestors moved by another component."""
    for source, target in moves:
        if path.HasPrefix(source):
            path = path.ReplacePrefix(source, target)
    return path


def _remap_body_relationships(
    work: Usd.Stage, on: Usd.Stage, result: GroupResult,
    moves: Sequence[tuple[Sdf.Path, Sdf.Path]],
) -> None:
    """Repoint and deduplicate body identity lists after all namespace moves.

    Read targets from ``work`` so writing a relationship preserves the namespace
    editor's fixup for its other targets. Collision filters have shape-level
    scope and are handled separately by ``_preserve_filtered_pairs``.
    """
    if not result.dissolved:
        return
    retained = _after_moves(Sdf.Path(result.retained), moves)
    moved = {_after_moves(Sdf.Path(d), moves) for d in result.dissolved}

    for prim in traverse(on.GetPseudoRoot()):
        for name in BODY_RELATIONSHIPS:
            if name == "physics:filteredPairs" or not prim.GetRelationship(name):
                continue
            holder = _after_moves(prim.GetPath(), moves)
            current = work.GetPrimAtPath(holder)
            rel = current.GetRelationship(name) if current else None
            targets = list(rel.GetTargets()) if rel else []
            if not any(t in moved for t in targets):
                continue

            remapped = []
            for target in targets:
                repointed = retained if target in moved else target
                if repointed not in remapped:
                    remapped.append(repointed)
            work.OverridePrim(holder).CreateRelationship(
                name, custom=False
            ).SetTargets(remapped)


def _preserve_filtered_pairs(
    work: Usd.Stage, on: Usd.Stage, results: Sequence[GroupResult],
    moves: Sequence[tuple[Sdf.Path, Sdf.Path]],
) -> None:
    """Keep each body's collision exclusions scoped to its original shapes.

    A retained body acquires more shapes, and a dissolved body ceases to be a
    filter endpoint. Expand both ends of affected body filters to their original
    colliders, preserving collider-local exclusions and independent nested bodies.
    """
    bodies = {Sdf.Path(path) for result in results for path in [result.frame_body, *result.dissolved]}
    shapes: dict[Sdf.Path, list[Sdf.Path]] = {}

    def endpoints(path: Sdf.Path) -> list[Sdf.Path]:
        if path not in bodies:
            return [_after_moves(path, moves)]
        if path not in shapes:
            shapes[path] = []
            for prim in traverse(on.GetPrimAtPath(path)):
                if prim.HasAPI(UsdPhysics.CollisionAPI) and rigid_body_owner(prim).GetPath() == path:
                    destination = _after_moves(prim.GetPath(), moves)
                    if work.GetPrimAtPath(destination).HasAPI(UsdPhysics.RigidBodyAPI):
                        raise MergeRefused(f"<{path}>: collision filters on a retained body that is itself a collider cannot be split")
                    shapes[path].append(destination)
        return shapes[path]

    desired: dict[Sdf.Path, set[Sdf.Path]] = {}
    for prim in traverse(on.GetPseudoRoot()):
        if not prim.HasAPI(UsdPhysics.FilteredPairsAPI):
            continue
        targets = UsdPhysics.FilteredPairsAPI(prim).GetFilteredPairsRel().GetTargets()
        if not targets:
            continue
        source = prim.GetPath()
        if source in bodies:
            desired.setdefault(_after_moves(source, moves), set())
        expanded = {item for target in targets for item in endpoints(target)}
        for destination in endpoints(source):
            desired.setdefault(destination, set()).update(expanded - {destination})

    for path, targets in desired.items():
        prim = work.GetPrimAtPath(path)
        current = prim.GetRelationship("physics:filteredPairs")
        if set(current.GetTargets() if current else []) == targets:
            continue
        if prim.IsInstanceProxy():
            raise MergeRefused(f"<{path}>: collision filter preservation requires an editable collider")
        UsdPhysics.FilteredPairsAPI.Apply(prim).CreateFilteredPairsRel().SetTargets(sorted(targets))

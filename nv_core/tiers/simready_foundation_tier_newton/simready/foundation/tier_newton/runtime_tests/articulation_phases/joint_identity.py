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
"""Neutral physical joint identity, owned by this runtime tier."""

from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)

# Canonical no-break values, not a tolerance on arbitrary large strengths.
_UNBREAKABLE_STRENGTHS = (float("inf"), float.fromhex("0x1.fffffep+127"))


class JointIdentityError(RequiredReadbackError):
    """Selected physical/native joint ownership could not be resolved."""


def native_joint_name(name):
    """Normalize only the SDK's documented axis suffix, never foreign paths."""
    text = str(name)
    base, separator, axis = text.rpartition(":")
    return base if separator and axis.isdigit() else text


def _joint_body_paths(stage, prim):
    from pxr import UsdPhysics

    joint = UsdPhysics.Joint(prim)
    result = []
    for relationship in (joint.GetBody0Rel(), joint.GetBody1Rel()):
        targets = relationship.GetForwardedTargets()
        if len(targets) > 1:
            raise JointIdentityError(f"Joint endpoint is ambiguous: {prim.GetPath()}")
        body = None
        if targets:
            target = stage.GetPrimAtPath(targets[0])
            if not targets[0].IsPrimPath() or not target or not target.IsValid():
                raise JointIdentityError(f"Joint endpoint is missing: {targets[0]}")
            while target and not target.IsPseudoRoot():
                if target.HasAPI(UsdPhysics.RigidBodyAPI):
                    body = str(target.GetPath())
                    break
                target = target.GetParent()
        result.append(body)
    return tuple(result)


def _resolve_articulation_root_body(stage, path, asset_path):
    from pxr import Sdf, UsdPhysics

    prim = stage.GetPrimAtPath(path)
    if prim.HasAPI(UsdPhysics.RigidBodyAPI):
        return str(prim.GetPath())
    if prim.IsA(UsdPhysics.Joint):
        endpoints = [body for body in _joint_body_paths(stage, prim) if body]
        if len(endpoints) == 1 and Sdf.Path(endpoints[0]).HasPrefix(Sdf.Path(asset_path)):
            return endpoints[0]
    return None


def selected_joint_prims(stage, root_path, dof_names=(), asset_prim=None):
    """Enumerate exact selected physical joints before any native-name mapping."""
    from types import SimpleNamespace

    from pxr import Usd, UsdPhysics

    if stage is None or not root_path:
        return []
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return []
    robot = SimpleNamespace(prim_path=root_path, dof_names=list(dof_names), asset_prim=asset_prim)
    if asset_prim is None and (root.IsA(UsdPhysics.Joint) or root.HasAPI(UsdPhysics.RigidBodyAPI)):
        return []
    analysis_path, selected = discovery_scope(stage, robot, None)
    analysis = stage.GetPrimAtPath(analysis_path)
    return [
        prim
        for prim in Usd.PrimRange(analysis, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.IsA(UsdPhysics.Joint)
        and (selected is None or str(prim.GetPath()) in selected)
        and UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is not False
    ]


def joint_for_native_name(joints, name):
    """Return one exact selected identity, or unknown for absent/ambiguous names."""
    text = native_joint_name(name)
    matches = [joint for joint in joints if str(joint.GetPath()) == text]
    if not matches:
        matches = [joint for joint in joints if joint.GetName() == native_joint_name(text)]
    return matches[0] if len(matches) == 1 else None


def discovery_scope(stage, robot, explicit_root):
    """Select physical ownership independently of the requested search subtree.

    Body/joint roots can have sibling joints in the verified loaded asset.
    Explicit roots constrain enumeration, including deliberately narrow scopes.
    Native joint identities select a container's connected articulation after
    separately declared foreign articulation components have been removed.
    """
    from pxr import Usd, UsdPhysics

    search_path = str(explicit_root or robot.prim_path)
    search = stage.GetPrimAtPath(search_path)
    root = stage.GetPrimAtPath(robot.prim_path)
    if not search or not search.IsValid() or not root or not root.IsValid():
        return search_path, None
    asset = getattr(robot, "asset_prim", None)
    if asset is not None:
        if (
            not asset
            or not asset.IsValid()
            or asset.GetStage() != stage
            or not root.GetPath().HasPrefix(asset.GetPath())
            or not search.GetPath().HasPrefix(asset.GetPath())
        ):
            raise JointIdentityError("Selected joint discovery requires a verified loaded asset subtree")
    elif root.IsA(UsdPhysics.Joint) or root.HasAPI(UsdPhysics.RigidBodyAPI):
        raise JointIdentityError("Selected joint body/joint-root discovery requires a verified loaded asset boundary")
    else:
        # Conventional callers already supply their bounded container. Never
        # climb it to an inferred wrapper, room or another loaded asset.
        asset = search if root.GetPath().HasPrefix(search.GetPath()) else root
    asset_path = str(asset.GetPath())
    try:
        prims = list(Usd.PrimRange(asset, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)))
        body_paths = {str(prim.GetPath()) for prim in prims if prim.HasAPI(UsdPhysics.RigidBodyAPI)}
        if not body_paths:
            # Schema-light topology callers have no cooked rigid-body ownership
            # to distinguish; retain their explicitly bounded enumeration.
            return str(explicit_root or asset_path), None
        adjacency = {path: set() for path in body_paths}
        endpoints_by_joint = {}
        for prim in prims:
            if not prim.IsA(UsdPhysics.Joint):
                continue
            joint = UsdPhysics.Joint(prim)
            if joint.GetJointEnabledAttr().Get() is False:
                continue
            endpoints = {path for path in _joint_body_paths(stage, prim) if path}
            endpoints_by_joint[str(prim.GetPath())] = endpoints
            if joint.GetExcludeFromArticulationAttr().Get():
                continue
            if endpoints and endpoints.issubset(body_paths):
                for body in endpoints:
                    adjacency[body].update(endpoints - {body})

        def connected(seed):
            found, pending = {seed}, [seed]
            while pending:
                for body in adjacency[pending.pop()] - found:
                    found.add(body)
                    pending.append(body)
            return found

        body = None
        if root.IsA(UsdPhysics.Joint) or root.HasAPI(UsdPhysics.RigidBodyAPI):
            body = _resolve_articulation_root_body(stage, str(root.GetPath()), asset_path)
            if body not in body_paths:
                raise RuntimeError("the articulation root has no unambiguous rigid-body endpoint")

        foreign_bodies = set()
        if body is not None or root.HasAPI(UsdPhysics.ArticulationRootAPI):
            for prim in prims:
                if prim == root or not prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                    continue
                if root.GetPath().HasPrefix(prim.GetPath()):
                    continue  # An ancestor container is the same selected root.
                if not prim.IsA(UsdPhysics.Joint) and not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    # Container ownership is undirected; carrier attachment's
                    # directed root-body inference is not membership evidence.
                    bounded = {
                        path for path in body_paths if stage.GetPrimAtPath(path).GetPath().HasPrefix(prim.GetPath())
                    }
                    for seed in bounded:
                        component = connected(seed)
                        if not component.issubset(bounded):
                            raise RuntimeError("foreign articulation component crosses its declared container")
                        foreign_bodies.update(component)
                else:
                    foreign_seed = _resolve_articulation_root_body(stage, str(prim.GetPath()), asset_path)
                    if foreign_seed not in body_paths:
                        raise RuntimeError("foreign articulation root has no unambiguous rigid-body endpoint")
                    foreign_bodies.update(connected(foreign_seed))
        if body is None:
            eligible = {
                path
                for path in body_paths
                if stage.GetPrimAtPath(path).GetPath().HasPrefix(root.GetPath()) and path not in foreign_bodies
            }
            native_seeds = {
                endpoint
                for path, endpoints in endpoints_by_joint.items()
                if any(
                    native_joint_name(name) in (path, stage.GetPrimAtPath(path).GetName()) for name in robot.dof_names
                )
                and not UsdPhysics.Joint(stage.GetPrimAtPath(path)).GetExcludeFromArticulationAttr().Get()
                for endpoint in endpoints & eligible
            }
            seeds = native_seeds or eligible
            components = {frozenset(connected(seed)) for seed in seeds}
            if len(components) != 1:
                raise RuntimeError("native identities do not select one connected articulation")
            bodies = set(next(iter(components)))
        else:
            bodies = connected(body)
        if bodies & foreign_bodies:
            raise RuntimeError("selected body graph overlaps another declared articulation")

        # Implicit body/joint roots enumerate sibling joints inside the verified
        # asset. Explicit scopes always remain an intersection with that graph.
        analysis_path = str(explicit_root or asset_path)
        analysis = stage.GetPrimAtPath(analysis_path)
        selected = set()
        for path, endpoints in endpoints_by_joint.items():
            if (
                endpoints
                and endpoints.issubset(bodies)
                and stage.GetPrimAtPath(path).GetPath().HasPrefix(analysis.GetPath())
            ):
                selected.add(path)
    except RuntimeError as error:
        raise JointIdentityError(
            f"Selected joint mapping/setup limitation: discovery cannot resolve its selected articulation: {error}"
        ) from error
    return analysis_path, frozenset(selected)


def _qualified_setup_world_pin(stage, robot, bodies):
    """Requalify the exact setup pin; arbitrary stage pins are not root evidence."""
    from pxr import Sdf, UsdPhysics
    from simready.foundation.tier_newton.runtime_tests._assessment import (
        _has_complete_prim_ancestry,
        _has_complete_relationship_sources,
    )

    receipt = getattr(robot, "_setup_world_pin", None)
    if receipt is None:
        return None
    if not isinstance(receipt, tuple) or len(receipt) != 2 or not all(isinstance(value, str) for value in receipt):
        raise JointIdentityError("Required child-body mapping has malformed setup pin provenance")
    pin_path, body_path = receipt
    for path in receipt:
        if not Sdf.Path(path).IsAbsolutePath() or not Sdf.Path(path).IsPrimPath():
            raise JointIdentityError("Required child-body mapping has invalid setup pin paths")
    pin = stage.GetPrimAtPath(pin_path)
    body = stage.GetPrimAtPath(body_path)
    if (
        body_path not in bodies
        or not pin
        or not pin.IsA(UsdPhysics.FixedJoint)
        or not _has_complete_prim_ancestry(stage, pin)
        or not _has_complete_prim_ancestry(stage, body)
        or not body.GetPath().HasPrefix(robot.asset_prim.GetPath())
        or not body.HasAPI(UsdPhysics.RigidBodyAPI)
    ):
        raise JointIdentityError("Required child-body mapping has unavailable or foreign setup pin ownership")
    joint = UsdPhysics.FixedJoint(pin)
    body_enabled = UsdPhysics.RigidBodyAPI(body).GetRigidBodyEnabledAttr()
    enabled, excluded = joint.GetJointEnabledAttr(), joint.GetExcludeFromArticulationAttr()
    if (
        any(attr.GetNumTimeSamples() for attr in (body_enabled, enabled, excluded))
        or body_enabled.Get() is not True
        or enabled.Get() is not True
        or excluded.Get() is not False
    ):
        raise JointIdentityError("Required child-body mapping has unqualified setup pin eligibility")
    # Only the canonical effectively-unbreakable export values qualify.
    if any(
        attr.GetNumTimeSamples() or attr.Get() not in _UNBREAKABLE_STRENGTHS
        for attr in (joint.GetBreakForceAttr(), joint.GetBreakTorqueAttr())
    ):
        raise JointIdentityError("Required child-body mapping has breakable or unavailable setup pin strength")
    relationships = (joint.GetBody0Rel(), joint.GetBody1Rel())
    if not all(_has_complete_relationship_sources(stage, rel) for rel in relationships):
        raise JointIdentityError("Required child-body mapping has incomplete setup pin endpoint sources")
    empty_sides = sum(not rel.GetTargets() and not rel.GetForwardedTargets() for rel in relationships)
    ends = _joint_body_paths(stage, pin)
    if empty_sides != 1 or ends.count(body_path) != 1 or ends.count(None) != 1:
        raise JointIdentityError("Required child-body mapping has rebound or non-world setup pin endpoints")
    return body_path


def selected_downstream_body(stage, robot, dof_index, physics_view):
    """Resolve the selected enabled native joint and its rooted downstream body.

    Called once at probe setup. Cooked membership is corroboration; neither USD
    endpoint order nor the first native link establishes parenthood.
    """
    from numbers import Integral

    from pxr import UsdPhysics

    if stage is None or physics_view is None:
        raise JointIdentityError("Required child-body mapping has no live articulation view")
    names = robot.dof_names
    if not 0 <= dof_index < len(names):
        raise JointIdentityError("Required child-body mapping has an invalid native index")
    rows = getattr(physics_view, "link_paths", None)
    if not isinstance(rows, (list, tuple)) or len(rows) != 1 or not isinstance(rows[0], (list, tuple)):
        raise JointIdentityError("Required child-body mapping needs one authoritative cooked link-path row")
    paths = [str(path) for path in rows[0]]
    if not paths or len(set(paths)) != len(paths):
        raise JointIdentityError("Required child-body mapping has ambiguous cooked links")
    joints = [
        prim
        for prim in selected_joint_prims(stage, robot.prim_path, names, robot.asset_prim)
        if not UsdPhysics.Joint(prim).GetExcludeFromArticulationAttr().Get()
    ]
    native_paths = getattr(physics_view, "dof_paths", None)
    identity = names[dof_index]
    if native_paths is not None:
        if (
            not isinstance(native_paths, (list, tuple))
            or len(native_paths) != 1
            or not isinstance(native_paths[0], (list, tuple))
            or len(native_paths[0]) != len(names)
        ):
            raise JointIdentityError("Required child-body mapping has invalid cooked DOF paths")
        identity = native_paths[0][dof_index]
        if not str(identity).startswith("/"):
            raise JointIdentityError("Required child-body mapping needs exact cooked DOF paths")
    selected = joint_for_native_name(joints, identity)
    if selected is None:
        raise JointIdentityError(f"Required child-body mapping has no unique selected enabled joint for {identity!r}")
    named = joint_for_native_name(joints, names[dof_index])
    if named is not None and named != selected:
        raise JointIdentityError("Required child-body mapping has conflicting native path and name")
    endpoints = {str(prim.GetPath()): _joint_body_paths(stage, prim) for prim in joints}
    selected_path = str(selected.GetPath())
    pair = endpoints[selected_path]
    if None in pair or pair[0] == pair[1] or any(body not in paths for body in pair):
        raise JointIdentityError("Required child-body mapping has unresolved or foreign joint endpoints")
    bodies = {body for ends in endpoints.values() for body in ends if body}
    if not set(paths).issubset(bodies):
        raise JointIdentityError("Required child-body mapping has foreign or rebound cooked links")
    root_body = _resolve_articulation_root_body(stage, robot.prim_path, str(robot.asset_prim.GetPath()))
    setup_root = _qualified_setup_world_pin(stage, robot, bodies)
    if setup_root is not None:
        getter = getattr(physics_view, "get_metatype", None)
        meta = getter(0) if callable(getter) else None
        if hasattr(meta, "fixed_base") and meta.fixed_base is not True:
            raise JointIdentityError(
                "Required child-body mapping setup pin is not corroborated by native fixed-base state"
            )
        pins = {next(body for body in ends if body) for ends in endpoints.values() if ends.count(None) == 1}
        if root_body not in (None, setup_root) or pins - {setup_root}:
            raise JointIdentityError("Required child-body mapping has conflicting setup and authored roots")
        root_body = setup_root
    if root_body is None:
        pins = {next(body for body in ends if body) for ends in endpoints.values() if ends.count(None) == 1}
        if len(pins) == 1:
            root_body = next(iter(pins))
        elif pins:
            raise JointIdentityError("Required child-body mapping has ambiguous world roots")
    if root_body is None:
        # SDK metadata is optional, and usable only as a complete qualified tree.
        getter = getattr(physics_view, "get_metatype", None)
        meta = getter(0) if callable(getter) else None
        names = getattr(meta, "link_names", None)
        parent_indices = getattr(meta, "link_parent_indices", None)
        indices = getattr(meta, "link_indices", None)
        if (
            not isinstance(names, (list, tuple))
            or len(names) != len(paths)
            or len(set(names)) != len(names)
            or not isinstance(parent_indices, dict)
            or set(parent_indices) != set(names)
            or not isinstance(indices, dict)
            or any(indices.get(name) != index for index, name in enumerate(names))
        ):
            raise JointIdentityError("Required child-body mapping has no qualified articulation root")
        parents = [parent_indices[name] for name in names]
        if any(
            isinstance(value, bool) or not isinstance(value, Integral) or value < -1 or value >= len(paths)
            for value in parents
        ):
            raise JointIdentityError("Required child-body mapping has invalid cooked parent indices")
        roots = [index for index, parent in enumerate(parents) if parent == -1]
        if len(roots) != 1:
            raise JointIdentityError("Required child-body mapping has ambiguous cooked roots")
        edges = {frozenset(ends) for ends in endpoints.values() if None not in ends}
        for index, parent in enumerate(parents):
            seen = set()
            current = index
            while current != -1:
                if current in seen:
                    raise JointIdentityError("Required child-body mapping has cyclic cooked parents")
                seen.add(current)
                current = parents[current]
            if parent != -1 and frozenset((paths[index], paths[parent])) not in edges:
                raise JointIdentityError("Required child-body mapping has foreign cooked parent topology")
        root_body = paths[roots[0]]
    if root_body not in paths:
        raise JointIdentityError("Required child-body mapping root is absent from the cooked articulation")
    adjacency = {body: set() for body in bodies}
    for path, ends in endpoints.items():
        if path != selected_path and None not in ends:
            adjacency[ends[0]].add(ends[1])
            adjacency[ends[1]].add(ends[0])
    reached, pending = {root_body}, [root_body]
    while pending:
        for body in adjacency[pending.pop()] - reached:
            reached.add(body)
            pending.append(body)
    children = [body for body in pair if body not in reached]
    if len(children) != 1:
        raise JointIdentityError("Required child-body mapping cannot establish unique downstream topology")
    return children[0]

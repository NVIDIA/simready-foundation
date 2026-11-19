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
"""Shared traversal helpers for the Assembly capability (`MC.*`, `CN.*`)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

MATE_NS = "simready:mate:"

DOMAIN_ATTR = "simready:mate:domain"
ROLE_ATTR = "simready:mate:role"
INTERFACE_ATTR = "simready:mate:mechanical:interface"
MAX_PAYLOAD_ATTR = "simready:mate:mechanical:maxPayload"
KIND_ATTR = "simready:mate:mechanical:kind"

REALIZATION_ATTR = "simready:mate:realization"
ASSEMBLY_TYPE_ATTR = "simready:mate:assemblyType"

SOCKET_REL = "simready:mate:socket"
PLUG_REL = "simready:mate:plug"
JOINT_REL = "simready:mate:joint"

CONNECTIONS_SCOPE = "Connections"
INSERTION_VECTOR_NAME = "mate_insertion_vector"

MECHANICAL_DOMAIN = "mechanical"
SOCKET_ROLE = "Socket"
PLUG_ROLE = "Plug"

REALIZATION_COMPOUND = "compound"
REALIZATION_JOINTED = "jointed"

# Mate-namespace attributes that describe the assembly or a pairing rather than a
# site, so they must not make their prim a site candidate. The socket, plug, and
# joint rels need no entry here: a site is declared with attributes only.
_NON_SITE_ATTRS = frozenset({REALIZATION_ATTR, ASSEMBLY_TYPE_ATTR})


def applied_api_schemas(prim: Usd.Prim) -> set[str]:
    """Applied API schema names, including ones whose schema is not installed."""
    schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
    op = prim.GetMetadata("apiSchemas")
    if op is None:
        return schemas
    for items in (
        op.explicitItems,
        op.prependedItems,
        op.appendedItems,
        op.addedItems,
        op.orderedItems,
    ):
        schemas.update(str(schema) for schema in items)
    return schemas


def authored_token(prim: Usd.Prim, name: str) -> str | None:
    """Composed value of a token attribute, or None when it is not authored."""
    attr = prim.GetAttribute(name)
    if not attr or not attr.HasAuthoredValue():
        return None
    value = attr.Get()
    return None if value is None else str(value)


def is_rigid_body_enabled(prim: Usd.Prim) -> bool:
    """True when the prim is a rigid body whose `physics:rigidBodyEnabled` resolves true."""
    if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        return False
    enabled = UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Get()
    return True if enabled is None else bool(enabled)


def resolve_mate_body(site: Usd.Prim) -> Usd.Prim | None:
    """`MC.003`: nearest ancestor-or-self with an enabled `PhysicsRigidBodyAPI`.

    A rigid body with `physics:rigidBodyEnabled = false` is transparent to the
    walk, which is what lets a demoted compound part resolve to the compound
    body above it.
    """
    prim = site
    while prim and not prim.IsPseudoRoot():
        if is_rigid_body_enabled(prim):
            return prim
        prim = prim.GetParent()
    return None


def common_ancestor(a: Usd.Prim, b: Usd.Prim) -> Usd.Prim | None:
    path = a.GetPath().GetCommonPrefix(b.GetPath())
    if path.isEmpty or path == Sdf.Path.absoluteRootPath:
        return None
    prim = a.GetStage().GetPrimAtPath(path)
    return prim if prim and prim.IsValid() else None


def authored_mass(prim: Usd.Prim) -> float | None:
    """Positive authored `physics:mass`, or None.

    `UsdPhysics` treats an unauthored or zero mass as "derive it", so neither
    counts as the prim stating a mass.
    """
    attr = prim.GetAttribute(UsdPhysics.Tokens.physicsMass)
    if not attr or not attr.HasAuthoredValue():
        return None
    value = attr.Get()
    if value is None or float(value) <= 0.0:
        return None
    return float(value)


def subtree_mass(root: Usd.Prim, include_root: bool = True) -> float:
    """Sum `physics:mass` over a subtree, pruning at the first mass on each branch.

    Pruning is what keeps a compound aggregate from being added to the part
    masses beneath it (`CN.005`, `CN.011`).
    """
    total = 0.0
    stack = [root] if include_root else list(root.GetChildren())
    while stack:
        prim = stack.pop()
        mass = authored_mass(prim)
        if mass is not None:
            total += mass
            continue
        stack.extend(prim.GetChildren())
    return total


def massless_bodies(root: Usd.Prim, include_root: bool = True) -> list[Usd.Prim]:
    """Topmost rigid bodies in a subtree with no authored mass at or below them.

    Each one is a branch that contributes nothing to `subtree_mass`, which makes
    the sum incomplete.
    """
    found: list[Usd.Prim] = []
    stack = [root] if include_root else list(root.GetChildren())
    while stack:
        prim = stack.pop()
        if authored_mass(prim) is not None:
            continue
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and subtree_mass(prim) == 0.0:
            found.append(prim)
            continue
        stack.extend(prim.GetChildren())
    return found


def unresolvable_mass(root: Usd.Prim, include_root: bool = True) -> list[Usd.Prim]:
    """Prims authoring `physics:mass` that no runtime can attribute to a body.

    `UsdPhysics` resolves a body's mass from the body itself and from the
    colliders beneath it. Mass on a prim that is neither is inert: the runtime
    derives that part's contribution from collider volume and density instead of
    reading the authored value.
    """
    found: list[Usd.Prim] = []
    stack = [root] if include_root else list(root.GetChildren())
    while stack:
        prim = stack.pop()
        if authored_mass(prim) is not None and not (
            prim.HasAPI(UsdPhysics.CollisionAPI) or is_rigid_body_enabled(prim)
        ):
            found.append(prim)
        stack.extend(prim.GetChildren())
    return found


def is_in_articulation(prim: Usd.Prim) -> bool:
    """True when the prim belongs to a `UsdPhysics` articulation.

    `PhysicsArticulationRootAPI` is applied either to a prim that encloses the
    articulation, or — the common robot pattern — to the fixed root joint inside
    it. In the joint case the articulation scope is the prim holding that joint,
    so an ancestor walk has to look for both placements.
    """
    current = prim
    while current and not current.IsPseudoRoot():
        if current.HasAPI(UsdPhysics.ArticulationRootAPI):
            return True
        for child in current.GetChildren():
            if child.IsA(UsdPhysics.Joint) and child.HasAPI(UsdPhysics.ArticulationRootAPI):
                return True
        current = current.GetParent()
    return False


def relative_transform(prim: Usd.Prim, ancestor: Usd.Prim) -> Gf.Matrix4d:
    """Transform of `prim` expressed in the frame of `ancestor`."""
    time = Usd.TimeCode.Default()
    prim_xf = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(time)
    ancestor_xf = UsdGeom.Xformable(ancestor).ComputeLocalToWorldTransform(time)
    return prim_xf * ancestor_xf.GetInverse()


@dataclass
class MateSite:
    """A prim that declares itself a mate site by authoring the mate namespace."""

    prim: Usd.Prim
    domain: str | None
    role: str | None

    @property
    def path(self) -> str:
        return str(self.prim.GetPath())

    @property
    def is_mechanical(self) -> bool:
        return self.domain == MECHANICAL_DOMAIN

    @property
    def is_well_formed(self) -> bool:
        """`MC.001`: an `Xform` authoring both discovery tokens."""
        return bool(self.prim.IsA(UsdGeom.Xform) and self.domain and self.role)


def read_mate_site(prim: Usd.Prim) -> MateSite | None:
    """Read a prim as a mate site, or None when it does not declare itself one.

    A prim declares itself a site by authoring any `simready:mate:` attribute
    other than the assembly-level ones. `MC.001` then decides whether that
    declaration is well formed; a prim that authors nothing in the namespace is
    simply not a site and is not a failure.
    """
    declared = any(
        attr.GetName().startswith(MATE_NS) and attr.GetName() not in _NON_SITE_ATTRS
        for attr in prim.GetAuthoredAttributes()
    )
    if not declared:
        return None
    return MateSite(
        prim=prim,
        domain=authored_token(prim, DOMAIN_ATTR),
        role=authored_token(prim, ROLE_ATTR),
    )


def iter_mate_sites(root: Usd.Prim):
    """Every prim under `root` that declares itself a mate site."""
    for prim in Usd.PrimRange(root):
        site = read_mate_site(prim)
        if site is not None:
            yield site


@dataclass
class Connection:
    """A connection prim under `<defaultPrim>/Connections`."""

    prim: Usd.Prim
    realization: str | None
    socket_targets: list = field(default_factory=list)
    plug_targets: list = field(default_factory=list)
    has_socket_rel: bool = False
    has_plug_rel: bool = False
    has_joint_rel: bool = False
    joint_targets: list = field(default_factory=list)

    @property
    def path(self) -> str:
        return str(self.prim.GetPath())

    @property
    def is_jointed(self) -> bool:
        return self.realization == REALIZATION_JOINTED

    @property
    def is_compound(self) -> bool:
        return self.realization == REALIZATION_COMPOUND

    def _single(self, targets: list) -> Usd.Prim | None:
        if len(targets) != 1:
            return None
        return self.prim.GetStage().GetPrimAtPath(targets[0]) or None

    @property
    def socket_prim(self) -> Usd.Prim | None:
        prim = self._single(self.socket_targets)
        return prim if prim and prim.IsValid() else None

    @property
    def plug_prim(self) -> Usd.Prim | None:
        prim = self._single(self.plug_targets)
        return prim if prim and prim.IsValid() else None

    @property
    def joint_prim(self) -> Usd.Prim | None:
        prim = self._single(self.joint_targets)
        return prim if prim and prim.IsValid() else None


def get_connections_scope(stage: Usd.Stage) -> Usd.Prim | None:
    """The stage's own `Connections` scope, directly under the default prim."""
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return None
    scope = default_prim.GetChild(CONNECTIONS_SCOPE)
    return scope if scope and scope.IsValid() else None


def iter_nested_assembly_roots(stage: Usd.Stage):
    """Prims below the default prim that carry their own `Connections` scope.

    Each is the root of a composed-in assembly. Discovery reads the scope, not
    the model kind, so attachment semantics do not depend on kind.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return
    for prim in Usd.PrimRange(default_prim):
        if prim == default_prim:
            continue
        scope = prim.GetChild(CONNECTIONS_SCOPE)
        if scope and scope.IsValid():
            yield prim


def read_connection(prim: Usd.Prim) -> Connection | None:
    """Read a prim as a connection, or None when it declares nothing of a pairing.

    A connection prim is one authoring `simready:mate:realization` and/or the
    socket and plug relationships (`CN.001`). The joint prim that sits beside it
    under the same Scope authors none of these and is correctly excluded.
    """
    realization = authored_token(prim, REALIZATION_ATTR)
    socket_rel = prim.GetRelationship(SOCKET_REL)
    plug_rel = prim.GetRelationship(PLUG_REL)
    joint_rel = prim.GetRelationship(JOINT_REL)

    has_socket = bool(socket_rel and socket_rel.IsAuthored())
    has_plug = bool(plug_rel and plug_rel.IsAuthored())
    has_joint = bool(joint_rel and joint_rel.IsAuthored())

    if realization is None and not has_socket and not has_plug:
        return None

    return Connection(
        prim=prim,
        realization=realization,
        socket_targets=socket_rel.GetTargets() if has_socket else [],
        plug_targets=plug_rel.GetTargets() if has_plug else [],
        has_socket_rel=has_socket,
        has_plug_rel=has_plug,
        has_joint_rel=has_joint,
        joint_targets=joint_rel.GetTargets() if has_joint else [],
    )


def _iter_scope_connections(scope: Usd.Prim):
    for prim in Usd.PrimRange(scope):
        connection = read_connection(prim)
        if connection is not None:
            yield connection


def iter_connections(stage: Usd.Stage):
    """Every connection prim under `<defaultPrim>/Connections`: the stage's own pairings."""
    scope = get_connections_scope(stage)
    if scope is None:
        return
    yield from _iter_scope_connections(scope)


def iter_nested_connections(stage: Usd.Stage):
    """Every connection a composed-in assembly declares, at any depth.

    These pairings are validated on the nested assembly's own stage. The outer
    stage reads them only to know which sites they occupy (`CN.007`).
    """
    for root in iter_nested_assembly_roots(stage):
        yield from _iter_scope_connections(root.GetChild(CONNECTIONS_SCOPE))

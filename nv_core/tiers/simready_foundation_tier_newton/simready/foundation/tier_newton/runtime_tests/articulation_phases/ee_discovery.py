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
"""End-effector discovery.

An explicit endpoint inside the loaded asset wins. Otherwise the composed
enabled articulation tree must identify a unique deepest non-finger chain.
Explicitly excluded constraints retain validated endpoints without forming
tree edges. Root anchoring handles either body0/body1 orientation.
Invalid or ambiguous graphs never fall back to stale link inventory order.
When no enabled graph exists, robotLinks and articulation body order remain
legacy hints. A unique fixed tool-frame child can refine the endpoint; the
heuristic does not establish a universally correct TCP or native qualification.
"""

# Names that identify a fixed "tool flange / TCP" frame parented to the last
# kinematic link. When the chain tip has one of these as a direct Xform child,
# that child is the actual end-effector output face (e.g. UR ``wrist_3_link``
# carries a ``flange`` child at a fixed offset/orientation).
_FIXED_EE_CHILD_NAMES = frozenset(
    {
        "flange",
        "tool0",
        "tcp",
        "ee_link",
        "tool",
        "end_effector",
        "coupling",
    }
)

# Articulation bodies that are NOT part of the main (base -> wrist) chain and
# must not be mistaken for the arm tip.
_NON_CHAIN_BODY_TOKENS = (
    "finger",
    "jaw",
    "knuckle",
    "gripper",
    "pad",
    "inner",
    "outer",
)


def discover_end_effector_link(stage, robot, robot_root_path, explicit_path=None):
    # type: (Any, Any, str) -> Optional[str]
    """Return the USD path of the robot's end-effector link, or ``None``.

    A valid explicit endpoint wins. Otherwise prefer the unique deepest main
    chain of a bounded, connected, acyclic enabled joint graph. Link collections
    and body order are fallbacks only without a graph; ambiguity returns None.
    """
    root_prim = stage.GetPrimAtPath(robot_root_path)
    if not root_prim or not root_prim.IsValid():
        return None

    if explicit_path is not None:
        from pxr import Sdf

        path = Sdf.Path(str(explicit_path))
        prim = stage.GetPrimAtPath(path) if path.IsAbsolutePath() and path.IsPrimPath() else None
        if prim and prim.IsValid() and path.HasPrefix(root_prim.GetPath()):
            return str(path)
        return None  # Invalid explicit identity must not silently select another endpoint.

    from pxr import Usd, UsdPhysics

    enabled_joints = [
        prim
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.IsA(UsdPhysics.Joint) and prim.GetAttribute("physics:jointEnabled").Get() is not False
    ]
    if enabled_joints:
        # Unordered link collections cannot override a present composed graph.
        return _find_ee_from_joint_graph(stage, root_prim)

    # Legacy fallback without an enabled graph: Isaac robot-link inventory.
    ee_path = _find_ee_from_robot_links(stage, root_prim)
    if ee_path:
        return ee_path

    # Legacy fallback: kinematic-chain tip from the articulation body order.
    ee_path = _find_ee_from_kinematic_chain(stage, root_prim, robot)
    if ee_path:
        return ee_path

    return None


def _find_fixed_ee_child(prim):
    # type: (Any) -> Optional[str]
    """Return the path of a direct Xform child of *prim* that is a fixed tool
    frame (``flange``, ``tool0``, ``tcp``, ``ee_link``, ...), or ``None``.

    The true end-effector output face is often a fixed (no-joint) frame one
    level beyond the last articulated link, carrying the tool's orientation.
    """
    from pxr import Usd, UsdGeom, UsdPhysics

    candidates = []
    for child in prim.GetChildren():
        if child.GetName().lower() in _FIXED_EE_CHILD_NAMES and child.IsA(UsdGeom.Xform):
            if UsdGeom.Xformable(child).GetResetXformStack() and not child.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            if child.HasAPI(UsdPhysics.RigidBodyAPI):
                stage = prim.GetStage()
                boundary = stage.GetPseudoRoot()
                parent_body = _joint_body_path(stage, boundary, prim.GetPath())
                connected = []
                unresolved = False
                # An external constraint may influence this loaded body; an
                # external marker cannot enter the candidate inventory.
                for joint in Usd.PrimRange(boundary, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
                    if not joint.IsA(UsdPhysics.Joint) or joint.GetAttribute("physics:jointEnabled").Get() is False:
                        continue
                    try:
                        endpoints = _joint_body_endpoints(stage, boundary, joint)
                    except ValueError:
                        unresolved = True
                        break
                    if str(child.GetPath()) in endpoints:
                        connected.append((joint, endpoints))
                if unresolved or any(not joint.IsA(UsdPhysics.FixedJoint) for joint, _ in connected):
                    continue
                if not parent_body or not any(parent_body in endpoints for _, endpoints in connected):
                    continue
            # A non-body child frame remains fixed to its parent even when
            # joint relationships use it as the parent body's joint frame.
            candidates.append(str(child.GetPath()))
    if len(candidates) > 1:
        return False  # Distinguish ambiguous marker identity from no marker.
    return candidates[0] if candidates else None


def _joint_body_path(stage, root_prim, path):
    """Resolve a bounded Xformable frame to its closest rigid-body owner.

    A frame with no body represents world/static. Invalid frames or ownership
    outside the loaded asset cannot be converted to world or a basename hint.
    """
    from pxr import Sdf, UsdGeom, UsdPhysics

    path = Sdf.Path(str(path))
    if not path.IsAbsolutePath() or not path.IsPrimPath() or not path.HasPrefix(root_prim.GetPath()):
        raise ValueError("Joint body frame is outside the loaded asset")
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid() or not UsdGeom.Xformable(prim):
        raise ValueError("Joint body frame is not a valid Xformable")
    while prim and prim.IsValid() and not prim.IsPseudoRoot():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            if not prim.GetPath().HasPrefix(root_prim.GetPath()):
                raise ValueError("Joint body owner is outside the loaded asset")
            if prim.GetAttribute("physics:rigidBodyEnabled").Get() is False:
                return None
            return str(prim.GetPath())
        prim = prim.GetParent()
    return None


def _joint_body_endpoints(stage, root_prim, joint):
    """Keep world absence distinct from malformed/missing forwarded targets."""
    from pxr import Tf

    endpoints = []
    try:
        for side in ("body0", "body1"):
            relationship = joint.GetRelationship("physics:" + side)
            targets = relationship.GetForwardedTargets()
            if len(targets) > 1 or (relationship.GetTargets() and not targets):
                raise ValueError("Joint body relationship has no unique forwarded target")
            endpoints.append(_joint_body_path(stage, root_prim, targets[0]) if targets else None)
    except Tf.ErrorException as exc:
        raise ValueError("Joint body relationship cannot be resolved") from exc
    return endpoints


def _finger_branch_name(path):
    """Match complete finger words rather than generic arm-name substrings."""
    import re

    name = path.rsplit("/", 1)[-1]
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    tokens = set(re.findall(r"[a-z]+", name.lower()))
    if tokens & {"finger", "fingertip", "jaw", "knuckle", "pad"}:
        return True
    lower = name.lower()
    if any(
        lower.endswith(suffix) or f"{suffix}_" in lower
        for suffix in ("leftfinger", "rightfinger", "fingertip")
    ):
        return True
    if tokens >= {"tip", "left"} or tokens >= {"tip", "right"}:
        return True
    return False


def _robot_links_targets(stage, root_prim):
    # type: (Any, Any) -> Optional[list[Any]]
    """Find ``isaac:physics:robotLinks`` targets.

    The relationship lives on the prim carrying ``IsaacRobotAPI`` (typically the
    default / robot prim), which may be an ancestor of the articulation root.
    Searches root_prim, its ancestors, and the stage default prim.
    """
    from pxr import Sdf

    candidates = []  # type: list[Any]
    prim = root_prim
    while prim and prim.IsValid() and prim.GetPath() != Sdf.Path("/"):
        candidates.append(prim)
        prim = prim.GetParent()
    try:
        default_prim = stage.GetDefaultPrim()
        if default_prim and default_prim.IsValid():
            candidates.append(default_prim)
    except Exception:
        pass

    for prim in candidates:
        try:
            rel = prim.GetRelationship("isaac:physics:robotLinks")
            if rel and rel.IsValid():
                targets = rel.GetForwardedTargets()
                if targets:
                    return list(targets)
        except Exception:
            continue
    return None


def _find_ee_from_robot_links(stage, root_prim):
    # type: (Any, Any) -> Optional[str]
    """Resolve the EE from ``isaac:physics:robotLinks`` (last entry = tip).

    Prefers a fixed tool-frame child of the tip link when present.
    """
    from pxr import Usd

    targets = _robot_links_targets(stage, root_prim)
    if not targets:
        return None

    last_link_path = str(targets[-1])

    from pxr import Sdf

    target_path = Sdf.Path(last_link_path)
    if target_path.IsAbsolutePath() and (
        not target_path.IsPrimPath() or not target_path.HasPrefix(root_prim.GetPath())
    ):
        return None

    # Resolve the tip link prim: absolute path first, then by basename under
    # the search root (handles assets that author relative-looking targets).
    tip_prim = stage.GetPrimAtPath(last_link_path)
    if target_path.IsAbsolutePath() and not (tip_prim and tip_prim.IsValid()):
        return None
    if tip_prim and tip_prim.IsValid() and not tip_prim.GetPath().HasPrefix(root_prim.GetPath()):
        return None
    if not (tip_prim and tip_prim.IsValid()):
        link_name = last_link_path.strip("<>").rstrip("/").split("/")[-1]
        tip_prim = None
        matches = [
            prim
            for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
            if prim.GetName() == link_name
        ]
        tip_prim = matches[0] if len(matches) == 1 else None
    if tip_prim is None or not tip_prim.IsValid():
        return None

    fixed_child = _find_fixed_ee_child(tip_prim)
    if fixed_child is False:
        return None
    if fixed_child:
        return fixed_child
    return str(tip_prim.GetPath())


def _find_ee_from_joint_graph(stage, root_prim):
    # type: (Any, Any) -> Optional[str]
    """Return the EE from the USD joint graph topology (no articulation needed).

    All enabled endpoints must be bounded. Nonexcluded edges form one acyclic
    tree with a unique base. Explicit maximal-coordinate closures remain
    validated constraints, not articulation-tree edges, and must connect bodies
    already in that tree. Rank non-finger endpoints by movable-joint depth;
    unexcluded cycles, disconnected components and ties return None.
    """
    from pxr import Usd, UsdPhysics

    adjacency = {}
    body0s, body1s = set(), set()
    pins, edges = [], set()
    excluded_constraints = []
    for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        if not prim.IsA(UsdPhysics.Joint) or prim.GetAttribute("physics:jointEnabled").Get() is False:
            continue
        try:
            endpoints = _joint_body_endpoints(stage, root_prim, prim)
        except ValueError:
            return None
        b0, b1 = endpoints
        if b0 is None and b1 is None:
            return None
        if b0 is None or b1 is None:
            anchor = b0 or b1
            pins.append(anchor)
            adjacency.setdefault(anchor, [])
            continue
        edge = frozenset((b0, b1))
        if b0 == b1:
            return None
        if prim.GetAttribute("physics:excludeFromArticulation").Get() is True:
            excluded_constraints.append((b0, b1))
            continue
        if edge in edges:
            return None
        edges.add(edge)
        movable = not prim.IsA(UsdPhysics.FixedJoint)
        adjacency.setdefault(b0, []).append((b1, movable))
        adjacency.setdefault(b1, []).append((b0, movable))
        body0s.add(b0)
        body1s.add(b1)
    if any(b0 not in adjacency or b1 not in adjacency for b0, b1 in excluded_constraints):
        return None
    roots = pins if pins else list(body0s - body1s)
    if len(roots) != 1:
        return None
    visited, candidates, traversal = set(), [], []
    pending = [(roots[0], None, 0)]
    while pending:
        path, parent, depth = pending.pop()
        if path in visited:
            return None  # Cycle, not a kinematic tree.
        visited.add(path)
        children = [(other, movable) for other, movable in adjacency[path] if other != parent]
        traversal.append((path, depth, children))
        for other, movable in children:
            pending.append((other, path, depth + int(movable)))
    if visited != set(adjacency):
        return None  # Disconnected, not one complete articulation tree.
    finger_subtrees = {}
    for path, depth, children in reversed(traversal):
        # Preserve serial continuations through finger-like intermediate names;
        # only wholly finger-like terminal subtrees are peripheral branches.
        finger_subtrees[path] = _finger_branch_name(path) and all(finger_subtrees[child] for child, _ in children)
        if not finger_subtrees[path] and not any(not finger_subtrees[child] for child, _ in children) and depth > 0:
            candidates.append((depth, path))
    if not candidates:
        return None
    deepest = max(depth for depth, _ in candidates)
    tips = [path for depth, path in candidates if depth == deepest]
    if len(tips) != 1:
        return None
    tip_path = tips[0]
    tip_prim = stage.GetPrimAtPath(tip_path)
    fixed_child = _find_fixed_ee_child(tip_prim)
    if fixed_child is False:
        return None
    return fixed_child or str(tip_prim.GetPath())


def _resolve_articulation(robot):
    # type: (Any) -> Any
    """Return the underlying SingleArticulation-like object (or None).

    Accepts a ``RobotHandle`` (uses ``robot.articulation``) or a raw object
    exposing ``body_names`` directly.
    """
    if robot is None:
        return None
    art = getattr(robot, "articulation", None)
    if art is not None:
        return art
    return robot


def _find_ee_from_kinematic_chain(stage, root_prim, robot):
    # type: (Any, Any, Any) -> Optional[str]
    """Use the last non-finger body as a legacy endpoint hint without a graph.

    Body order does not establish kinematic topology or a universally correct
    TCP. Require a unique bounded name match and prefer a fixed tool-frame child.
    """
    from pxr import Usd

    art = _resolve_articulation(robot)
    if art is None:
        return None
    body_names = list(getattr(art, "body_names", None) or [])
    if not body_names:
        return None

    main_chain = [name for name in body_names if not any(tok in name.lower() for tok in _NON_CHAIN_BODY_TOKENS)]
    if not main_chain:
        main_chain = body_names
    tip_name = main_chain[-1]

    tip_prim = None  # type: Optional[Any]
    matches = [
        prim
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.GetName().lower() == tip_name.lower()
    ]
    tip_prim = matches[0] if len(matches) == 1 else None
    if tip_prim is None:
        return None

    fixed_child = _find_fixed_ee_child(tip_prim)
    if fixed_child is False:
        return None
    if fixed_child:
        return fixed_child
    return str(tip_prim.GetPath())

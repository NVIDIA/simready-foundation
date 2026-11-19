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

An explicit endpoint inside the loaded asset wins. Otherwise the enabled
composed articulation tree must have a unique base and deepest non-finger
endpoint. Explicit maximal-coordinate closures keep validated endpoints but
are not tree edges. World anchoring handles either body0/body1
orientation. Invalid or ambiguous graphs never fall back to stale link order.
When no enabled graph exists, robotLinks inventory order and articulation body
order remain legacy hints. A unique fixed tool-frame child can refine the tip;
arbitrary similarly named prims elsewhere in the asset are never selected.
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
        "link_eef",
        "link_tcp",
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

    Explicit endpoint, then unambiguous composed topology; legacy inventory
    and body-order hints are used only without an enabled joint graph. An
    invalid explicit endpoint or ambiguous graph returns None, not a guess.
    """
    root_prim = stage.GetPrimAtPath(robot_root_path)
    if not root_prim or not root_prim.IsValid():
        return None

    if explicit_path is not None:
        from pxr import Sdf

        path = Sdf.Path(str(explicit_path))
        prim = stage.GetPrimAtPath(path) if path.IsAbsolutePath() and path.IsPrimPath() else None
        return str(path) if prim and prim.IsValid() and path.HasPrefix(root_prim.GetPath()) else None

    # Composed joint topology outranks unordered/stale metadata. An ambiguous
    # enabled graph must not silently fall back to another arbitrary endpoint.
    if _enabled_joints(root_prim):
        return _find_ee_from_joint_graph(stage, root_prim)

    # Without an enabled graph, robotLinks is only a legacy inventory hint.
    ee_path = _find_ee_from_robot_links(stage, root_prim)
    if ee_path:
        return ee_path

    # Articulation body order is another legacy hint, not an explicit TCP.
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
    from pxr import UsdGeom, UsdPhysics

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
                for joint in _enabled_joints(boundary):
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
            # A child frame without its own body follows its parent. A joint
            # targeting that frame constrains the parent body, not the frame.
            candidates.append(str(child.GetPath()))
    if len(candidates) > 1:
        return False  # Distinguish ambiguous TCP identity from no named marker.
    return candidates[0] if candidates else None


def _enabled_joints(root_prim):
    from pxr import Usd, UsdPhysics

    return [
        prim
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.IsA(UsdPhysics.Joint) and prim.GetAttribute("physics:jointEnabled").Get() is not False
    ]


def _joint_body_path(stage, root_prim, path):
    """Resolve a joint's Xformable frame to its nearest bounded rigid body.

    A valid frame without a body is world/static. An invalid frame or a body
    outside the loaded boundary is not a world anchor or a basename hint.
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
    """Normalize single forwarded endpoints; authored unresolved targets fail."""
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
    """Recognize finger words, not arm names containing inner/outer/pad."""
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


def _resolve_bounded_link(stage, root_prim, path):
    from pxr import Sdf, Usd

    usd_path = Sdf.Path(str(path))
    if usd_path.IsAbsolutePath():
        if not usd_path.IsPrimPath() or not usd_path.HasPrefix(root_prim.GetPath()):
            return None
        prim = stage.GetPrimAtPath(usd_path)
        return prim if prim and prim.IsValid() else None
    name = str(path).strip("<>").rstrip("/").split("/")[-1]
    matches = [
        prim
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.GetName() == name
    ]
    return matches[0] if len(matches) == 1 else None


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
    targets = _robot_links_targets(stage, root_prim)
    if not targets:
        return None

    tip_prim = _resolve_bounded_link(stage, root_prim, targets[-1])
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
    """Resolve a unique deepest main-chain endpoint in an anchored USD tree.

    Validate all enabled endpoints before ranking the articulation tree by
    movable-joint depth. Explicitly excluded maximal-coordinate constraints
    can close a physical loop without becoming tree edges; both bodies must
    still resolve inside this tree. Unexcluded cycles remain ambiguous.
    The walk is iterative for long legal chains.
    """
    from pxr import UsdPhysics

    graph = {}
    directed_children = set()
    world_roots = []
    excluded_edges = []
    for joint in _enabled_joints(root_prim):
        try:
            paths = _joint_body_endpoints(stage, root_prim, joint)
        except ValueError:
            return None
        a, b = paths
        if a is None and b is None:
            return None
        if a is None or b is None:
            path = a or b
            world_roots.append(path)
            graph.setdefault(path, {})
            continue
        if a == b:
            return None
        if joint.GetAttribute("physics:excludeFromArticulation").Get() is True:
            excluded_edges.append((a, b))
            continue
        if b in graph.get(a, {}):
            return None
        weight = int(not joint.IsA(UsdPhysics.FixedJoint))
        graph.setdefault(a, {})[b] = weight
        graph.setdefault(b, {})[a] = weight
        directed_children.add(b)
    if any(a not in graph or b not in graph for a, b in excluded_edges):
        return None
    roots = world_roots or [path for path in graph if path not in directed_children]
    if len(roots) != 1:
        return None
    visited = set()
    candidates = []
    traversal = []
    pending = [(roots[0], None, 0)]
    while pending:
        path, parent, depth = pending.pop()
        if path in visited:
            return None
        visited.add(path)
        children = [(child, weight) for child, weight in graph[path].items() if child != parent]
        traversal.append((path, depth, children))
        pending.extend((child, path, depth + weight) for child, weight in children)

    if len(visited) != len(graph):
        return None
    finger_subtrees = {}
    for path, depth, children in reversed(traversal):
        # A finger-like intermediate is still in the arm when its continuation
        # reaches a non-finger wrist. Exclude only complete terminal subtrees.
        finger_subtrees[path] = _finger_branch_name(path) and all(finger_subtrees[child] for child, _ in children)
        if not finger_subtrees[path] and not any(not finger_subtrees[child] for child, _ in children) and depth > 0:
            candidates.append((depth, path))
    if not candidates:
        return None
    max_depth = max(depth for depth, _ in candidates)
    tips = [path for depth, path in candidates if depth == max_depth]
    if len(tips) != 1:
        return None
    tip = stage.GetPrimAtPath(tips[0])
    fixed_child = _find_fixed_ee_child(tip)
    return None if fixed_child is False else fixed_child or str(tip.GetPath())


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
    """Return the EE from the articulation kinematic-chain tip.

    The articulation orders its links base -> tip, so the last body that is not
    part of a gripper/finger sub-chain is the arm tip. A fixed tool-frame child
    of that tip is preferred when present.
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

    matches = [
        prim
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.GetName().lower() == tip_name.lower()
    ]
    if len(matches) != 1:
        return None
    tip_prim = matches[0]

    fixed_child = _find_fixed_ee_child(tip_prim)
    if fixed_child is False:
        return None
    if fixed_child:
        return fixed_child
    return str(tip_prim.GetPath())

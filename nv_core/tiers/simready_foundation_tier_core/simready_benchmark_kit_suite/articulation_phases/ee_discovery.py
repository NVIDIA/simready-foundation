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

Identifies the end-effector (tool) link of a robot from SPEC-DEFINED sources
only. Two sources, in priority order:

  1. The Isaac Robot schema relationship ``isaac:physics:robotLinks`` (refer to
     sr_specs robot-schema.md). It lists the kinematic links ordered base ->
     tip, so the last entry is the end-effector. If that tip link has a fixed
     tool frame as a direct child (``flange``, ``tool0``, ``tcp``, ``ee_link``,
     ...), that child is the true tool output face and is returned instead.
  2. The kinematic-chain tip derived from the articulation's body order. Isaac
     orders the articulation links base -> tip, so the last non-gripper body is
     the tip; again a fixed tool-frame child is preferred when present.
  3. The USD joint-graph tip: the child body (joint ``body1``) that is never a
     parent (``body0``) of another joint. This is a pure-topology fallback for
     when the articulation body order is unavailable (for example
     ``body_names`` is empty); it resolves only an unambiguous single tip.

There is deliberately NO name-based guessing of the end-effector anywhere in
the prim tree. The previous implementation matched a fixed list of common names
(``ee_link``, ``tool0``, ..., ``wrist_3_link``) against every prim in traversal
order, which on a UR-style arm matched the intermediate ``wrist_3_link`` before
the real tool flange and produced a wrong EE frame. When neither spec-defined
source resolves a tip, ``discover_end_effector_link`` returns ``None`` and the
caller reports it for tech-art remediation rather than guessing.
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
    "hand",
    "inner",
    "outer",
    "left",
    "right",
)


def discover_end_effector_link(stage, robot, robot_root_path):
    # type: (Any, Any, str) -> Optional[str]
    """Return the USD path of the robot's end-effector link, or ``None``.

    Resolution uses spec-defined sources only (``isaac:physics:robotLinks``,
    then the articulation kinematic-chain tip), preferring a fixed tool frame
    child at the tip. Returns ``None`` when no spec source resolves a tip; the
    caller is expected to report that for tech-art remediation rather than
    guess a link by name.
    """
    root_prim = stage.GetPrimAtPath(robot_root_path)
    if not root_prim or not root_prim.IsValid():
        return None

    # 1. Authoritative: Isaac Robot schema isaac:physics:robotLinks.
    ee_path = _find_ee_from_robot_links(stage, root_prim)
    if ee_path:
        return ee_path

    # 2. Spec-aligned: kinematic-chain tip from the articulation body order.
    ee_path = _find_ee_from_kinematic_chain(stage, root_prim, robot)
    if ee_path:
        return ee_path

    # 3. Topology fallback: USD joint-graph tip. Works when the articulation
    #    body order is unavailable (for example body_names empty), using only
    #    the authored joint relationships. Resolves only an unambiguous tip.
    ee_path = _find_ee_from_joint_graph(stage, root_prim)
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
    from pxr import UsdGeom

    for child in prim.GetChildren():
        if child.GetName().lower() in _FIXED_EE_CHILD_NAMES and child.IsA(UsdGeom.Xform):
            return str(child.GetPath())
    return None


def _robot_links_targets(stage, root_prim):
    # type: (Any, Any) -> Optional[List[Any]]
    """Find ``isaac:physics:robotLinks`` targets.

    The relationship lives on the prim carrying ``IsaacRobotAPI`` (typically the
    default / robot prim), which may be an ancestor of the articulation root.
    Searches root_prim, its ancestors, and the stage default prim.
    """
    from pxr import Sdf

    candidates = []  # type: List[Any]
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
                targets = rel.GetTargets()
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

    # Resolve the tip link prim: absolute path first, then by basename under
    # the search root (handles assets that author relative-looking targets).
    tip_prim = stage.GetPrimAtPath(last_link_path)
    if not (tip_prim and tip_prim.IsValid()):
        link_name = last_link_path.strip("<>").rstrip("/").split("/")[-1]
        tip_prim = None
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            if prim.GetName() == link_name:
                tip_prim = prim
                break
    if tip_prim is None or not tip_prim.IsValid():
        return None

    fixed_child = _find_fixed_ee_child(tip_prim)
    if fixed_child:
        return fixed_child
    return str(tip_prim.GetPath())


def _find_ee_from_joint_graph(stage, root_prim):
    # type: (Any, Any) -> Optional[str]
    """Return the EE from the USD joint graph topology (no articulation needed).

    The kinematic tip is the child body (a joint ``body1``) that is never a
    parent (``body0``) of another joint. This works when the articulation body
    order is unavailable (for example when ``body_names`` is empty), using only
    the authored joint relationships. Only resolves when the tip is unambiguous
    (a single non-gripper leaf) -- it never guesses among multiple leaves. A
    fixed tool-frame child of the tip is preferred when present.
    """
    from pxr import Usd, UsdPhysics

    body0s = set()  # paths used as a joint parent
    body1s = []  # paths used as a joint child, in traversal order
    for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        b0 = prim.GetRelationship("physics:body0").GetTargets()
        b1 = prim.GetRelationship("physics:body1").GetTargets()
        if not b1:
            continue
        if b0:
            body0s.add(str(b0[0]))
        body1s.append(str(b1[0]))
    if not body1s:
        return None

    def _leaf_name(path):
        return path.strip("<>").rstrip("/").split("/")[-1]

    # Tip candidates: child bodies that are never a parent.
    leaves = [p for p in dict.fromkeys(body1s) if p not in body0s]
    main = [p for p in leaves if not any(tok in _leaf_name(p).lower() for tok in _NON_CHAIN_BODY_TOKENS)]
    candidates = main or leaves
    if len(candidates) != 1:
        return None  # ambiguous (branched / gripper); do not guess

    tip_path = candidates[0]
    tip_prim = stage.GetPrimAtPath(tip_path)
    if not (tip_prim and tip_prim.IsValid()):
        name = _leaf_name(tip_path)
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            if prim.GetName() == name:
                tip_prim = prim
                break
    if tip_prim is None or not tip_prim.IsValid():
        return None

    fixed_child = _find_fixed_ee_child(tip_prim)
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

    tip_prim = None  # type: Optional[Any]
    for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        if prim.GetName() == tip_name or prim.GetName().lower() == tip_name.lower():
            tip_prim = prim
            break
    if tip_prim is None:
        return None

    fixed_child = _find_fixed_ee_child(tip_prim)
    if fixed_child:
        return fixed_child
    return str(tip_prim.GetPath())

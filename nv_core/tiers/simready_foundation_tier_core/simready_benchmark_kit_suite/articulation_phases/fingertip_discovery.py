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
"""Classify a gripper's finger topology at runtime.

Three outcomes:

- ``mimic_parallel_jaw`` -- exactly two finger DOFs related by a mimic joint
  (e.g. Robotiq 2F-85). Closure uses Isaac Sim's ``ParallelGripper`` API.
- ``independent_fingers`` -- N independent finger DOFs (e.g. multi-finger hand).
  Closure targets are inferred from kinematic fingertip motion.
- ``unsupported`` -- tendon-driven, coupled, or otherwise unrecognized
  topologies. The phase skips with a clear reason.

Polymorphism is intentionally avoided: ``FingertipSet`` is a tagged dataclass
with a ``kind`` field. The phase code branches on ``kind`` once. No isinstance
dispatch.
"""
from dataclasses import dataclass
from typing import List, Literal, Optional


@dataclass
class FingertipSet:
    kind: Literal["mimic_parallel_jaw", "independent_fingers", "unsupported"]
    tip_link_paths: List[str]
    mimic_master_dof: Optional[int]
    mimic_follower_dof: Optional[int]
    finger_chains: Optional[List[List[int]]]
    # Human-readable diagnostic explaining how the classifier reached this
    # kind. When ``kind == "unsupported"`` this is the WHY a real asset
    # failed the parallel-jaw check (mimic counts, master DOF resolution,
    # tip-body topology, etc.). Surfaced to result.json by the caller so
    # asset/framework triage doesn't require live log capture.
    reason: Optional[str] = None
    # All candidate tip-body prim paths for a mimic parallel jaw (master +
    # every follower child link). ``tip_link_paths`` is a rest-pose guess (two
    # of these); the close-lift phase re-selects the real pads from this full
    # list by MOTION, since finger links carry no live USD pose to rank at
    # discovery time. None for non-parallel-jaw kinds.
    candidate_tip_paths: Optional[List[str]] = None
    # True when ``tip_link_paths`` were matched to the authored
    # gripper_grip_line endpoints rather than inferred from topology alone.
    tips_from_grip_line: bool = False
    # Every independently actuated leader of a symmetric parallel jaw. The
    # common case has one master; Newton-native jaws may use two gentle
    # actuators, one per side, with passive linkage joints mimicking their
    # local leader. ``mimic_master_dof`` remains the primary/legacy leader.
    mimic_master_dofs: Optional[List[int]] = None


def discover_fingertips(stage, robot, gripper_site, robot_prim_path=None, ignored_joint_paths=()) -> FingertipSet:
    """Classify the gripper's finger topology.

    ``robot`` is a ``RobotHandle``-shape object exposing ``dof_names`` and
    ``prim_path`` (the asset's articulation root prim path). ``gripper_site``
    is a ``GripperSite`` from ``articulation_phases.gripper_sites``.
    ``ignored_joint_paths`` contains exact USD paths for test-owned joints
    which must not be classified as fingers.
    """
    from simready_benchmark_kit_suite.articulation_phases.mimic_joints import (
        detect_mimic_joints,
    )

    analysis_root = str(robot_prim_path or robot.prim_path)
    asset_prim = stage.GetPrimAtPath(analysis_root)
    if not asset_prim or not asset_prim.IsValid():
        return _unsupported("robot_prim_path %r did not resolve to a valid prim on the stage." % analysis_root)

    # detect_mimic_joints signature: (stage, asset_prim, robot_prim_path, dof_names)
    mimics = detect_mimic_joints(stage, asset_prim, analysis_root, robot.dof_names)

    parallel_jaw_outcome = _classify_parallel_jaw_mimic(
        stage,
        robot,
        mimics,
        analysis_root=analysis_root,
        ignored_joint_paths=ignored_joint_paths,
        gripper_site=gripper_site,
    )
    if isinstance(parallel_jaw_outcome, FingertipSet):
        return parallel_jaw_outcome
    parallel_jaw_reason = parallel_jaw_outcome  # str

    independent = _classify_independent_fingers(
        stage,
        robot,
        gripper_site,
        analysis_root=analysis_root,
        ignored_joint_paths=ignored_joint_paths,
    )
    if independent is not None:
        return independent

    return _unsupported(_summarize_unsupported(robot, mimics, parallel_jaw_reason))


def _summarize_unsupported(robot, mimics, parallel_jaw_reason: str) -> str:
    """Build a comprehensive diagnostic for the unsupported case.

    Reports everything the classifier saw -- DOF list summary, mimic count
    with per-spec details, why the parallel-jaw branch rejected, and why the
    independent-fingers branch wasn't taken. This is the message asset/framework
    triage reads when ``kind == "unsupported"``; it MUST contain enough detail
    to choose the correct fix (asset edit, classifier bug, framework bug, or
    genuine unsupported mechanism) without running the test again with extra
    logging.
    """
    lines = []
    lines.append("Classifier returned 'unsupported'. Diagnostic detail:")
    lines.append("")
    lines.append("Articulation DOFs (%d):" % len(robot.dof_names or []))
    for i, name in enumerate(robot.dof_names or []):
        lines.append("  [%d] %s" % (i, name))
    lines.append("")
    lines.append("Mimic specs detected: %d" % len(mimics))
    for i, m in enumerate(mimics):
        fpath = m.follower_joint_path.rsplit("/", 1)[-1]
        rpath = m.reference_joint_path.rsplit("/", 1)[-1]
        lines.append(
            "  [%d] follower=%s ref=%s gear=%r offset=%r "
            "follower_dof=%r ref_dof=%r"
            % (i, fpath, rpath, m.gear, m.offset, m.follower_dof_index, m.reference_dof_index)
        )
    lines.append("")
    lines.append("Parallel-jaw branch verdict:")
    lines.append("  %s" % parallel_jaw_reason)
    lines.append("")
    lines.append("Independent-fingers branch: fewer than two distinct driven fingertip branches resolved.")
    return "\n".join(lines)


def _unsupported(reason: Optional[str] = None) -> FingertipSet:
    return FingertipSet(
        kind="unsupported",
        tip_link_paths=[],
        mimic_master_dof=None,
        mimic_follower_dof=None,
        finger_chains=None,
        reason=reason,
    )


def _classify_parallel_jaw_mimic(
    stage,
    robot,
    mimics,
    analysis_root=None,
    ignored_joint_paths=(),
    gripper_site=None,
):
    """Symmetric mimic linkage with one or two driven leaders -> parallel_jaw.

    Accepts:
    - 1 master + 1 follower (e.g. simple symmetric two-finger gripper).
    - 1 master + N followers, all referencing the same master with |gear|=1
      (e.g. Robotiq 2F-85's 4-bar linkage: one driven joint, several
      mechanical-linkage followers).
    - 2 actuator-owned leaders, each with its own symmetric follower group,
      when the authored grip line resolves the two opposed pad branches.

    Returns:
    - A ``FingertipSet`` on success.
    - A ``str`` explaining the rejection reason on failure. The caller
      surfaces this string in the unsupported diagnostic so triage doesn't
      need a live log capture.
    """
    import logging

    log = logging.getLogger(__name__)

    if not mimics:
        return (
            "No PhysxMimicJointAPI applications detected by "
            "detect_mimic_joints. Either the asset authors no mimic "
            "relationships, or the detector failed to enumerate them "
            "(check mimic_joints.detect_mimic_joints for a regression)."
        )

    # A conventional mimic jaw has one leader. A Newton-native equivalent may
    # split the squeeze across two actuator-owned jaw leaders. Do not interpret
    # arbitrary two-master mechanisms as a gripper: both leaders must be
    # explicit Newton actuator targets, and the grip-line check below must
    # resolve an opposed pad pair.
    master_indices = {s.reference_dof_index for s in mimics}
    if None in master_indices or len(master_indices) not in (1, 2):
        unresolved = sum(1 for s in mimics if s.reference_dof_index is None)
        distinct = len([x for x in master_indices if x is not None])
        log.info(
            "Mimic specs reference %d distinct master DOFs (need 1 or a supported actuator-owned pair); "
            "rejecting parallel-jaw classification",
            len(master_indices),
        )
        return (
            "Mimic-master DOF check failed: distinct master DOF indices=%d, "
            "specs with unresolvable master DOF (ref_dof_index=None)=%d. "
            "Parallel-jaw requires one master DOF, or exactly two supported "
            "actuator-owned master DOFs, across all mimics; a None "
            "reference_dof_index means the ref joint's name "
            "isn't in robot.dof_names (multi-finger hand topology or "
            "name-mismatch authoring)." % (distinct, unresolved)
        )
    master_indices = sorted(master_indices)
    master_idx = master_indices[0]
    dual_master = len(master_indices) == 2
    if dual_master:
        from simready_benchmark_kit_suite.articulation_phases.passive_joints import (
            _actuator_target_paths,
        )

        actuator_targets = _actuator_target_paths(stage, str(analysis_root or robot.prim_path))
        master_paths = {spec.reference_joint_path for spec in mimics}
        if not master_paths.issubset(actuator_targets):
            return (
                "Two mimic masters were found, but both are not explicit NewtonActuator "
                "targets. Refusing to treat an arbitrary multi-master mechanism as a "
                "parallel jaw. masters=%s actuator_targets=%s."
                % (sorted(master_paths), sorted(actuator_targets))
            )

    # All mimics must be symmetric (|gear|=1, offset~0). Any asymmetric one
    # disqualifies the whole assembly.
    for spec in mimics:
        if not _is_symmetric_mimic(spec):
            log.info(
                "Mimic gear %r (offset %r) outside {+/-1.0, 0}; " "rejecting parallel-jaw classification",
                getattr(spec, "gear", None),
                getattr(spec, "offset", None),
            )
            return (
                "Asymmetric mimic detected: follower=%s gear=%r offset=%r. "
                "Parallel-jaw requires |gear|=1 and offset~0; any other "
                "value implies a non-symmetric coupling that doesn't fit "
                "the close+lift model."
                % (
                    spec.follower_joint_path.rsplit("/", 1)[-1],
                    spec.gear,
                    spec.offset,
                )
            )

    # No extra independent DOFs allowed. Two ordinary arrangements:
    # - len(dof_names) == 1: use_mimic_joints already on, only master visible.
    # - len(dof_names) == 1 + len(mimics): all DOFs visible (master + every
    #   follower). Anything else means there are independent joints we're not
    #   modelling -- reject.
    #
    # Newton exposes passive DOFs in closed four-bar linkages even though only
    # the master and mimic follower are controlled.  Those are not independent
    # fingers and must not make a valid parallel jaw look like mixed topology.
    # Reuse the same closed-loop classification as FET022 and accept extras
    # only when every one is a loop/linkage DOF.  An arbitrary extra joint is
    # still rejected.
    n_dof = len(robot.dof_names)
    ignored_names = {str(path).rsplit("/", 1)[-1] for path in ignored_joint_paths}
    ignored_indices = {index for index, name in enumerate(robot.dof_names) if str(name) in ignored_names}
    expected_indices = set(master_indices)
    expected_indices.update(s.follower_dof_index for s in mimics if s.follower_dof_index is not None)
    extra_indices = set(range(n_dof)) - expected_indices - ignored_indices
    loop_indices = frozenset()
    if extra_indices:
        try:
            from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
                detect_loop_joints,
            )

            loop_indices, _loop_names = detect_loop_joints(
                stage,
                str(analysis_root or robot.prim_path),
                robot.dof_names,
            )
        except Exception:
            loop_indices = frozenset()
    extras_are_linkage = bool(extra_indices) and extra_indices.issubset(loop_indices)
    effective_dof_count = n_dof - len(ignored_indices)
    visible_master_count = len(master_indices)
    if (
        effective_dof_count != visible_master_count
        and effective_dof_count != visible_master_count + len(mimics)
        and not extras_are_linkage
    ):
        log.info(
            "Articulation has %d DOFs but %d mimics; expected %d (mimics hidden) "
            "or %d (all visible); rejecting parallel-jaw classification",
            effective_dof_count,
            len(mimics),
            visible_master_count,
            visible_master_count + len(mimics),
        )
        return (
            "DOF count check failed: articulation has %d DOFs but %d mimics; "
            "expected DOFs to equal master_count=%d (mimics hidden by "
            "use_mimic_joints) or master_count+mimic_count=%d (all DOFs "
            "visible). %d-vs-%d means there "
            "are extra independent joints in the articulation that don't "
            "belong to the mimic chain or a detected closed linkage -- mixed "
            "topology. Extra DOF indices=%s; detected linkage indices=%s."
            % (
                effective_dof_count,
                len(mimics),
                visible_master_count,
                visible_master_count + len(mimics),
                effective_dof_count,
                visible_master_count + len(mimics),
                sorted(extra_indices),
                sorted(loop_indices),
            )
        )

    # Collect the candidate tip body paths: one from each follower joint
    # plus one from the master joint. Deduplicate while preserving discovery
    # order (master first, then followers in their original order).
    candidate_paths = []
    seen = set()
    for master_path in dict.fromkeys(spec.reference_joint_path for spec in mimics):
        master_tip = _resolve_joint_child_link_from_path(stage, master_path)
        if master_tip and master_tip not in seen:
            candidate_paths.append(master_tip)
            seen.add(master_tip)
    for spec in mimics:
        tip = _resolve_joint_child_link_from_path(stage, spec.follower_joint_path)
        if tip and tip not in seen:
            candidate_paths.append(tip)
            seen.add(tip)

    # A native Newton four-bar normally authors one master plus one mimic
    # driver; its real pads are reached through passive linkage joints.  Add
    # every downstream body as a motion candidate so the runtime aperture
    # probe can select the physical pads rather than the proximal knuckles.
    asset_prim = stage.GetPrimAtPath(str(analysis_root or robot.prim_path))
    child_map = _build_child_link_map(stage, asset_prim)
    for seed in list(candidate_paths):
        for body_path in _reachable_descendants(child_map, seed):
            if body_path not in seen:
                candidate_paths.append(body_path)
                seen.add(body_path)

    if len(candidate_paths) < 2:
        log.info(
            "Mimic chain produced only %d distinct tip bodies; need >= 2",
            len(candidate_paths),
        )
        return (
            "Tip body resolution failed: mimic chain produced only %d "
            "distinct tip bodies (need >= 2). Each follower joint's "
            "body1 (or body0 fallback) didn't resolve to a unique rigid "
            "body. Inspect the joint relationships under the gripper "
            "subtree." % len(candidate_paths)
        )

    # For 2 candidates this is identity; for N>2 (e.g. Robotiq 2F-85), pick the
    # two bodies furthest apart in rest pose -- those are the real contact pads
    # at the ends of the two finger chains. Internal linkage bodies cluster
    # near the palm and lose to the leaf pads on the pairwise-distance metric.
    tip_paths = _pick_bodies_at_grip_line_endpoints(stage, candidate_paths, gripper_site)
    tips_from_grip_line = tip_paths is not None
    if tip_paths is None:
        tip_paths = _pick_two_furthest_apart(stage, candidate_paths)
    if tip_paths is None:
        return (
            "Tip body world-pose resolution failed: _pick_two_furthest_apart "
            "encountered an invalid prim while computing rest-pose XYZs "
            "for the %d candidate paths." % len(candidate_paths)
        )
    if dual_master and not tips_from_grip_line:
        return (
            "Two actuator-owned mimic masters were found, but their downstream "
            "bodies could not be matched to both authored gripper_grip_line "
            "endpoints. Refusing ambiguous dual-jaw classification."
        )

    # Pick a representative follower DOF index (first one with a resolved
    # index). Multi-mimic assemblies don't have a single canonical follower,
    # but downstream orchestration uses this only for diagnostics; the master
    # DOF is what drives the assembly.
    follower_idx = next(
        (s.follower_dof_index for s in mimics if s.follower_dof_index is not None),
        None,
    )

    return FingertipSet(
        kind="mimic_parallel_jaw",
        tip_link_paths=tip_paths,
        mimic_master_dof=master_idx,
        mimic_follower_dof=follower_idx,
        finger_chains=None,
        candidate_tip_paths=candidate_paths,
        tips_from_grip_line=tips_from_grip_line,
        mimic_master_dofs=master_indices,
    )


def _pick_bodies_at_grip_line_endpoints(stage, body_paths, gripper_site):
    """Resolve the two pad bodies from the authored FET028 grip line.

    ``gripper_grip_line`` is the contract's pad-to-pad line at maximum open.
    Match each endpoint to the closest candidate rigid body's world bound.  This
    is more reliable than ranking live four-bar poses: a solver can transiently
    overshoot a mimic follower during endpoint probing, while the authored site
    remains the asset's stable semantic declaration of its contact pads.
    """
    if gripper_site is None or not getattr(gripper_site, "grip_line_world", None):
        return None
    try:
        from pxr import Gf, Usd, UsdGeom

        endpoints = [Gf.Vec3d(*[float(value) for value in point]) for point in gripper_site.grip_line_world]
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
        bounds = {}
        for path in body_paths:
            prim = stage.GetPrimAtPath(path)
            if not prim or not prim.IsValid():
                continue
            bounds[path] = cache.ComputeWorldBound(prim).ComputeAlignedBox()

        def _distance_to_bound(point, bound):
            minimum = bound.GetMin()
            maximum = bound.GetMax()
            squared = 0.0
            for axis in range(3):
                value = float(point[axis])
                if value < float(minimum[axis]):
                    squared += (float(minimum[axis]) - value) ** 2
                elif value > float(maximum[axis]):
                    squared += (value - float(maximum[axis])) ** 2
            return squared**0.5

        best = None
        for first_path, first_bound in bounds.items():
            for second_path, second_bound in bounds.items():
                if second_path == first_path:
                    continue
                score = _distance_to_bound(endpoints[0], first_bound) + _distance_to_bound(endpoints[1], second_bound)
                candidate = (score, first_path, second_path)
                if best is None or candidate < best:
                    best = candidate
        return [best[1], best[2]] if best is not None else None
    except Exception:
        return None


def _pick_two_furthest_apart(stage, body_paths):
    """Return the pair of body paths with the largest rest-pose XYZ distance.

    Used to disambiguate the two contact-pad bodies from internal linkage
    bodies in multi-mimic grippers. Reads USD-authored transforms (the
    asset's rest pose), not live physics state, so it works at discovery
    time before the simulation has stepped.

    Returns ``None`` if any path resolves to an invalid prim (caller should
    treat as ``unsupported``).
    """
    import numpy as np
    from pxr import UsdGeom

    cache = UsdGeom.XformCache()
    positions = []
    for p in body_paths:
        prim = stage.GetPrimAtPath(p)
        if not prim or not prim.IsValid():
            return None
        m = np.array(cache.GetLocalToWorldTransform(prim)).reshape(4, 4)
        positions.append(m[3, :3])

    best_d2 = -1.0
    best_i = best_j = 0
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            d = positions[i] - positions[j]
            d2 = float(d.dot(d))
            if d2 > best_d2:
                best_d2 = d2
                best_i, best_j = i, j
    return [body_paths[best_i], body_paths[best_j]]


def _is_symmetric_mimic(spec) -> bool:
    """Accept gear in {1.0, -1.0} (symmetric closure) and offset close to 0."""
    gear = getattr(spec, "gear", None)
    offset = getattr(spec, "offset", 0.0) or 0.0
    if gear is None:
        return False
    return abs(abs(gear) - 1.0) < 1e-6 and abs(offset) < 1e-3


def _resolve_joint_child_link_from_path(stage, joint_path: str):
    """Given a known joint prim path, return the 'tip' body path.

    Tries ``body1`` first (the conventional moving-link target); falls back to
    ``body0`` if ``body1`` is empty (some assets author the convention
    reversed). Returns None on any failure -- callers translate that into
    ``unsupported``.
    """
    from pxr import UsdPhysics

    if not joint_path:
        return None
    prim = stage.GetPrimAtPath(joint_path)
    if not prim or not prim.IsValid():
        return None
    if not prim.IsA(UsdPhysics.Joint):
        return None
    for rel_name in ("physics:body1", "physics:body0"):
        rel = prim.GetRelationship(rel_name)
        if not rel:
            continue
        targets = rel.GetTargets()
        if targets:
            return str(targets[0])
    return None


def _joint_bodies(stage, joint_path: str):
    """Return ``(body0, body1)`` prim paths of a joint (parent, child), or
    ``(None, None)``. Used to walk a finger's kinematic chain to its distal end."""
    from pxr import UsdPhysics

    if not joint_path:
        return (None, None)
    prim = stage.GetPrimAtPath(joint_path)
    if not prim or not prim.IsValid():
        return (None, None)
    if not prim.IsA(UsdPhysics.Joint):
        return (None, None)

    def _first(rel_name):
        rel = prim.GetRelationship(rel_name)
        if not rel:
            return None
        targets = rel.GetTargets()
        return str(targets[0]) if targets else None

    return (_first("physics:body0"), _first("physics:body1"))


def _build_child_link_map(stage, asset_prim):
    """``{body0_path: [body1_path, ...]}`` over ALL joints under the asset
    (revolute, prismatic, AND fixed -- drive or not). This is the full link
    graph, so a finger's tip can be traced past its last ACTUATED joint through
    the passive/virtual links that extend it to the real fingertip."""
    from pxr import Usd, UsdPhysics

    child_map = {}
    for prim in Usd.PrimRange(asset_prim):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        b0, b1 = _joint_bodies(stage, str(prim.GetPath()))
        if b0 and b1:
            child_map.setdefault(b0, []).append(b1)
    return child_map


def _deepest_leaf(child_map, seed):
    """Follow child links forward from ``seed`` to the deepest reachable leaf.
    Returns ``(leaf_path, depth)``. Cycle-guarded."""
    best = (seed, 0)
    stack = [(seed, 0, {seed})]
    while stack:
        node, d, ancestors = stack.pop()
        kids = [c for c in child_map.get(node, []) if c and c not in ancestors]
        if not kids and d > best[1]:
            best = (node, d)
        for c in kids:
            stack.append((c, d + 1, ancestors | {c}))
    return best


def _reachable_descendants(child_map, seed):
    """Return all bodies reachable below ``seed`` in stable graph order.

    The seed itself is omitted.  The traversal is cycle-safe because closed
    gripper linkages can contain a maximal-coordinate closure edge.
    """
    found = []
    seen = {seed}
    pending = list(child_map.get(seed, []))
    while pending:
        body_path = pending.pop(0)
        if not body_path or body_path in seen:
            continue
        seen.add(body_path)
        found.append(body_path)
        pending.extend(child_map.get(body_path, []))
    return found


def _distal_tip_of_finger(joints, child_map):
    """Most-distal fingertip link of a finger.

    ``joints`` is ``[(joint_path, body0, body1, name_lower), ...]`` for the
    finger's ACTUATED joints. Starting from each actuated joint's child link,
    walk the FULL link graph (``child_map``, including passive/virtual/fixed
    joints) to the deepest leaf, and return the deepest leaf across all the
    finger's actuated branches. This is purely kinematic -- no joint-name
    assumptions -- so it picks the thumb's flexion chain leaf over the shorter
    opposition-output link, and extends every finger past its last actuated
    joint to the real fingertip. Returns ``None`` if no branch resolves.
    """
    best_leaf, best_depth = None, -1
    for _p, _b0, b1, _n in joints:
        if not b1:
            continue
        leaf, depth = _deepest_leaf(child_map, b1)
        if depth > best_depth:
            best_leaf, best_depth = leaf, depth
    return best_leaf


def _joint_has_drive(prim):
    """True if a joint prim has a PhysicsDriveAPI applied (angular or linear).

    Reads the raw ``apiSchemas`` listOp metadata (robust offline AND in Isaac,
    where some schemas are unregistered) rather than HasAPI."""
    try:
        md = prim.GetMetadata("apiSchemas")
        items = list(md.GetAddedOrExplicitItems()) if md else []
    except Exception:
        items = []
    return any("DriveAPI" in str(x) for x in items)


def _distinct_resolved_tip_paths(fingers, distal_tip):
    """Return resolved tips only when they identify two physical branches."""
    tip_paths = [distal_tip[finger] for finger in fingers if finger in distal_tip]
    if len(tip_paths) < 2 or len(set(tip_paths)) < 2:
        return None
    return tip_paths


def _group_actuated_joint_branches(records, parent_map):
    """Group driven joints by their highest driven ancestor in the link graph."""
    driven_by_child = {record["body1"]: record for record in records if record["body1"]}
    groups = {}
    for record in records:
        branch_root = record["path"]
        current = record["body0"]
        visited = set()
        while current and current not in visited:
            visited.add(current)
            ancestor = driven_by_child.get(current)
            if ancestor is not None:
                branch_root = ancestor["path"]
            current = parent_map.get(current)
        groups.setdefault(branch_root, []).append(record)
    return groups


def _classify_independent_fingers(stage, robot, gripper_site, analysis_root=None, ignored_joint_paths=()):
    """Multi-finger hand: N independently-actuated finger DOFs with no single
    mimic master (for example, an anthropomorphic hand).

    Returns a ``FingertipSet`` whose ``finger_chains`` is one list of actuated
    DOF indices per physical branch (grouped by driven-joint ancestry), and
    ``tip_link_paths`` is each finger's distal child link. The grasp phase
    drives these DOFs toward contact. Returns ``None`` unless at least two
    actuated finger branches resolve to distinct
    physical tip links (not a grasping hand otherwise)."""
    from pxr import Usd, UsdPhysics

    search_root = str(analysis_root or robot.prim_path)
    asset_prim = stage.GetPrimAtPath(search_root)
    if not asset_prim or not asset_prim.IsValid():
        return None
    name_to_idx = {n: i for i, n in enumerate(robot.dof_names)}
    ignored_paths = {str(path) for path in ignored_joint_paths}
    # Newton runtime layers normally remove PhysicsDriveAPI and express each
    # independently controlled finger with a NewtonActuator. Treat those
    # actuator targets exactly like driven joints for topology discovery.
    from simready_benchmark_kit_suite.articulation_phases.passive_joints import (
        _actuator_target_paths,
    )

    actuator_target_paths = _actuator_target_paths(stage, search_root)

    parent_map = {}
    records = []
    for prim in Usd.PrimRange(asset_prim):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        b0, b1 = _joint_bodies(stage, str(prim.GetPath()))
        if b0 and b1:
            parent_map[b1] = b0
        if not (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)):
            continue
        if not _joint_has_drive(prim) and str(prim.GetPath()) not in actuator_target_paths:
            continue
        jname = prim.GetName()
        if str(prim.GetPath()) in ignored_paths:
            continue
        idx = name_to_idx.get(jname)
        if idx is None:
            continue
        records.append(
            {
                "path": str(prim.GetPath()),
                "body0": b0,
                "body1": b1,
                "idx": idx,
                "name": jname,
            }
        )

    branches = _group_actuated_joint_branches(records, parent_map)
    if len(records) < 2 or len(branches) < 2:
        return None

    fingers = list(branches.keys())
    finger_chains = [[record["idx"] for record in branches[finger]] for finger in fingers]
    # Each finger's tip is the deepest leaf link reachable from its actuated
    # joints through the FULL link graph (passive/virtual joints included), so
    # the tip is the real fingertip and not a mid-chain or opposition-output
    # link -- see _distal_tip_of_finger.
    child_map = _build_child_link_map(stage, asset_prim)
    distal_tip = {}
    for f in fingers:
        joints = [(record["path"], record["body0"], record["body1"], record["name"].lower()) for record in branches[f]]
        tip = _distal_tip_of_finger(joints, child_map)
        if tip is not None:
            distal_tip[f] = tip
    tip_paths = _distinct_resolved_tip_paths(fingers, distal_tip)
    if tip_paths is None:
        return None

    return FingertipSet(
        kind="independent_fingers",
        tip_link_paths=tip_paths,
        mimic_master_dof=None,
        mimic_follower_dof=None,
        finger_chains=finger_chains,
        reason=("independent_fingers: %d actuated DOFs across %d graph branches" % (len(records), len(fingers))),
    )

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

- ``mimic_parallel_jaw`` -- position-driven parallel/centric fingers related
  by mimic joints. Closure uses sparse leader commands and measured polarity.
- ``independent_fingers`` -- N independent finger DOFs (e.g. multi-finger hand).
  Closure targets are inferred from kinematic fingertip motion.
- ``unsupported`` -- no usable finger branches resolved.

Active couplings require complete selected ownership before either mapping.
Independent finger chains contain leaders only; follower geometry remains in
the physical graph. Unsafe or unresolved ownership is a runtime/setup error.

Polymorphism is intentionally avoided: ``FingertipSet`` is a tagged dataclass
with a ``kind`` field. The phase code branches on ``kind`` once. No isinstance
dispatch.
"""

from dataclasses import dataclass
from typing import Literal


class GripperTopologyError(RuntimeError):
    """Active coupling could not establish safe sparse leader ownership."""


@dataclass
class FingertipSet:
    kind: Literal["mimic_parallel_jaw", "independent_fingers", "unsupported"]
    tip_link_paths: list[str]
    mimic_master_dof: int | None
    mimic_follower_dof: int | None
    finger_chains: list[list[int]] | None
    # Human-readable diagnostic explaining how the classifier reached this
    # kind. When ``kind == "unsupported"`` this is the WHY a real asset
    # failed the parallel-jaw check (mimic counts, master DOF resolution,
    # tip-body topology, etc.). Surfaced to result.json by the caller so
    # asset/framework triage doesn't require live log capture.
    reason: str | None = None
    # All candidate tip-body prim paths for a mimic parallel jaw (master +
    # every follower child link). ``tip_link_paths`` is a rest-pose guess (two
    # of these); the close-lift phase re-selects the real pads from this full
    # list by MOTION, since finger links carry no live USD pose to rank at
    # discovery time. None for non-parallel-jaw kinds.
    candidate_tip_paths: list[str] | None = None
    # Legacy compatibility field; GR.003 never declares jaw endpoint identity.
    tips_from_grip_line: bool = False
    # Every independently actuated leader of a symmetric parallel jaw. The
    # common case has one master; Newton-native jaws may use two gentle
    # actuators, one per side, with passive linkage joints mimicking their
    # local leader. ``mimic_master_dof`` remains the primary/legacy leader.
    mimic_master_dofs: list[int] | None = None
    candidate_branches: dict | None = None
    master_open_closed_positions: dict | None = None


def discover_fingertips(stage, robot, gripper_site, robot_prim_path=None, ignored_joint_paths=()) -> FingertipSet:
    """Classify the gripper's finger topology.

    ``robot`` is a ``RobotHandle``-shape object exposing ``dof_names`` and
    ``prim_path`` (the asset's articulation root prim path). ``gripper_site``
    is a ``GripperSite`` from ``articulation_phases.gripper_sites``.
    An explicit ``robot_prim_path`` restricts joint enumeration, not the verified
    loaded ``robot.asset_prim`` boundary used to establish physical ownership.
    ``ignored_joint_paths`` contains exact USD paths for test-owned joints
    which must not be classified as fingers.
    """
    from simready.foundation.tier_core.runtime_tests.articulation_phases.mimic_joints import (
        detect_mimic_joints,
    )

    analysis_root, selected_joint_paths = _discovery_scope(stage, robot, robot_prim_path)
    asset_prim = stage.GetPrimAtPath(analysis_root)
    if not asset_prim or not asset_prim.IsValid():
        return _unsupported("robot_prim_path %r did not resolve to a valid prim on the stage." % analysis_root)
    if selected_joint_paths is not None:
        _validate_selected_drive_identities(stage, robot, asset_prim, selected_joint_paths, ignored_joint_paths)

    # Physical discovery retains the verified boundary even when enumeration is
    # narrowed to a sibling joint subtree. The selected-path intersection below
    # still rejects references outside that scope. Schema-light legacy callers
    # retain their explicitly bounded enumeration.
    mimic_boundary = getattr(robot, "asset_prim", None) if selected_joint_paths is not None else None
    if mimic_boundary is None:
        mimic_boundary = asset_prim
    try:
        mimics = detect_mimic_joints(stage, mimic_boundary, robot.prim_path, robot.dof_names)
    except RuntimeError as error:
        detail = str(error).replace("verified loaded asset subtree", "verified loaded asset boundary")
        raise GripperTopologyError(f"FET028 mapping/setup limitation: {detail}") from error
    if selected_joint_paths is not None:
        from pxr import UsdPhysics

        controlled_joint_paths = {
            path
            for path in selected_joint_paths
            if not UsdPhysics.Joint(stage.GetPrimAtPath(path)).GetExcludeFromArticulationAttr().Get()
        }
        mimics = [spec for spec in mimics if spec.follower_joint_path in controlled_joint_paths]
        for spec in mimics:
            if spec.reference_joint_path not in controlled_joint_paths:
                raise GripperTopologyError(
                    f"FET028 mapping/setup limitation: selected mimic follower {spec.follower_joint_path} references "
                    f"a joint outside its articulation: {spec.reference_joint_path}"
                )

    # The response detector can omit unresolved authored edges. Validate raw
    # coverage BEFORE accepting even a plausible parallel-jaw subset.
    mimics = _validated_mimic_ownership(stage, robot, asset_prim, mimics, selected_joint_paths, ignored_joint_paths)

    parallel_jaw_outcome = _classify_parallel_jaw_mimic(
        stage,
        robot,
        mimics,
        analysis_root=analysis_root,
        ignored_joint_paths=ignored_joint_paths,
        gripper_site=gripper_site,
        selected_joint_paths=selected_joint_paths,
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
        selected_joint_paths=selected_joint_paths,
        mimics=mimics,
    )
    if independent is not None:
        return independent
    if mimics:
        bindings = "; ".join(
            "follower=%s[DOF=%r] reference=%s[DOF=%r] gear=%r offset=%r"
            % (
                spec.follower_joint_path,
                spec.follower_dof_index,
                spec.reference_joint_path,
                spec.reference_dof_index,
                spec.gear,
                spec.offset,
            )
            for spec in mimics
        )
        raise GripperTopologyError(
            "FET028 mapping/setup limitation: active mimic topology is not a supported "
            f"parallel/centric mapping or independent leader-owned physical branches. {parallel_jaw_reason} "
            f"Couplings: {bindings}"
        )

    return _unsupported(_summarize_unsupported(robot, mimics, parallel_jaw_reason))


def _validated_mimic_ownership(stage, robot, asset_prim, mimics, selected_paths, ignored_paths):
    """Require every active authored selected edge, identity and finite equation.

    Hidden follower DOFs are permitted. The ultimate independent reference must
    resolve uniquely in the native coordinate list; no detector defaults can
    substitute for a missing raw authored equation.
    """
    from math import isfinite
    from numbers import Real

    from pxr import Usd, UsdPhysics
    from simready.foundation.tier_core.runtime_tests.articulation_phases.mimic_joints import (
        _raw_applied_api_names,
    )

    def reject(detail):
        raise GripperTopologyError("FET028 mapping/setup limitation: active mimic topology " + detail)

    ignored = set(map(str, ignored_paths))
    joints, by_name, raw = {}, {}, {}
    for prim in Usd.PrimRange(asset_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        path = str(prim.GetPath())
        if path in ignored or (selected_paths is not None and path not in selected_paths):
            continue
        schemas = set(_raw_applied_api_names(prim)) | set(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        instances = sorted(name for name in schemas if name.startswith("PhysxMimicJointAPI:"))
        enabled = prim.GetAttribute("newton:mimicEnabled")
        if "NewtonMimicAPI" in schemas and not (enabled and enabled.Get() is False):
            instances.append("NewtonMimicAPI")
        if not prim.IsA(UsdPhysics.Joint):
            if instances:
                reject(f"is authored on a non-joint: {path}")
            continue
        joint = UsdPhysics.Joint(prim)
        if joint.GetJointEnabledAttr().Get() is False or joint.GetExcludeFromArticulationAttr().Get():
            continue
        joints[path] = prim
        by_name.setdefault(prim.GetName(), []).append(path)
        if not instances:
            continue
        if len(instances) != 1 or not (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)):
            reject(f"has ambiguous/unsupported coupling APIs: {path}: {instances}")
        schema = instances[0]
        if schema == "NewtonMimicAPI":
            rel_name, gear_name, offset_name = "newton:mimicJoint", "newton:mimicCoef1", "newton:mimicCoef0"
        else:
            axis = schema.split(":", 1)[1]
            rel_name = f"physxMimicJoint:{axis}:referenceJoint"
            gear_name, offset_name = f"physxMimicJoint:{axis}:gearing", f"physxMimicJoint:{axis}:offset"
        rel = prim.GetRelationship(rel_name)
        targets = rel.GetForwardedTargets() if rel else []
        if len(targets) != 1 or not targets[0].IsPrimPath():
            reject(f"has an unresolved reference: {path}")
        coefficients = []
        for name in (gear_name, offset_name):
            attr = prim.GetAttribute(name)
            value = attr.Get() if attr else None
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
                reject(f"has missing/invalid coefficient {name}: {path}")
            coefficients.append(float(value))
        raw[path] = (str(targets[0]), *coefficients)

    from .joint_identity import joint_for_native_name

    def native_indices(path):
        return [
            i
            for i, name in enumerate(robot.dof_names)
            if joint_for_native_name(list(joints.values()), name) == joints[path]
        ]

    selected = [spec for spec in mimics if spec.follower_joint_path in joints]
    followers = {}
    for spec in selected:
        follower, reference = spec.follower_joint_path, spec.reference_joint_path
        if reference not in joints:
            reject(f"references a joint outside its articulation: {follower} -> {reference}")
        if follower in followers:
            reject(f"has duplicate follower ownership: {follower}")
        for value in (spec.gear, spec.offset):
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
                reject(f"has invalid/nonfinite coefficients: {follower}")
        for path, index in ((follower, spec.follower_dof_index), (reference, spec.reference_dof_index)):
            indices = native_indices(path)
            if len(indices) > 1 or (index is not None and indices != [index]):
                reject(f"has ambiguous joint/native identity: {path}")
        if follower in raw and raw[follower] != (reference, float(spec.gear), float(spec.offset)):
            reject(f"has an inconsistent detected equation: {follower}")
        followers[follower] = reference
    if not raw.keys() <= followers.keys():
        reject(f"has unresolved authored coupling coverage: {sorted(raw.keys() - followers.keys())}")
    for follower in followers:
        current, visited = follower, set()
        while current in followers:
            if current in visited:
                reject(f"contains a reference cycle: {follower}")
            visited.add(current)
            current = followers[current]
        if len(native_indices(current)) != 1:
            reject(f"has no unique native leader coordinate: {current}")
    return selected


def _discovery_scope(stage, robot, explicit_root):
    from .joint_identity import JointIdentityError, discovery_scope

    try:
        return discovery_scope(stage, robot, explicit_root)
    except JointIdentityError as error:
        detail = str(error).replace("verified loaded asset subtree", "verified loaded asset boundary")
        raise GripperTopologyError(f"FET028 mapping/setup limitation: {detail}") from error


def _selected_native_indices(joints, names):
    from .joint_identity import joint_for_native_name

    indices = {}
    for index, name in enumerate(names):
        prim = joint_for_native_name(joints, name)
        if prim is not None:
            indices.setdefault(str(prim.GetPath()), []).append(index)
    return indices


def _validate_selected_drive_identities(stage, robot, asset_prim, joint_paths, ignored_joint_paths):
    """Reject ambiguous native ownership before accepting a jaw or hand."""
    from pxr import UsdPhysics

    from .joint_identity import native_joint_name

    joints = [
        stage.GetPrimAtPath(path)
        for path in joint_paths
        if path not in set(ignored_joint_paths)
        and not UsdPhysics.Joint(stage.GetPrimAtPath(path)).GetExcludeFromArticulationAttr().Get()
    ]
    indices = _selected_native_indices(joints, robot.dof_names)
    for prim in joints:
        basename = prim.GetName()
        ambiguous_name = sum(joint.GetName() == basename for joint in joints) > 1 and any(
            native_joint_name(name) == basename for name in robot.dof_names
        )
        if _joint_has_drive(prim) and (len(indices.get(str(prim.GetPath()), [])) > 1 or ambiguous_name):
            raise GripperTopologyError(
                f"FET028 mapping/setup limitation: selected driven joint name {basename!r} is ambiguous"
            )


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


def _unsupported(reason: str | None = None) -> FingertipSet:
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
    selected_joint_paths=None,
):
    """Symmetric mimic linkage with one or two driven leaders -> parallel_jaw.

    Accepts:
    - 1 master + 1 follower (e.g. simple symmetric two-finger gripper).
    - 1 master + N followers, all referencing the same master with |gear|=1
      (e.g. Robotiq 2F-85's 4-bar linkage: one driven joint, several
      mechanical-linkage followers).
    - 2 actuator-owned leaders, each with its own symmetric follower group,
      with distinct physical joint-graph branches and live-owned pad mapping.

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
    # explicit Newton actuator targets. Distinct joint-graph branches below
    # supply candidates; later live geometry resolves pads and leader polarity.
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
        from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
            _actuator_target_paths,
        )

        actuator_targets = _actuator_target_paths(stage, str(analysis_root or robot.prim_path))
        master_paths = {spec.reference_joint_path for spec in mimics}
        if not master_paths.issubset(actuator_targets):
            return (
                "Two mimic masters were found, but both are not explicit NewtonActuator "
                "targets. Refusing to treat an arbitrary multi-master mechanism as a "
                "parallel jaw. masters=%s actuator_targets=%s." % (sorted(master_paths), sorted(actuator_targets))
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

    # Every native coordinate needs exact selected ownership. Hidden followers
    # cannot lend their expected count to unrelated independent coordinates.
    #
    # Newton exposes passive DOFs in closed four-bar linkages even though only
    # the master and mimic follower are controlled.  Those are not independent
    # fingers and must not make a valid parallel jaw look like mixed topology.
    # Reuse the same closed-loop classification as FET022 and accept extras
    # only when every one is a loop/linkage DOF.  An arbitrary extra joint is
    # still rejected.
    n_dof = len(robot.dof_names)
    from pxr import Usd, UsdPhysics

    owned_paths = selected_joint_paths
    if owned_paths is None:
        owned_paths = {
            str(prim.GetPath())
            for prim in Usd.PrimRange(stage.GetPrimAtPath(str(analysis_root or robot.prim_path)))
            if prim.IsA(UsdPhysics.Joint)
        }
    ignored_indices = set()
    for ignored_path in map(str, ignored_joint_paths):
        prim = stage.GetPrimAtPath(ignored_path)
        if not prim or not prim.IsA(UsdPhysics.Joint):
            continue
        name = prim.GetName()
        matching_owned = {path for path in owned_paths if stage.GetPrimAtPath(path).GetName() == name}
        if matching_owned - {ignored_path} or robot.dof_names.count(name) != 1:
            continue
        ignored_indices.add(robot.dof_names.index(name))
    expected_indices = set(master_indices)
    expected_indices.update(s.follower_dof_index for s in mimics if s.follower_dof_index is not None)
    extra_indices = set(range(n_dof)) - expected_indices - ignored_indices
    loop_indices = frozenset()
    if extra_indices:
        try:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
                detect_loop_joints,
            )

            loop_indices, _loop_names = detect_loop_joints(
                stage,
                str(analysis_root or robot.prim_path),
                robot.dof_names,
                selected_joint_paths=selected_joint_paths,
            )
        except Exception:
            loop_indices = frozenset()
    extras_are_linkage = bool(extra_indices) and extra_indices.issubset(loop_indices)
    if extra_indices and not extras_are_linkage:
        return (
            "DOF ownership check failed: extra native coordinates do not "
            "belong to the selected mimic chain or a qualified selected closed linkage -- mixed "
            f"topology. Extra DOF indices={sorted(extra_indices)}; detected linkage indices={sorted(loop_indices)}."
        )

    asset_prim = stage.GetPrimAtPath(str(analysis_root or robot.prim_path))
    oriented = None
    if selected_joint_paths is not None:
        selected_joints = [
            prim
            for prim in Usd.PrimRange(asset_prim)
            if prim.IsA(UsdPhysics.Joint)
            and str(prim.GetPath()) in selected_joint_paths
            and UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is not False
            and not UsdPhysics.Joint(prim).GetExcludeFromArticulationAttr().Get()
        ]
        # Authored endpoint order does not determine physical ownership.
        # Reuse qualified root orientation; excluded closure edges cannot
        # supply a second parent or turn the palm into a fingertip.
        oriented = _orient_independent_tree(stage, robot, asset_prim, selected_joints)

    # Collect the candidate tip body paths: one from each follower joint
    # plus one from the master joint. Deduplicate while preserving discovery
    # order (master first, then followers in their original order).
    candidate_paths = []
    seen = set()
    for master_path in dict.fromkeys(spec.reference_joint_path for spec in mimics):
        master_tip = _resolve_joint_child_link_from_path(stage, master_path, oriented)
        if master_tip and master_tip not in seen:
            candidate_paths.append(master_tip)
            seen.add(master_tip)
    for spec in mimics:
        tip = _resolve_joint_child_link_from_path(stage, spec.follower_joint_path, oriented)
        if tip and tip not in seen:
            candidate_paths.append(tip)
            seen.add(tip)

    # A native Newton four-bar normally authors one master plus one mimic
    # driver; its real pads are reached through passive linkage joints.  Add
    # every downstream body as a motion candidate so the runtime aperture
    # probe can select the physical pads rather than the proximal knuckles.
    child_map = _build_child_link_map(stage, asset_prim, selected_joint_paths, oriented=oriented)
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
            f"Tip body resolution failed: mimic chain produced only {len(candidate_paths)} "
            "distinct tip bodies (need >= 2). The selected joints' "
            "downstream endpoints didn't resolve to distinct rigid "
            "body. Inspect the joint relationships under the gripper "
            "subtree."
        )

    # GR.003 describes the tube axis/contact-pad width, NOT a pad-to-pad
    # maximum-opening segment. Keep a rest-pose pair only as a provisional
    # display hint. The live phase must identify pads and endpoint polarity.
    tip_paths = _pick_two_furthest_apart(stage, candidate_paths)
    if tip_paths is None:
        return (
            "Tip body world-pose resolution failed: _pick_two_furthest_apart "
            "encountered an invalid prim while computing rest-pose XYZs "
            "for the %d candidate paths." % len(candidate_paths)
        )
    candidate_branches = _candidate_branch_groups(stage, asset_prim, candidate_paths, selected_joint_paths)
    if len(set(candidate_branches.values())) < 2:
        return "Candidate fingertip bodies do not resolve to distinct physical branches."

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
        tips_from_grip_line=False,
        candidate_branches=candidate_branches,
        mimic_master_dofs=master_indices,
    )


def _candidate_branch_groups(stage, asset_prim, body_paths, selected_joint_paths=None):
    """Connected candidate bodies form one branch, without the shared palm.

    Passive/fixed/closure edges are included; grouping is cycle-safe and never
    depends on link names or GR.003 line endpoints.
    """
    from pxr import Usd, UsdPhysics

    neighbors = {path: set() for path in body_paths}
    for prim in Usd.PrimRange(asset_prim):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if selected_joint_paths is not None and str(prim.GetPath()) not in selected_joint_paths:
            continue
        first, second = _joint_bodies(stage, str(prim.GetPath()))
        if first in neighbors and second in neighbors:
            neighbors[first].add(second)
            neighbors[second].add(first)
    groups = {}
    for path in body_paths:
        if path in groups:
            continue
        group = len(set(groups.values()))
        pending = [path]
        while pending:
            current = pending.pop()
            if current in groups:
                continue
            groups[current] = group
            pending.extend(neighbors[current] - groups.keys())
    return groups


def _pick_two_furthest_apart(stage, body_paths):
    """Return the pair of body paths with the largest rest-pose XYZ distance.

    This is a provisional discovery/display hint only. It does NOT establish
    contact-pad identity or endpoint polarity; the live phase replaces it.

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


def _resolve_joint_child_link_from_path(stage, joint_path: str, oriented=None):
    """Return a selected joint's qualified downstream candidate body.

    Real selected graphs use rooted orientation, independent of authored
    endpoint order. Bounded schema-light callers retain the conventional
    body1/body0 fallback; that compatibility path does not qualify native
    ownership. Multiple forwarded endpoints remain a setup error.
    """
    if oriented is not None:
        if joint_path not in oriented:
            raise GripperTopologyError(f"FET028 mapping/setup limitation: unresolved selected joint {joint_path}")
        return oriented[joint_path][1]
    first, second = _joint_bodies(stage, joint_path)
    return second or first


def _joint_bodies(stage, joint_path: str):
    """Resolve authored ``(body0, body1)`` endpoints, or ``(None, None)``.

    Endpoint order alone does not identify physical parent and child.
    """
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
        targets = rel.GetForwardedTargets()
        if len(targets) > 1:
            raise GripperTopologyError(f"FET028 joint endpoint has multiple targets: {joint_path}")
        if not targets:
            return None
        target = stage.GetPrimAtPath(targets[0])
        while target and target.IsValid():
            if target.HasAPI(UsdPhysics.RigidBodyAPI):
                return str(target.GetPath())
            target = target.GetParent()
        # Preserve the conventional raw link path for schema-light discovery
        # callers; joint-root scopes above require real rigid-body ownership.
        return str(targets[0])

    return (_first("physics:body0"), _first("physics:body1"))


def _build_child_link_map(stage, asset_prim, selected_joint_paths=None, oriented=None):
    """Map parent bodies to children, including passive/fixed distal links.

    A supplied qualified orientation bounds traversal to selected non-closure
    edges. Schema-light compatibility uses authored body0-to-body1 order.
    """
    from pxr import Usd, UsdPhysics

    child_map = {}
    for prim in Usd.PrimRange(asset_prim):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is False:
            continue
        if selected_joint_paths is not None and str(prim.GetPath()) not in selected_joint_paths:
            continue
        if oriented is not None:
            if str(prim.GetPath()) not in oriented:
                continue
            b0, b1 = oriented[str(prim.GetPath())]
        else:
            b0, b1 = _joint_bodies(stage, str(prim.GetPath()))
        if b0 and b1:
            child_map.setdefault(b0, []).append(b1)
    return child_map


def _orient_independent_tree(stage, robot, asset_prim, joints):
    """Orient selected non-closure edges from an explicitly qualified root."""
    from pxr import Usd, UsdPhysics

    from .joint_identity import (
        JointIdentityError,
        _resolve_articulation_root_body,
        qualified_cooked_root,
    )

    endpoints = {str(prim.GetPath()): _joint_bodies(stage, str(prim.GetPath())) for prim in joints}
    bodies = {body for pair in endpoints.values() for body in pair if body}
    roots = {
        body
        for prim in Usd.PrimRange(asset_prim)
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI)
        for body in [_resolve_articulation_root_body(stage, str(prim.GetPath()), str(asset_prim.GetPath()))]
        if body in bodies
    }
    selected_root = _resolve_articulation_root_body(stage, str(robot.prim_path), str(asset_prim.GetPath()))
    if selected_root is None and str(robot.prim_path) in bodies:
        # Schema-light callers may explicitly select an endpoint as the root.
        # This uses caller identity, never authored endpoint ordering.
        selected_root = str(robot.prim_path)
    if selected_root in bodies:
        roots.add(selected_root)
    roots.update(next(body for body in pair if body) for pair in endpoints.values() if pair.count(None) == 1)
    if not roots:
        articulation = getattr(robot, "articulation", None)
        view = getattr(getattr(articulation, "_articulation_view", None), "_physics_view", None)
        rows = getattr(view, "link_paths", None)
        if isinstance(rows, (list, tuple)) and len(rows) == 1 and isinstance(rows[0], (list, tuple)):
            paths = list(map(str, rows[0]))
            # The hand needs the complete selected tree, not a rebound or
            # partial cooked row. Physical ownership remains required here.
            if (
                len(set(paths)) == len(paths)
                and set(paths) == bodies
                and all(stage.GetPrimAtPath(path).HasAPI(UsdPhysics.RigidBodyAPI) for path in paths)
            ):
                try:
                    roots.add(qualified_cooked_root(view, paths, endpoints))
                except JointIdentityError as error:
                    raise GripperTopologyError(f"FET028 mapping/setup limitation: {error}") from error
    if len(roots) != 1:
        raise GripperTopologyError(
            "FET028 mapping/setup limitation: unavailable or ambiguous physical articulation root"
        )
    root = next(iter(roots))
    adjacency = {body: [] for body in bodies}
    oriented = {}
    for path, (first, second) in endpoints.items():
        if first is None or second is None:
            oriented[path] = (None, first or second)
            continue
        adjacency[first].append((second, path))
        adjacency[second].append((first, path))
    reached, pending = {root}, [root]
    while pending:
        parent = pending.pop()
        for child, path in adjacency[parent]:
            if path in oriented:
                continue
            if child in reached:
                raise GripperTopologyError("FET028 mapping/setup limitation: ambiguous physical branch parent")
            oriented[path] = (parent, child)
            reached.add(child)
            pending.append(child)
    if reached != bodies:
        raise GripperTopologyError("FET028 mapping/setup limitation: disconnected independent physical branches")
    return oriented


def _deepest_leaf(child_map, seed, require_unique=False):
    """Follow child links forward from ``seed`` to the deepest reachable leaf.
    Returns ``(leaf_path, depth)``. Cycle-guarded."""
    best = (seed, 0)
    deepest = {seed}
    stack = [(seed, 0, {seed})]
    while stack:
        node, d, ancestors = stack.pop()
        kids = [c for c in child_map.get(node, []) if c and c not in ancestors]
        if require_unique and any(child in ancestors for child in child_map.get(node, [])):
            raise GripperTopologyError("FET028 mapping/setup limitation: cyclic independent physical branch")
        if not kids and d > best[1]:
            best = (node, d)
            deepest = {node}
        elif not kids and d == best[1]:
            deepest.add(node)
        for c in kids:
            stack.append((c, d + 1, ancestors | {c}))
    if require_unique and len(deepest) != 1:
        raise GripperTopologyError("FET028 mapping/setup limitation: ambiguous distal independent-finger tips")
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


def _distal_tip_of_finger(joints, child_map, require_unique=False):
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
    deepest = set()
    for _p, _b0, b1, _n in joints:
        if not b1:
            continue
        leaf, depth = _deepest_leaf(child_map, b1, require_unique=require_unique)
        if depth > best_depth:
            best_leaf, best_depth = leaf, depth
            deepest = {leaf}
        elif depth == best_depth:
            deepest.add(leaf)
    if require_unique and len(deepest) > 1:
        raise GripperTopologyError("FET028 mapping/setup limitation: ambiguous distal independent-finger tips")
    return best_leaf


def _joint_has_drive(prim):
    """Effective positive stiffness or damping owns control; API presence does not."""
    from .passive_joints import _joint_is_passive

    return not _joint_is_passive(prim)


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


def _classify_independent_fingers(
    stage, robot, gripper_site, analysis_root=None, ignored_joint_paths=(), selected_joint_paths=None, mimics=()
):
    """Multi-finger hand with independent leaders and optional local followers.

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
    selected_joints = [
        prim
        for prim in Usd.PrimRange(asset_prim)
        if prim.IsA(UsdPhysics.Joint)
        and (selected_joint_paths is None or str(prim.GetPath()) in selected_joint_paths)
        and UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is not False
        and not UsdPhysics.Joint(prim).GetExcludeFromArticulationAttr().Get()
    ]
    indices_by_path = _selected_native_indices(selected_joints, robot.dof_names)
    ignored_paths = {str(path) for path in ignored_joint_paths}
    # Newton runtime layers normally remove PhysicsDriveAPI and express each
    # independently controlled finger with a NewtonActuator. Treat those
    # actuator targets exactly like driven joints for topology discovery.
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        _actuator_target_paths,
    )

    actuator_target_paths = _actuator_target_paths(stage, search_root)
    followers = {spec.follower_joint_path: spec.reference_joint_path for spec in mimics}
    independent = [
        prim
        for prim in selected_joints
        if (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint))
        and str(prim.GetPath()) not in ignored_paths | set(followers)
        and (_joint_has_drive(prim) or str(prim.GetPath()) in actuator_target_paths)
    ]
    if len(independent) < 2:
        return None
    oriented = _orient_independent_tree(stage, robot, asset_prim, selected_joints)

    parent_map = {}
    records = []
    for prim in Usd.PrimRange(asset_prim):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if selected_joint_paths is not None and str(prim.GetPath()) not in selected_joint_paths:
            continue
        joint = UsdPhysics.Joint(prim)
        if joint.GetJointEnabledAttr().Get() is False:
            continue
        if joint.GetExcludeFromArticulationAttr().Get():
            # Maximal-coordinate closure edges still contribute bounded geometry
            # below, but their basenames cannot identify live articulation DOFs.
            continue
        b0, b1 = oriented[str(prim.GetPath())]
        if b0 and b1:
            if b1 in parent_map and parent_map[b1] != b0:
                raise GripperTopologyError("FET028 mapping/setup limitation: ambiguous physical branch parent")
            parent_map[b1] = b0
        if not (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)):
            continue
        if not _joint_has_drive(prim) and str(prim.GetPath()) not in actuator_target_paths:
            continue
        if str(prim.GetPath()) in ignored_paths:
            continue
        if str(prim.GetPath()) in followers:
            continue
        indices = indices_by_path.get(str(prim.GetPath()), [])
        if len(indices) != 1:
            raise GripperTopologyError(
                "FET028 mapping/setup limitation: unresolved or ambiguous independent drive identity"
            )
        idx = indices[0]
        jname = robot.dof_names[idx]
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
    child_map = _build_child_link_map(stage, asset_prim, selected_joint_paths, oriented=oriented)
    if followers:
        # Each dependent joint must remain in the physical branch of its
        # ultimate independent leader. Cross-finger couplings cannot use this
        # per-branch hand contract.
        branch_by_joint = {record["path"]: branch for branch, group in branches.items() for record in group}
        reachable = {
            branch: {
                body
                for record in group
                for body in [record["body1"], *_reachable_descendants(child_map, record["body1"])]
                if body
            }
            for branch, group in branches.items()
        }
        owners = {}
        for branch, bodies in reachable.items():
            for body in bodies:
                if body in owners and owners[body] != branch:
                    raise GripperTopologyError(
                        "FET028 mapping/setup limitation: overlapping independent physical branches"
                    )
                owners[body] = branch
        for follower in followers:
            leader = followers[follower]
            while leader in followers:
                leader = followers[leader]
            branch = branch_by_joint.get(leader)
            child = oriented[follower][1]
            if branch is None or child not in reachable[branch]:
                raise GripperTopologyError(
                    "FET028 mapping/setup limitation: active mimic topology crosses independent branches"
                )
    distal_tip = {}
    for f in fingers:
        joints = [(record["path"], record["body0"], record["body1"], record["name"].lower()) for record in branches[f]]
        tip = _distal_tip_of_finger(joints, child_map, require_unique=True)
        if tip is not None and not stage.GetPrimAtPath(tip):
            raise GripperTopologyError("FET028 mapping/setup limitation: missing independent-finger tip body")
        if tip is not None:
            distal_tip[f] = tip
    tip_paths = _distinct_resolved_tip_paths(fingers, distal_tip)
    if tip_paths is None:
        return None
    if len(tip_paths) != len(fingers) or len(set(tip_paths)) != len(fingers):
        raise GripperTopologyError("FET028 mapping/setup limitation: incomplete or shared independent-finger tips")

    return FingertipSet(
        kind="independent_fingers",
        tip_link_paths=tip_paths,
        mimic_master_dof=None,
        mimic_follower_dof=None,
        finger_chains=finger_chains,
        reason=("independent_fingers: %d actuated DOFs across %d graph branches" % (len(records), len(fingers))),
    )

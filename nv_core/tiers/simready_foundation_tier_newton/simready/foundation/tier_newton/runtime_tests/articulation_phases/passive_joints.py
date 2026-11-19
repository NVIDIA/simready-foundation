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
"""Detect passive (undriven) joints that the per-joint motion tests must skip.

A joint is 'passive' when it has no active drive on either axis -- that is,
neither the linear nor the angular drive has a positive effective stiffness OR
damping. A stiffness-only check misses velocity (damping-only) drives and would
wrongly exclude a driven joint from the velocity (DJ.005) and effort (DJ.006)
tests, so both gains are considered, using the resolved (effective) value.

FET_022_NEWTON also permits joints to be driven by either a direct
``NewtonActuator`` or an ``MjcActuator`` targeting a fixed ``MjcTendon``. Those
targets are active even when the joints intentionally have no
``PhysicsDriveAPI``.
"""

_NEWTON_ACTUATOR_TYPE = "NewtonActuator"
_NEWTON_TARGETS_REL = "newton:targets"
_MJC_ACTUATOR_TYPE = "MjcActuator"
_MJC_TENDON_TYPE = "MjcTendon"
_MJC_TARGET_REL = "mjc:target"
_MJC_PATH_REL = "mjc:path"


def _read_drive_gain(joint_prim, drive_name, attr_name):
    # type: (Any, str, str) -> float
    """Read the effective stiffness or damping of DriveAPI(drive_name); 0.0 when unset.

    Uses the resolved value (``Get()``). The schema fallback for both gains is
    0.0, so an unauthored or unapplied drive reads as 0.0 (passive), while an
    authored value (or a non-zero default) is honoured -- this is the effective
    gain compiled into the Newton simulation, not merely whether a value was explicitly authored.
    """
    import math
    from numbers import Real

    from pxr import UsdPhysics
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
        RequiredReadbackError,
    )

    try:
        api = UsdPhysics.DriveAPI(joint_prim, drive_name)
        if not api:
            return 0.0
        attr = getattr(api, attr_name)()
        if not attr:
            raise ValueError("applied drive gain attribute is unavailable")
        value = attr.Get()
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid effective drive gain: {value!r}")
        return float(value)
    except Exception as error:
        raise RequiredReadbackError(
            f"Required drive gain readback failed for {joint_prim.GetPath()} {drive_name}.{attr_name}: {error}"
        ) from error


def _joint_is_passive(joint_prim, actuator_target_paths=frozenset(), newton_adds_mobility=False):
    # type: (Any, FrozenSet[str]) -> bool
    """Return True when the joint has no active drive (no positive stiffness or
    damping) on either the linear or the angular axis."""
    if newton_adds_mobility or str(joint_prim.GetPath()) in actuator_target_paths:
        return False
    for drive_name in ("linear", "angular"):
        if _read_drive_gain(joint_prim, drive_name, "GetStiffnessAttr") > 0.0:
            return False
        if _read_drive_gain(joint_prim, drive_name, "GetDampingAttr") > 0.0:
            return False
    return True


def _actuator_source_targets(prim, name, *, strict_sources=False):
    """Read the detector's actual relationship source without inventing absence."""
    relationship = prim.GetRelationship(name)
    if not relationship:
        if strict_sources:
            raise RuntimeError(f"Required actuator relationship is unavailable: {prim.GetPath()}.{name}")
        return []
    targets = relationship.GetTargets()
    if strict_sources:
        if not targets:
            raise RuntimeError(f"Required actuator targets are unavailable: {relationship.GetPath()}")
        stage = prim.GetStage()
        for path in targets:
            if not path.IsAbsolutePath() or not path.IsPrimPath():
                raise RuntimeError(f"Required actuator target is not an absolute prim path: {path}")
            target = stage.GetPrimAtPath(path)
            if (
                not target
                or not target.IsValid()
                or not target.IsActive()
                or not target.IsDefined()
                or target.IsAbstract()
                or not target.IsLoaded()
                or not stage.GetPopulationMask().IncludesSubtree(path)
            ):
                raise RuntimeError(f"Required actuator target is unavailable: {path}")
    return targets


def _actuator_target_paths(stage, root_path, *, strict_sources=False):
    # type: (Any, str) -> FrozenSet[str]
    """Return joint paths controlled by supported Newton actuator contracts.

    Strict source reads qualify markers; default reads retain legacy eligibility.
    """
    if stage is None or not root_path:
        if strict_sources:
            raise RuntimeError("Required actuator discovery stage/root is unavailable")
        return frozenset()
    try:
        from pxr import Usd, UsdPhysics

        root = stage.GetPrimAtPath(root_path)
        if not root or not root.IsValid():
            if strict_sources:
                raise RuntimeError("Required actuator discovery root is unavailable")
            return frozenset()
        targets = set()
        tendons = {}
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            type_name = prim.GetTypeName()
            if type_name == _NEWTON_ACTUATOR_TYPE:
                targets.update(
                    str(path)
                    for path in _actuator_source_targets(prim, _NEWTON_TARGETS_REL, strict_sources=strict_sources)
                )
            elif type_name == _MJC_TENDON_TYPE:
                tendons[str(prim.GetPath())] = {
                    str(path) for path in _actuator_source_targets(prim, _MJC_PATH_REL, strict_sources=strict_sources)
                }
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            if prim.GetTypeName() != _MJC_ACTUATOR_TYPE:
                continue
            for path in _actuator_source_targets(prim, _MJC_TARGET_REL, strict_sources=strict_sources):
                path_string = str(path)
                if path_string in tendons:
                    targets.update(tendons[path_string])
                else:
                    target_prim = stage.GetPrimAtPath(path)
                    if target_prim and target_prim.IsA(UsdPhysics.Joint):
                        targets.add(path_string)
                    elif strict_sources:
                        raise RuntimeError(f"Required actuator target is not a supported joint or tendon: {path}")
        return frozenset(targets)
    except Exception:
        if strict_sources:
            raise
        return frozenset()


def detect_passive_joints(stage, robot_root_path, dof_names, asset_prim=None, *, strict_sources=False):
    """Return (indices, names) of DOFs whose matching joint is passive.

    Marker proof opts into strict_sources to propagate unavailable required
    sources. The default preserves the detector's existing eligibility policy.

    Indices are positions in dof_names. Names is the subset of dof_names
    found to be passive, in list order. When supplied, the verified loaded
    asset subtree supplies joints/actuators even if the articulation root is
    a leaf fixed joint. Root mobility policy still comes from the actual
    articulation root; room/probe content outside the asset is not scanned.
    """
    if not dof_names:
        return (frozenset(), [])
    from .joint_identity import (
        JointIdentityError,
        joint_for_native_name,
        selected_joint_prims,
    )

    joints = selected_joint_prims(stage, robot_root_path, dof_names, asset_prim)
    if not joints:
        if strict_sources:
            raise RuntimeError("Required passive ownership has no selected joint inventory")
        return (frozenset(), [])
    scan_path = str(asset_prim.GetPath()) if asset_prim is not None else robot_root_path
    source_options = {"strict_sources": True} if strict_sources else {}
    actuator_target_paths = _actuator_target_paths(stage, scan_path, **source_options)
    root_prim = stage.GetPrimAtPath(robot_root_path)
    if strict_sources and (not root_prim or not root_prim.IsValid()):
        raise RuntimeError("Required mobility source root is unavailable")
    mobility_attr = root_prim.GetAttribute("newton:jointsAddMobility") if root_prim else None
    mobility_value = mobility_attr.Get() if mobility_attr else False
    if strict_sources and not isinstance(mobility_value, bool):
        raise RuntimeError("Required authored mobility source is unavailable or not boolean")
    newton_adds_mobility = bool(mobility_value)
    passive_indices, passive_names = [], []
    for index, name in enumerate(dof_names):
        joint = joint_for_native_name(joints, name)
        if joint is None:
            raise JointIdentityError(f"Passive ownership has no unique selected joint for native coordinate {name!r}")
        if _joint_is_passive(joint, actuator_target_paths, newton_adds_mobility):
            passive_indices.append(index)
            passive_names.append(name)
    return (frozenset(passive_indices), passive_names)

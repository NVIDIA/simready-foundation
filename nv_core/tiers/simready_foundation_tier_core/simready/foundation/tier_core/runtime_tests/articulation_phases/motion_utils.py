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
"""USD max-velocity resolution and DOF-property helpers.

Ported from v1 shared_phases/motion_utils.py.
"""

import math

import numpy as np


def smoothstep(t):
    # type: (float) -> float
    """Smoothstep ease for trajectory pacing: 0 at t<=0, 1 at t>=1, smooth between.

    Used to drive joints like a real robot trajectory -- a stream of intermediate
    position setpoints ramped from start to goal -- instead of a single far-target
    step command. A step command makes the PD drive accelerate hard toward the
    goal; on an uncapped (no authored velocity limit) joint that whips the joint
    and can destabilize the solver. This helper only interpolates setpoints;
    it does not establish physical stability or speed/acceleration enforcement.
    """
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def get_dof_property(dof_properties, key):
    # type: (Any, str) -> Optional[np.ndarray]
    """Extract a named column from SingleArticulation dof_properties."""
    if dof_properties is None:
        return None
    try:
        names = getattr(dof_properties.dtype, "names", None)
        if names and key in names:
            return np.array(dof_properties[key])
    except Exception:
        pass
    try:
        values = []
        for entry in dof_properties:
            if isinstance(entry, dict) and key in entry:
                values.append(float(entry[key]))
            else:
                return None
        return np.array(values) if values else None
    except Exception:
        return None


def get_limits(lowers, uppers, idx):
    # type: (Any, Any, int) -> tuple[Optional[float], Optional[float]]
    """Return (lower, upper) floats at idx, or (None, None) when unavailable."""
    if lowers is None or uppers is None:
        return (None, None)
    try:
        if idx < 0 or idx >= len(lowers) or idx >= len(uppers):
            return (None, None)
        return (float(lowers[idx]), float(uppers[idx]))
    except Exception:
        return (None, None)


def merge_velocity_limits(dof_vels, usd_vels, use_min_when_both=True):
    # type: (Optional[np.ndarray], Optional[np.ndarray], bool) -> Optional[np.ndarray]
    """Merge DOF-reported and USD-authored max velocities per joint."""
    if dof_vels is None and usd_vels is None:
        return None

    length = 0
    if dof_vels is not None:
        length = max(length, len(dof_vels))
    if usd_vels is not None:
        length = max(length, len(usd_vels))

    out = np.full(length, np.nan, dtype=np.float64)
    for i in range(length):
        d = float(dof_vels[i]) if (dof_vels is not None and i < len(dof_vels)) else float("nan")
        u = float(usd_vels[i]) if (usd_vels is not None and i < len(usd_vels)) else float("nan")
        d_ok = math.isfinite(d) and d > 0
        u_ok = math.isfinite(u) and u > 0
        if d_ok and u_ok:
            out[i] = min(d, u) if use_min_when_both else d
        elif d_ok:
            out[i] = d
        elif u_ok:
            out[i] = u
    return out


def _iter_joint_prims(stage, robot_prim_path, asset_prim, robot_root_prim, qualified=False):
    # type: (Any, str, Any, Any) -> list[Any]
    """Collect joint prims under the robot root, preferring a 'joints' scope when present."""
    from pxr import Usd, UsdPhysics

    roots = []
    for candidate in (asset_prim, robot_root_prim):
        if candidate is not None and candidate.IsValid():
            roots.append(candidate)
    if not roots and robot_prim_path:
        prim = stage.GetPrimAtPath(robot_prim_path)
        if prim and prim.IsValid():
            roots.append(prim)

    joints = []
    for root in roots:
        joints_scope = root.GetChild("joints") if root else None
        traverse_root = joints_scope if not qualified and joints_scope and joints_scope.IsValid() else root
        traversal = (
            Usd.PrimRange(traverse_root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
            if qualified
            else Usd.PrimRange(traverse_root)
        )
        for prim in traversal:
            if prim.IsA(UsdPhysics.Joint):
                joints.append(prim)
    seen = set()
    unique = []
    for j in joints:
        p = str(j.GetPath())
        if p in seen:
            continue
        seen.add(p)
        unique.append(j)
    return unique


def _read_joint_max_velocity(joint_prim, actuator_deg_to_rad=True, reject_unlimited=False):
    # type: (Any, bool) -> Optional[float]
    """Read the existing authored comparison input, or None if unavailable.

    Angular USD degrees/s convert to radians/s. Linear authored values remain
    stage-distance/s; Core's native prismatic tensor scale is not qualified,
    so this legacy comparison input does not prove matching meters/s.

    Supports BOTH authoring forms:
      1. ``physxJoint:maxJointVelocity`` (PhysxJointAPI) -- legacy form.
      2. ``physxDrivePerformanceEnvelope:{angular,linear}:maxActuatorVelocity``
         (PhysxDrivePerformanceEnvelopeAPI) -- the modern form UR-style arms
         (e.g. ur10) use.

    UNITS (authoritative, PhysX/USD schema docs): USD authors BOTH forms in
    *degrees/second* for angular (revolute) joints and *distance/second* for
    linear (prismatic) joints, while the runtime joint-velocity tensor reports
    *radians/second* for revolute. So for a revolute joint we convert the
    authored value deg/s -> rad/s (gated by ``actuator_deg_to_rad``); for a
    prismatic joint no conversion is applied; native scale remains unqualified.

    Unavailable optional schema support and absent or unusable values yield
    no hint. Queries of supported selected properties remain required reads:
    failures propagate unchanged, with the qualified property path noted
    best-effort. Legacy Form (1) takes precedence over Form (2).
    """
    from pxr import UsdPhysics

    from .error_utils import note_secondary_error

    is_angular = bool(joint_prim.IsA(UsdPhysics.RevoluteJoint))
    if reject_unlimited and not (is_angular or joint_prim.IsA(UsdPhysics.PrismaticJoint)):
        return None

    def _to_runtime_units(value):
        # type: (float) -> float
        if is_angular and actuator_deg_to_rad:
            return value * math.pi / 180.0  # deg/s -> rad/s for revolute
        return value

    def _usable_input(value):
        if reject_unlimited:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
                usable_velocity,
            )

            return usable_velocity(value) is not None
        return value is not None and math.isfinite(float(value)) and float(value) > 0

    # Form 1: legacy PhysxJointAPI.maxJointVelocity.
    try:
        try:
            from pxr import PhysxSchema
        except ImportError:
            from physx_usd_schemas import PhysxSchema

    except ImportError:
        PhysxSchema = None

    if PhysxSchema is not None:
        property_path = str(joint_prim.GetPath()) + ".physxJoint:maxJointVelocity"
        try:
            physx = PhysxSchema.PhysxJointAPI.Get(joint_prim.GetStage(), joint_prim.GetPath())
            attr = physx.GetMaxJointVelocityAttr() if physx else None
            val = attr.Get() if attr and attr.HasAuthoredValue() else None
        except BaseException as primary:
            note_secondary_error(primary, lambda path=property_path: "Required authored velocity read failed: " + path)
            raise
        try:
            if _usable_input(val):
                return _to_runtime_units(float(val))
        except (TypeError, ValueError, OverflowError):
            pass  # An unusable legacy value retains the envelope fallback.

    # Form 2: PhysxDrivePerformanceEnvelopeAPI.maxActuatorVelocity. Read the
    # instance matching the joint's DOF ("angular" for revolute, "linear" for
    # prismatic); fall back to whichever instance is authored.
    instances = ("angular", "linear") if is_angular else ("linear", "angular")
    if reject_unlimited:
        instances = instances[:1]
    for dof in instances:
        property_name = "physxDrivePerformanceEnvelope:%s:maxActuatorVelocity" % dof
        property_path = str(joint_prim.GetPath()) + "." + property_name
        try:
            attr = joint_prim.GetAttribute(property_name)
            val = attr.Get() if attr and attr.HasAuthoredValue() else None
        except BaseException as primary:
            note_secondary_error(primary, lambda path=property_path: "Required authored velocity read failed: " + path)
            raise
        try:
            if _usable_input(val):
                return _to_runtime_units(float(val))
        except (TypeError, ValueError, OverflowError):
            return None  # Preserve Form2's existing conversion-failure boundary.
    return None


def resolve_usd_max_velocities(
    stage,
    robot_prim_path,
    dof_names,
    asset_prim,
    robot_root_prim,
    use_min_when_both=True,
    actuator_deg_to_rad=True,
    reject_unlimited=False,
):
    # type: (Any, str, list[str], Any, Any, bool, bool) -> Optional[np.ndarray]
    """Resolve selected physical-joint ceilings in native DOF order.

    Qualified joint identity admits unique names, paths and native axis aliases
    while excluding foreign articulation shadows. Returns float64 values with
    NaN for absent/unusable hints, or None when no selected joints are found.
    Supported authored-property query failures propagate, never becoming NaN.
    VEL opts into rejecting raw SDK unlimited sentinels before angular unit
    conversion; other callers retain their existing comparison-input policy.
    """
    if stage is None or not dof_names:
        return None

    from .joint_identity import joint_for_native_name, selected_joint_prims

    joint_prims = selected_joint_prims(stage, robot_prim_path, dof_names, asset_prim)
    if not joint_prims:
        return None
    out = np.full(len(dof_names), np.nan, dtype=np.float64)
    for index, name in enumerate(dof_names):
        joint = joint_for_native_name(joint_prims, name)
        if joint is None:
            continue
        velocity = _read_joint_max_velocity(
            joint, actuator_deg_to_rad=actuator_deg_to_rad, reject_unlimited=reject_unlimited
        )
        if velocity is not None and math.isfinite(velocity) and velocity > 0:
            out[index] = velocity
    return out

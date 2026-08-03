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
    and can destabilize the solver. Ramping the commanded target keeps motion
    physical and stable regardless of whether a velocity limit is enforced.
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
    # type: (Any, Any, int) -> Tuple[Optional[float], Optional[float]]
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


def _iter_joint_prims(stage, robot_prim_path, asset_prim, robot_root_prim):
    # type: (Any, str, Any, Any) -> List[Any]
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
        traverse_root = joints_scope if joints_scope and joints_scope.IsValid() else root
        for prim in Usd.PrimRange(traverse_root):
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


def _read_joint_max_velocity(joint_prim, actuator_deg_to_rad=True):
    # type: (Any, bool) -> Optional[float]
    """Read the authored max velocity for a joint, returned in the SAME units
    the runtime tensor API reports (rad/s for revolute, m/s for prismatic), or
    None if unauthored.

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
    prismatic joint the units already match and no conversion is applied.

    Two bugs previously lived here:
      - Form (2) was never read, so robots authoring only the drive performance
        envelope reported NO velocity limit and the test silently skipped.
      - Form (1) was read raw with no deg->rad conversion, so when the
        articulation tensor did not independently carry the limit the ceiling
        was ~57x too high and the test trivially "passed".
    """
    from pxr import UsdPhysics

    is_angular = bool(joint_prim.IsA(UsdPhysics.RevoluteJoint))

    def _to_runtime_units(value):
        # type: (float) -> float
        if is_angular and actuator_deg_to_rad:
            return value * math.pi / 180.0  # deg/s -> rad/s for revolute
        return value

    # Form 1: legacy PhysxJointAPI.maxJointVelocity.
    try:
        from pxr import PhysxSchema

        physx = PhysxSchema.PhysxJointAPI.Get(joint_prim.GetStage(), joint_prim.GetPath())
        if physx:
            attr = physx.GetMaxJointVelocityAttr()
            if attr and attr.HasAuthoredValue():
                val = attr.Get()
                if val is not None and math.isfinite(float(val)) and float(val) > 0:
                    return _to_runtime_units(float(val))
    except Exception:
        pass

    # Form 2: PhysxDrivePerformanceEnvelopeAPI.maxActuatorVelocity. Read the
    # instance matching the joint's DOF ("angular" for revolute, "linear" for
    # prismatic); fall back to whichever instance is authored.
    try:
        instances = ("angular", "linear") if is_angular else ("linear", "angular")
        for dof in instances:
            a = joint_prim.GetAttribute("physxDrivePerformanceEnvelope:%s:maxActuatorVelocity" % dof)
            if a and a.HasAuthoredValue():
                v = a.Get()
                if v is not None and math.isfinite(float(v)) and float(v) > 0:
                    return _to_runtime_units(float(v))
    except Exception:
        pass
    return None


def resolve_usd_max_velocities(
    stage,
    robot_prim_path,
    dof_names,
    asset_prim,
    robot_root_prim,
    use_min_when_both=True,
    actuator_deg_to_rad=True,
):
    # type: (Any, str, List[str], Any, Any, bool, bool) -> Optional[np.ndarray]
    """Resolve USD-authored max velocity per DOF name. NaN where unauthored.

    Strategy: iterate joint prims under the robot root, read PhysxJointAPI.maxJointVelocity,
    match by prim basename against dof_names. Returns a float64 array of length len(dof_names),
    or None when no joints were found at all.
    """
    if stage is None or not dof_names:
        return None

    joint_prims = _iter_joint_prims(stage, robot_prim_path, asset_prim, robot_root_prim)
    if not joint_prims:
        return None

    name_to_vel = {}
    for joint in joint_prims:
        name = joint.GetName()
        vel = _read_joint_max_velocity(joint, actuator_deg_to_rad=actuator_deg_to_rad)
        if vel is not None and math.isfinite(vel) and vel > 0:
            name_to_vel[name] = vel

    if not name_to_vel:
        return np.full(len(dof_names), np.nan, dtype=np.float64)

    out = np.full(len(dof_names), np.nan, dtype=np.float64)
    for i, dof_name in enumerate(dof_names):
        if dof_name in name_to_vel:
            out[i] = name_to_vel[dof_name]
    return out

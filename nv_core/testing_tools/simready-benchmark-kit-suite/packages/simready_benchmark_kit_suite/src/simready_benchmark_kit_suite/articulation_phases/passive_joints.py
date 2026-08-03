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
"""


def _read_drive_gain(joint_prim, drive_name, attr_name):
    # type: (Any, str, str) -> float
    """Read the effective stiffness or damping of DriveAPI(drive_name); 0.0 when unset.

    Uses the resolved value (``Get()``). The schema fallback for both gains is
    0.0, so an unauthored or unapplied drive reads as 0.0 (passive), while an
    authored value (or a non-zero default) is honoured -- this is the effective
    gain PhysX simulates, not merely whether a value was explicitly authored.
    """
    try:
        from pxr import UsdPhysics

        api = UsdPhysics.DriveAPI(joint_prim, drive_name)
        if api:
            attr = getattr(api, attr_name)()
            if attr:
                val = attr.Get()
                if val is not None:
                    return float(val)
    except Exception:
        pass
    return 0.0


def _joint_is_passive(joint_prim):
    # type: (Any) -> bool
    """Return True when the joint has no active drive (no positive stiffness or
    damping) on either the linear or the angular axis."""
    for drive_name in ("linear", "angular"):
        if _read_drive_gain(joint_prim, drive_name, "GetStiffnessAttr") > 0.0:
            return False
        if _read_drive_gain(joint_prim, drive_name, "GetDampingAttr") > 0.0:
            return False
    return True


def _iter_joints_under(stage, root_path):
    # type: (Any, str) -> List[Any]
    if stage is None or not root_path:
        return []
    try:
        from pxr import Usd, UsdPhysics

        root = stage.GetPrimAtPath(root_path)
        if not root or not root.IsValid():
            return []
        joints = []
        for prim in Usd.PrimRange(root):
            if prim.IsA(UsdPhysics.Joint):
                joints.append(prim)
        return joints
    except Exception:
        return []


def detect_passive_joints(stage, robot_root_path, dof_names):
    # type: (Any, str, List[str]) -> Tuple[FrozenSet[int], List[str]]
    """Return (indices, names) of DOFs whose matching joint is passive.

    Indices are positions in dof_names. Names is the subset of dof_names
    found to be passive, in list order.
    """
    if not dof_names:
        return (frozenset(), [])
    joints = _iter_joints_under(stage, robot_root_path)
    if not joints:
        return (frozenset(), [])
    name_to_passive = {}
    for joint in joints:
        name_to_passive[joint.GetName()] = _joint_is_passive(joint)

    passive_indices = []
    passive_names = []
    for i, dof_name in enumerate(dof_names):
        if name_to_passive.get(dof_name, False):
            passive_indices.append(i)
            passive_names.append(dof_name)
    return (frozenset(passive_indices), passive_names)

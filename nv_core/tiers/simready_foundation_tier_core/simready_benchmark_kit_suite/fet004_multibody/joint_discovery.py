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
"""Joint enumeration, force calculation, and position utilities for FET004.

Discovers all movable joints in a USD asset, reads drive parameters,
and computes the test force for each joint.
"""
import math
import re

from simready_benchmark_kit_suite.fet004_multibody.joint_checks import is_movable_joint


def compute_test_force(max_force, multiplier, default, cap):
    # type: (Optional[float], float, float, float) -> float
    """Compute the force to apply for a joint movement test.

    If the joint has a drive with max_force > 0, apply multiplier * max_force.
    Otherwise use the default force. Result is capped to prevent simulation blow-up.
    """
    if max_force is not None and max_force > 0:
        force = max_force * multiplier
    else:
        force = default
    if math.isinf(force) or math.isnan(force) or force > cap:
        force = cap
    return force


def sanitize_metric_name(name):
    # type: (str) -> str
    """Replace non-alphanumeric chars (except underscore) with underscore."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _get_drive_max_force(prim):
    # type: (Any) -> Optional[float]
    """Read max_force from UsdPhysics.DriveAPI on a joint prim.

    Checks all possible drive axes. Returns the first positive value found,
    or None if no drive is configured.
    """
    try:
        from pxr import UsdPhysics
    except ImportError:
        return None

    axes = ("angular", "linear", "rotX", "rotY", "rotZ", "transX", "transY", "transZ")
    for axis in axes:
        try:
            api = UsdPhysics.DriveAPI(prim, axis)
            if api:
                attr = api.GetMaxForceAttr()
                if attr.IsDefined():
                    val = attr.Get()
                    if val is not None and val > 0:
                        return float(val)
        except Exception:
            continue
    return None


def _find_rigid_body_path(stage, start_path):
    # type: (Any, str) -> Optional[str]
    """Walk from start_path up to the root to find the nearest prim with RigidBodyAPI.

    Joint body relationships sometimes target a mesh child rather than the
    rigid body parent.  PhysX apply_force_at_pos requires the prim that
    owns the RigidBodyAPI.
    """
    try:
        from pxr import UsdPhysics

        prim = stage.GetPrimAtPath(start_path)
        while prim and prim.IsValid():
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                return str(prim.GetPath())
            prim = prim.GetParent()
            if prim and str(prim.GetPath()) == "/":
                break
    except Exception:
        pass
    return None


def _find_body_path(joint_prim, rel_name, stage=None):
    # type: (Any, str, Any) -> Optional[str]
    """Resolve a body relationship (body0 or body1) on a joint prim.

    If stage is provided, walks up from the target to find the nearest
    ancestor with RigidBodyAPI (the actual rigid body, not a mesh child).
    """
    try:
        from pxr import UsdPhysics

        joint_api = UsdPhysics.Joint(joint_prim)
        if rel_name == "body0":
            rel = joint_api.GetBody0Rel()
        else:
            rel = joint_api.GetBody1Rel()
        targets = rel.GetTargets()
        if targets:
            raw_path = str(targets[0])
            # Try to resolve to the actual rigid body prim
            if stage is not None:
                rb_path = _find_rigid_body_path(stage, raw_path)
                if rb_path is not None:
                    return rb_path
            return raw_path
    except Exception:
        pass
    return None


def _get_joint_axis(prim):
    # type: (Any) -> str
    """Read the joint axis attribute. Returns 'X', 'Y', or 'Z' (default Z)."""
    try:
        attr = prim.GetAttribute("physics:axis")
        if attr and attr.IsDefined():
            val = attr.Get()
            if val in ("X", "Y", "Z"):
                return val
    except Exception:
        pass
    return "Z"


def discover_joints(stage, asset_root_path):
    # type: (Any, str) -> List[Dict[str, Any]]
    """Discover all movable joints under the asset root.

    Returns a list of dicts, one per joint:
        name:             prim name (for display/metrics)
        prim_path:        USD path of the joint prim
        type_name:        USD type name (PhysicsRevoluteJoint, etc.)
        axis:             joint axis ('X', 'Y', or 'Z')
        child_body_path:  path of body1 (child) -- where force is applied
        parent_body_path: path of body0 (parent) -- reference for relative motion
        max_force:        drive max_force (float or None for passive joints)
        test_force:       will be filled by caller
    """
    try:
        from pxr import Usd
    except ImportError:
        return []

    root_prim = stage.GetPrimAtPath(asset_root_path)
    if not root_prim or not root_prim.IsValid():
        return []

    joints = []  # type: List[Dict[str, Any]]
    for prim in Usd.PrimRange(root_prim):
        if not is_movable_joint(prim):
            continue
        type_name = prim.GetTypeName()

        child_path = _find_body_path(prim, "body1", stage)
        parent_path = _find_body_path(prim, "body0", stage)
        if not child_path:
            continue  # need a child body to apply force on

        joints.append(
            {
                "name": prim.GetName(),
                "prim_path": str(prim.GetPath()),
                "type_name": type_name,
                "axis": _get_joint_axis(prim),
                "child_body_path": child_path,
                "parent_body_path": parent_path,
                "max_force": _get_drive_max_force(prim),
                "test_force": 0.0,
            }
        )

    return joints

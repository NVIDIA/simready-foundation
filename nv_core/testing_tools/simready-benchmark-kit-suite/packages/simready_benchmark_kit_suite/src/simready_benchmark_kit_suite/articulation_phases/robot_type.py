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
"""Robot type detection, phase applicability, and scene defaults.

Ported from v1 nv_core/testing_tools/test_definitions/isaac_sim/test_infra/robot_type.py.
"""
from enum import Enum, auto


class RobotType(Enum):
    ARM = auto()
    GRIPPER = auto()
    MOBILE_BASE = auto()
    LEGGED = auto()
    HUMANOID = auto()
    SCARA = auto()
    COMPOSITE = auto()


_USD_TOKEN_TO_ROBOT_TYPE = {
    "arm": RobotType.ARM,
    "manipulator": RobotType.ARM,
    "gripper": RobotType.GRIPPER,
    "end_effector": RobotType.GRIPPER,
    "end-effector": RobotType.GRIPPER,
    "mobile_base": RobotType.MOBILE_BASE,
    "mobile-base": RobotType.MOBILE_BASE,
    "wheeled": RobotType.MOBILE_BASE,
    "legged": RobotType.LEGGED,
    "quadruped": RobotType.LEGGED,
    "humanoid": RobotType.HUMANOID,
    "scara": RobotType.SCARA,
    "composite": RobotType.COMPOSITE,
}  # type: Dict[str, RobotType]


# Scene defaults per robot type.
#
# Gravity is ON for every robot type: assets run under gravity exactly as they
# would in Isaac Sim, so weak drives, missing limits, and other real defects
# surface instead of being hidden by a zero-gravity test rig. (Earlier the
# framework disabled gravity for ARM / SCARA and then injected a hard velocity
# cap to tame the resulting un-damped overshoot; both heuristics have been
# removed -- gravity provides the damping.)
#
# ``activate_ground_plane`` remains per-type: it is a test-rig framing choice,
# not a spec behavior. ARM / SCARA hide the floor because their joints sweep
# below the mounted base and would otherwise collide with a surface they are
# not meant to touch (a rig artifact, not a real asset defect).
SCENE_DEFAULTS = {
    RobotType.ARM: {"activate_ground_plane": False},
    RobotType.GRIPPER: {"activate_ground_plane": True},
    RobotType.MOBILE_BASE: {"activate_ground_plane": True},
    RobotType.LEGGED: {"activate_ground_plane": True},
    RobotType.HUMANOID: {"activate_ground_plane": True},
    RobotType.SCARA: {"activate_ground_plane": False},
}  # type: Dict[RobotType, Dict[str, Any]]


def read_robot_type(stage, asset_prim):
    # type: (Any, Any) -> RobotType
    """Return RobotType from the 'isaac:robotType' attribute on asset_prim or children."""
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return RobotType.ARM

    candidates = [asset_prim]
    try:
        candidates.extend(list(asset_prim.GetChildren()))
    except Exception:
        pass

    for prim in candidates:
        try:
            attr = prim.GetAttribute("isaac:robotType")
            if attr is None or not attr.IsValid():
                continue
            if not attr.HasAuthoredValue():
                continue
            raw_value = attr.Get()
            if raw_value is None:
                continue
            token = str(raw_value).strip().lower()
            if token and token in _USD_TOKEN_TO_ROBOT_TYPE:
                return _USD_TOKEN_TO_ROBOT_TYPE[token]
        except Exception:
            continue
    return RobotType.ARM


def has_authored_robot_type(stage, asset_prim):
    # type: (Any, Any) -> bool
    """Return True iff ``isaac:robotType`` is authored on asset_prim or any
    direct child. Mirrors the lookup in ``read_robot_type``; used by callers
    that need to distinguish "asset declared its type" from "we used the default".
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return False
    candidates = [asset_prim]
    try:
        candidates.extend(list(asset_prim.GetChildren()))
    except Exception:
        pass
    for prim in candidates:
        try:
            attr = prim.GetAttribute("isaac:robotType")
            if attr is None or not attr.IsValid():
                continue
            if attr.HasAuthoredValue():
                return True
        except Exception:
            continue
    return False


def _detect_scara_from_structure(stage, asset_prim):
    # type: (Any, Any) -> bool
    """Return True when asset has 4-5 joints with exactly one prismatic (SCARA signature)."""
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return False
    try:
        from pxr import Usd, UsdPhysics

        revolute = 0
        prismatic = 0
        for prim in Usd.PrimRange(asset_prim):
            if prim.IsA(UsdPhysics.RevoluteJoint):
                revolute += 1
            elif prim.IsA(UsdPhysics.PrismaticJoint):
                prismatic += 1
        total = revolute + prismatic
        return 4 <= total <= 5 and prismatic == 1
    except Exception:
        return False


def determine_robot_type(stage, asset_prim, robot=None):
    # type: (Any, Any, Optional[Any]) -> RobotType
    """read_robot_type first; fall back to SCARA structural detection when result is ARM."""
    result = read_robot_type(stage, asset_prim)
    if result == RobotType.ARM and stage is not None and asset_prim is not None:
        if _detect_scara_from_structure(stage, asset_prim):
            return RobotType.SCARA
    return result


def get_scene_defaults(robot_type):
    # type: (RobotType) -> Dict[str, Any]
    """Return scene defaults dict for robot_type. Empty dict for unknown types."""
    return dict(SCENE_DEFAULTS.get(robot_type, {}))

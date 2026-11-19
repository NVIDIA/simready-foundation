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

Ported from the retired v1 test infrastructure.
"""

from enum import Enum, auto
from math import isfinite
from numbers import Integral

from simready.foundation.contracts import ContractError, FeatureId


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
}  # type: dict[str, RobotType]


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
}  # type: dict[RobotType, dict[str, Any]]


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
            # USD tokens in existing robot assets use both machine-style
            # spellings (``end_effector``) and display-style spellings
            # (``End Effector``).  Normalize whitespace so both resolve to
            # the same runtime classification.
            token = "_".join(str(raw_value).strip().lower().split())
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


def _contract_family(contract_id):
    """Identify exact runtime-tested gripper families in F2 or legacy receipts."""
    if contract_id.startswith("FET_022_"):
        return "022"
    if contract_id.startswith("FET_028_"):
        return "028"
    try:
        identity = FeatureId.parse(contract_id)
    except ContractError:
        return None
    return {"FET022_DrivenJoints": "022", "FET028_Gripper": "028"}.get(identity.name)


def has_standalone_gripper_topology(stage, asset_prim):
    """Qualify a simple one-leader jaw before any type-specific scene changes.

    Count all enabled movable joints, not only joints with strong drives. An
    arm with weak or passive joints must not be pinned as a jaw. Only verified
    local mimic followers can reduce this count; unsupported joints, ambiguous
    names, outside references, and cyclic mimic constraints provide no proof.
    This is a conservative setup hint, not a replacement for native DOF state.
    """
    try:
        from pxr import Usd, UsdPhysics
        from simready.foundation.tier_newton.runtime_tests.articulation_phases.mimic_joints import (
            detect_mimic_joints,
        )

        if stage is None or not asset_prim or not asset_prim.IsValid() or asset_prim.GetStage() != stage:
            return False
        joints = {}
        names = set()
        active_mimic_paths = set()
        for prim in Usd.PrimRange(asset_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            if not prim.IsA(UsdPhysics.Joint):
                continue
            joint = UsdPhysics.Joint(prim)
            if joint.GetJointEnabledAttr().Get() is False or prim.IsA(UsdPhysics.FixedJoint):
                continue
            if not (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)):
                return False
            name = prim.GetName()
            if name in names:
                return False
            names.add(name)
            joints[str(prim.GetPath())] = prim
            schemas = list(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
            authored_schemas = prim.GetMetadata("apiSchemas")
            for field in ("explicitItems", "prependedItems", "appendedItems", "addedItems"):
                schemas.extend(getattr(authored_schemas, field, ()) or ())
            native_mimic = "NewtonMimicAPI" in schemas
            enabled = prim.GetAttribute("newton:mimicEnabled")
            if native_mimic and enabled and enabled.Get() is False:
                continue
            if native_mimic or any(str(schema).startswith("PhysxMimicJointAPI:") for schema in schemas):
                active_mimic_paths.add(str(prim.GetPath()))
        if not joints:
            return False
        followers = {}
        specs = detect_mimic_joints(stage, asset_prim, str(asset_prim.GetPath()), sorted(names))
        for spec in specs:
            follower = spec.follower_joint_path
            if not stage.GetPrimAtPath(follower).GetPath().HasPrefix(asset_prim.GetPath()):
                continue
            reference = spec.reference_joint_path
            enabled = stage.GetPrimAtPath(follower).GetAttribute("newton:mimicEnabled")
            if spec.backend == "newton" and enabled and enabled.Get() is False:
                continue
            if follower not in joints or reference not in joints or follower in followers:
                return False
            if not isfinite(spec.gear) or not isfinite(spec.offset):
                return False
            if spec.backend == "newton":
                targets = stage.GetPrimAtPath(follower).GetRelationship("newton:mimicJoint").GetForwardedTargets()
            else:
                target_sets = [
                    relationship.GetForwardedTargets()
                    for relationship in stage.GetPrimAtPath(follower).GetRelationships()
                    if relationship.GetName().startswith("physxMimicJoint:")
                    and relationship.GetName().endswith(":referenceJoint")
                ]
                if len(target_sets) != 1:
                    return False
                targets = target_sets[0]
            if len(targets) != 1 or str(targets[0]) != reference:
                return False
            followers[follower] = reference
        if not active_mimic_paths.issubset(followers):
            return False
        for follower in followers:
            chain = set()
            current = follower
            while current in followers:
                if current in chain:
                    return False
                chain.add(current)
                current = followers[current]
        return len(joints) - len(followers) == 1
    except Exception:
        return False


def is_standalone_gripper(robot, scene_info, validated_features=None):
    """Return whether positive type/topology evidence excludes arm-style IK.

    Gripper receipts can also belong to an arm with an attached gripper. They
    supply a gripper signal, not proof that the whole articulation is a gripper.
    Unknown or malformed topology must not silently exclude an arm from IK.
    """
    families = {_contract_family(str(feature)) for feature in (validated_features or [])}
    has_driven_joints = "022" in families
    has_gripper = "028" in families
    if scene_info.get("robot_type") == RobotType.GRIPPER and scene_info.get("robot_type_authored", True):
        return True
    if not (scene_info.get("has_gripper_signals") or (has_driven_joints and has_gripper)):
        return False
    dof_count = getattr(robot, "dof_count", None)
    if isinstance(dof_count, bool) or not isinstance(dof_count, Integral) or dof_count <= 0:
        return False
    excluded = set()
    for key in ("passive_joint_indices", "mimic_follower_indices", "loop_joint_indices"):
        indices = scene_info.get(key)
        if indices is None:
            continue
        try:
            for index in indices:
                if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index < dof_count:
                    return False
                excluded.add(int(index))
        except TypeError:
            return False
    independent_count = dof_count - len(excluded)
    return independent_count <= 1


def get_scene_defaults(robot_type):
    # type: (RobotType) -> dict[str, Any]
    """Return scene defaults dict for robot_type. Empty dict for unknown types."""
    return dict(SCENE_DEFAULTS.get(robot_type, {}))

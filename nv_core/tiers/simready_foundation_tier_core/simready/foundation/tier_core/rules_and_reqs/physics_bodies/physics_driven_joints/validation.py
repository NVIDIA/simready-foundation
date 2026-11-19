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
__all__ = ["PhysicsDrivenJointsValidation"]

import math
from collections import defaultdict

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Tf, Usd, UsdGeom, UsdPhysics

# Prefer Kit's native bindings; standalone USD uses the codeless schema package.
try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema


# Ships in the tier's optional `isaac` extra, which installs only on Python 3.12.
# Absent means DJ.008/DJ.009/DJ.010 cannot be evaluated, not that the asset complies.
try:
    from usd.schema.isaac import robot_schema
except ImportError:
    robot_schema = None

_ROBOT_SCHEMA_UNAVAILABLE = (
    "Requirement not evaluated: the Isaac robot schema (usd.schema.isaac) is unavailable. "
    "It requires Python 3.12 and the tier's optional dependencies; install them with "
    'pip install "simready-foundation-tier-core[isaac]".'
)

# PhysxMimicJointAPI multiple-apply instance names. Rotational and translational
# tokens are accepted, plus the short X/Y/Z spelling used by prismatic couplings.
_MIMIC_AXES = frozenset(
    {
        "rotX",
        "rotY",
        "rotZ",
        "transX",
        "transY",
        "transZ",
        "X",
        "Y",
        "Z",
    }
)
_MUJOCO_JOINT_API = "MjcJointAPI"
_MUJOCO_EQUALITY_JOINT_API = "MjcEqualityJointAPI"
_MUJOCO_EQUALITY_CONNECT_API = "MjcEqualityConnectAPI"
_MUJOCO_EQUALITY_WELD_API = "MjcEqualityWeldAPI"
_NEWTON_MIMIC_API = "NewtonMimicAPI"
_NEWTON_MIMIC_JOINT_REL = "newton:mimicJoint"
_NEWTON_MIMIC_ENABLED_ATTR = "newton:mimicEnabled"
_NEWTON_MIMIC_COEF_ATTRS = ("newton:mimicCoef0", "newton:mimicCoef1")
_MUJOCO_EQUALITY_HIGHER_COEF_ATTRS = ("mjc:coef2", "mjc:coef3", "mjc:coef4")
_MUJOCO_EQUALITY_ARRAY_ATTRS = ("mjc:solimp", "mjc:solref")
_MUJOCO_ACTUATOR_TYPE = "MjcActuator"
_MUJOCO_TENDON_TYPE = "MjcTendon"
_MUJOCO_TENDON_PATH_REL = "mjc:path"
_MUJOCO_JOINT_NON_NEGATIVE_ATTRS = ("mjc:armature",)
_MUJOCO_ACTUATOR_ARRAY_ATTRS = ("mjc:gainPrm", "mjc:biasPrm")
_MUJOCO_ACTUATOR_RANGE_ATTRS = (
    ("mjc:ctrlRange:min", "mjc:ctrlRange:max", "control range"),
    ("mjc:forceRange:min", "mjc:forceRange:max", "force range"),
)


def _applied_api_schemas(prim: Usd.Prim) -> set[str]:
    schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
    op = prim.GetMetadata("apiSchemas")
    if op is None:
        return schemas
    for items in (
        op.explicitItems,
        op.prependedItems,
        op.appendedItems,
        op.addedItems,
        op.orderedItems,
    ):
        schemas.update(str(schema) for schema in items)
    return schemas


def _has_applied_api_schema(prim: Usd.Prim, schema_name: str) -> bool:
    return schema_name in _applied_api_schemas(prim)


def _as_finite_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _has_authored_attr(prim: Usd.Prim, attr_name: str) -> bool:
    attr = prim.GetAttribute(attr_name)
    return attr.IsValid() and attr.HasAuthoredValueOpinion()


def _is_non_fixed_articulation_joint(prim: Usd.Prim) -> bool:
    if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
        return False
    joint = UsdPhysics.Joint(prim)
    return not bool(joint.GetExcludeFromArticulationAttr().Get())


def _is_scalar_articulation_joint(prim: Usd.Prim) -> bool:
    if not _is_non_fixed_articulation_joint(prim):
        return False
    return bool(prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint))


def _as_exact_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        return None
    return int(value)


def _is_mujoco_actuator(prim: Usd.Prim) -> bool:
    return prim.GetTypeName() == _MUJOCO_ACTUATOR_TYPE


def _is_mujoco_tendon(prim: Usd.Prim) -> bool:
    return prim.GetTypeName() == _MUJOCO_TENDON_TYPE


def _enclosing_rigid_body_path(stage: Usd.Stage, path) -> str:
    """Resolve a joint endpoint path to its owning PhysicsRigidBodyAPI prim path."""
    prim = stage.GetPrimAtPath(path)
    while prim and prim.IsValid() and not prim.IsPseudoRoot():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) or "PhysicsRigidBodyAPI" in _applied_api_schemas(prim):
            return str(prim.GetPath())
        prim = prim.GetParent()
    return str(path)


def _joint_local_transform(prim: Usd.Prim, body0: bool) -> Gf.Transform:
    joint = UsdPhysics.Joint(prim)
    pos_attr = joint.GetLocalPos0Attr() if body0 else joint.GetLocalPos1Attr()
    rot_attr = joint.GetLocalRot0Attr() if body0 else joint.GetLocalRot1Attr()
    pos = pos_attr.Get() if pos_attr.IsValid() else None
    rot = rot_attr.Get() if rot_attr.IsValid() else None
    transform = Gf.Transform()
    if rot is not None:
        quat = Gf.Quatd(rot)
        if quat.GetLength() > 0.0:
            transform.SetRotation(Gf.Rotation(quat.GetNormalized()))
    if pos is not None:
        transform.SetTranslation(Gf.Vec3d(pos))
    return transform


def _joint_axis_vector(prim: Usd.Prim) -> Gf.Vec3d:
    axis_attr = prim.GetAttribute("physics:axis")
    axis_token = str(axis_attr.Get() if axis_attr.IsValid() and axis_attr.Get() else "X").upper()
    if axis_token == "Y":
        return Gf.Vec3d(0.0, 1.0, 0.0)
    if axis_token == "Z":
        return Gf.Vec3d(0.0, 0.0, 1.0)
    return Gf.Vec3d(1.0, 0.0, 0.0)


def _screw_rank(columns: list[tuple[float, float, float, float, float, float]], tol: float = 1e-5) -> int:
    if not columns:
        return 0
    rows = 6
    cols = len(columns)
    mat = [[float(columns[c][r]) for c in range(cols)] for r in range(rows)]
    rank = 0
    for col in range(cols):
        if rank >= rows:
            break
        best_val = 0.0
        best_r = rank
        best_c = col
        for r in range(rank, rows):
            for c in range(col, cols):
                val = abs(mat[r][c])
                if val > best_val:
                    best_val = val
                    best_r = r
                    best_c = c
        if best_val <= tol:
            break
        mat[rank], mat[best_r] = mat[best_r], mat[rank]
        if best_c != col:
            for r in range(rows):
                mat[r][col], mat[r][best_c] = mat[r][best_c], mat[r][col]
        pivot = mat[rank][col]
        for r in range(rank + 1, rows):
            factor = mat[r][col] / pivot
            if factor != 0.0:
                for c in range(col, cols):
                    mat[r][c] -= factor * mat[rank][c]
        rank += 1
    return rank


def _is_supported_loop_closure_joint(prim: Usd.Prim) -> bool:
    if not prim.IsValid() or not UsdPhysics.Joint(prim):
        return False
    schemas = _applied_api_schemas(prim)
    if _MUJOCO_EQUALITY_CONNECT_API in schemas or _MUJOCO_EQUALITY_WELD_API in schemas:
        return True
    return bool(
        prim.IsA(UsdPhysics.RevoluteJoint)
        or prim.IsA(UsdPhysics.PrismaticJoint)
        or prim.IsA(UsdPhysics.SphericalJoint)
        or prim.IsA(UsdPhysics.FixedJoint)
    )


def _joint_screw_columns(
    prim: Usd.Prim,
    frame: Gf.Transform,
    length_scale: float,
    *,
    is_closure: bool = False,
) -> list[tuple[float, float, float, float, float, float]]:
    anchor = Gf.Vec3d(frame.GetTranslation()) / length_scale
    rot = frame.GetRotation()
    schemas = _applied_api_schemas(prim)
    if is_closure and _MUJOCO_EQUALITY_WELD_API in schemas:
        return []
    if is_closure and (_MUJOCO_EQUALITY_CONNECT_API in schemas or prim.IsA(UsdPhysics.SphericalJoint)):
        cols: list[tuple[float, float, float, float, float, float]] = []
        for basis in (Gf.Vec3d(1.0, 0.0, 0.0), Gf.Vec3d(0.0, 1.0, 0.0), Gf.Vec3d(0.0, 0.0, 1.0)):
            v = Gf.Cross(anchor, basis)
            cols.append((basis[0], basis[1], basis[2], v[0], v[1], v[2]))
        return cols
    if prim.IsA(UsdPhysics.FixedJoint):
        return []
    axis_world = Gf.Vec3d(rot.TransformDir(_joint_axis_vector(prim)))
    norm = axis_world.GetLength()
    if norm <= 1e-12:
        return []
    axis_world /= norm
    if prim.IsA(UsdPhysics.RevoluteJoint):
        v = Gf.Cross(anchor, axis_world)
        return [(axis_world[0], axis_world[1], axis_world[2], v[0], v[1], v[2])]
    if prim.IsA(UsdPhysics.PrismaticJoint):
        return [(0.0, 0.0, 0.0, axis_world[0], axis_world[1], axis_world[2])]
    return []


def _frames_constrain_unactuated_loop_joints(
    stage: Usd.Stage,
    frames: dict[str, Gf.Transform],
    actuated_cycle: list[str],
    unactuated_cycle: list[str],
    closure_path: str,
) -> bool:
    all_paths = actuated_cycle + unactuated_cycle + [closure_path]
    anchors = [Gf.Vec3d(frames[p].GetTranslation()) for p in all_paths if p in frames]
    max_dist = 0.0
    for i, a in enumerate(anchors):
        for b in anchors[i + 1 :]:
            dist = (a - b).GetLength()
            if dist > max_dist:
                max_dist = dist
    length_scale = max_dist if max_dist > 1e-6 else 1.0

    s_act: list[tuple[float, float, float, float, float, float]] = []
    for jpath in actuated_cycle:
        jprim = stage.GetPrimAtPath(jpath)
        s_act.extend(_joint_screw_columns(jprim, frames[jpath], length_scale, is_closure=False))

    s_unact: list[tuple[float, float, float, float, float, float]] = []
    for jpath in unactuated_cycle:
        jprim = stage.GetPrimAtPath(jpath)
        cols = _joint_screw_columns(jprim, frames[jpath], length_scale, is_closure=False)
        if len(cols) != 1:
            return False
        s_unact.extend(cols)

    closure_prim = stage.GetPrimAtPath(closure_path)
    s_close = _joint_screw_columns(closure_prim, frames[closure_path], length_scale, is_closure=True)

    rank_close = _screw_rank(s_close)
    rank_unact_close = _screw_rank(s_unact + s_close)
    free_motion_dim = len(s_unact) - (rank_unact_close - rank_close)
    if free_motion_dim != 0:
        return False

    # At least one actuated joint on the cycle must couple into the passive loop subspace.
    return any(
        _screw_rank(s_unact + s_close + [s_a]) == rank_unact_close and _screw_rank(s_close + [s_a]) > rank_close
        for s_a in s_act
    )


def _loop_has_no_free_unactuated_coordinates(
    stage: Usd.Stage,
    cache: UsdGeom.XformCache,
    path_edges: list[tuple[str, str, str]],
    joint_bodies: dict[str, tuple[str, str]],
    actuated_cycle: list[str],
    unactuated_cycle: list[str],
    closure_path: str,
) -> bool:
    """Return True only when holding the cycle's actuated joint(s) leaves zero free passive DOFs."""
    # A single loop closure in a 4-bar / planar linkage can constrain at most 2 passive 1-DOF tree joints.
    if not actuated_cycle or not unactuated_cycle or len(unactuated_cycle) > 2:
        return False

    closure_prim = stage.GetPrimAtPath(closure_path)
    if not _is_supported_loop_closure_joint(closure_prim):
        return False

    all_joint_paths = [jpath for _, _, jpath in path_edges] + [closure_path]
    cycle_bodies = {u for u, _, _ in path_edges} | {v for _, v, _ in path_edges}
    has_authored_geometry = any(
        _has_authored_attr(stage.GetPrimAtPath(jpath), attr_name)
        for jpath in all_joint_paths
        for attr_name in ("physics:localPos0", "physics:localPos1", "physics:localRot0", "physics:localRot1")
    ) or any(
        bool(UsdGeom.Xformable(stage.GetPrimAtPath(bpath)).GetOrderedXformOps())
        for bpath in cycle_bodies
        if stage.GetPrimAtPath(bpath).IsValid() and UsdGeom.Xformable(stage.GetPrimAtPath(bpath))
    )

    if not has_authored_geometry:
        # In a purely topological fixture without authored link/joint transforms, require <= 2 passive
        # 1-DOF joints and compatible joint axes between the cycle actuator(s) and passive joints.
        act_axes = [
            (
                stage.GetPrimAtPath(jpath).IsA(UsdPhysics.RevoluteJoint),
                tuple(_joint_axis_vector(stage.GetPrimAtPath(jpath))),
            )
            for jpath in actuated_cycle
        ]
        return all(
            (
                stage.GetPrimAtPath(jpath).IsA(UsdPhysics.RevoluteJoint),
                tuple(_joint_axis_vector(stage.GetPrimAtPath(jpath))),
            )
            in act_axes
            for jpath in unactuated_cycle
        )

    # 1. Evaluate using composed world transforms on the stage.
    world_frames: dict[str, Gf.Transform] = {}
    for jpath in all_joint_paths:
        jprim = stage.GetPrimAtPath(jpath)
        use_body0 = (
            _has_authored_attr(jprim, "physics:localPos0")
            or _has_authored_attr(jprim, "physics:localRot0")
            or not (_has_authored_attr(jprim, "physics:localPos1") or _has_authored_attr(jprim, "physics:localRot1"))
        )
        world_frames[jpath] = get_world_body_transform(stage, cache, UsdPhysics.Joint(jprim), use_body0)

    if _frames_constrain_unactuated_loop_joints(stage, world_frames, actuated_cycle, unactuated_cycle, closure_path):
        return True

    # 2. Fallback for stages where body Xforms are left at identity and link offsets are authored
    #    purely via joint localPos0/localRot0 and localPos1/localRot1 along the tree path.
    start_body = path_edges[0][0]
    start_prim = stage.GetPrimAtPath(start_body)
    body_matrices: dict[str, Gf.Matrix4d] = {
        start_body: cache.GetLocalToWorldTransform(start_prim)
        if start_prim and start_prim.IsValid()
        else Gf.Matrix4d(1.0)
    }
    fk_frames: dict[str, Gf.Transform] = {}
    for u_body, v_body, jpath in path_edges:
        jprim = stage.GetPrimAtPath(jpath)
        b0, _ = joint_bodies[jpath]
        t0 = _joint_local_transform(jprim, True).GetMatrix()
        t1 = _joint_local_transform(jprim, False).GetMatrix()
        u_mat = body_matrices.get(u_body, Gf.Matrix4d(1.0))
        if u_body == b0:
            j_mat = t0 * u_mat
            v_mat = t1.GetInverse() * j_mat
        else:
            j_mat = t1 * u_mat
            v_mat = t0.GetInverse() * j_mat
        fk_frames[jpath] = Gf.Transform(j_mat)
        body_matrices[v_body] = v_mat

    cb0, cb1 = joint_bodies[closure_path]
    if cb0 in body_matrices:
        c_mat = _joint_local_transform(closure_prim, True).GetMatrix() * body_matrices[cb0]
    else:
        c_mat = _joint_local_transform(closure_prim, False).GetMatrix() * body_matrices.get(cb1, Gf.Matrix4d(1.0))
    fk_frames[closure_path] = Gf.Transform(c_mat)

    return _frames_constrain_unactuated_loop_joints(stage, fk_frames, actuated_cycle, unactuated_cycle, closure_path)


def _closed_loop_articulation_joint_paths(stage: Usd.Stage, actuated_joints: set[str]) -> set[str]:
    """Return paths of passive articulation joints on a closed loop that is driven by an actuated joint.

    In closed-loop 4-bar linkages (such as Robotiq 2F-85 or Dofbot), an excluded
    joint (physics:excludeFromArticulation = true, optionally with
    MjcEqualityConnectAPI / MjcEqualityWeldAPI) closes a cycle between two branches
    of the articulation tree. Passive 1-DOF linkage joints along that cycle are coupled
    mechanically through the loop closure only when at least one joint on that
    same cycle is actuated (directly, via a fixed tendon, or via a mimic chain
    rooted at an actuated joint), holding the actuated joint(s) leaves zero free
    unactuated motion dimensions in the loop constraint Jacobian, and at least
    one of the joint's endpoint bodies is a loop-only branch body.
    """
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    body_movable_joints: dict[str, set[str]] = defaultdict(set)
    joint_bodies: dict[str, tuple[str, str]] = {}
    closures: list[tuple[str, str, str]] = []

    for prim in stage.Traverse():
        if not UsdPhysics.Joint(prim):
            continue
        joint = UsdPhysics.Joint(prim)
        enabled_attr = joint.GetJointEnabledAttr()
        if enabled_attr.IsValid() and enabled_attr.HasAuthoredValueOpinion() and enabled_attr.Get() is False:
            continue
        b0_targets = joint.GetBody0Rel().GetTargets()
        b1_targets = joint.GetBody1Rel().GetTargets()
        if not b0_targets or not b1_targets:
            continue
        b0 = _enclosing_rigid_body_path(stage, b0_targets[0])
        b1 = _enclosing_rigid_body_path(stage, b1_targets[0])
        if not b0 or not b1 or b0 == b1:
            continue
        jpath = str(prim.GetPath())
        joint_bodies[jpath] = (b0, b1)
        if not UsdPhysics.FixedJoint(prim):
            body_movable_joints[b0].add(jpath)
            body_movable_joints[b1].add(jpath)
        if bool(joint.GetExcludeFromArticulationAttr().Get()):
            closures.append((jpath, b0, b1))
        else:
            adj[b0].append((b1, jpath))
            adj[b1].append((b0, jpath))

    cache = UsdGeom.XformCache()
    loop_joints: set[str] = set()
    for closure_path, start_body, end_body in closures:
        if start_body not in adj or end_body not in adj:
            continue
        visited = {start_body}
        queue: list[tuple[str, list[tuple[str, str, str]]]] = [(start_body, [])]
        path_edges: list[tuple[str, str, str]] = []
        cycle_movable: list[str] = []
        while queue:
            curr, edges = queue.pop(0)
            if curr == end_body:
                path_edges = edges
                for _, _, jpath in edges:
                    jprim = stage.GetPrimAtPath(jpath)
                    if jprim.IsValid() and not UsdPhysics.FixedJoint(jprim):
                        cycle_movable.append(jpath)
                break
            for neighbor, jpath in adj.get(curr, ()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, edges + [(curr, neighbor, jpath)]))
        if not cycle_movable:
            continue
        if not all(_is_scalar_articulation_joint(stage.GetPrimAtPath(jpath)) for jpath in cycle_movable):
            continue
        actuated_cycle = [jpath for jpath in cycle_movable if jpath in actuated_joints]
        unactuated_cycle = [jpath for jpath in cycle_movable if jpath not in actuated_joints]
        if not _loop_has_no_free_unactuated_coordinates(
            stage, cache, path_edges, joint_bodies, actuated_cycle, unactuated_cycle, closure_path
        ):
            continue
        cycle_all = set(cycle_movable) | {closure_path}
        for jpath in unactuated_cycle:
            b0, b1 = joint_bodies[jpath]
            b0_loop_only = bool(body_movable_joints[b0]) and body_movable_joints[b0].issubset(cycle_all)
            b1_loop_only = bool(body_movable_joints[b1]) and body_movable_joints[b1].issubset(cycle_all)
            if b0_loop_only or b1_loop_only:
                loop_joints.add(jpath)
    return loop_joints


def _is_mujoco_mimic_follower(prim: Usd.Prim) -> bool:
    """Return True if the joint is coupled to a leader joint via MjcEqualityJointAPI or NewtonMimicAPI.

    In official mjcPhysics / mujoco-usd-converter authoring, MjcEqualityJointAPI
    prepends NewtonMimicAPI and uses newton:mimicJoint, newton:mimicEnabled,
    newton:mimicCoef0, and newton:mimicCoef1 for the target and linear terms.
    """
    schemas = _applied_api_schemas(prim)
    if _MUJOCO_EQUALITY_JOINT_API not in schemas and _NEWTON_MIMIC_API not in schemas:
        return False
    enabled_attr = prim.GetAttribute(_NEWTON_MIMIC_ENABLED_ATTR)
    if enabled_attr.IsValid() and enabled_attr.HasAuthoredValueOpinion() and enabled_attr.Get() is False:
        return False
    rel = prim.GetRelationship(_NEWTON_MIMIC_JOINT_REL)
    if rel and rel.GetTargets():
        return True
    legacy_rel = prim.GetRelationship("mjc:target")
    return bool(legacy_rel and legacy_rel.GetTargets())


def _is_numeric_sequence(value) -> bool:
    if value is None or isinstance(value, (str, bytes)):
        return False
    try:
        values = list(value)
    except TypeError:
        return False
    return bool(values) and all(_as_finite_float(item) is not None for item in values)


def get_world_body_transform(stage, cache, joint, body0base):
    """Get the world transform of a joint computed from either body 0 or body 1.

    Args:
        stage: The USD stage containing the joint.
        cache: XformCache for efficient transform computation.
        joint: The joint to compute the transform for.
        body0base: If True, compute transform from body 0, otherwise from body 1.

    Returns:
        The world transform of the joint.
    """
    # get both bodies if available
    b0paths = joint.GetBody0Rel().GetTargets()
    b1paths = joint.GetBody1Rel().GetTargets()

    b0prim = None
    b1prim = None

    if len(b0paths):
        b0prim = stage.GetPrimAtPath(b0paths[0])
        if not b0prim.IsValid():
            b0prim = None

    if len(b1paths):
        b1prim = stage.GetPrimAtPath(b1paths[0])
        if not b1prim.IsValid():
            b1prim = None

    b0locpos = joint.GetLocalPos0Attr().Get()
    b1locpos = joint.GetLocalPos1Attr().Get()
    b0locrot = joint.GetLocalRot0Attr().Get()
    b1locrot = joint.GetLocalRot1Attr().Get()

    # switch depending on which is the base
    if body0base:
        t0prim = b0prim
        t0locpos = b0locpos
        t0locrot = b0locrot
        t1prim = b1prim
    else:
        t0prim = b1prim
        t0locpos = b1locpos
        t0locrot = b1locrot
        t1prim = b0prim

    if t0prim:
        t0world = cache.GetLocalToWorldTransform(t0prim)
    else:
        t0world = Gf.Matrix4d()
        t0world.SetIdentity()

    if t1prim:
        t1world = cache.GetLocalToWorldTransform(t1prim)
    else:
        t1world = Gf.Matrix4d()
        t1world.SetIdentity()

    t0local = Gf.Transform()
    t0local.SetRotation(Gf.Rotation(Gf.Quatd(t0locrot)))
    t0local.SetTranslation(Gf.Vec3d(t0locpos))
    t0mult = t0local * Gf.Transform(t0world)

    return t0mult


def GetJointDrivesAndJointStates(joint):
    """Get the drive APIs and joint state APIs for a joint.

    Args:
        joint: The joint to get drive and state APIs for.

    Returns:
        A tuple of (drive_apis, joint_state_apis) for the joint.
    """
    if PhysxSchema is None:
        raise RuntimeError("PhysxSchema is not available in this environment")
    driveAPIs = []
    joint_states = []
    # Only collect drives that are actually applied (HasAPI guard). Without this
    # guard `UsdPhysics.DriveAPI(joint, axis)` returns a truthy wrapper even when
    # the schema is not applied, which makes `drives` never empty and neuters the
    # "has no drive or mimic API" check in PhysicsJointHasDriveOrMimicAPI.
    if joint.IsA(UsdPhysics.RevoluteJoint):
        if joint.HasAPI(UsdPhysics.DriveAPI, "angular"):
            driveAPIs.append(UsdPhysics.DriveAPI(joint, "angular"))
            joint_states.append(PhysxSchema.JointStateAPI(joint, "angular"))
    elif joint.IsA(UsdPhysics.PrismaticJoint):
        if joint.HasAPI(UsdPhysics.DriveAPI, "linear"):
            driveAPIs.append(UsdPhysics.DriveAPI(joint, "linear"))
            joint_states.append(PhysxSchema.JointStateAPI(joint, "linear"))
    else:
        for axis in (f"{prefix}{i}" for prefix in ("rot", "trans") for i in ("X", "Y", "Z")):
            if joint.HasAPI(UsdPhysics.DriveAPI, axis):
                driveAPIs.append(UsdPhysics.DriveAPI(joint, axis))
                joint_states.append(PhysxSchema.JointStateAPI(joint, axis))
    return driveAPIs, joint_states


def GfQuatToVec4d(quat: Gf.Quatd) -> Gf.Vec4d:
    """Convert a quaternion to a 4D vector.

    Args:
        quat: The quaternion to convert.

    Returns:
        A Vec4d with (real, imaginary_x, imaginary_y, imaginary_z) components.
    """
    return Gf.Vec4d(quat.GetReal(), quat.GetImaginary()[0], quat.GetImaginary()[1], quat.GetImaginary()[2])


def GfRotationToVec4d(rot: Gf.Rotation) -> Gf.Vec4d:
    """Convert a rotation to a 4D vector.

    Args:
        rot: The rotation to convert.

    Returns:
        A Vec4d representation of the rotation's quaternion.
    """
    return GfQuatToVec4d(rot.GetQuat())


def _rotations_match_orientation(qa: Gf.Quatd, qb: Gf.Quatd, tol: float) -> bool:
    """Return True if two quaternions represent the same orientation (double-cover safe).

    ``q`` and ``-q`` are treated as the same rotation. Uses ``abs(dot) >= 1.0 - tol``.
    Component-wise ``Gf.IsClose`` on the quaternion vec4d would false-fail on the
    antipodal representation of an identical orientation.

    Args:
        qa: First quaternion to compare.
        qb: Second quaternion to compare.
        tol: Allowed tolerance from an absolute dot product of 1.0.

    Returns:
        True if the quaternions represent the same orientation, False otherwise.
    """
    qa_n = qa.GetNormalized()
    qb_n = qb.GetNormalized()
    dot = qa_n.GetReal() * qb_n.GetReal() + Gf.Dot(qa_n.GetImaginary(), qb_n.GetImaginary())
    return abs(dot) >= 1.0 - tol


def _rotation_error_magnitude(qa: Gf.Quatd, qb: Gf.Quatd) -> float:
    """Return the orientation mismatch magnitude between two quaternions.

    Args:
        qa: First quaternion to compare.
        qb: Second quaternion to compare.

    Returns:
        The value ``1.0 - abs(dot)`` for normalized quaternions.
    """
    qa_n = qa.GetNormalized()
    qb_n = qb.GetNormalized()
    dot = qa_n.GetReal() * qb_n.GetReal() + Gf.Dot(qa_n.GetImaginary(), qb_n.GetImaginary())
    return 1.0 - abs(dot)


def get_prismatic_or_revolute_limits(joint_prim: Usd.Prim) -> tuple[float, float]:
    """Get the lower and upper limits for prismatic or revolute joints.

    Args:
        joint_prim: The joint prim to get limits from.

    Returns:
        A tuple containing (lower_limit, upper_limit) or (None, None) if not applicable.
    """
    if joint_prim.IsA(UsdPhysics.RevoluteJoint):
        joint = UsdPhysics.RevoluteJoint(joint_prim)
        return joint.GetLowerLimitAttr().Get(), joint.GetUpperLimitAttr().Get()
    elif joint_prim.IsA(UsdPhysics.PrismaticJoint):
        joint = UsdPhysics.PrismaticJoint(joint_prim)
        return joint.GetLowerLimitAttr().Get(), joint.GetUpperLimitAttr().Get()
    else:
        return None, None


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_001, override=True)
class MuJoCoJointAPIChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates MuJoCo joint API placement and authored joint tuning values."""

    MUJOCO_JOINT_API_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_001

    def _validate_non_negative_number(self, prim: Usd.Prim, attr_name: str) -> None:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return

        numeric_value = _as_finite_float(attr.Get())
        if numeric_value is None:
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=f"MuJoCo joint attribute '{attr_name}' on '{prim.GetPath()}' must be a finite number.",
                at=attr,
            )
            return
        if numeric_value < 0:
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=f"MuJoCo joint attribute '{attr_name}' on '{prim.GetPath()}' must be non-negative.",
                at=attr,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        has_mujoco_joint_api = _has_applied_api_schema(prim, _MUJOCO_JOINT_API)
        authored_mujoco_joint_attrs = tuple(
            attr_name for attr_name in _MUJOCO_JOINT_NON_NEGATIVE_ATTRS if _has_authored_attr(prim, attr_name)
        )

        if (has_mujoco_joint_api or authored_mujoco_joint_attrs) and not UsdPhysics.Joint(prim):
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=(
                    f"Prim '{prim.GetPath()}' authors MuJoCo joint data but is not a UsdPhysics.Joint. "
                    "Apply MjcJointAPI and mjc:* joint attributes only to USD physics joint prims."
                ),
                at=prim,
            )
            return

        if _is_non_fixed_articulation_joint(prim) and not has_mujoco_joint_api:
            self._AddFailedCheck(
                requirement=self.MUJOCO_JOINT_API_REQUIREMENT,
                message=(
                    f"MuJoCo articulation joint '{prim.GetPath()}' does not apply MjcJointAPI. "
                    "Apply MjcJointAPI to every non-fixed joint that participates in the articulation."
                ),
                at=prim,
            )
            return

        if not has_mujoco_joint_api:
            return

        for attr_name in _MUJOCO_JOINT_NON_NEGATIVE_ATTRS:
            self._validate_non_negative_number(prim, attr_name)


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_002, override=True)
class MuJoCoActuatorTargetsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates MuJoCo actuator prims and their target joint relationships."""

    MUJOCO_ACTUATOR_REQUIREMENT = cap.PhysicsDrivenJointsRequirements.MUJOCO_DJ_002

    def _validate_range_pair(
        self,
        prim: Usd.Prim,
        min_attr_name: str,
        max_attr_name: str,
        label: str,
    ) -> None:
        min_attr = prim.GetAttribute(min_attr_name)
        max_attr = prim.GetAttribute(max_attr_name)
        has_min = min_attr.IsValid() and min_attr.HasAuthoredValueOpinion()
        has_max = max_attr.IsValid() and max_attr.HasAuthoredValueOpinion()

        if not has_min and not has_max:
            return

        # In mjcPhysics schemas, mjc:ctrlRange:min and mjc:forceRange:min default to 0.0;
        # mujoco-usd-converter omits default-valued attributes when authoring USD.
        min_raw = min_attr.Get() if has_min else (min_attr.Get() if min_attr.IsValid() else 0.0)
        max_raw = max_attr.Get() if has_max else (max_attr.Get() if max_attr.IsValid() else 0.0)
        if min_raw is None:
            min_raw = 0.0
        if max_raw is None:
            max_raw = 0.0

        min_value = _as_finite_float(min_raw)
        max_value = _as_finite_float(max_raw)
        if min_value is None or max_value is None:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' has a non-finite {label}.",
                at=prim,
            )
            return
        if min_value > max_value:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' has an inverted {label}.",
                at=prim,
            )

    def _validate_numeric_array(self, prim: Usd.Prim, attr_name: str) -> None:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
            return

        if not _is_numeric_sequence(attr.Get()):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' must author '{attr_name}' as a non-empty numeric array.",
                at=attr,
            )

    def _validate_tendon_target(
        self, stage: Usd.Stage, actuator_prim: Usd.Prim, tendon_prim: Usd.Prim, targeted_joints: set[str]
    ) -> bool:
        tendon_type_attr = tendon_prim.GetAttribute("mjc:type")
        tendon_type = (
            tendon_type_attr.Get()
            if tendon_type_attr.IsValid() and tendon_type_attr.HasAuthoredValueOpinion()
            else None
        )
        if not isinstance(tendon_type, str) or tendon_type.lower() != "fixed":
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo actuator '{actuator_prim.GetPath()}' targets MjcTendon '{tendon_prim.GetPath()}' "
                    f"with unsupported or unauthored 'mjc:type' ({tendon_type!r}); only fixed tendons "
                    "('mjc:type = \"fixed\"') provide joint actuation coverage."
                ),
                at=tendon_type_attr if tendon_type_attr.IsValid() else tendon_prim,
            )
            return False

        path_rel = tendon_prim.GetRelationship(_MUJOCO_TENDON_PATH_REL)
        joint_targets = list(path_rel.GetTargets()) if path_rel else []
        if not joint_targets:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo actuator '{actuator_prim.GetPath()}' targets MjcTendon '{tendon_prim.GetPath()}' "
                    f"which has no '{_MUJOCO_TENDON_PATH_REL}' joint targets."
                ),
                at=tendon_prim,
            )
            return False

        indices_attr = tendon_prim.GetAttribute("mjc:path:indices")
        selected_indices: list[int] = []
        if indices_attr.IsValid() and indices_attr.HasAuthoredValueOpinion():
            raw_indices = indices_attr.Get()
            if raw_indices is None or isinstance(raw_indices, (str, bytes)):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo tendon '{tendon_prim.GetPath()}' must author 'mjc:path:indices' as an "
                        "integer array."
                    ),
                    at=indices_attr,
                )
                return False
            try:
                raw_index_list = list(raw_indices)
            except TypeError:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo tendon '{tendon_prim.GetPath()}' must author 'mjc:path:indices' as an "
                        "integer array."
                    ),
                    at=indices_attr,
                )
                return False
            if not raw_index_list:
                # Schema default [] selects all mjc:path targets in relationship order.
                selected_indices = list(range(len(joint_targets)))
            else:
                for item in raw_index_list:
                    idx = _as_exact_int(item)
                    if idx is None or idx < 0 or idx >= len(joint_targets):
                        self._AddFailedCheck(
                            requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                            message=(
                                f"MuJoCo tendon '{tendon_prim.GetPath()}' has invalid or out-of-range 'mjc:path:indices' "
                                f"entry {item!r} for {len(joint_targets)} '{_MUJOCO_TENDON_PATH_REL}' target(s)."
                            ),
                            at=indices_attr,
                        )
                        return False
                    selected_indices.append(idx)
        else:
            selected_indices = list(range(len(joint_targets)))

        coef_attr = tendon_prim.GetAttribute("mjc:path:coef")
        coefs: list[float] = []
        if coef_attr.IsValid() and coef_attr.HasAuthoredValueOpinion():
            raw_coefs = coef_attr.Get()
            if raw_coefs is None or isinstance(raw_coefs, (str, bytes)):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo tendon '{tendon_prim.GetPath()}' must author 'mjc:path:coef' as a "
                        "finite numeric array."
                    ),
                    at=coef_attr,
                )
                return False
            try:
                raw_coef_list = list(raw_coefs)
            except TypeError:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo tendon '{tendon_prim.GetPath()}' must author 'mjc:path:coef' as a "
                        "finite numeric array."
                    ),
                    at=coef_attr,
                )
                return False
            if not raw_coef_list:
                # Schema default [] assigns unit coefficient 1.0 to each selected path entry.
                coefs = [1.0] * len(selected_indices)
            else:
                if not all(_as_finite_float(item) is not None for item in raw_coef_list):
                    self._AddFailedCheck(
                        requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                        message=(
                            f"MuJoCo tendon '{tendon_prim.GetPath()}' must author 'mjc:path:coef' as a "
                            "finite numeric array."
                        ),
                        at=coef_attr,
                    )
                    return False
                coefs = [float(_as_finite_float(item)) for item in raw_coef_list]
                if len(coefs) != len(selected_indices):
                    self._AddFailedCheck(
                        requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                        message=(
                            f"MuJoCo tendon '{tendon_prim.GetPath()}' has {len(coefs)} 'mjc:path:coef' value(s) "
                            f"for {len(selected_indices)} selected path entry/entries."
                        ),
                        at=coef_attr,
                    )
                    return False
        else:
            coefs = [1.0] * len(selected_indices)

        valid = True
        effective_contributions: dict[str, float] = defaultdict(float)
        for path_idx, coef in zip(selected_indices, coefs):
            joint_path = joint_targets[path_idx]
            joint_prim = stage.GetPrimAtPath(joint_path)
            if not joint_prim.IsValid() or not _is_scalar_articulation_joint(joint_prim):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo tendon '{tendon_prim.GetPath()}' (targeted by actuator '{actuator_prim.GetPath()}') "
                        f"includes '{joint_path}' in '{_MUJOCO_TENDON_PATH_REL}', which is not a valid non-fixed "
                        "1-DOF (revolute or prismatic) USD physics articulation joint."
                    ),
                    at=tendon_prim,
                )
                valid = False
                continue
            if not _has_applied_api_schema(joint_prim, _MUJOCO_JOINT_API):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo tendon '{tendon_prim.GetPath()}' (targeted by actuator '{actuator_prim.GetPath()}') "
                        f"targets joint '{joint_path}' without MjcJointAPI. Apply MjcJointAPI to the target joint."
                    ),
                    at=joint_prim,
                )
                valid = False
                continue
            effective_contributions[str(joint_path)] += coef

        active_joints = {jpath for jpath, total_coef in effective_contributions.items() if total_coef != 0.0}
        if not active_joints:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo tendon '{tendon_prim.GetPath()}' (targeted by actuator '{actuator_prim.GetPath()}') "
                    "has no effective non-zero joint transmission in 'mjc:path:coef'."
                ),
                at=tendon_prim,
            )
            return False

        targeted_joints.update(active_joints)
        return valid

    def _validate_actuator(self, stage: Usd.Stage, prim: Usd.Prim, targeted_joints: set[str]) -> None:
        target_rel = prim.GetRelationship("mjc:target")
        targets = target_rel.GetTargets() if target_rel else []
        if len(targets) != 1:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' must target exactly one joint or MjcTendon with 'mjc:target'.",
                at=prim,
            )
            return

        target_prim = stage.GetPrimAtPath(targets[0])
        if target_prim.IsValid() and _is_mujoco_tendon(target_prim):
            if not self._validate_tendon_target(stage, prim, target_prim, targeted_joints):
                return
        elif not target_prim.IsValid() or not _is_non_fixed_articulation_joint(target_prim):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo actuator '{prim.GetPath()}' targets '{targets[0]}', "
                    "which is not a valid non-fixed USD physics articulation joint or MjcTendon."
                ),
                at=prim,
            )
            return
        else:
            if not _has_applied_api_schema(target_prim, _MUJOCO_JOINT_API):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo actuator '{prim.GetPath()}' targets joint '{targets[0]}' without MjcJointAPI. "
                        "Apply MjcJointAPI to the target joint."
                    ),
                    at=target_prim,
                )
                return

            targeted_joints.add(str(targets[0]))

        for min_attr_name, max_attr_name, label in _MUJOCO_ACTUATOR_RANGE_ATTRS:
            self._validate_range_pair(prim, min_attr_name, max_attr_name, label)
        for attr_name in _MUJOCO_ACTUATOR_ARRAY_ATTRS:
            self._validate_numeric_array(prim, attr_name)

        bias_type_attr = prim.GetAttribute("mjc:biasType")
        if bias_type_attr.IsValid() and bias_type_attr.HasAuthoredValueOpinion() and not str(bias_type_attr.Get()):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo actuator '{prim.GetPath()}' authors an empty 'mjc:biasType'.",
                at=bias_type_attr,
            )

    def _validate_mimic_follower(self, stage: Usd.Stage, prim: Usd.Prim) -> str | None:
        schemas = _applied_api_schemas(prim)
        if _MUJOCO_EQUALITY_JOINT_API not in schemas and _NEWTON_MIMIC_API not in schemas:
            return None

        if not _is_scalar_articulation_joint(prim):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo mimic joint '{prim.GetPath()}' has type '{prim.GetTypeName()}'; "
                    "MjcEqualityJointAPI / NewtonMimicAPI only supports 1-DOF scalar joints "
                    "(PhysicsRevoluteJoint or PhysicsPrismaticJoint)."
                ),
                at=prim,
            )
            return None

        enabled_attr = prim.GetAttribute(_NEWTON_MIMIC_ENABLED_ATTR)
        if enabled_attr.IsValid() and enabled_attr.HasAuthoredValueOpinion():
            enabled_val = enabled_attr.Get()
            if not isinstance(enabled_val, bool):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo mimic joint '{prim.GetPath()}' attribute '{_NEWTON_MIMIC_ENABLED_ATTR}' "
                        "must be a boolean."
                    ),
                    at=enabled_attr,
                )
                return None
            if enabled_val is False:
                return None

        rel = prim.GetRelationship(_NEWTON_MIMIC_JOINT_REL)
        targets = rel.GetTargets() if rel else []
        if not targets:
            legacy_rel = prim.GetRelationship("mjc:target")
            targets = legacy_rel.GetTargets() if legacy_rel else []
        if len(targets) != 1:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo mimic joint '{prim.GetPath()}' must target exactly one leader joint via "
                    f"'{_NEWTON_MIMIC_JOINT_REL}', got {len(targets)}."
                ),
                at=prim,
            )
            return None

        leader_path = targets[0]
        if str(leader_path) == str(prim.GetPath()):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=f"MuJoCo mimic joint '{prim.GetPath()}' must not mimic itself.",
                at=prim,
            )
            return None

        leader_prim = stage.GetPrimAtPath(leader_path)
        if not leader_prim.IsValid() or not _is_scalar_articulation_joint(leader_prim):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo mimic joint '{prim.GetPath()}' targets '{leader_path}', "
                    "which is not a valid 1-DOF (revolute or prismatic) USD physics articulation joint."
                ),
                at=prim,
            )
            return None
        if not _has_applied_api_schema(leader_prim, _MUJOCO_JOINT_API):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo mimic joint '{prim.GetPath()}' targets leader joint '{leader_path}' "
                    "without MjcJointAPI."
                ),
                at=prim,
            )
            return None

        for attr_name in _NEWTON_MIMIC_COEF_ATTRS + ("mjc:coef0", "mjc:coef1") + _MUJOCO_EQUALITY_HIGHER_COEF_ATTRS:
            if not _has_authored_attr(prim, attr_name):
                continue
            if _as_finite_float(prim.GetAttribute(attr_name).Get()) is None:
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=f"MuJoCo mimic joint '{prim.GetPath()}' attribute '{attr_name}' must be a finite number.",
                    at=prim.GetAttribute(attr_name),
                )
                return None

        # Verify that the effective coupling consumed by the SDK has a non-zero dependence on the leader joint.
        # In _resolve_newton_mimic (import_usd.py), newton:mimicCoef1 takes precedence over legacy mjc:coef1
        # (defaulting to 1.0 when neither is authored) regardless of whether newton:mimicJoint or mjc:target
        # was used, and higher-order terms mjc:coef2..mjc:coef4 are only consumed when MjcEqualityJointAPI
        # is applied.
        if _has_authored_attr(prim, "newton:mimicCoef1"):
            coef1 = _as_finite_float(prim.GetAttribute("newton:mimicCoef1").Get())
        elif _has_authored_attr(prim, "mjc:coef1"):
            coef1 = _as_finite_float(prim.GetAttribute("mjc:coef1").Get())
        else:
            coef1 = 1.0
        higher_coefs = (
            [
                _as_finite_float(prim.GetAttribute(attr_name).Get()) or 0.0
                for attr_name in _MUJOCO_EQUALITY_HIGHER_COEF_ATTRS
                if _has_authored_attr(prim, attr_name)
            ]
            if _MUJOCO_EQUALITY_JOINT_API in schemas
            else []
        )
        if (coef1 is None or coef1 == 0.0) and all(c == 0.0 for c in higher_coefs):
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo mimic joint '{prim.GetPath()}' has zero coupling coefficients and does not transmit "
                    f"motion from leader joint '{leader_path}'."
                ),
                at=prim,
            )
            return None

        for attr_name in _MUJOCO_EQUALITY_ARRAY_ATTRS:
            if not _has_authored_attr(prim, attr_name):
                continue
            if not _is_numeric_sequence(prim.GetAttribute(attr_name).Get()):
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo mimic joint '{prim.GetPath()}' must author '{attr_name}' as a non-empty numeric array."
                    ),
                    at=prim.GetAttribute(attr_name),
                )
                return None

        return str(leader_path)

    def CheckStage(self, stage: Usd.Stage) -> None:
        mujoco_joints = []
        mujoco_actuators = []

        for prim in stage.Traverse():
            if _is_non_fixed_articulation_joint(prim) and _has_applied_api_schema(prim, _MUJOCO_JOINT_API):
                mujoco_joints.append(prim)
            if _is_mujoco_actuator(prim):
                mujoco_actuators.append(prim)

        if mujoco_joints and not mujoco_actuators:
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message="MuJoCo driven joints are present, but no MjcActuator prims target them.",
                at=stage.GetDefaultPrim() or stage.GetPseudoRoot(),
            )
            return

        targeted_joints: set[str] = set()
        for actuator_prim in mujoco_actuators:
            self._validate_actuator(stage, actuator_prim, targeted_joints)

        mimic_leader_by_follower: dict[str, str] = {}
        invalid_mimic_followers: set[str] = set()
        for joint_prim in mujoco_joints:
            joint_path = str(joint_prim.GetPath())
            if joint_path in targeted_joints:
                continue
            if _is_mujoco_mimic_follower(joint_prim):
                leader_path = self._validate_mimic_follower(stage, joint_prim)
                if leader_path is not None:
                    mimic_leader_by_follower[joint_path] = leader_path
                else:
                    invalid_mimic_followers.add(joint_path)

        # Resolve mimic chains: a follower is covered only if its leader chain
        # reaches an actuator-driven joint without cycles.
        actuated_joints = set(targeted_joints)
        for follower_path in list(mimic_leader_by_follower):
            visited: list[str] = [follower_path]
            curr = mimic_leader_by_follower[follower_path]
            while curr in mimic_leader_by_follower and curr not in visited and curr not in actuated_joints:
                visited.append(curr)
                curr = mimic_leader_by_follower[curr]
            if curr in actuated_joints:
                actuated_joints.update(visited)
            elif curr in visited:
                fprim = stage.GetPrimAtPath(follower_path)
                self._AddFailedCheck(
                    requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                    message=(
                        f"MuJoCo mimic joint '{follower_path}' is part of a cyclic or unactuated mimic reference "
                        f"chain ({' -> '.join(visited + [curr])})."
                    ),
                    at=fprim if fprim.IsValid() else stage.GetDefaultPrim() or stage.GetPseudoRoot(),
                )
                invalid_mimic_followers.add(follower_path)

        loop_joints = _closed_loop_articulation_joint_paths(stage, actuated_joints)

        for joint_prim in mujoco_joints:
            joint_path = str(joint_prim.GetPath())
            if joint_path in actuated_joints or joint_path in loop_joints or joint_path in invalid_mimic_followers:
                continue
            self._AddFailedCheck(
                requirement=self.MUJOCO_ACTUATOR_REQUIREMENT,
                message=(
                    f"MuJoCo joint '{joint_prim.GetPath()}' is not targeted by any MjcActuator prim "
                    "and is not coupled to an actuated leader joint by MjcEqualityJointAPI / NewtonMimicAPI. "
                    "Author an MjcActuator targeting the joint (or a fixed MjcTendon containing it), "
                    "couple it to an actuated leader joint with MjcEqualityJointAPI and NewtonMimicAPI, "
                    "or exclude a loop-closure joint from the articulation."
                ),
                at=joint_prim,
            )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_001, override=True)
class PhysicsDriveAndJointState(usd_validation_nvidia.BaseRuleChecker):
    """Validator to check physics driven joints for proper drive and joint state configuration."""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has proper drive and joint state configuration.

        Args:
            prim: The USD prim to validate.
        """
        drives, joint_states = GetJointDrivesAndJointStates(prim)
        if not drives:
            return
        is_mimic = prim.HasAPI("PhysxMimicJointAPI")
        stop = is_mimic
        if is_mimic:
            for drive, joint_state in zip(drives, joint_states):
                stiffness_attr = drive.GetStiffnessAttr()
                damping_attr = drive.GetDampingAttr()
                stiffness = stiffness_attr.Get() if stiffness_attr.IsValid() else None
                damping = damping_attr.Get() if damping_attr.IsValid() else None
                if (stiffness is not None and stiffness != 0.0) or (damping is not None and damping != 0.0):
                    stop = False
                    break
        if stop:
            return

        for drive, joint_state in zip(drives, joint_states):
            force_attr = drive.GetMaxForceAttr()
            if not force_attr.IsDefined():
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                    message=f"Drive Max Force is not set on <{prim.GetPath()}>",
                    at=force_attr,
                )
            else:
                raw_force = force_attr.Get()
                max_force = _as_finite_float(raw_force)
                if max_force is None:
                    if raw_force is None:
                        message = "Drive Max Force is not set"
                    elif raw_force in (float("inf"), -float("inf")):
                        message = "Drive Max Force is infinite"
                    else:
                        message = "Drive Max Force is not a finite number"
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                        message=f"{message} <{force_attr.GetPath()}>",
                        at=force_attr,
                    )
                elif max_force <= 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                        message=f"Drive Max Force is zero <{force_attr.GetPath()}>",
                        at=force_attr,
                    )
                drive_target_position = drive.GetTargetPositionAttr()
                drive_target_velocity = drive.GetTargetVelocityAttr()

                joint_state_position = joint_state.GetPositionAttr()
                joint_state_velocity = joint_state.GetVelocityAttr()

                tolerance = 1e-2
                for label, target_attr, state_attr in (
                    ("position", drive_target_position, joint_state_position),
                    ("velocity", drive_target_velocity, joint_state_velocity),
                ):
                    if not target_attr or not state_attr:
                        continue
                    target = _as_finite_float(target_attr.Get())
                    state = _as_finite_float(state_attr.Get())
                    if target is None or state is None:
                        invalid_attr = target_attr if target is None else state_attr
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                            message=f"Joint state {label} and drive target {label} must have finite values <{invalid_attr.GetPath()}>",
                            at=invalid_attr,
                        )
                        continue
                    difference = abs(target - state)
                    if difference > tolerance:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_001,
                            message=f"Joint state {label} is very different from drive target {label} <{target_attr.GetPath()}>: difference is {difference}",
                            at=target_attr,
                        )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_002, override=True)
class JointHasJointStateAPI(usd_validation_nvidia.BaseRuleChecker):
    """Validates that joints have the JointStateAPI applied.

    This rule checks that all joints (except fixed joints) have the PhysxSchema.JointStateAPI
    applied. The JointStateAPI is required for proper joint state tracking during simulation.
    """

    @classmethod
    def apply_api(cls, _: Usd.Stage, joint_prim: Usd.Prim) -> None:
        """Apply the appropriate JointStateAPI to a joint prim.

        Args:
            stage: The USD stage containing the joint.
            joint_prim: The joint prim to apply the API to.
        """
        actuator_type = None
        spec_stack = joint_prim.GetPrimStack()
        if spec_stack:
            defining_spec = spec_stack[-1]
            layer = defining_spec.layer
            from ...core.path_utils import delivered_asset_identifier

            if (
                delivered_asset_identifier(layer).lower().endswith(".usdz")
                or not layer.permissionToEdit
                or not layer.permissionToSave
            ):
                raise RuntimeError(
                    f"Cannot apply JointStateAPI fix to read-only layer '{layer.identifier}'. "
                    "Extract the package or author the correction in a writable override layer."
                )
            edit_stage = Usd.Stage.Open(layer.identifier)
            if edit_stage is None:
                raise RuntimeError(f"Could not open writable layer '{layer.identifier}' for correction")

            prim = edit_stage.GetPrimAtPath(defining_spec.path)

            if prim.IsA(UsdPhysics.PrismaticJoint):
                actuator_type = "linear"
            elif prim.IsA(UsdPhysics.RevoluteJoint):
                actuator_type = "angular"

            if PhysxSchema is None:
                raise RuntimeError("PhysxSchema is not available; cannot apply JointStateAPI fix")
            PhysxSchema.JointStateAPI.Apply(prim, actuator_type)
            edit_stage.Save()

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has the required JointStateAPI applied.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check JointStateAPI")
            return
        if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
            return

        actuator_type = None
        if prim.IsA(UsdPhysics.PrismaticJoint):
            actuator_type = "linear"
        elif prim.IsA(UsdPhysics.RevoluteJoint):
            actuator_type = "angular"
        # check if the joint api has a joint state api
        if actuator_type is None:
            return
        if not PhysxSchema.JointStateAPI(prim, actuator_type):
            self._AddFailedCheck(
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_002,
                message=f"{prim.GetPath()} Has no Joint State API",
                at=prim,
                suggestion=usd_validation_nvidia.Suggestion(message="Apply Joint State API", callable=self.apply_api),
            )
        else:
            return


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_003, override=True)
class JointHasCorrectTransformAndState(usd_validation_nvidia.BaseRuleChecker):
    """Validates that joint transforms and states are consistent with the connected bodies.

    This rule checks that the joint's transform and state values correctly define the
    relationship between the connected bodies. Inconsistencies can cause incorrect
    joint behavior during simulation.
    """

    joint_axis_map = {
        "X": Gf.Vec3d(1, 0, 0),
        "Y": Gf.Vec3d(0, 1, 0),
        "Z": Gf.Vec3d(0, 0, 1),
    }

    def CheckPrim(self, prim: Usd.Prim) -> None:
        # print(f"JointHasCorrectTransform: {prim.GetPath()}")
        joint = UsdPhysics.Joint(prim)

        if not joint:
            return

        if not (
            prim.IsA(UsdPhysics.RevoluteJoint)
            # or prim.IsA(UsdPhysics.SphericalJoint)
            or prim.IsA(UsdPhysics.PrismaticJoint)
            # or prim.IsA(UsdPhysics.FixedJoint)
        ):
            return

        stage = prim.GetStage()

        # Check if the bodies are valid
        b0paths = joint.GetBody0Rel().GetTargets()
        b1paths = joint.GetBody1Rel().GetTargets()

        if len(b0paths):
            if not stage.GetPrimAtPath(b0paths[0]).IsValid():
                return
        else:
            return

        if len(b1paths):
            if not stage.GetPrimAtPath(b1paths[0]).IsValid():
                return
        else:
            return

        # Get the expected transform
        cache = UsdGeom.XformCache()
        expected_tm_0 = get_world_body_transform(stage, cache, joint, False)
        expected_tm_1 = get_world_body_transform(stage, cache, joint, True)

        # Compute the joint state offset transform
        joint_state_transform = Gf.Transform()
        if prim.IsA(UsdPhysics.RevoluteJoint):
            jointState = PhysxSchema.JointStateAPI(prim, "angular")
            if jointState:
                revolute_joint = UsdPhysics.RevoluteJoint(prim)
                value = jointState.GetPositionAttr().Get()
                axis = revolute_joint.GetAxisAttr().Get()
                joint_state_transform.SetRotation(
                    Gf.Rotation(Gf.Vec3d(JointHasCorrectTransformAndState.joint_axis_map[str(axis)]), value)
                )
        if prim.IsA(UsdPhysics.PrismaticJoint):
            jointState = PhysxSchema.JointStateAPI(prim, "linear")
            if jointState:
                prismatic_joint = UsdPhysics.PrismaticJoint(prim)
                value = jointState.GetPositionAttr().Get()
                axis = prismatic_joint.GetAxisAttr().Get()
                joint_state_transform.SetTranslation(
                    Gf.Vec3d(JointHasCorrectTransformAndState.joint_axis_map[str(axis)]) * value
                )

        joint_state_pos_0 = joint_state_transform * expected_tm_0

        expected_state_pos_0 = joint_state_pos_0.GetTranslation()
        expected_pos_0 = expected_tm_0.GetTranslation()
        expected_pos_1 = expected_tm_1.GetTranslation()

        if not Gf.IsClose(expected_state_pos_0, expected_pos_1, 1e-4):
            if not Gf.IsClose(expected_pos_0, expected_pos_1, 1e-4):
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} position not well-defined ({(expected_pos_0 - expected_pos_1).GetLength()}). From body 0: {expected_pos_0}, from body 1: {expected_pos_1}",
                    at=prim,
                )
            else:
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} state not matching robot pose({(expected_state_pos_0 - expected_pos_1).GetLength()}). From body 0: {expected_state_pos_0}, from body 1: {expected_pos_1}",
                    at=prim,
                )

        # Check if the orientation is as expected (double-cover safe: q and -q same rotation)
        _ROT_TOL = 1e-3
        expected_state_rot_0 = joint_state_pos_0.GetRotation()
        expected_rot_0 = expected_tm_0.GetRotation()
        expected_rot_1 = expected_tm_1.GetRotation()
        q_state = expected_state_rot_0.GetQuat().GetNormalized()
        q0 = expected_rot_0.GetQuat().GetNormalized()
        q1 = expected_rot_1.GetQuat().GetNormalized()

        base_rot_match = _rotations_match_orientation(q0, q1, _ROT_TOL)
        state_rot_match = _rotations_match_orientation(q_state, q1, _ROT_TOL)

        if not state_rot_match:
            if not base_rot_match:
                mag = _rotation_error_magnitude(q0, q1)
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} Rotation not well defined ({mag}), From body 0: {expected_rot_0}, From body 1: {expected_rot_1}",
                    at=prim,
                )
            else:
                mag = _rotation_error_magnitude(q_state, q1)
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_003,
                    message=f"Joint {prim.GetPath()} state not matching robot pose ({mag}). From body 0: {expected_state_rot_0}, from body 1: {expected_rot_1}",
                    at=prim,
                )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_004, override=True)
class PhysicsJointHasDriveOrMimicAPI(usd_validation_nvidia.BaseRuleChecker):
    """Validates that joints have a drive or mimic API.

    This rule ensures that all joints (except fixed joints) have either a drive API
    or a mimic API configured. When both are present, revolute (and other non-prismatic)
    followers must zero drive gains so the mimic constraint owns the DOF. Prismatic
    followers must keep non-zero drive stiffness because PhysX does not enforce
    PhysxMimicJointAPI on linear DOFs.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has proper drive or mimic API configuration.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check drive or mimic API")
            return
        if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
            return
        drives, joint_states = GetJointDrivesAndJointStates(prim)
        has_mimic = prim.HasAPI("PhysxMimicJointAPI")
        exclude_from_articulation = UsdPhysics.Joint(prim).GetExcludeFromArticulationAttr().Get()
        if not drives and not has_mimic and not exclude_from_articulation:
            self._AddFailedCheck(
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_004,
                message=f"Joint {prim.GetPath()} has no drive or mimic API",
                at=prim,
            )
        if drives and has_mimic:
            is_prismatic = prim.IsA(UsdPhysics.PrismaticJoint)
            for drive in drives:
                stiffness_attr = drive.GetStiffnessAttr()
                damping_attr = drive.GetDampingAttr()
                stiffness = stiffness_attr.Get() if stiffness_attr.IsValid() else None
                damping = damping_attr.Get() if damping_attr.IsValid() else None
                has_nonzero_stiffness = stiffness is not None and stiffness != 0.0
                has_nonzero_gain = has_nonzero_stiffness or (damping is not None and damping != 0.0)
                if is_prismatic:
                    # PhysX does not enforce PhysxMimicJointAPI on prismatic DOFs; the
                    # follower drive is what couples the mechanism. Damping alone cannot
                    # hold a position target, so stiffness must be non-zero.
                    if not has_nonzero_stiffness:
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_004,
                            message=(
                                f"Joint {prim.GetPath()} is a prismatic mimic follower without "
                                "non-zero drive stiffness; PhysX does not enforce linear mimic, "
                                "so a positive follower drive stiffness is required"
                            ),
                            at=prim,
                        )
                elif has_nonzero_gain:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_004,
                        message=f"Joint {prim.GetPath()} has both drive and mimic API",
                        at=prim,
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_005, override=True)
class PhysicsJointMaxVelocity(usd_validation_nvidia.BaseRuleChecker):
    """Validates that joints have a positive max velocity set.

    This rule checks that joints with the PhysxJointAPI have a defined and positive
    max joint velocity, which is required for proper joint simulation.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has proper max joint velocity configuration.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check max joint velocity")
            return
        if prim.HasAPI("PhysxJointAPI"):
            joint = PhysxSchema.PhysxJointAPI(prim)
            attr = joint.GetMaxJointVelocityAttr()
            if not attr.IsDefined():
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_005,
                    message=f"Max joint velocity is not set on <{prim.GetPath()}>",
                    at=prim,
                )
            else:
                max_joint_velocity = attr.Get()
                if max_joint_velocity <= 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_005,
                        message=f"Max joint velocity is zero <{attr.GetPath()}>",
                        at=attr,
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_006, override=True)
class DriveJointValueReasonable(usd_validation_nvidia.BaseRuleChecker):
    """Validates that joint drive stiffness values are within reasonable ranges.

    This rule checks that joint drive stiffness values are within defined minimum and
    maximum limits to ensure stable simulation behavior.
    """

    DRIVE_STIFFNESS_MIN = 0.0
    DRIVE_STIFFNESS_MAX = 1000000.0  # 1e6 stiffness
    NATURAL_FREQUENCY_MIN = 0.0
    NATURAL_FREQUENCY_MAX = 500.0  # 500 Hz - warning threshold.

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim has reasonable drive stiffness values.

        Args:
            prim: The USD prim to validate.
        """
        drives, joint_states = GetJointDrivesAndJointStates(prim)
        is_mimic = PhysxSchema is not None and prim.HasAPI("PhysxMimicJointAPI")
        # PhysX does not enforce PhysxMimicJointAPI on prismatic DOFs, so prismatic
        # mimic followers keep a real drive and use the normal stiffness range checks.
        is_prismatic_mimic = is_mimic and prim.IsA(UsdPhysics.PrismaticJoint)
        for drive in drives:
            stiffness_attr = drive.GetStiffnessAttr()
            stiffness = (
                stiffness_attr.Get() if stiffness_attr.IsValid() and stiffness_attr.HasAuthoredValueOpinion() else None
            )
            if stiffness is None and (not is_mimic or is_prismatic_mimic):
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                    message=f"Drive stiffness is not set on <{drive.GetPath()}>",
                    at=stiffness_attr,
                )
                continue
            elif is_prismatic_mimic and stiffness == 0.0:
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                    message=(f"prismatic mimic joint requires non-zero drive stiffness " f"<{drive.GetPath()}>"),
                    at=stiffness_attr,
                )
            elif is_mimic and not is_prismatic_mimic:
                damping_attr = drive.GetDampingAttr()
                damping = (
                    damping_attr.Get() if damping_attr.IsValid() and damping_attr.HasAuthoredValueOpinion() else None
                )
                if damping is not None and damping != 0.0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                        message=f"joint is mimic but has damping set <{drive.GetPath()}>",
                        at=damping_attr,
                    )
                if stiffness is not None and stiffness != 0.0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                        message=f"joint is mimic but has stiffness set <{drive.GetPath()}>",
                        at=stiffness_attr,
                    )
            elif stiffness < self.DRIVE_STIFFNESS_MIN or stiffness > self.DRIVE_STIFFNESS_MAX:
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_006,
                    message=f"Drive stiffness is out of range <{drive.GetPath()}>: {stiffness}",
                    at=prim,
                )
            continue
            # TODO: Work in progress for natural frequency


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_007, override=True)
class MimicAPICheck(usd_validation_nvidia.BaseRuleChecker):
    """Validates proper configuration of mimic joint APIs.

    This rule checks that mimic joints have proper reference joints, gear ratios,
    natural frequencies, damping ratios, and compatible joint limits.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check if a prim with mimic API is properly configured.

        Args:
            prim: The USD prim to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check mimic joint API")
            return
        if not prim.HasAPI("PhysxMimicJointAPI"):
            return
        else:
            applied_schema = prim.GetAppliedSchemas()
            list_of_mimic_apis = []
            for schema in applied_schema:
                if schema.startswith("PhysxMimicJointAPI"):
                    list_of_mimic_apis.append(schema[19:])
            for axis in list_of_mimic_apis:
                if axis not in _MIMIC_AXES:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has unknown mimic axis: {axis}, aborting checks",
                        at=prim,
                    )
                    return
                mimic_api = PhysxSchema.PhysxMimicJointAPI(prim, axis)

                # For the mimic API, perform checks

                # reference joint check
                # USD relationship forwarding is legal. Cardinality and joint
                # validity apply to the resolved targets, not intermediary
                # relationship property paths.
                try:
                    reference_joint = mimic_api.GetReferenceJointRel().GetForwardedTargets()
                except Tf.ErrorException:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has an unresolvable reference joint relationship",
                        at=prim,
                    )
                    continue
                if not reference_joint or len(reference_joint) > 1:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has incorrect number of reference joints, expected: 1, actual: {len(reference_joint)}",
                        at=prim,
                    )
                    continue

                # self value checks
                gear_ratio = mimic_api.GetGearingAttr().Get()
                offset = mimic_api.GetOffsetAttr().Get()
                natural_frequency = prim.GetAttribute(f"physxMimicJoint:{axis}:naturalFrequency").Get()
                damping_ratio = prim.GetAttribute(f"physxMimicJoint:{axis}:dampingRatio").Get()

                if gear_ratio is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no gear ratio",
                        at=prim,
                    )

                if natural_frequency is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no natural frequency",
                        at=prim,
                    )

                if damping_ratio is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no damping ratio",
                        at=prim,
                    )

                if gear_ratio == 0:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has gear ratio == 0",
                        at=prim,
                    )

                if damping_ratio == 0:
                    self._AddInfo(message=f"Joint {prim.GetPath()} has damping ratio == 0", at=prim)

                # PhysX uses naturalFrequency <= 0 (including the schema
                # default zero) for a rigid constraint without compliance.
                for label, value in (("natural frequency", natural_frequency), ("damping ratio", damping_ratio)):
                    if value is not None and (not isinstance(value, (int, float)) or _as_finite_float(value) is None):
                        self._AddFailedCheck(
                            requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                            message=f"Joint {prim.GetPath()} has non-finite or invalid {label}: {value}",
                            at=prim,
                        )

                # An unauthored offset has the schema default zero. A blocked
                # value is unavailable, not permission to fabricate that default.
                finite_gearing = _as_finite_float(gear_ratio) if isinstance(gear_ratio, (int, float)) else None
                finite_offset = _as_finite_float(offset) if isinstance(offset, (int, float)) else None
                if gear_ratio is not None and finite_gearing is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has non-finite or invalid gear ratio: {gear_ratio}",
                        at=prim,
                    )
                if finite_offset is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has unavailable, non-finite or invalid mimic offset: {offset}",
                        at=prim,
                    )
                if finite_gearing is None or finite_gearing == 0 or finite_offset is None:
                    continue

                # limit checks
                self_joint_lower_limit, self_joint_upper_limit = get_prismatic_or_revolute_limits(prim)
                if self_joint_lower_limit is None or self_joint_upper_limit is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no limits",
                        at=prim,
                    )
                    continue

                # obtain the limits from the reference joint
                stage = prim.GetStage()
                reference_joint_prim = stage.GetPrimAtPath(reference_joint[0])
                if not reference_joint_prim or not reference_joint_prim.IsA(UsdPhysics.Joint):
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has invalid reference joint: {reference_joint[0]}",
                        at=prim,
                    )
                    continue
                reference_joint_lower_limit, reference_joint_upper_limit = get_prismatic_or_revolute_limits(
                    reference_joint_prim
                )
                if reference_joint_prim == prim:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} cannot mimic its own joint DOF",
                        at=prim,
                    )
                    continue
                if reference_joint_lower_limit is None or reference_joint_upper_limit is None:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has no limits",
                        at=prim,
                    )
                    continue

                # USD uses infinity for unlimited joint endpoints. Keep those
                # valid, but do not let NaN or reversed ranges silently pass.
                bounds = (
                    self_joint_lower_limit,
                    self_joint_upper_limit,
                    reference_joint_lower_limit,
                    reference_joint_upper_limit,
                )
                if (
                    any(
                        isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value)
                        for value in bounds
                    )
                    or self_joint_lower_limit > self_joint_upper_limit
                    or reference_joint_lower_limit > reference_joint_upper_limit
                    or self_joint_lower_limit == math.inf
                    or self_joint_upper_limit == -math.inf
                    or reference_joint_lower_limit == math.inf
                    or reference_joint_upper_limit == -math.inf
                ):
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()} has invalid or reversed mimic/reference joint limits",
                        at=prim,
                    )
                    continue

                # ensure the mimic joint and the reference joint are not excluded from articulation
                if reference_joint_prim.GetAttribute("physics:excludeFromArticulation").Get():
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Mimic joint {prim.GetPath()} has a reference joint {reference_joint_prim.GetPath()} that is excluded from articulation.. The mimic joint reference joint cannot be excluded from articulation.",
                        at=prim,
                    )
                    return
                if prim.GetAttribute("physics:excludeFromArticulation").Get():
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Mimic joint {prim.GetPath()} is excluded from articulation. The mimic joint cannot be excluded from articulation.",
                        at=prim,
                    )
                    return

                # PhysX: follower + gearing * reference + offset = 0.
                # Map both endpoints, sort for either gearing sign, and require
                # the whole reference sweep to fit inside the follower range.
                # Touching either authored boundary is legal.
                (expected_lower, lower_reference), (expected_upper, upper_reference) = sorted(
                    (
                        (-finite_gearing * reference_joint_lower_limit - finite_offset, reference_joint_lower_limit),
                        (-finite_gearing * reference_joint_upper_limit - finite_offset, reference_joint_upper_limit),
                    )
                )

                def at_float_boundary(mapped, boundary, reference, gearing=finite_gearing, offset=finite_offset):
                    # Joint endpoints, gearing and offset are USD float values.
                    # Bound their arithmetic roundoff, including cancellation;
                    # this is not a physical travel/penetration tolerance.
                    if not all(math.isfinite(value) for value in (mapped, boundary, reference)):
                        return False
                    roundoff = 2.0**-23 * (abs(gearing * reference) + abs(offset) + abs(boundary))
                    return math.isfinite(roundoff) and abs(mapped - boundary) <= roundoff

                if expected_lower < self_joint_lower_limit and not at_float_boundary(
                    expected_lower, self_joint_lower_limit, lower_reference
                ):
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()}'s mapped mimic lower limit ({expected_lower}) is below its lower limit ({self_joint_lower_limit})",
                        at=prim,
                    )
                if expected_upper > self_joint_upper_limit and not at_float_boundary(
                    expected_upper, self_joint_upper_limit, upper_reference
                ):
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_007,
                        message=f"Joint {prim.GetPath()}'s mapped mimic upper limit ({expected_upper}) is above its upper limit ({self_joint_upper_limit})",
                        at=prim,
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_008, override=True)
class JointsExist(usd_validation_nvidia.BaseRuleChecker):
    """Validates that robot assets contain at least one joint.

    This rule checks that robot assets have at least one prim with the JointAPI
    applied, which is typically required for articulated robots.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Skipped on rigid-body-only assets (vehicles, non-articulated props)
        # which are not expected to carry any isaac:physics:JointAPI.
        if not any(prim.IsA(UsdPhysics.Joint) for prim in stage.Traverse()):
            return
        if robot_schema is None:
            self._AddFailedCheck(
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_008,
                message=_ROBOT_SCHEMA_UNAVAILABLE,
                at=stage,
            )
            return

        for prim in stage.Traverse():
            if prim.HasAPI(robot_schema.Classes.JOINT_API.value):
                return
        self._AddFailedCheck(
            requirement=cap.PhysicsDrivenJointsRequirements.DJ_008,
            message=f"No joints found in robot asset <{stage.GetRootLayer().realPath}>",
            at=stage,
        )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_009, override=True)
class LinksExist(usd_validation_nvidia.BaseRuleChecker):
    """Validates that robot assets contain at least one link.

    This rule checks that robot assets have at least one prim with the LinkAPI
    applied, which is typically required for articulated robots.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Skipped on rigid-body-only assets (vehicles, non-articulated props)
        # which are not expected to carry any isaac:physics:LinkAPI.
        if not any(prim.IsA(UsdPhysics.Joint) for prim in stage.Traverse()):
            return
        if robot_schema is None:
            self._AddFailedCheck(
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_009,
                message=_ROBOT_SCHEMA_UNAVAILABLE,
                at=stage,
            )
            return

        for prim in stage.Traverse():
            if prim.HasAPI(robot_schema.Classes.LINK_API.value):
                return
        self._AddFailedCheck(
            requirement=cap.PhysicsDrivenJointsRequirements.DJ_009,
            message=f"No links found in robot asset <{stage.GetRootLayer().realPath}>",
            at=stage,
        )


def is_relationship_prepended(relationship) -> bool:
    """Check if a relationship is prepended in the layer stack.

    Examines the property stack of the relationship to determine if it uses
    prepended items rather than explicit items in the target path list.

    Args:
        relationship: The USD relationship to check.

    Returns:
        True if the relationship is prepended, False if it uses explicit items.
    """
    rel_stack = relationship.GetPropertyStack()
    return all(not spec.targetPathList.isExplicit for spec in rel_stack)


def make_relationship_prepended(relationship) -> bool:
    """Convert a relationship to use prepended items in the layer stack.

    Modifies the relationship's property specs to use prepended items instead of
    explicit items, which allows for composition with stronger layers.

    Args:
        relationship: The USD relationship to convert.

    Returns:
        True if the operation was successful.
    """
    rel_stack = relationship.GetPropertyStack()
    for spec in rel_stack:
        if spec.targetPathList.isExplicit:
            items = list(spec.targetPathList.explicitItems)
            spec.targetPathList.prependedItems = items
            spec.targetPathList.explicitItems = []
    return True


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_010, override=True)
class CheckRobotRelationships(usd_validation_nvidia.BaseRuleChecker):
    """Validates that robot relationships are properly defined and prepended.

    This rule checks that robot assets have the required robotLinks and robotJoints
    relationships defined and that they are prepended for proper composition.

    The suggestion callables below read the module-level ``robot_schema``, which
    ``CheckStage`` has already confirmed is importable before it reports any
    failure that offers one.
    """

    @classmethod
    def create_link_relationship(cls, stage, prim):
        """Create the robotLinks relationship on a prim.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim to create the relationship on.
        """
        relationship = prim.CreateRelationship(robot_schema.Relations.ROBOT_LINKS.name)

    @classmethod
    def create_joint_relationship(cls, stage, prim):
        """Create the robotJoints relationship on a prim.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim to create the relationship on.
        """
        relationship = prim.CreateRelationship(robot_schema.Relations.ROBOT_JOINTS.name)

    @classmethod
    def make_joint_relationship_prepended(cls, stage, prim):
        """Make the robotJoints relationship prepended for composition.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim with the relationship to modify.
        """
        relationship = prim.GetRelationship(robot_schema.Relations.ROBOT_JOINTS.name)
        make_relationship_prepended(relationship)

    @classmethod
    def make_link_relationship_prepended(cls, stage, prim):
        """Make the robotLinks relationship prepended for composition.

        Args:
            stage: The USD stage containing the prim.
            prim: The prim with the relationship to modify.
        """
        relationship = prim.GetRelationship(robot_schema.Relations.ROBOT_LINKS.name)
        make_relationship_prepended(relationship)

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check if robot relationships are properly configured.

        Args:
            stage: The USD stage to validate.
        """
        prim = stage.GetDefaultPrim()
        if not prim:
            self._AddFailedCheck(
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is not set",
                at=stage,
            )
            return

        if robot_schema is None:
            self._AddFailedCheck(
                requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
                message=_ROBOT_SCHEMA_UNAVAILABLE,
                at=stage,
            )
            return

        if prim.HasAPI(robot_schema.Classes.ROBOT_API.value):
            relationship_name_list = [robot_schema.Relations.ROBOT_LINKS.name, robot_schema.Relations.ROBOT_JOINTS.name]
            fix_methods = [self.create_link_relationship, self.create_joint_relationship]
            make_methods = [self.make_link_relationship_prepended, self.make_joint_relationship_prepended]
            for relationship_name, fix_method, make_method in zip(relationship_name_list, fix_methods, make_methods):
                relationship = prim.GetRelationship(relationship_name)
                if not relationship:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
                        message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a {relationship_name} relationship",
                        at=prim,
                        suggestion=usd_validation_nvidia.Suggestion(
                            message="Create relationship",
                            callable=fix_method,
                            at=usd_validation_nvidia.AuthoringLayers(prim),
                        ),
                    )
                    continue

                # Check if the relationship is prepended
                is_prepended = is_relationship_prepended(relationship)
                if not is_prepended:
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_010,
                        message=f"Relationship {relationship_name} is not prepended",
                        at=prim,
                        suggestion=usd_validation_nvidia.Suggestion(
                            message="Make relationship prepended", callable=make_method
                        ),
                    )


@usd_validation_nvidia.register_rule("PhysicsDrivenJoints")
@usd_validation_nvidia.register_requirements(cap.PhysicsDrivenJointsRequirements.DJ_011, override=True)
class ArticulationNoLoopsOrMultiJoint(usd_validation_nvidia.BaseRuleChecker):
    """Validates that the articulation has no loops and at most one joint between any two bodies.

    Only joints that participate in the articulation (excludeFromArticulation is not true)
    are considered. Joints with physics:excludeFromArticulation = true are skipped,
    so a loop is allowed if one of its joints is excluded from the articulation.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check that the body-joint graph has no cycles and at most one joint per body pair.

        Args:
            stage: The USD stage to validate.
        """
        pair_to_joints = defaultdict(list)
        adjacency = defaultdict(list)
        joint_to_bodies = {}

        for prim in stage.Traverse():
            if not UsdPhysics.Joint(prim) or UsdPhysics.FixedJoint(prim):
                continue
            joint = UsdPhysics.Joint(prim)
            if joint.GetExcludeFromArticulationAttr().Get():
                continue
            b0_targets = joint.GetBody0Rel().GetTargets()
            b1_targets = joint.GetBody1Rel().GetTargets()
            if not b0_targets or not b1_targets:
                continue
            path0 = b0_targets[0]
            path1 = b1_targets[0]
            if not stage.GetPrimAtPath(path0).IsValid() or not stage.GetPrimAtPath(path1).IsValid():
                continue
            key = (min(path0, path1), max(path0, path1))
            pair_to_joints[key].append(prim)
            joint_to_bodies[prim] = (path0, path1)

        for path0, path1 in pair_to_joints:
            adjacency[path0].append(path1)
            adjacency[path1].append(path0)

        for key, joints in pair_to_joints.items():
            if len(joints) > 1:
                joint_paths = ", ".join(str(p.GetPath()) for p in joints)
                self._AddFailedCheck(
                    requirement=cap.PhysicsDrivenJointsRequirements.DJ_011,
                    message=f"Multiple joints connect the same body pair {key[0]} -- {key[1]}: {joint_paths}\nOnly one joint per body pair is allowed, remove the extra joints.",
                    at=joints[0],
                )

        visited = set()

        def dfs_find_cycle(node, parent, stack):
            visited.add(node)
            stack.append(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    cycle = dfs_find_cycle(neighbor, node, stack)
                    if cycle is not None:
                        return cycle
                elif neighbor != parent:
                    idx = stack.index(neighbor)
                    return stack[idx:] + [neighbor]
            stack.pop()
            return None

        path_to_joint = {}
        for prim, (p0, p1) in joint_to_bodies.items():
            path_to_joint[(min(p0, p1), max(p0, p1))] = prim

        for body in adjacency:
            if body not in visited:
                stack = []
                cycle_bodies = dfs_find_cycle(body, None, stack)
                if cycle_bodies is not None:
                    cycle_joints = []
                    for i in range(len(cycle_bodies) - 1):
                        a, b = cycle_bodies[i], cycle_bodies[i + 1]
                        k = (min(a, b), max(a, b))
                        if k in path_to_joint:
                            cycle_joints.append(path_to_joint[k].GetPath())
                    self._AddFailedCheck(
                        requirement=cap.PhysicsDrivenJointsRequirements.DJ_011,
                        message=f"Articulation has a loop: bodies {cycle_bodies}; joints involved: {cycle_joints}\nEnable excludeFromArticulation on one of the joints in the loop to allow for loops.",
                        at=path_to_joint[
                            (min(cycle_bodies[0], cycle_bodies[1]), max(cycle_bodies[0], cycle_bodies[1]))
                        ],
                    )

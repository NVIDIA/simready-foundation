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
"""Z-axis gantry carrier for FET028 gripper tests.

Pattern adapted from FET005 (``fet005_grasp/grasp_robot.py``): instead
of teleporting the gripper articulation root via ``set_world_pose``
(which leaves the root velocity at 0 every step, so PhysX friction
can't transmit lift motion to held objects), we build a tiny PhysX
articulation that owns a Z-axis prismatic joint with a position drive.
The gripper's base body is rigidly attached to the prismatic's mover
via a ``FixedJoint``; driving the prismatic's target moves both the
gantry mover and the attached gripper smoothly. Held objects follow
via friction because PhysX integrates the prismatic motion with real
continuous velocity.

Build flow follows FET005's mid-test pattern:
  1. ``physics.stop()`` so PhysX re-cooks the articulation graph.
  2. Author the gantry USD: gantry_base (FixedJoint to world),
     gantry_z (PrismaticJoint Z to base, with drive), and an
     ``attach_joint`` FixedJoint between gantry_z and the gripper
     base. Both gantry bodies are co-located at the gripper base's
     current world pose so the FixedJoint identity-binds them.
  3. ``physics.play()`` -- PhysX picks up the new articulation and
     the cross-articulation FixedJoint as a regular joint constraint.

Detach is symmetric: stop, remove gantry prims, restore world pin if
it was present at attach time, restart.
"""

import asyncio
import hashlib
import math
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
    record_required_cleanup_failure,
)

# Gantry USD layout (kept under /World so it survives world.reset).
_GANTRY_ROOT = "/World/_FET028_Gantry"
_GANTRY_BASE = _GANTRY_ROOT + "/gantry_base"
_GANTRY_Z = _GANTRY_ROOT + "/gantry_z"
_ROOT_JOINT = _GANTRY_ROOT + "/root_joint"  # FixedJoint, world -> gantry_base
_JOINT_Z = _GANTRY_ROOT + "/joint_z"  # PrismaticJoint, base -> gantry_z
_ATTACH_JOINT = _GANTRY_ROOT + "/attach_joint"  # FixedJoint, gantry_z -> gripper_base


@dataclass
class CarrierHandle:
    """Persistent state for the gantry-driven carrier across a test run."""

    robot: Any  # RobotHandle wrapper around the gripper
    gripper_base_path: str
    physics: Any  # ctx.scene physics handle (for stop/play)
    initial_target_z: float  # joint_z drive target at attach time (always 0)
    world_pin_was_present: bool  # for detach to re-pin if we unpinned
    root_orientation_state: Any = None
    articulation_default_state: Any = None
    joint_default_state: Any = None
    physics_was_playing: bool = True
    root_path: str = _GANTRY_ROOT
    joint_z_path: str = _JOINT_Z
    world_pin_paths: tuple = ()
    # Last COMMANDED joint_z target (ramp reference for linear_translate/shake).
    # Tracked here because the rail-mode target is set via apply_action, not USD.
    last_target_z: float = 0.0
    active_physics_engine: str = "physx"
    prebuilt: bool = False
    asset_robot_root_path: str = ""
    suspended_root_schemas: Any = None
    carrier_robot: Any = None
    stationary: bool = False
    orientation_root_path: str = ""
    articulation_root_transfer: Any = None
    world_pin_states: Any = None
    # Generated PhysX rail's fixed world anchor. Controller pose semantics can
    # change from the gantry root to the moving body after a root transfer.
    rail_world_anchor: Any = None


def _carrier_asset_root(stage, robot, base_path):
    """Return a verified content boundary, independently of the API prim."""
    root = stage.GetPrimAtPath(robot.prim_path)
    base = stage.GetPrimAtPath(base_path)
    asset = getattr(robot, "asset_prim", None)
    if not root or not root.IsValid() or not base or not base.IsValid():
        raise RuntimeError("FET028 requires a valid articulation root and gripper base")
    if asset and asset.IsValid() and all(prim.GetPath().HasPrefix(asset.GetPath()) for prim in (root, base)):
        return str(asset.GetPath())
    if not root.IsA(UsdPhysics.Joint) and base.GetPath().HasPrefix(root.GetPath()):
        return str(root.GetPath())
    raise RuntimeError(
        "FET028 cannot resolve a loaded asset boundary containing the articulation root and gripper base"
    )


def _capture_edit_properties(stage, prim_path, names, metadata=()):
    """Snapshot edit-target opinions, including absence, without flattening composition."""
    target = stage.GetEditTarget()
    layer = target.GetLayer()
    spec_path = target.MapToSpecPath(Sdf.Path(prim_path))
    backup = Sdf.Layer.CreateAnonymous("fet028_restore.usda")
    Sdf.CreatePrimInLayer(backup, spec_path)
    prim_spec = layer.GetPrimAtPath(spec_path)
    state = {"layer": layer, "path": spec_path, "backup": backup, "properties": {}, "metadata": {}}
    state["missing_prims"] = [path for path in spec_path.GetPrefixes() if not layer.GetPrimAtPath(path)]
    for name in names:
        path = spec_path.AppendProperty(name)
        existed = bool(layer.GetPropertyAtPath(path))
        state["properties"][name] = existed
        if existed:
            Sdf.CopySpec(layer, path, backup, path)
    for name in metadata:
        state["metadata"][name] = (
            bool(prim_spec and prim_spec.HasInfo(name)),
            prim_spec.GetInfo(name) if prim_spec and prim_spec.HasInfo(name) else None,
        )
    return state


def _restore_edit_properties(state):
    layer, path = state["layer"], state["path"]
    prim_spec = layer.GetPrimAtPath(path)
    for name, existed in state["properties"].items():
        property_path = path.AppendProperty(name)
        if existed:
            Sdf.CopySpec(state["backup"], property_path, layer, property_path)
        elif prim_spec:
            property_spec = layer.GetPropertyAtPath(property_path)
            if property_spec:
                prim_spec.RemoveProperty(property_spec)
    for name, (existed, value) in state["metadata"].items():
        if prim_spec:
            if existed:
                prim_spec.SetInfo(name, value)
            else:
                prim_spec.ClearInfo(name)
    _prune_missing_edit_prims(state)


def _prune_missing_edit_prims(state):
    layer = state["layer"]
    for missing_path in reversed(state.get("missing_prims", ())):
        missing_spec = layer.GetPrimAtPath(missing_path)
        if missing_spec and not missing_spec.properties and not missing_spec.nameChildren:
            if set(missing_spec.ListInfoKeys()) <= {"specifier"}:
                if missing_spec.nameParent is None:
                    del layer.rootPrims[missing_spec.name]
                else:
                    del missing_spec.nameParent.nameChildren[missing_spec.name]


def _cleanup_carrier_opinions(root_orientation_state, root_transfer, pin_states):
    """Prune empty overs after all interacting restoration steps complete."""
    states = list((pin_states or {}).values())
    if root_transfer:
        states.append(root_transfer["opinions"])
    if root_orientation_state and "opinions" in root_orientation_state:
        states.append(root_orientation_state["opinions"])
    for state in states:
        _prune_missing_edit_prims(state)


def _transfer_joint_root_for_carrier(stage, robot, root_body_path, setup_state=None):
    """Rebind an inactive API-bearing world joint to its physical root body."""
    root = stage.GetPrimAtPath(robot.prim_path)
    if not root or not root.IsValid() or not root.IsA(UsdPhysics.Joint):
        return None
    body = stage.GetPrimAtPath(root_body_path)
    if not body or not body.IsValid() or not body.HasAPI(UsdPhysics.RigidBodyAPI):
        raise RuntimeError("FET028 root transfer requires a resolved rigid body")
    if body.HasAPI(UsdPhysics.ArticulationRootAPI):
        raise RuntimeError("FET028 cannot transfer root ownership onto another articulation root")
    setting_names = sorted(
        {
            attr.GetName()
            for prim in (root, body)
            for attr in prim.GetAttributes()
            if attr.GetName().startswith("physxArticulation:") and attr.HasAuthoredValueOpinion()
        }
    )
    state = {
        "robot_path": robot.prim_path,
        "body_path": str(root_body_path),
        "opinions": _capture_edit_properties(stage, root_body_path, setting_names, ("apiSchemas",)),
    }
    if setup_state is not None:
        setup_state["articulation_root_transfer"] = state
    try:
        UsdPhysics.ArticulationRootAPI.Apply(body)
        if not body.HasAPI(UsdPhysics.ArticulationRootAPI):
            raise RuntimeError("FET028 root transfer is overridden by a stronger USD opinion")
        if "PhysxArticulationAPI" in root.GetAppliedSchemas():
            body.AddAppliedSchema("PhysxArticulationAPI")
            if "PhysxArticulationAPI" not in body.GetAppliedSchemas():
                raise RuntimeError("FET028 PhysX root transfer is overridden by a stronger USD opinion")
        for name in setting_names:
            attr = root.GetAttribute(name)
            # Copy the resolved property, including blocks and time samples.
            # Selective Set calls would leave stale destination defaults or
            # samples active and silently change the articulation settings.
            if attr:
                # A schema fallback on the old root takes precedence over an
                # otherwise dormant authored setting on the destination body.
                copied = attr.FlattenTo(body)
                value = attr.Get()
                times = attr.GetTimeSamples()
            else:
                copied = body.GetAttribute(name)
                copied.Block()
                value = None
                times = []
            if not copied:
                raise RuntimeError(f"FET028 could not transfer articulation setting {name}")
            if (
                copied.Get() != value
                or copied.GetTimeSamples() != times
                or any(copied.Get(time) != attr.Get(time) for time in times)
            ):
                raise RuntimeError(f"FET028 articulation setting is overridden by a stronger USD opinion: {name}")
        robot.set_articulation_root_path(root_body_path)
    except BaseException as error:
        try:
            _restore_carrier_root_transfer(stage, robot, state)
        except BaseException as restore_error:
            note_secondary_error(
                error, lambda restore_error=restore_error: f"FET028 root transfer restoration failed: {restore_error!r}"
            )
        raise
    return state


def _restore_carrier_root_transfer(stage, robot, state):
    if state is None:
        return
    _restore_edit_properties(state["opinions"])
    robot.set_articulation_root_path(state["robot_path"])


def _gantry_paths(root_path):
    joint_name = "joint_z"
    if root_path != _GANTRY_ROOT:
        digest = hashlib.sha256(str(root_path).encode("utf-8")).hexdigest()[:12]
        joint_name = f"_fet028_carrier_z_{digest}"
    return {
        "root": root_path,
        "base": root_path + "/gantry_base",
        "z": root_path + "/gantry_z",
        "root_joint": root_path + "/root_joint",
        "joint_z": root_path + "/" + joint_name,
        "attach_joint": root_path + "/attach_joint",
    }


def build_precompiled_carrier(
    stage,
    root_path: str,
    root_body_path: str,
    base_world_pos,
    active_physics_engine: str,
):
    """Author the merged FET028 carrier before the first physics cook."""
    _build_gantry(
        stage,
        root_body_path,
        base_world_pos,
        merge_into_articulation=True,
        root_path=root_path,
        active_physics_engine=active_physics_engine,
        # Keep a distinct moving rail body and fixed attachment. Connecting the
        # prismatic directly to the gripper root changes Newton's reduction of
        # the gripper linkage and pins its master drive.
        direct_precompiled_rail=False,
    )
    paths = _gantry_paths(root_path)
    return paths["base"], paths["joint_z"]


def build_in_place_newton_carrier(
    stage,
    namespace_path: str,
    articulation_root_path: str,
    root_body_path: str,
    root_body_world_position,
    root_body_world_orientation_wxyz,
):
    """Add a world-Z lift DOF without migrating the asset articulation root.

    Newton closed-loop grippers must retain the articulation root under which
    their joint coordinates and mimic constraints were compiled.  Making a
    sibling test carrier the root changes that reduction and can lock an
    otherwise valid hand at a non-authored configuration.  This carrier instead
    deactivates the asset's fixed world pin (handled by the caller), authors a
    test-owned rigid base fixed to world, and connects that base directly to the
    asset root body with one prismatic joint under the existing asset root.

    The fixed carrier base owns the already-authored gripper approach
    orientation.  The prismatic joint uses identity frames on both bodies, so
    the gripper root inherits that orientation while translating along the
    carrier base's local Z axis.  For a top-down grasp that local axis points
    along world -Z.
    """
    UsdGeom.Scope.Define(stage, namespace_path)
    base_path = namespace_path + "/gantry_base"
    root_joint_path = namespace_path + "/root_joint"
    joint_path = _gantry_paths(namespace_path)["joint_z"]
    actuator_path = joint_path + "_actuator"

    position = tuple(float(value) for value in root_body_world_position)
    orientation = tuple(float(value) for value in root_body_world_orientation_wxyz)
    if len(position) != 3:
        raise ValueError("root body world position must contain three values")
    if len(orientation) != 4:
        raise ValueError("root body world orientation must be a wxyz quaternion")

    # Newton does not expose a world-to-root-body prismatic joint as an
    # articulation DOF.  Give the rail an explicit root body, fixed to world,
    # then connect that body directly to the asset's original root body.  Both
    # bodies now belong to the same existing articulation and no cross-root
    # fixed attachment is needed.
    quat = Gf.Quatd(orientation[0], Gf.Vec3d(*orientation[1:])).GetNormalized()
    quat_imag = quat.GetImaginary()
    quat_f = Gf.Quatf(
        float(quat.GetReal()),
        Gf.Vec3f(float(quat_imag[0]), float(quat_imag[1]), float(quat_imag[2])),
    )

    base_xform = UsdGeom.Xform.Define(stage, base_path)
    base_xform.AddTranslateOp().Set(Gf.Vec3d(*position))
    base_xform.AddOrientOp().Set(quat_f)
    base_prim = base_xform.GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(base_prim)
    base_mass = UsdPhysics.MassAPI.Apply(base_prim)
    base_mass.CreateMassAttr(1.0)
    base_mass.CreateCenterOfMassAttr(Gf.Vec3f(0.0, 0.0, 0.0))
    base_mass.CreateDiagonalInertiaAttr(Gf.Vec3f(1.0e-3, 1.0e-3, 1.0e-3))
    base_mass.CreatePrincipalAxesAttr(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))

    root_joint = UsdPhysics.FixedJoint.Define(stage, root_joint_path)
    root_joint.CreateBody1Rel().SetTargets([base_path])
    root_joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*position))
    root_joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    # With body0 omitted, local frame 0 is a world-space frame.  Give that
    # frame the desired approach rotation so this fixed joint does not force
    # the carrier base back to identity orientation during Newton reduction.
    root_joint.CreateLocalRot0Attr().Set(quat_f)
    root_joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))

    joint_z = UsdPhysics.PrismaticJoint.Define(stage, joint_path)
    joint_z.CreateAxisAttr().Set(UsdPhysics.Tokens.z)
    joint_z.CreateBody0Rel().SetTargets([base_path])
    joint_z.CreateBody1Rel().SetTargets([root_body_path])
    joint_z.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    joint_z.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    # Both bodies must share the carrier base orientation.  Identity joint
    # frames preserve that relative rotation and make the prismatic axis the
    # base's local Z (world -Z for the normal top-down FET028 pose).
    joint_z.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
    joint_z.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
    joint_z.CreateLowerLimitAttr().Set(-1.0)
    joint_z.CreateUpperLimitAttr().Set(1.0)
    joint_z.CreateBreakForceAttr().Set(1.0e6)
    joint_z.CreateBreakTorqueAttr().Set(1.0e6)
    joint_z.GetPrim().SetMetadata(
        "apiSchemas",
        Sdf.TokenListOp.Create(prependedItems=["NewtonJointAPI", "PhysicsJointStateAPI:linear"]),
    )

    actuator = stage.DefinePrim(actuator_path, "NewtonActuator")
    actuator.ApplyAPI("NewtonPDControlAPI")
    actuator.ApplyAPI("NewtonMaxEffortClampingAPI")
    actuator.CreateRelationship("newton:targets").SetTargets([joint_path])
    actuator.CreateAttribute("newton:kp", Sdf.ValueTypeNames.Float).Set(1000.0)
    actuator.CreateAttribute("newton:kd", Sdf.ValueTypeNames.Float).Set(125.0)
    actuator.CreateAttribute("newton:maxEffort", Sdf.ValueTypeNames.Float).Set(1000.0)

    return articulation_root_path, joint_path


def _physics_is_playing(physics):
    for name in ("is_playing", "is_simulating"):
        method = getattr(physics, name, None)
        if callable(method):
            try:
                return bool(method())
            except Exception:
                pass
    return True


def _capture_root_orientation(stage, root_prim_path):
    prim = stage.GetPrimAtPath(root_prim_path)
    if not prim or not prim.IsValid():
        return None
    orient = prim.GetAttribute("xformOp:orient")
    order = prim.GetAttribute("xformOpOrder")
    return {
        "opinions": _capture_edit_properties(
            stage, root_prim_path, ("xformOp:orient", "xformOp:transform:fet028Approach", "xformOpOrder")
        ),
        "orient_existed": bool(orient and orient.HasAuthoredValueOpinion()),
        "orient_value": orient.Get() if orient and orient.HasAuthoredValueOpinion() else None,
        "order_existed": bool(order and order.HasAuthoredValueOpinion()),
        "order_value": order.Get() if order and order.HasAuthoredValueOpinion() else None,
    }


def _restore_root_orientation(stage, root_prim_path, state):
    if state is None:
        return
    if "opinions" in state:
        _restore_edit_properties(state["opinions"])
        return
    prim = stage.GetPrimAtPath(root_prim_path)
    if not prim or not prim.IsValid():
        return
    if state["orient_existed"]:
        prim.GetAttribute("xformOp:orient").Set(state["orient_value"])
    else:
        prim.RemoveProperty("xformOp:orient")
    if state["order_existed"]:
        prim.GetAttribute("xformOpOrder").Set(state["order_value"])
    else:
        prim.RemoveProperty("xformOpOrder")


def _capture_default_state(articulation):
    getter = getattr(articulation, "get_default_state", None)
    if not callable(getter):
        return None
    try:
        state = getter()
        return (getattr(state, "position", None), getattr(state, "orientation", None))
    except Exception:
        return None


def _restore_default_state(articulation, state):
    if state is None:
        return
    kwargs = {}
    if state[0] is not None:
        kwargs["position"] = state[0]
    if state[1] is not None:
        kwargs["orientation"] = state[1]
    if kwargs:
        articulation.set_default_state(**kwargs)


def _capture_joint_default_state(articulation):
    getter = getattr(articulation, "get_joints_default_state", None)
    if not callable(getter):
        return None
    try:
        state = getter()
        return (
            getattr(state, "positions", None),
            getattr(state, "velocities", None),
            getattr(state, "efforts", None),
        )
    except Exception:
        return None


def _restore_joint_default_state(articulation, state):
    setter = getattr(articulation, "set_joints_default_state", None)
    if state is None or not callable(setter):
        return
    kwargs = {}
    for name, value in zip(("positions", "velocities", "efforts"), state, strict=False):
        if value is not None:
            kwargs[name] = value
    if kwargs:
        setter(**kwargs)


def _joint_body_paths(stage, joint_prim):
    joint = UsdPhysics.Joint(joint_prim)
    result = []
    for relationship in (joint.GetBody0Rel(), joint.GetBody1Rel()):
        targets = relationship.GetForwardedTargets()
        if len(targets) > 1:
            raise RuntimeError(f"FET028 joint endpoint has multiple targets: {joint_prim.GetPath()}")
        if targets and not stage.GetPrimAtPath(targets[0]).IsValid():
            raise RuntimeError(f"FET028 joint endpoint is missing: {targets[0]}")
        result.append(_owning_rigid_body_path(stage, targets[0]) if targets else None)
    return tuple(result)


def _asset_joint_prims(stage, asset_root_path):
    root = stage.GetPrimAtPath(asset_root_path)
    if not root or not root.IsValid():
        return []
    return [prim for prim in Usd.PrimRange(root) if prim.IsA(UsdPhysics.Joint)]


def _articulation_body_paths(stage, root_body_path, asset_root_path):
    """Connected rigid-body graph, bounded by the verified loaded asset."""
    adjacency = {}
    for prim in _asset_joint_prims(stage, asset_root_path):
        joint = UsdPhysics.Joint(prim)
        if joint.GetJointEnabledAttr().Get() is False or joint.GetExcludeFromArticulationAttr().Get():
            continue
        b0, b1 = _joint_body_paths(stage, prim)
        if b0 and b1 and all(_path_is_at_or_below(path, asset_root_path) for path in (b0, b1)):
            adjacency.setdefault(b0, set()).add(b1)
            adjacency.setdefault(b1, set()).add(b0)
    bodies = {str(root_body_path)}
    pending = list(bodies)
    while pending:
        for other in adjacency.get(pending.pop(), ()):
            if other not in bodies:
                bodies.add(other)
                pending.append(other)
    return bodies


def _resolve_articulation_root_body(stage, robot_prim_path: str, asset_root_path=None):
    """Return the USD path of the articulation's ROOT rigid body, or None.

    A body-root API identifies that body. A world-joint API identifies its one
    rigid-body endpoint, which may be a sibling of the API prim. For a container
    API, a unique enabled fixed-to-world joint identifies its rigid endpoint,
    regardless of whether that endpoint is ``body0`` or ``body1``. Joint body
    relationship direction alone does not identify the root of a pinned tree.
    Competing world anchors are ambiguous. Without an anchor, retain the
    conventional ``body0`` parent / ``body1`` child fallback only for a connected,
    unambiguous tree wholly inside the container and loaded asset.

    The gantry must weld to THIS body. Welding to a non-root link that is itself
    rigidly fixed-jointed to the floating root (e.g. the SVH hand's
    ``left_hand_base_link`` -> ``left_hand_base_joint`` -> ``base_link``) adds a
    maximal-coordinate constraint redundant with the articulation's internal
    fixed joint; PhysX cannot solve the resulting loop for a floating base and
    explodes to non-finite bounds. For single-root-body grippers (ezu: the
    gripper base IS the root body) this returns that same body, so the weld is
    unchanged.

    Returns None when the root is ambiguous or cannot be resolved. Callers must
    not substitute a site body, which may be a non-root articulation link.
    """
    root = stage.GetPrimAtPath(robot_prim_path)
    if (
        not root
        or not root.IsValid()
        or not root.IsActive()
        or (asset_root_path is not None and not _path_is_at_or_below(root.GetPath(), asset_root_path))
    ):
        return None
    if root.HasAPI(UsdPhysics.RigidBodyAPI):
        return str(root.GetPath())
    if root.IsA(UsdPhysics.Joint):
        body_paths = _joint_body_paths(stage, root)
        candidates = [path for path in body_paths if path]
        if len(candidates) != 1:
            return None
        body = candidates[0]
        return body if asset_root_path is None or _path_is_at_or_below(body, asset_root_path) else None
    prims = list(Usd.PrimRange(root))
    bodies = {str(prim.GetPath()) for prim in prims if prim.HasAPI(UsdPhysics.RigidBodyAPI)}
    world_anchors = []
    child_links = set()
    adjacency = {body: set() for body in bodies}
    edge_count = 0
    for prim in prims:
        if prim.IsA(UsdPhysics.Joint):
            joint = UsdPhysics.Joint(prim)
            if joint.GetJointEnabledAttr().Get() is False or joint.GetExcludeFromArticulationAttr().Get():
                continue
            b0, b1 = _joint_body_paths(stage, prim)
            if any(body and body not in bodies for body in (b0, b1)):
                return None
            if prim.IsA(UsdPhysics.FixedJoint) and (not b0 or not b1):
                endpoints = [body for body in (b0, b1) if body]
                if len(endpoints) != 1:
                    return None
                world_anchors.append(endpoints[0])
            if b0 and b1:
                if b0 == b1:
                    return None
                child_links.add(b1)
                adjacency[b0].add(b1)
                adjacency[b1].add(b0)
                edge_count += 1
    if world_anchors:
        return world_anchors[0] if len(world_anchors) == 1 else None
    candidates = [b for b in bodies if b not in child_links]
    if len(candidates) != 1 or edge_count != len(bodies) - 1:
        return None
    connected = {candidates[0]}
    pending = list(connected)
    while pending:
        for body in adjacency[pending.pop()]:
            if body not in connected:
                connected.add(body)
                pending.append(body)
    return candidates[0] if connected == bodies else None


async def _rollback_partial_carrier(stage, robot, physics, setup_state, ctx=None):
    """Best-effort rollback for a failed carrier attachment.

    A successful physics stop is a hard prerequisite for topology restoration.
    After it, every independent restoration step is attempted. The returned
    errors are secondary diagnostics; callers must preserve and re-raise the
    attachment failure that triggered the rollback.
    """
    if not setup_state.get("physics_stopped"):
        # Pose/discovery failures precede every carrier mutation. Do not stop a
        # healthy timeline just to "restore" an unchanged fixture/controller.
        return []
    errors = []

    def _attempt(operation):
        try:
            operation()
        except BaseException as exc:
            errors.append(exc)
            record_required_cleanup_failure(ctx, "Required FET028 carrier restoration failed.", exc)

    try:
        physics.stop()
    except BaseException as exc:
        record_required_cleanup_failure(ctx, "Required FET028 carrier physics stop failed.", exc)
        if not isinstance(exc, Exception):
            raise
        error = RuntimeError(
            "FET028 carrier restoration could not stop physics; topology, "
            "controller bindings and timeline restart were left untouched. "
            "The runner must retry teardown or retire the disposable stage."
        )
        error.__cause__ = exc
        return [error]
    _attempt(lambda: _remove_existing_gantry(stage, setup_state["root_path"]))
    _attempt(
        lambda: _restore_root_orientation(
            stage, setup_state.get("orientation_root_path", robot.prim_path), setup_state["root_orientation_state"]
        )
    )
    _attempt(lambda: _restore_carrier_root_transfer(stage, robot, setup_state.get("articulation_root_transfer")))
    _attempt(lambda: _restore_default_state(robot.articulation, setup_state["articulation_default_state"]))
    _attempt(lambda: _restore_joint_default_state(robot.articulation, setup_state["joint_default_state"]))
    pin_paths = setup_state.get("world_pin_paths", ())
    if pin_paths:
        _attempt(lambda: _require_world_pin_restore(stage, pin_paths, setup_state.get("world_pin_states")))
    _attempt(
        lambda: _cleanup_carrier_opinions(
            setup_state.get("root_orientation_state"),
            setup_state.get("articulation_root_transfer"),
            setup_state.get("world_pin_states"),
        )
    )

    # Rebind the controller after every topology-changing stop, even if the
    # caller's timeline was already stopped. Restoring only the USD/API path
    # would leave its native articulation view bound to the temporary root.
    if setup_state.get("physics_stopped"):
        _attempt(physics.play)
        try:
            await robot.initialize(ctx)
        except BaseException as exc:
            errors.append(exc)
            record_required_cleanup_failure(ctx, "Required FET028 carrier reinitialization failed.", exc)
        else:
            _attempt(lambda: _restore_default_state(robot.articulation, setup_state["articulation_default_state"]))
            _attempt(lambda: _restore_joint_default_state(robot.articulation, setup_state["joint_default_state"]))
            world = getattr(robot, "_world", None)
            if world is None:
                errors.append(RuntimeError("robot initialization did not provide a World instance"))
            else:
                try:
                    await world.reset_async()
                except BaseException as exc:
                    errors.append(exc)
                    record_required_cleanup_failure(ctx, "Required FET028 carrier reset failed.", exc)
    if setup_state["physics_was_playing"]:
        _attempt(physics.play)
    else:
        _attempt(physics.stop)
    return errors


def _require_world_pin_restore(stage, pin_paths, pin_states=None):
    failed = []
    first_error = None
    for pin_path in pin_paths:
        try:
            if not _restore_world_pin(stage, pin_path, (pin_states or {}).get(pin_path)):
                failed.append(pin_path)
        except BaseException as error:
            if first_error is None:
                first_error = error
            else:
                note_secondary_error(first_error, lambda error=error: f"Another world-pin restoration failed: {error}")
    if first_error is not None:
        raise first_error
    if failed:
        raise RuntimeError("failed to restore suspended FET028 world pin(s): %s" % ", ".join(failed))


async def _finish_carrier_restore(stage, robot, physics, setup_state, ctx=None, propagate_cancel=True):
    task = asyncio.create_task(_rollback_partial_carrier(stage, robot, physics, setup_state, ctx=ctx))
    cancellation = None
    while True:
        try:
            errors = await asyncio.shield(task)
            break
        except asyncio.CancelledError as error:
            cancellation = error
            if task.cancelled():
                errors = [RuntimeError("FET028 carrier restoration was cancelled")]
                break
    if cancellation is not None and propagate_cancel:
        record_required_cleanup_failure(ctx, "Required FET028 carrier restoration was interrupted.", cancellation)
        raise cancellation
    if errors:
        record_required_cleanup_failure(ctx, "Required FET028 carrier restoration failed.", errors[0])
    if propagate_cancel:
        for error in errors:
            if not isinstance(error, Exception):
                raise error
    return errors


async def attach_carrier(
    stage, scene_info, robot, gripper_base_path: str, base_orient_wxyz=None, ctx=None, merge_rail: bool = False
) -> CarrierHandle:
    """Attach a uniquely namespaced carrier and roll back partial setup."""
    physics = scene_info["physics"]
    if scene_info.get("stationary_gripper_load_test"):
        return CarrierHandle(
            robot=robot,
            gripper_base_path=gripper_base_path,
            physics=physics,
            initial_target_z=0.0,
            world_pin_was_present=False,
            root_orientation_state=None,
            articulation_default_state=_capture_default_state(robot.articulation),
            joint_default_state=_capture_joint_default_state(robot.articulation),
            physics_was_playing=True,
            root_path=robot.prim_path,
            joint_z_path="",
            active_physics_engine=str(scene_info.get("active_physics_engine") or "newton"),
            prebuilt=True,
            asset_robot_root_path=robot.prim_path,
            stationary=True,
        )
    prebuilt = scene_info.get("prebuilt_gripper_carrier")
    if prebuilt is not None:
        if prebuilt.get("gripper_base_path") != gripper_base_path:
            raise RuntimeError(
                "Prebuilt FET028 carrier targets {}, but the phase resolved {}.".format(
                    prebuilt.get("gripper_base_path"), gripper_base_path
                )
            )
        return CarrierHandle(
            robot=robot,
            gripper_base_path=gripper_base_path,
            physics=physics,
            initial_target_z=0.0,
            world_pin_was_present=bool(prebuilt.get("world_pin_paths")),
            root_orientation_state=prebuilt.get("root_orientation_state"),
            articulation_default_state=_capture_default_state(robot.articulation),
            joint_default_state=_capture_joint_default_state(robot.articulation),
            physics_was_playing=True,
            root_path=prebuilt["root_path"],
            joint_z_path=prebuilt["joint_z_path"],
            world_pin_paths=tuple(prebuilt.get("world_pin_paths") or ()),
            active_physics_engine=str(scene_info.get("active_physics_engine") or "physx"),
            prebuilt=True,
            asset_robot_root_path=str(prebuilt.get("asset_robot_root_path") or ""),
            suspended_root_schemas=prebuilt.get("suspended_root_schemas"),
            carrier_robot=None,
        )
    root_path = "/World/_FET028_Gantry_%s" % uuid4().hex[:8]
    asset_root_path = _carrier_asset_root(stage, robot, gripper_base_path)
    root_body_path = _resolve_articulation_root_body(stage, robot.prim_path, asset_root_path)
    if not root_body_path:
        raise RuntimeError(f"FET028 cannot resolve an unambiguous articulation root body for {robot.prim_path}")
    body_paths = _articulation_body_paths(stage, root_body_path, asset_root_path)
    if _owning_rigid_body_path(stage, gripper_base_path) not in body_paths:
        raise RuntimeError("FET028 gripper base does not belong to the selected articulation")
    orientation_root_path = (
        _carrier_orientation_root(stage, asset_root_path, body_paths) if base_orient_wxyz is not None else ""
    )
    setup_state = {
        "root_path": root_path,
        "asset_root_path": asset_root_path,
        "asset_robot_root_path": robot.prim_path,
        "root_body_path": root_body_path,
        "orientation_root_path": orientation_root_path,
        "physics_was_playing": _physics_is_playing(physics),
        "physics_stopped": False,
        "root_orientation_state": (
            _capture_root_orientation(stage, orientation_root_path) if orientation_root_path else None
        ),
        "articulation_default_state": _capture_default_state(robot.articulation),
        "joint_default_state": _capture_joint_default_state(robot.articulation),
        "world_pin_paths": (),
    }
    try:
        return await _attach_carrier_impl(
            stage,
            scene_info,
            robot,
            gripper_base_path,
            base_orient_wxyz=base_orient_wxyz,
            ctx=ctx,
            merge_rail=merge_rail,
            setup_state=setup_state,
        )
    except BaseException as attachment_error:
        # Task cancellation is also an interrupted topology mutation. Shield
        # restoration and finish it before propagating the original failure.
        try:
            rollback_errors = await _finish_carrier_restore(
                stage, robot, physics, setup_state, ctx=ctx, propagate_cancel=False
            )
        except BaseException as restoration_error:
            rollback_errors = [restoration_error]
        for error in rollback_errors:
            note_secondary_error(
                attachment_error, lambda secondary=error: "FET028 carrier rollback failed: %r" % secondary
            )
            try:
                if ctx is not None:
                    ctx.warn("FET028 carrier rollback step failed: %r" % error)
            except BaseException as diagnostic_error:
                # Cleanup diagnostics must not replace the original failure,
                # including the cancellation that interrupted attachment.
                note_secondary_error(
                    attachment_error,
                    lambda secondary=diagnostic_error: "Carrier rollback warning was unavailable: %r" % secondary,
                )
        raise


async def _attach_carrier_impl(
    stage,
    scene_info,
    robot,
    gripper_base_path: str,
    base_orient_wxyz=None,
    ctx=None,
    merge_rail: bool = False,
    setup_state=None,
) -> CarrierHandle:
    """Build the Z-axis gantry and attach it to the gripper's base body.

    Side effects (in order):
      - ``physics.stop()`` so PhysX re-cooks the articulation graph.
      - Temporarily deactivates the framework's world-pin FixedJoint (it
        would over-constrain the gripper -- the gantry constrains it now).
      - Authors the gantry USD prims and joints under a unique per-run
        ``/World/_FET028_Gantry_<suffix>`` namespace.
      - ``physics.play()`` to restart simulation.
      - Authors the bounded gripper orientation before the new graph cooks.
        An existing floating-root controller also receives that physical
        root's pose as its reset default. A freshly initialized controller
        instead captures its own authored root defaults; a merged rail's root
        is the fixed gantry, not the oriented gripper.
      - Re-initializes after changing controller ownership or DOF count;
        otherwise uses ``world.reset_async()`` to re-cook the graph. Without this
        re-cook, the existing gripper's tensor view (built when
        ``RobotHandle.initialize`` originally ran) is left stale by the
        stop/play cycle and downstream calls like
        ``ParallelGripper.initialize`` see ``robot.dof_names`` empty or
        out-of-date -- the next ``parallel_gripper.forward`` returns
        ``None`` and the test crashes with
        ``'NoneType' object has no attribute 'joint_positions'``.

    The gripper's authored physics materials are kept as-is. If the
    asset doesn't author friction on the finger pads, that's an asset
    compliance issue (FET006 covers it) -- this test should *fail*
    rather than silently override pad materials.
    """
    physics = scene_info["physics"]
    setup_state = setup_state or {}
    root_path = setup_state.get("root_path", "/World/_FET028_Gantry_%s" % uuid4().hex[:8])
    physics_was_playing = setup_state.get("physics_was_playing", _physics_is_playing(physics))
    root_orientation_state = setup_state.get("root_orientation_state")
    articulation_default_state = setup_state.get("articulation_default_state")
    joint_default_state = setup_state.get("joint_default_state")

    # Weld the gantry to the articulation ROOT body, not necessarily the site's
    # gripper-base body. They are the same for single-root grippers (ezu), but
    # for a hand whose gripper base is a separate link fixed-jointed to the
    # floating root (svh: left_hand_base_link -> base_link), welding the
    # maximal-coordinate gantry constraint to the non-root link is redundant
    # with that internal fixed joint and makes PhysX explode (non-finite bounds,
    # tensor view never created). Resolving and measuring the physical root
    # keeps the identity-pose FixedJoint geometrically exact. An unresolved root
    # is an error because welding a site body can introduce a constraint loop.
    asset_root_path = setup_state.get("asset_root_path") or _carrier_asset_root(stage, robot, gripper_base_path)
    asset_robot_root_path = setup_state.get("asset_robot_root_path", robot.prim_path)
    weld_body_path = setup_state.get("root_body_path") or _resolve_articulation_root_body(
        stage, robot.prim_path, asset_root_path
    )
    if not weld_body_path:
        raise RuntimeError("FET028 cannot resolve an unambiguous articulation root body")
    if ctx is not None and weld_body_path != gripper_base_path:
        ctx.log(
            "FET028 carrier: welding gantry to articulation ROOT body %s "
            "(gripper base %s is a non-root link fixed to it; welding the root "
            "avoids a redundant constraint that explodes a floating base)." % (weld_body_path, gripper_base_path)
        )

    def _probe(label):
        # Diagnostic: report whether the articulation tensor view is alive and
        # where the base is, after each attach step, so the exact operation that
        # produces the non-finite explosion (stop / play / reset) is pinpointed.
        if ctx is None:
            return
        try:
            jp = robot.articulation.get_joint_positions()
            if jp is None:
                jpstat = "None (view DEAD)"
            else:
                a = np.asarray(jp)
                jpstat = "finite(n=%d)" % a.size if np.isfinite(a).all() else "NON-FINITE/NaN"
            wp, _wq = robot.articulation.get_world_pose()
            wp = np.asarray(wp, dtype=np.float64).reshape(3)
            ctx.log(
                "FET028 attach-probe[%s]: joint_pos=%s |base_world|=%.4g" % (label, jpstat, float(np.linalg.norm(wp)))
            )
        except Exception as exc:
            ctx.log("FET028 attach-probe[%s]: raised %r" % (label, exc))

    _probe("entry")

    # An API-bearing joint has no body transform. Read the physical body,
    # preferring its live tensor pose to the authored rest transform.
    live_getter = getattr(robot, "get_link_world_transforms", None)
    live_pose = live_getter([weld_body_path]).get(weld_body_path) if callable(live_getter) else None
    pos = (
        live_pose[0]
        if live_pose is not None
        else UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(weld_body_path)).ExtractTranslation()
    )
    base_world_pos = tuple(float(value) for value in pos)
    if len(base_world_pos) != 3 or not np.isfinite(base_world_pos).all():
        raise RuntimeError("FET028 physical root body pose is non-finite")

    setup_state["physics_stopped"] = True
    physics.stop()
    # Stop/topology edits invalidate the old tensor view. Do not query it again
    # until initialization/reset has rebuilt the articulation.

    pins = _asset_world_pin_paths(stage, asset_robot_root_path, asset_root_path, weld_body_path)
    if asset_robot_root_path in pins:
        _transfer_joint_root_for_carrier(stage, robot, weld_body_path, setup_state)
    world_pin_paths = _suspend_world_pins(stage, asset_robot_root_path, asset_root_path, weld_body_path, setup_state)
    setup_state["world_pin_paths"] = world_pin_paths
    world_pin_was_present = bool(world_pin_paths)

    # Orient the gripper base to point its forward_axis along the approach
    # (down) by AUTHORING the bounded content transform while physics
    # is stopped, BEFORE play() cooks the gantry FixedJoint. This is the only
    # mechanism that works (all three measured on this Isaac build):
    #   - the maximal-coordinate weld cannot reorient the base: it enforces
    #     position only and ignores its own localRot0;
    #   - the weld cooks the base->gantry relative orientation at play() and
    #     then HOLDS it, so any later teleport (set_world_pose / reset default)
    #     is yanked back to the cooked pose;
    #   - set_default_state alone applies at reset -- AFTER the cook -- so it
    #     does not change the cooked-in orientation.
    # Authoring the root pose here makes the base already point down when the
    # weld cooks, so the cooked relative IS the down orientation. We also set
    # the default state (below) so the reset re-cook keeps it. The bounded
    # subtree adjustment preserves the site's native offset from the physical
    # root, whose own resulting world rotation becomes the reset default.
    fresh_controller = merge_rail or setup_state.get("articulation_root_transfer") is not None
    if base_orient_wxyz is not None:
        _orient_gripper_base(
            stage, setup_state["orientation_root_path"], gripper_base_path, base_orient_wxyz, weld_body_path
        )
        root_world = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(weld_body_path))
        root_quat = Gf.Transform(root_world).GetRotation().GetQuat().GetNormalized()
        root_orient_wxyz = np.asarray([root_quat.GetReal(), *root_quat.GetImaginary()], dtype=np.float64)

    _build_gantry(
        stage,
        weld_body_path,
        base_world_pos,
        merge_into_articulation=merge_rail,
        root_path=root_path,
    )
    if ctx is not None:
        ctx.log(
            "FET028 carrier: rail mode = %s"
            % (
                "PRISMATIC RAIL (merged into articulation, fixed base + Z lift)"
                if merge_rail
                else "external weld (floating gripper root)"
            )
        )
    physics.play()

    if base_orient_wxyz is not None and not fresh_controller:
        # Make the down orientation the reset default too, so reset_async's
        # post_reset (the robot is registered in world.scene) restores it and
        # the re-cook keeps the gripper pointing down rather than reverting to
        # the asset's authored +Z rest pose.
        robot.articulation.set_default_state(position=np.asarray(base_world_pos), orientation=root_orient_wxyz)

    # Re-cook articulations. ``robot._world`` is the Isaac Sim
    # ``isaacsim.core.api.World`` singleton built by
    # ``RobotHandle.initialize``. ``reset_async()`` re-cooks every
    # articulation in the scene -- both the gripper (which had its
    # tensor view invalidated by stop/play) and the new gantry --
    # and rebuilds the per-articulation indices that
    # ``ParallelGripper.initialize`` will look up downstream. Re-raise
    # on failure: a stale tensor view here makes the very next
    # ``robot.dof_names`` read return empty / out-of-date and crashes
    # downstream with a misleading
    # ``'NoneType' object has no attribute 'joint_positions'``.
    world = getattr(robot, "_world", None)
    if world is None:
        raise RuntimeError("FET028 articulation re-cook requires a World instance after physics.stop()/play()")
    if world is not None:
        try:
            if fresh_controller:
                # The rail merged a prismatic DOF INTO the articulation
                # (19 -> 20 DOFs). The prismatic DOF only materializes when the
                # articulation is COOKED, but a plain reset_async re-applies the
                # stale old-DOF-count default actuation (sized before the cook)
                # and PhysX rejects the size mismatch. A FULL re-initialize
                # (World.clear_instance + fresh World + fresh cook) rebuilds the
                # articulation from scratch with the rail prims already on the
                # stage, so it is cooked at the new DOF count from the start and
                # every cached array is sized correctly -- the "build before
                # cook" path, run after the rail is authored.
                await robot.initialize(ctx)
                world = getattr(robot, "_world", None)
                if world is None:
                    raise RuntimeError("robot initialization did not provide a World instance")
                # initialize already cooks and resets the fresh articulation.
                # Its root defaults belong to the new physical root (the
                # fixed gantry in merged mode), not to the gripper body. A
                # second reset with the gripper rotation moves the gantry
                # against its world-pin frames and corrupts the fixture.
            else:
                await world.reset_async()
        except Exception as exc:
            raise RuntimeError(
                "articulation re-cook failed after physics.stop()/play() "
                "in attach_carrier; the articulation tensor view is now "
                "stale and downstream gripper operations would crash "
                "with misleading errors.\n" + _format_kit_log_tail(prefix="Recent kit_logs (most relevant first):")
            ) from exc
    _probe("after reset_async")

    return CarrierHandle(
        robot=robot,
        gripper_base_path=gripper_base_path,
        physics=physics,
        initial_target_z=0.0,
        world_pin_was_present=world_pin_was_present,
        root_orientation_state=root_orientation_state,
        articulation_default_state=articulation_default_state,
        joint_default_state=joint_default_state,
        physics_was_playing=physics_was_playing,
        root_path=root_path,
        joint_z_path=_gantry_paths(root_path)["joint_z"],
        world_pin_paths=world_pin_paths,
        world_pin_states=setup_state.get("world_pin_states"),
        orientation_root_path=setup_state.get("orientation_root_path", ""),
        asset_robot_root_path=asset_robot_root_path,
        articulation_root_transfer=setup_state.get("articulation_root_transfer"),
        rail_world_anchor=base_world_pos if merge_rail else None,
    )


async def detach_carrier(stage, handle: CarrierHandle, ctx=None) -> None:
    """Remove the gantry, reinstate the framework's world pin if needed.

    Symmetric with attach_carrier: stop physics, tear down the gantry
    + cross-articulation FixedJoint, reinstate the world pin if it
    was present at attach time, restart physics, re-cook via
    ``world.reset_async()`` so the gripper's tensor view is valid
    for any subsequent test phase or shape iteration.

    A successful physics stop is required before any topology changes or
    controller rebind. After it, every independent restoration is attempted.
    Any incomplete restoration is reported as an error, including a world pin
    that cannot be restored.
    """
    # The prebuilt rail belongs to this disposable test stage. Removing it
    # would invalidate the cooked articulation at the end of the test.
    if handle.prebuilt:
        if handle.carrier_robot is not None:
            handle.carrier_robot.teardown()
        return

    setup_state = {
        "root_path": handle.root_path,
        "orientation_root_path": handle.orientation_root_path or handle.robot.prim_path,
        "root_orientation_state": handle.root_orientation_state,
        "articulation_root_transfer": handle.articulation_root_transfer,
        "articulation_default_state": handle.articulation_default_state,
        "joint_default_state": handle.joint_default_state,
        "world_pin_paths": handle.world_pin_paths if handle.world_pin_was_present else (),
        "world_pin_states": handle.world_pin_states,
        "physics_was_playing": handle.physics_was_playing,
        "physics_stopped": True,
    }
    errors = await _finish_carrier_restore(stage, handle.robot, handle.physics, setup_state, ctx=ctx)
    if errors:
        details = []
        for error in errors:
            try:
                details.append(str(error)[:1024])
            except BaseException:
                details.append("required restoration cause could not be formatted")
        restoration_error = RuntimeError("FET028 carrier detach restoration failed: " + "; ".join(details)[:4096])
        for error in errors:
            note_secondary_error(restoration_error, lambda error=error: f"Required restoration cause: {error}")
        for error in errors:
            try:
                if ctx is not None:
                    ctx.warn(f"FET028 carrier detach restoration failed: {error!r}")
            except BaseException as diagnostic_error:
                note_secondary_error(
                    restoration_error,
                    lambda secondary=diagnostic_error: "Carrier detach warning was unavailable: %r" % secondary,
                )
        raise restoration_error from errors[0]


def _gantry_dof_index(robot, joint_path: str = _JOINT_Z):
    """Index of the exact test-owned carrier joint in the articulation's
    DOF list, or ``None`` when the gantry is not merged (legacy
    excludeFromArticulation mode) and so is not an articulation DOF.

    The generated joint leaf contains a digest of its unique USD namespace,
    preventing it from colliding with an asset-authored DOF such as
    ``joint_z``. The articulation API exposes names rather than USD paths, so
    require exactly one matching generated leaf before returning an index.
    """
    names = list(getattr(robot, "dof_names", None) or [])
    joint_name = str(joint_path).rsplit("/", 1)[-1]
    matches = [index for index, name in enumerate(names) if str(name) == joint_name]
    return matches[0] if len(matches) == 1 else None


def set_carrier_target_z(stage, handle: CarrierHandle, target_z: float) -> None:
    """Command the gantry's prismatic Z position target.

    In rail mode (the default) the gantry prismatic is a DOF of the merged
    gripper articulation, so it is driven via ``apply_action`` -- the physics
    tensor path. Writing the USD ``drive:linear:physics:targetPosition`` attribute
    during simulation does NOT propagate to the running PhysX view (the same
    reason link poses must be read from the physics view, not USD), so it cannot
    command live motion -- the USD attribute is only the cook-time rest target.
    When the gantry is NOT merged (legacy maximal-coordinate mode) there is no DOF
    to drive, so the USD attribute is the only path and is used as a fallback.

    The drive (high stiffness ~50000, critically damped, authored on ``joint_z``)
    pulls the gantry smoothly toward this target; the gripper follows rigidly and
    held objects follow via friction.
    """
    if handle is not None and handle.stationary:
        return
    robot = (handle.carrier_robot or handle.robot) if handle is not None else None
    # Record the COMMANDED target so carrier_target_z / linear_translate ramp from
    # it, not from the lagging live joint position (which would compound the drive
    # lag across chunks and undershoot the descent/lift).
    if handle is not None:
        handle.last_target_z = float(target_z)
    dof = _gantry_dof_index(robot, handle.joint_z_path if handle is not None else _JOINT_Z)
    if dof is not None:
        from isaacsim.core.utils.types import ArticulationAction

        act = ArticulationAction(
            joint_positions=np.array([float(target_z)], dtype=np.float32),
            joint_indices=np.array([dof], dtype=np.int32),
        )
        if handle.active_physics_engine == "newton":
            robot.apply_action(act)
        else:
            robot.articulation.apply_action(act)
        return
    joint_path = handle.joint_z_path if handle is not None else _JOINT_Z
    joint_prim = stage.GetPrimAtPath(joint_path)
    if not joint_prim or not joint_prim.IsValid():
        return
    attr = joint_prim.GetAttribute("drive:linear:physics:targetPosition")
    if attr:
        attr.Set(float(target_z))


def carrier_target_z(stage, handle: CarrierHandle = None) -> float:
    """Return the gantry's last COMMANDED Z target -- the ramp reference.

    Must be the commanded value, NOT the live joint position: ``linear_translate``
    ramps incrementally from this each chunk, so reading the (lagging) live
    position instead makes the drive lag compound across chunks and the
    descent/lift undershoot the target. The rail-mode target is set via
    ``apply_action`` (not USD), so it is tracked on the handle. With no handle
    (before attach / legacy mode) fall back to the USD drive target, or 0.0."""
    if handle is not None:
        return float(getattr(handle, "last_target_z", 0.0))
    joint_prim = stage.GetPrimAtPath(_JOINT_Z)
    if not joint_prim or not joint_prim.IsValid():
        return 0.0
    attr = joint_prim.GetAttribute("drive:linear:physics:targetPosition")
    val = attr.Get() if attr else None
    try:
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _carrier_world_axis_sign(handle: CarrierHandle) -> float:
    """Map the carrier joint coordinate onto world-Z travel.

    The precompiled Newton carrier connects ``body0=gantry_base`` to the
    already-oriented gripper root as ``body1``.  Newton reports that
    prismatic coordinate with the opposite sign from the resulting body1
    world-Z displacement.  PhysX's gantry coordinate follows world Z.
    """
    return -1.0 if str(handle.active_physics_engine).lower() == "newton" else 1.0


def carrier_world_position(handle: CarrierHandle) -> np.ndarray:
    """Return the carrier's (gripper's) current world position (3,).

    Generated PhysX rails use their captured fixed world anchor plus the live
    prismatic coordinate. ``get_world_pose()`` may describe either the fixed
    gantry or an already-moving root body after controller ownership transfer;
    adding the rail coordinate to the latter would count travel twice. Missing
    live rail evidence is an error, never a commanded-target/rest-pose fallback.
    Legacy floating carriers and the experimental prebuilt Newton carrier keep
    their existing controller-pose and joint-coordinate conventions.
    """
    motion_robot = handle.carrier_robot or handle.robot
    if handle.rail_world_anchor is not None:
        pos = np.asarray(handle.rail_world_anchor, dtype=np.float64).reshape(3).copy()
        if not np.isfinite(pos).all():
            raise RuntimeError("FET028 carrier rail world anchor is non-finite")
        dof = _gantry_dof_index(motion_robot, handle.joint_z_path)
        if dof is None:
            raise RuntimeError("FET028 carrier rail DOF is absent from the live articulation")
        try:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_state import (
                validate_selected_native_positions,
            )

            positions = motion_robot.get_joint_positions()
            travel = validate_selected_native_positions(positions, len(motion_robot.dof_names), [dof])[0]
        except Exception as exc:
            raise RuntimeError("FET028 carrier rail position requires finite live joint evidence") from exc
        pos[2] += travel
        return pos
    pos, _ = motion_robot.get_world_pose()
    pos = np.array(pos, dtype=np.float64).reshape(3)
    dof = _gantry_dof_index(motion_robot, handle.joint_z_path)
    if dof is not None:
        try:
            jp = motion_robot.get_joint_positions()
            if jp is not None:
                pos[2] = pos[2] + _carrier_world_axis_sign(handle) * float(jp[dof])
        except Exception:
            pass
    return pos


async def shake_gantry_z(
    ctx,
    stage,
    handle: CarrierHandle,
    amplitude: float,
    frequency_hz: float,
    duration_s: float,
    fps: int = 240,
    on_step=None,
) -> None:
    """Sinusoidally oscillate the gantry's Z drive target.

    Used to test grip robustness under dynamic perturbation. The
    target oscillates around the current target with the given
    amplitude (m) and frequency (Hz) for ``duration_s`` seconds.
    Restores the original target at the end.

    ``on_step(i, n_steps)`` -- optional async callback after each
    physics step, used for video capture.
    """
    import math as _math

    n_steps = max(1, int(round(duration_s * fps)))
    base_target = carrier_target_z(stage, handle)
    omega = 2.0 * _math.pi * float(frequency_hz)
    dt = 1.0 / float(fps)
    required_rail = getattr(handle, "rail_world_anchor", None) is not None
    if required_rail:
        carrier_world_position(handle)

    for i in range(1, n_steps + 1):
        t = i * dt
        target = base_target + float(amplitude) * _math.sin(omega * t)
        set_carrier_target_z(stage, handle, target)
        await ctx.step_one()
        if required_rail:
            carrier_world_position(handle)
        if on_step is not None:
            await on_step(i, n_steps)

    set_carrier_target_z(stage, handle, base_target)


async def linear_translate(
    ctx,
    stage,
    handle: CarrierHandle,
    delta_world: np.ndarray,
    duration_s: float,
    fps: int = 240,
    on_substep=None,
) -> None:
    """Smoothly ramp the gantry's Z drive target over ``duration_s``.

    Only the Z component of ``delta_world`` is used -- the gantry is
    Z-only by design. (Different approach directions are handled by
    setting the FixedJoint's local pose so the gripper hangs at the
    right orientation under the gantry; the gantry itself always
    drives along world Z.)

    Each iteration writes the smoothstep-interpolated drive target
    and runs one physics step. PhysX's drive integrator does the rest:
    gantry_z accelerates, decelerates, and settles smoothly toward
    the target with proper continuous velocity. The gripper base
    follows via the FixedJoint, and held objects follow via friction
    (which now has a real velocity to track because the prismatic
    drive isn't a teleport).

    ``on_substep(i, n_steps)`` -- optional async callback after each
    physics step for video capture.
    """
    if handle.stationary:
        return

    from simready.foundation.tier_core.runtime_tests.articulation_phases.jacobian_ik import smoothstep

    delta_z = _carrier_world_axis_sign(handle) * float(np.asarray(delta_world).reshape(3)[2])
    n_steps = max(1, int(round(duration_s * fps)))

    start_target = carrier_target_z(stage, handle)
    end_target = start_target + delta_z

    motion_robot = handle.carrier_robot or handle.robot
    dof = _gantry_dof_index(motion_robot, handle.joint_z_path)
    if dof is None:
        raise RuntimeError(
            "FET028 carrier joint_z is absent from the live articulation; "
            "the test-owned rail was not compiled as a controllable DOF."
        )
    required_rail = getattr(handle, "rail_world_anchor", None) is not None
    if required_rail:
        carrier_world_position(handle)

    warned_trace_channels = set()

    def _warn_trace_once(channel, error):
        if channel in warned_trace_channels:
            return
        warned_trace_channels.add(channel)
        try:
            warn = getattr(ctx, "warn", None)
            if callable(warn):
                warn("FET028 optional carrier %s diagnostic unavailable: %r" % (channel, error))
        except Exception:
            # Optional diagnostics cannot interrupt control. Cancellation is
            # intentionally not caught, just as for the read/log below.
            pass

    def _trace_carrier(step_index, commanded):
        try:
            trace_log = getattr(ctx, "log", None)
            if not callable(trace_log):
                return
            # These reads are trace-only. The control trajectory uses the
            # existing commanded target, and its caller separately checks
            # required live carrier motion. Logging cannot gate that control.
            positions = np.asarray(motion_robot.get_joint_positions(), dtype=np.float64).reshape(-1)
            targets = np.asarray(motion_robot.get_joint_position_targets(), dtype=np.float64).reshape(-1)
            efforts = None
            try:
                observed_efforts = motion_robot.get_applied_joint_efforts()
                if observed_efforts is None:
                    raise ValueError("effort readback is unavailable")
                effort_array = np.asarray(observed_efforts, dtype=np.float64).reshape(-1)
                if effort_array.size != positions.size or not np.isfinite(effort_array).all():
                    raise ValueError("effort readback is incomplete or non-finite")
                efforts = np.round(effort_array, 6).tolist()
            except Exception as exc:
                _warn_trace_once("effort", exc)
            actual = float(positions[dof]) if dof < positions.size else float("nan")
            live_target = float(targets[dof]) if dof < targets.size else float("nan")
            trace_log(
                "FET028 carrier trace: step=%d/%d joint_z_index=%d "
                "command=%.6f live_target=%.6f actual=%.6f "
                "positions=%s targets=%s efforts=%s dof_names=%r"
                % (
                    step_index,
                    n_steps,
                    dof,
                    float(commanded),
                    live_target,
                    actual,
                    np.round(positions, 6).tolist(),
                    np.round(targets, 6).tolist(),
                    efforts,
                    list(getattr(motion_robot, "dof_names", None) or []),
                )
            )
        except Exception as exc:
            _warn_trace_once("trace", exc)

    _trace_carrier(0, start_target)
    trace_steps = {1, max(1, n_steps // 4), max(1, n_steps // 2), max(1, 3 * n_steps // 4), n_steps}

    for i in range(1, n_steps + 1):
        t = smoothstep(i / n_steps)
        target = start_target + (end_target - start_target) * t
        set_carrier_target_z(stage, handle, target)
        await ctx.step_one()
        if required_rail:
            carrier_world_position(handle)
        if i in trace_steps:
            _trace_carrier(i, target)
        if on_substep is not None:
            await on_substep(i, n_steps)


# ---------------------------------------------------------------------------
# Gantry construction helpers
# ---------------------------------------------------------------------------


def _format_kit_log_tail(prefix: str = "", max_entries: int = 8) -> str:
    """Return a formatted tail of recent Kit log entries for exception messages.

    Reads from ``KitLogMonitor.get_current()`` (the live monitor the test
    runner installed) and filters to entries from PhysX-adjacent channels
    (``omni.physx*`` and ``omni.fabric*``). Newest entries first.

    This is the bridge that makes ``world.reset_async()`` failures
    actionable: PhysX errors that previously only appeared in
    ``result.json -> kit_logs[]`` (where users have to dig for them) now
    appear directly in the test exception, which the report headline
    shows at the top of the test card.

    Returns an empty string when no monitor is active (running outside
    Kit, e.g. in unit tests) or when no matching entries were captured.
    """
    try:
        from simready.evaluate_engine_kit.kit_log_monitor import KitLogMonitor
    except Exception:
        return ""
    monitor = KitLogMonitor.get_current()
    if monitor is None:
        return ""
    try:
        entries = monitor.get_entries()
    except Exception:
        return ""
    relevant = []
    for entry in entries:
        channel = str(entry.get("channel", "") or "")
        if channel.startswith("omni.physx") or channel.startswith("omni.fabric"):
            relevant.append(entry)
    if not relevant:
        return ""
    # Newest first, capped at max_entries.
    tail = list(reversed(relevant))[:max_entries]
    lines = []
    if prefix:
        lines.append(prefix)
    for e in tail:
        lvl = (e.get("level") or "?").upper()
        ch = e.get("channel") or "?"
        msg = e.get("message") or ""
        lines.append("  [%s] %s: %s" % (lvl, ch, msg))
    return "\n".join(lines)


def _set_root_orientation(stage, root_prim_path: str, orient_wxyz) -> None:
    """Set a transformable root's world rotation while preserving its position."""
    _orient_gripper_base(stage, root_prim_path, root_prim_path, orient_wxyz)


def _carrier_orientation_root(stage, asset_root_path, body_paths):
    """Find a common transform that moves only the selected articulation."""
    path = _common_ancestor_path(sorted(body_paths))
    root = stage.GetPrimAtPath(path)
    while root and root.IsValid() and _path_is_at_or_below(root.GetPath(), asset_root_path):
        if UsdGeom.Xformable(root):
            break
        root = root.GetParent()
    if not root or not root.IsValid() or not _path_is_at_or_below(root.GetPath(), asset_root_path):
        raise RuntimeError("FET028 cannot rotate the selected articulation inside its loaded asset boundary")
    for prim in Usd.PrimRange(root):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and str(prim.GetPath()) not in body_paths:
            raise RuntimeError(f"FET028 approach transform would move an unrelated rigid body: {prim.GetPath()}")
        if str(prim.GetPath()) in body_paths:
            current = prim
            while current != root:
                if UsdGeom.Xformable(current).GetResetXformStack():
                    raise RuntimeError("FET028 articulation has a reset transform stack below its approach transform")
                current = current.GetParent()
    return str(root.GetPath())


def _orient_gripper_base(stage, root_path, base_path, desired_wxyz, pivot_path=None):
    """Apply a world rotation to a bounded subtree around the physical root pivot.

    The outer adjustment preserves authored local rotations and translations,
    including a gripper site body offset from the articulation's physical root.
    USD row-vector composition requires parent * world_delta * parent^-1.
    """
    root = stage.GetPrimAtPath(root_path)
    base = stage.GetPrimAtPath(base_path)
    pivot = stage.GetPrimAtPath(pivot_path or base_path)
    if (
        not root
        or not base
        or not pivot
        or not UsdGeom.Xformable(root)
        or not all(prim.GetPath().HasPrefix(root.GetPath()) for prim in (base, pivot))
    ):
        raise RuntimeError("FET028 orientation requires a valid base and pivot below a transformable content root")
    current = base
    while current != root:
        if UsdGeom.Xformable(current).GetResetXformStack():
            raise RuntimeError("FET028 base has a reset transform stack below the approach transform")
        current = current.GetParent()
    values = np.asarray(desired_wxyz, dtype=np.float64).reshape(4).copy()
    if not np.isfinite(values).all() or not np.any(values):
        raise RuntimeError("FET028 approach orientation must be a finite nonzero quaternion")
    # Quaternion magnitude carries no rotation information. Scale before the
    # norm so finite large/subnormal inputs cannot overflow/underflow into a
    # zero quaternion that Gf would silently interpret as identity.
    values /= np.max(np.abs(values))
    values /= np.linalg.norm(values)
    cache = UsdGeom.XformCache()
    current_rotation = Gf.Transform(cache.GetLocalToWorldTransform(base)).GetRotation()
    desired = Gf.Rotation(Gf.Quatd(float(values[0]), Gf.Vec3d(*map(float, values[1:]))))
    delta = current_rotation.GetInverse() * desired
    anchor = cache.GetLocalToWorldTransform(pivot).ExtractTranslation()
    world_adjustment = Gf.Matrix4d(1.0)
    world_adjustment.SetRotate(delta)
    world_adjustment.SetTranslateOnly(anchor - delta.TransformDir(anchor))
    xf = UsdGeom.Xformable(root)
    parent_world = Gf.Matrix4d(1.0) if xf.GetResetXformStack() else cache.GetParentToWorldTransform(root)
    adjustment = parent_world * world_adjustment * parent_world.GetInverse()
    ops = xf.GetOrderedXformOps()
    name = "xformOp:transform:fet028Approach"
    existing = [op for op in ops if op.GetOpName() == name]
    if existing:
        if ops[0].GetOpName() != name:
            raise RuntimeError("FET028 approach adjustment must be the outermost transform")
        existing[0].Set(existing[0].Get() * adjustment)
    else:
        reset_stack = xf.GetResetXformStack()
        op = xf.AddTransformOp(UsdGeom.XformOp.PrecisionDouble, "fet028Approach")
        op.Set(adjustment)
        xf.SetXformOpOrder([op, *ops], resetXformStack=reset_stack)
    composed = UsdGeom.XformCache()
    actual = Gf.Transform(composed.GetLocalToWorldTransform(base)).GetRotation()
    axes = (Gf.Vec3d(1, 0, 0), Gf.Vec3d(0, 1, 0), Gf.Vec3d(0, 0, 1))
    if not all(Gf.IsClose(actual.TransformDir(axis), desired.TransformDir(axis), 1e-6) for axis in axes):
        raise RuntimeError(
            "FET028 approach orientation is overridden or cannot be represented by the composed USD transforms"
        )
    if not Gf.IsClose(composed.GetLocalToWorldTransform(pivot).ExtractTranslation(), anchor, 1e-6):
        raise RuntimeError("FET028 approach orientation did not preserve the physical root pivot")


def _rigid_world_rotation(world, body_path):
    """Extract rigid axes without interpreting scale or shear as rotation."""
    matrix = np.asarray(world, dtype=np.float64)
    if not np.isfinite(matrix).all():
        raise RuntimeError(f"FET028 attachment frame is non-finite: {body_path}")
    basis = matrix[:3, :3]
    scales = np.linalg.norm(basis, axis=1)
    if not np.isfinite(scales).all() or np.any(scales <= 1e-12):
        raise RuntimeError(f"FET028 attachment frame has singular scale: {body_path}")
    axes = basis / scales[:, None]
    if not np.allclose(axes @ axes.T, np.eye(3), atol=1e-5, rtol=0):
        raise RuntimeError(f"FET028 attachment frame has unsupported shear: {body_path}")
    if np.linalg.det(axes) <= 0:
        raise RuntimeError(f"FET028 attachment frame is reflected: {body_path}")
    return Gf.Matrix4d(Gf.Matrix3d(*map(float, axes.reshape(-1))), Gf.Vec3d(0))


def _align_attachment_frames(stage, joint, body0_path, body1_path):
    """Preserve the relative authored pose of a merged rigid attachment.

    Joint positions are local points, so their world placement includes the
    body's inherited scale. Joint orientations have only rigid axes; compute
    them separately instead of decomposing a scaled relative matrix.
    """
    cache = UsdGeom.XformCache()
    world0 = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(body0_path))
    world1 = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(body1_path))
    rotation0 = _rigid_world_rotation(world0, body0_path)
    rotation1 = _rigid_world_rotation(world1, body1_path)
    position0 = world0.GetInverse().Transform(world1.ExtractTranslation())
    rotation = (rotation1 * rotation0.GetTranspose()).ExtractRotationQuat().GetNormalized()
    joint.CreateLocalPos0Attr().Set(Gf.Vec3f(position0))
    joint.CreateLocalRot0Attr().Set(Gf.Quatf(rotation))
    joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0))
    joint.CreateLocalRot1Attr().Set(Gf.Quatf(1))


def _build_gantry(
    stage,
    gripper_base_path: str,
    base_world_pos,
    merge_into_articulation: bool = False,
    root_path: str = _GANTRY_ROOT,
    active_physics_engine: str = "physx",
    direct_precompiled_rail: bool = False,
) -> None:
    """Author the gantry USD: base, gantry_z, joints, drive, attach.

    ``merge_into_articulation`` controls how the gantry connects to the gripper:
      - False (legacy): the attach_joint is ``excludeFromArticulation`` -- a
        maximal-coordinate weld. The gripper articulation stays separate and its
        base becomes a FLOATING root held only by this external constraint.
        Stable for simple grippers (ezu), but a complex mimic-coupled hand (svh)
        diverges to non-finite as a floating root (it is rock-solid FIXED-base
        under FET022).
      - True (prismatic rail): the attach_joint is a normal articulation joint,
        so the gantry (gantry_base FIXED to world -> prismatic Z -> gripper)
        MERGES into the gripper articulation. The articulation then has a FIXED
        base (gantry_base pinned to world) plus a controllable prismatic Z lift
        DOF -- FET022-style stability AND real velocity for friction-driven
        lift. The DOF count grows by 1 (the prismatic), so grasp DOF indices
        must be re-resolved by name after attach.

    Both gantry bodies (base and z) are placed at the gripper base's
    current world position. A merged attachment uses matching joint frames
    to retain its authored orientation; the legacy external weld keeps its
    existing identity-frame convention.

    Drive parameters (matching FET005's gantry):
      - stiffness 50000 N/m
      - damping = 2*sqrt(mass*stiffness) (critical damping)
      - maxForce 10000 N
      - max velocity 20 m/s
    Plenty for moving any reasonable gripper smoothly.
    """
    if merge_into_articulation and not direct_precompiled_rail:
        body = stage.GetPrimAtPath(gripper_base_path)
        if not body or not body.IsValid():
            raise RuntimeError("FET028 merged attachment requires a valid rigid body")
        _rigid_world_rotation(UsdGeom.XformCache().GetLocalToWorldTransform(body), gripper_base_path)
    # Kit binds PhysxSchema into pxr; outside Kit it comes from physx-usd-schemas.
    # Lazy-imported so the module loads cleanly without either.
    try:
        from pxr import PhysxSchema
    except ImportError:
        from physx_usd_schemas import PhysxSchema

    paths = _gantry_paths(root_path)

    gantry_mass = 1.0  # kg, light enough for fast drive response
    px, py, pz = float(base_world_pos[0]), float(base_world_pos[1]), float(base_world_pos[2])

    # Plain Xform root -- intentionally NOT an articulation. The
    # gripper asset already has its own ArticulationRootAPI; if we
    # also make the gantry an articulation, the cross FixedJoint
    # between gantry_z and gripper_base causes PhysX to merge the two
    # into a single articulation with 1+6 DOFs. That breaks
    # ``ParallelGripper`` (which was bound to the original 6-DOF
    # gripper articulation) and the drive-boost arrays (sized 6).
    # Keeping the gantry as plain rigid bodies + a prismatic joint
    # with a position drive avoids the merge -- PhysX handles regular
    # (non-articulation) joint drives just fine.
    UsdGeom.Xform.Define(stage, paths["root"])
    is_newton = str(active_physics_engine).lower() == "newton"
    direct_precompiled_rail = bool(direct_precompiled_rail)

    # gantry_base -- fixed to world. All gantry bodies need explicit
    # mass; without it PhysX logs "invalid inertia tensor" and the
    # drive can't move them.
    base_xform = UsdGeom.Xform.Define(stage, paths["base"])
    base_xform.AddTranslateOp().Set(Gf.Vec3d(px, py, pz))
    base_prim = base_xform.GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(base_prim)
    base_mass = UsdPhysics.MassAPI.Apply(base_prim)
    base_mass.CreateMassAttr(gantry_mass)
    base_mass.CreateCenterOfMassAttr(Gf.Vec3f(0.0, 0.0, 0.0))
    base_mass.CreateDiagonalInertiaAttr(Gf.Vec3f(1.0e-3, 1.0e-3, 1.0e-3))
    base_mass.CreatePrincipalAxesAttr(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
    if is_newton:
        # Preserve the rigid-body and mass APIs when adding provisional Newton
        # schemas. Replacing apiSchemas with only root markers makes the body
        # disappear from the physics joint graph.
        base_prim.SetMetadata(
            "apiSchemas",
            Sdf.TokenListOp.Create(
                prependedItems=[
                    "PhysicsRigidBodyAPI",
                    "PhysicsMassAPI",
                    "PhysicsArticulationRootAPI",
                    "NewtonArticulationRootAPI",
                ]
            ),
        )

    # gantry_z -- the moving body. Initially co-located with the base
    # so the joint sits at zero displacement.
    moving_body_path = gripper_base_path if direct_precompiled_rail else paths["z"]
    if not direct_precompiled_rail:
        gz_xform = UsdGeom.Xform.Define(stage, paths["z"])
        gz_xform.AddTranslateOp().Set(Gf.Vec3d(px, py, pz))
        gz_prim = gz_xform.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(gz_prim)
        UsdPhysics.MassAPI.Apply(gz_prim).CreateMassAttr(gantry_mass)

    # root_joint: FixedJoint between world (body0 empty) and gantry_base
    root_joint = UsdPhysics.FixedJoint.Define(stage, paths["root_joint"])
    root_joint.CreateBody1Rel().SetTargets([paths["base"]])

    # joint_z: PrismaticJoint along Z, base -> gantry_z. Limits +/-1m
    # cover any reasonable descent + lift range; the default is way
    # bigger than the test ever needs.
    joint_z = UsdPhysics.PrismaticJoint.Define(stage, paths["joint_z"])
    joint_z.CreateAxisAttr().Set(UsdPhysics.Tokens.z)
    joint_z.CreateBody0Rel().SetTargets([paths["base"]])
    joint_z.CreateBody1Rel().SetTargets([moving_body_path])
    joint_z.CreateLowerLimitAttr().Set(-1.0)
    joint_z.CreateUpperLimitAttr().Set(1.0)
    joint_z.CreateBreakForceAttr().Set(1e6)
    joint_z.CreateBreakTorqueAttr().Set(1e6)

    # Position drive on joint_z. ``damping = 2*sqrt(m*k)`` is the
    # critical-damping formula for a 1-DOF mass-spring system of
    # mass ``m`` and stiffness ``k``. We use ``gantry_mass`` (1 kg)
    # here, NOT the effective system mass which includes the
    # rigidly-attached gripper articulation.
    #
    # Trade-off: the actual moving mass is gantry_z (1 kg) + the
    # gripper assembly. For grippers up to ~1 kg total mass (Robotiq
    # 2F-85 is ~0.9 kg) the system stays close to critically damped.
    # For heavier industrial grippers (3-5 kg) the damping ratio
    # drops to ~sqrt(1/4) ≈ 0.5, i.e. visibly underdamped, and the
    # lift / shake phases will show some oscillation. If that
    # interferes with the shake-phase relative-slip measurement on
    # a specific asset, derive the damping from the actual gripper
    # mass at attach time (``robot.total_mass()`` once it exists on
    # the RobotHandle), or expose stiffness / damping as config
    # knobs so the test pack can tune per asset.
    stiffness = 50000.0
    damping = 2.0 * math.sqrt(gantry_mass * stiffness)
    max_force = 10000.0
    drive = None if is_newton else UsdPhysics.DriveAPI.Apply(joint_z.GetPrim(), "linear")
    PhysxSchema.JointStateAPI.Apply(joint_z.GetPrim(), "linear")
    if drive is not None:
        drive.CreateTargetPositionAttr().Set(0.0)
        drive.CreateStiffnessAttr().Set(stiffness)
        drive.CreateDampingAttr().Set(damping)
        drive.CreateMaxForceAttr().Set(max_force)
    px_joint = PhysxSchema.PhysxJointAPI.Apply(joint_z.GetPrim())
    px_joint.CreateMaxJointVelocityAttr().Set(20.0)

    # attach_joint: FixedJoint between gantry_z (body0) and gripper
    # base (body1). Merged attachments use matching rigid joint frames below.
    # The legacy external joint enforces the base POSITION (and so transmits
    # the gantry's Z motion to the gripper); it does NOT set the base
    # orientation -- that is handled by the articulation default state
    # in attach_carrier, because this maximal-coordinate joint locks
    # the base orientation to the reset pose and ignores localRot0
    # (measured on this Isaac build; authoring localRot0 had no effect).
    #
    # ``excludeFromArticulation = true`` is critical: without it,
    # PhysX adds the gantry bodies (gantry_z + gantry_base via the
    # prismatic) into the gripper's articulation through this fixed
    # joint, growing it from 6 to 7 DOFs. ParallelGripper and the
    # drive-boost arrays (sized for 6) then crash with
    # "could not broadcast input array from shape (7,) into shape (6,)".
    # With this flag the joint is solved as a maximal-coordinate
    # constraint and the gripper articulation stays at 6 DOFs.
    if is_newton:
        joint_z.GetPrim().SetMetadata(
            "apiSchemas",
            Sdf.TokenListOp.Create(prependedItems=["NewtonJointAPI", "PhysicsJointStateAPI:linear"]),
        )
        # Newton's experimental articulation accepts a prismatic joint in its
        # DOF list, but ``SingleArticulation.apply_action`` does not establish
        # a live controller target for a test-authored standard DriveAPI.  The
        # observed target remains NaN and the rail only drifts by sub-mm
        # amounts.  Author the runtime-native actuator contract before the
        # first physics cook so ``ArticulationActuators`` owns this test DOF.
        # Keep the actuator below the articulation-root prim.  Newton's
        # ArticulationActuators discovery walks that subtree; a sibling under
        # the carrier namespace is imported by the solver but invisible to the
        # runtime controller bridge.
        actuator = stage.DefinePrim(paths["base"] + "/joint_z_actuator", "NewtonActuator")
        actuator.ApplyAPI("NewtonPDControlAPI")
        actuator.ApplyAPI("NewtonMaxEffortClampingAPI")
        actuator.CreateRelationship("newton:targets").SetTargets([paths["joint_z"]])
        actuator.CreateAttribute("newton:kp", Sdf.ValueTypeNames.Float).Set(1000.0)
        actuator.CreateAttribute("newton:kd", Sdf.ValueTypeNames.Float).Set(125.0)
        actuator.CreateAttribute("newton:maxEffort", Sdf.ValueTypeNames.Float).Set(1000.0)

    if not direct_precompiled_rail:
        attach = UsdPhysics.FixedJoint.Define(stage, paths["attach_joint"])
        attach.CreateBody0Rel().SetTargets([paths["z"]])
        attach.CreateBody1Rel().SetTargets([gripper_base_path])
        attach.CreateExcludeFromArticulationAttr().Set(not merge_into_articulation)
        if merge_into_articulation:
            _align_attachment_frames(stage, attach, paths["z"], gripper_base_path)


def _remove_existing_gantry(stage, root_path: str = _GANTRY_ROOT) -> None:
    """Remove only the explicitly supplied carrier namespace."""
    prim = stage.GetPrimAtPath(root_path)
    if prim and prim.IsValid():
        stage.RemovePrim(root_path)


# ---------------------------------------------------------------------------
# World-pin handling (framework's static-base FixedJoint at WORLD_PIN_PATH)
# ---------------------------------------------------------------------------


def _path_is_at_or_below(path, root_path):
    path = str(path).rstrip("/")
    root_path = str(root_path).rstrip("/")
    return path == root_path or path.startswith(root_path + "/")


def _owning_rigid_body_path(stage, target_path):
    if target_path is None:
        return None
    prim = stage.GetPrimAtPath(target_path)
    while prim and prim.IsValid():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            return str(prim.GetPath())
        prim = prim.GetParent()
    return None


def _is_robot_world_pin(stage, joint_prim, robot_prim_path, body_paths=None):
    """Return whether a joint has one robot body and one world endpoint."""
    if not joint_prim or not joint_prim.IsValid() or not joint_prim.IsA(UsdPhysics.Joint):
        return False
    endpoints = _joint_body_paths(stage, joint_prim)
    robot_endpoints = [
        body_path
        for body_path in endpoints
        if body_path
        and (body_path in body_paths if body_paths is not None else _path_is_at_or_below(body_path, robot_prim_path))
    ]
    world_endpoints = [body_path for body_path in endpoints if body_path is None]
    return len(robot_endpoints) == 1 and len(world_endpoints) == 1


def _common_ancestor_path(paths):
    ancestor = Sdf.Path(str(paths[0]))
    for path in paths[1:]:
        while not Sdf.Path(str(path)).HasPrefix(ancestor):
            ancestor = ancestor.GetParentPath()
    return str(ancestor)


def _asset_world_pin_paths(stage, robot_prim_path, asset_root_path=None, root_body_path=None):
    """Discover active asset-authored joints that pin the tested robot."""
    root_body_path = root_body_path or _resolve_articulation_root_body(stage, robot_prim_path, asset_root_path)
    if not root_body_path:
        return ()
    asset_root_path = asset_root_path or _common_ancestor_path((robot_prim_path, root_body_path))
    body_paths = _articulation_body_paths(stage, root_body_path, asset_root_path)
    candidate_paths = [str(prim.GetPath()) for prim in _asset_joint_prims(stage, asset_root_path)]
    current = stage.GetPrimAtPath(robot_prim_path)
    while current and current.IsValid() and _path_is_at_or_below(current.GetPath(), asset_root_path):
        relationship = current.GetRelationship("isaac:physics:robotJoints")
        if relationship:
            candidate_paths.extend(str(path) for path in relationship.GetForwardedTargets())
        current = current.GetParent()
    result = []
    for candidate_path in candidate_paths:
        if candidate_path in result:
            continue
        prim = stage.GetPrimAtPath(candidate_path)
        if (
            prim
            and prim.IsValid()
            and prim.IsActive()
            and prim.IsA(UsdPhysics.Joint)
            and UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is not False
            and _is_robot_world_pin(stage, prim, robot_prim_path, body_paths)
        ):
            result.append(candidate_path)
    return tuple(result)


def _suspend_world_pins(stage, robot_prim_path, asset_root_path=None, root_body_path=None, setup_state=None):
    """Deactivate only world pins that would over-constrain the FET028 rail."""
    root_body_path = root_body_path or _resolve_articulation_root_body(stage, robot_prim_path, asset_root_path)
    pin_paths = list(_asset_world_pin_paths(stage, robot_prim_path, asset_root_path, root_body_path))
    body_paths = (
        _articulation_body_paths(
            stage, root_body_path, asset_root_path or _common_ancestor_path((robot_prim_path, root_body_path))
        )
        if root_body_path
        else set()
    )
    try:
        from simready.evaluate_engine_kit.physics_utils import WORLD_PIN_PATH
    except Exception:
        WORLD_PIN_PATH = None
    if WORLD_PIN_PATH is not None:
        framework_path = str(WORLD_PIN_PATH)
        prim = stage.GetPrimAtPath(framework_path)
        if (
            prim
            and prim.IsValid()
            and prim.IsActive()
            and framework_path not in pin_paths
            and _is_robot_world_pin(stage, prim, robot_prim_path, body_paths)
            and UsdPhysics.Joint(prim).GetJointEnabledAttr().Get() is not False
        ):
            pin_paths.append(framework_path)
    suspended = []
    pin_states = {}
    if setup_state is not None:
        setup_state["world_pin_states"] = pin_states
    for pin_path in pin_paths:
        prim = stage.GetPrimAtPath(pin_path)
        pin_states[pin_path] = _capture_edit_properties(stage, pin_path, (), ("active",))
        suspended.append(pin_path)
        if setup_state is not None:
            setup_state["world_pin_paths"] = tuple(suspended)
        try:
            if not prim.SetActive(False):
                raise RuntimeError("USD refused to deactivate the world pin")
            if prim.IsActive():
                raise RuntimeError("world pin deactivation is overridden by a stronger USD opinion")
        except BaseException as error:
            _require_world_pin_restore(stage, suspended, pin_states)
            raise RuntimeError("failed to suspend FET028 world pin at %s" % pin_path) from error
    return tuple(suspended)


def suspend_world_joint_for_body(stage, body_path):
    """Deactivate an authored fixed-to-world joint before adding the rail."""
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.FixedJoint):
            continue
        joint = UsdPhysics.FixedJoint(prim)
        body0 = joint.GetBody0Rel().GetTargets()
        body1 = joint.GetBody1Rel().GetTargets()
        if not body0 and body1 and str(body1[0]) == str(body_path):
            prim.SetActive(False)
            return str(prim.GetPath())
    return None


def suspend_articulation_root_apis(prim):
    """Move root ownership to the transient carrier without nested roots."""
    if not prim or not prim.IsValid():
        return []
    schemas = [
        name for name in ("PhysicsArticulationRootAPI", "NewtonArticulationRootAPI") if name in prim.GetAppliedSchemas()
    ]
    if schemas:
        prim.SetMetadata("apiSchemas", Sdf.TokenListOp.Create(deletedItems=schemas))
    return schemas


def _restore_world_pin(stage, pin_path, state=None) -> bool:
    """Reactivate the exact world-pin prim suspended for this run."""
    if not pin_path:
        return True
    prim = stage.GetPrimAtPath(pin_path)
    if not prim or not prim.IsValid():
        return False
    try:
        if state is None:
            prim.SetActive(True)
        else:
            _restore_edit_properties(state)
        return True
    except Exception:
        return False

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
import hashlib
import math
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

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


def _gantry_paths(root_path):
    joint_name = "joint_z"
    if root_path != _GANTRY_ROOT:
        digest = hashlib.sha256(str(root_path).encode("utf-8")).hexdigest()[:12]
        joint_name = "_fet028_carrier_z_{}".format(digest)
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
        "orient_existed": bool(orient and orient.HasAuthoredValueOpinion()),
        "orient_value": orient.Get() if orient and orient.HasAuthoredValueOpinion() else None,
        "order_existed": bool(order and order.HasAuthoredValueOpinion()),
        "order_value": order.Get() if order and order.HasAuthoredValueOpinion() else None,
    }


def _restore_root_orientation(stage, root_prim_path, state):
    if state is None:
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
    for name, value in zip(("positions", "velocities", "efforts"), state):
        if value is not None:
            kwargs[name] = value
    if kwargs:
        setter(**kwargs)


def _resolve_articulation_root_body(stage, robot_prim_path: str):
    """Return the USD path of the articulation's ROOT rigid body, or None.

    The root body is the rigid body under ``robot_prim_path`` that is NOT the
    child (``body1``) of any joint whose other end (``body0``) is another body
    in the articulation -- i.e. the top of the kinematic tree. A fixed-to-world
    "root_joint" has an empty ``body0``, so it does not exclude its ``body1``
    (the root stays a candidate).

    The gantry must weld to THIS body. Welding to a non-root link that is itself
    rigidly fixed-jointed to the floating root (e.g. the SVH hand's
    ``left_hand_base_link`` -> ``left_hand_base_joint`` -> ``base_link``) adds a
    maximal-coordinate constraint redundant with the articulation's internal
    fixed joint; PhysX cannot solve the resulting loop for a floating base and
    explodes to non-finite bounds. For single-root-body grippers (ezu: the
    gripper base IS the root body) this returns that same body, so the weld is
    unchanged.

    Returns None when the root is ambiguous (more than one candidate) or cannot
    be resolved, so the caller falls back to the gripper base path.
    """
    root = stage.GetPrimAtPath(robot_prim_path)
    if not root or not root.IsValid():
        return None
    bodies = []
    child_links = set()
    for prim in Usd.PrimRange(root):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            bodies.append(prim.GetPath().pathString)
        if prim.IsA(UsdPhysics.Joint):
            joint = UsdPhysics.Joint(prim)
            b0 = joint.GetBody0Rel().GetTargets()
            b1 = joint.GetBody1Rel().GetTargets()
            # body0 non-empty -> body1 is a child link in the kinematic tree.
            # (root_joint to world has an empty body0, so its body1 is kept.)
            if b0 and b1:
                child_links.add(str(b1[0]))
    candidates = [b for b in bodies if b not in child_links]
    return candidates[0] if len(candidates) == 1 else None


async def _rollback_partial_carrier(stage, robot, physics, setup_state, ctx=None):
    """Best-effort rollback for a failed carrier attachment.

    Every independent restoration step is attempted. The returned errors are
    secondary diagnostics; callers must preserve and re-raise the attachment
    failure that triggered the rollback.
    """
    errors = []

    def _attempt(operation):
        try:
            operation()
        except Exception as exc:
            errors.append(exc)

    _attempt(physics.stop)
    _attempt(lambda: _remove_existing_gantry(stage, setup_state["root_path"]))
    _attempt(lambda: _restore_root_orientation(stage, robot.prim_path, setup_state["root_orientation_state"]))
    _attempt(lambda: _restore_default_state(robot.articulation, setup_state["articulation_default_state"]))
    _attempt(lambda: _restore_joint_default_state(robot.articulation, setup_state["joint_default_state"]))
    pin_paths = setup_state.get("world_pin_paths", ())
    if pin_paths:
        _attempt(lambda: _require_world_pin_restore(stage, pin_paths))

    if setup_state["physics_was_playing"]:
        _attempt(physics.play)
        if setup_state.get("physics_stopped"):
            try:
                await robot.initialize(ctx)
            except Exception as exc:
                errors.append(exc)
            else:
                _attempt(lambda: _restore_default_state(robot.articulation, setup_state["articulation_default_state"]))
                _attempt(lambda: _restore_joint_default_state(robot.articulation, setup_state["joint_default_state"]))
                world = getattr(robot, "_world", None)
                if world is None:
                    errors.append(RuntimeError("robot initialization did not provide a World instance"))
                else:
                    try:
                        await world.reset_async()
                    except Exception as exc:
                        errors.append(exc)
    else:
        _attempt(physics.stop)
    return errors


def _require_world_pin_restore(stage, pin_paths):
    failed = [pin_path for pin_path in pin_paths if not _restore_world_pin(stage, pin_path)]
    if failed:
        raise RuntimeError("failed to restore suspended FET028 world pin(s): %s" % ", ".join(failed))


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
    setup_state = {
        "root_path": root_path,
        "physics_was_playing": _physics_is_playing(physics),
        "physics_stopped": False,
        "root_orientation_state": _capture_root_orientation(stage, robot.prim_path),
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
    except Exception:
        rollback_errors = await _rollback_partial_carrier(stage, robot, physics, setup_state, ctx=ctx)
        if ctx is not None:
            for error in rollback_errors:
                ctx.warn("FET028 carrier rollback step failed: %r" % error)
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
      - If ``base_orient_wxyz`` is given, sets it as the articulation's
        DEFAULT (reset) orientation via
        ``robot.articulation.set_default_state`` so the next reset
        teleports the gripper base to that orientation (e.g. pointing
        its forward_axis down for a top-down grasp). This is the ONLY
        way to orient the base: the gantry's maximal-coordinate
        FixedJoint enforces the base POSITION but locks its ORIENTATION
        to the reset pose, ignoring the joint's ``localRot0`` (measured
        on this Isaac build). Reset cooks the FixedJoint with the base
        already at this orientation, so the down pose is held.
      - ``world.reset_async()`` to re-cook the full articulation
        graph (and apply the default orientation above). Without this
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
    # tensor view never created). ``robot.articulation.get_world_pose()`` below
    # already returns the ROOT body pose, so welding to the root body keeps the
    # identity-pose FixedJoint geometrically exact. Falls back to the gripper
    # base path if the root cannot be resolved unambiguously.
    weld_body_path = _resolve_articulation_root_body(stage, robot.prim_path) or gripper_base_path
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

    pos, _orient = robot.articulation.get_world_pose()
    base_world_pos = (
        float(np.asarray(pos).reshape(3)[0]),
        float(np.asarray(pos).reshape(3)[1]),
        float(np.asarray(pos).reshape(3)[2]),
    )

    physics.stop()
    setup_state["physics_stopped"] = True
    _probe("after stop")

    world_pin_paths = _suspend_world_pins(stage, robot.prim_path)
    setup_state["world_pin_paths"] = world_pin_paths
    world_pin_was_present = bool(world_pin_paths)

    # Orient the gripper base to point its forward_axis along the approach
    # (down) by AUTHORING the articulation root's USD orientation while physics
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
    # the default state (below) so the reset re-cook keeps it. This assumes the
    # base link shares the articulation-root orientation, which holds for the
    # centric / parallel grippers that reach this path (the base link IS the
    # root link).
    if base_orient_wxyz is not None:
        _set_root_orientation(stage, robot.prim_path, base_orient_wxyz)

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
    _probe("after build_gantry")

    physics.play()
    _probe("after play")

    if base_orient_wxyz is not None:
        # Make the down orientation the reset default too, so reset_async's
        # post_reset (the robot is registered in world.scene) restores it and
        # the re-cook keeps the gripper pointing down rather than reverting to
        # the asset's authored +Z rest pose.
        robot.articulation.set_default_state(orientation=np.asarray(base_orient_wxyz, dtype=np.float64))

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
    if world is not None:
        try:
            if merge_rail and ctx is not None:
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
    )


async def detach_carrier(stage, handle: CarrierHandle, ctx=None) -> None:
    """Remove the gantry, reinstate the framework's world pin if needed.

    Symmetric with attach_carrier: stop physics, tear down the gantry
    + cross-articulation FixedJoint, reinstate the world pin if it
    was present at attach time, restart physics, re-cook via
    ``world.reset_async()`` so the gripper's tensor view is valid
    for any subsequent test phase or shape iteration.

    ``ctx`` is optional but recommended -- when provided, a failed
    world-pin restoration is reported via ``ctx.warn`` so subsequent
    test phases that rely on a static-base gripper get a clear
    breadcrumb instead of silent unexpected drift.
    """
    # The prebuilt rail belongs to this disposable test stage. Removing it
    # would invalidate the cooked articulation at the end of the test.
    if handle.prebuilt:
        if handle.carrier_robot is not None:
            handle.carrier_robot.teardown()
        return

    handle.physics.stop()
    _remove_existing_gantry(stage, handle.root_path)
    _restore_root_orientation(stage, handle.robot.prim_path, handle.root_orientation_state)
    # Re-enable any asset-side world pins (e.g. ``root_joint``) we
    # disabled in attach_carrier. Symmetric with the attach path so
    # subsequent test phases / shape iterations see the asset in its
    # authored configuration.
    if handle.world_pin_was_present:
        failed_pins = [pin_path for pin_path in handle.world_pin_paths if not _restore_world_pin(stage, pin_path)]
        if failed_pins:
            msg = (
                "World pin restoration failed for %s (%s) -- subsequent test "
                "phases that rely on a static-base gripper may see "
                "unexpected drift." % (handle.gripper_base_path, ", ".join(failed_pins))
            )
            if ctx is not None:
                ctx.warn(msg)
    if handle.physics_was_playing:
        handle.physics.play()
    world = getattr(handle.robot, "_world", None)
    if world is not None and handle.physics_was_playing:
        try:
            # Removing the merged rail changes the articulation DOF count and
            # invalidates its tensor view. Rebuild the RobotHandle before reset;
            # resetting the stale view cannot repair a topology change.
            await handle.robot.initialize(ctx)
            _restore_default_state(handle.robot.articulation, handle.articulation_default_state)
            _restore_joint_default_state(handle.robot.articulation, handle.joint_default_state)
            world = getattr(handle.robot, "_world", None)
            if world is None:
                raise RuntimeError("robot initialization did not provide a World instance")
            await world.reset_async()
        except Exception as exc:
            raise RuntimeError(
                "articulation reinitialization failed after removing the "
                "FET028 carrier; the tensor view could not be restored."
            ) from exc


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

    In rail mode the merged articulation's ROOT is the gantry_base, which is
    FIXED to world -- ``get_world_pose()`` on it never moves, so it cannot
    measure the lift. The gripper's actual vertical travel is the ``joint_z``
    prismatic DOF, read reliably via ``get_joint_positions``; add it to the
    (fixed) root Z so the returned Z tracks the descent/lift. In legacy mode
    (no gantry DOF) the root IS the gripper, so the DOF term is absent and the
    root pose is used directly.
    """
    motion_robot = handle.carrier_robot or handle.robot
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

    for i in range(1, n_steps + 1):
        t = i * dt
        target = base_target + float(amplitude) * _math.sin(omega * t)
        set_carrier_target_z(stage, handle, target)
        await ctx.step_one()
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

    from simready_benchmark_kit_suite.articulation_phases.jacobian_ik import smoothstep

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

    def _trace_carrier(step_index, commanded):
        if not hasattr(ctx, "log"):
            return
        positions = np.asarray(motion_robot.get_joint_positions(), dtype=np.float64).reshape(-1)
        targets = np.asarray(motion_robot.get_joint_position_targets(), dtype=np.float64).reshape(-1)
        efforts = np.asarray(motion_robot.get_applied_joint_efforts(), dtype=np.float64).reshape(-1)
        actual = float(positions[dof]) if dof < positions.size else float("nan")
        live_target = float(targets[dof]) if dof < targets.size else float("nan")
        ctx.log(
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
                np.round(efforts, 6).tolist(),
                list(getattr(motion_robot, "dof_names", None) or []),
            )
        )

    _trace_carrier(0, start_target)
    trace_steps = {1, max(1, n_steps // 4), max(1, n_steps // 2), max(1, 3 * n_steps // 4), n_steps}

    for i in range(1, n_steps + 1):
        t = smoothstep(i / n_steps)
        target = start_target + (end_target - start_target) * t
        set_carrier_target_z(stage, handle, target)
        await ctx.step_one()
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
        from simready_benchmark_engine_kit.kit_log_monitor import KitLogMonitor
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
    """Author the articulation root's local ``xformOp:orient`` to the given
    world quaternion (scalar-first ``w, x, y, z``).

    The articulation root prim (``/World/AssetRoot/Asset`` for the sample
    grippers) has an identity-oriented parent chain (``AssetRoot`` and
    ``World`` are identity), so the authored LOCAL orientation equals the
    desired WORLD orientation. Sets the existing orient op if present
    (the sample assets author ``quatd xformOp:orient``), else adds one.
    """
    prim = stage.GetPrimAtPath(root_prim_path)
    if not prim or not prim.IsValid():
        raise RuntimeError("Cannot orient gripper: articulation root prim %r not found on " "stage." % root_prim_path)
    quat = Gf.Quatd(
        float(orient_wxyz[0]),
        Gf.Vec3d(float(orient_wxyz[1]), float(orient_wxyz[2]), float(orient_wxyz[3])),
    )
    xf = UsdGeom.Xformable(prim)
    for op in xf.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeOrient:
            op.Set(quat)
            return
    xf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(quat)


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
    current world position so the attach_joint FixedJoint at identity
    local poses rigidly binds gripper-base to gantry-z without any
    geometric snap.

    Drive parameters (matching FET005's gantry):
      - stiffness 50000 N/m
      - damping = 2*sqrt(mass*stiffness) (critical damping)
      - maxForce 10000 N
      - max velocity 20 m/s
    Plenty for moving any reasonable gripper smoothly.
    """
    # PhysxSchema isn't importable outside Kit; lazy-import here so
    # the module loads cleanly in pure-Python unit tests.
    from pxr import PhysxSchema

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
    # base (body1) at identity local poses, so the two bodies coincide
    # rigidly. The joint enforces the base POSITION (and so transmits
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


def _is_robot_world_pin(stage, joint_prim, robot_prim_path):
    """Return whether a joint has one robot body and one world endpoint."""
    if not joint_prim or not joint_prim.IsValid() or not joint_prim.IsA(UsdPhysics.Joint):
        return False
    joint = UsdPhysics.Joint(joint_prim)
    body_paths = []
    for relationship in (joint.GetBody0Rel(), joint.GetBody1Rel()):
        targets = relationship.GetTargets()
        body_paths.append(_owning_rigid_body_path(stage, targets[0]) if targets else None)
    robot_endpoints = [
        body_path for body_path in body_paths if body_path and _path_is_at_or_below(body_path, robot_prim_path)
    ]
    world_endpoints = [body_path for body_path in body_paths if body_path is None]
    return len(robot_endpoints) == 1 and len(world_endpoints) == 1


def _asset_world_pin_paths(stage, robot_prim_path):
    """Discover active asset-authored joints that pin the tested robot."""
    candidate_paths = []
    roots = []
    for prim in (stage.GetDefaultPrim(), stage.GetPrimAtPath(robot_prim_path)):
        if prim and prim.IsValid() and str(prim.GetPath()) not in {str(item.GetPath()) for item in roots}:
            roots.append(prim)
        current = prim
        while current and current.IsValid() and not current.IsPseudoRoot():
            relationship = current.GetRelationship("isaac:physics:robotJoints")
            if relationship:
                candidate_paths.extend(str(path) for path in relationship.GetTargets())
            current = current.GetParent()
    for root in roots:
        for prim in Usd.PrimRange(root):
            if prim.IsA(UsdPhysics.Joint):
                candidate_paths.append(str(prim.GetPath()))
    result = []
    for candidate_path in candidate_paths:
        if candidate_path in result:
            continue
        prim = stage.GetPrimAtPath(candidate_path)
        if prim and prim.IsValid() and prim.IsActive() and _is_robot_world_pin(stage, prim, robot_prim_path):
            result.append(candidate_path)
    return tuple(result)


def _suspend_world_pins(stage, robot_prim_path):
    """Deactivate only world pins that would over-constrain the FET028 rail."""
    pin_paths = list(_asset_world_pin_paths(stage, robot_prim_path))
    try:
        from simready_benchmark_engine_kit.physics_utils import WORLD_PIN_PATH
    except Exception:
        WORLD_PIN_PATH = None
    if WORLD_PIN_PATH is not None:
        framework_path = str(WORLD_PIN_PATH)
        prim = stage.GetPrimAtPath(framework_path)
        if prim and prim.IsValid() and prim.IsActive() and framework_path not in pin_paths:
            pin_paths.append(framework_path)
    suspended = []
    for pin_path in pin_paths:
        prim = stage.GetPrimAtPath(pin_path)
        try:
            prim.SetActive(False)
        except Exception:
            _require_world_pin_restore(stage, suspended)
            raise RuntimeError("failed to suspend FET028 world pin at %s" % pin_path)
        suspended.append(pin_path)
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


def _restore_world_pin(stage, pin_path) -> bool:
    """Reactivate the exact world-pin prim suspended for this run."""
    if not pin_path:
        return True
    prim = stage.GetPrimAtPath(pin_path)
    if not prim or not prim.IsValid():
        return False
    try:
        prim.SetActive(True)
        return True
    except Exception:
        return False

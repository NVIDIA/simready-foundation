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
"""FET004 Joint Movement: drive joints and verify they can move.

WHAT: For each movable joint, apply a velocity drive (or velocity nudge
      fallback) and verify the joint produces relative motion between
      connected bodies.

HOW:  Drive each joint on the DOF implied by its TYPE (revolute ->
      "angular", prismatic -> "linear"); PhysX applies the drive about the
      joint's own authored axis, so there is no need to brute-force every
      axis name.  Rendering dominates this test, so physics runs WITHOUT
      captures first, then the winning direction is re-run WITH captures.

      1. Load asset in white room, gravity=0, visual ground for context.
      2. Pre-checks: skip if no movable joints.
      3. Discover joints; classify each by drive DOF (angular/linear).
         D6/Spherical/other joints have no direct DOF and use the nudge.
      4. Pass 1 (no capture, batched): drive every revolute on "angular"
         and every prismatic on "linear" simultaneously for sign +, then
         re-drive only the still-idle joints for sign - (a joint at its +
         limit only moves toward -).  Drive effort (damping) is ramped
         low -> high across the sim so stiff joints break free while light
         parts are not flung at the start.
      5. Pass 2 (capture winner): re-run the sign that moved the most
         joints, on those joints, with arrows + frame capture, and encode
         the video.
      6. Nudge fallback (no capture): if the drive moved nothing, sweep
         six XYZ velocity directions per still-idle joint (also the path
         for D6/other joints).
      7. Nudge fallback (capture winner): re-run the winning
         (joint, direction) pair with arrows + captures.
      8. Final fallback (nothing worked): render one static frame per
         attempted DOF/direction into a low-fps "tried and failed" video.
      9. PASS if any joint produced movement.  FAIL otherwise.

WHY:  RB.MB.001 requires joints to produce relative motion. Driving the
      joint's own DOF (both directions, with a force ramp) exercises the
      real degree of freedom directly -- faster than sweeping every axis
      and robust to stiff drives, axis orientation, and joint limits.
"""
from simready_benchmark.core.decorator import test
from simready_benchmark_engine_kit.force_display import (
    clear_visuals,
    compute_arrow_length,
    draw_force_arrow,
    get_prim_world_position,
)
from simready_benchmark_engine_kit.physics_utils import (
    find_root_body,
)
from simready_benchmark_kit_suite.fet004_multibody.joint_checks import run_pre_checks
from simready_benchmark_kit_suite.fet004_multibody.joint_discovery import (
    discover_joints,
    sanitize_metric_name,
)

ANGULAR_AXES = ("angular", "rotX", "rotY", "rotZ")
LINEAR_AXES = ("linear", "transX", "transY", "transZ")


def _disable_floor_collision(stage):
    # type: (object) -> None
    """Turn off collision on the room floor while keeping it visible.

    ``room.show_ground()`` enables the floor's visibility AND its collision.
    FET004 runs with gravity=0 and a pinned root, so nothing rests on the
    floor -- but a live floor collider at z=0 silently blocks any joint
    driven toward the floor, which would read as "did not move" (a false
    FAIL). We want the floor for visual context only, so clear its
    collision flag (the room is always at /World/Room).
    """
    try:
        from pxr import UsdPhysics

        prim = stage.GetPrimAtPath("/World/Room/Floor")
        if not prim or not prim.IsValid():
            return
        api = UsdPhysics.CollisionAPI(prim)
        if not api:
            return
        attr = api.GetCollisionEnabledAttr()
        if attr and attr.IsValid():
            attr.Set(False)
        else:
            api.CreateCollisionEnabledAttr(False)
    except Exception:
        pass


def _find_anchor_bodies(joints):
    # type: (list) -> list
    """Base bodies to pin: rigid bodies that are a joint PARENT but never a
    joint CHILD -- the immovable trunk the moving parts hang off.

    Uses discovery's obj-level resolved body paths (``parent_body_path`` /
    ``child_body_path``), so it is correct even when a joint's body
    relationship targets a mesh child. The framework's ``find_root_body``
    compares mesh-level joint targets against obj-level rigid bodies, so its
    "not a child" filter never matches here and it returns whatever body is
    first in traversal order (e.g. the freezer drawer instead of the
    cabinet) -- which left the real base free to drift.
    """
    children = {j.get("child_body_path") for j in joints}
    parents = {j.get("parent_body_path") for j in joints if j.get("parent_body_path")}
    return sorted(b for b in (parents - children) if b)


def _set_body_kinematic(stage, body_path, kinematic):
    # type: (object, str, bool) -> object
    """Toggle a rigid body's kinematic flag; return the prior value.

    A kinematic root is an immovable anchor. Unlike a world FixedJoint (a
    soft solver constraint that drifts under load), a kinematic body
    absorbs ANY reaction force and cannot be pushed. FET004 now drives
    joints with a high force cap, and the equal-and-opposite reaction was
    sliding the whole asset across the floor; pinning the base body
    kinematic plants it so only the joints move. Returns the previous
    ``kinematicEnabled`` value (None if the body is invalid) so the caller
    can restore it after the test.
    """
    try:
        from pxr import UsdPhysics

        prim = stage.GetPrimAtPath(body_path)
        if not prim or not prim.IsValid():
            return None
        rb = UsdPhysics.RigidBodyAPI(prim)
        if not rb:
            return None
        attr = rb.GetKinematicEnabledAttr()
        prev = bool(attr.Get()) if attr and attr.IsDefined() else False
        rb.CreateKinematicEnabledAttr(bool(kinematic))
        return prev
    except Exception:
        return None


def _emit_result_event(**fields):
    # type: (**object) -> None
    """Emit a structured ``joint_movement_result`` event on the engine channel.

    Uses the same ``@@EVENT@@`` stdout channel the orchestrator parses
    (the cook safeguard uses it too), so a full per-joint summary is
    observable when the test is driven interactively from Isaac Sim --
    not just buried in the result JSON. Import is lazy + guarded so this
    is a no-op outside the Kit runner (e.g. unit tests).
    """
    try:
        from simready_benchmark_engine_kit.kit_runner import emit_event

        emit_event("joint_movement_result", **fields)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Drive helpers: activate / deactivate a SINGLE axis on a joint
# ---------------------------------------------------------------------------


def _activate_drive_axis(stage, joint_prim_path, axis, velocity, max_force=None):
    # type: (object, str, str, float, object) -> dict
    """Override or create a drive on one axis to velocity mode.

    ``max_force`` caps the torque/force the drive can exert. The asset's
    joints here author NO drive, so an applied drive inherits PhysX's
    default force cap -- enough to slide a light part, but NOT enough to
    break a heavy door free of a stiff hinge (the artist confirmed the
    doors need a high opening force). Setting a high cap lets the velocity
    drive actually deliver the torque it computes. Returns saved original
    values for restoration (empty dict on failure).
    """
    saved = {}
    try:
        from pxr import UsdPhysics

        prim = stage.GetPrimAtPath(joint_prim_path)
        if not prim or not prim.IsValid():
            return saved

        api = UsdPhysics.DriveAPI(prim, axis)
        stiff_attr = api.GetStiffnessAttr() if api else None
        has_existing = stiff_attr is not None and stiff_attr.IsDefined()

        if not has_existing:
            api = UsdPhysics.DriveAPI.Apply(prim, axis)
            saved["_is_temp"] = True
        else:
            saved["_is_temp"] = False
            v = stiff_attr.Get()
            if v is not None:
                saved["stiffness"] = float(v)
            damp_attr = api.GetDampingAttr()
            if damp_attr.IsDefined():
                v = damp_attr.Get()
                if v is not None:
                    saved["damping"] = float(v)
            vel_attr = api.GetTargetVelocityAttr()
            if vel_attr.IsDefined():
                v = vel_attr.Get()
                if v is not None:
                    saved["target_velocity"] = float(v)
            force_attr = api.GetMaxForceAttr()
            if force_attr.IsDefined():
                v = force_attr.Get()
                if v is not None:
                    saved["max_force"] = float(v)

        api.CreateStiffnessAttr(0.0)
        api.CreateDampingAttr(max(saved.get("damping", 50.0), 10.0))
        api.CreateTargetVelocityAttr(float(velocity))
        if max_force is not None:
            api.CreateMaxForceAttr(float(max_force))
    except Exception:
        pass
    return saved


def _deactivate_drive_axis(stage, joint_prim_path, axis, saved):
    # type: (object, str, str, dict) -> None
    """Restore or remove a drive on one axis."""
    try:
        from pxr import UsdPhysics

        prim = stage.GetPrimAtPath(joint_prim_path)
        if not prim or not prim.IsValid():
            return
        if saved.get("_is_temp"):
            prim.RemoveAPI(UsdPhysics.DriveAPI, axis)
        else:
            api = UsdPhysics.DriveAPI(prim, axis)
            if not api:
                return
            if "stiffness" in saved:
                api.CreateStiffnessAttr(saved["stiffness"])
            if "damping" in saved:
                api.CreateDampingAttr(saved["damping"])
            if "target_velocity" in saved:
                api.CreateTargetVelocityAttr(saved["target_velocity"])
            else:
                api.CreateTargetVelocityAttr(0.0)
            if "max_force" in saved:
                api.CreateMaxForceAttr(saved["max_force"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Velocity nudge fallback (for joints that don't respond to DriveAPI)
# ---------------------------------------------------------------------------


def _apply_velocity_nudge(stage, body_path, direction, nudge=0.1):
    # type: (object, str, tuple, float) -> bool
    """Set linear velocity on a rigid body. Fallback when drives don't work."""
    try:
        from pxr import Gf, UsdPhysics

        prim = stage.GetPrimAtPath(body_path)
        if not prim or not prim.IsValid():
            return False
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            return False
        rb = UsdPhysics.RigidBodyAPI(prim)
        vel = Gf.Vec3f(float(direction[0] * nudge), float(direction[1] * nudge), float(direction[2] * nudge))
        rb.GetVelocityAttr().Set(vel)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Transform save/reset + movement detection
# ---------------------------------------------------------------------------


def _distance(a, b):
    # type: (tuple, tuple) -> float
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _save_transforms(stage, asset_root_path):
    # type: (object, str) -> dict
    saved = {}
    try:
        from pxr import Usd, UsdGeom, UsdPhysics

        root = stage.GetPrimAtPath(asset_root_path)
        if not root or not root.IsValid():
            return saved
        for prim in Usd.PrimRange(root):
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            path = str(prim.GetPath())
            entry = {"prim": prim}
            t_attr = prim.GetAttribute("xformOp:translate")
            if t_attr and t_attr.IsValid():
                entry["translate"] = t_attr.Get()
            o_attr = prim.GetAttribute("xformOp:orient")
            if o_attr and o_attr.IsValid():
                entry["orient"] = o_attr.Get()
            xf = UsdGeom.Xformable(prim)
            entry["world_matrix"] = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            saved[path] = entry
    except Exception:
        pass
    return saved


def _reset_transforms(stage, saved):
    # type: (object, dict) -> None
    try:
        from pxr import Gf, UsdPhysics

        for path, info in saved.items():
            prim = info["prim"]
            if "translate" in info:
                t_attr = prim.GetAttribute("xformOp:translate")
                if t_attr and t_attr.IsValid():
                    t_attr.Set(info["translate"])
            if "orient" in info:
                o_attr = prim.GetAttribute("xformOp:orient")
                if o_attr and o_attr.IsValid():
                    o_attr.Set(info["orient"])
            rb = UsdPhysics.RigidBodyAPI(prim)
            rb.GetVelocityAttr().Set(Gf.Vec3f(0, 0, 0))
            rb.GetAngularVelocityAttr().Set(Gf.Vec3f(0, 0, 0))
    except Exception:
        pass


def _get_world_matrix(stage, prim_path):
    # type: (object, str) -> object
    """Get the current local-to-world transform matrix for a prim."""
    try:
        from pxr import Usd, UsdGeom

        prim = stage.GetPrimAtPath(prim_path)
        if prim and prim.IsValid():
            xf = UsdGeom.Xformable(prim)
            return xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    except Exception:
        pass
    return None


def _get_bbox_diagonal(stage, prim_path):
    # type: (object, str) -> float
    """Compute the bounding box diagonal of a prim (meters)."""
    try:
        from pxr import Usd, UsdGeom

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            return 0.1
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"])
        bbox = cache.ComputeWorldBound(prim)
        r = bbox.ComputeAlignedRange()
        sz = r.GetMax() - r.GetMin()
        return float((sz[0] ** 2 + sz[1] ** 2 + sz[2] ** 2) ** 0.5)
    except Exception:
        return 0.1


def _compute_relative_transform(parent_world, child_world):
    # type: (object, object) -> object
    """Compute child pose in parent's frame: parent_inverse * child."""
    try:
        return parent_world.GetInverse() * child_world
    except Exception:
        return child_world


def _measure_relative_rotation_deg(rel_init, rel_now):
    # type: (object, object) -> float
    """Measure rotation change between two relative transforms (degrees)."""
    try:
        import math

        q_init = rel_init.ExtractRotationQuat()
        q_now = rel_now.ExtractRotationQuat()
        # Angle between quaternions: angle = 2 * acos(|dot(q1, q2)|)
        dot = (
            float(q_init.GetReal()) * float(q_now.GetReal())
            + float(q_init.GetImaginary()[0]) * float(q_now.GetImaginary()[0])
            + float(q_init.GetImaginary()[1]) * float(q_now.GetImaginary()[1])
            + float(q_init.GetImaginary()[2]) * float(q_now.GetImaginary()[2])
        )
        dot = max(-1.0, min(1.0, abs(dot)))
        angle_rad = 2.0 * math.acos(dot)
        return math.degrees(angle_rad)
    except Exception:
        return 0.0


def _measure_relative_translation(rel_init, rel_now):
    # type: (object, object) -> float
    """Measure translation change between two relative transforms (meters)."""
    try:
        t_init = rel_init.ExtractTranslation()
        t_now = rel_now.ExtractTranslation()
        dx = float(t_now[0] - t_init[0])
        dy = float(t_now[1] - t_init[1])
        dz = float(t_now[2] - t_init[2])
        return (dx * dx + dy * dy + dz * dz) ** 0.5
    except Exception:
        return 0.0


class JointTracker:
    """Tracks per-frame joint movement, keeping max values.

    Measures child body pose in parent body's local frame every frame.
    Compares to the reference (frame 0) and keeps the maximum rotation
    and translation seen across all frames.
    """

    def __init__(self, stage, joint):
        # type: (object, dict) -> None
        self.stage = stage
        self.joint = joint
        self.child_path = joint["child_body_path"]
        self.parent_path = joint.get("parent_body_path")
        self.rot_thresh = joint.get("_rot_thresh_deg", 1.0)
        self.trans_thresh_pct = joint.get("_trans_thresh_pct", 2.0)

        self._ref_relative = None  # type: object
        self._bbox_diag = _get_bbox_diagonal(stage, self.child_path)

        self.max_rot_deg = 0.0
        self.max_trans_m = 0.0

        self._capture_reference()

    def _capture_reference(self):
        # type: () -> None
        parent_mat = _get_world_matrix(self.stage, self.parent_path) if self.parent_path else None
        child_mat = _get_world_matrix(self.stage, self.child_path)
        if child_mat is None:
            return
        if parent_mat is not None:
            self._ref_relative = _compute_relative_transform(parent_mat, child_mat)
        else:
            self._ref_relative = child_mat

    def update(self):
        # type: () -> None
        """Sample current frame and update max values."""
        if self._ref_relative is None:
            return
        parent_mat = _get_world_matrix(self.stage, self.parent_path) if self.parent_path else None
        child_mat = _get_world_matrix(self.stage, self.child_path)
        if child_mat is None:
            return
        if parent_mat is not None:
            rel_now = _compute_relative_transform(parent_mat, child_mat)
        else:
            rel_now = child_mat

        rot = _measure_relative_rotation_deg(self._ref_relative, rel_now)
        trans = _measure_relative_translation(self._ref_relative, rel_now)
        if rot > self.max_rot_deg:
            self.max_rot_deg = rot
        if trans > self.max_trans_m:
            self.max_trans_m = trans

    def result(self):
        # type: () -> dict
        """Return measurement results."""
        trans_pct = self.max_trans_m / self._bbox_diag * 100.0 if self._bbox_diag > 1e-6 else 0.0
        moved = self.max_rot_deg >= self.rot_thresh or trans_pct >= self.trans_thresh_pct
        return {
            "rotation_deg": round(self.max_rot_deg, 3),
            "translation_pct": round(trans_pct, 2),
            "translation_m": round(self.max_trans_m, 4),
            "bbox_diag_m": round(self._bbox_diag, 4),
            "moved": moved,
        }


# ---------------------------------------------------------------------------
# Arrow helpers
# ---------------------------------------------------------------------------


def _draw_arrows(stage, joints, arrow_len, drive_axis="angular"):
    # type: (object, list, float, str) -> None
    """Draw arrows showing the current drive axis direction."""
    # Map drive axis name to visual direction
    axis_to_dir = {
        "angular": (0, 0, 1),
        "rotX": (1, 0, 0),
        "rotY": (0, 1, 0),
        "rotZ": (0, 0, 1),
        "linear": (0, 0, 1),
        "transX": (1, 0, 0),
        "transY": (0, 1, 0),
        "transZ": (0, 0, 1),
    }
    direction = axis_to_dir.get(drive_axis, (0, 0, 1))
    for i, joint in enumerate(joints):
        pos = get_prim_world_position(stage, joint["child_body_path"])
        if pos is None:
            continue
        shaft = arrow_len * 0.8
        draw_force_arrow(
            stage,
            pos,
            direction,
            shaft_length=shaft,
            shaft_radius=shaft * 0.04,
            head_length=shaft * 0.25,
            head_radius=shaft * 0.12,
            prim_path="/World/JM_Arrow_%d" % i,
        )


def _clear_arrows(stage, count):
    # type: (object, int) -> None
    for i in range(count):
        try:
            p = stage.GetPrimAtPath("/World/JM_Arrow_%d" % i)
            if p and p.IsValid():
                stage.RemovePrim("/World/JM_Arrow_%d" % i)
        except Exception:
            pass
    clear_visuals(stage)


# ---------------------------------------------------------------------------
# Two-pass simulation helpers
# ---------------------------------------------------------------------------


async def _run_drive_sim(
    ctx, stage, joints, saved, physics, axis, vel, total_frames, capture_interval, capture, show_arrows, arrow_len
):
    # type: (object, object, list, dict, object, str, float, int, int, bool, bool, float) -> tuple
    """Run one drive-axis simulation. Returns (trackers, captured_frames).

    ``capture`` toggles per-frame ``ctx.capture_frame`` calls and arrow
    redraws.  Pass 1 (search) calls this with capture=False.  Pass 2
    (record) calls it with capture=True on the winning axis.
    """
    physics.stop()
    _reset_transforms(stage, saved)
    activated = {}  # type: dict
    for j in joints:
        sv = _activate_drive_axis(stage, j["prim_path"], axis, vel)
        activated[j["prim_path"]] = sv
    if capture and show_arrows:
        _draw_arrows(stage, joints, arrow_len, drive_axis=axis)
    physics.play()

    trackers = {j["name"]: JointTracker(stage, j) for j in joints}
    captured = []  # type: list
    for frame in range(total_frames):
        await ctx.physics_step()
        for tracker in trackers.values():
            tracker.update()
        ctx.scene.update_camera_follow()
        if capture and frame % capture_interval == 0:
            if show_arrows:
                _draw_arrows(stage, joints, arrow_len, drive_axis=axis)
            captured.append(await ctx.capture_frame(label="joint_movement"))
        await ctx.physics_advance()

    physics.stop()
    for j in joints:
        _deactivate_drive_axis(stage, j["prim_path"], axis, activated[j["prim_path"]])
    return trackers, captured


async def _run_nudge_sim(
    ctx,
    stage,
    joint,
    saved,
    physics,
    direction,
    total_frames,
    capture_interval,
    capture,
    show_arrows,
    arrow_len,
    joint_count,
):
    # type: (object, object, dict, dict, object, tuple, int, int, bool, bool, float, int) -> tuple
    """Run one velocity-nudge simulation on a single joint.

    Same capture toggle as ``_run_drive_sim``.  Returns (tracker, frames).
    """
    physics.stop()
    _reset_transforms(stage, saved)
    if capture and show_arrows:
        _clear_arrows(stage, joint_count)
        pos = get_prim_world_position(stage, joint["child_body_path"])
        if pos:
            shaft = arrow_len * 0.8
            draw_force_arrow(
                stage,
                pos,
                direction,
                shaft_length=shaft,
                shaft_radius=shaft * 0.04,
                head_length=shaft * 0.25,
                head_radius=shaft * 0.12,
                prim_path="/World/JM_Arrow_0",
            )
    physics.play()

    tracker = JointTracker(stage, joint)
    captured = []  # type: list
    for frame in range(total_frames):
        _apply_velocity_nudge(stage, joint["child_body_path"], direction)
        await ctx.physics_step()
        tracker.update()
        ctx.scene.update_camera_follow()
        if capture and frame % capture_interval == 0:
            captured.append(await ctx.capture_frame(label="joint_movement"))
        await ctx.physics_advance()

    physics.stop()
    return tracker, captured


async def _capture_tried_axes_video(
    ctx, stage, joints, saved, tried_drive_axes, tried_nudges, arrow_len, show_arrows, fallback_fps
):
    # type: (object, object, list, dict, list, list, float, bool, float) -> list
    """Produce one still frame per attempted axis/nudge for the fallback video.

    No physics simulation is run -- just draw the arrows, capture, move on.
    Each entry in ``tried_nudges`` is (joint_dict, direction_tuple, label).
    """
    frames = []  # type: list
    # Drive axes: one frame showing all joints with the axis arrow.
    for axis in tried_drive_axes:
        _reset_transforms(stage, saved)
        if show_arrows:
            _draw_arrows(stage, joints, arrow_len, drive_axis=axis)
        await ctx.settle(count=1)
        frames.append(await ctx.capture_frame(label="joint_movement_tried"))
    # Nudges: one frame per (joint, direction).
    for joint, direction, _label in tried_nudges:
        _reset_transforms(stage, saved)
        if show_arrows:
            _clear_arrows(stage, len(joints))
            pos = get_prim_world_position(stage, joint["child_body_path"])
            if pos:
                shaft = arrow_len * 0.8
                draw_force_arrow(
                    stage,
                    pos,
                    direction,
                    shaft_length=shaft,
                    shaft_radius=shaft * 0.04,
                    head_length=shaft * 0.25,
                    head_radius=shaft * 0.12,
                    prim_path="/World/JM_Arrow_0",
                )
        await ctx.settle(count=1)
        frames.append(await ctx.capture_frame(label="joint_movement_tried"))
    _clear_arrows(stage, len(joints))
    return frames


def _record_joint_metrics(ctx, joints, trackers, joint_moved):
    # type: (object, list, dict, dict) -> bool
    """Write per-joint metrics from a trackers dict. Returns True if any moved."""
    any_moved = False
    for j in joints:
        tracker = trackers.get(j["name"])
        if tracker is None:
            continue
        m = tracker.result()
        safe = sanitize_metric_name(j["name"])
        ctx.add_metric("jm_joint_%s_rot_deg" % safe, m["rotation_deg"])
        ctx.add_metric("jm_joint_%s_trans_pct" % safe, m["translation_pct"])
        ctx.add_metric("jm_joint_%s_bbox_m" % safe, m["bbox_diag_m"])
        if m["moved"]:
            joint_moved[j["name"]] = True
            any_moved = True
    return any_moved


# ---------------------------------------------------------------------------
# Type-aware batched drive (axis derived from joint type, +/- signs, ramp)
# ---------------------------------------------------------------------------


def _drive_dof_for_joint(j):
    # type: (dict) -> object
    """Return the drive DOF name for a joint, derived from its type.

    Revolute -> "angular", Prismatic -> "linear" (PhysX applies the drive
    about the joint's own authored axis, so the X/Y/Z axis letter is only
    needed for the arrow direction). Returns None for D6/Spherical/other
    joints, which have no single obvious DOF and fall back to the velocity
    nudge.
    """
    t = j.get("type_name")
    if t == "PhysicsRevoluteJoint":
        return "angular"
    if t == "PhysicsPrismaticJoint":
        return "linear"
    return None


def _open_direction(stage, j):
    # type: (object, dict) -> tuple
    """Derive the OPEN drive direction for a joint from its authored limits.

    A joint's drive target and its lower/upper limits live in the same DOF
    coordinate, so "open" is simply the limit farthest from the closed rest
    (assumed ~0): a door at [0, 130] opens toward +130, one at [-130, 0]
    toward -130, a drawer at [-0.42, 0.01] toward -0.42. Driving each joint
    toward ITS OWN open end (rather than one shared sign for the whole
    batch) keeps french doors from jamming each other shut at the center.

    Returns ``(sign, travel)`` -- sign is +1.0/-1.0, travel is the authored
    range to the open end (degrees for revolute, stage-linear-units for
    prismatic). Returns ``(None, None)`` when the limits are missing,
    infinite, or symmetric/zero (no unambiguous open end) -- those joints
    fall back to the +/- search.
    """
    try:
        import math

        prim = stage.GetPrimAtPath(j["prim_path"])
        if not prim or not prim.IsValid():
            return (None, None)
        lo_a = prim.GetAttribute("physics:lowerLimit")
        hi_a = prim.GetAttribute("physics:upperLimit")
        lo = lo_a.Get() if lo_a and lo_a.IsDefined() else None
        hi = hi_a.Get() if hi_a and hi_a.IsDefined() else None
        if lo is None or hi is None:
            return (None, None)
        lo = float(lo)
        hi = float(hi)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            return (None, None)
        open_target = lo if abs(lo) > abs(hi) else hi
        if abs(open_target) < 1e-6:
            return (None, None)
        return (1.0 if open_target > 0 else -1.0, abs(open_target))
    except Exception:
        return (None, None)


def _set_drive_damping(stage, joint_prim_path, axis, damping):
    # type: (object, str, str, float) -> None
    """Update the damping on an already-active drive (used for the ramp)."""
    try:
        from pxr import UsdPhysics

        prim = stage.GetPrimAtPath(joint_prim_path)
        if not prim or not prim.IsValid():
            return
        api = UsdPhysics.DriveAPI(prim, axis)
        if api:
            api.CreateDampingAttr(float(damping))
    except Exception:
        pass


def _world_bbox_center(stage, prim_path):
    # type: (object, str) -> object
    """World-space bounding-box center of a prim (the part's visual middle).

    Used to anchor the motion arrow on the MIDDLE of the moving part (e.g.
    a door panel) rather than on its body origin, which for a hinged door
    sits at the hinge. A fresh BBoxCache is built each call because the
    part is moving during the sim.
    """
    try:
        from pxr import Usd, UsdGeom

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            return None
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
        rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        if rng.IsEmpty():
            return None
        mn = rng.GetMin()
        mx = rng.GetMax()
        return (
            (float(mn[0]) + float(mx[0])) * 0.5,
            (float(mn[1]) + float(mx[1])) * 0.5,
            (float(mn[2]) + float(mx[2])) * 0.5,
        )
    except Exception:
        return None


def _draw_motion_arrows(stage, joints, arrow_len, ref_centers, eps):
    # type: (object, list, float, dict, float) -> None
    """Draw one arrow per joint showing where its part is ACTUALLY moving.

    For each joint, the arrow is anchored at the part's current bbox center
    (its visual middle) and points along the displacement from the part's
    reference (pre-play) center -- i.e. the real direction the door swings
    or the drawer slides ("inside-out" as a door opens). This is derived
    from observed motion, so it is correct regardless of joint type, axis
    orientation, or drive sign. A joint that has not moved past ``eps`` yet
    draws no arrow (its stale arrow, if any, is removed) so the viewer never
    sees an arrow on a part that is not moving.
    """
    for i, joint in enumerate(joints):
        path = "/World/JM_Arrow_%d" % i
        prev = stage.GetPrimAtPath(path)
        if prev and prev.IsValid():
            stage.RemovePrim(path)
        ref = ref_centers.get(joint["name"])
        cur = _world_bbox_center(stage, joint["child_body_path"])
        if ref is None or cur is None:
            continue
        d = (cur[0] - ref[0], cur[1] - ref[1], cur[2] - ref[2])
        dist = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) ** 0.5
        if dist < eps:
            continue
        direction = (d[0] / dist, d[1] / dist, d[2] / dist)
        shaft = arrow_len * 0.8
        draw_force_arrow(
            stage,
            cur,
            direction,
            shaft_length=shaft,
            shaft_radius=shaft * 0.04,
            head_length=shaft * 0.25,
            head_radius=shaft * 0.12,
            prim_path=path,
        )


def _accumulate(joints, trackers, acc):
    # type: (list, dict, dict) -> None
    """Merge tracker results into acc: keep max rot/trans, OR the moved flag."""
    for j in joints:
        tracker = trackers.get(j["name"])
        if tracker is None:
            continue
        m = tracker.result()
        a = acc.get(j["name"])
        if a is None:
            acc[j["name"]] = {
                "rotation_deg": m["rotation_deg"],
                "translation_pct": m["translation_pct"],
                "translation_m": m["translation_m"],
                "bbox_diag_m": m["bbox_diag_m"],
                "moved": m["moved"],
            }
        else:
            a["rotation_deg"] = max(a["rotation_deg"], m["rotation_deg"])
            a["translation_pct"] = max(a["translation_pct"], m["translation_pct"])
            a["translation_m"] = max(a["translation_m"], m["translation_m"])
            a["bbox_diag_m"] = m["bbox_diag_m"]
            a["moved"] = a["moved"] or m["moved"]


async def _run_batched_drive_sim(
    ctx,
    stage,
    drive_joints,
    saved,
    physics,
    sign,
    ang_vel,
    lin_vel,
    damp_start,
    damp_max,
    total_frames,
    capture_interval,
    capture,
    show_arrows,
    arrow_len,
    max_force=None,
):
    # type: (object, object, list, dict, object, float, float, float, float, float, int, int, bool, bool, float, object) -> tuple
    """Drive each joint on its own DOF (angular/linear) simultaneously.

    Each joint is driven toward its OWN open direction when known: a joint
    carrying ``_open_sign`` (set from its authored limits) uses that sign so
    french doors swing apart instead of jamming; joints without it use the
    global ``sign`` (the +/- search fallback). Drive effort (damping) is
    ramped from ``damp_start`` to ``damp_max`` across the sim, and
    ``max_force`` caps the torque so heavy/stiff joints can actually break
    free. Resets transforms first; deactivates all drives at the end.
    Returns (trackers, captured_frames).
    """
    import time

    physics.stop()
    _reset_transforms(stage, saved)

    s = 1.0 if sign >= 0 else -1.0
    activated = {}  # prim_path -> (dof, saved)
    for j in drive_joints:
        dof = _drive_dof_for_joint(j)
        if dof is None:
            continue
        js = j.get("_open_sign")
        sj = js if js is not None else s
        vmag = j.get("_open_vel_mag")
        if vmag is None:
            vmag = ang_vel if dof == "angular" else lin_vel
        vel = vmag * sj
        sv = _activate_drive_axis(stage, j["prim_path"], dof, vel, max_force=max_force)
        activated[j["prim_path"]] = (dof, sv)
        _set_drive_damping(stage, j["prim_path"], dof, damp_start)

    # Reference (pre-play) part centers, so the capture pass can draw arrows
    # along each part's REAL motion (see _draw_motion_arrows). Anchored on the
    # bbox center -- the visual middle of the door/drawer, not the hinge.
    ref_centers = {}  # type: dict
    arrow_eps = max(1e-4, arrow_len * 0.02)
    if capture and show_arrows:
        for j in drive_joints:
            ref_centers[j["name"]] = _world_bbox_center(stage, j["child_body_path"])
    physics.play()

    trackers = {j["name"]: JointTracker(stage, j) for j in drive_joints}
    captured = []  # type: list
    denom = max(1, total_frames - 1)
    ratio = (damp_max / damp_start) if damp_start > 0 else 1.0
    deadline = time.monotonic() + 120.0
    for frame in range(total_frames):
        damping = damp_start * (ratio ** (float(frame) / denom))
        for ppath, (dof, _sv) in activated.items():
            _set_drive_damping(stage, ppath, dof, damping)
        await ctx.physics_step()
        for tracker in trackers.values():
            tracker.update()
        ctx.scene.update_camera_follow()
        if capture and frame % capture_interval == 0:
            if show_arrows:
                _draw_motion_arrows(stage, drive_joints, arrow_len, ref_centers, arrow_eps)
            captured.append(await ctx.capture_frame(label="joint_movement"))
        if time.monotonic() > deadline:
            ctx.step("Batched drive sim hit 120s watchdog at frame %d" % frame)
            break
        await ctx.physics_advance()

    physics.stop()
    for ppath, (dof, sv) in activated.items():
        _deactivate_drive_axis(stage, ppath, dof, sv)
    return trackers, captured


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


@test(
    features=[
        {"id": "FET004_BASE_PHYSX", "version": ">=0.1.0"},
        {"id": "FET004_ROBOT_PHYSX", "version": ">=0.1.0"},
    ],
    name="joint_movement",
    description=(
        "For each authored joint on the asset, applies a velocity drive "
        "(falling back to a velocity nudge for joints without DriveAPI) "
        "and verifies that relative motion between the joint's connected "
        "bodies actually occurs. Validates that joints aren't seized, "
        "their axis is correctly authored, and the bodies they connect "
        "are free to move per the joint type."
    ),
    expected_video=(
        "Each authored joint is exercised one at a time. The two bodies "
        "connected by that joint visibly move relative to each other in "
        "the joint's allowed direction (rotate around the axis for a "
        "revolute joint, slide for a prismatic, etc.). A joint that "
        "produces no visible relative motion fails the check."
    ),
    version="2.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "physics_fps": 240,
        "capture_fps": 15,
        "settle_frames": 5,
        "asset_load_timeout": 30,
        # Drives each joint for this long. This is ALSO the recorded video
        # length, so keep it long enough to clearly SEE the joint move -- a
        # sub-second clip is too short to read. The no-capture probe passes are
        # physics-only (no render), so the extra duration is cheap; the captured
        # record pass is what the viewer sees.
        "test_duration_seconds": 3.0,
        "angular_velocity_deg_s": 45.0,
        "linear_velocity_m_s": 0.05,
        # Drive-effort (damping) ramp bounds. Start low so light parts are
        # not flung at the start; ramp to the cap so stiff/heavy joints
        # still break free. Applied across each batched-drive sim.
        "drive_damping_start": 5.0,
        "drive_damping_max": 10000.0,
        # The search passes ramp damping from a low floor so stiff/light
        # joints are probed without flinging anything. But that floor keeps
        # the drive weak for most of the clip, so the RECORDED pass barely
        # moved (a door cracked ~2 deg). The record pass re-runs joints that
        # already proved they move, so it can start the ramp high -- the
        # part swings/slides clearly from the first frame of the video.
        "drive_damping_record_start": 1000.0,
        # Max torque/force the applied drive may exert. These joints author
        # no drive, so an applied drive otherwise inherits PhysX's default
        # cap -- enough for a light part but NOT to break a heavy door free
        # of a stiff hinge (artist-confirmed). A high cap lets the drive
        # deliver the torque it computes; the joint's own limit still stops
        # the motion at the open end.
        "drive_max_force": 1.0e7,
        "rotation_threshold_deg": 1.0,
        "translation_threshold_pct": 2.0,
        "show_force_arrows": True,
        # Fallback video FPS when nothing worked. Low so the viewer can
        # see each tried axis clearly.
        "fallback_video_fps": 0.5,
    },
    max_duration=300,
)
async def test_joint_movement(ctx):
    """Joint movement -- try drive axes one at a time until joints move."""
    cfg = ctx.config
    physics_fps = int(cfg["physics_fps"])
    capture_fps = int(cfg["capture_fps"])
    ang_vel = float(cfg["angular_velocity_deg_s"])
    lin_vel = float(cfg["linear_velocity_m_s"])
    show_arrows = bool(cfg["show_force_arrows"])

    # --- Load asset + room (before pre-checks, same as FET003) ---
    ctx.set_settle_frames(cfg["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=cfg["asset_load_timeout"])
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0.3, 0.4, 0.7)
    room.show_ground(color=(0.25, 0.35, 0.6))
    # Seat the asset ON the ground (not floating) so the scene reads
    # naturally. This test runs with gravity=0 and a pinned root, so the
    # floor never bears weight -- its collision is disabled below (once the
    # stage is in hand) so a joint driven toward the floor (a flap, a
    # downward prismatic) is not silently blocked and misread as "did not
    # move".
    room.place_asset_at_ground()

    # --- Pre-checks (before physics/camera -- fast skip) ---
    pre = run_pre_checks(ctx)
    if pre is not None:
        if pre.startswith("SKIP:"):
            reason = pre[5:].strip()
            # Structural non-applicability -- the asset simply has nothing
            # for this test to exercise. Always SKIP, regardless of the
            # asset's validation claim: an asset with only fixed joints
            # (or no joints at all) cannot "fail" a joint-movement test.
            if reason.startswith("No joints found") or reason.startswith("All joints are FixedJoint"):
                ctx.skip(reason)
            else:
                ctx.precheck_failure(reason)
        else:
            ctx.fail(pre)
        return

    # --- Discover joints (also before physics) ---
    import omni.usd

    stage = omni.usd.get_context().get_stage()
    # Disable the (purposeless, gravity=0) floor collider now that the stage
    # is available -- see place_asset_at_ground() comment above.
    _disable_floor_collision(stage)
    asset_path = ctx.scene.asset.prim_path
    joints = discover_joints(stage, asset_path)
    if not joints:
        ctx.precheck_failure("No joints with child bodies found")
        return

    ctx.step("Found %d movable joints" % len(joints))

    # Inject config thresholds into joint dicts for _measure_joint_movement
    rot_thresh = float(cfg["rotation_threshold_deg"])
    trans_thresh = float(cfg["translation_threshold_pct"])
    for j in joints:
        j["_rot_thresh_deg"] = rot_thresh
        j["_trans_thresh_pct"] = trans_thresh

    # --- Classify joints by drive DOF derived from joint type ---
    # Revolute -> "angular", Prismatic -> "linear" (PhysX applies the drive
    # about the joint's own authored axis). D6/Spherical/other joints have no
    # direct DOF mapping and fall through to the velocity-nudge fallback.
    batchable = [j for j in joints if _drive_dof_for_joint(j) is not None]

    # --- Lighting + Camera (only if pre-checks passed) ---
    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=0.0, fps=float(physics_fps))
    ctx.scene.setup_camera_follow()
    await ctx.settle(count=3)

    # Cook dynamic mesh colliders (and author missing mass) OFF the timeline
    # path, time-boxed, BEFORE play() -- a cold SDF cook triggered by play()
    # can freeze the run. Reports a clean failure if a collider cannot cook.
    from simready_benchmark_engine_kit.physics_utils import cook_skip_message

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        return

    # --- Anchor the base body/bodies (make them kinematic) ---
    # A kinematic base is immovable: it absorbs the reaction force from
    # driving the joints (a world FixedJoint flexed and let the whole asset
    # slide across the floor). Only joint DOFs can then produce motion, so
    # any detected movement is real. Restored in cleanup.
    anchor_bodies = _find_anchor_bodies(joints)
    if not anchor_bodies:
        # Fallback for odd rigs (e.g. a single body, or all joints attached
        # straight to world): best-effort base from the framework helper.
        rb = find_root_body(stage, asset_path)
        anchor_bodies = [rb] if rb else []
    kin_saved = {}  # type: dict  body_path -> prior kinematicEnabled
    for b in anchor_bodies:
        prev = _set_body_kinematic(stage, b, True)
        if prev is not None:
            kin_saved[b] = prev
    if anchor_bodies:
        ctx.step("Anchored base body(ies) kinematic: %s" % ", ".join(anchor_bodies))
    else:
        ctx.step("WARNING: Could not find a base body to anchor")

    # --- Save initial state ---
    saved = _save_transforms(stage, asset_path)
    arrow_len = compute_arrow_length(stage, asset_path) if show_arrows else 0.15

    # --- Config derived values ---
    test_dur = float(cfg["test_duration_seconds"])
    capture_interval = max(1, physics_fps // capture_fps)
    total_frames = int(test_dur * physics_fps)
    fallback_fps = float(cfg["fallback_video_fps"])

    frames_captured = []  # type: list
    any_joint_moved = False
    joint_moved = {}  # joint name -> bool
    winning_nudge = None  # (joint_dict, direction_tuple, label)
    acc = {}  # joint name -> best {rotation_deg, translation_pct, bbox_diag_m, moved}
    tried_drive_axes = []  # type: list (DOF labels, for the fallback overview)

    damp_start = float(cfg["drive_damping_start"])
    damp_max = float(cfg["drive_damping_max"])
    damp_record_start = float(cfg["drive_damping_record_start"])
    max_force = float(cfg["drive_max_force"])

    # --- Resolve each joint's OPEN direction from its authored limits. ---
    # A joint with informative limits is driven straight toward its OWN open
    # end (so french doors swing APART instead of jamming each other shut at
    # the center seam); joints without usable limits fall back to the +/-
    # search.
    # Scale each directed joint's target speed to its OWN travel so it
    # reaches its open limit within the clip regardless of range -- a
    # short-range door and a long-throw drawer both open fully (the drawer
    # at the fixed 0.05 m/s only reached ~36% of its 0.42 m in 3 s). Never
    # slower than the configured baseline, so tiny-range joints are not
    # under-driven. ``0.8`` leaves the last fifth of the clip with the part
    # held open.
    open_fill = 0.8 * max(test_dur, 1e-3)
    for j in batchable:
        sgn, travel = _open_direction(stage, j)
        j["_open_sign"] = sgn
        j["_open_travel"] = travel
        if sgn is not None:
            base = ang_vel if _drive_dof_for_joint(j) == "angular" else lin_vel
            j["_open_vel_mag"] = max(base, float(travel) / open_fill)
    directed = [j for j in batchable if j.get("_open_sign") is not None]
    undirected = [j for j in batchable if j.get("_open_sign") is None]
    if batchable:
        tried_drive_axes = sorted({_drive_dof_for_joint(j) for j in batchable})

    winning_sign = None  # type: object (undirected +/- result, for the event)
    record_joints = []  # type: list

    # --- Pass 1a (search, no capture): drive each DIRECTED joint toward its
    #     own open limit, all simultaneously. ---
    if directed:
        ctx.step("Pass 1 (search) - drive %d joint(s) toward their open limit" % len(directed))
        trackers_d, _ = await _run_batched_drive_sim(
            ctx,
            stage,
            directed,
            saved,
            physics,
            1.0,
            ang_vel,
            lin_vel,
            damp_start,
            damp_max,
            total_frames,
            capture_interval,
            capture=False,
            show_arrows=False,
            arrow_len=arrow_len,
            max_force=max_force,
        )
        _accumulate(directed, trackers_d, acc)

    # --- Pass 1b (search, no capture): +/- probe for UNDIRECTED joints (no
    #     usable limits). Drive sign + then - on the still-idle ones. ---
    if undirected:
        ctx.step("Pass 1 (search) - +/- probe on %d unlimited joint(s)" % len(undirected))
        trackers_pos, _ = await _run_batched_drive_sim(
            ctx,
            stage,
            undirected,
            saved,
            physics,
            1.0,
            ang_vel,
            lin_vel,
            damp_start,
            damp_max,
            total_frames,
            capture_interval,
            capture=False,
            show_arrows=False,
            arrow_len=arrow_len,
            max_force=max_force,
        )
        _accumulate(undirected, trackers_pos, acc)
        movers_pos = [j for j in undirected if acc.get(j["name"], {}).get("moved")]
        not_moved = [j for j in undirected if not acc.get(j["name"], {}).get("moved")]
        movers_neg = []  # type: list
        if not_moved:
            trackers_neg, _ = await _run_batched_drive_sim(
                ctx,
                stage,
                not_moved,
                saved,
                physics,
                -1.0,
                ang_vel,
                lin_vel,
                damp_start,
                damp_max,
                total_frames,
                capture_interval,
                capture=False,
                show_arrows=False,
                arrow_len=arrow_len,
                max_force=max_force,
            )
            _accumulate(not_moved, trackers_neg, acc)
            movers_neg = [j for j in not_moved if acc.get(j["name"], {}).get("moved")]
        # Pin the sign that moved the most undirected joints onto those movers
        # so the record pass drives them the same (proven) way.
        if movers_pos or movers_neg:
            winning_sign = 1.0 if len(movers_pos) >= len(movers_neg) else -1.0
            for j in (movers_pos if winning_sign > 0 else movers_neg):
                j["_open_sign"] = winning_sign

    # --- Pass 2 (record, with capture): re-drive every joint that moved, each
    #     toward its own open direction, to produce the summary video. ---
    record_joints = [j for j in batchable if acc.get(j["name"], {}).get("moved")]
    if record_joints:
        ctx.step("Pass 2 (record) - drive %d moving joint(s) for capture" % len(record_joints))
        trackers_rec, frames = await _run_batched_drive_sim(
            ctx,
            stage,
            record_joints,
            saved,
            physics,
            1.0,
            ang_vel,
            lin_vel,
            damp_record_start,
            damp_max,
            total_frames,
            capture_interval,
            capture=True,
            show_arrows=show_arrows,
            arrow_len=arrow_len,
            max_force=max_force,
        )
        _accumulate(record_joints, trackers_rec, acc)
        frames_captured.extend(frames)

    # --- Commit batched-drive metrics + movement flags ---
    for j in batchable:
        a = acc.get(j["name"])
        if a is None:
            continue
        safe = sanitize_metric_name(j["name"])
        ctx.add_metric("jm_joint_%s_rot_deg" % safe, round(a["rotation_deg"], 3))
        ctx.add_metric("jm_joint_%s_trans_pct" % safe, round(a["translation_pct"], 2))
        ctx.add_metric("jm_joint_%s_bbox_m" % safe, round(a["bbox_diag_m"], 4))
        # Fraction of the joint's authored travel actually reached -- the
        # meaningful "how far did it open" number. Informational only: a
        # stiff-but-functional joint that moves a little still PASSES (the
        # pass criterion stays "moved > threshold"), it is not failed for
        # not reaching 100%.
        travel = j.get("_open_travel")
        if travel:
            dof = _drive_dof_for_joint(j)
            achieved = a["rotation_deg"] if dof == "angular" else a["translation_m"]
            pct = round(min(achieved / travel * 100.0, 100.0), 1)
            ctx.add_metric("jm_joint_%s_pct_of_travel" % safe, pct)
            a["pct_of_travel"] = pct
        if a["moved"]:
            joint_moved[j["name"]] = True
    any_joint_moved = any(joint_moved.values())

    # --- Nudge fallback Pass 1 (no capture) ---
    velocity_dirs = [
        ((1, 0, 0), "+X"),
        ((-1, 0, 0), "-X"),
        ((0, 1, 0), "+Y"),
        ((0, -1, 0), "-Y"),
        ((0, 0, 1), "+Z"),
        ((0, 0, -1), "-Z"),
    ]
    tried_nudges = []  # type: list (joint, direction, label)
    if not any_joint_moved:
        remaining = [j for j in joints if j["name"] not in joint_moved]
        if remaining:
            ctx.step("Drives failed. Pass 1 (search) - velocity nudges...")
        for j in remaining:
            if winning_nudge is not None:
                break
            for direction, dname in velocity_dirs:
                tried_nudges.append((j, direction, dname))
                ctx.step("  %s nudge %s" % (j["name"], dname))
                tracker, _ = await _run_nudge_sim(
                    ctx,
                    stage,
                    j,
                    saved,
                    physics,
                    direction,
                    total_frames,
                    capture_interval,
                    capture=False,
                    show_arrows=False,
                    arrow_len=arrow_len,
                    joint_count=len(joints),
                )
                m = tracker.result()
                safe = sanitize_metric_name(j["name"])
                ctx.add_metric("jm_joint_%s_rot_deg" % safe, m["rotation_deg"])
                ctx.add_metric("jm_joint_%s_trans_pct" % safe, m["translation_pct"])
                ctx.add_metric("jm_joint_%s_bbox_m" % safe, m["bbox_diag_m"])
                if m["moved"]:
                    winning_nudge = (j, direction, dname)
                    joint_moved[j["name"]] = True
                    any_joint_moved = True
                    ctx.step("    -> PASSED (velocity %s)" % dname)
                    break

    # --- Nudge fallback Pass 2 (capture winner) ---
    if winning_nudge is not None:
        j, direction, dname = winning_nudge
        ctx.step("Pass 2 (record) - nudge %s direction %s" % (j["name"], dname))
        tracker, frames = await _run_nudge_sim(
            ctx,
            stage,
            j,
            saved,
            physics,
            direction,
            total_frames,
            capture_interval,
            capture=True,
            show_arrows=show_arrows,
            arrow_len=arrow_len,
            joint_count=len(joints),
        )
        frames_captured.extend(frames)
        m = tracker.result()
        safe = sanitize_metric_name(j["name"])
        ctx.add_metric("jm_joint_%s_rot_deg" % safe, m["rotation_deg"])
        ctx.add_metric("jm_joint_%s_trans_pct" % safe, m["translation_pct"])
        ctx.add_metric("jm_joint_%s_bbox_m" % safe, m["bbox_diag_m"])

    # --- Final fallback: no axis/nudge worked. Render a tried-and-failed video. ---
    if not any_joint_moved and (tried_drive_axes or tried_nudges):
        ctx.step("No movement detected. Building tried-and-failed overview video.")
        tried_frames = await _capture_tried_axes_video(
            ctx, stage, joints, saved, tried_drive_axes, tried_nudges, arrow_len, show_arrows, fallback_fps
        )
        if tried_frames:
            ctx.encode_video(tried_frames, fps=fallback_fps, label="joint_movement_tried", role="error")

    # --- Mark joints that never moved ---
    for j in joints:
        if j["name"] not in joint_moved:
            joint_moved[j["name"]] = False

    # --- Clean up ---
    physics.stop()
    for b, prev in kin_saved.items():
        _set_body_kinematic(stage, b, prev)
    _reset_transforms(stage, saved)
    _clear_arrows(stage, len(joints))

    # --- Encode main video (only if we have captured frames from a winner) ---
    video_path = None
    if frames_captured:
        video_path = ctx.encode_video(frames_captured, fps=capture_fps, label="joint_movement", role="summary")

    # --- Metrics ---
    joints_passed = sum(1 for v in joint_moved.values() if v)
    joints_failed = sum(1 for v in joint_moved.values() if not v)
    total = joints_passed + joints_failed
    ctx.add_metric("jm_joints_total", total)
    ctx.add_metric("jm_joints_passed", joints_passed)
    ctx.add_metric("jm_joints_failed", joints_failed)
    for j in joints:
        safe = sanitize_metric_name(j["name"])
        ctx.add_metric("jm_joint_%s_status" % safe, "passed" if joint_moved.get(j["name"]) else "failed")

    # --- Instrumentation: emit a full per-joint summary on the event channel ---
    # Emitted on BOTH outcomes (before the pass/fail branch) so an
    # interactive Isaac run dumps everything in one place: per-joint
    # moved/rotation/translation, totals, the winning drive sign, the
    # tried DOFs, and the actual recorded video path.
    import os as _os

    per_joint = {}  # type: dict
    for j in joints:
        name = j["name"]
        a = acc.get(name) or {}
        sgn = j.get("_open_sign")
        per_joint[name] = {
            "type": j.get("type_name"),
            "axis": j.get("axis"),
            "open_sign": ("+" if sgn and sgn > 0 else "-" if sgn else None),
            "open_travel": j.get("_open_travel"),
            "moved": bool(joint_moved.get(name)),
            "rotation_deg": a.get("rotation_deg"),
            "translation_pct": a.get("translation_pct"),
            "translation_m": a.get("translation_m"),
            "pct_of_travel": a.get("pct_of_travel"),
            "bbox_diag_m": a.get("bbox_diag_m"),
        }
    _emit_result_event(
        asset=asset_path,
        passed=(joints_passed >= 1),
        joints_total=total,
        joints_passed=joints_passed,
        joints_failed=joints_failed,
        winning_sign=("+" if winning_sign and winning_sign > 0 else "-" if winning_sign else None),
        winning_nudge=(winning_nudge[2] if winning_nudge else None),
        tried_drive_dofs=tried_drive_axes,
        video=(_os.path.basename(video_path) if video_path else None),
        joints=per_joint,
    )

    # --- Result ---
    if joints_passed >= 1:
        ctx.log("Joint movement PASSED: %d/%d joints responded" % (joints_passed, total))
    else:
        tried_desc = ", ".join(tried_drive_axes) if tried_drive_axes else "none"
        ctx.fail(
            "Joint movement FAILED: 0/%d joints responded.\n"
            "Tried drive DOFs (both directions): %s, plus velocity nudges -- "
            "no movement detected on any.\n"
            "Fix: Check joint configuration, drive settings, and "
            "joint limits." % (total, tried_desc)
        )

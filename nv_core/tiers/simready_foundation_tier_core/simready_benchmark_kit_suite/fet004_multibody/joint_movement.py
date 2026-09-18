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

WHAT: For each movable joint, apply a velocity drive (or type-aware fallback)
      and verify the joint produces relative motion between
      connected bodies.

HOW:  Drive each joint on the DOF implied by its TYPE (revolute ->
      "angular", prismatic -> "linear"); PhysX applies the drive about the
      joint's own authored axis, so there is no need to brute-force every
      axis name.  Rendering dominates this test, so physics runs WITHOUT
      captures first, then the winning direction is re-run WITH captures.

      1. Load asset in white room, gravity=0, visual ground for context.
      2. Pre-checks: skip if no movable joints.
      3. Discover joints; classify each by drive DOF (angular/linear).
         PhysX spherical joints use a temporary external D6 driver because
         PhysX does not support drives directly on SphericalJoint. Newton
         spherical joints use a balanced, mass-scaled force pair applied at a
         long lever arm. D6/other joints use the existing linear nudge where
         the runtime supports it.
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
from simready_benchmark_engine_kit.fabric_utils import live_world_matrix
from simready_benchmark_engine_kit.force_display import (
    clear_visuals,
    compute_arrow_length,
    draw_force_arrow,
    get_prim_world_position,
)
from simready_benchmark_engine_kit.physics_utils import (
    active_physics_engine,
    find_root_body,
)
from simready_benchmark_kit_suite.engine_guard import (
    NEWTON_SCENE_SKIP,
    articulationize_loose_joints,
    asset_has_articulation,
    newton_scene_initialized,
)
from simready_benchmark_kit_suite.fet004_multibody.joint_checks import run_pre_checks
from simready_benchmark_kit_suite.fet004_multibody.joint_discovery import (
    discover_joints,
    sanitize_metric_name,
)
from simready_benchmark_kit_suite.fet004_multibody.newton_drive import (
    activate_newton_position_drives,
    restore_newton_position_drives,
)

ANGULAR_AXES = ("angular", "rotX", "rotY", "rotZ")
LINEAR_AXES = ("linear", "transX", "transY", "transZ")

# Frames to step the freshly-played simulation BEFORE applying any joint drive.
# Applying a high-force drive on the very first step after play() -- before the
# PhysX solver has initialized contacts, articulation state, and cooked
# colliders -- can destabilize the constraint solve. Gravity is 0 during the
# test, so these warm-up steps leave the asset at rest; they only give the
# engine time to reach a stable initial state before it is driven.
DRIVE_WARMUP_FRAMES = 8

# A drivable joint (revolute/prismatic) with no finite authored limit would be
# driven open-endedly and run its part away to infinity, destabilizing the
# solver and eventually crashing. Before driving, such a joint gets a temporary
# bounded limit so the drive stops instead of running away: +/- this many
# degrees for a revolute DOF, or this fraction of the child part's bounding-box
# diagonal for a prismatic DOF. The bound only needs to exceed the movement-
# detection threshold; it is not meant to reflect the joint's real range.
ANGULAR_DRIVE_BOUND_DEG = 30.0
LINEAR_DRIVE_BOUND_FRACTION = 0.25

# Honest skip when the Newton position-target drive cannot be created for an
# asset -- no articulation view, or the Newton backend cannot gear an
# articulation drive (driven-joint control unavailable, the same limitation the
# FET022 driven-joint tests skip on). PhysX never reaches this: it drives the
# joints through the USD DriveAPI path, which Newton does not actuate.
NEWTON_DRIVE_SKIP = (
    "Newton could not drive this asset's joints: no articulation view was "
    "available, or Newton's backend does not provide driven-joint (articulation "
    "drive) control for it. USD DriveAPI velocity targets are inert under Newton, "
    "so joint movement is validated on PhysX; this is an engine-capability gap, "
    "not a runtime failure or an asset defect."
)


def _joint_dof_locked(stage, prim_path):
    # type: (object, str) -> object
    """Return (lower, upper) when a joint's DOF is intentionally LOCKED
    (lowerLimit >= upperLimit, both finite), else None.

    Authoring a revolute/prismatic limit with the lower limit at or above the
    upper limit is a convention to pin the degree of freedom -- the joint is
    not meant to move. Such a joint must NOT be driven: PhysX treats the
    inverted twist limit as invalid ("PxD6Joint::setTwistLimit: limit invalid")
    and driving it can take the process down. Read failures return None (never
    exclude a joint we cannot classify).
    """
    try:
        import math

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            return None
        lo_a = prim.GetAttribute("physics:lowerLimit")
        hi_a = prim.GetAttribute("physics:upperLimit")
        lo = lo_a.Get() if lo_a and lo_a.IsDefined() else None
        hi = hi_a.Get() if hi_a and hi_a.IsDefined() else None
        if lo is None or hi is None:
            return None
        lo = float(lo)
        hi = float(hi)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            return None
        return (lo, hi) if lo >= hi else None
    except Exception:
        return None


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


def _spherical_drive_axes(joint):
    # type: (dict) -> tuple
    """Return the two rot DOFs perpendicular to a spherical joint's axis."""
    primary = str(joint.get("axis") or "Z").upper()
    return tuple("rot%s" % axis for axis in ("X", "Y", "Z") if axis != primary)


def _next_temp_driver_path(stage):
    # type: (object) -> str
    """Return an unused test-owned prim path without overwriting stage data."""
    base = "/World/__SimReadyBenchmark_FET004_Driver"
    candidate = base
    index = 1
    while stage.GetPrimAtPath(candidate).IsValid():
        candidate = "%s_%d" % (base, index)
        index += 1
    return candidate


def _copy_joint_frame(source, destination):
    # type: (object, object) -> None
    """Copy body relationships and local frames between USD joints."""
    relationship_pairs = (
        (source.GetBody0Rel(), destination.CreateBody0Rel()),
        (source.GetBody1Rel(), destination.CreateBody1Rel()),
    )
    for source_rel, destination_rel in relationship_pairs:
        destination_rel.SetTargets(source_rel.GetTargets())

    attribute_pairs = (
        (source.GetLocalPos0Attr(), destination.CreateLocalPos0Attr()),
        (source.GetLocalRot0Attr(), destination.CreateLocalRot0Attr()),
        (source.GetLocalPos1Attr(), destination.CreateLocalPos1Attr()),
        (source.GetLocalRot1Attr(), destination.CreateLocalRot1Attr()),
    )
    for source_attr, destination_attr in attribute_pairs:
        value = source_attr.Get()
        if value is not None:
            destination_attr.Set(value)


def _create_external_spherical_driver(stage, joint, drive_axis, velocity, damping, max_force):
    # type: (object, dict, str, float, float, float) -> object
    """Create the PhysX-supported external D6 driver for a spherical joint.

    PhysX's USD integration explicitly does not support DriveAPI directly on a
    SphericalJoint. Its own spherical-joint tests exercise articulations with a
    generic Joint excluded from the articulation, sharing the spherical joint's
    bodies/frame, with all but the selected swing axis locked. The returned prim
    path is test-owned and must be removed after the stopped simulation.
    """
    from pxr import UsdPhysics

    source_prim = stage.GetPrimAtPath(joint["prim_path"])
    if not source_prim or not source_prim.IsValid():
        return None
    source = UsdPhysics.Joint(source_prim)
    if not source:
        return None

    driver_path = _next_temp_driver_path(stage)
    driver = UsdPhysics.Joint.Define(stage, driver_path)
    _copy_joint_frame(source, driver)
    driver.CreateExcludeFromArticulationAttr(True)

    for axis in ("transX", "transY", "transZ", "rotX", "rotY", "rotZ"):
        if axis == drive_axis:
            continue
        limit = UsdPhysics.LimitAPI.Apply(driver.GetPrim(), axis)
        limit.CreateLowAttr(1.0)
        limit.CreateHighAttr(-1.0)

    drive = UsdPhysics.DriveAPI.Apply(driver.GetPrim(), drive_axis)
    drive.CreateTypeAttr("force")
    drive.CreateStiffnessAttr(0.0)
    drive.CreateDampingAttr(float(damping))
    drive.CreateTargetVelocityAttr(float(velocity))
    drive.CreateMaxForceAttr(float(max_force))
    return driver_path


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
    """Get the current world transform matrix for a prim, engine-aware.

    A non-PhysX engine (Newton) writes simulation pose to Fabric, not to the USD
    stage, so a USD ``ComputeLocalToWorldTransform`` read would return the static
    authored pose and miss ALL joint motion (every joint reads as "did not
    move"). Under such an engine, read the live world matrix from Fabric instead;
    fall back to the USD read when Fabric has no data. PhysX writes pose back to
    USD, so it takes the USD path unchanged.
    """
    try:
        from pxr import Gf, Usd, UsdGeom

        prim = stage.GetPrimAtPath(prim_path)
        if not (prim and prim.IsValid()):
            return None
        if active_physics_engine() != "physx":
            rows = live_world_matrix(stage, prim_path)
            if rows is not None:
                mat = Gf.Matrix4d(1.0)
                for i in range(4):
                    mat.SetRow(i, Gf.Vec4d(*rows[i]))
                return mat
        xf = UsdGeom.Xformable(prim)
        return xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    except Exception:
        pass
    return None


def _get_bbox_diagonal(stage, prim_path):
    # type: (object, str) -> float
    """Compute the bounding box diagonal of a prim, in STAGE units.

    ``ComputeWorldBound`` returns the bound in the stage's own linear units (not
    metres), so the result is directly comparable to authored joint limits and
    translations, which are also in stage units.
    """
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
    if capture and show_arrows:
        _draw_arrows(stage, joints, arrow_len, drive_axis=axis)
    physics.play()
    # Warm up the freshly-played sim before applying the drive (see
    # DRIVE_WARMUP_FRAMES). Gravity is 0, so the asset stays at rest.
    await ctx.settle(count=DRIVE_WARMUP_FRAMES)
    activated = {}  # type: dict
    for j in joints:
        sv = _activate_drive_axis(stage, j["prim_path"], axis, vel)
        activated[j["prim_path"]] = sv

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
    """Run one linear-velocity-nudge simulation on a single joint.

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
    # Warm up before the first velocity nudge (see DRIVE_WARMUP_FRAMES).
    await ctx.settle(count=DRIVE_WARMUP_FRAMES)

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


async def _run_spherical_drive_sim(
    ctx,
    stage,
    joint,
    saved,
    physics,
    drive_axis,
    velocity,
    damping,
    max_force,
    total_frames,
    capture_interval,
    capture,
    show_arrows,
    arrow_len,
    joint_count,
):
    # type: (object, object, dict, dict, object, str, float, float, float, int, int, bool, bool, float, int) -> tuple
    """Exercise one spherical swing axis with a temporary external D6 drive."""
    physics.stop()
    _reset_transforms(stage, saved)
    if capture and show_arrows:
        _clear_arrows(stage, joint_count)
        _draw_arrows(stage, [joint], arrow_len, drive_axis=drive_axis)

    driver_path = _create_external_spherical_driver(
        stage,
        joint,
        drive_axis,
        velocity,
        damping,
        max_force,
    )
    if driver_path is None:
        return None, []

    tracker = None
    captured = []  # type: list
    try:
        # The external joint must exist before play so PhysX parses it into the
        # scene. It is excluded from the articulation and drives the same bodies
        # in the same local joint frame as the authored spherical constraint.
        physics.play()
        await ctx.settle(count=DRIVE_WARMUP_FRAMES)
        tracker = JointTracker(stage, joint)
        for frame in range(total_frames):
            await ctx.physics_step()
            tracker.update()
            ctx.scene.update_camera_follow()
            if capture and frame % capture_interval == 0:
                captured.append(await ctx.capture_frame(label="joint_movement"))
            await ctx.physics_advance()
    finally:
        physics.stop()
        prim = stage.GetPrimAtPath(driver_path)
        if prim and prim.IsValid():
            stage.RemovePrim(driver_path)
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
    joints. PhysX spherical joints use a temporary external D6 driver because
    drives directly on SphericalJoint are unsupported; other unconstrained
    types retain the linear-velocity fallback.
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


def _bound_unlimited_drivable_joints(ctx, stage, joints):
    # type: (object, object, list) -> None
    """Impose a temporary bounded limit on every drivable joint that lacks a
    finite authored limit, so the drive stops at the bound instead of running the
    part away to infinity (which destabilizes the solver and can crash).

    Revolute DOFs get +/-ANGULAR_DRIVE_BOUND_DEG degrees; prismatic DOFs a
    fraction of the child part's bounding-box diagonal. Both the diagonal and the
    authored prismatic limit are in stage units, so no unit conversion is applied
    (a prior ``/ metersPerUnit`` over-inflated the bound by 1/mpu on non-metre
    stages -- e.g. 100x on a centimetre stage -- leaving the joint effectively
    unbounded). Naturally limited joints keep their authored limits untouched.
    """
    from pxr import UsdPhysics

    bounded = []
    for j in joints:
        dof = _drive_dof_for_joint(j)
        if dof is None:
            continue
        if _open_direction(stage, j)[0] is not None:
            continue  # already has a usable finite limit
        prim = stage.GetPrimAtPath(j["prim_path"])
        if not prim or not prim.IsValid():
            continue
        if dof == "angular":
            bound = ANGULAR_DRIVE_BOUND_DEG
            joint = UsdPhysics.RevoluteJoint(prim)
        else:
            diag = _get_bbox_diagonal(stage, j["child_body_path"])  # stage units
            bound = max(1e-3, LINEAR_DRIVE_BOUND_FRACTION * diag)
            joint = UsdPhysics.PrismaticJoint(prim)
        joint.CreateLowerLimitAttr(-float(bound))
        joint.CreateUpperLimitAttr(float(bound))
        bounded.append(j.get("name") or j["prim_path"])
    if bounded:
        ctx.step(
            "Bounded %d unlimited drivable joint(s) so the drive stops instead of running away: %s"
            % (len(bounded), ", ".join(bounded))
        )


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

    # Reference (pre-play) part centers, so the capture pass can draw arrows
    # along each part's REAL motion (see _draw_motion_arrows). Anchored on the
    # bbox center -- the visual middle of the door/drawer, not the hinge.
    ref_centers = {}  # type: dict
    arrow_eps = max(1e-4, arrow_len * 0.02)
    if capture and show_arrows:
        for j in drive_joints:
            ref_centers[j["name"]] = _world_bbox_center(stage, j["child_body_path"])
    physics.play()
    # Warm up the freshly-played sim before applying the drives (see
    # DRIVE_WARMUP_FRAMES). Gravity is 0, so the asset stays at rest.
    await ctx.settle(count=DRIVE_WARMUP_FRAMES)

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
# Newton tensor drive
#
# Newton (MuJoCo-Warp) is a reduced-coordinate engine: it does NOT actuate the
# USD DriveAPI velocity targets the batched-drive path above sets, so every
# joint reads as "did not move" (0/N). Under Newton the joints are instead
# driven through the physics tensor view (isaacsim.core.prims.SingleArticulation)
# with POSITION targets ramped toward each joint's open limit -- the same
# mechanism proven to drive the FET005 gripper on Newton. Motion detection is
# unchanged: JointTracker reads live Fabric pose under Newton, so only the drive
# differs. If Newton's backend cannot provide an articulation drive for the asset
# (drive types unavailable / no articulation view), the drive reports it could
# not run and the test skips honestly rather than reporting a false 0/N fail.
# ---------------------------------------------------------------------------


def _articulation_roots(stage):
    # type: (object) -> list
    """Return the prim paths carrying UsdPhysics.ArticulationRootAPI.

    One for a native robot (ur10); one per base link for a prop whose loose
    joints were wrapped by ``articulationize_loose_joints``.
    """
    roots = []
    try:
        for prim in stage.Traverse():
            schemas = prim.GetMetadata("apiSchemas")
            names = list(getattr(schemas, "GetAppliedItems", lambda: [])()) if schemas else []
            if any("ArticulationRootAPI" in n for n in names):
                roots.append(str(prim.GetPath()))
    except Exception:
        pass
    return roots


def _newton_dof_names_for_joint(j):
    # type: (dict) -> list
    """Candidate articulation DOF names for a joint dict (its name, then its prim
    basename -- Isaac names each DOF after its joint prim)."""
    cands = []
    n = j.get("name")
    if n:
        cands.append(str(n))
    pp = j.get("prim_path")
    if pp:
        base = str(pp).rsplit("/", 1)[-1]
        if base not in cands:
            cands.append(base)
    return cands


def _read_dof_positions(art, dof_count):
    # type: (object, int) -> list
    """Read an articulation's joint positions as plain floats.

    Under Newton the tensor backend is torch/CUDA, so ``get_joint_positions``
    can return a CUDA tensor that ``np.array`` refuses to convert; index it
    element-wise and ``float()`` each entry instead (the pattern FET005 uses).
    """
    raw = art.get_joint_positions()
    out = [0.0] * dof_count
    for i in range(dof_count):
        try:
            out[i] = float(raw[i])
        except Exception:
            out[i] = 0.0
    return out


def _joint_world_anchor(stage, joint):
    # type: (object, dict) -> object
    """Return the authored joint anchor in world space, preferring body1.

    The body1 frame belongs to the moving link, so it remains meaningful for
    joints whose body0 relationship is empty (a joint to world).  This helper is
    evaluated while physics is stopped, before the force probe starts.
    """
    try:
        from pxr import Gf, UsdPhysics

        prim = stage.GetPrimAtPath(joint["prim_path"])
        api = UsdPhysics.Joint(prim)
        local = api.GetLocalPos1Attr().Get()
        body_path = joint.get("child_body_path")
        if local is None or not body_path:
            return None
        matrix = _get_world_matrix(stage, body_path)
        point = matrix.Transform(Gf.Vec3d(float(local[0]), float(local[1]), float(local[2])))
        return (float(point[0]), float(point[1]), float(point[2]))
    except Exception:
        return None


def _lever_application_point(stage, joint):
    # type: (object, dict) -> object
    """Choose a bbox face-center farthest from the joint pivot.

    A face center is preferable to a bbox corner: it still provides a long
    lever arm but avoids applying the diagnostic force at an extreme point far
    outside irregular geometry.  Returns ``(point, lever)`` in world space.
    """
    try:
        from pxr import Usd, UsdGeom

        anchor = _joint_world_anchor(stage, joint)
        prim = stage.GetPrimAtPath(joint["child_body_path"])
        if anchor is None or not prim or not prim.IsValid():
            return None
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
        rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        if rng.IsEmpty():
            return None
        mn = rng.GetMin()
        mx = rng.GetMax()
        center = tuple((float(mn[i]) + float(mx[i])) * 0.5 for i in range(3))
        candidates = []
        for axis in range(3):
            for bound in (float(mn[axis]), float(mx[axis])):
                point = list(center)
                point[axis] = bound
                candidates.append(tuple(point))
        point = max(candidates, key=lambda p: sum((p[i] - anchor[i]) ** 2 for i in range(3)))
        lever = tuple(point[i] - anchor[i] for i in range(3))
        if sum(v * v for v in lever) <= 1.0e-12:
            return None
        return point, lever
    except Exception:
        return None


def _perpendicular_force_directions(lever):
    # type: (tuple) -> list
    """Return world cardinal directions ordered by produced torque."""
    import numpy as np

    r = np.asarray(lever, dtype=np.float64)
    axes = [
        np.asarray((1.0, 0.0, 0.0), dtype=np.float64),
        np.asarray((0.0, 1.0, 0.0), dtype=np.float64),
        np.asarray((0.0, 0.0, 1.0), dtype=np.float64),
    ]
    axes.sort(key=lambda axis: float(np.linalg.norm(np.cross(r, axis))), reverse=True)
    return [tuple(float(value) for value in axis) for axis in axes if np.linalg.norm(np.cross(r, axis)) > 1.0e-9]


def _newton_link_force_view(asset_path, child_body_path, parent_body_path=None):
    # type: (str, str, object) -> tuple
    """Create a Newton articulation force view for a joint's two links."""
    try:
        from isaacsim.core.prims import SingleArticulation  # type: ignore
    except Exception:
        try:
            from isaacsim.core.prims.single_articulation import SingleArticulation  # type: ignore
        except Exception:
            return None, "SingleArticulation is unavailable in this Isaac Sim build"

    try:
        art = SingleArticulation(prim_path=asset_path, name="jm_newton_force_view")
        art.initialize()
        view = getattr(art, "_articulation_view", None) or art
        physics_view = getattr(view, "_physics_view", None)
        body_names = list(getattr(view, "body_names", None) or [])
        if physics_view is None or not body_names:
            return None, "the Newton articulation exposes no link-force tensor view"
        leaf_name = str(child_body_path).rsplit("/", 1)[-1]
        matches = [index for index, name in enumerate(body_names) if str(name) == leaf_name]
        if len(matches) != 1:
            return None, "child link '%s' resolved to %d Newton bodies" % (leaf_name, len(matches))
        parent_index = None
        if parent_body_path:
            parent_name = str(parent_body_path).rsplit("/", 1)[-1]
            parent_matches = [index for index, name in enumerate(body_names) if str(name) == parent_name]
            if len(parent_matches) != 1:
                return None, "parent link '%s' resolved to %d Newton bodies" % (
                    parent_name,
                    len(parent_matches),
                )
            parent_index = parent_matches[0]
        return {
            "art": art,
            "physics_view": physics_view,
            "body_count": len(body_names),
            "body_index": matches[0],
            "parent_index": parent_index,
        }, None
    except Exception as exc:
        return None, "Newton link-force view initialization failed: %s" % exc


def _newton_link_world_position(force_view):
    # type: (dict) -> object
    """Read one live Newton link origin as a host-side world vector."""
    import numpy as np

    rows = force_view["physics_view"].get_link_transforms()
    if hasattr(rows, "detach"):
        rows = rows.detach()
    if hasattr(rows, "cpu"):
        rows = rows.cpu()
    rows = np.asarray(rows)
    if rows.ndim == 3:
        rows = rows[0]
    index = force_view["body_index"]
    if index >= len(rows) or rows.shape[-1] < 3:
        return None
    point = np.asarray(rows[index, :3], dtype=np.float64)
    return point if np.all(np.isfinite(point)) else None


def _newton_link_mass(force_view):
    # type: (dict) -> object
    """Read the effective mass Newton is simulating for the selected link."""
    import numpy as np

    masses = force_view["physics_view"].get_masses()
    if hasattr(masses, "detach"):
        masses = masses.detach()
    if hasattr(masses, "cpu"):
        masses = masses.cpu()
    masses = np.asarray(masses)
    if masses.ndim == 2:
        masses = masses[0]
    index = force_view["body_index"]
    if index >= len(masses):
        return None
    mass = float(masses[index])
    return mass if np.isfinite(mass) and mass > 0.0 else None


def _apply_newton_force_at_position(force_view, direction, magnitude, position):
    # type: (dict, tuple, float, object) -> None
    """Apply one transient world force to a Newton articulation link."""
    import numpy as np

    art = force_view["art"]
    count = force_view["body_count"]
    body_index = force_view["body_index"]
    forces = np.zeros((1, count, 3), dtype=np.float32)
    positions = np.zeros((1, count, 3), dtype=np.float32)
    forces[0, body_index, :] = np.asarray(direction, dtype=np.float32) * float(magnitude)
    positions[0, body_index, :] = np.asarray(position, dtype=np.float32)
    parent_index = force_view.get("parent_index")
    if parent_index is not None:
        # Apply an equal opposite load to the parent at the same world point.
        # This is an internal force pair: it exercises the joint while adding
        # neither net force nor net torque to a floating articulation.
        forces[0, parent_index, :] = -forces[0, body_index, :]
        positions[0, parent_index, :] = positions[0, body_index, :]
    indices = np.asarray([0], dtype=np.int32)
    backend_utils = getattr(art, "_backend_utils", None)
    device = getattr(art, "_device", None)
    if backend_utils is not None:
        forces = backend_utils.convert(forces, device=device, dtype="float32")
        positions = backend_utils.convert(positions, device=device, dtype="float32")
        indices = backend_utils.convert(indices, device=device, dtype="int32")
    force_view["physics_view"].apply_forces_and_torques_at_position(
        forces, None, positions, indices, is_global=True
    )


async def _run_newton_spherical_force_sim(
    ctx,
    stage,
    asset_path,
    joint,
    saved,
    physics,
    direction,
    acceleration_start,
    acceleration_max,
    total_frames,
    capture_interval,
    capture,
    show_arrows,
    arrow_len,
    joint_count,
):
    # type: (object, object, str, dict, dict, object, tuple, float, float, int, int, bool, bool, float, int) -> tuple
    """Exercise a Newton spherical joint with a force at a long lever arm."""
    import numpy as np

    physics.stop()
    _reset_transforms(stage, saved)
    geometry = _lever_application_point(stage, joint)
    if geometry is None:
        return None, [], "could not derive a force point and joint lever arm"
    initial_point, lever = geometry

    if capture and show_arrows:
        _clear_arrows(stage, joint_count)
        shaft = arrow_len * 0.8
        draw_force_arrow(
            stage,
            initial_point,
            direction,
            shaft_length=shaft,
            shaft_radius=shaft * 0.04,
            head_length=shaft * 0.25,
            head_radius=shaft * 0.12,
            prim_path="/World/JM_Arrow_0",
        )

    physics.play()
    await ctx.settle(count=DRIVE_WARMUP_FRAMES)
    force_view, error = _newton_link_force_view(
        asset_path,
        joint["child_body_path"],
        joint.get("parent_body_path"),
    )
    if force_view is None:
        physics.stop()
        return None, [], error

    body_mass = _newton_link_mass(force_view)
    if body_mass is None:
        physics.stop()
        return None, [], "Newton returned no finite positive mass for the child link"
    force_start = body_mass * float(acceleration_start)
    force_max = body_mass * float(acceleration_max)
    ctx.step(
        "Newton spherical joint %s: %.6g-%.6g N force ramp for %.6g kg simulated link"
        % (joint["name"], force_start, force_max, body_mass)
    )

    initial_origin = _newton_link_world_position(force_view)
    if initial_origin is None:
        physics.stop()
        return None, [], "Newton returned no finite transform for the child link"
    point_offset = np.asarray(initial_point, dtype=np.float64) - initial_origin
    tracker = JointTracker(stage, joint)
    captured = []  # type: list
    denom = max(1, total_frames - 1)
    for frame in range(total_frames):
        origin = _newton_link_world_position(force_view)
        if origin is None:
            physics.stop()
            return None, captured, "Newton child-link transform became unavailable"
        application_point = origin + point_offset
        magnitude = float(force_start) + (float(force_max) - float(force_start)) * float(frame) / denom
        _apply_newton_force_at_position(force_view, direction, magnitude, application_point)
        await ctx.physics_step()
        tracker.update()
        ctx.scene.update_camera_follow()
        if capture and frame % capture_interval == 0:
            captured.append(await ctx.capture_frame(label="joint_movement"))
        await ctx.physics_advance()
    physics.stop()
    return tracker, captured, None


def _build_newton_articulations(ctx, stage, asset_path, drive_joints):
    # type: (object, object, str, list) -> object
    """Initialize an asset-root articulation view and map USD joints to DOFs.

    Returns ``(state, reason)``. ``state`` is a dict with keys ``arts`` (list
    of views), ``targets`` (per-view float lists, initialized to the start
    pose), and ``joints`` (list of per-joint drive records). It is ``None``
    when no drivable articulation view could be created; ``reason`` then
    identifies the failed integration stage. MUST be called after
    ``physics.play()`` so the tensor sim view is live.
    """
    roots = _articulation_roots(stage)
    if not roots:
        return None, "the stage exposes no articulation root"
    try:
        from isaacsim.core.prims import SingleArticulation  # type: ignore
    except Exception:
        try:
            from isaacsim.core.prims.single_articulation import (  # type: ignore
                SingleArticulation,
            )
        except Exception:
            return None, "SingleArticulation is unavailable in this Isaac Sim build"

    # SingleArticulation expects the enclosing asset/robot prim, not
    # necessarily the rigid-body prim carrying ArticulationRootAPI. Many
    # SimReady props author (or receive a temporary) articulation root on a
    # link below ``asset_path``. Passing that link directly creates a valid
    # object but exposes no DOFs under Newton. This is the same enclosing-root
    # pattern used by FET005's generated gripper and the articulation suite's
    # RobotHandle.
    view_paths = [asset_path]

    arts = []  # type: list
    targets = []  # type: list  # per-art float list (live drive targets)
    dof_map = {}  # dof name -> (art_index, local_index)
    init_errors = []  # type: list
    for root in view_paths:
        try:
            art = SingleArticulation(prim_path=root, name="jm_newton_view_%d" % len(arts))
            art.initialize()
        except Exception as exc:
            ctx.step("Newton drive: articulation view '%s' init failed (%s)" % (root, exc))
            init_errors.append("%s: %s" % (root, exc))
            continue
        names = list(getattr(art, "dof_names", None) or [])
        if not names:
            ctx.step(
                "Newton drive: articulation view '%s' exposed no DOFs "
                "(authored articulation roots: %s)" % (root, ", ".join(roots))
            )
            init_errors.append("%s: no DOFs" % root)
            continue
        ai = len(arts)
        arts.append(art)
        targets.append(_read_dof_positions(art, len(names)))
        for li, n in enumerate(names):
            dof_map[str(n)] = (ai, li)
    if not arts:
        return None, "articulation view initialization failed (%s)" % "; ".join(init_errors)

    # Resolve each driven USD joint to its runtime articulation DOF.
    joint_records = []  # type: list
    for j in drive_joints:
        res = None
        for name in _newton_dof_names_for_joint(j):
            if name in dof_map:
                res = dof_map[name]
                break
        if res is None:
            continue
        ai, li = res
        dof = _drive_dof_for_joint(j)
        joint_records.append({"joint": j, "art": ai, "dof_index": li, "dof": dof, "start": targets[ai][li]})

    if not joint_records:
        joint_names = sorted({name for joint in drive_joints for name in _newton_dof_names_for_joint(joint)})
        runtime_names = sorted(dof_map)
        reason = "no USD joint mapped to a Newton DOF (USD: %s; Newton: %s)" % (
            ", ".join(joint_names) or "<none>",
            ", ".join(runtime_names) or "<none>",
        )
        ctx.step("Newton drive: %s" % reason)
        return None, reason

    return {"arts": arts, "targets": targets, "joints": joint_records}, None


async def _run_newton_drive_sim(
    ctx,
    stage,
    asset_path,
    drive_joints,
    saved,
    physics,
    cfg,
    total_frames,
    capture_interval,
    show_arrows,
    arrow_len,
):
    # type: (object, object, str, list, dict, object, dict, int, int, bool, float) -> tuple
    """Drive every joint toward its open limit via position targets on the Newton
    tensor view, capturing a summary video. Returns ``(trackers, captured, ok)``;
    ``ok`` is False when no articulation drive could be created (caller skips).
    The fourth return value is the specific integration failure reason.
    """
    import math
    import time

    import numpy as np
    from isaacsim.core.utils.types import ArticulationAction  # type: ignore
    from pxr import UsdGeom

    physics.stop()
    _reset_transforms(stage, saved)
    activated_drives = activate_newton_position_drives(stage, drive_joints, cfg)

    ref_centers = {}  # type: dict
    arrow_eps = max(1e-4, arrow_len * 0.02)
    if show_arrows:
        for j in drive_joints:
            ref_centers[j["name"]] = _world_bbox_center(stage, j["child_body_path"])

    physics.play()
    # Warm up the freshly-played sim before building the view / driving (see
    # DRIVE_WARMUP_FRAMES). Gravity is 0, so the asset stays at rest.
    await ctx.settle(count=DRIVE_WARMUP_FRAMES)

    built, build_error = _build_newton_articulations(ctx, stage, asset_path, drive_joints)
    if built is None:
        physics.stop()
        restore_newton_position_drives(stage, activated_drives)
        return {}, [], False, build_error

    arts = built["arts"]
    targets = built["targets"]
    records = built["joints"]

    mpu = UsdGeom.GetStageMetersPerUnit(stage) or 1.0
    # Absolute open target per driven DOF, in the DOF's own units (radians for a
    # revolute DOF, metres for a prismatic one). All batchable joints carry an
    # _open_sign / _open_travel here (undirected joints were bounded upstream).
    for rec in records:
        j = rec["joint"]
        sgn = j.get("_open_sign") or 1.0
        travel = j.get("_open_travel")
        if travel is None:
            # Batchable joints are bounded upstream so this is defensive, but keep
            # it correct: a fixed angular span (degrees), or a bbox-fraction linear
            # span in STAGE units -- NOT the bare fraction, which is a sub-mm move.
            if rec["dof"] == "angular":
                travel = ANGULAR_DRIVE_BOUND_DEG
            else:
                travel = LINEAR_DRIVE_BOUND_FRACTION * _get_bbox_diagonal(stage, j["child_body_path"])
        if rec["dof"] == "angular":
            delta = math.radians(float(travel)) * float(sgn)
        else:
            delta = float(travel) * float(mpu) * float(sgn)
        rec["open_target"] = rec["start"] + delta

    trackers = {j["name"]: JointTracker(stage, j) for j in drive_joints}
    captured = []  # type: list
    deadline = time.monotonic() + 120.0
    for frame in range(total_frames):
        # Ramp each driven DOF's target from its start toward the open target so
        # the drive is a gradual input (a step input can ring / destabilize).
        frac = float(frame + 1) / float(total_frames)
        for rec in records:
            base = rec["start"]
            targets[rec["art"]][rec["dof_index"]] = base + frac * (rec["open_target"] - base)
        for ai, art in enumerate(arts):
            art.apply_action(ArticulationAction(joint_positions=np.array(targets[ai], dtype=np.float64)))
        await ctx.physics_step()
        for tracker in trackers.values():
            tracker.update()
        ctx.scene.update_camera_follow()
        if frame % capture_interval == 0:
            if show_arrows:
                _draw_motion_arrows(stage, drive_joints, arrow_len, ref_centers, arrow_eps)
            captured.append(await ctx.capture_frame(label="joint_movement"))
        if time.monotonic() > deadline:
            ctx.step("Newton drive sim hit 120s watchdog at frame %d" % frame)
            break
        await ctx.physics_advance()

    physics.stop()
    restore_newton_position_drives(stage, activated_drives)
    return trackers, captured, True, None


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


@test(
    features=[
        {"id": "FET_004_STANDARD", "version": ">=0.1.0"},
        {"id": "FET_004_PHYSX", "version": ">=0.1.0"},
        {"id": "FET_004_NEWTON", "version": ">=0.1.0"},
        {"id": "FET_004_ROBOT_PHYSX", "version": ">=0.1.0"},
        {"id": "FET_004_ROBOT_NEWTON", "version": ">=0.1.0"},
    ],
    name="joint_movement",
    description=(
        "For each authored joint on the asset, applies a type-aware excitation "
        "(including a temporary external D6 driver for PhysX spherical joints, "
        "a balanced force-at-lever-arm probe for Newton spherical joints, and "
        "a linear-velocity nudge for other supported non-scalar joints) "
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
    version="2.2.0",
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
        # PhysX does not support DriveAPI directly on SphericalJoint. The test
        # temporarily overlays the external D6 driver pattern used by PhysX's
        # own spherical articulation tests and drives one permitted swing axis.
        "spherical_drive_velocity_deg_s": 45.0,
        "spherical_drive_damping": 1000.0,
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
        # Newton (MuJoCo-Warp) does not actuate USD DriveAPI velocity targets,
        # so under Newton each joint is driven with a POSITION target through the
        # physics tensor view instead (see _run_newton_drive_sim). The sample
        # assets author no drive gains on these joints -- exactly as on the PhysX
        # path, which applies a uniform damping ramp + high max-force -- so a
        # uniform default stiffness/damping is pushed onto every driven DOF.
        # Revolute DOFs (radians) need a softer kp than prismatic DOFs (metres).
        # These only have to produce detectable motion (> the pass thresholds)
        # with gravity=0 and a fixed base, not track a trajectory; the target is
        # ramped gradually and the joint's own limit bounds the travel. Tune here
        # if a Newton run shows joints under- or over-driven.
        "newton_drive_stiffness_angular": 1.0e4,
        "newton_drive_stiffness_linear": 1.0e5,
        "newton_drive_damping": 5.0e2,
        # Spherical joints have multi-coordinate state and cannot use the
        # scalar position-target mapping above. Newton can still exercise the
        # real constraint with balanced forces on the child and parent at a
        # point far from the joint anchor. Ramp gently to avoid an impulse.
        "newton_spherical_acceleration_start_m_s2": 0.002,
        "newton_spherical_acceleration_max_m_s2": 0.05,
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
    # Loose (maximal-coordinate) joints crash the PhysX D6 solver when driven;
    # wrap them in a reduced-coordinate articulation so they drive stably. No-op
    # for already-articulated robots and for graphs that are not a clean tree.
    articulationize_loose_joints(ctx, stage)
    joints = discover_joints(stage, asset_path)
    if not joints:
        ctx.precheck_failure("No joints with child bodies found")
        return

    ctx.step("Found %d movable joints" % len(joints))

    # --- Exclude joints whose DOF is intentionally locked ---
    # A revolute/prismatic joint authored with lowerLimit >= upperLimit has a
    # LOCKED degree of freedom (a common convention to pin a DOF). It is not
    # meant to move, and driving it makes PhysX reject the twist limit and can
    # crash the process. Treat it like a fixed joint: do not drive it, exclude
    # it from the movable set, and note it (informational, not an error).
    # Movable joints on the same asset are still exercised.
    movable = []
    locked = []
    for j in joints:
        (locked if _joint_dof_locked(stage, j["prim_path"]) is not None else movable).append(j)
    if locked:
        ctx.step(
            "Excluding %d locked joint(s) (lowerLimit >= upperLimit, DOF pinned): %s"
            % (len(locked), ", ".join(j.get("name") or j["prim_path"] for j in locked))
        )
    if not movable:
        ctx.skip(
            "All %d joint(s) have a locked DOF (lowerLimit >= upperLimit); "
            "there is no movable joint for this test to exercise." % len(joints)
        )
        return
    joints = movable

    # Force-driving a LOOSE (maximal-coordinate) revolute/prismatic joint
    # intermittently blows up the PhysX D6 constraint solver and kills the
    # process. articulationize_loose_joints above wraps such joints in an
    # articulation, which drives them stably -- but only when the asset is a
    # clean, all-revolute/prismatic/fixed tree. If a force-drivable joint is
    # still loose here, the wrap could not apply (a joint to world, a shared
    # child, a loop, or a spherical/D6 joint in the graph), so skip honestly
    # rather than risk a crash a retry could mask as a pass.
    #
    # Spherical joints use the temporary external D6 driver; other unsupported
    # joint types use the linear-velocity nudge. Neither path force-drives the
    # authored loose joint, so an asset containing only these types proceeds.
    has_articulation = asset_has_articulation(stage)
    force_drivable = [j for j in joints if _drive_dof_for_joint(j) is not None]
    if not has_articulation and force_drivable:
        ctx.skip(
            "Asset has %d force-drivable joint(s) (revolute/prismatic) that could "
            "not be wrapped in an articulation (a joint to world, a shared child, "
            "a loop, or a spherical/D6 joint in the graph). Driving them loose "
            "intermittently blows up the PhysX D6 solver and crashes the engine, "
            "so joint_movement is skipped for this asset." % len(force_drivable)
        )
        return

    # Inject config thresholds into joint dicts for _measure_joint_movement
    rot_thresh = float(cfg["rotation_threshold_deg"])
    trans_thresh = float(cfg["translation_threshold_pct"])
    for j in joints:
        j["_rot_thresh_deg"] = rot_thresh
        j["_trans_thresh_pct"] = trans_thresh

    # --- Classify joints by drive DOF derived from joint type ---
    # Revolute -> "angular", Prismatic -> "linear" (PhysX applies the drive
    # about the joint's own authored axis). PhysX spherical joints are handled
    # by a temporary external D6 driver below because PhysX does not integrate
    # drives directly on SphericalJoint. D6/other joints retain the linear-body-
    # velocity fallback.
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

    # --- Newton scene-init guard (Newton only; PhysX untouched) ---
    # Newton parses the whole USD stage and aborts scene init on composition
    # errors (an unresolved reference, an unsupported schema) that PhysX
    # tolerates and simulates. timeline.play() still returns, but stepping the
    # un-built sim crashes the session, so verify the scene actually initialized
    # before driving and skip honestly if not. active_physics_engine() gates
    # this to Newton, so PhysX never plays here (no-op, unchanged behavior).
    if active_physics_engine() != "physx":
        physics.play()
        await ctx.settle(count=3)
        newton_ready = newton_scene_initialized()
        physics.stop()
        if not newton_ready:
            ctx.skip(NEWTON_SCENE_SKIP)
            return

    # --- Anchor the base body/bodies (make them kinematic) ---
    # A kinematic base is immovable: it absorbs the reaction force from
    # driving the joints (a world FixedJoint flexed and let the whole asset
    # slide across the floor). Only joint DOFs can then produce motion, so
    # any detected movement is real. Restored in cleanup.
    #
    # This is only valid for loose (maximal-coordinate) props. PhysX forbids a
    # kinematic body inside an articulation ("Articulations with kinematic
    # bodies are not supported") and crashes the engine, so an articulated asset
    # is never pinned kinematic. A native robot (e.g. ur10) usually has an
    # authored fixed base, so its root is anchored. A prop wrapped by
    # articulationize_loose_joints, however, gets an ArticulationRootAPI but NO
    # fixed-base joint, so it is a FLOATING-base articulation: driving a joint
    # recoils the free base and the asset can drift (gravity is 0). That is
    # acceptable here because JointTracker measures parent->child RELATIVE motion,
    # which is unaffected by base drift; it only means the capture may wander.
    kin_saved = {}  # type: dict  body_path -> prior kinematicEnabled
    if has_articulation:
        anchor_bodies = []
        ctx.step("Articulated asset: no kinematic anchor (kinematic bodies are illegal inside an articulation)")
    else:
        anchor_bodies = _find_anchor_bodies(joints)
        if not anchor_bodies:
            # Fallback for odd rigs (e.g. a single body, or all joints attached
            # straight to world): best-effort base from the framework helper.
            rb = find_root_body(stage, asset_path)
            anchor_bodies = [rb] if rb else []
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
    winning_spherical = None  # (joint_dict, drive_axis, sign)
    winning_newton_force = None  # (joint_dict, direction)
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
    # Give any unlimited drivable joint a bounded limit first, so the drive stops
    # at the bound instead of running the part away (a runaway destabilizes the
    # solver and can crash). After this, those joints read as directed below.
    _bound_unlimited_drivable_joints(ctx, stage, batchable)
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

    # --- Newton drive (Newton only; PhysX takes the USD-drive passes below) ---
    # Newton does not actuate USD DriveAPI velocity targets, so drive every
    # force-drivable joint toward its open limit with a single position-target
    # pass on the tensor view (capture included). Spherical joints instead use
    # a real force applied at a long lever arm on their moving body: this creates
    # a torque without requiring an unsupported scalar spherical target.
    newton_engine = active_physics_engine() != "physx"
    if newton_engine and not batchable:
        spherical = [j for j in joints if j.get("type_name") == "PhysicsSphericalJoint"]
        if not spherical:
            physics.stop()
            for b, prev in kin_saved.items():
                _set_body_kinematic(stage, b, prev)
            _reset_transforms(stage, saved)
            _clear_arrows(stage, len(joints))
            joint_types = sorted({j.get("type_name") or "unknown" for j in joints})
            ctx.skip(
                "Newton cannot currently exercise this asset's movable joint types "
                "(%s): they have neither a scalar articulation target nor the "
                "spherical force-at-lever-arm path." % ", ".join(joint_types)
            )
            return

        force_error = None
        ctx.step("Newton: probing %d spherical joint(s) with an external force at a lever arm" % len(spherical))
        for joint in spherical:
            acceleration_start = float(cfg["newton_spherical_acceleration_start_m_s2"])
            acceleration_max = float(cfg["newton_spherical_acceleration_max_m_s2"])
            geometry = _lever_application_point(stage, joint)
            if geometry is None:
                force_error = "could not derive a force point for %s" % joint["name"]
                continue
            _point, lever = geometry
            for base_direction in _perpendicular_force_directions(lever):
                if winning_newton_force is not None:
                    break
                for sign in (1.0, -1.0):
                    direction = tuple(sign * value for value in base_direction)
                    label = "newton_force_(%.0f,%.0f,%.0f)" % direction
                    if label not in tried_drive_axes:
                        tried_drive_axes.append(label)
                    tracker, _frames, error = await _run_newton_spherical_force_sim(
                        ctx,
                        stage,
                        asset_path,
                        joint,
                        saved,
                        physics,
                        direction,
                        acceleration_start,
                        acceleration_max,
                        total_frames,
                        capture_interval,
                        capture=False,
                        show_arrows=False,
                        arrow_len=arrow_len,
                        joint_count=len(joints),
                    )
                    if error is not None:
                        force_error = error
                        break
                    _accumulate([joint], {joint["name"]: tracker}, acc)
                    if tracker.result()["moved"]:
                        winning_newton_force = (joint, direction)
                        break
                if force_error is not None:
                    break
            if force_error is not None:
                break

        if force_error is not None and winning_newton_force is None:
            physics.stop()
            for b, prev in kin_saved.items():
                _set_body_kinematic(stage, b, prev)
            _reset_transforms(stage, saved)
            _clear_arrows(stage, len(joints))
            ctx.skip("Newton spherical force probe unavailable: %s." % force_error)
            return

        if winning_newton_force is not None:
            joint, direction = winning_newton_force
            ctx.step("Newton: recording spherical joint %s under lever-arm force" % joint["name"])
            tracker, frames, error = await _run_newton_spherical_force_sim(
                ctx,
                stage,
                asset_path,
                joint,
                saved,
                physics,
                direction,
                acceleration_start,
                acceleration_max,
                total_frames,
                capture_interval,
                capture=True,
                show_arrows=show_arrows,
                arrow_len=arrow_len,
                joint_count=len(joints),
            )
            if error is not None:
                ctx.fail("Newton spherical force record pass failed: %s" % error)
                return
            _accumulate([joint], {joint["name"]: tracker}, acc)
            frames_captured.extend(frames)
    if newton_engine and batchable:
        ctx.step("Newton: driving %d joint(s) via position targets on the tensor view" % len(batchable))
        trackers_n, frames_n, ok, drive_error = await _run_newton_drive_sim(
            ctx,
            stage,
            asset_path,
            batchable,
            saved,
            physics,
            cfg,
            total_frames,
            capture_interval,
            show_arrows,
            arrow_len,
        )
        if not ok:
            physics.stop()
            for b, prev in kin_saved.items():
                _set_body_kinematic(stage, b, prev)
            _reset_transforms(stage, saved)
            _clear_arrows(stage, len(joints))
            ctx.skip("%s Reason: %s." % (NEWTON_DRIVE_SKIP, drive_error or "unknown"))
            return
        _accumulate(batchable, trackers_n, acc)
        frames_captured.extend(frames_n)

    # --- Pass 1a (search, no capture): drive each DIRECTED joint toward its
    #     own open limit, all simultaneously. ---
    if directed and not newton_engine:
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
    if undirected and not newton_engine:
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
    if record_joints and not newton_engine:
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

    # --- PhysX spherical fallback. ---
    # PhysX explicitly does not support DriveAPI directly on SphericalJoint,
    # and an articulation projects direct child angular-velocity writes away.
    # Follow PhysX's own spherical articulation test pattern: overlay a generic
    # D6 joint outside the articulation, copy the authored bodies/local frames,
    # lock every DOF except one permitted swing axis, and drive that axis. The
    # temporary prim exists only while physics is stopped/played for this probe
    # and is removed after every attempt.
    spherical = [j for j in joints if j.get("type_name") == "PhysicsSphericalJoint"]
    if not newton_engine and spherical and not any(a.get("moved") for a in acc.values()):
        spherical_velocity = float(cfg["spherical_drive_velocity_deg_s"])
        spherical_damping = float(cfg["spherical_drive_damping"])
        ctx.step("PhysX: probing %d spherical joint(s) through temporary external D6 drives" % len(spherical))
        for joint in spherical:
            if winning_spherical is not None:
                break
            for drive_axis in _spherical_drive_axes(joint):
                if drive_axis not in tried_drive_axes:
                    tried_drive_axes.append(drive_axis)
                for sign in (1.0, -1.0):
                    tracker, _ = await _run_spherical_drive_sim(
                        ctx,
                        stage,
                        joint,
                        saved,
                        physics,
                        drive_axis,
                        sign * spherical_velocity,
                        spherical_damping,
                        max_force,
                        total_frames,
                        capture_interval,
                        capture=False,
                        show_arrows=False,
                        arrow_len=arrow_len,
                        joint_count=len(joints),
                    )
                    if tracker is None:
                        continue
                    _accumulate([joint], {joint["name"]: tracker}, acc)
                    if tracker.result()["moved"]:
                        winning_spherical = (joint, drive_axis, sign)
                        break
                if winning_spherical is not None:
                    break

    if winning_spherical is not None:
        joint, drive_axis, sign = winning_spherical
        ctx.step("PhysX: recording spherical joint %s on %s" % (joint["name"], drive_axis))
        tracker, frames = await _run_spherical_drive_sim(
            ctx,
            stage,
            joint,
            saved,
            physics,
            drive_axis,
            sign * float(cfg["spherical_drive_velocity_deg_s"]),
            float(cfg["spherical_drive_damping"]),
            max_force,
            total_frames,
            capture_interval,
            capture=True,
            show_arrows=show_arrows,
            arrow_len=arrow_len,
            joint_count=len(joints),
        )
        if tracker is not None:
            _accumulate([joint], {joint["name"]: tracker}, acc)
        frames_captured.extend(frames)

    # --- Commit drive metrics + movement flags ---
    for j in joints:
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
    # The velocity nudge is a USD body-velocity write, which Newton does not
    # apply, so it is a PhysX-only fallback for D6/other unconstrained joints.
    # Spherical joints were already exercised through the external D6 driver.
    # Under Newton the tensor drive above exercised every scalar-drivable joint.
    if not any_joint_moved and not newton_engine:
        remaining = [
            j
            for j in joints
            if j["name"] not in joint_moved and j.get("type_name") != "PhysicsSphericalJoint"
        ]
        if remaining:
            ctx.step("Drives failed. Pass 1 (search) - velocity nudges...")
        for j in remaining:
            if winning_nudge is not None:
                break
            for direction, dname in velocity_dirs:
                tried_nudges.append((j, direction, dname))
                ctx.step("  %s linear-velocity nudge %s" % (j["name"], dname))
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
        ctx.step("Pass 2 (record) - linear-velocity nudge %s direction %s" % (j["name"], dname))
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
            "Tried drive DOFs and supported fallbacks (both directions): %s -- "
            "no movement detected on any.\n"
            "Fix: Check joint configuration, drive settings, and "
            "joint limits." % (total, tried_desc)
        )

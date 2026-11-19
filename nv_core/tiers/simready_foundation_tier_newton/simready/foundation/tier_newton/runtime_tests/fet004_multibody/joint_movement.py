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

"""Newton-owned FET004 constraint-movement probe.

Scalar joints receive temporary, bounded Newton tensor position targets with
test-owned gains. Supported spherical joints are probed with a balanced force
pair at a lever arm, then the successful direction is recorded. This module
does not perform PhysX USD velocity/nudge or temporary external-D6 trials.

Movement is measured between connected bodies using live transforms. The
configured thresholds and existing aggregate any-joint-moved criterion are
unchanged. Motion evidence only observes the reads already used by that test;
it records nominal step times and partial contexts without changing verdicts.
This probe does not qualify the asset's authored drive tuning (FET022 does).
"""

from simready.evaluate.core.decorator import test
from simready.evaluate_engine_kit.fabric_utils import live_world_matrix
from simready.evaluate_engine_kit.force_display import (
    clear_visuals,
    compute_arrow_length,
    draw_force_arrow,
    get_prim_world_position,
)
from simready.evaluate_engine_kit.physics_utils import (
    active_physics_engine,
    find_root_body,
)
from simready.foundation.tier_newton.runtime_tests._assessment import (
    _has_complete_asset_composition,
    not_applicable,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases._diagnostic_notes import (
    note_secondary_error,
    record_required_cleanup_failure,
)
from simready.foundation.tier_newton.runtime_tests.engine_guard import (
    NEWTON_SCENE_ERROR,
    NewtonSceneInitializationError,
    articulationize_loose_joints,
    asset_has_articulation,
    newton_scene_initialized,
)
from simready.foundation.tier_newton.runtime_tests.fet004_multibody.joint_checks import run_pre_checks
from simready.foundation.tier_newton.runtime_tests.fet004_multibody.joint_discovery import (
    discover_joints,
    sanitize_metric_name,
)
from simready.foundation.tier_newton.runtime_tests.fet004_multibody.newton_drive import (
    activate_newton_position_drives,
    restore_newton_position_drives,
)

ANGULAR_AXES = ("angular", "rotX", "rotY", "rotZ")
LINEAR_AXES = ("linear", "transX", "transY", "transZ")


def _owned_joint_absence_is_established(ctx):
    """Qualify only the applicability marker, including instance-proxy joints."""
    try:
        import omni.usd
        from pxr import Usd, UsdPhysics

        stage = omni.usd.get_context().get_stage()
        asset = ctx.scene.asset
        if stage is None or asset is None:
            return False
        root = stage.GetPrimAtPath(asset.prim_path)
        if not _has_complete_asset_composition(stage, root, ctx=ctx, inspection_includes_instance_proxies=True):
            return False
        if not root or not root.IsValid() or not root.IsActive() or not root.IsDefined():
            return False
        if not stage.GetPopulationMask().IncludesSubtree(root.GetPath()):
            return False
        # Include active but unloaded/undefined prims so incomplete composition
        # cannot establish absence. The asset subtree excludes unrelated joints.
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies(Usd.PrimIsActive)):
            if not prim.IsValid() or not prim.IsDefined() or not prim.IsLoaded():
                return False
            if prim.IsA(UsdPhysics.Joint) and not prim.IsA(UsdPhysics.FixedJoint):
                return False
        return True
    except Exception:
        return False


def _movement_threshold(value, name):
    """Qualify verdict thresholds without changing finite nonnegative policies."""
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.config_validation import (
        finite_number,
    )

    try:
        return finite_number(value, name)
    except ValueError as exc:
        raise RuntimeError("FET004 invalid measurement configuration: %s" % exc) from exc


def _qualify_joint_identities(joints):
    """Keep unique authored names; disambiguate colliding names by prim path."""
    import hashlib
    from collections import Counter

    names = Counter(str(joint["name"]) for joint in joints)
    metric_names = Counter(sanitize_metric_name(str(joint["name"])) for joint in joints)
    used_names = set(names)
    used_metrics = set(metric_names)
    collisions = []
    for joint in joints:
        authored_name = str(joint["name"])
        joint["authored_name"] = authored_name
        if names[authored_name] > 1 or metric_names[sanitize_metric_name(authored_name)] > 1:
            collisions.append(joint)
    for joint in sorted(collisions, key=lambda candidate: str(candidate.get("prim_path", ""))):
        path = joint.get("prim_path")
        if not isinstance(path, str) or not path:
            raise RuntimeError("FET004 cannot disambiguate joint evidence without a prim path")
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        for length in (12, 16, 32, 64):
            alias = f"{joint['authored_name']}__{digest[:length]}"
            metric_alias = sanitize_metric_name(alias)
            if alias not in used_names and metric_alias not in used_metrics:
                joint["name"] = alias
                used_names.add(alias)
                used_metrics.add(metric_alias)
                break
        else:
            raise RuntimeError("FET004 could not establish distinct path-based joint evidence identities")
    return joints


# Frames to step the freshly-played simulation BEFORE applying any joint drive.
# Applying a high-force drive on the very first step after play() -- before the
# Newton runtime has initialized its scene state -- can destabilize the
# constraint solve. Warm-up gives initialization an opportunity before driving;
# zero gravity removes gravitational acceleration but does not prove rest or
# eliminate constraint, contact or control transients.
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

# Missing articulation view or backend position-target support leaves the
# requested FET004 probe incomplete. The execution error carries the setup
# diagnostic; no joint-response failure or applicability is established.
NEWTON_DRIVE_SKIP = (
    "Newton could not drive this asset's joints: no articulation view was "
    "available, or Newton's backend does not provide driven-joint (articulation "
    "drive) control for it. USD DriveAPI velocity targets are inert under Newton, "
    "so this requested movement probe is incomplete. Inspect initialization "
    "logs before classifying the cause; this result alone does not diagnose "
    "an asset defect or prove that another solver passed."
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
        from simready.evaluate_engine_kit.kit_runner import emit_event

        emit_event("joint_movement_result", **fields)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Drive helpers: activate / deactivate a SINGLE axis on a joint
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Velocity nudge fallback (for joints that don't respond to DriveAPI)
# ---------------------------------------------------------------------------


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

        for _path, info in saved.items():
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
    """Require a current Newton Fabric body pose; never use an authored fallback."""
    try:
        from pxr import Gf

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"FET004 Newton required body prim is unavailable: {prim_path}")
        rows = live_world_matrix(stage, prim_path)
        if rows is None:
            raise RuntimeError("FET004 Newton required live Fabric body pose is unavailable")
        matrix = Gf.Matrix4d(1.0)
        for i in range(4):
            matrix.SetRow(i, Gf.Vec4d(*rows[i]))
        return _require_transform(matrix, prim_path)
    except Exception as error:
        raise RuntimeError(f"FET004 Newton required live body transform unavailable: {prim_path}") from error


def _get_authored_setup_matrix(stage, prim_path):
    """Read an explicit stopped-setup anchor reference, never a motion observation."""
    from pxr import Usd, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid() or not UsdGeom.Xformable(prim):
        raise RuntimeError(f"FET004 Newton required setup body is unavailable: {prim_path}")
    return _require_transform(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()), prim_path)


def _require_transform(matrix, label):
    """Reject unavailable, nonfinite or singular required body transforms."""
    import math

    if matrix is None:
        raise RuntimeError(f"FET004 required transform unavailable: {label}")
    try:
        finite = all(math.isfinite(float(matrix[i][j])) for i in range(4) for j in range(4))
        determinant = float(matrix.GetDeterminant())
    except Exception as exc:
        raise RuntimeError(f"FET004 required transform is invalid: {label}") from exc
    if not finite or not math.isfinite(determinant) or determinant == 0.0:
        raise RuntimeError(f"FET004 required transform must be finite and nonsingular: {label}")
    return matrix


def _get_bbox_diagonal(stage, prim_path):
    """Require a finite positive reference diagonal from complete live body geometry."""
    try:
        import math

        from simready.evaluate_engine_kit.fabric_utils import (
            is_rigid_body,
            live_world_aabb,
        )

        live = live_world_aabb(stage, prim_path, is_rigid_body, require_complete=True)
        if live is None:
            raise RuntimeError("FET004 Newton complete live child bounds are unavailable")
        minimum, maximum = live
        if len(minimum) != 3 or len(maximum) != 3:
            raise RuntimeError("FET004 Newton required child bounds must have three coordinates")
        if not all(math.isfinite(float(point[i])) for point in (minimum, maximum) for i in range(3)):
            raise RuntimeError("FET004 Newton required child bounds must be finite")
        extents = [float(maximum[i]) - float(minimum[i]) for i in range(3)]
        if any(value < 0.0 for value in extents):
            raise RuntimeError("FET004 Newton required child bounds are inverted")
        diagonal = math.hypot(*extents)
        if not math.isfinite(diagonal) or diagonal <= 0.0:
            raise RuntimeError("FET004 Newton required child bounds need a positive finite diagonal")
        return diagonal
    except Exception as error:
        raise RuntimeError(f"FET004 Newton required live child bounds unavailable: {prim_path}") from error


def _get_authored_setup_bbox_diagonal(stage, prim_path):
    # type: (object, str) -> float
    """Explicit authored setup sizing, not an evaluated motion observation.

    ``ComputeWorldBound`` returns the bound in the stage's own linear units (not
    metres), so the result is directly comparable to authored joint limits and
    translations, which are also in stage units.
    """
    try:
        import math

        from pxr import Usd, UsdGeom

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"FET004 required child bounds prim is unavailable: {prim_path}")
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
        bbox = cache.ComputeWorldBound(prim)
        r = bbox.ComputeAlignedRange()
        if r.IsEmpty():
            raise RuntimeError("FET004 required child bounds are empty")
        minimum, maximum = r.GetMin(), r.GetMax()
        if not all(math.isfinite(float(point[i])) for point in (minimum, maximum) for i in range(3)):
            raise RuntimeError("FET004 required child bounds must be finite")
        size = [float(maximum[i]) - float(minimum[i]) for i in range(3)]
        if any(value < 0.0 for value in size):
            raise RuntimeError("FET004 required child bounds must have nonnegative extents")
        diagonal = math.hypot(*size)
        if not math.isfinite(diagonal) or diagonal <= 0.0:
            raise RuntimeError("FET004 required child bounds need a positive finite diagonal")
        return diagonal
    except Exception as exc:
        raise RuntimeError(f"FET004 required child bounds unavailable: {prim_path}") from exc


def _compute_relative_transform(parent_world, child_world):
    # type: (object, object) -> object
    """Compute child pose in the parent's frame using Gf row-vector order."""
    parent_world = _require_transform(parent_world, "parent body")
    child_world = _require_transform(child_world, "child body")
    return _require_transform(child_world * parent_world.GetInverse(), "parent-relative body pose")


def _measure_relative_rotation_deg(rel_init, rel_now):
    # type: (object, object) -> float
    """Measure rotation change between two relative transforms (degrees)."""
    try:
        import math

        from pxr import Gf

        def rotation_components(matrix, label):
            # ExtractRotationQuat assumes an orthonormal basis. Decompose the
            # affine transform first so scale/shear cannot masquerade as zero
            # rotation when the quaternion dot product is clamped.
            matrix = _require_transform(matrix, label)
            # Gf's decomposition uses absolute numerical tolerances. A common
            # positive rescaling leaves rotation unchanged and keeps legitimate
            # small-scale assets from being decomposed as the identity pose.
            basis_scale = max(abs(float(matrix[i][j])) for i in range(3) for j in range(3))
            if not math.isfinite(basis_scale) or basis_scale <= 0.0:
                raise RuntimeError("FET004 required relative transform has no finite rotation basis")
            normalized_matrix = Gf.Matrix4d(matrix)
            for i in range(3):
                for j in range(3):
                    normalized_matrix[i, j] = float(matrix[i][j]) / basis_scale
            # Gf.Transform uses an absolute scale cutoff internally and can
            # silently produce identity for a highly anisotropic invertible
            # basis. Factor with no arbitrary cutoff, then qualify the actual
            # finite scale and proper orthonormal rotation before measurement.
            factored, _scale_orientation, scale, rotation, _translation, _projection = normalized_matrix.Factor(0.0)
            if not factored or not all(math.isfinite(float(value)) and float(value) != 0.0 for value in scale):
                raise RuntimeError("FET004 required rotation basis could not be decomposed")
            if not all(math.isfinite(float(rotation[i][j])) for i in range(3) for j in range(3)):
                raise RuntimeError("FET004 decomposed rotation basis must be finite")
            for i in range(3):
                for j in range(3):
                    dot = math.fsum(float(rotation[i][k]) * float(rotation[j][k]) for k in range(3))
                    if not math.isclose(dot, 1.0 if i == j else 0.0, rel_tol=1e-8, abs_tol=1e-8):
                        raise RuntimeError("FET004 decomposed rotation basis is not orthonormal")
            if not math.isclose(float(rotation.GetDeterminant()), 1.0, rel_tol=1e-8, abs_tol=1e-8):
                raise RuntimeError("FET004 decomposed rotation basis is not a proper rotation")
            quaternion = rotation.ExtractRotationQuat()
            components = [float(quaternion.GetReal()), *(float(value) for value in quaternion.GetImaginary())]
            norm = math.hypot(*components)
            if not all(math.isfinite(value) for value in components) or not math.isfinite(norm) or norm <= 0.0:
                raise RuntimeError("FET004 decomposed rotation quaternion must be finite and nonzero")
            return [value / norm for value in components]

        q_init = rotation_components(rel_init, "initial relative body pose")
        q_now = rotation_components(rel_now, "current relative body pose")
        # Angle between quaternions: angle = 2 * acos(|dot(q1, q2)|)
        dot = math.fsum(first * second for first, second in zip(q_init, q_now, strict=True))
        dot = max(-1.0, min(1.0, abs(dot)))
        angle_rad = 2.0 * math.acos(dot)
        return math.degrees(angle_rad)
    except Exception as exc:
        raise RuntimeError("FET004 required relative rotation measurement failed") from exc


def _relative_translation_delta(rel_init, rel_now, reference_parent_world=None):
    """Return displacement in stage units along frozen reference-world axes."""
    try:
        import math

        from pxr import Gf

        rel_init = _require_transform(rel_init, "initial relative body pose")
        rel_now = _require_transform(rel_now, "current relative body pose")
        t_init = rel_init.ExtractTranslation()
        t_now = rel_now.ExtractTranslation()
        delta = Gf.Vec3d(*(float(t_now[i] - t_init[i]) for i in range(3)))
        if reference_parent_world is not None:
            basis = _require_transform(reference_parent_world, "reference parent body pose")
            delta = basis.TransformDir(delta)
        if not all(math.isfinite(float(value)) for value in delta):
            raise RuntimeError("FET004 relative translation must be finite")
        return delta
    except Exception as exc:
        raise RuntimeError("FET004 required relative translation measurement failed") from exc


def _measure_relative_translation(rel_init, rel_now, reference_parent_world=None):
    # type: (object, object, object) -> float
    """Measure translation in world stage units using the frozen parent basis."""
    try:
        import math

        distance = math.hypot(*_relative_translation_delta(rel_init, rel_now, reference_parent_world))
        if not math.isfinite(distance):
            raise RuntimeError("FET004 relative translation must be finite")
        return distance
    except Exception as exc:
        raise RuntimeError("FET004 required relative translation measurement failed") from exc


class JointTracker:
    """Tracks per-frame joint movement, keeping max values.

    Measures child body pose in parent body's local frame every frame.
    Compares to the reference (frame 0) and keeps the maximum rotation
    and translation seen across all frames.
    """

    def __init__(self, stage, joint, ctx=None, phase="movement"):
        # type: (object, dict) -> None
        self.stage = stage
        self.joint = joint
        self.child_path = joint["child_body_path"]
        self.parent_path = joint.get("parent_body_path")
        self.rot_thresh = _movement_threshold(joint.get("_rot_thresh_deg", 1.0), "rotation_threshold_deg")
        self.trans_thresh_pct = _movement_threshold(joint.get("_trans_thresh_pct", 2.0), "translation_threshold_pct")

        self._ref_relative = None  # type: object
        self._bbox_diag = _get_bbox_diagonal(stage, self.child_path)

        self.max_rot_deg = 0.0
        self.max_trans_m = 0.0

        self._capture_reference()
        self.motion = None
        self.observation_steps = 0
        self.phase = phase
        self.physics_fps = 240
        if ctx is not None and callable(getattr(ctx, "begin_motion_history", None)):
            from simready.foundation.tier_newton.runtime_tests.motion_observer import MotionObserver

            counter = getattr(ctx, "_joint_movement_history_count", 0)
            ctx._joint_movement_history_count = counter + 1
            self.physics_fps = int(ctx.config["physics_fps"])
            metadata = {
                "joint_name": joint["name"],
                "authored_joint_name": joint.get("authored_name", joint["name"]),
                "prim_path": joint["prim_path"],
                "child_body_path": self.child_path,
                "parent_body_path": self.parent_path,
                "reference_frame": self.parent_path or "world",
                "phase": phase,
                "physics_fps": self.physics_fps,
                "clock_basis": "nominal observed physics-step index / configured physics_fps; warmup, reset and render ticks excluded",
                "measurement_basis": "live child-body rotation in parent frame; translation mapped through frozen reference-parent linear transform into reference-world stage units; not joint-coordinate or contact evidence",
                "translation_axes": "frozen reference-world axes; common parent motion excluded",
            }
            try:
                from pxr import UsdGeom

                metadata["meters_per_unit"] = float(UsdGeom.GetStageMetersPerUnit(stage))
            except Exception:
                metadata["context_partial"] = True
            self.motion = MotionObserver(
                ctx,
                "joint_movement_%03d" % counter,
                {
                    "rotation_delta": {"unit": "deg", "source": "relative body rotation change from trial reference"},
                    "translation_delta": {
                        "unit": "stage_length",
                        "source": "parent-relative displacement magnitude in frozen reference-world stage units",
                    },
                    **{
                        "translation_"
                        + axis: {
                            "unit": "stage_length",
                            "source": "parent-relative displacement along frozen reference-world axes",
                        }
                        for axis in ("x", "y", "z")
                    },
                },
                metadata=metadata,
                sample_stride=4,
            )
            if metadata.get("context_partial") or not self._reference_parent_available:
                self.motion._warn()

    def _capture_reference(self):
        # type: () -> None
        parent_mat = _get_world_matrix(self.stage, self.parent_path) if self.parent_path else None
        child_mat = _require_transform(_get_world_matrix(self.stage, self.child_path), self.child_path)
        self._reference_parent_world = parent_mat
        if self.parent_path:
            self._ref_relative = _compute_relative_transform(parent_mat, child_mat)
        else:
            self._ref_relative = child_mat
        self._reference_parent_available = True

    def update(self):
        # type: () -> None
        """Sample current frame and update max values."""
        self.observation_steps += 1
        if self._ref_relative is None:
            raise RuntimeError("FET004 required reference transform unavailable")
        parent_mat = _get_world_matrix(self.stage, self.parent_path) if self.parent_path else None
        child_mat = _require_transform(_get_world_matrix(self.stage, self.child_path), self.child_path)
        if self.parent_path:
            rel_now = _compute_relative_transform(parent_mat, child_mat)
        else:
            rel_now = child_mat

        rot = _measure_relative_rotation_deg(self._ref_relative, rel_now)
        trans = _measure_relative_translation(self._ref_relative, rel_now, self._reference_parent_world)
        if rot > self.max_rot_deg:
            self.max_rot_deg = rot
        if trans > self.max_trans_m:
            self.max_trans_m = trans
        if self.motion is not None:
            if not self._reference_parent_available or (self.parent_path and parent_mat is None):
                self.motion._warn()
                return
            try:
                delta = _relative_translation_delta(self._ref_relative, rel_now, self._reference_parent_world)
                self.motion.sample(
                    {
                        "rotation_delta": rot,
                        "translation_delta": trans,
                        **{"translation_" + axis: float(delta[i]) for i, axis in enumerate(("x", "y", "z"))},
                    },
                    self.observation_steps / float(self.physics_fps),
                    self.phase,
                )
            except Exception:
                self.motion._warn()

    def record_capture(self, path):
        if self.motion is not None:
            self.motion.record_capture(path)

    def finish(self, reason="observation_budget_exhausted"):
        if self.motion is not None:
            if reason in ("watchdog_budget_exhausted", "required_transform_unavailable"):
                self.motion._warn()
            self.motion.finish(reason)

    def result(self):
        # type: () -> dict
        """Return measurement results."""
        import math

        if not math.isfinite(self._bbox_diag) or self._bbox_diag <= 0.0:
            raise RuntimeError("FET004 required child bounds need a positive finite diagonal")
        trans_pct = self.max_trans_m / self._bbox_diag * 100.0
        if not math.isfinite(trans_pct):
            raise RuntimeError("FET004 required normalized translation must be finite")
        moved = self.max_rot_deg >= self.rot_thresh or trans_pct >= self.trans_thresh_pct
        return {
            "rotation_deg": round(self.max_rot_deg, 3),
            "translation_pct": round(trans_pct, 2),
            "translation_m": round(self.max_trans_m, 4),
            "bbox_diag_m": round(self._bbox_diag, 4),
            "translation_stage_units": float(self.max_trans_m),
            "bbox_diagonal_stage_units": float(self._bbox_diag),
            "translation_unit": "stage_length",
            "translation_basis": "frozen_reference_world",
            "bbox_diagonal_unit": "stage_length",
            "bbox_purposes": ["default", "render", "proxy"],
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


def _record_joint_metrics(ctx, joints, trackers, joint_moved):
    # type: (object, list, dict, dict) -> bool
    """Write per-joint metrics from a trackers dict. Returns True if any moved."""
    any_moved = False
    for j in joints:
        tracker = trackers.get(j["name"])
        if tracker is None:
            continue
        m = tracker.result()
        _publish_joint_measurements(ctx, j["name"], m)
        if m["moved"]:
            joint_moved[j["name"]] = True
            any_moved = True
    return any_moved


def _publish_joint_measurements(ctx, name, measurement):
    """Publish compatible metrics plus unrounded measurements and their basis."""
    safe = sanitize_metric_name(name)
    for suffix, key in (
        ("rot_deg", "rotation_deg"),
        ("trans_pct", "translation_pct"),
        ("bbox_m", "bbox_diag_m"),
        ("translation_stage_units", "translation_stage_units"),
        ("bbox_diagonal_stage_units", "bbox_diagonal_stage_units"),
        ("translation_unit", "translation_unit"),
        ("translation_basis", "translation_basis"),
        ("translation_evidence_basis", "translation_evidence_basis"),
        ("bbox_diagonal_unit", "bbox_diagonal_unit"),
        ("bbox_purposes", "bbox_purposes"),
    ):
        ctx.add_metric(f"jm_joint_{safe}_{suffix}", measurement.get(key))


def _joint_result_summary(joint, measurement, moved):
    """Retain available evidence in the event without inventing absent reads."""
    sign = joint.get("_open_sign")
    return {
        "name": joint.get("name"),
        "authored_name": joint.get("authored_name", joint.get("name")),
        "prim_path": joint.get("prim_path"),
        "child_body_path": joint.get("child_body_path"),
        "parent_body_path": joint.get("parent_body_path"),
        "type": joint.get("type_name"),
        "axis": joint.get("axis"),
        "open_sign": "+" if sign and sign > 0 else "-" if sign else None,
        "open_travel": joint.get("_open_travel"),
        "moved": bool(moved),
        **{
            key: measurement.get(key)
            for key in (
                "rotation_deg",
                "translation_pct",
                "translation_m",
                "pct_of_travel",
                "bbox_diag_m",
                "translation_stage_units",
                "bbox_diagonal_stage_units",
                "translation_unit",
                "translation_basis",
                "translation_evidence_basis",
                "bbox_diagonal_unit",
                "bbox_purposes",
            )
        },
    }


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
            diag = _get_authored_setup_bbox_diagonal(stage, j["child_body_path"])  # explicit stopped-setup stage units
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


def _world_bbox_center(stage, prim_path):
    # type: (object, str) -> object
    """Composed-USD default-time bounding-box center for optional visualization.

    A fresh BBoxCache is built for the part's visual middle, not its body origin.
    This is not a native/Fabric observation or proof that composed USD follows
    the simulated body. Required tracker observations independently gate motion.
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
    """Draw optional arrows from composed-USD center displacement.

    Centers use default-time composed USD, not a native/Fabric pose readback.
    Draw when that proxy moves past ``eps`` relative to its pre-play center;
    absent/stale centers can omit or misrepresent actual simulated motion.
    Arrows do not establish the verdict or replace required tracker evidence.
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
    """Keep legacy maxima and paired exact evidence from the best normalized trial."""
    for j in joints:
        tracker = trackers.get(j["name"])
        if tracker is None:
            continue
        m = tracker.result()
        a = acc.get(j["name"])
        if a is None:
            acc[j["name"]] = dict(m)
        else:
            # The numerator and reference diagonal must come from one actual
            # trial, not independent maxima with a denominator from a later
            # window. Raw values are never reconstructed from rounded aliases.
            if m.get("translation_stage_units") is not None and m.get("bbox_diagonal_stage_units") is not None:
                ratio = m["translation_stage_units"] / m["bbox_diagonal_stage_units"]
                previous_ratio = (
                    a["translation_stage_units"] / a["bbox_diagonal_stage_units"]
                    if a.get("translation_stage_units") is not None and a.get("bbox_diagonal_stage_units") is not None
                    else None
                )
                if previous_ratio is None or ratio > previous_ratio:
                    for key in (
                        "translation_stage_units",
                        "bbox_diagonal_stage_units",
                        "translation_unit",
                        "translation_basis",
                        "bbox_diagonal_unit",
                        "bbox_purposes",
                    ):
                        a[key] = m.get(key)
            a["rotation_deg"] = max(a["rotation_deg"], m["rotation_deg"])
            a["translation_pct"] = max(a["translation_pct"], m["translation_pct"])
            a["translation_m"] = max(a["translation_m"], m["translation_m"])
            a["bbox_diag_m"] = m["bbox_diag_m"]
            a["moved"] = a["moved"] or m["moved"]
        accumulated = acc[j["name"]]
        accumulated["translation_evidence_basis"] = (
            "trial_with_maximum_normalized_translation"
            if accumulated.get("translation_stage_units") is not None
            else None
        )


# ---------------------------------------------------------------------------
# Newton tensor drive
#
# Newton (MuJoCo-Warp) is a reduced-coordinate engine: it does NOT actuate the
# USD DriveAPI velocity targets the batched-drive path above sets, so every
# joint reads as "did not move" (0/N). Under Newton the joints are instead
# driven through the physics tensor view (isaacsim.core.prims.SingleArticulation)
# with POSITION targets ramped toward each joint's open limit. Motion detection is
# unchanged: JointTracker reads live Fabric pose under Newton, so only the drive
# differs. If Newton's backend cannot provide an articulation drive for the asset
# (drive types unavailable / no articulation view), the drive reports it could
# not run and this FET004 procedure retains its prerequisite skip instead of
# reporting a false 0/N movement failure. That skip proves no movement coverage.
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
    n = j.get("authored_name", j.get("name"))
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
    """Read one required ramp-start snapshot, preserving native real dtypes.

    Move supported tensor buffers to the host before array inspection. Missing
    coordinates or invalid numeric state must stop before target dispatch;
    inventing zeros would change the starting pose and command other DOFs.
    """
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
        require_vector,
    )

    try:
        raw = art.get_joint_positions()
        if callable(getattr(raw, "detach", None)):
            raw = raw.detach()
        if callable(getattr(raw, "cpu", None)):
            raw = raw.cpu()
        positions = require_vector(raw, "FET004 Newton", "joint position", dof_count)
        # Only coerce after dtype, shape and finiteness qualification. Validate
        # the converted snapshot too, rather than admitting conversion overflow.
        result = [float(value) for value in positions]
        require_vector(result, "FET004 Newton", "joint position", dof_count)
        return result
    except Exception as error:
        raise RuntimeError("FET004 Newton required joint-position control readback is unavailable") from error


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
        matrix = _get_authored_setup_matrix(stage, body_path)
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
            from isaacsim.core.prims.single_articulation import (
                SingleArticulation,  # type: ignore
            )
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
    force_view["physics_view"].apply_forces_and_torques_at_position(forces, None, positions, indices, is_global=True)


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
    tracker = JointTracker(stage, joint, ctx, "newton_force_record" if capture else "newton_force_probe")
    captured = []  # type: list
    denom = max(1, total_frames - 1)
    for frame in range(total_frames):
        origin = _newton_link_world_position(force_view)
        if origin is None:
            physics.stop()
            tracker.finish("required_transform_unavailable")
            return None, captured, "Newton child-link transform became unavailable"
        application_point = origin + point_offset
        magnitude = float(force_start) + (float(force_max) - float(force_start)) * float(frame) / denom
        _apply_newton_force_at_position(force_view, direction, magnitude, application_point)
        await ctx.physics_step()
        tracker.update()
        ctx.scene.update_camera_follow()
        if capture and frame % capture_interval == 0:
            captured.append(await ctx.capture_frame(label="joint_movement"))
            tracker.record_capture(captured[-1])
        await ctx.physics_advance()
    physics.stop()
    tracker.finish()
    return tracker, captured, None


def _read_dof_limits(art, dof_count):
    """Require native stops from the same articulation coordinate interface."""
    import math

    import numpy as np
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
        as_real_array,
    )

    try:
        getter = getattr(art, "get_joint_limits", None)
        if callable(getter):
            raw = getter()
        else:
            view = getattr(art, "_articulation_view", None)
            getter = getattr(view, "get_dof_limits", None)
            if callable(getter):
                raw = getter()
            else:
                props = getattr(art, "dof_properties", None)
                if props is None:
                    raise ValueError("native articulation limits are unavailable")
                lower, upper = as_real_array(props["lower"]), as_real_array(props["upper"])
                raw = np.column_stack((lower, upper))
        raw = raw.detach() if callable(getattr(raw, "detach", None)) else raw
        raw = raw.cpu() if callable(getattr(raw, "cpu", None)) else raw
        limits = as_real_array(raw).astype(np.float64)
        if limits.shape == (1, dof_count, 2):
            limits = limits[0]
        if limits.shape != (dof_count, 2):
            raise ValueError("native limit observation has an invalid shape")
        for lower, upper in limits:
            if math.isnan(lower) or math.isnan(upper) or lower > upper or lower == math.inf or upper == -math.inf:
                raise ValueError("native joint stops are unknown or unordered")
        return limits
    except Exception as error:
        raise RuntimeError("FET004 Newton required native joint-limit readback is unavailable") from error


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
    limits = []
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
        limits.append(_read_dof_limits(art, len(names)))
        for li, n in enumerate(names):
            if str(n) in dof_map:
                return None, f"ambiguous Newton DOF name {n!r}; no distinct USD-to-native mapping established"
            dof_map[str(n)] = (ai, li)
    if not arts:
        return None, "articulation view initialization failed (%s)" % "; ".join(init_errors)

    # Resolve each driven USD joint to its runtime articulation DOF.
    joint_records = []  # type: list
    mapped_coordinates = {}
    for j in drive_joints:
        res = None
        for name in _newton_dof_names_for_joint(j):
            if name in dof_map:
                res = dof_map[name]
                break
        if res is None:
            continue
        ai, li = res
        if res in mapped_coordinates and mapped_coordinates[res] != j["prim_path"]:
            return None, "distinct USD joints resolve to the same Newton coordinate; native mapping is ambiguous"
        mapped_coordinates[res] = j["prim_path"]
        dof = _drive_dof_for_joint(j)
        lower, upper = (float(value) for value in limits[ai][li])
        joint_records.append(
            {
                "joint": j,
                "art": ai,
                "dof_index": li,
                "dof": dof,
                "start": targets[ai][li],
                "lower": lower,
                "upper": upper,
            }
        )

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
    """Restore temporary scalar controls even when required state fails."""
    import sys

    try:
        if physics.stop() is False:
            raise RuntimeError("FET004 Newton physics stop was not acknowledged")
    except BaseException as error:
        sys._simready_evaluate_kit_engine_retired = True
        record_required_cleanup_failure(ctx, "Required Newton temporary drive physics stop failed.", error)
        raise
    _reset_transforms(stage, saved)
    activated = {}
    primary = None
    try:
        activated = activate_newton_position_drives(stage, drive_joints, cfg, ctx=ctx)
        return await _run_newton_drive_sim_impl(
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
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup_error = None
        stopped = False
        operations = (
            physics.stop,
            lambda: restore_newton_position_drives(stage, activated, ctx=ctx),
        )
        for index, operation in enumerate(operations):
            if index == 1 and not stopped:
                break  # Never edit DriveAPI opinions on an uncertain live graph.
            try:
                if operation() is False:
                    raise RuntimeError("FET004 Newton physics stop was not acknowledged")
                if index == 0:
                    stopped = True
            except BaseException as error:
                sys._simready_evaluate_kit_engine_retired = True
                record_required_cleanup_failure(
                    ctx, "Required Newton temporary drive cleanup failed.", primary or cleanup_error or error
                )
                if primary is not None:
                    note_secondary_error(
                        primary,
                        lambda secondary=error: f"FET004 Newton temporary drive cleanup also failed: {secondary}",
                    )
                elif cleanup_error is None:
                    cleanup_error = error
                else:
                    note_secondary_error(
                        cleanup_error, lambda error=error: f"Another Newton drive cleanup failed: {error}"
                    )
        if cleanup_error is not None:
            if not isinstance(cleanup_error, Exception):
                raise cleanup_error
            raise RuntimeError("FET004 Newton required temporary drive cleanup failed") from cleanup_error


async def _run_newton_drive_sim_impl(
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

    ref_centers = {}  # type: dict
    arrow_eps = max(1e-4, arrow_len * 0.02)
    if show_arrows:
        for j in drive_joints:
            ref_centers[j["name"]] = _world_bbox_center(stage, j["child_body_path"])

    physics.play()
    # Warm up the freshly-played sim before building the view / driving (see
    # DRIVE_WARMUP_FRAMES). Zero gravity does not itself establish observed rest.
    await ctx.settle(count=DRIVE_WARMUP_FRAMES)

    built, build_error = _build_newton_articulations(ctx, stage, asset_path, drive_joints)
    if built is None:
        return {}, [], False, build_error

    arts = built["arts"]
    targets = built["targets"]
    records = built["joints"]

    # Authoring chooses the existing open direction; required native limits
    # define its absolute stop in the same coordinates as the live start.
    # No USD-to-tensor prismatic unit assumption or start+absolute-limit sum.
    for rec in records:
        j = rec["joint"]
        sgn = j.get("_open_sign") or 1.0
        lower, upper = rec["lower"], rec["upper"]
        from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_targets import (
            _FLOAT32_LIMIT_SENTINEL,
        )

        if (
            not all(math.isfinite(value) for value in (lower, upper))
            or lower >= upper
            or math.isclose(lower, -_FLOAT32_LIMIT_SENTINEL, rel_tol=1e-6, abs_tol=0.0)
            or math.isclose(upper, _FLOAT32_LIMIT_SENTINEL, rel_tol=1e-6, abs_tol=0.0)
        ):
            raise RuntimeError("FET004 Newton requires imported bounded native stops before scalar excitation")
        rec["open_target"] = upper if sgn > 0 else lower

    trackers = {j["name"]: JointTracker(stage, j, ctx, "newton_position_drive") for j in drive_joints}
    captured = []  # type: list
    deadline = time.monotonic() + 240.0
    stop_reason = "observation_budget_exhausted"
    for frame in range(total_frames):
        # Ramp each driven DOF's target from its start toward the open target so
        # the drive is a gradual input (a step input can ring / destabilize).
        frac = float(frame + 1) / float(total_frames)
        for rec in records:
            base = rec["start"]
            targets[rec["art"]][rec["dof_index"]] = min(
                rec["upper"], max(rec["lower"], base + frac * (rec["open_target"] - base))
            )
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
            for tracker in trackers.values():
                tracker.record_capture(captured[-1])
        if time.monotonic() > deadline:
            ctx.step("Newton drive sim hit 240s watchdog at frame %d" % frame)
            stop_reason = "watchdog_budget_exhausted"
            break
        await ctx.physics_advance()

    physics.stop()
    for tracker in trackers.values():
        tracker.finish(stop_reason)
    return trackers, captured, True, None


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


# Newton-owned test policy and decorator metadata.
JOINT_MOVEMENT_KWARGS = {
    "description": (
        "Probes the supported authored joints with type-aware excitation "
        "(Newton tensor position targets for scalar joints and a balanced "
        "force-at-lever-arm probe for supported spherical joints) "
        "and records relative motion between connected bodies. Overall PASS "
        "requires at least one evaluated joint to exceed its configured "
        "rotation or translation threshold; failed per-joint checks remain "
        "visible. This uses temporary test-owned controls, not the asset's "
        "authored robot-drive configuration, and does not certify every joint "
        "or diagnose a seized joint or incorrect axis by itself."
    ),
    "expected_video": (
        "Scalar joints are driven together; supported spherical joints "
        "are probed separately. The two bodies "
        "connected by that joint visibly move relative to each other in "
        "the joint's allowed direction (rotate around the axis for a "
        "revolute joint, slide for a prismatic, etc.). A joint that "
        "does not exceed the measured motion threshold retains a failed "
        "per-joint check even when another joint makes the aggregate pass. "
        "Judge the numeric relative-body observations, not visibility alone."
    ),
    "version": "2.2.5",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": {
        "physics_fps": 240,
        "capture_fps": 15,
        "settle_frames": 5,
        "asset_load_timeout": 30,
        "test_duration_seconds": 3.0,
        "angular_velocity_deg_s": 45.0,
        "linear_velocity_m_s": 0.05,
        "drive_max_force": 10000000.0,
        "rotation_threshold_deg": 1.0,
        "translation_threshold_pct": 2.0,
        "newton_drive_stiffness_angular": 10000.0,
        "newton_drive_stiffness_linear": 100000.0,
        "newton_drive_damping": 500.0,
        "newton_spherical_acceleration_start_m_s2": 0.002,
        "newton_spherical_acceleration_max_m_s2": 0.05,
        "show_force_arrows": True,
    },
    "max_duration": 600,
}


@test(
    features=[
        {"id": "FET004_Multibody.Newton.0-1-0", "version": "*"},
        {"id": "FET004_Multibody.RobotNewton.0-1-0", "version": "*"},
    ],
    name="joint_movement_newton",
    **JOINT_MOVEMENT_KWARGS,
)
async def test_joint_movement_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_joint_movement(ctx)


async def run_joint_movement(ctx):
    """Joint movement -- try drive axes one at a time until joints move."""
    cfg = ctx.config
    rot_thresh = _movement_threshold(cfg["rotation_threshold_deg"], "rotation_threshold_deg")
    trans_thresh = _movement_threshold(cfg["translation_threshold_pct"], "translation_threshold_pct")
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
                if _owned_joint_absence_is_established(ctx):
                    ctx.add_metric("assessment_applicability", not_applicable("no_movable_joints", reason))
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
    # This probe requires scalar articulation mapping for revolute/prismatic
    # position commands. Wrap eligible loose tree graphs before discovery;
    # already-articulated assets and unsupported graph shapes remain unchanged.
    articulationize_loose_joints(ctx, stage)
    joints = _qualify_joint_identities(discover_joints(stage, asset_path))
    if not joints:
        ctx.precheck_failure("No joints with child bodies found")
        return

    ctx.step("Found %d movable joints" % len(joints))

    # --- Exclude joints whose DOF is intentionally locked ---
    # A revolute/prismatic joint authored with lowerLimit >= upperLimit has a
    # LOCKED degree of freedom (a common convention to pin a DOF). It is not
    # meant to move. Preserve the probe's exclusion: do not drive it, exclude
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

    # Keep the existing prerequisite: scalar position probes need an imported
    # articulation mapping. A graph that the wrapper cannot convert does not
    # satisfy this test setup, regardless of whether another Newton workflow
    # can simulate it. Spherical joints use the separate balanced-force probe.
    has_articulation = asset_has_articulation(stage)
    force_drivable = [j for j in joints if _drive_dof_for_joint(j) is not None]
    if not has_articulation and force_drivable:
        raise RuntimeError(
            f"Asset has {len(force_drivable):d} force-drivable joint(s) (revolute/prismatic) that could "
            "not be wrapped in an articulation (a joint to world, a shared child, "
            "a loop, or a spherical/D6 joint in the graph). The Newton scalar "
            "position probe requires articulation DOF mapping; this is an "
            "unsupported test setup; no joint-movement verdict is available."
        )
        return

    # Inject config thresholds into joint dicts for _measure_joint_movement
    for j in joints:
        j["_rot_thresh_deg"] = rot_thresh
        j["_trans_thresh_pct"] = trans_thresh

    # --- Classify joints by drive DOF derived from joint type ---
    # Revolute -> angular and prismatic -> linear scalar position probes.
    # Spherical joints instead use Newton's native balanced-force backend.
    batchable = [j for j in joints if _drive_dof_for_joint(j) is not None]

    # --- Lighting + Camera (only if pre-checks passed) ---
    ctx.scene.lighting.add_dome(intensity=1000.0)
    physics = ctx.scene.add_physics(gravity=0.0, fps=float(physics_fps))
    ctx.scene.setup_camera_follow()
    await ctx.settle(count=3)

    # Cook dynamic mesh colliders (and author missing mass) OFF the timeline
    # path, time-boxed, BEFORE play() -- a cold SDF cook triggered by play()
    # can freeze the run. Reports a clean failure if a collider cannot cook.
    from simready.evaluate_engine_kit.physics_utils import cook_skip_message

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        return

    # --- Newton scene-init guard (Newton only; PhysX untouched) ---
    # Newton parses the whole USD stage and aborts scene init on composition
    # errors (an unresolved reference, an unsupported schema) that PhysX
    # tolerates and simulates. timeline.play() still returns, but stepping the
    # un-built sim crashes the session, so verify the scene actually initialized
    # before driving and report an incomplete/error result if not.
    # active_physics_engine() gates this to Newton, so PhysX never plays here.
    physics.play()
    await ctx.settle(count=3)
    newton_ready = newton_scene_initialized()
    physics.stop()
    if not newton_ready:
        raise NewtonSceneInitializationError(NEWTON_SCENE_ERROR)

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

    frames_captured = []  # type: list
    joint_moved = {}  # joint name -> bool
    winning_nudge = None  # (joint_dict, direction_tuple, label)
    winning_newton_force = None  # (joint_dict, direction)
    acc = {}  # joint name -> best {rotation_deg, translation_pct, bbox_diag_m, moved}
    tried_drive_axes = []  # type: list (DOF labels, for the fallback overview)

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
    if batchable:
        tried_drive_axes = sorted({_drive_dof_for_joint(j) for j in batchable})

    winning_sign = None  # type: object (undirected +/- result, for the event)

    # --- Newton position drive and spherical force probe ---
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
            raise RuntimeError(
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
            raise RuntimeError("Newton spherical force probe unavailable: %s." % force_error)
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
                # Losing required state on the recording rerun is not a
                # measured joint-response failure, even if the probe moved.
                failure = RuntimeError(f"Newton spherical force recording unavailable: {error}")
                try:
                    if physics.stop() is False:
                        raise RuntimeError("Newton physics stop was not acknowledged")
                    for body, previous in kin_saved.items():
                        _set_body_kinematic(stage, body, previous)
                    _reset_transforms(stage, saved)
                    _clear_arrows(stage, len(joints))
                except BaseException as cleanup_error:
                    import sys

                    sys._simready_evaluate_kit_engine_retired = True
                    record_required_cleanup_failure(ctx, "Required Newton spherical cleanup failed.", failure)
                    note_secondary_error(
                        failure, lambda secondary=cleanup_error: f"Newton spherical cleanup also failed: {secondary}"
                    )
                raise failure
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
            raise RuntimeError("%s Reason: %s." % (NEWTON_DRIVE_SKIP, drive_error or "unknown"))
            return
        _accumulate(batchable, trackers_n, acc)
        frames_captured.extend(frames_n)

    # --- Commit drive metrics + movement flags ---
    for j in joints:
        a = acc.get(j["name"])
        if a is None:
            continue
        safe = sanitize_metric_name(j["name"])
        _publish_joint_measurements(ctx, j["name"], a)
        # Legacy diagnostic ratio, not native joint-coordinate completion:
        # rounded relative-body motion / authored endpoint magnitude, capped
        # at 100%. Preserve the value and motion verdict; expose its basis.
        travel = j.get("_open_travel")
        if travel:
            dof = _drive_dof_for_joint(j)
            achieved = a["rotation_deg"] if dof == "angular" else a["translation_m"]
            pct = round(min(achieved / travel * 100.0, 100.0), 1)
            ctx.add_metric("jm_joint_%s_pct_of_travel" % safe, pct)
            ctx.add_metric(
                "jm_joint_%s_pct_of_travel_basis" % safe,
                "capped_relative_body_motion_over_authored_endpoint_magnitude",
            )
            a["pct_of_travel"] = pct
            a["pct_of_travel_basis"] = "capped_relative_body_motion_over_authored_endpoint_magnitude"
        if a["moved"]:
            joint_moved[j["name"]] = True

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
        per_joint[name] = _joint_result_summary(j, a, joint_moved.get(name))
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

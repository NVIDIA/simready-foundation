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
"""External-force application + viewport visualization for the EFF phase.

Wiring (post-Isaac Sim probe 2026-04-25):

- External force API:
    omni.physx.get_physx_simulation_interface().apply_force_at_pos(
        body_path, world_force_vec, world_pos_vec, "Force")
  This is the same imperative call v1.6 used; in current Kit (110.0+) it
  lives on the simulation interface (IPhysxSimulation) instead of the
  PhysX C++ class returned by get_physx_interface(). The call is single-
  shot per physics tick, so the EFF runner re-applies it every frame --
  matches v1.6 exactly. No USD schema mutation, no PhysX re-cook, no
  tensor-view invalidation.

  The schema-based route (PhysxSchema.PhysxForceAPI) was tried first but
  authoring the schema mid-simulation re-cooks the articulation and surfaces
  as 'Failed to get DOF positions from backend'. The imperative interface
  on get_physx_simulation_interface() avoids that entirely.

- Arrow visualization: ephemeral USD geometry (UsdGeom.Cylinder shaft +
  UsdGeom.Cone head) under a stable prim path that the EFF phase rewrites and
  removes per (joint, direction). Same approach as v1.6 force_visualization.py.
"""
import math
from dataclasses import dataclass
from typing import Tuple

# ---------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class ForceVector:
    direction: Tuple[float, float, float]
    label: str


def generate_12_force_directions():
    # type: () -> List[ForceVector]
    """Return the 12 unit force vectors: 6 axis-aligned + 6 diagonals (pairwise opposite)."""
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    return [
        ForceVector(direction=(1.0, 0.0, 0.0), label="+X"),
        ForceVector(direction=(-1.0, 0.0, 0.0), label="-X"),
        ForceVector(direction=(0.0, 1.0, 0.0), label="+Y"),
        ForceVector(direction=(0.0, -1.0, 0.0), label="-Y"),
        ForceVector(direction=(0.0, 0.0, 1.0), label="+Z"),
        ForceVector(direction=(0.0, 0.0, -1.0), label="-Z"),
        ForceVector(direction=(inv_sqrt2, inv_sqrt2, 0.0), label="+XY"),
        ForceVector(direction=(-inv_sqrt2, -inv_sqrt2, 0.0), label="-XY"),
        ForceVector(direction=(0.0, inv_sqrt2, inv_sqrt2), label="+YZ"),
        ForceVector(direction=(0.0, -inv_sqrt2, -inv_sqrt2), label="-YZ"),
        ForceVector(direction=(inv_sqrt2, 0.0, inv_sqrt2), label="+XZ"),
        ForceVector(direction=(-inv_sqrt2, 0.0, -inv_sqrt2), label="-XZ"),
    ]


def bisect_break_force(lo, hi, max_iterations, probe):
    # type: (float, float, int, Callable[[float], bool]) -> float
    """Binary-search the smallest force in [lo, hi] where probe(force) is True.

    probe(force) -> True means "the joint broke at this force".

    Returns lo when probe(lo) is True, hi when probe(hi) is False, otherwise the
    midpoint of the final search window.
    """
    if probe(lo):
        return float(lo)
    if not probe(hi):
        return float(hi)
    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        if probe(mid):
            hi = mid
        else:
            lo = mid
    return float((lo + hi) / 2.0)


# ---------------------------------------------------------------------
# Kit-side helpers (lazy imports; NOT unit-tested -- exercised on Kit)
# ---------------------------------------------------------------------


def _get_physx_simulation_interface():
    """Acquire the IPhysxSimulation interface lazily; return None when unavailable."""
    try:
        from omni.physx import get_physx_simulation_interface

        return get_physx_simulation_interface()
    except Exception:
        return None


def apply_external_force(stage, body_path, force_vec, magnitude_newtons):
    # type: (Any, str, Tuple[float, float, float], float) -> None
    """Apply a transient world-frame force to the rigid body at body_path.

    Calls IPhysxSimulation.apply_force_at_pos. In Kit 110+ the signature is:
        apply_force_at_pos(stage_id: int, body_path_int: int,
                           force: carb.Float3, pos: carb.Float3,
                           mode: str = 'Force')

    Single-shot per physics tick: callers MUST re-invoke each step for the
    force to persist (the EFF runner does so).

    Silently no-ops when the simulation interface or required helpers cannot
    be acquired (e.g., pure-Python unit tests). Other exceptions propagate.
    """
    if stage is None or not body_path:
        return
    sim = _get_physx_simulation_interface()
    if sim is None:
        return
    try:
        import carb
        from pxr import PhysicsSchemaTools, UsdUtils
    except Exception:
        return

    stage_id = UsdUtils.StageCache.Get().GetId(stage).ToLongInt()
    if stage_id == -1:
        stage_id = UsdUtils.StageCache.Get().Insert(stage).ToLongInt()
    body_path_int = PhysicsSchemaTools.sdfPathToInt(str(body_path))

    fx = float(force_vec[0]) * float(magnitude_newtons)
    fy = float(force_vec[1]) * float(magnitude_newtons)
    fz = float(force_vec[2]) * float(magnitude_newtons)
    sim.apply_force_at_pos(
        stage_id,
        body_path_int,
        carb.Float3(fx, fy, fz),
        carb.Float3(0.0, 0.0, 0.0),
        "Force",
    )


def clear_external_force(stage, body_path):
    # type: (Any, str) -> None
    """Stop applying force to body_path.

    apply_force_at_pos is single-shot per physics tick, so 'clear' is implicit
    -- skip the next per-tick re-apply and the force vanishes. This function
    exists so callers have a symmetric API.
    """
    return


# ---------------------------------------------------------------------
# Arrow visualization
# ---------------------------------------------------------------------


def _normalize_dir(direction):
    # type: (Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]
    dx, dy, dz = float(direction[0]), float(direction[1]), float(direction[2])
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return None
    return (dx / length, dy / length, dz / length)


def _rotation_from_direction(direction):
    """Quaternion (w, x, y, z) that rotates +Z to direction."""
    from pxr import Gf

    norm = _normalize_dir(direction)
    if norm is None:
        return Gf.Quatf(1.0, 0.0, 0.0, 0.0)
    dx, dy, dz = norm
    if abs(dz - 1.0) < 1e-6:
        return Gf.Quatf(1.0, 0.0, 0.0, 0.0)
    if abs(dz + 1.0) < 1e-6:
        return Gf.Quatf(0.0, 1.0, 0.0, 0.0)
    # Axis = cross(+Z, direction) = (-dy, dx, 0)
    axis_x, axis_y = -dy, dx
    axis_len = math.sqrt(axis_x * axis_x + axis_y * axis_y)
    if axis_len < 1e-6:
        return Gf.Quatf(1.0, 0.0, 0.0, 0.0)
    axis_x /= axis_len
    axis_y /= axis_len
    angle = math.acos(max(-1.0, min(1.0, dz)))
    half = angle / 2.0
    sh = math.sin(half)
    return Gf.Quatf(math.cos(half), axis_x * sh, axis_y * sh, 0.0)


def visualize_force_arrow(
    stage, body_path, force_vec, magnitude_newtons, arrow_path, origin=None, color=(1.0, 0.2, 0.0)
):
    # type: (Any, str, Tuple[float, float, float], float, str, Optional[Tuple[float, float, float]], Tuple[float, float, float]) -> None
    """Author an ephemeral arrow at origin (or body world position) pointing along force_vec.

    Removes any existing prim at arrow_path first. Silent no-op when stage is
    None or the body path does not resolve.
    """
    if stage is None or not arrow_path:
        return
    try:
        from pxr import Gf, UsdGeom
    except Exception:
        return

    norm = _normalize_dir(force_vec)
    if norm is None:
        return

    # Determine origin
    if origin is None:
        try:
            body_prim = stage.GetPrimAtPath(str(body_path))
            if body_prim and body_prim.IsValid():
                bbox_cache = UsdGeom.BBoxCache(0, ["default", "render"], False)
                bbox = bbox_cache.ComputeWorldBound(body_prim)
                aligned = bbox.ComputeAlignedBox()
                mn = aligned.GetMin()
                mx = aligned.GetMax()
                origin = (
                    float((mn[0] + mx[0]) * 0.5),
                    float((mn[1] + mx[1]) * 0.5),
                    float((mn[2] + mx[2]) * 0.5),
                )
            else:
                origin = (0.0, 0.0, 0.0)
        except Exception:
            origin = (0.0, 0.0, 0.0)

    # Arrow points FROM the direction the force is coming FROM, toward the body.
    flipped = (-norm[0], -norm[1], -norm[2])

    # Remove existing arrow at this path
    try:
        existing = stage.GetPrimAtPath(arrow_path)
        if existing and existing.IsValid():
            stage.RemovePrim(arrow_path)
    except Exception:
        pass

    shaft_length = 0.25
    shaft_radius = 0.012
    head_length = 0.08
    head_radius = 0.035

    try:
        arrow_xform = UsdGeom.Xform.Define(stage, arrow_path)
        arrow_xform.AddTranslateOp().Set(Gf.Vec3d(origin[0], origin[1], origin[2]))
        arrow_xform.AddOrientOp().Set(_rotation_from_direction(flipped))

        head_path = arrow_path + "/Head"
        head = UsdGeom.Cone.Define(stage, head_path)
        head.CreateRadiusAttr(head_radius)
        head.CreateHeightAttr(head_length)
        head.CreateAxisAttr("Z")
        head.CreateDisplayColorAttr([Gf.Vec3f(color[0], color[1], color[2])])
        head_xform = UsdGeom.Xformable(head.GetPrim())
        head_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, head_length / 2.0))
        head_xform.AddRotateXOp().Set(180.0)

        shaft_path = arrow_path + "/Shaft"
        shaft = UsdGeom.Cylinder.Define(stage, shaft_path)
        shaft.CreateRadiusAttr(shaft_radius)
        shaft.CreateHeightAttr(shaft_length)
        shaft.CreateAxisAttr("Z")
        shaft.CreateDisplayColorAttr([Gf.Vec3f(color[0], color[1], color[2])])
        shaft_xform = UsdGeom.Xformable(shaft.GetPrim())
        shaft_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, head_length + shaft_length / 2.0))
    except Exception:
        # Authoring on instance-proxy paths can fail; skip viz silently rather than
        # failing the test.
        pass


def clear_force_visualization(stage, arrow_path):
    # type: (Any, str) -> None
    """Remove the ephemeral arrow at arrow_path. Silent on any error."""
    if stage is None or not arrow_path:
        return
    try:
        existing = stage.GetPrimAtPath(arrow_path)
        if existing and existing.IsValid():
            stage.RemovePrim(arrow_path)
    except Exception:
        pass


# ---------------------------------------------------------------------
# Contact-force readback (unit-tested via stub robot)
# ---------------------------------------------------------------------


def read_contact_force_magnitude(robot, body_path):
    """Return the L2 norm of the net contact force on ``body_path`` (in N), or
    ``None`` if contact-force readback is not available for this body.

    Wraps the per-body contact-force source on ``robot``. The robot is
    expected to expose
    ``get_body_contact_force(body_path) -> Optional[Tuple[float, float, float]]``
    that returns the world-space force vector or None if the body isn't
    being tracked.

    Today's ``RobotHandle`` (in ``articulation_phases.robot_handle``) does
    not yet expose ``get_body_contact_force``: contact reporting requires
    a ``RigidContactView`` set up at articulation construction with the
    fingertip body paths registered. Adding that view is tracked as a
    follow-up. Until then, this helper returns ``None`` for callers that
    use contact force as an early-exit optimization; those callers fall back
    to running their full step budget, which is slower but functionally
    correct.
    """
    import math

    if not hasattr(robot, "get_body_contact_force"):
        # Contact-force readback not yet implemented on this RobotHandle.
        # Caller treats None as "not in contact" and proceeds with its
        # default termination policy (typically step-count cap).
        return None
    f = robot.get_body_contact_force(body_path)
    if f is None:
        return None
    return math.sqrt(f[0] * f[0] + f[1] * f[1] + f[2] * f[2])

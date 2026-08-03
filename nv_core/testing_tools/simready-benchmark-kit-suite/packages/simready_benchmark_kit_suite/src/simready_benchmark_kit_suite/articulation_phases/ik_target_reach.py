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
"""IK Target Reach phase (Lula solver) -- Framework 2.0 port from v1.6.

Merges v1's ``shared_phases/ik_target_reach.py`` (orchestration, Lula solver
build, EE discovery) with ``shared_phases/ik_execution.py`` (precompute,
motion interpolation, teleport, hold) into a single phase module.

Public phase entry point:
    async def run_ik_target_reach(ctx, robot, scene_info, config) -> None

Pure helpers exposed for unit testing:
- ``get_defaults() -> Dict[str, Any]``
- ``aggregate_ik_summary(per_target_results) -> Dict[str, Any]``
- ``select_lula_robot_name(robot_type_name, asset_name, override) -> Optional[str]``
- ``default_ee_candidates(robot_name) -> List[str]``

Viewport legend authoring (target spheres, color, text overlays) is NOT
ported; it is intentionally deferred per spec Section 1.2.
"""

import math
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.error_utils import (
    engine_note,
)
from simready_benchmark_kit_suite.articulation_phases.ik_targets import (
    COLOR_TARGET_MOTION_FAILED,
    COLOR_TARGET_OOR_FALSE_POSITIVE,
    COLOR_TARGET_OUT_OF_REACH_OK,
    COLOR_TARGET_REACHED,
    COLOR_TARGET_SOLVE_FAILED,
    IKTarget,
    cleanup_target_spheres,
    create_target_spheres_from_targets,
    generate_ik_targets,
    set_target_sphere_color,
)
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)
from simready_benchmark_kit_suite.articulation_phases.motion_utils import (
    merge_velocity_limits,
    resolve_usd_max_velocities,
    smoothstep,
)

# ---------------------------------------------------------------------------
# Failure-message helpers
# ---------------------------------------------------------------------------
#
# Library philosophy: when a test cannot run on (or fails on) an asset, the
# failure message must teach the asset author EXACTLY how to fix the asset.
# Generic "could not solve IK" / "no descriptor" is useless to an author --
# they need (1) which prim/attribute to edit, (2) example good values, and
# (3) a spec reference + a real-asset example to copy from.
#
# These helpers are exposed at module scope (not nested) so the test
# harness can render them in result.json + the HTML report without any
# string surgery, and so they remain unit-testable.

_IK_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:      nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/"
    "requirements/robot-type.md (RC.008)\n"
    "             nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/"
    "requirements/robot-schema.md (RC.007)\n"
    "  Feature:   nv_core/sr_specs/docs/features/FET_021-robot_core.md\n"
    "  Lula descriptors: Isaac Sim ships YAML+URDF pairs under\n"
    "             isaacsim.robot_motion.motion_generation/policies/\n"
    "             policy_map.json -- keyed by canonical robot name\n"
    "             (Franka, UR3, UR5, UR10, UR16e, Kinova_Gen3,\n"
    "              Cobotta_Pro_900, Cobotta_Pro_1300, Denso_Cobotta,\n"
    "              Festo_Cobot, Rethink_Sawyer, Rizon4).\n"
    "  Example:   Any Franka_*.usd or UR10_*.usd asset under\n"
    "             sample_content/common_assets/robots_general/ -- the\n"
    "             asset folder name contains the canonical robot key\n"
    '             and the default prim sets isaac:robotType="Manipulator".'
)


def _fix_message_no_lula_descriptor(asset_path, robot_type_name):
    # type: (Any, Any) -> str
    """No Lula descriptor matched this asset -- asset-authoring guidance."""
    supported = ", ".join(_LULA_ROBOT_NAMES)
    return (
        "IK Target Reach phase cannot run: no Lula kinematics descriptor matched this asset.\n"
        "\n"
        "  Found:    asset_path=%r\n"
        "            isaac:robotType=%r\n"
        "  Expected: the asset's path OR its IsaacRobotAPI.isaac:robotType\n"
        "            value contains one of the canonical Lula-supported\n"
        "            robot keys (case-insensitive substring match):\n"
        "              %s\n"
        "\n"
        "FIX (asset-authoring): the Lula IK solver needs a descriptor YAML +\n"
        "URDF pair to know your robot's kinematic chain. Two ways to satisfy\n"
        "this test:\n"
        "\n"
        "  1. RENAME / RETAG to a supported model. If your robot IS one of the\n"
        "     supported models above, ensure the asset folder name (or the\n"
        "     default prim's isaac:robotType token) contains the canonical\n"
        "     key. For example, place the asset under a folder containing\n"
        "     'Franka' or set:\n"
        '         token isaac:robotType = "Manipulator"\n'
        '         string isaac:robotName = "Franka"\n'
        "     on the default prim.\n"
        "\n"
        "  2. PROVIDE an explicit Lula descriptor. Set the phase config in\n"
        "     your test profile:\n"
        '         lula_robot_name: "<canonical-name>"\n'
        '         lula_yaml_path:  "/abs/path/to/robot_descriptor.yaml"\n'
        '         lula_urdf_path:  "/abs/path/to/robot.urdf"\n'
        "     The YAML must list the kinematic chain (base_link, cspace,\n"
        "     active joints, default_q) per Isaac Sim's Lula descriptor\n"
        "     format. See any policy in the policy_map directory cited below\n"
        "     for a working template.\n"
        "\n"
        "%s" % (asset_path, robot_type_name, supported, _IK_SPEC_REFERENCE)
    )


def _fix_message_no_ee_pose(robot_name, ee_frame, asset_path):
    # type: (Any, Any, Any) -> str
    """EE candidate constructed but EE pose query failed at runtime."""
    return (
        "IK Target Reach phase cannot run: Lula solver built for robot %r\n"
        "with EE frame %r, but compute_end_effector_pose() returned no pose\n"
        "for this articulation.\n"
        "\n"
        "  Asset: %s\n"
        "\n"
        "This means the EE link name exists in the Lula descriptor but is\n"
        "NOT present in the articulation's link list at runtime, OR the link\n"
        "is present but has no world transform (e.g. excluded from physics\n"
        "by a 'physics:disabled' override).\n"
        "\n"
        "FIX (asset-authoring): ensure the EE link is part of the\n"
        "articulation and physically active.\n"
        "\n"
        "  1. Verify the link prim exists under the robot's articulation\n"
        "     root and is one of: %s\n"
        "     (the first matching name wins; the canonical default for\n"
        "     Franka-class arms is 'panda_hand'; UR-class arms use 'tool0'\n"
        "     or 'ee_link').\n"
        "  2. If you renamed your EE link, add an alias prim or update the\n"
        "     Lula descriptor YAML to point at the actual name. The link\n"
        "     name in the URDF/USDA must match what the descriptor lists.\n"
        "  3. Confirm the EE link has UsdPhysics.RigidBodyAPI applied and\n"
        "     is NOT overridden with physics:rigidBodyEnabled = false.\n"
        "  4. Confirm the chain from articulation root to EE link has no\n"
        "     gaps -- every intermediate joint must be a physics joint\n"
        "     (revolute/prismatic) listed in IsaacRobotAPI.\n"
        "\n"
        "%s"
        % (
            robot_name,
            ee_frame,
            asset_path,
            ", ".join(repr(c) for c in _DEFAULT_EE_CANDIDATES),
            _IK_SPEC_REFERENCE,
        )
    )


def _fix_message_no_targets(reach_m, base_xyz):
    # type: (float, np.ndarray) -> str
    """Target generator returned empty -- almost always a reach=0 asset."""
    return (
        "IK Target Reach phase cannot run: target generator returned 0\n"
        "targets for this robot.\n"
        "\n"
        "  Computed reach radius : %.4f m\n"
        "  Base world position   : (%.3f, %.3f, %.3f)\n"
        "\n"
        "Targets are sampled on a hemisphere of radius = robot reach around\n"
        "the base. An empty target list means the reach estimate collapsed\n"
        "(typically reach <= 0.1 m), which happens when the asset's world-\n"
        "aligned bounding box is empty -- usually because mesh prims under\n"
        "the asset have no extent or are gated by 'purpose=guide'/'proxy'.\n"
        "\n"
        "FIX (asset-authoring):\n"
        "\n"
        "  1. Ensure the visible robot meshes have purpose=default (or\n"
        "     render). Guide-only / proxy-only meshes are excluded from\n"
        "     the bbox compute and produce reach=0.\n"
        "  2. Compute extents on every UsdGeom.Boundable mesh: in usdview\n"
        "     run `usdGenSchema`-equivalent or simply ensure the .extent\n"
        "     attribute is authored on each mesh prim. Stale or missing\n"
        "     extents cause UsdGeom.BBoxCache to return an empty box.\n"
        "  3. If your robot is non-standard size (>3 m or <0.1 m end-to-end\n"
        "     reach), set the phase config `radius_factors` and physical\n"
        "     scale explicitly -- the auto-clamp in _compute_robot_reach\n"
        "     limits estimates to [0.1, 3.0] m.\n"
        "\n"
        "%s" % (float(reach_m), float(base_xyz[0]), float(base_xyz[1]), float(base_xyz[2]), _IK_SPEC_REFERENCE)
    )


def _fix_message_no_targets_reached(reachable_count, ee_frame, robot_name):
    # type: (int, Any, Any) -> str
    """Solver converged on 0/N reachable targets -- physics / authoring."""
    return (
        "IK Target Reach phase failed: 0 of %d in-reach targets were\n"
        "reached by the end-effector.\n"
        "\n"
        "  Robot solver name : %r\n"
        "  EE link / frame   : %r\n"
        "\n"
        "Targets in this bucket are sampled INSIDE the reach hemisphere, so\n"
        "they are geometrically achievable. Failing all of them indicates\n"
        "the IK chain is mis-authored OR the joint drives cannot move the\n"
        "arm fast / far enough to converge within the per-target frame\n"
        "budget. The most common asset-side root causes:\n"
        "\n"
        "FIX (asset-authoring):\n"
        "\n"
        "  1. JOINT LIMITS too tight. Open every UsdPhysics.RevoluteJoint\n"
        "     and PrismaticJoint along the IK chain and confirm\n"
        "     physics:lowerLimit / physics:upperLimit cover the full\n"
        "     working range of the real robot (e.g. Franka joint 1 is\n"
        "     [-2.8973, 2.8973] rad, NOT the default [-1.0, 1.0]).\n"
        "  2. DRIVE GAINS too weak. Every active joint must have\n"
        "     UsdPhysicsDriveAPI:angular (or :linear) with\n"
        "     drive:stiffness >= 1e5 and drive:damping >= 1e4 for a\n"
        "     position-controlled arm. Zero stiffness = the arm cannot\n"
        "     hold or move toward the target.\n"
        "         float drive:angular:physics:stiffness = 400000\n"
        "         float drive:angular:physics:damping   = 40000\n"
        "         float drive:angular:physics:maxForce  = 1000\n"
        "  3. JOINT VELOCITY LIMITS missing. Without\n"
        "     physics:maxJointVelocity the motion budget falls back to\n"
        "     %.1f rad/s which is too slow for some assets. Set\n"
        "     realistic per-joint maxJointVelocity values (Franka:\n"
        "     ~2.0 rad/s, UR10: ~3.14 rad/s).\n"
        "  4. EE FRAME OFFSET wrong. The Lula descriptor's tool-tip\n"
        "     transform may not match your asset's flange geometry. Inspect\n"
        "     the EE link's xformOp:translate/orient and confirm it lands\n"
        "     at the same world position as the asset's actual TCP.\n"
        "\n"
        "Capture the IK video (label='ik_target_reach') and inspect the\n"
        "first failed target frame -- if the EE is stuck at a single pose,\n"
        "drives are the cause; if it oscillates near the target, gains are\n"
        "too low; if it stops mid-trajectory, joint limits clip the IK\n"
        "solution.\n"
        "\n"
        "%s\n"
        "- %s"
        % (
            int(reachable_count),
            robot_name,
            ee_frame,
            float(get_defaults()["motion_velocity_fallback"]),
            _IK_SPEC_REFERENCE,
            engine_note(
                "If joint authoring is correct, capture per-target solver "
                "logs (motion_generation debug) and file an engine ticket."
            ),
        )
    )


def _fix_message_low_success_rate(
    targets_reached,
    reachable_count,
    actual_rate,
    min_rate,
    failed_indices,
    max_pos_error_m,
):
    # type: (int, int, float, float, List[int], float) -> str
    """Solver reached some but not enough targets -- tuning + authoring."""
    failed_str = ", ".join(str(i) for i in failed_indices[:8]) if failed_indices else "(none recorded)"
    if len(failed_indices) > 8:
        failed_str += " ..."
    return (
        "IK Target Reach phase failed: %d / %d in-reach targets reached\n"
        "(%.1f%%) which is below the %.0f%% minimum required.\n"
        "\n"
        "  Failed target indices : %s\n"
        "  Max position error    : %.4f m\n"
        "\n"
        "Some targets converged, so the IK chain is fundamentally wired up,\n"
        "but specific poses are unreachable. This is almost always one of\n"
        "two things on the asset side:\n"
        "\n"
        "FIX (asset-authoring):\n"
        "\n"
        "  1. JOINT LIMITS clip the IK solution for the failed poses.\n"
        "     Open each failed target's frame in the captured video; if\n"
        "     the arm visibly stops short and one joint sits exactly at\n"
        "     its limit, widen that joint's physics:lowerLimit /\n"
        "     physics:upperLimit to the manufacturer's spec range. Example\n"
        "     for a 7-DOF Franka-class joint:\n"
        "         float physics:lowerLimit = -2.8973\n"
        "         float physics:upperLimit =  2.8973\n"
        "  2. DRIVE GAINS too low to converge within the motion budget.\n"
        "     The per-target motion budget is ~1.5 s (motion_max_seconds).\n"
        "     If the error decreases but does not finish, raise drive\n"
        "     stiffness/damping or relax the position_tolerance config:\n"
        "         float drive:angular:physics:stiffness = 400000\n"
        "         float drive:angular:physics:damping   = 40000\n"
        "  3. EE link OFFSET / orientation mismatch. If max_position_error\n"
        "     hovers at a constant non-zero value across many targets, the\n"
        "     EE link's transform in the Lula descriptor differs from the\n"
        "     authored EE prim. Inspect xformOp:translate on the EE link\n"
        "     and confirm it matches the URDF tool0 / flange origin.\n"
        "\n"
        "%s\n"
        "- %s"
        % (
            int(targets_reached),
            int(reachable_count),
            float(actual_rate) * 100.0,
            float(min_rate) * 100.0,
            failed_str,
            float(max_pos_error_m),
            _IK_SPEC_REFERENCE,
            engine_note(
                "If joint authoring matches the manufacturer spec, capture "
                "the IK video and per-target solver logs for engine review."
            ),
        )
    )


# --- Lula descriptor sourcing (hardcoded table mirroring v1 robot pool) ---
#
# Hardcoded Lula-supported robot names. Mirrors Isaac Sim's policy_map.json
# keys for robots typically shipped with descriptors. ``select_lula_robot_name``
# matches an asset path / type substring against these (case-insensitive);
# Lula's runtime ``load_supported_lula_kinematics_solver_config`` is what
# actually resolves YAML/URDF paths inside ``_try_build_ik_solver``.
_LULA_ROBOT_NAMES = (
    "Franka",
    "UR3",
    "UR5",
    "UR10",
    "UR16e",
    "Kinova_Gen3",
    "Cobotta_Pro_900",
    "Cobotta_Pro_1300",
    "Denso_Cobotta",
    "Festo_Cobot",
    "Rethink_Sawyer",
    "Rizon4",
)

# Generic EE-link candidates tried in order. The same list is used for every
# robot; the kinematics solver picks up whichever name exists in its descriptor.
_DEFAULT_EE_CANDIDATES = (
    "ee_link",
    "tool0",
    "tcp",
    "flange",
    "panda_hand",
    "hand",
    "gripper",
    "right_gripper",
    "ee_suction_link",
)


def select_lula_robot_name(robot_type_name, asset_name, override):
    # type: (Optional[str], Optional[str], Optional[str]) -> Optional[str]
    """Return canonical Lula robot name for this asset, or None.

    Resolution order:
      1. Explicit ``override`` (when truthy).
      2. Substring match against ``asset_name`` (case-insensitive).
      3. Substring match against ``robot_type_name`` (case-insensitive).
    """
    if override:
        return str(override)
    haystacks = [s for s in (asset_name, robot_type_name) if s]
    haystacks = [str(s).lower() for s in haystacks]
    for hay in haystacks:
        for canonical in _LULA_ROBOT_NAMES:
            if canonical.lower() in hay:
                return canonical
    return None


def default_ee_candidates(robot_name):
    # type: (Optional[str]) -> List[str]
    """Default EE-link candidate list (same for every robot)."""
    _ = robot_name
    return list(_DEFAULT_EE_CANDIDATES)


# --- Defaults ---


def get_defaults():
    # type: () -> Dict[str, Any]
    """Default config values; mirrors JIK defaults plus Lula overrides."""
    return {
        "settle_seconds": 1.0,
        "num_reachable_targets": 5,
        "num_out_of_reach_targets": 2,
        "radius_factors": [0.5, 0.7, 0.9],
        "out_of_reach_factor": 1.3,
        "hemisphere_only": True,
        "position_tolerance": 0.02,
        "orientation_tolerance": 0.25,
        "motion_seconds": 4.0,
        "motion_min_seconds": 1.5,
        "motion_max_seconds": 1.5,
        "motion_velocity_scale": 1.0,
        "motion_velocity_fallback": 2.0,
        "motion_update_hz": 60.0,
        "settle_seconds_after_apply": 0.25,
        "min_success_rate": 0.5,
        "bbox_explode_ratio": 10.0,
        "physics_fps": 240.0,
        "capture_fps": 8,
        "lula_robot_name": None,
        "lula_yaml_path": None,
        "lula_urdf_path": None,
    }


# --- Aggregation ---


def aggregate_ik_summary(per_target_results):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    """Roll up per-target results to phase-level metrics."""
    total = len(per_target_results)
    in_reach = [r for r in per_target_results if r.get("reachable", True)]
    out_of_reach = [r for r in per_target_results if not r.get("reachable", True)]
    in_reach_passed = sum(1 for r in in_reach if r.get("ok", False))
    targets_passed = sum(1 for r in per_target_results if r.get("ok", False))
    failed_indices = [int(r.get("index", -1)) for r in per_target_results if not r.get("ok", False)]
    valid_errs = []
    for r in per_target_results:
        err = r.get("pos_error", None)
        if err is None:
            continue
        try:
            err_f = float(err)
        except Exception:
            continue
        if math.isfinite(err_f):
            valid_errs.append(err_f)
    pass_rate = float(in_reach_passed) / float(len(in_reach)) if len(in_reach) > 0 else 0.0
    return {
        "targets_total": int(total),
        "targets_reachable": int(len(in_reach)),
        "targets_out_of_reach": int(len(out_of_reach)),
        "targets_passed": int(targets_passed),
        "targets_failed": int(total - targets_passed),
        "in_reach_passed": int(in_reach_passed),
        "in_reach_failed": int(len(in_reach) - in_reach_passed),
        "failed_indices": failed_indices,
        "max_position_error_m": float(max(valid_errs)) if valid_errs else 0.0,
        "pass_rate": float(pass_rate),
    }


# --- Internal data class ---


@dataclass
class _IKPrecomputeSolution:
    target: IKTarget
    joint_positions: Optional[np.ndarray]
    success: bool
    message: str


# --- Pure motion / wraparound helpers ---


def _normalize_joint_delta(current, target, lower, upper):
    """Pick the shorter +/-2*pi-shifted delta that stays in [lower, upper]."""
    direct = float(target) - float(current)
    if not (math.isfinite(lower) and math.isfinite(upper)):
        return direct
    candidates = [direct]
    for shift in (2.0 * math.pi, -2.0 * math.pi):
        alt = float(target) + shift
        if lower <= alt <= upper:
            candidates.append(alt - float(current))
    return min(candidates, key=lambda d: abs(d))


def _adjust_target_joints(current_joints, target_joints, lowers, uppers):
    """Wraparound + clamp. Returns (adjusted, wrap_count, violation_count)."""
    n = min(len(current_joints), len(target_joints))
    deltas = np.zeros(n, dtype=np.float64)
    wrap = 0
    for i in range(n):
        lo = float(lowers[i]) if i < len(lowers) else -math.inf
        up = float(uppers[i]) if i < len(uppers) else math.inf
        direct = float(target_joints[i]) - float(current_joints[i])
        d = _normalize_joint_delta(float(current_joints[i]), float(target_joints[i]), lo, up)
        deltas[i] = d
        if abs(d - direct) > 0.01:
            wrap += 1
    adjusted = current_joints[:n] + deltas
    violations = 0
    for i in range(n):
        lo = float(lowers[i]) if i < len(lowers) else -math.inf
        up = float(uppers[i]) if i < len(uppers) else math.inf
        v = float(adjusted[i])
        if math.isfinite(lo) and v < lo - 0.001:
            violations += 1
            adjusted[i] = lo
        elif math.isfinite(up) and v > up + 0.001:
            violations += 1
            adjusted[i] = up
    return adjusted, wrap, violations


def _compute_motion_duration_seconds(
    start_joints,
    target_joints,
    max_velocities,
    default_seconds,
    min_seconds,
    max_seconds,
    velocity_scale,
    fallback_velocity,
):
    """Estimate motion duration. Falls back to default when no velocities."""
    try:
        max_vels = max_velocities
        if max_vels is None:
            fb = float(fallback_velocity) if fallback_velocity is not None else 0.0
            if not math.isfinite(fb) or fb <= 0.0:
                return float(default_seconds)
            count = min(len(start_joints), len(target_joints))
            if count <= 0:
                return float(default_seconds)
            max_vels = np.full(count, fb, dtype=np.float64)
        max_vels = np.asarray(max_vels, dtype=np.float64).flatten()
        count = min(len(start_joints), len(target_joints), len(max_vels))
        if count <= 0:
            return float(default_seconds)
        deltas = np.abs(target_joints[:count] - start_joints[:count])
        velocities = max_vels[:count]
        valid = np.isfinite(velocities) & (velocities > 0)
        if not np.any(valid):
            return float(default_seconds)
        max_time = float(np.max(deltas[valid] / velocities[valid]))
        if not math.isfinite(max_time) or max_time <= 0.0:
            return float(default_seconds)
        scale = float(velocity_scale) if math.isfinite(float(velocity_scale)) else 1.0
        if scale <= 0.0:
            scale = 1.0
        duration = max_time * scale
        if math.isfinite(min_seconds) and min_seconds > 0.0:
            duration = max(duration, float(min_seconds))
        if math.isfinite(max_seconds) and max_seconds > 0.0:
            duration = min(duration, float(max_seconds))
        return float(duration)
    except Exception:
        return float(default_seconds)


def _compute_update_interval_frames(timeline_fps, update_hz):
    """Convert update Hz to a frame interval (>= 1)."""
    if timeline_fps <= 0 or update_hz is None or update_hz <= 0:
        return 1
    return max(1, int(round(float(timeline_fps) / float(update_hz))))


# --- Lula solver build (Kit-only; lazy imports) ---


def _resolve_lula_robot_name(ctx, robot, override, interface_config_loader):
    """Resolve robot_name or None on miss (with runtime fallback to Isaac)."""
    robot_type = getattr(robot, "robot_type", None)
    rt_name = getattr(robot_type, "name", None) if robot_type is not None else None
    asset_name = str(getattr(ctx, "asset_path", "") or "")
    name = select_lula_robot_name(rt_name, asset_name, override)
    if name is None:
        try:
            supported = list(interface_config_loader.get_supported_robots_with_lula_kinematics() or [])
        except Exception:
            supported = []
        for s in supported:
            if str(s).lower() in asset_name.lower():
                name = str(s)
                break
    if name is None:
        ctx.log(
            "IK: could not match asset to a supported Lula robot. " "asset=%r robot_type=%r" % (asset_name, rt_name)
        )
        return None
    return name


def _build_lula_kinematics(ctx, robot_name, yaml_path, urdf_path, LulaKinematicsSolver, interface_config_loader):
    """Build LulaKinematicsSolver. Explicit YAML+URDF wins; else policy_map."""
    if yaml_path and urdf_path:
        try:
            return LulaKinematicsSolver(
                robot_description_path=str(yaml_path),
                urdf_path=str(urdf_path),
            )
        except Exception as exc:
            ctx.log("IK: explicit Lula descriptor failed (%s); using policy_map" % exc)
    try:
        cfg = interface_config_loader.load_supported_lula_kinematics_solver_config(robot_name)
    except Exception as exc:
        ctx.log("IK: kinematics loader raised for %r (%s)" % (robot_name, exc))
        return None
    if not cfg:
        ctx.log("IK: no kinematics config for supported robot %r" % robot_name)
        return None
    try:
        return LulaKinematicsSolver(**cfg)
    except Exception as exc:
        ctx.log("IK: LulaKinematicsSolver failed for %r (%s)" % (robot_name, exc))
        return None


def _try_build_ik_solver(ctx, robot, scene_info, config):
    """Construct an ArticulationKinematicsSolver. None on any prereq miss."""
    _ = scene_info
    try:
        from isaacsim.robot_motion.motion_generation import (
            ArticulationKinematicsSolver,
            LulaKinematicsSolver,
            interface_config_loader,
        )
    except Exception as exc:
        ctx.log("IK: motion_generation extension not available (%s)" % exc)
        return None

    robot_name = _resolve_lula_robot_name(ctx, robot, config.get("lula_robot_name"), interface_config_loader)
    if robot_name is None:
        return None

    kinematics = _build_lula_kinematics(
        ctx,
        robot_name,
        config.get("lula_yaml_path"),
        config.get("lula_urdf_path"),
        LulaKinematicsSolver,
        interface_config_loader,
    )
    if kinematics is None:
        return None

    articulation = getattr(robot, "articulation", None) or robot
    for ee in default_ee_candidates(robot_name):
        try:
            solver = ArticulationKinematicsSolver(articulation, kinematics, ee)
            return solver, ee, robot_name
        except Exception:
            continue

    ctx.log("IK: no EE candidate constructed for %r (tried %r)" % (robot_name, list(default_ee_candidates(robot_name))))
    return None


# --- EE / scene helpers (Kit-only) ---


def _get_ee_position(art_ik, ctx):
    try:
        pos, _ = art_ik.compute_end_effector_pose()
        return np.array(pos, dtype=np.float64).reshape(-1)
    except Exception as exc:
        ctx.log("IK: unable to compute end-effector pose (%s)" % exc)
        return None


def _compute_target_error(art_ik, target):
    pos, _ = art_ik.compute_end_effector_pose()
    pos = np.array(pos, dtype=np.float64).reshape(-1)
    return float(np.linalg.norm(pos - target.position))


def _get_robot_base_position(robot, scene_info):
    """Robot base world position. Falls back to origin on failure."""
    stage = scene_info.get("stage")
    try:
        from pxr import Usd, UsdGeom

        root = stage.GetPrimAtPath(robot.prim_path) if stage is not None else None
        if root and root.IsValid():
            xf = UsdGeom.Xformable(root).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            t = xf.ExtractTranslation()
            return np.array([t[0], t[1], t[2]], dtype=np.float64)
    except Exception:
        pass
    return np.array([0.0, 0.0, 0.0], dtype=np.float64)


def _compute_robot_reach(scene_info):
    """Estimate robot reach from asset bbox (clamped to [0.1, 3.0])."""
    asset_prim = scene_info.get("asset_prim")
    if asset_prim is None or not asset_prim.IsValid():
        return 0.5
    try:
        from pxr import Usd, UsdGeom

        purposes = [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy]
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), purposes, useExtentsHint=True)
        aligned = cache.ComputeWorldBound(asset_prim).ComputeAlignedBox()
        if aligned.IsEmpty():
            return 0.5
        size = aligned.GetSize()
        return max(0.1, min(3.0, max(float(size[0]), float(size[1]))))
    except Exception:
        return 0.5


async def _teleport_to_joints(robot, joint_positions, ctx, settle_frames=3):
    """Teleport joints, zero velocities, step a few frames."""
    positions = np.array(joint_positions, dtype=np.float64)
    try:
        robot.set_joint_positions(positions)
    except Exception:
        try:
            robot.set_joint_position_targets(positions)
        except Exception:
            pass
    try:
        robot.set_joint_velocities(np.zeros_like(positions))
    except Exception:
        pass
    for _ in range(int(settle_frames)):
        await ctx.step_one()


# --- Precompute (per-target IK solve + validation) ---


async def _precompute_ik_solutions(
    ctx,
    robot,
    art_ik,
    targets,
    pos_tol,
    ori_tol,
    reference_joints,
):
    """Precompute IK joint targets per-target. Returns (solutions, metrics)."""
    metrics = {
        "out_of_reach_tested": 0,
        "out_of_reach_correctly_failed": 0,
        "precompute_success": 0,
        "solve_success_reachable": 0,
        "solve_failed_reachable": 0,
    }
    solutions = []  # type: List[_IKPrecomputeSolution]
    current_start = reference_joints.copy()
    total_targets = len(targets)

    for i, target in enumerate(targets):
        target_name = "target_%d" % target.index
        # Heartbeat per target: compute_inverse_kinematics is a blocking
        # C++ call (Lula) that does not pump Kit's event loop. Without a
        # ctx.step here, a slow first-call cold-cache solve can starve
        # the orchestrator's 180s stdout-inactivity watchdog and get the
        # whole Kit session killed mid-precompute.
        ctx.step("IK: precomputing %s (%d/%d)" % (target_name, i + 1, total_targets))
        await _teleport_to_joints(robot, current_start, ctx, settle_frames=3)
        try:
            ik_action, success = art_ik.compute_inverse_kinematics(target.position, None, pos_tol, ori_tol)
        except Exception as exc:
            ctx.warn("IK: solver exception for %s (%s)" % (target_name, exc))
            ik_action, success = None, False

        if not target.is_reachable:
            metrics["out_of_reach_tested"] += 1

        if not success or ik_action is None:
            if target.is_reachable:
                metrics["solve_failed_reachable"] += 1
                ctx.warn("IK: solve failed for reachable %s" % target_name)
            else:
                metrics["out_of_reach_correctly_failed"] += 1
                ctx.log("IK: out-of-reach %s correctly rejected" % target_name)
            solutions.append(_IKPrecomputeSolution(target, None, False, "ik_failed"))
            continue

        target_joints = np.array(ik_action.joint_positions, dtype=np.float64)
        await _teleport_to_joints(robot, target_joints, ctx, settle_frames=3)
        solve_error = _compute_target_error(art_ik, target)
        if solve_error > pos_tol:
            ctx.warn("IK: %s precompute validation failed: error=%.4fm" % (target_name, solve_error))
            if target.is_reachable:
                metrics["solve_failed_reachable"] += 1
            solutions.append(_IKPrecomputeSolution(target, None, False, "validation_failed"))
            continue

        metrics["precompute_success"] += 1
        if target.is_reachable:
            metrics["solve_success_reachable"] += 1
        current_start = target_joints.copy()
        solutions.append(_IKPrecomputeSolution(target, target_joints, True, "success"))

    await _teleport_to_joints(robot, reference_joints, ctx, settle_frames=3)
    return solutions, metrics


# --- Motion (per-target interpolation) ---


async def _capture_or_follow(ctx, label, capture_frames, do_capture):
    """One-step capture-or-follow used inside motion / hold loops."""
    if do_capture:
        fp = await ctx.capture_frame(label=label, stabilize_frames=0)
        if fp:
            capture_frames.append(fp)
        ctx.scene.update_camera_follow(update_history=True)
    else:
        ctx.scene.update_camera_follow(update_history=False)


async def _interpolate_ik_motion(
    ctx,
    robot,
    art_ik,
    target,
    target_joints,
    capture_interval,
    capture_frames,
    motion_frames,
    pos_tol,
    robot_root_prim,
    baseline_bbox,
    bbox_ratio_limit,
    target_name,
):
    """Ramp commanded targets start->goal (smoothstep) frame-by-frame, then hold
    and step until convergence -- a paced trajectory, not a single far-target
    step command. Matches how JIK / FRS / MJC / STA drive the robot; keeps an
    uncapped joint from whipping to the goal and destabilizing the solver."""
    HB_EVERY = 40
    if motion_frames <= 0:
        return False, float("inf")
    try:
        start_joints = np.asarray(robot.get_joint_positions(), dtype=np.float64).copy()
        goal = np.asarray(target_joints, dtype=np.float64)
    except Exception as exc:
        ctx.warn("IK: dispatch failed for %s (%s)" % (target_name, exc))
        return False, float("inf")
    n = min(len(start_joints), len(goal))
    delta = np.zeros_like(start_joints)
    delta[:n] = goal[:n] - start_joints[:n]
    ramp_frames = max(1, int(motion_frames))

    last_error = float("inf")
    reached = False
    consecutive_ok = 0
    min_settle = 3

    for fi in range(motion_frames):
        # Paced command: ramp start -> goal over ramp_frames, then hold goal.
        eased = smoothstep((fi + 1) / float(ramp_frames))
        robot.set_joint_position_targets(start_joints + delta * eased)
        await ctx.step_one()
        try:
            last_error = _compute_target_error(art_ik, target)
        except Exception:
            last_error = float("inf")

        if last_error <= pos_tol:
            reached = True
            consecutive_ok += 1
            if consecutive_ok >= min_settle:
                await _capture_or_follow(
                    ctx,
                    "ik_%s_settled_%04d" % (target_name, fi),
                    capture_frames,
                    True,
                )
                break
        else:
            consecutive_ok = 0

        await _capture_or_follow(
            ctx,
            "ik_%s_%04d" % (target_name, fi),
            capture_frames,
            fi % capture_interval == 0,
        )

        if fi % 10 == 0 and baseline_bbox is not None and robot_root_prim is not None:
            cur = compute_world_aligned_bbox(robot_root_prim)
            msg = check_bbox_explode(cur, baseline_bbox, bbox_ratio_limit)
            if msg:
                ctx.warn("IK: %s: %s" % (target_name, msg))
                break

        if fi % HB_EVERY == 0:
            ctx.step("IK %s frame=%d/%d err=%.4f" % (target_name, fi, motion_frames, last_error))

    return reached, last_error


async def _hold_after_reach(
    ctx,
    robot,
    target_joints,
    hold_frames,
    capture_interval,
    capture_frames,
    update_interval_frames,
    target_name,
):
    """Hold at the reached target so captures stabilize."""
    update_interval = max(1, int(update_interval_frames))
    next_update = 0
    for fi in range(int(hold_frames)):
        if target_joints is not None and fi >= next_update:
            try:
                robot.set_joint_position_targets(target_joints)
            except Exception:
                pass
            next_update = fi + update_interval
        await _capture_or_follow(
            ctx,
            "ik_%s_hold_%04d" % (target_name, fi),
            capture_frames,
            fi % capture_interval == 0,
        )
        await ctx.step_one()


async def _capture_and_step_burst(
    ctx,
    capture_frames,
    capture_interval,
    num_frames,
    label_fmt,
):
    """Capture-then-step loop used for reset / final-hold passes."""
    for fi in range(int(num_frames)):
        await _capture_or_follow(
            ctx,
            label_fmt % fi,
            capture_frames,
            fi % capture_interval == 0,
        )
        await ctx.step_one()


# --- Phase entry point ---


async def _setup_ik_phase(ctx, robot, scene_info, config):
    """Build solver, settle, sample base/reach, generate targets.

    Returns dict with art_ik + targets, or None when the phase decided to skip.
    """
    physics_fps = float(config.get("physics_fps", 240.0))
    settle_seconds = float(config.get("settle_seconds", 1.0))

    ctx.step("IK: building Lula kinematics solver")
    ik_impl = _try_build_ik_solver(ctx, robot, scene_info, config)
    if ik_impl is None:
        robot_type = getattr(robot, "robot_type", None)
        rt_name = getattr(robot_type, "name", None) if robot_type is not None else None
        ctx.skip(
            _fix_message_no_lula_descriptor(
                asset_path=str(getattr(ctx, "asset_path", "") or "(unknown)"),
                robot_type_name=rt_name,
            )
        )
        return None
    art_ik, ee_frame_name, robot_name = ik_impl
    ctx.add_metric("ik_robot_name", str(robot_name))
    ctx.add_metric("ik_ee_frame", str(ee_frame_name))
    ctx.log("IK: enabled for robot %r, EE frame %r" % (robot_name, ee_frame_name))

    ctx.step("IK: settling before target generation")
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    ee_pos = _get_ee_position(art_ik, ctx)
    if ee_pos is None:
        ctx.skip(
            _fix_message_no_ee_pose(
                robot_name=robot_name,
                ee_frame=ee_frame_name,
                asset_path=str(getattr(ctx, "asset_path", "") or "(unknown)"),
            )
        )
        return None
    base_pos = _get_robot_base_position(robot, scene_info)
    reach = _compute_robot_reach(scene_info)
    ctx.add_metric("ik_robot_reach_m", float(reach))
    ctx.add_metric("ik_sphere_center_x", float(base_pos[0]))
    ctx.add_metric("ik_sphere_center_y", float(base_pos[1]))
    ctx.add_metric("ik_sphere_center_z", float(base_pos[2]))
    ctx.add_metric("ik_ee_position_x", float(ee_pos[0]))
    ctx.add_metric("ik_ee_position_y", float(ee_pos[1]))
    ctx.add_metric("ik_ee_position_z", float(ee_pos[2]))

    targets = generate_ik_targets(
        robot_reach=reach,
        base_position=base_pos,
        num_reachable=int(config.get("num_reachable_targets", 5)),
        num_out_of_reach=int(config.get("num_out_of_reach_targets", 2)),
        radius_factors=tuple(config.get("radius_factors", [0.5, 0.7, 0.9])),
        out_of_reach_factor=float(config.get("out_of_reach_factor", 1.3)),
        hemisphere_only=bool(config.get("hemisphere_only", True)),
    )
    ctx.add_metric("ik_targets_total", int(len(targets)))
    if not targets:
        ctx.skip(_fix_message_no_targets(reach_m=reach, base_xyz=base_pos))
        return None
    return {
        "art_ik": art_ik,
        "targets": targets,
        "robot_name": robot_name,
        "ee_frame_name": ee_frame_name,
    }


async def _gather_motion_inputs(ctx, robot, scene_info, capture_frames):
    """Capture initial frame, build bbox baseline, fetch joint constraints."""
    fp = await ctx.capture_frame(label="ik_initial", stabilize_frames=0)
    if fp:
        capture_frames.append(fp)
    ctx.scene.update_camera_follow(update_history=True)

    robot_root_prim = scene_info.get("robot_root_prim")
    asset_prim = scene_info.get("asset_prim")
    baseline_bbox = (
        compute_world_aligned_bbox(robot_root_prim or asset_prim) if (robot_root_prim or asset_prim) else None
    )
    if baseline_bbox is not None:
        ctx.add_metric("ik_bbox_baseline_volume", float(baseline_bbox.volume))

    lowers, uppers = robot.get_joint_position_limits()
    dof_vel_limits = robot.get_joint_velocity_limits()
    dof_names = list(robot.dof_names)
    usd_vels = resolve_usd_max_velocities(
        stage=scene_info.get("stage"),
        robot_prim_path=str(getattr(robot, "prim_path", "") or ""),
        dof_names=[str(n) for n in dof_names],
        asset_prim=asset_prim,
        robot_root_prim=robot_root_prim,
        use_min_when_both=True,
        actuator_deg_to_rad=True,
    )
    return {
        "robot_root_prim": robot_root_prim,
        "asset_prim": asset_prim,
        "baseline_bbox": baseline_bbox,
        "lowers": lowers,
        "uppers": uppers,
        "merged_vels": merge_velocity_limits(dof_vel_limits, usd_vels, use_min_when_both=True),
    }


async def _resolve_actual_error(
    ctx,
    robot,
    art_ik,
    target,
    target_joints,
    target_name,
    reached,
    last_error,
    motion_frames,
    capture_frames,
    capture_interval,
    motion_metrics,
    motion_cfg,
):
    """Hold-after-reach + recompute error, or record a timeout."""
    if reached:
        await _hold_after_reach(
            ctx=ctx,
            robot=robot,
            target_joints=target_joints,
            hold_frames=motion_cfg["hold_frames"],
            capture_interval=capture_interval,
            capture_frames=capture_frames,
            update_interval_frames=motion_cfg["update_interval_frames"],
            target_name=target_name,
        )
        try:
            return _compute_target_error(art_ik, target)
        except Exception:
            return last_error
    motion_metrics["motion_timeouts"] += 1
    ctx.warn("IK: %s motion timed out after %d frames (err=%.4fm)" % (target_name, motion_frames, last_error))
    return last_error


def _classify_target_pass(ctx, target, target_name, actual_error, pos_tol, motion_metrics):
    """Decide if a target counts as passing and emit warnings."""
    if actual_error <= pos_tol:
        if not target.is_reachable:
            ctx.log("IK: unexpectedly reached out-of-reach %s (err=%.4fm)" % (target_name, actual_error))
        return bool(target.is_reachable)
    if target.is_reachable:
        motion_metrics["motion_failed_reachable"] += 1
        ctx.warn("IK: %s failed to converge (err=%.4fm > tol=%.4fm)" % (target_name, actual_error, pos_tol))
    return not target.is_reachable


async def _execute_one_target(
    ctx,
    robot,
    art_ik,
    solution,
    capture_frames,
    capture_interval,
    inputs,
    motion_metrics,
    motion_cfg,
):
    """Drive one solved target through motion + hold + reset."""
    target = solution.target
    target_name = "target_%d" % target.index

    if not solution.success or solution.joint_positions is None:
        return {
            "index": int(target.index),
            "ok": bool(not target.is_reachable),
            "reachable": bool(target.is_reachable),
            "pos_error": float("inf"),
            "message": solution.message,
            "solved": False,
            "reached": False,
        }

    current_joints = robot.get_joint_positions().copy()
    target_joints, wrap, viols = _adjust_target_joints(
        current_joints,
        solution.joint_positions,
        inputs["lowers"],
        inputs["uppers"],
    )
    motion_metrics["wraparound_corrections"] += int(wrap)
    motion_metrics["joint_limit_violations"] += int(viols)

    duration = _compute_motion_duration_seconds(
        start_joints=current_joints,
        target_joints=target_joints,
        max_velocities=inputs["merged_vels"],
        default_seconds=motion_cfg["motion_seconds"],
        min_seconds=motion_cfg["motion_min_seconds"],
        max_seconds=motion_cfg["motion_max_seconds"],
        velocity_scale=motion_cfg["motion_velocity_scale"],
        fallback_velocity=motion_cfg["motion_velocity_fallback"],
    )
    motion_frames = max(1, int(duration * motion_cfg["physics_fps"]))
    pos_tol = float(motion_cfg["pos_tol"])

    reached, last_error = await _interpolate_ik_motion(
        ctx=ctx,
        robot=robot,
        art_ik=art_ik,
        target=target,
        target_joints=target_joints,
        capture_interval=capture_interval,
        capture_frames=capture_frames,
        motion_frames=motion_frames,
        pos_tol=pos_tol,
        robot_root_prim=inputs["robot_root_prim"],
        baseline_bbox=inputs["baseline_bbox"],
        bbox_ratio_limit=motion_cfg["bbox_ratio_limit"],
        target_name=target_name,
    )
    actual_error = await _resolve_actual_error(
        ctx=ctx,
        robot=robot,
        art_ik=art_ik,
        target=target,
        target_joints=target_joints,
        target_name=target_name,
        reached=reached,
        last_error=last_error,
        motion_frames=motion_frames,
        capture_frames=capture_frames,
        capture_interval=capture_interval,
        motion_metrics=motion_metrics,
        motion_cfg=motion_cfg,
    )
    target_pass = _classify_target_pass(ctx, target, target_name, actual_error, pos_tol, motion_metrics)

    await _teleport_to_joints(robot, target_joints, ctx, settle_frames=3)
    await _capture_and_step_burst(
        ctx,
        capture_frames,
        capture_interval,
        max(1, int(0.25 * motion_cfg["physics_fps"])),
        "ik_%s_reset_%%04d" % target_name,
    )
    return {
        "index": int(target.index),
        "ok": bool(target_pass),
        "reachable": bool(target.is_reachable),
        "pos_error": float(actual_error),
        "message": "ok" if target_pass else "failed",
        "solved": True,
        "reached": bool(reached),
    }


def _record_phase_metrics(ctx, summary, targets_reached, metrics, motion_metrics):
    """Push aggregate + per-bucket metrics to the test result."""
    ctx.add_metric("ik_targets_reachable", summary["targets_reachable"])
    ctx.add_metric("ik_targets_out_of_reach", summary["targets_out_of_reach"])
    ctx.add_metric("ik_targets_passed", summary["targets_passed"])
    ctx.add_metric("ik_targets_failed", summary["targets_failed"])
    ctx.add_metric("ik_in_reach_passed", summary["in_reach_passed"])
    ctx.add_metric("ik_in_reach_failed", summary["in_reach_failed"])
    ctx.add_metric("ik_max_position_error_m", summary["max_position_error_m"])
    ctx.add_metric("ik_pass_rate", summary["pass_rate"])
    ctx.add_metric("ik_targets_reached", int(targets_reached))
    ctx.add_metric("ik_out_of_reach_tested", int(metrics.get("out_of_reach_tested", 0)))
    ctx.add_metric("ik_out_of_reach_correctly_failed", int(metrics.get("out_of_reach_correctly_failed", 0)))
    ctx.add_metric("ik_solve_success_reachable", int(metrics.get("solve_success_reachable", 0)))
    ctx.add_metric("ik_solve_failed_reachable", int(metrics.get("solve_failed_reachable", 0)))
    ctx.add_metric("ik_motion_failed_reachable", int(motion_metrics["motion_failed_reachable"]))
    ctx.add_metric("ik_motion_timeouts", int(motion_metrics["motion_timeouts"]))
    ctx.add_metric("ik_joint_limit_violations", int(motion_metrics["joint_limit_violations"]))
    ctx.add_metric("ik_wraparound_corrections", int(motion_metrics["wraparound_corrections"]))


def _emit_pass_or_fail(
    ctx,
    summary,
    targets_reached,
    min_success_rate,
    robot_name=None,
    ee_frame_name=None,
):
    """Decide pass/fail based on reachable target success rate."""
    reachable_count = summary["targets_reachable"]
    if reachable_count <= 0:
        return
    actual_rate = float(targets_reached) / float(reachable_count)
    ctx.add_metric("ik_success_rate", actual_rate)
    if targets_reached == 0:
        ctx.fail(
            _fix_message_no_targets_reached(
                reachable_count=reachable_count,
                ee_frame=ee_frame_name,
                robot_name=robot_name,
            )
        )
    elif actual_rate < min_success_rate:
        ctx.fail(
            _fix_message_low_success_rate(
                targets_reached=targets_reached,
                reachable_count=reachable_count,
                actual_rate=actual_rate,
                min_rate=min_success_rate,
                failed_indices=list(summary.get("failed_indices", []) or []),
                max_pos_error_m=float(summary.get("max_position_error_m", 0.0)),
            )
        )


def _build_motion_cfg(config, physics_fps):
    """Pack the motion-sub-cfg dict consumed by ``_execute_one_target``."""
    return {
        "physics_fps": physics_fps,
        "pos_tol": float(config.get("position_tolerance", 0.02)),
        "motion_seconds": float(config.get("motion_seconds", 4.0)),
        "motion_min_seconds": float(config.get("motion_min_seconds", 1.5)),
        "motion_max_seconds": float(config.get("motion_max_seconds", 1.5)),
        "motion_velocity_scale": float(config.get("motion_velocity_scale", 1.0)),
        "motion_velocity_fallback": float(config.get("motion_velocity_fallback", 2.0)),
        "hold_frames": max(1, int(float(config.get("settle_seconds_after_apply", 0.25)) * physics_fps)),
        "update_interval_frames": _compute_update_interval_frames(
            int(physics_fps),
            float(config.get("motion_update_hz", 60.0)),
        ),
        "bbox_ratio_limit": float(config.get("bbox_explode_ratio", 10.0)),
    }


def _ik_sphere_color(result):
    # type: (Dict[str, Any]) -> Tuple[float, float, float]
    """Map a per-target result to its sphere color (same scheme as JIK)."""
    reachable = bool(result.get("reachable", True))
    ok = bool(result.get("ok", False))
    solved = bool(result.get("solved", False))
    if not reachable:
        # Out-of-reach: green-equivalent is "correctly flagged unreachable"
        # (ok) -> magenta; a solver that claimed it reachable -> yellow.
        return COLOR_TARGET_OUT_OF_REACH_OK if ok else COLOR_TARGET_OOR_FALSE_POSITIVE
    if ok:
        return COLOR_TARGET_REACHED  # green: reached within tolerance
    if not solved:
        return COLOR_TARGET_SOLVE_FAILED  # red: no joint solution
    return COLOR_TARGET_MOTION_FAILED  # orange: solved but motion missed


async def run_ik_target_reach(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run the Lula IK Target Reach phase. Mutates ctx via skip / fail / metrics."""
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 8))
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))

    setup = await _setup_ik_phase(ctx, robot, scene_info, config)
    if setup is None:
        return
    art_ik = setup["art_ik"]
    targets = setup["targets"]
    robot_name = setup.get("robot_name")
    ee_frame_name = setup.get("ee_frame_name")

    # Target-sphere visualization (one sphere per target; gray = pending, then
    # colored per outcome). Mirrors JIK so the IK video shows the targets and
    # whether each was reached. Created before the first capture so they are in
    # frame throughout, and removed at the end so the stage stays clean.
    stage = scene_info.get("stage")
    show_spheres = bool(config.get("show_target_spheres", True))
    sphere_scope = str(config.get("target_sphere_scope", "/World/IK_Targets"))
    sphere_radius = float(config.get("target_sphere_radius", 0.04))
    sphere_by_index = {}  # type: Dict[int, Any]
    if show_spheres and stage is not None:
        prims = create_target_spheres_from_targets(
            stage=stage,
            parent_path=sphere_scope,
            targets=targets,
            radius=sphere_radius,
        )
        for tgt, prim in zip(targets, prims):
            sphere_by_index[int(tgt.index)] = prim

    capture_frames = []  # type: List[Any]
    inputs = await _gather_motion_inputs(ctx, robot, scene_info, capture_frames)
    reference_joints = robot.get_joint_positions().copy()

    ctx.step("IK: precomputing solutions for %d targets" % len(targets))
    t0 = time.perf_counter()
    solutions, metrics = await _precompute_ik_solutions(
        ctx=ctx,
        robot=robot,
        art_ik=art_ik,
        targets=targets,
        pos_tol=float(config.get("position_tolerance", 0.02)),
        ori_tol=float(config.get("orientation_tolerance", 0.25)),
        reference_joints=reference_joints,
    )
    ctx.add_metric("ik_precompute_time_sec", float(time.perf_counter() - t0))

    motion_cfg = _build_motion_cfg(config, physics_fps)
    motion_metrics = {
        "joint_limit_violations": 0,
        "wraparound_corrections": 0,
        "motion_timeouts": 0,
        "motion_failed_reachable": 0,
    }
    per_target_results = []  # type: List[Dict[str, Any]]
    targets_reached = 0

    t1 = time.perf_counter()
    for solution in solutions:
        result = await _execute_one_target(
            ctx=ctx,
            robot=robot,
            art_ik=art_ik,
            solution=solution,
            capture_frames=capture_frames,
            capture_interval=capture_interval,
            inputs=inputs,
            motion_metrics=motion_metrics,
            motion_cfg=motion_cfg,
        )
        per_target_results.append(result)
        if result["ok"] and result["reachable"]:
            targets_reached += 1
        if show_spheres:
            prim = sphere_by_index.get(int(result.get("index", -1)))
            if prim is not None:
                set_target_sphere_color(prim, _ik_sphere_color(result))
    ctx.add_metric("ik_motion_time_sec", float(time.perf_counter() - t1))

    await _capture_and_step_burst(
        ctx,
        capture_frames,
        capture_interval,
        max(1, int(0.25 * physics_fps)),
        "ik_final_%04d",
    )
    # Remove the spheres so the asset stage stays clean between tests. The
    # captured frames already contain them, so the video is unaffected.
    if show_spheres and stage is not None:
        cleanup_target_spheres(stage, sphere_scope)
    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="ik_target_reach", role="summary")

    summary = aggregate_ik_summary(per_target_results)
    _record_phase_metrics(ctx, summary, targets_reached, metrics, motion_metrics)
    _emit_pass_or_fail(
        ctx,
        summary,
        targets_reached,
        float(config.get("min_success_rate", 0.5)),
        robot_name=robot_name,
        ee_frame_name=ee_frame_name,
    )


# Re-export for unused-import suppression by lint.
_UNUSED = (Any, Tuple)

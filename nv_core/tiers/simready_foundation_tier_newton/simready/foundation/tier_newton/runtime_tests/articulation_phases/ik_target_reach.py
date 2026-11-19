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

Optional target spheres and result colors are diagnostic media. The verdict
uses the configured sampled success fraction and final live end-effector
position error, not marker color, a kinematic solution alone or a live
orientation guarantee. Standalone-gripper and descriptor prerequisites are
checked separately; required execution failures are not rejected target trials.
"""

import math
import re
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from simready.foundation.tier_newton.runtime_tests._assessment import (
    _has_current_coordinate_exclusions,
    not_applicable,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases._diagnostic_notes import (
    note_secondary_error,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases._independent_dofs import (
    IndependentRobot,
    excluded_dof_indices,
    sample_joint_motion,
    validate_indices,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.config_validation import (
    validate_phase_config,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.ik_targets import (
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
from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_history import (
    finish_joint_observers,
    make_joint_observer,
    record_joint_captures,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_utils import (
    merge_velocity_limits,
    resolve_usd_max_velocities,
    smoothstep,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
    as_real_array,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    require_vector as _require_vector,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_type import (
    is_standalone_gripper,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
    settle_nominal,
)

# ---------------------------------------------------------------------------
# Failure-message helpers
# ---------------------------------------------------------------------------
#
# Diagnostics distinguish missing prerequisites, sampled observations and
# possible setup/importer/asset causes. They do not prescribe unsupported
# authoring changes or force-pass tuning from a failed criterion alone.
#
# These helpers are exposed at module scope (not nested) so the test
# harness can render them in result.json + the HTML report without any
# string surgery, and so they remain unit-testable.

_IK_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:      nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/robot_core/"
    "requirements/robot-type.md (RC.008)\n"
    "             nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/robot_core/"
    "requirements/robot-schema.md (RC.007)\n"
    "  Feature:   nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/"
    "FET022_DrivenJoints.Newton.md\n"
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
    """Describe a missing descriptor prerequisite without fabricating robot identity."""
    return (
        "IK Target Reach cannot run: no Lula descriptor matched this asset.\n"
        "  Asset path: %r\n"
        "  isaac:robotType: %r\n"
        "  Supported model keys: %s\n\n"
        "Check the selected robot, installed Lula policy map and any explicit\n"
        "lula_robot_name/lula_yaml_path/lula_urdf_path configuration. A YAML/URDF\n"
        "pair must describe this actual mechanism, joint order and end-effector\n"
        "frame; do not rename or retag a different robot merely to select a policy.\n"
        "A missing compatible descriptor is insufficient IK evidence, not an\n"
        "automatic asset defect. Preserve the plan and selected runtime version.\n\n"
        "%s" % (asset_path, robot_type_name, ", ".join(_LULA_ROBOT_NAMES), _IK_SPEC_REFERENCE)
    )


def _fix_message_no_ee_pose(robot_name, ee_frame, asset_path):
    # type: (Any, Any, Any) -> str
    """Report a failed pose query without inferring missing physical authoring."""
    return (
        "IK Target Reach cannot run: Lula solver %r with EE frame %r returned\n"
        "no end-effector pose for the articulation.\n"
        "  Asset: %s\n\n"
        "Inspect the descriptor/URDF frame, imported DOF and link mapping,\n"
        "runtime initialization, selected variant and pose-query exception.\n"
        "Compare the actual TCP transform and joint order before attributing an\n"
        "asset defect. Missing query evidence does not prove a missing link or\n"
        "disabled rigid body. Do not add an alias/TCP or physics API with invented\n"
        "transforms merely to satisfy discovery.\n\n"
        "%s" % (robot_name, ee_frame, asset_path, _IK_SPEC_REFERENCE)
    )


def _fix_message_no_targets(reach_m, base_xyz):
    # type: (float, np.ndarray) -> str
    """Report the target-generator context, not a presumed geometry defect."""
    return (
        "IK Target Reach cannot run: target generator returned 0 targets.\n"
        "  Estimated reach radius: %.4f m\n"
        "  Base world position: (%.3f, %.3f, %.3f)\n\n"
        "Inspect the sampled-target configuration, composed geometry/bounds,\n"
        "geometry purpose selection, base transform and execution-stage scale.\n"
        "This reach estimate is a sampling heuristic, not a certified workspace.\n"
        "The current Kit adapter normalizes its execution stage to metersPerUnit\n"
        "1.0; preserve the original authored scale for comparison. Do not invent\n"
        "extents, change geometry purposes or rescale the asset to force coverage.\n\n"
        "%s" % (float(reach_m), float(base_xyz[0]), float(base_xyz[1]), float(base_xyz[2]), _IK_SPEC_REFERENCE)
    )


def _fix_message_no_targets_reached(reachable_count, ee_frame, robot_name):
    # type: (int, Any, Any) -> str
    """Summarize zero successful sampled targets without selecting a repair."""
    return (
        "IK Target Reach failed: 0 of %d in-reach sampled targets reached.\n"
        "  Robot solver name: %r\n"
        "  EE link / frame: %r\n\n"
        "'In-reach' is a geometric sampling label, not proof that each target\n"
        "has a valid IK solution or can be executed within the playback budget.\n"
        "Separate solver failures from playback position-error failures. Compare\n"
        "the descriptor/TCP, DOF order, commands/readbacks, imported controls,\n"
        "limits, coupling, unit basis, base/gravity setup and runtime support.\n"
        "Authored USD revolute limits are degrees and prismatic limits are stage\n"
        "units; runtime angular coordinates are radians and linear tensor units\n"
        "require the qualified motion-metadata basis. Do not paste radian values\n"
        "into USD angular limits, widen limits, raise ratings or change gains/\n"
        "tolerances merely to obtain a pass. Preserve the plan, video and traces.\n"
        "The final observed criterion is end-effector position error; orientation\n"
        "tolerance is a Lula solver input, not a live orientation guarantee.\n\n"
        "%s" % (int(reachable_count), robot_name, ee_frame, _IK_SPEC_REFERENCE)
    )


def _fix_message_low_success_rate(
    targets_reached,
    reachable_count,
    actual_rate,
    min_rate,
    failed_indices,
    max_pos_error_m,
):
    # type: (int, int, float, float, list[int], float) -> str
    """Keep observed target failures separate from possible setup/asset causes."""
    failed_str = ", ".join(str(i) for i in failed_indices[:8]) if failed_indices else "(none recorded)"
    if len(failed_indices) > 8:
        failed_str += " ..."
    return (
        "IK Target Reach failed: %d / %d in-reach sampled targets reached\n"
        "(%.1f%%), below the %.0f%% configured minimum.\n"
        "  Failed target indices: %s\n"
        "  Max live position error: %.4f m\n\n"
        "Partial success does not establish descriptor correctness or identify\n"
        "why the other targets failed. Compare per-target solver status against\n"
        "the actual issued trajectory and live EE position. Check descriptor/TCP\n"
        "alignment, DOF mapping, imported controls/limits, coupling, units and\n"
        "the playback budget before distinguishing an asset defect from setup,\n"
        "solver limitations or a test edge case. Authored USD angular limits use\n"
        "degrees; runtime angular coordinates use radians. Linear runtime units\n"
        "need the recorded qualification. Do not widen limits, raise force ratings,\n"
        "rewrite gains or relax tolerances merely to force a pass.\n"
        "A pass only meets the configured sampled position-success fraction;\n"
        "it does not certify all targets, the full workspace or live orientation.\n\n"
        "%s"
        % (
            int(targets_reached),
            int(reachable_count),
            float(actual_rate) * 100.0,
            float(min_rate) * 100.0,
            failed_str,
            float(max_pos_error_m),
            _IK_SPEC_REFERENCE,
        )
    )


# --- Lula descriptor sourcing (hardcoded table mirroring v1 robot pool) ---
#
# Hardcoded Lula-supported robot names. Mirrors Isaac Sim's policy_map.json
# keys for robots typically shipped with descriptors. ``select_lula_robot_name``
# matches complete asset model identifiers against these (case-insensitive);
# Lula's runtime ``load_supported_lula_kinematics_solver_config`` is what
# actually resolves YAML/URDF paths inside ``_try_build_ik_solver``.
_LULA_ROBOT_NAMES = (
    "Franka",
    "FR3",
    "UR3",
    "UR3e",
    "UR5",
    "UR5e",
    "UR10",
    "UR10e",
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


def _model_identifier_matches(identifier, text):
    return (
        re.search(r"(?<![a-z0-9])" + re.escape(str(identifier).lower()) + r"(?![a-z0-9])", str(text).lower())
        is not None
    )


def select_lula_robot_name(robot_type_name, asset_name, override):
    # type: (Optional[str], Optional[str], Optional[str]) -> Optional[str]
    """Return canonical Lula robot name for this asset, or None.

    Resolution order:
      1. Explicit ``override`` (when truthy).
      2. Complete model identifier in ``asset_name`` (case-insensitive).
      3. Complete model identifier in ``robot_type_name`` (case-insensitive).
    """
    if override:
        return str(override)
    haystacks = [s for s in (asset_name, robot_type_name) if s]
    haystacks = [str(s).lower() for s in haystacks]
    for hay in haystacks:
        if _model_identifier_matches("panda", hay):
            return "Franka"
        for canonical in _LULA_ROBOT_NAMES:
            if _model_identifier_matches(canonical, hay):
                return canonical
    return None


def default_ee_candidates(robot_name):
    # type: (Optional[str]) -> list[str]
    """Default EE-link candidate list (same for every robot)."""
    _ = robot_name
    return list(_DEFAULT_EE_CANDIDATES)


# --- Defaults ---


def get_defaults():
    # type: () -> dict[str, Any]
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
    # type: (list[dict[str, Any]]) -> dict[str, Any]
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
    joint_positions: np.ndarray | None
    success: bool
    message: str
    command_indices: list[int] | None = None


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
            if _model_identifier_matches(s, asset_name):
                name = str(s)
                break
    if name is None:
        ctx.log(f"IK: could not match asset to a supported Lula robot. asset={asset_name!r} robot_type={rt_name!r}")
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


def _host_array(value):
    """Copy backend data to the host without erasing its validation dtype."""
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return as_real_array(value)


def _required_host_vector(value, signal, size=None):
    """Validate the original dtype, then preserve Lula's float64 host contract."""
    original = _require_vector(_host_array(value), "IK", signal, size)
    with np.errstate(over="ignore", invalid="ignore"):
        numeric = original.astype(np.float64, copy=False)
    # A wider real dtype can be finite before narrowing but overflow float64.
    return _require_vector(numeric, "IK", signal, size)


def _compute_end_effector_pose_host(art_ik, position_only=False):
    try:
        joints = _required_host_vector(art_ik.get_joints_subset().get_joint_positions(), "kinematics joint position")
        position, orientation = art_ik.get_kinematics_solver().compute_forward_kinematics(
            art_ik.get_end_effector_frame(), joints, position_only=position_only
        )
        position = _required_host_vector(position, "end-effector position", 3)
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: required kinematics pose readback failed.") from exc
    return position, orientation


def _compute_inverse_kinematics_host(art_ik, target_position, position_tolerance, orientation_tolerance):
    try:
        subset = art_ik.get_joints_subset()
        warm_start = _required_host_vector(subset.get_joint_positions(), "kinematics warm start")
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: required kinematics warm start failed.") from exc
    try:
        result, success = art_ik.get_kinematics_solver().compute_inverse_kinematics(
            art_ik.get_end_effector_frame(),
            target_position,
            None,
            warm_start,
            position_tolerance,
            orientation_tolerance,
        )
        if not isinstance(success, (bool, np.bool_)):
            raise RequiredReadbackError("IK runtime error: solver success status must be a boolean.")
        if not success:
            # Explicit geometric rejection needs no articulation action.
            return None, False
        action = subset.make_articulation_action(result, None)
        if action is None:
            raise RequiredReadbackError("IK runtime error: successful solver returned no articulation action.")
        return action, True
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: required inverse-kinematics execution failed.") from exc


def _get_ee_position(art_ik, ctx):
    try:
        pos, _ = _compute_end_effector_pose_host(art_ik)
        return np.array(pos, dtype=np.float64).reshape(-1)
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: required end-effector position conversion failed.") from exc


def _compute_target_error(art_ik, target):
    try:
        pos, _ = _compute_end_effector_pose_host(art_ik)
        target_position = _required_host_vector(target.position, "target position", 3)
        error = math.dist(pos, target_position)
        if not math.isfinite(error):
            raise RequiredReadbackError("IK runtime error: end-effector position error is not finite.")
        return error
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError(
            "IK runtime error: required end-effector position error calculation failed."
        ) from exc


def _get_robot_base_position(robot, scene_info):
    """Read the finite robot-base world position required for target generation."""
    try:
        from pxr import Usd, UsdGeom

        stage = scene_info.get("stage")
        if stage is None:
            raise ValueError("stage is unavailable")
        root = stage.GetPrimAtPath(robot.prim_path)
        if not root or not root.IsValid():
            raise ValueError("robot root is unavailable")
        xf = UsdGeom.Xformable(root).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = xf.ExtractTranslation()
        position = np.array([translation[0], translation[1], translation[2]], dtype=np.float64)
        if not np.isfinite(position).all():
            raise ValueError("robot-base translation is not finite")
        return position
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: required robot base world position unavailable") from exc


def _compute_robot_reach(scene_info):
    """Estimate reach from a finite, positive asset XY bound before clamping."""
    try:
        from pxr import Usd, UsdGeom

        asset_prim = scene_info.get("asset_prim")
        if asset_prim is None or not asset_prim.IsValid():
            raise ValueError("asset root is unavailable")
        purposes = [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy]
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), purposes, useExtentsHint=True)
        aligned = cache.ComputeWorldBound(asset_prim).ComputeAlignedBox()
        if aligned.IsEmpty():
            raise ValueError("asset bounds are empty")
        size = aligned.GetSize()
        horizontal = np.array([size[0], size[1]], dtype=np.float64)
        if not np.isfinite(horizontal).all() or np.any(horizontal < 0.0) or np.max(horizontal) <= 0.0:
            raise ValueError("asset XY bounds must have a positive finite extent")
        return max(0.1, min(3.0, float(np.max(horizontal))))
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: required robot reach bounds unavailable") from exc


def expand_ik_action(action, current_positions):
    """Expand a finite full or strictly indexed Lula action without losing DOFs."""
    full = _require_vector(current_positions, "IK", "current joint position").astype(np.float64).copy()
    positions = as_real_array(action.joint_positions)
    if positions.dtype.kind not in "iuf" or positions.ndim != 1 or not np.isfinite(positions).all():
        raise ValueError("IK action positions must be a finite vector")
    positions = positions.astype(np.float64)
    raw_indices = getattr(action, "joint_indices", None)
    if raw_indices is None:
        if positions.shape != full.shape:
            raise ValueError("Partial IK action requires joint_indices")
        return positions.copy()
    if any(isinstance(value, (bool, np.bool_)) for value in np.asarray(raw_indices, dtype=object).flat):
        raise ValueError("IK action joint indices cannot be boolean")
    indices = np.asarray(raw_indices)
    if indices.ndim != 1 or indices.shape != positions.shape or indices.dtype.kind not in "iu":
        raise ValueError("IK action indices must be an equally sized integer vector")
    if len(set(map(int, indices))) != len(indices) or np.any(indices < 0) or np.any(indices >= len(full)):
        raise ValueError("IK action contains invalid joint_indices")
    full[indices] = positions
    return full


def _lula_controlled_robot(robot, art_ik, scene_info):
    """Resolve declared coupling and the public descriptor subset before probes."""
    excluded = excluded_dof_indices(scene_info, len(robot.dof_names))
    excluded.update(getattr(robot, "_ik_excluded_indices", ()))
    subset = art_ik.get_joints_subset()
    getter = getattr(subset, "get_joint_subset_indices", None)
    raw_indices = getter() if callable(getter) else getattr(subset, "joint_indices", None)
    if raw_indices is None:
        raise RequiredReadbackError("IK runtime error: Lula descriptor subset has no qualified joint-index mapping")
    if raw_indices is not None:
        indices = list(raw_indices)
        selected = validate_indices(indices, len(robot.dof_names))
        if len(selected) != len(indices):
            raise RequiredReadbackError("IK runtime error: descriptor joint indices are repeated")
        excluded.update(set(range(len(robot.dof_names))) - selected)
    if len(excluded) == len(robot.dof_names):
        raise RequiredReadbackError("IK runtime error: descriptor exposes no independently commandable DOF")
    if not excluded:
        return robot
    return IndependentRobot(robot, excluded)


def _action_controlled_robot(robot, indices):
    if indices is None:
        return robot
    indices = list(indices)
    selected = validate_indices(indices, len(robot.dof_names))
    if len(selected) != len(indices):
        raise RequiredReadbackError("IK runtime error: action joint indices are repeated")
    excluded = set(getattr(robot, "_ik_excluded_indices", ()))
    excluded.update(set(range(len(robot.dof_names))) - selected)
    if len(excluded) == len(robot.dof_names):
        raise RequiredReadbackError("IK runtime error: solver action exposes no independently commandable DOF")
    return IndependentRobot(robot, excluded) if excluded else robot


async def _teleport_to_joints(robot, joint_positions, ctx, settle_frames=3):
    """Synchronize pose and targets, zero velocities, and propagate errors."""
    current = _required_positions(robot, "IK")
    positions = as_real_array(joint_positions)
    if positions.dtype.kind not in "iuf" or positions.shape != current.shape or not np.isfinite(positions).all():
        raise ValueError("IK teleport requires one finite position per articulation DOF")
    positions = positions.astype(np.float64)
    try:
        robot.set_joint_positions(positions)
        robot.set_joint_position_targets(positions)
        robot.set_joint_velocities(np.zeros_like(positions))
    except Exception as exc:
        raise RequiredReadbackError("IK runtime error: failed to establish the required probe configuration") from exc
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
    """Restore reference state on success, error and cancellation."""
    primary_error = None
    try:
        return await _precompute_ik_solutions_impl(ctx, robot, art_ik, targets, pos_tol, ori_tol, reference_joints)
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            await _teleport_to_joints(robot, reference_joints, ctx, settle_frames=3)
        except BaseException as restore_error:
            if primary_error is None:
                raise
            note_secondary_error(
                primary_error,
                lambda restore_error=restore_error: f"IK reference restoration also failed: {restore_error}",
            )


async def _precompute_ik_solutions_impl(ctx, robot, art_ik, targets, pos_tol, ori_tol, reference_joints):
    """Precompute IK joint targets per-target. Returns (solutions, metrics)."""
    metrics = {
        "out_of_reach_tested": 0,
        "out_of_reach_correctly_failed": 0,
        "precompute_success": 0,
        "solve_success_reachable": 0,
        "solve_failed_reachable": 0,
    }
    solutions = []  # type: list[_IKPrecomputeSolution]
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
            ik_action, success = _compute_inverse_kinematics_host(art_ik, target.position, pos_tol, ori_tol)
        except RequiredReadbackError:
            raise
        except Exception as exc:
            raise RequiredReadbackError(f"IK runtime error: solver execution failed for {target_name}.") from exc

        if not isinstance(success, (bool, np.bool_)):
            raise RequiredReadbackError("IK runtime error: solver success status must be a boolean.")
        if success and ik_action is None:
            raise RequiredReadbackError("IK runtime error: successful solver returned no articulation action.")

        if not target.is_reachable:
            metrics["out_of_reach_tested"] += 1

        if not success:
            if target.is_reachable:
                metrics["solve_failed_reachable"] += 1
                ctx.warn("IK: solve failed for reachable %s" % target_name)
            else:
                metrics["out_of_reach_correctly_failed"] += 1
                ctx.log("IK: out-of-reach %s correctly rejected" % target_name)
            solutions.append(_IKPrecomputeSolution(target, None, False, "ik_failed"))
            continue

        target_joints = expand_ik_action(ik_action, _required_positions(robot, "IK"))
        raw_indices = getattr(ik_action, "joint_indices", None)
        command_indices = list(raw_indices) if raw_indices is not None else list(range(len(robot.dof_names)))
        action_robot = _action_controlled_robot(robot, command_indices)
        await _teleport_to_joints(action_robot, target_joints, ctx, settle_frames=3)
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
        solutions.append(_IKPrecomputeSolution(target, target_joints, True, "success", command_indices))

    return solutions, metrics


# --- Motion (per-target interpolation) ---


async def _capture_or_follow(ctx, label, capture_frames, do_capture, motion_observers=None):
    """One-step capture-or-follow used inside motion / hold loops."""
    if do_capture:
        fp = await ctx.capture_frame(label=label, stabilize_frames=0)
        if fp:
            capture_frames.append(fp)
            record_joint_captures(motion_observers or {}, fp)
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
    geometry_root_prim,
    baseline_bbox,
    bbox_ratio_limit,
    target_name,
    motion_observers=None,
    motion_clock=None,
    physics_fps=240.0,
):
    """Ramp commanded targets start->goal (smoothstep) frame-by-frame, then hold
    and step until convergence -- a paced trajectory, not a single far-target
    step command. Matches how JIK / FRS / MJC / STA drive the robot; keeps an
    uncapped joint from whipping to the goal and destabilizing the solver."""
    HB_EVERY = 40
    if motion_frames <= 0:
        return False, float("inf")
    try:
        start_joints = np.asarray(_required_positions(robot, "IK"), dtype=np.float64).copy()
        goal = _required_host_vector(target_joints, "playback joint target", len(start_joints))
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError(f"IK runtime error: required motion dispatch failed for {target_name}.") from exc
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
        command = start_joints + delta * eased
        robot.set_joint_position_targets(command)
        await ctx.step_one()
        if motion_clock is not None:
            motion_clock["steps"] += 1
            motion_clock["command"] = command.copy()
            sample_joint_motion(
                robot,
                motion_observers or {},
                command,
                motion_clock["steps"] / physics_fps,
                "interpolation",
                set(getattr(robot, "_ik_excluded_indices", ())),
            )
        try:
            last_error = _compute_target_error(art_ik, target)
        except RequiredReadbackError:
            raise
        except Exception as exc:
            raise RequiredReadbackError("IK runtime error: required motion position error failed.") from exc

        if last_error <= pos_tol:
            reached = True
            consecutive_ok += 1
            if consecutive_ok >= min_settle:
                await _capture_or_follow(
                    ctx,
                    "ik_%s_settled_%04d" % (target_name, fi),
                    capture_frames,
                    True,
                    motion_observers,
                )
                if motion_clock is not None:
                    motion_clock["stop_reason"] = "end_effector_proximity_observed"
                break
        else:
            consecutive_ok = 0

        await _capture_or_follow(
            ctx,
            "ik_%s_%04d" % (target_name, fi),
            capture_frames,
            fi % capture_interval == 0,
            motion_observers,
        )

        if fi % 10 == 0 and baseline_bbox is not None and geometry_root_prim is not None:
            cur = compute_world_aligned_bbox(geometry_root_prim)
            msg = check_bbox_explode(cur, baseline_bbox, bbox_ratio_limit)
            if msg:
                ctx.warn("IK: %s: %s" % (target_name, msg))
                if motion_clock is not None:
                    motion_clock["stop_reason"] = "bbox_explode_guard"
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
    motion_observers=None,
    motion_clock=None,
    physics_fps=240.0,
):
    """Hold at the reached target so captures stabilize."""
    update_interval = max(1, int(update_interval_frames))
    next_update = 0
    for fi in range(int(hold_frames)):
        if target_joints is not None and fi >= next_update:
            try:
                robot.set_joint_position_targets(target_joints)
                if motion_clock is not None:
                    motion_clock["command"] = np.asarray(target_joints, dtype=np.float64).copy()
            except RequiredReadbackError:
                raise
            except Exception as exc:
                raise RequiredReadbackError("IK runtime error: required reached-target hold command failed.") from exc
            next_update = fi + update_interval
        await _capture_or_follow(
            ctx,
            "ik_%s_hold_%04d" % (target_name, fi),
            capture_frames,
            fi % capture_interval == 0,
            motion_observers,
        )
        await ctx.step_one()
        if motion_clock is not None:
            motion_clock["steps"] += 1
            sample_joint_motion(
                robot,
                motion_observers or {},
                motion_clock.get("command"),
                motion_clock["steps"] / physics_fps,
                "hold",
                set(getattr(robot, "_ik_excluded_indices", ())),
            )


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

    Returns art_ik and targets; missing required inputs raise an execution error.
    """
    nominal_settle_steps(config.get("settle_seconds", 1.0), config.get("physics_fps", 240.0))
    physics_fps = float(config.get("physics_fps", 240.0))
    settle_seconds = float(config.get("settle_seconds", 1.0))

    ctx.step("IK: building Lula kinematics solver")
    ik_impl = _try_build_ik_solver(ctx, robot, scene_info, config)
    if ik_impl is None:
        robot_type = getattr(robot, "robot_type", None)
        rt_name = getattr(robot_type, "name", None) if robot_type is not None else None
        raise RuntimeError(
            _fix_message_no_lula_descriptor(
                asset_path=str(getattr(ctx, "asset_path", "") or "(unknown)"),
                robot_type_name=rt_name,
            )
        )
        return None
    art_ik, ee_frame_name, robot_name = ik_impl
    controlled_robot = _lula_controlled_robot(robot, art_ik, scene_info)
    ctx.add_metric("ik_robot_name", str(robot_name))
    ctx.add_metric("ik_ee_frame", str(ee_frame_name))
    ctx.log("IK: enabled for robot %r, EE frame %r" % (robot_name, ee_frame_name))

    ctx.step("IK: settling before target generation")
    await settle_nominal(ctx, settle_seconds, physics_fps, phase="IK")
    ee_pos = _get_ee_position(art_ik, ctx)
    if ee_pos is None:
        raise RuntimeError(
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
        raise RuntimeError(_fix_message_no_targets(reach_m=reach, base_xyz=base_pos))
        return None
    return {
        "art_ik": art_ik,
        "targets": targets,
        "robot_name": robot_name,
        "ee_frame_name": ee_frame_name,
        "controlled_robot": controlled_robot,
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
        freeze_bbox_reference(
            compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "ik"
        )
        if (asset_prim or robot_root_prim)
        else None
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
    motion_observers=None,
    motion_clock=None,
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
            motion_observers=motion_observers,
            motion_clock=motion_clock,
            physics_fps=motion_cfg["physics_fps"],
        )
        try:
            return _compute_target_error(art_ik, target)
        except RequiredReadbackError:
            raise
        except Exception as exc:
            raise RequiredReadbackError("IK runtime error: required reached-target position error failed.") from exc
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
    scene_info=None,
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

    robot = _action_controlled_robot(robot, solution.command_indices)
    excluded = set(getattr(robot, "_ik_excluded_indices", ()))
    current_joints = _required_positions(robot, "IK").copy()
    solver_joints = solution.joint_positions.copy()
    for index in excluded:
        solver_joints[index] = current_joints[index]
    target_joints, wrap, viols = _adjust_target_joints(
        current_joints,
        solver_joints,
        inputs["lowers"],
        inputs["uppers"],
    )
    motion_metrics["wraparound_corrections"] += int(wrap)
    motion_metrics["joint_limit_violations"] += int(viols)
    for index in excluded:
        target_joints[index] = current_joints[index]

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
    motion_observers = {
        index: make_joint_observer(
            ctx,
            scene_info or {},
            str(joint_name),
            "ik_target_%03d_joint_%03d" % (int(target.index), index),
            (
                {
                    "position": {
                        "unit": "{joint}",
                        "source": "RobotHandle articulation position readback",
                    },
                    "target": {"unit": "{joint}", "source": "position command issued by test"},
                    "error": {
                        "unit": "{joint}",
                        "source": "command minus measured position",
                    },
                }
                if index not in excluded
                else {"position": {"unit": "{joint}", "source": "constraint/passive-owned articulation readback"}}
            ),
            metadata={
                "target_index": int(target.index),
                "target_reachable": bool(target.is_reachable),
                "commanded_independently": index not in excluded,
                "physics_fps": motion_cfg["physics_fps"],
                "capture_interval_steps": capture_interval,
                "observation_basis": "target-local nominal steps during playback and reached-target hold only; solver, teleport, reset and rendering ticks excluded",
                "verdict_basis": "existing end-effector position-error check; joint plots do not prove end-effector tolerance",
                "end_effector_position_tolerance_m": pos_tol,
            },
        )
        for index, joint_name in enumerate(
            getattr(robot, "dof_names", ()) if callable(getattr(ctx, "begin_motion_history", None)) else ()
        )
    }
    motion_clock = {"steps": 0, "stop_reason": "interpolation_window_completed", "command": None}

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
        geometry_root_prim=inputs["asset_prim"] or inputs["robot_root_prim"],
        baseline_bbox=inputs["baseline_bbox"],
        bbox_ratio_limit=motion_cfg["bbox_ratio_limit"],
        target_name=target_name,
        motion_observers=motion_observers,
        motion_clock=motion_clock,
        physics_fps=motion_cfg["physics_fps"],
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
        motion_observers=motion_observers,
        motion_clock=motion_clock,
    )
    target_pass = _classify_target_pass(ctx, target, target_name, actual_error, pos_tol, motion_metrics)
    finish_joint_observers(
        motion_observers,
        "reached_target_hold_completed" if reached else motion_clock["stop_reason"],
    )

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
    # type: (dict[str, Any]) -> tuple[float, float, float]
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
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    """Run the Lula IK Target Reach phase. Mutates ctx via skip / fail / metrics."""
    validate_phase_config(config, "ik_target_reach")
    nominal_settle_steps(config.get("settle_seconds", 1.0), config.get("physics_fps", 240.0))
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 8))
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))

    if is_standalone_gripper(robot, scene_info, getattr(ctx, "asset_validated_features", None)):
        reason = (
            "IK Target Reach is not applicable to standalone grippers: their "
            "articulation DOFs open and close the fingers but do not provide "
            "an arm-like Cartesian workspace for inverse kinematics."
        )
        if _has_current_coordinate_exclusions(robot, scene_info, ctx=ctx):
            ctx.add_metric("assessment_applicability", not_applicable("standalone_gripper", reason))
        ctx.skip(reason)
        return

    setup = await _setup_ik_phase(ctx, robot, scene_info, config)
    if setup is None:
        return
    art_ik = setup["art_ik"]
    robot = setup.get("controlled_robot", robot)
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
    sphere_by_index = {}  # type: dict[int, Any]
    if show_spheres and stage is not None:
        prims = create_target_spheres_from_targets(
            stage=stage,
            parent_path=sphere_scope,
            targets=targets,
            radius=sphere_radius,
        )
        for tgt, prim in zip(targets, prims, strict=False):
            sphere_by_index[int(tgt.index)] = prim

    capture_frames = []  # type: list[Any]
    inputs = await _gather_motion_inputs(ctx, robot, scene_info, capture_frames)
    reference_joints = _required_positions(robot, "IK").copy()

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
    per_target_results = []  # type: list[dict[str, Any]]
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
            scene_info=scene_info,
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
_UNUSED = (Any, tuple)

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

"""Core JIK phase: bounded Jacobian search and sampled live playback checks.
V1 references:
  - shared_phases/jacobian_ik.py (orchestration, target generation,
    success-rate gating).
  - shared_phases/jik_execution.py (precompute, motion interpolation,
    teleport, hold).

This module exposes ``async def run_jacobian_ik(ctx, robot, scene_info,
config) -> None``. It samples live FK poses, searches unchanged targets with
bounded seeds, plays back accepted solutions and evaluates a sampled success
fraction. Optional target spheres and joint histories aid diagnosis without
establishing complete workspace or orientation qualification.

The damped least-squares solver lives in ``jik_solver.py``. Its async solve
awaits the caller's physics-step function after probe writes so live
articulation poses reflect the requested joint configuration.
"""

import math
import time

import numpy as np
from simready.evaluate.core.output_layout import UnsafeEvidencePathError
from simready.foundation.tier_core.runtime_tests._assessment import (
    _has_current_coordinate_exclusions,
    not_applicable,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
    command_targets,
    excluded_dof_indices,
    require_indexed_control,
    sample_joint_motion,
    validate_indices,
    write_probe_state,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    finite_number,
    validate_phase_config,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.ee_discovery import (
    discover_end_effector_link,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.ik_targets import (
    COLOR_TARGET_MOTION_FAILED,
    COLOR_TARGET_OOR_FALSE_POSITIVE,
    COLOR_TARGET_OUT_OF_REACH_OK,
    COLOR_TARGET_REACHED,
    COLOR_TARGET_SOLVE_FAILED,
    IKTarget,
    cleanup_target_spheres,
    create_target_spheres_from_targets,
    set_target_sphere_color,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.jik_solver import JacobianIKSolver
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_history import (
    finish_joint_observers,
    make_joint_observer,
    record_joint_captures,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    require_vector as _require_vector,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import (
    is_standalone_gripper,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
    settle_nominal,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
    SEGMENT_DEFAULTS,
    _finite,
    resolve_velocity_hints,
    segment_frames,
)

# ---------------------------------------------------------------------------
# Fix-message helpers (asset-author guidance)
#
# Reports preserve observed solver/playback failures and prerequisite context.
# A failed criterion is not sufficient evidence of an asset defect or a safe
# gain/limit edit. Repairs and tuning require independent cause verification.
# ---------------------------------------------------------------------------


_SPEC_REFERENCE_ARTICULATION = (
    "REFERENCE:\n"
    "  Spec:      nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_joints/requirements/articulation.md\n"
    "             nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_joints/requirements/joint-body-target-exists.md\n"
    "             nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/hierarchy/"
    "requirements/kinematic-chain-hierarchy.md\n"
    "  Example:   sample_content/common_assets/robots_general/"
    "ur10/simready_usd/ur10.usd\n"
    "             (search for: PhysicsArticulationRootAPI, "
    "PhysicsRevoluteJoint)"
)


def _fix_message_no_end_effector(search_root, robot_prim_path):
    # type: (str, str) -> str
    """Report failed discovery without prescribing an invented tool frame."""
    return (
        f"JIK: no end-effector link could be discovered under {search_root}.\n"
        f"  Articulation root: {robot_prim_path}\n\n"
        "Inspect the composed robotLinks relationship, kinematic-chain tip,\n"
        "imported body/link mapping and actual fixed TCP frame. Compare discovery\n"
        "with the selected variant and initialized runtime articulation before\n"
        "attributing an asset defect. A missing discoverable frame is insufficient\n"
        "test evidence, not permission to invent a zero-offset tool0 or restructure\n"
        "a valid mechanism merely to satisfy this test.\n\n"
        f"{_SPEC_REFERENCE_ARTICULATION}"
    )


def _fix_message_solver_construct(exc):
    # type: (Exception) -> str
    """Retain the construction exception and distinguish setup from asset defects."""
    return (
        "JIK: failed to construct JacobianIKSolver(robot, ee_link).\n"
        "  Exception: %s: %s\n\n"
        "Inspect the initialized backend, imported DOF/link lists, EE body mapping,\n"
        "joint/body relationships, selected variant and articulation-root setup.\n"
        "An importer/API limitation or incomplete initialization can prevent solver\n"
        "construction even for a valid asset. Resolve the actual prerequisite\n"
        "failure before changing authoring; do not add canned physics schemas,\n"
        "limits or gains merely to obtain test coverage.\n\n"
        "%s" % (type(exc).__name__, exc, _SPEC_REFERENCE_ARTICULATION)
    )


def _fix_message_no_in_reach_targets(robot_reach, asset_prim_path):
    # type: (float, str) -> str
    """Describe empty target evidence without blaming authored scale or hierarchy."""
    return (
        "JIK: target generator produced no in-reach targets.\n"
        "  Bbox-based reach estimate: %.4f m\n"
        "  Asset prim: %s\n\n"
        "Inspect target generation, live FK/EE pose updates, returned joint limits,\n"
        "geometry selection/bounds, base transform and execution-stage scale.\n"
        "The estimate is a sampling heuristic, not proof of physical reachability.\n"
        "The current Kit adapter normalizes its execution stage to metersPerUnit\n"
        "1.0; compare this with source scale and importer behavior. Do not change\n"
        "geometry purpose, invent bounds, rescale the asset or reduce coverage\n"
        "merely to pass. Preserve the plan and pose-query diagnostics.\n\n"
        "%s" % (float(robot_reach), asset_prim_path, _SPEC_REFERENCE_ARTICULATION)
    )


def _fix_message_pass_rate_below_min(
    pass_rate,
    min_pass_rate,
    in_reach_passed,
    in_reach_total,
    in_reach_solver_failed,
    in_reach_motion_failed,
    max_pos_err,
    max_orient_err_deg,
    pos_tol,
    orient_tol_deg,
    failure_names,
    ee_link_path,
):
    # type: (float, float, int, int, int, int, float, float, float, float, list[str], str) -> str
    """Separate solver/playback observations from unproven repair prescriptions."""
    return (
        "JIK: in-reach pass rate %.2f below the %.2f configured minimum.\n"
        "  Targets passed: %d / %d\n"
        "  Solver failures (red targets): %d\n"
        "  Playback failures after a solution (orange targets): %d\n"
        "  Worst recorded position residual (solver or playback): %.4f m (tolerance %.3f m)\n"
        "  Worst solver orientation error: %.2f deg (tolerance %.2f deg)\n"
        "  End-effector under test: %s\n"
        "  Failed targets: %s\n\n"
        "A red target did not produce an accepted solver solution; an orange\n"
        "target did not satisfy the final playback criterion. Neither identifies\n"
        "a gain problem, incorrect joint limits or an asset defect by itself.\n"
        "Inspect live FK/Jacobian updates, DOF/link mapping, TCP, solver status,\n"
        "actual commands/readbacks, imported controls/limits, coupling, units,\n"
        "base/gravity setup and playback budget. Authored USD angular limits are\n"
        "degrees; runtime angular coordinates are radians. Qualify linear tensor\n"
        "units from motion metadata. Do not widen limits, raise ratings, prescribe\n"
        "generic drive gains or loosen tolerances merely to obtain a pass.\n"
        "The criterion uses final live EE position plus solver orientation error;\n"
        "it does not independently certify the final live orientation. A pass only\n"
        "meets the sampled success fraction, not every target or the full workspace.\n\n"
        "%s"
        % (
            float(pass_rate),
            float(min_pass_rate),
            int(in_reach_passed),
            int(in_reach_total),
            int(in_reach_solver_failed),
            int(in_reach_motion_failed),
            float(max_pos_err),
            float(pos_tol),
            float(max_orient_err_deg),
            float(orient_tol_deg),
            ee_link_path,
            ", ".join(failure_names) or "(none)",
            _SPEC_REFERENCE_ARTICULATION,
        )
    )


# ---------------------------------------------------------------------------
# Defaults (spec Section 4.1)
# ---------------------------------------------------------------------------


def get_defaults():
    # type: () -> dict[str, Any]
    # Current defaults use five FK-generated reachable poses and two radial
    # diagnostic targets, with 150 iterations per seed attempt (at most four
    # deduplicated attempts). These are bounded sampling/search policies, not
    # guarantees of native runtime support, execution speed or every-target success.
    return {
        "settle_seconds": 1.0,
        # 5 in-reach + 2 out-of-reach = 7 total. Pass = 2/5 = 40%.
        "num_targets": 5,
        "out_of_reach_count": 2,
        # Headline reach-radius diagnostics only; FK sampling does not
        # consume these legacy shell factors.
        "target_radius_factors": (0.5, 0.7, 0.9),
        "out_of_reach_factor": 1.5,
        "position_tolerance": 0.05,
        "orientation_tolerance_deg": 10.0,
        # Finite iteration allowance per seed. FK sampling does not guarantee
        # convergence from a different pose or completion within the wall budget.
        "max_solver_iterations": 150,
        "max_search_wall_seconds": 1800.0,
        "damping_lambda": 0.05,
        "finite_difference_epsilon": 1.0e-5,
        "jacobian_propagation_steps": 1,
        **SEGMENT_DEFAULTS,
        "interpolation_seconds": 0.67,
        "hold_after_reach_seconds": 0.3,
        "interpolation_profile": "smoothstep",
        "physics_fps": 240.0,
        "capture_fps": 15,
        "min_pass_rate": 0.40,
        "bbox_explode_ratio": 10.0,
        "hemisphere_only": True,
        # Visual targets (ported from v1.6 target_generator viewport
        # legend). Disable via `show_target_spheres=False` if asset
        # authoring flags any conflict at /World/IK_Targets/.
        "show_target_spheres": True,
        "target_sphere_radius": 0.04,
        "target_sphere_scope": "/World/IK_Targets",
    }


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


class JIKSearchBudgetExceeded(RequiredReadbackError):
    """The bounded search stopped before complete target evidence existed."""


def validate_search_budget(config):
    """Validate the local search allowance before scene setup or motion."""
    return finite_number(
        (config or {}).get("max_search_wall_seconds", 1800.0),
        "max_search_wall_seconds",
        positive=True,
        maximum=1800.0,
    )


class _JIKSearchContext:
    """Bound existing search work without adding native ticks or changing targets."""

    def __init__(self, ctx, seconds, clock=None):
        self._ctx = ctx
        self._clock = clock or time.perf_counter
        self._started = self._clock()
        self.limit_seconds = seconds
        self.active = True
        self._elapsed = None
        self.stop_reason = "search_in_progress"
        self.last_progress = "phase_entry"
        self.ticks_requested = self.ticks_completed = 0
        self.solver_attempts_started = self.solver_attempts_completed = 0
        self.solver_iterations_completed = 0
        self._jik_search_budget = self

    def __getattr__(self, name):
        return getattr(self._ctx, name)

    def check(self):
        if self.active and self._clock() - self._started >= self.limit_seconds:
            self.stop_reason = "search_budget_exhausted"
            raise JIKSearchBudgetExceeded(
                "JIK search wall budget exhausted (%.3fs allowance, %d completed ticks, "
                "%d completed solver attempts); last progress: %s. "
                "Required target coverage is incomplete; this does not establish an asset defect."
                % (self.limit_seconds, self.ticks_completed, self.solver_attempts_completed, self.last_progress)
            )

    async def step_one(self):
        self.check()
        searching = self.active
        if searching:
            self.ticks_requested += 1
        # An operation's error/cancellation takes precedence over a late budget.
        await self._ctx.step_one()
        if searching:
            self.ticks_completed += 1
        self.check()

    def step(self, message, *args, **kwargs):
        if self.active:
            self.last_progress = str(message)[:256]
        self.check()
        self._ctx.step(message, *args, **kwargs)
        self.check()

    def begin_solver(self):
        self.check()
        self.solver_attempts_started += 1

    def finish_solver(self, result):
        self.solver_attempts_completed += 1
        self.solver_iterations_completed += int(result.iterations)
        self.check()

    def finish(self, reason):
        if self.active:
            self._elapsed = max(0.0, self._clock() - self._started)
            self.active = False
            if self.stop_reason != "search_budget_exhausted":
                self.stop_reason = reason

    def timing_record(self):
        elapsed = self._elapsed if self._elapsed is not None else max(0.0, self._clock() - self._started)
        return {
            "wall_allowance_seconds": self.limit_seconds,
            "wall_elapsed_seconds": elapsed,
            "whole_test_ceiling_seconds": 2400,
            "search_ticks_requested": self.ticks_requested,
            "search_ticks_completed": self.ticks_completed,
            "solver_attempts_started": self.solver_attempts_started,
            "solver_attempts_completed": self.solver_attempts_completed,
            "solver_iterations_completed": self.solver_iterations_completed,
            "last_progress": self.last_progress,
            "stop_reason": self.stop_reason,
            "timing_basis": "phase entry through initial settling, FK sampling and solver search; excludes prior scene setup and subsequent playback/video/cleanup",
        }


def _record_search_timing(ctx, search, primary=None):
    """Optional timing evidence cannot replace the operation's original cause."""
    try:
        ctx.add_metric("jik_search_timing", search.timing_record())
    except BaseException as secondary:
        if primary is None and (not isinstance(secondary, Exception) or isinstance(secondary, UnsafeEvidencePathError)):
            raise
        if primary is not None:
            note_secondary_error(
                primary, lambda secondary=secondary: "JIK optional search timing unavailable: %r" % secondary
            )
        try:
            ctx.warn("JIK optional search timing unavailable; execution outcome unchanged.")
        except BaseException as warning_error:
            if primary is None and (
                not isinstance(warning_error, Exception) or isinstance(warning_error, UnsafeEvidencePathError)
            ):
                raise


def smoothstep(t):
    # type: (float) -> float
    """Smoothstep ease at t in [0, 1]; returns 3t^2 - 2t^3."""
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def interpolate_profile(profile, t):
    # type: (str, float) -> float
    """Evaluate the named interpolation profile at t in [0, 1]."""
    name = str(profile).lower()
    if name == "smoothstep":
        return smoothstep(t)
    t = max(0.0, min(1.0, float(t)))
    if name == "smootherstep":
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    return t


def resolve_motion_timing(config):
    # type: (dict[str, Any]) -> tuple[float, float]
    """Resolve the Core playback timing from its configured PhysX defaults."""
    interp = float(config["interpolation_seconds"])
    hold = float(config["hold_after_reach_seconds"])
    return interp, hold


def compute_pass_rate(passed, total):
    # type: (int, int) -> float
    """Return passed / total, or 0.0 when total <= 0."""
    if total <= 0:
        return 0.0
    return float(passed) / float(total)


def count_distinct_reachable_positions(targets, tolerance=1e-5):
    # type: (list[IKTarget], float) -> int
    """Count spatially distinct reachable targets within *tolerance*.

    This guards the behavioral proof against stale pose sources: if physics
    commands change but every sampled FK pose is identical, an IK solver can
    report zero error in one iteration without the robot moving.
    """
    distinct = []  # type: list[np.ndarray]
    for target in targets:
        if not target.is_reachable:
            continue
        position = np.asarray(target.position, dtype=np.float64).reshape(-1)
        if position.size != 3 or not np.isfinite(position).all():
            continue
        if not any(float(np.linalg.norm(position - known)) <= tolerance for known in distinct):
            distinct.append(position)
    return len(distinct)


def aggregate_jik_summary(per_target_results):
    # type: (list[dict[str, Any]]) -> dict[str, Any]
    """Roll up per-target results to phase-level metrics.

    Splits in-reach failures into two categories that match the target-
    sphere colors in the captured video:
    - solver_failed (red)  -- the IK solver could not find a joint solution.
    - motion_failed (orange/yellow) -- solver succeeded, but the PD drive
      did not track the precomputed solution to within tolerance.
    """
    in_reach_total = 0
    in_reach_passed = 0
    in_reach_solver_failed = 0
    in_reach_motion_failed = 0
    out_of_reach_total = 0
    out_of_reach_correct = 0
    out_of_reach_false_positive = 0
    max_pos_err = 0.0
    max_orient_err_deg = 0.0
    playback_position_errors = []
    failure_names = []  # type: list[str]

    for r in per_target_results:
        playback_error = r.get("playback_position_error_m")
        if playback_error is not None:
            playback_position_errors.append(float(playback_error))
        pos_err = float(r.get("pos_err", 0.0) or 0.0)
        orient_err = float(r.get("orient_err_deg", 0.0) or 0.0)
        if pos_err > max_pos_err:
            max_pos_err = pos_err
        if orient_err > max_orient_err_deg:
            max_orient_err_deg = orient_err

        if r.get("is_reachable"):
            in_reach_total += 1
            if r.get("passed"):
                in_reach_passed += 1
            else:
                if r.get("solver_success"):
                    in_reach_motion_failed += 1
                else:
                    in_reach_solver_failed += 1
                failure_names.append(str(r.get("name", "target_?")))
        else:
            out_of_reach_total += 1
            # OOR target: "pass" means the solver correctly flagged it as
            # unreachable. If the solver claimed reachable it is a false
            # positive (solver bug or asset reach overestimate).
            if r.get("passed"):
                out_of_reach_correct += 1
            elif r.get("solver_success"):
                out_of_reach_false_positive += 1

    return {
        "targets_total": len(per_target_results),
        "in_reach_total": in_reach_total,
        "in_reach_passed": in_reach_passed,
        "in_reach_failed": in_reach_solver_failed + in_reach_motion_failed,
        "in_reach_solver_failed": in_reach_solver_failed,
        "in_reach_motion_failed": in_reach_motion_failed,
        "out_of_reach_total": out_of_reach_total,
        "out_of_reach_correct": out_of_reach_correct,
        "out_of_reach_false_positive": out_of_reach_false_positive,
        "max_position_error_m": float(max_pos_err),
        "max_orientation_error_deg": float(max_orient_err_deg),
        "position_error_basis": "mixed_solver_or_live_playback_residual",
        "max_live_playback_position_error_m": max(playback_position_errors, default=None),
        "live_playback_targets_observed": len(playback_position_errors),
        "pass_rate": compute_pass_rate(in_reach_passed, in_reach_total),
        "failure_names": failure_names,
    }


def get_robot_base_position(robot, scene_info):
    # type: (Any, dict[str, Any]) -> np.ndarray
    """Return the robot's articulation root world position [x, y, z].

    Uses the ``robot_root_prim`` (or asset prim) recorded by the scene
    builder; falls back to origin when neither is valid. Lazy imports
    pxr so the helper stays import-clean outside Kit.
    """
    root_prim = scene_info.get("robot_root_prim") or scene_info.get("asset_prim")
    if root_prim is None:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)
    try:
        from pxr import Usd, UsdGeom

        if not root_prim.IsValid():
            return np.array([0.0, 0.0, 0.0], dtype=np.float64)
        xformable = UsdGeom.Xformable(root_prim)
        world_transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = world_transform.ExtractTranslation()
        return np.array(
            [
                float(translation[0]),
                float(translation[1]),
                float(translation[2]),
            ],
            dtype=np.float64,
        )
    except Exception:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)


def resolve_live_end_effector_link(robot, discovered_path):
    # type: (Any, str) -> Optional[str]
    """Resolve an authored EE marker to the nearest live physics-link path.

    Assets commonly place a marker such as ``wrist_3_link/flange`` beneath
    the terminal rigid body. Tensor views expose the rigid body, not arbitrary
    descendant Xforms, so walk upward until the pose accessor resolves one
    unambiguous live link.
    """
    getter = getattr(robot, "get_link_world_transforms", None)
    if not callable(getter):
        return None
    candidate = str(discovered_path).rstrip("/")
    while candidate and candidate != "/":
        transforms = getter([candidate])
        if transforms and candidate in transforms:
            return candidate
        if "/" not in candidate.lstrip("/"):
            break
        candidate = candidate.rsplit("/", 1)[0]
    return None


def estimate_robot_reach(asset_prim):
    # type: (Any) -> float
    """Estimate robot reach from the asset prim's world-aligned bbox.

    Uses the diagonal of the AABB as a coarse upper bound on reach; this
    matches v1's bbox-based reach estimate. Returns 0.5 m as a final
    fallback when the prim is unavailable or the bbox is degenerate.
    """
    if asset_prim is None:
        return 0.5
    try:
        bbox = compute_world_aligned_bbox(asset_prim, authored=True)
        dx = bbox.max_point[0] - bbox.min_point[0]
        dy = bbox.max_point[1] - bbox.min_point[1]
        dz = bbox.max_point[2] - bbox.min_point[2]
        diag = math.sqrt(max(0.0, dx) ** 2 + max(0.0, dy) ** 2 + max(0.0, dz) ** 2)
        if diag <= 1e-3:
            return 0.5
        # Reach is roughly half the diagonal (one arm extending from base).
        return float(diag * 0.5)
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------
# Solver wrapping
# ---------------------------------------------------------------------------


def _require_solver_result(result, expected_size, max_iterations):
    """Require explicit nonconvergence evidence, not a failed solver invocation."""
    try:
        if result is None or not isinstance(result.success, (bool, np.bool_)):
            raise ValueError("solver must return an explicit boolean success flag")
        iterations = result.iterations
        if (
            isinstance(iterations, (bool, np.bool_))
            or not isinstance(iterations, (int, np.integer))
            or not 0 <= iterations <= max_iterations
        ):
            raise ValueError("solver returned an invalid iteration count")
        _require_vector(result.converged_joints, "JIK", "solver joint solution", expected_size)
        _require_vector(result.final_position, "JIK", "solver final position", 3)
        orientation = _require_vector(result.final_orientation, "JIK", "solver final quaternion", 4)
        norm = float(np.linalg.norm(orientation))
        if not math.isfinite(norm) or norm <= 0.0:
            raise ValueError("solver returned an invalid final quaternion")
        for error in (result.final_pos_error, result.final_orient_error_deg):
            if (
                isinstance(error, (bool, np.bool_))
                or not isinstance(error, (int, float, np.integer, np.floating))
                or not math.isfinite(float(error))
                or error < 0.0
            ):
                raise ValueError("solver returned an invalid final error")
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError(
            "JIK runtime error: required solver result is malformed; target reachability was not evaluated"
        ) from exc
    return result


def _capture_home_orientation(solver):
    # type: (JacobianIKSolver) -> Optional[np.ndarray]
    """Return the home end-effector quaternion or None when unavailable."""
    try:
        _, quat = solver.get_ee_pose()
        return np.asarray(quat, dtype=np.float64)
    except RequiredReadbackError:
        raise
    except Exception:
        return None


async def _solve_target(
    ctx,
    solver,
    target,
    home_orientation,
    pos_tol,
    orient_tol_rad,
    max_iterations,
):
    # type: (Any, JacobianIKSolver, IKTarget, Optional[np.ndarray], float, float, int) -> JacobianIKResult
    """Run the DLS solver against a single target.

    The solver is async and steps physics after every tensor-view write so
    PhysX propagates the new joint state into the USD xform cache before
    the next pose read.

    A well-formed result with explicit ``success=False`` is nonconvergence.
    Solver exceptions and missing, malformed, or nonfinite required evidence
    raise RequiredReadbackError; they cannot establish target reachability.
    """
    # Prefer the target's own orientation (FK-sampled targets carry a provably
    # feasible EE orientation). Fall back to the home orientation, then identity.
    target_orient = getattr(target, "orientation", None)
    if target_orient is None:
        target_orient = home_orientation
    if target_orient is None:
        target_orient = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    try:
        result = await solver.solve(
            target_pos=np.asarray(target.position, dtype=np.float64),
            target_orient=target_orient,
            step_fn=ctx.step_one,
            max_iterations=max_iterations,
            pos_tol=pos_tol,
            orient_tol_rad=orient_tol_rad,
            heartbeat_fn=ctx.step,
        )
        return _require_solver_result(result, getattr(solver, "dof_count", None), max_iterations)
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError(
            f"JIK runtime error: required solver execution failed for target_{getattr(target, 'index', -1)}; "
            "target reachability was not evaluated"
        ) from exc


# ---------------------------------------------------------------------------
# Async runner (Kit-only)
# ---------------------------------------------------------------------------


async def _settle_and_snapshot(ctx, robot, settle_seconds, physics_fps):
    # type: (Any, Any, float, float) -> np.ndarray
    """Settle physics and snapshot the home joint configuration."""
    count = nominal_settle_steps(settle_seconds, physics_fps)
    ctx.step("JIK: initial nominal settle %.2fs (%d requested ticks)" % (settle_seconds, count))
    await settle_nominal(ctx, settle_seconds, physics_fps, phase="JIK")
    return _required_positions(robot, "JIK").copy()


async def _teleport_to_joints(ctx, robot, positions, settle_frames=3, excluded_indices=()):
    # type: (Any, Any, np.ndarray, int) -> None
    """Teleport joints to *positions* (zero velocities) and step a few frames."""
    from .required_readback import require_vector

    positions = require_vector(positions, "JIK", "probe configuration", len(robot.dof_names)).astype(np.float64)
    try:
        write_probe_state(robot, positions, excluded_indices)
    except Exception as exc:
        raise RequiredReadbackError("JIK runtime error: failed to establish the required probe configuration") from exc
    for _ in range(max(1, int(settle_frames))):
        try:
            await ctx.step_one()
        except RequiredReadbackError:
            raise
        except Exception as exc:
            raise RequiredReadbackError("JIK runtime error: required probe-state propagation failed") from exc


def _sampling_joint_indices(home_joints, lowers, uppers, locked, angular_indices=None):
    """Return DOFs with a qualified nonlocked excursion, not just a home pose."""
    from .joint_targets import bounded_joint_range

    angular_indices = set(angular_indices or ())
    eligible = set()
    for index, position in enumerate(home_joints):
        if index in locked:
            continue
        bounds = bounded_joint_range(
            lowers[index] if index < len(lowers) else float("nan"),
            uppers[index] if index < len(uppers) else float("nan"),
            position,
            angular=index in angular_indices,
        )
        if bounds is not None and bounds[1] - bounds[0] > 1.0e-3:
            eligible.add(index)
    return eligible


def _sample_joint_configs(home_joints, lowers, uppers, locked, count, seed=20260608, angular_indices=None):
    # type: (np.ndarray, Any, Any, set, int, int) -> list[np.ndarray]
    """Deterministically sample ``count`` in-limits joint configurations.

    Locked (closed-loop) DOFs are held at their home value -- they are governed
    by the loop constraint, not sampled. Finite-limit joints are sampled within
    a 15% margin off each limit. Only explicitly identified angular joints use
    local +/- pi bounds for SDK unlimited limits, retaining one-sided stops.
    Unbounded linear/unknown joints stay home. Deterministic for the same input.
    """
    from .joint_targets import bounded_joint_range

    rng = np.random.default_rng(seed)
    angular_indices = set(angular_indices or ())
    n = len(home_joints)
    configs = []  # type: list[np.ndarray]
    # Bound each joint's deviation from home to SPREAD * range and stay 15% off
    # the limits. This bounds the selected FK sample window; it does not
    # guarantee conditioning, representative workspace coverage or later
    # solver/playback success from a different starting configuration.
    SPREAD = 0.35
    for _ in range(count):
        q = np.array(home_joints, dtype=np.float64).copy()
        for i in range(n):
            if i in locked:
                continue
            lo = float(lowers[i]) if i < len(lowers) else float("-inf")
            hi = float(uppers[i]) if i < len(uppers) else float("inf")
            bounds = bounded_joint_range(lo, hi, home_joints[i], angular=i in angular_indices)
            if bounds is not None and (bounds[1] - bounds[0]) > 1e-3:
                safe_lo, safe_hi = bounds
                span = safe_hi - safe_lo
                margin = 0.15 * span
                offset = float(rng.uniform(-SPREAD, SPREAD)) * span
                q[i] = float(np.clip(home_joints[i] + offset, safe_lo + margin, safe_hi - margin))
        configs.append(q)
    return configs


async def _generate_fk_targets(
    ctx,
    robot,
    solver,
    home_joints,
    base_pos,
    lowers,
    uppers,
    locked,
    num_reachable,
    num_out_of_reach,
    settle_frames=4,
    angular_indices=None,
):
    """Generate FK targets and restore home even when a probe fails or is cancelled."""
    primary_error = None
    try:
        return await _generate_fk_targets_impl(
            ctx,
            robot,
            solver,
            home_joints,
            base_pos,
            lowers,
            uppers,
            locked,
            num_reachable,
            num_out_of_reach,
            settle_frames,
            angular_indices,
        )
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            await _teleport_to_joints(ctx, robot, home_joints, settle_frames, excluded_indices=locked)
        except BaseException as restore_error:
            if primary_error is None:
                raise
            note_secondary_error(
                primary_error,
                lambda restore_error=restore_error: "JIK home restoration also failed: %s" % restore_error,
            )


async def _generate_fk_targets_impl(
    ctx,
    robot,
    solver,
    home_joints,
    base_pos,
    lowers,
    uppers,
    locked,
    num_reachable,
    num_out_of_reach,
    settle_frames,
    angular_indices,
):
    # type: (Any, Any, JacobianIKSolver, np.ndarray, np.ndarray, Any, Any, set, int, int, int) -> tuple[list[IKTarget], float]
    """Generate IK targets by forward kinematics from sampled joint configs.

    In-reach labels identify live EE poses observed after sampled joint probes,
    including their observed orientations. They do not guarantee controllability,
    convergence from another seed or successful dynamic playback.

    Additional diagnostic targets lie beyond the largest sampled base-to-EE
    distance and use the home orientation. Their radial label is a sampling
    heuristic, not proof that the complete robot workspace cannot reach them.

    Returns ``(targets, max_observed_reach)``.
    """
    targets = []  # type: list[IKTarget]
    max_dist = 0.0

    # Capture the home EE orientation for the out-of-reach targets.
    await _teleport_to_joints(ctx, robot, home_joints, settle_frames, excluded_indices=locked)
    home_quat = None  # type: Optional[np.ndarray]
    try:
        _, home_quat = solver.get_ee_pose()
    except RequiredReadbackError:
        raise
    except Exception:
        home_quat = None

    configs = _sample_joint_configs(
        home_joints, lowers, uppers, set(locked), num_reachable, angular_indices=angular_indices
    )
    idx = 0
    for q in configs:
        await _teleport_to_joints(ctx, robot, q, settle_frames, excluded_indices=locked)
        try:
            pos, quat = solver.get_ee_pose()
        except RequiredReadbackError:
            raise
        except Exception:
            continue
        dist = float(np.linalg.norm(np.asarray(pos, dtype=np.float64) - np.asarray(base_pos, dtype=np.float64)))
        max_dist = max(max_dist, dist)
        targets.append(
            IKTarget(
                position=np.asarray(pos, dtype=np.float64),
                is_reachable=True,
                index=idx,
                orientation=np.asarray(quat, dtype=np.float64),
            )
        )
        idx += 1
        ctx.step("JIK: FK target %d/%d sampled (EE dist %.3f)" % (idx, num_reachable, dist))

    # Out-of-reach targets: beyond the farthest observed reach, home orientation.
    if num_out_of_reach > 0 and max_dist > 1e-3:
        rng = np.random.default_rng(20260609)
        for _ in range(num_out_of_reach):
            v = np.asarray(rng.normal(size=3), dtype=np.float64)
            nrm = float(np.linalg.norm(v))
            if nrm < 1e-6:
                v = np.array([1.0, 0.0, 0.0], dtype=np.float64)
                nrm = 1.0
            v = v / nrm
            v[2] = abs(v[2])  # upper hemisphere
            oor = np.asarray(base_pos, dtype=np.float64) + v * max_dist * 1.4
            targets.append(
                IKTarget(
                    position=oor,
                    is_reachable=False,
                    index=idx,
                    orientation=home_quat,
                )
            )
            idx += 1

    return targets, max_dist


async def _precompute_solutions(
    ctx,
    robot,
    solver,
    targets,
    home_joints,
    home_orientation,
    pos_tol,
    orient_tol_rad,
    max_iterations,
):
    try:
        return await _precompute_solutions_impl(
            ctx, robot, solver, targets, home_joints, home_orientation, pos_tol, orient_tol_rad, max_iterations
        )
    except BaseException as primary:
        # Restore control state without introducing new ticks during failure or
        # cancellation, and retain the original solver/runtime exception.
        try:
            positions = _require_vector(home_joints, "JIK", "home configuration", len(robot.dof_names))
            write_probe_state(robot, positions, getattr(solver, "_locked", ()))
        except BaseException as secondary:
            note_secondary_error(
                primary, lambda secondary=secondary: f"JIK home restoration also failed: {secondary!r}"
            )
        raise


def _record_seed_attempts(ctx, records, omitted):
    """Optional bounded diagnostics must not change a valid solver verdict."""
    try:
        ctx.add_metric("jik_seed_attempts", list(records))
        ctx.add_metric("jik_seed_attempts_omitted", omitted)
    except UnsafeEvidencePathError:
        raise
    except Exception:
        try:
            ctx.warn("JIK seed-attempt diagnostics unavailable; solver result unchanged.")
        except UnsafeEvidencePathError:
            raise
        except Exception:
            pass


async def _solve_seeded_target(
    ctx, robot, solver, target, home_joints, previous_joints, home_orientation, pos_tol, orient_tol_rad, max_iterations
):
    """Bounded deterministic restarts of one unchanged target, never an FK answer."""
    excluded = set(getattr(solver, "_locked", ()))
    independent = [i for i in range(len(home_joints)) if i not in excluded]
    candidates = [
        ("previous_success", previous_joints.copy()),
        ("current", _required_positions(robot, "JIK").copy()),
        ("home", home_joints.copy()),
    ]
    seen, attempts = set(), []
    best_result = None
    best_seed_added = False
    total_iterations = 0
    while candidates and len(attempts) < 4:
        seed_name, seed = candidates.pop(0)
        seed = _require_vector(seed, "JIK", "solver seed", len(home_joints)).astype(np.float64).copy()
        key = tuple(float(seed[i]) for i in independent)
        if key in seen:
            continue
        seen.add(key)
        await _teleport_to_joints(ctx, robot, seed, excluded_indices=excluded)
        ctx.step("JIK target_%d seed=%s attempt=%d/4" % (target.index, seed_name, len(attempts) + 1))
        search = getattr(ctx, "_jik_search_budget", None)
        if search is not None:
            search.begin_solver()
        result = await _solve_target(ctx, solver, target, home_orientation, pos_tol, orient_tol_rad, max_iterations)
        if search is not None:
            search.finish_solver(result)
        total_iterations += int(result.iterations)
        attempts.append(
            {
                "seed": seed_name,
                "seed_indices": independent[:64],
                "seed_positions": [float(seed[i]) for i in independent[:64]],
                "seed_coordinates_omitted": max(0, len(independent) - 64),
                "solver_success": bool(result.success),
                "iterations": int(result.iterations),
                "position_error_m": float(result.final_pos_error),
                "orientation_error_deg": float(result.final_orient_error_deg),
            }
        )
        if (
            best_result is None
            or bool(result.success)
            or (result.final_pos_error, result.final_orient_error_deg)
            < (best_result.final_pos_error, best_result.final_orient_error_deg)
        ):
            best_result = result
        if result.success:
            break
        if not best_seed_added:
            # Try the first finite failed solver configuration, after the
            # existing current-state candidate and before the independent home
            # seed. Add it once so home cannot be starved by unlimited restarts.
            candidates.insert(max(0, len(candidates) - 1), ("best_failed", result.converged_joints.copy()))
            best_seed_added = True
    return best_result, attempts, total_iterations


async def _precompute_solutions_impl(
    ctx,
    robot,
    solver,
    targets,
    home_joints,
    home_orientation,
    pos_tol,
    orient_tol_rad,
    max_iterations,
):
    # type: (Any, Any, JacobianIKSolver, list[IKTarget], np.ndarray, Optional[np.ndarray], float, float, int) -> list[dict[str, Any]]
    """Solve every target up front; return per-target solution records.

    Each record carries ``target``, ``solution`` (joints or None),
    ``solver_success`` (the raw solver flag), ``iterations``,
    ``pos_err``, and ``orient_err_deg`` so the motion phase can dispatch
    without running the solver again.
    """
    # Heartbeat per target -- every solve can take seconds. The configured
    # session-inactivity watchdog detects prolonged stdout silence.
    # Emit a ctx.step before each solve so the watchdog sees
    # progress even if a single target takes a long time to converge.
    solutions = []  # type: list[dict[str, Any]]
    current_start = home_joints.copy()
    total_iterations = 0
    seed_records = []
    for i, target in enumerate(targets):
        target_name = "target_%d" % target.index
        ctx.step("JIK precompute %d/%d: %s reachable=%s" % (i + 1, len(targets), target_name, target.is_reachable))
        result, attempts, target_iterations = await _solve_seeded_target(
            ctx,
            robot,
            solver,
            target,
            home_joints,
            current_start,
            home_orientation,
            pos_tol,
            orient_tol_rad,
            max_iterations,
        )
        total_iterations += target_iterations
        if i < 64:
            seed_records.append({"target_index": int(target.index), "attempts": attempts})
        _record_seed_attempts(ctx, seed_records, max(0, i + 1 - len(seed_records)))
        solver_success = bool(result.success)
        solution_joints = (
            _require_vector(result.converged_joints, "JIK", "solver joint solution", len(home_joints))
            .astype(np.float64)
            .copy()
        )
        if solver_success:
            current_start = solution_joints.copy()
        solutions.append(
            {
                "target": target,
                "solution": solution_joints,
                "solver_success": solver_success,
                "iterations": int(result.iterations),
                "pos_err": float(result.final_pos_error),
                "orient_err_deg": float(result.final_orient_error_deg),
            }
        )
    # Restore the home configuration before motion playback begins.
    await _teleport_to_joints(ctx, robot, home_joints, excluded_indices=getattr(solver, "_locked", ()))
    ctx.add_metric("jik_total_iterations", total_iterations)
    return solutions


def _playback_frames(start, target, velocity_hints, excluded, config, minimum_seconds):
    """Schedule complete independent playback, never shorten it to fit a budget."""
    count = len(start)
    start = _require_vector(start, "JIK", "playback start", count)
    target = _require_vector(target, "JIK", "playback target", count)
    if len(velocity_hints) != count:
        raise ValueError("JIK velocity hint dimension does not match required positions")
    excluded = validate_indices(excluded or (), count)
    fps = _finite(config.get("physics_fps", 240.0), "physics_fps", positive=True, phase="JIK")
    minimum = _finite(minimum_seconds, "interpolation_seconds", positive=True, phase="JIK")
    ticks = minimum * fps
    if not math.isfinite(ticks):
        raise ValueError("JIK interpolation tick budget must be finite")
    fallback = max(1, math.ceil(ticks))
    # Validate the fallback and policy even when every coordinate is held.
    frames = segment_frames(0.0, 0.0, 0.0, None, config, fallback, phase="JIK")
    for index in range(count):
        if index not in excluded:
            frames = max(
                frames,
                segment_frames(
                    start[index],
                    target[index],
                    start[index],
                    velocity_hints[index][0],
                    config,
                    fallback,
                    phase="JIK",
                ),
            )
    return frames


def _optional_playback(operation, *args, primary=None, **kwargs):
    """Ordinary presentation failures are optional; cancellation and safety are required."""
    try:
        return operation(*args, **kwargs)
    except BaseException as error:
        if primary is None and (not isinstance(error, Exception) or isinstance(error, UnsafeEvidencePathError)):
            raise
        if primary is not None:
            note_secondary_error(primary, lambda error=error: f"JIK optional delivery also failed: {error!r}")
        return None


async def _optional_playback_capture(ctx, **kwargs):
    # Capture crosses engine and evidence-path validation. Its producer's None
    # is recoverable; unknown exceptions must keep their required classification.
    return await ctx.capture_frame(**kwargs)


def _publish_playback_evidence(ctx, records, interrupted_index=None, primary=None):
    fields = [("jik_per_target", list(records))]
    if interrupted_index is not None:
        fields.extend(
            (("jik_playback_completion", "incomplete"), ("jik_interrupted_target_index", int(interrupted_index)))
        )
    for name, value in fields:
        try:
            ctx.add_metric(name, value)
        except BaseException as error:
            if primary is None and (not isinstance(error, Exception) or isinstance(error, UnsafeEvidencePathError)):
                raise
            if primary is not None:
                try:
                    primary.add_note(f"JIK evidence publication unavailable for {name}: {error}")
                except BaseException:
                    pass


async def _interpolate_to_solution(
    ctx,
    robot,
    scene_info,
    start_joints,
    target_joints,
    interp_seconds,
    physics_fps,
    capture_interval,
    capture_frames,
    capture_label,
    profile,
    baseline_bbox,
    bbox_ratio_limit,
    target_name,
    locked_indices=None,
    motion_observers=None,
    motion_clock=None,
    motion_frames=None,
):
    # type: (Any, Any, dict[str, Any], np.ndarray, np.ndarray, float, float, int, list[str], str, str, Optional[BBoxSnapshot], float, str, Any) -> list[str]
    """Smoothstep-interpolate joint targets and step physics frame-by-frame.

    Returns a list of bbox-explode error strings (empty when none).
    Captures into ``capture_frames`` at ``capture_interval`` cadence.
    """
    HB_EVERY = 40
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    bbox_errors = []  # type: list[str]

    if motion_frames is None:
        motion_frames = max(1, math.ceil(interp_seconds * physics_fps))
    delta = np.array(target_joints, dtype=np.float64) - np.array(start_joints, dtype=np.float64)
    # Constraint/passive-owned DOFs are not independently PD-driven. Their
    # entries remain observation context only; sparse dispatch omits them.
    locked = validate_indices(locked_indices or (), len(robot.dof_names))
    for li in locked:
        if li < len(delta):
            delta[li] = 0.0
    for frame in range(motion_frames):
        t = (frame + 1) / float(motion_frames)
        eased = interpolate_profile(profile, t)
        command = np.array(start_joints, dtype=np.float64) + delta * eased
        if locked:
            live = np.asarray(_required_positions(robot, "JIK"), dtype=np.float64)
            for li in locked:
                if li < len(command) and li < len(live):
                    command[li] = live[li]
        command_targets(robot, command, locked)
        await ctx.step_one()
        if motion_clock is not None:
            motion_clock["steps"] += 1
            _optional_playback(
                sample_joint_motion,
                robot,
                motion_observers or {},
                command,
                motion_clock["steps"] / physics_fps,
                "interpolation",
                locked,
            )

        if frame % 20 == 0 and baseline_bbox is not None:
            current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
            msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
            if msg:
                bbox_errors.append("JIK: %s: %s" % (target_name, msg))

        if frame % capture_interval == 0:
            fp = await _optional_playback_capture(
                ctx,
                label="%s_%04d" % (capture_label, frame),
                stabilize_frames=0,
            )
            if fp:
                capture_frames.append(fp)
                _optional_playback(record_joint_captures, motion_observers or {}, fp)
            _optional_playback(ctx.scene.update_camera_follow, update_history=True)
        else:
            _optional_playback(ctx.scene.update_camera_follow, update_history=False)

        if frame % HB_EVERY == 0:
            live = np.asarray(_required_positions(robot, "JIK"), dtype=np.float64)
            comparable = [i for i in range(min(len(command), len(live))) if i not in locked]
            max_joint_err = float(np.max(np.abs(command[comparable] - live[comparable]))) if comparable else 0.0
            ctx.step(
                "JIK %s frame=%d/%d eased=%.3f max_joint_err_rad=%.4f target_range=[%.3f,%.3f] live_range=[%.3f,%.3f]"
                % (
                    target_name,
                    frame,
                    motion_frames,
                    eased,
                    max_joint_err,
                    float(np.min(command)) if command.size else 0.0,
                    float(np.max(command)) if command.size else 0.0,
                    float(np.min(live)) if live.size else 0.0,
                    float(np.max(live)) if live.size else 0.0,
                )
            )
    return bbox_errors


async def _hold_after_reach(
    ctx,
    robot,
    final_joints,
    hold_seconds,
    physics_fps,
    capture_interval,
    capture_frames,
    capture_label,
    locked_indices=None,
    motion_observers=None,
    motion_clock=None,
):
    # type: (Any, Any, np.ndarray, float, float, int, list[str], str, Any) -> None
    """Hold at the reached pose to stabilize captured frames."""
    HB_EVERY = 40
    hold_frames = max(1, int(hold_seconds * physics_fps))
    locked = validate_indices(locked_indices or (), len(robot.dof_names))
    base_cmd = None
    if final_joints is not None:
        base_cmd = np.array(final_joints, dtype=np.float64)
        command_targets(robot, base_cmd, locked)
    for frame in range(hold_frames):
        # Refresh observation context only; sparse dispatch never commands
        # the passive/mimic/loop-owned DOFs, including the first hold write.
        if base_cmd is not None and locked:
            live = np.asarray(_required_positions(robot, "JIK"), dtype=np.float64)
            for li in locked:
                if li < len(base_cmd) and li < len(live):
                    base_cmd[li] = live[li]
            command_targets(robot, base_cmd, locked)
        await ctx.step_one()
        if motion_clock is not None:
            motion_clock["steps"] += 1
            _optional_playback(
                sample_joint_motion,
                robot,
                motion_observers or {},
                base_cmd,
                motion_clock["steps"] / physics_fps,
                "hold",
                locked,
            )
        if frame % capture_interval == 0:
            fp = await _optional_playback_capture(
                ctx,
                label="%s_hold_%04d" % (capture_label, frame),
                stabilize_frames=0,
            )
            if fp:
                capture_frames.append(fp)
                _optional_playback(record_joint_captures, motion_observers or {}, fp)
            _optional_playback(ctx.scene.update_camera_follow, update_history=True)
        else:
            _optional_playback(ctx.scene.update_camera_follow, update_history=False)
        if frame % HB_EVERY == 0:
            ctx.step("JIK hold %s frame=%d/%d" % (capture_label, frame, hold_frames))


def _evaluate_target(solver, target, pos_tol, orient_tol_deg):
    # type: (JacobianIKSolver, IKTarget, float, float) -> tuple[float, float]
    """Read the EE pose and compute (pos_err_m, orient_err_deg) vs the target.

    An unavailable required EE pose raises an execution error with its cause.
    """
    try:
        ee_pos, _ = solver.get_ee_pose()
    except RequiredReadbackError:
        raise
    except Exception as error:
        raise RequiredReadbackError("JIK final end-effector readback failed") from error
    pos_err = float(np.linalg.norm(np.asarray(ee_pos, dtype=np.float64) - target.position))
    # Orientation error tracking is optional in v2; the solver records
    # orient_err_deg in JacobianIKResult. The motion-phase value is
    # informational only -- the gate uses solver-recorded errors.
    return pos_err, 0.0


async def _run_motion_for_solutions(
    ctx,
    robot,
    solver,
    scene_info,
    solutions,
    home_joints,
    cfg,
    capture_frames,
    capture_interval,
    baseline_bbox,
    target_sphere_prims=None,
    locked_indices=None,
):
    # type: (Any, Any, JacobianIKSolver, dict[str, Any], list[dict[str, Any]], np.ndarray, dict[str, Any], list[str], int, Optional[BBoxSnapshot], Optional[list[Any]]) -> list[dict[str, Any]]
    """Drive motion to each precomputed solution; return per-target results.

    Per-target sphere color reflects the final outcome:
    - Green: in-reach target, robot reached it within tolerance.
    - Red: solver failed (no joint solution found).
    - Orange: solver succeeded but motion did not converge to within tolerance.
    - Magenta: out-of-reach target, solver correctly failed.
    """
    pos_tol = float(cfg["position_tolerance"])
    orient_tol_deg = float(cfg["orientation_tolerance_deg"])
    interp_seconds, hold_seconds = resolve_motion_timing(cfg)
    physics_fps = float(cfg["physics_fps"])
    profile = str(cfg["interpolation_profile"])
    bbox_ratio_limit = float(cfg["bbox_explode_ratio"])

    per_target_results = []  # type: list[dict[str, Any]]
    for solution in solutions:
        target = solution["target"]
        motion_observers = {}
        try:
            target_name = "target_%d" % target.index
            ctx.step("JIK motion for %s reachable=%s" % (target_name, target.is_reachable))

            # Each segment starts FROM the previous target's final pose (NOT
            # home). v1.6 chains the motion target-to-target so the robot
            # sweeps through the target field instead of darting back to
            # home between every reach. This also halves the cumulative
            # motion distance and keeps the captured video continuous.

            solver_success = bool(solution["solver_success"])
            solver_pos_err = float(solution["pos_err"])
            solver_orient_err_deg = float(solution["orient_err_deg"])
            target_joints = solution["solution"]
            bbox_errors = []  # type: list[str]
            actual_pos_err = float("inf")
            scheduled_frames = None

            if target_joints is not None and solver_success:
                start_joints = _required_positions(robot, "JIK").copy()
                velocity_hints = resolve_velocity_hints(robot, scene_info)
                scheduled_frames = _playback_frames(
                    start_joints,
                    target_joints,
                    velocity_hints,
                    locked_indices,
                    cfg,
                    interp_seconds,
                )
                motion_observers = {
                    index: _optional_playback(
                        make_joint_observer,
                        ctx,
                        scene_info,
                        str(joint_name),
                        "jik_target_%03d_joint_%03d" % (int(target.index), index),
                        (
                            {
                                "position": {
                                    "unit": "{joint}",
                                    "source": "RobotHandle articulation position readback",
                                },
                                "target": {
                                    "unit": "{joint}",
                                    "source": "position command issued by test",
                                },
                                "error": {
                                    "unit": "{joint}",
                                    "source": "command minus measured position",
                                },
                            }
                            if index not in set(locked_indices or ())
                            else {
                                "position": {
                                    "unit": "{joint}",
                                    "source": "constraint/passive-owned articulation readback",
                                }
                            }
                        ),
                        metadata={
                            "target_index": int(target.index),
                            "target_reachable": bool(target.is_reachable),
                            "physics_fps": physics_fps,
                            "encoded_video_fps": cfg.get("capture_fps"),
                            "capture_interval_steps": capture_interval,
                            "locked_dof": index in set(locked_indices or ()),
                            "commanded_independently": index not in set(locked_indices or ()),
                            "observation_basis": "target-local nominal steps during interpolation and hold only; FK sampling, solver perturbations and rendering ticks excluded",
                            "verdict_basis": "existing final live end-effector position error and solver orientation error; joint plots alone do not establish those tolerances",
                            "end_effector_position_tolerance_m": pos_tol,
                        },
                    )
                    for index, joint_name in enumerate(
                        getattr(robot, "dof_names", ()) if callable(getattr(ctx, "begin_motion_history", None)) else ()
                    )
                }
                motion_clock = {"steps": 0}
                bbox_errors = await _interpolate_to_solution(
                    ctx=ctx,
                    robot=robot,
                    scene_info=scene_info,
                    start_joints=start_joints,
                    target_joints=target_joints,
                    interp_seconds=scheduled_frames / physics_fps,
                    motion_frames=scheduled_frames,
                    physics_fps=physics_fps,
                    capture_interval=capture_interval,
                    capture_frames=capture_frames,
                    capture_label="jacobian_ik_%s" % target_name,
                    profile=profile,
                    baseline_bbox=baseline_bbox,
                    bbox_ratio_limit=bbox_ratio_limit,
                    target_name=target_name,
                    locked_indices=locked_indices,
                    motion_observers=motion_observers,
                    motion_clock=motion_clock,
                )
                await _hold_after_reach(
                    ctx=ctx,
                    robot=robot,
                    final_joints=target_joints,
                    hold_seconds=hold_seconds,
                    physics_fps=physics_fps,
                    capture_interval=capture_interval,
                    capture_frames=capture_frames,
                    capture_label="jacobian_ik_%s" % target_name,
                    locked_indices=locked_indices,
                    motion_observers=motion_observers,
                    motion_clock=motion_clock,
                )
                actual_pos_err, _ = _evaluate_target(solver, target, pos_tol, orient_tol_deg)
                _optional_playback(finish_joint_observers, motion_observers, "target_playback_and_hold_completed")

            if target.is_reachable:
                # Pass = solver succeeded AND end pose is within tolerance.
                motion_within_tol = actual_pos_err <= pos_tol and solver_orient_err_deg <= orient_tol_deg
                passed = bool(solver_success and motion_within_tol)
            else:
                # Out-of-reach target: solver SHOULD fail. We mirror v1.
                passed = not solver_success
                motion_within_tol = False

            # Update target sphere color to reflect the outcome. One color per
            # outcome so the video legend matches the metric breakdown 1:1.
            if target_sphere_prims is not None and target.index < len(target_sphere_prims):
                sphere_prim = target_sphere_prims[target.index]
                if sphere_prim is not None:
                    if target.is_reachable and passed:
                        _optional_playback(set_target_sphere_color, sphere_prim, COLOR_TARGET_REACHED)
                    elif target.is_reachable and not solver_success:
                        _optional_playback(set_target_sphere_color, sphere_prim, COLOR_TARGET_SOLVE_FAILED)
                    elif target.is_reachable:
                        _optional_playback(set_target_sphere_color, sphere_prim, COLOR_TARGET_MOTION_FAILED)
                    elif not target.is_reachable and passed:
                        _optional_playback(set_target_sphere_color, sphere_prim, COLOR_TARGET_OUT_OF_REACH_OK)
                    else:
                        # OOR target but solver claimed reachable -- false positive.
                        _optional_playback(set_target_sphere_color, sphere_prim, COLOR_TARGET_OOR_FALSE_POSITIVE)

            # Keep legacy mixed-stage fields, but identify actual live playback
            # separately. A rejected/unplayed target has no measured playback error.
            record = {
                "index": target.index,
                "name": target_name,
                "is_reachable": bool(target.is_reachable),
                "passed": bool(passed),
                "solver_success": bool(solver_success),
                "solver_position_error_m": solver_pos_err,
                "playback_position_error_m": float(actual_pos_err) if math.isfinite(actual_pos_err) else None,
                "orientation_error_basis": "solver_pose_not_live_playback",
                "pos_err": float(actual_pos_err if math.isfinite(actual_pos_err) else solver_pos_err),
                "orient_err_deg": float(solver_orient_err_deg),
                "iterations": int(solution["iterations"]),
                "scheduled_interpolation_frames": scheduled_frames,
                "scheduled_interpolation_seconds": (
                    scheduled_frames / physics_fps if scheduled_frames is not None else None
                ),
                "interpolation_time_basis": "scheduled nominal physics ticks, not measured simulation or wall time",
            }
            per_target_results.append(record)
            _publish_playback_evidence(ctx, per_target_results)

            if bbox_errors:
                for msg in bbox_errors:
                    _optional_playback(ctx.warn, msg)
            if not passed and target.is_reachable:
                _optional_playback(
                    ctx.warn,
                    "JIK: %s failed (pos_err=%.4f m, orient_err=%.2f deg, iters=%d)"
                    % (
                        target_name,
                        record["pos_err"],
                        record["orient_err_deg"],
                        record["iterations"],
                    ),
                )
            elif passed and target.is_reachable:
                _optional_playback(
                    ctx.log,
                    "JIK: %s reached (pos_err=%.4f m, iters=%d)"
                    % (target_name, record["pos_err"], record["iterations"]),
                )
            elif not target.is_reachable and passed:
                _optional_playback(
                    ctx.log,
                    "JIK: %s out-of-reach correctly rejected (pos_err=%.4f m)" % (target_name, record["pos_err"]),
                )
        except BaseException as error:
            _publish_playback_evidence(ctx, per_target_results, target.index, error)
            _optional_playback(finish_joint_observers, motion_observers, "target_playback_interrupted", primary=error)
            raise
    return per_target_results


def _record_phase_metrics(ctx, summary, ee_link_path):
    # type: (Any, dict[str, Any], str) -> None
    """Write the metric set used by report.html.

    The first three metrics give the at-a-glance "generated vs reached"
    summary the user wants in the report:
    - jik_targets_generated: total targets created (in-reach + out-of-reach).
    - jik_targets_reached: in-reach targets the robot successfully reached.
    - jik_targets_total_passed: total passing targets including out-of-reach
      that correctly failed (the headline pass count).
    """
    targets_total = int(summary["targets_total"])
    in_reach_total = int(summary["in_reach_total"])
    in_reach_passed = int(summary["in_reach_passed"])
    in_reach_solver_failed = int(summary["in_reach_solver_failed"])
    in_reach_motion_failed = int(summary["in_reach_motion_failed"])
    out_of_reach_total = int(summary["out_of_reach_total"])
    out_of_reach_correct = int(summary["out_of_reach_correct"])
    out_of_reach_false_positive = int(summary["out_of_reach_false_positive"])

    # Headline metrics.
    _optional_playback(ctx.add_metric, "jik_targets_generated", targets_total)
    _optional_playback(ctx.add_metric, "jik_targets_reached", in_reach_passed)
    _optional_playback(ctx.add_metric, "jik_targets_total_passed", in_reach_passed + out_of_reach_correct)

    # Reach-class totals.
    _optional_playback(ctx.add_metric, "jik_targets_in_reach", in_reach_total)
    _optional_playback(ctx.add_metric, "jik_targets_out_of_reach", out_of_reach_total)
    _optional_playback(ctx.add_metric, "jik_in_reach_failed", summary["in_reach_failed"])

    # Per-outcome counts. The COLOR is embedded in the metric name so the
    # report row reads "what happened + what color" in one line, and the
    # alphabetic sort groups in-reach-* and out-of-reach-* together.
    _optional_playback(ctx.add_metric, "jik_in_reach_passed_green", in_reach_passed)
    _optional_playback(ctx.add_metric, "jik_in_reach_solver_failed_red", in_reach_solver_failed)
    _optional_playback(ctx.add_metric, "jik_in_reach_motion_failed_orange", in_reach_motion_failed)
    _optional_playback(ctx.add_metric, "jik_out_of_reach_correctly_failed_magenta", out_of_reach_correct)
    _optional_playback(ctx.add_metric, "jik_out_of_reach_false_positive_yellow", out_of_reach_false_positive)

    _optional_playback(
        ctx.add_metric,
        "jik_max_position_error_m",
        round(summary["max_position_error_m"], 6),
    )
    _optional_playback(
        ctx.add_metric,
        "jik_max_orientation_error_deg",
        round(summary["max_orientation_error_deg"], 4),
    )
    _optional_playback(ctx.add_metric, "jik_pass_rate", round(summary["pass_rate"], 4))
    _optional_playback(ctx.add_metric, "jik_position_error_basis", summary["position_error_basis"])
    playback_error = summary["max_live_playback_position_error_m"]
    _optional_playback(
        ctx.add_metric,
        "jik_max_live_playback_position_error_m",
        round(playback_error, 6) if playback_error is not None else None,
    )
    _optional_playback(ctx.add_metric, "jik_live_playback_targets_observed", summary["live_playback_targets_observed"])
    _optional_playback(ctx.add_metric, "jik_ee_link", ee_link_path)


async def run_jacobian_ik(ctx, robot, scene_info, config):
    """Run with a fixed search allowance and retain optional timing on every exit."""
    validate_phase_config(config, "jacobian_ik")
    search = _JIKSearchContext(ctx, validate_search_budget(config))
    primary = None
    try:
        await _run_jacobian_ik_impl(search, robot, scene_info, config)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        search.finish("execution_error" if primary is not None else "phase_stopped_before_playback")
        _record_search_timing(ctx, search, primary)


async def _run_jacobian_ik_impl(ctx, robot, scene_info, config):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    """Run the JIK phase. Mutates ctx via skip / add_metric / warn / fail."""
    validate_phase_config(config, "jacobian_ik")
    settling_config = config or {}
    defaults = get_defaults()
    nominal_settle_steps(
        settling_config.get("settle_seconds", defaults["settle_seconds"]),
        settling_config.get("physics_fps", defaults["physics_fps"]),
    )
    if is_standalone_gripper(robot, scene_info, getattr(ctx, "asset_validated_features", None)):
        reason = (
            "JIK is not applicable to standalone grippers: their articulation "
            "DOFs open and close the fingers but do not provide an arm-like "
            "Cartesian workspace for inverse kinematics."
        )
        if _has_current_coordinate_exclusions(robot, scene_info, ctx=ctx):
            ctx.add_metric("assessment_applicability", not_applicable("standalone_gripper", reason))
        ctx.skip(reason)
        return

    # ---- Resolve config ------------------------------------------------
    cfg = dict(get_defaults())
    if config:
        cfg.update(config)

    settle_seconds = float(cfg["settle_seconds"])
    num_targets = int(cfg["num_targets"])
    out_of_reach_count = int(cfg["out_of_reach_count"])
    # Accept either a tuple of factors (v1.6 multi-shell pattern) or a
    # single float (legacy callers / overrides).
    rf_cfg = cfg.get("target_radius_factors") or cfg.get("target_radius_factor")
    if isinstance(rf_cfg, (int, float)):
        target_radius_factors = (float(rf_cfg),)
    elif isinstance(rf_cfg, (list, tuple)) and rf_cfg:
        target_radius_factors = tuple(float(f) for f in rf_cfg)
    else:
        target_radius_factors = (0.5, 0.7, 0.9)
    # out_of_reach_factor is an inert compatibility key. FK-generated
    # radial probes retain their existing 1.4-times-sampled-reach heuristic.
    pos_tol = float(cfg["position_tolerance"])
    orient_tol_deg = float(cfg["orientation_tolerance_deg"])
    orient_tol_rad = math.radians(orient_tol_deg)
    max_solver_iterations = int(cfg["max_solver_iterations"])
    damping_lambda = float(cfg["damping_lambda"])
    physics_fps = float(cfg["physics_fps"])
    capture_fps = int(cfg["capture_fps"])
    min_pass_rate = float(cfg["min_pass_rate"])
    # hemisphere_only is an inert compatibility key: FK radial probes retain
    # their existing upper-hemisphere placement regardless of its value.
    finite_difference_epsilon = float(cfg["finite_difference_epsilon"])
    jacobian_propagation_steps = int(cfg["jacobian_propagation_steps"])

    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))

    # ---- Discover end-effector ----------------------------------------
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    if stage is None:
        # scene_info["stage"] is wired by the runner; missing it is a
        # framework setup bug, not an asset-authoring issue. Tag clearly so
        # the asset author does not chase a phantom asset fix.
        raise RuntimeError(
            "INTERNAL: JIK scene_info has no USD stage -- runner did not "
            "populate scene_info['stage'] before invoking the phase. This "
            "is a framework bug; the asset under test is not at fault. "
            "File against the core tier's articulation runtime-test implementation (runner / "
            "scene builder) with the asset path and the runner log."
        )
        return

    # v1.6 parity: pass the ASSET root prim (e.g. /World/AssetRoot/Asset),
    # NOT the articulation root (e.g. /robot/Geometry/world). Many robots
    # (Fanuc CR/CRX) author the articulation root in a sibling scope to the
    # link prims; walking under the articulation root finds zero links.
    asset_prim = scene_info.get("asset_prim")
    if asset_prim is not None and asset_prim.IsValid():
        search_root = str(asset_prim.GetPath())
    else:
        search_root = robot.prim_path
    ctx.step("JIK: discovering end-effector under %s" % search_root)
    ee_link_path = discover_end_effector_link(
        stage=stage, robot=robot, robot_root_path=search_root, explicit_path=cfg.get("ee_link_path")
    )
    if ee_link_path is None:
        ctx.skip(
            _fix_message_no_end_effector(
                search_root=search_root,
                robot_prim_path=str(robot.prim_path),
            )
        )
        return
    discovered_ee_path = ee_link_path
    ee_link_path = resolve_live_end_effector_link(robot, discovered_ee_path)
    if ee_link_path is None:
        detail = getattr(robot, "_link_transform_resolve_detail", "")
        raise RuntimeError(
            "INTERNAL: JIK discovered end-effector marker %s but could not "
            "resolve it or any ancestor to a live articulation link%s. The "
            "test cannot measure simulated travel from authored USD transforms."
            % (discovered_ee_path, (": " + detail) if detail else "")
        )
        return
    if ee_link_path != discovered_ee_path:
        ctx.log("JIK: end-effector marker %s resolves to live physics link %s" % (discovered_ee_path, ee_link_path))
    else:
        ctx.log("JIK: end-effector link: %s" % ee_link_path)

    # ---- Settle + snapshot home configuration -------------------------
    locked_indices = excluded_dof_indices(scene_info, len(robot.dof_names))
    if len(locked_indices) == len(robot.dof_names):
        ctx.add_metric("jik_sampled_joint_count", 0)
        ctx.add_metric("jik_sampling_eligible_dofs", 0)
        ctx.skip("JIK insufficient coverage: no nonlocked joint has a qualified bounded excursion.")
        return
    require_indexed_control(robot, locked_indices)
    home_joints = await _settle_and_snapshot(ctx, robot, settle_seconds, physics_fps)

    # ---- Build solver --------------------------------------------------
    # Closed-loop / parallel-linkage joints (e.g. the M-2000 counterbalance
    # P2/P2_01) cannot be driven as free DOFs: the loop constraint fights the
    # finite-difference perturbation and corrupts their Jacobian columns. Lock
    # them so the DLS solve runs over the main open chain only and the loop
    # joints passively follow their constraint. Empty on open-chain robots.
    locked_indices = excluded_dof_indices(scene_info, len(robot.dof_names))
    loop_joint_names = scene_info.get("loop_joint_names") or []
    if locked_indices:
        ctx.step(
            "JIK: excluding %d passive/mimic-follower/loop DOF(s) from independent commands (%s); "
            "solving IK over independent coordinates only." % (len(locked_indices), ", ".join(loop_joint_names))
        )
        ctx.add_metric("jik_loop_joints_locked", len(scene_info.get("loop_joint_indices") or ()))
        ctx.add_metric("jik_independent_dof_exclusions", sorted(locked_indices)[:64])
        ctx.add_metric("jik_independent_dof_exclusions_omitted", max(0, len(locked_indices) - 64))
    from .joint_targets import bounded_joint_range, joint_is_angular

    lowers, uppers = robot.get_joint_position_limits()
    angular_indices = {i for i, name in enumerate(robot.dof_names) if joint_is_angular(scene_info, name)}
    eligible_indices = _sampling_joint_indices(home_joints, lowers, uppers, locked_indices, angular_indices)
    unsampled = [
        str(name)
        for i, name in enumerate(robot.dof_names)
        if i not in locked_indices
        and bounded_joint_range(
            lowers[i] if i < len(lowers) else float("nan"),
            uppers[i] if i < len(uppers) else float("nan"),
            home_joints[i],
            angular=i in angular_indices,
        )
        is None
    ]
    if unsampled:
        ctx.warn(
            f"JIK: holding joints without a safe bounded excursion at home for FK target samples: {', '.join(unsampled)}"
        )
    ctx.add_metric("jik_joints_without_safe_range", unsampled)
    ctx.add_metric("jik_sampled_joint_count", len(eligible_indices))
    if not eligible_indices:
        ctx.skip(
            "JIK insufficient coverage: no nonlocked joint has a qualified bounded excursion. "
            "Home-only poses cannot exercise IK, even with one requested target. "
            "Unbounded linear or unidentified joints require a qualified sampling policy; "
            "this does not establish a stale pose source or an asset-response defect."
        )
        return
    try:
        solver = JacobianIKSolver(
            robot=robot,
            ee_link_path=ee_link_path,
            damping_lambda=damping_lambda,
            locked_indices=locked_indices,
            finite_difference_epsilon=finite_difference_epsilon,
            jacobian_propagation_steps=jacobian_propagation_steps,
        )
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RuntimeError(_fix_message_solver_construct(exc)) from exc
        return

    home_orientation = _capture_home_orientation(solver)

    # ---- Reach + base position -----------------------------------------
    base_pos = get_robot_base_position(robot, scene_info)
    robot_reach = estimate_robot_reach(asset_prim or robot_root_prim)
    # Use the largest factor as the headline radius for metrics.
    max_radius_factor = max(target_radius_factors)
    target_radius = max(0.05, robot_reach * max_radius_factor)
    ctx.add_metric("jik_robot_reach", round(robot_reach, 4))
    ctx.add_metric("jik_target_radius", round(target_radius, 4))
    ctx.add_metric("jik_base_position_x", round(float(base_pos[0]), 4))
    ctx.add_metric("jik_base_position_y", round(float(base_pos[1]), 4))
    ctx.add_metric("jik_base_position_z", round(float(base_pos[2]), 4))

    # ---- Generate targets (forward-kinematics sampled) ----------------
    # Targets are EE poses the arm demonstrably holds at sampled in-limits
    # configurations, so every in-reach target is a provably feasible 6-DOF
    # pose (position + orientation). This replaces position-only shell targets,
    # which fixed the home orientation at every sampled point and were
    # infeasible for most points on a real arm -- the cause of spurious red
    # solver failures on conformant arms. Loop-locked DOFs are not sampled.
    targets, max_observed_reach = await _generate_fk_targets(
        ctx=ctx,
        robot=robot,
        solver=solver,
        home_joints=home_joints,
        base_pos=base_pos,
        lowers=lowers,
        uppers=uppers,
        locked=locked_indices,
        num_reachable=num_targets,
        num_out_of_reach=out_of_reach_count,
        angular_indices=angular_indices,
    )
    ctx.add_metric("jik_max_observed_reach", round(float(max_observed_reach), 4))
    if not targets:
        # The target generator should always return at least one target as
        # long as num_reachable + num_out_of_reach > 0 and a radius factor
        # is set -- all of which are guaranteed by get_defaults(). An empty
        # list here means the generator itself failed or the caller
        # overrode config with zero counts.
        raise RuntimeError(
            "INTERNAL: JIK target generator returned zero targets despite "
            "num_targets=%d, out_of_reach_count=%d, radius_factors=%s. "
            "This is a framework / test-config bug (not an asset issue). "
            "Verify the JIK config override on this profile and file "
            "against the core tier's runtime-test implementation if the defaults are in use."
            % (num_targets, out_of_reach_count, str(target_radius_factors))
        )
        return
    ctx.log("JIK: generated %d targets" % len(targets))
    distinct_reachable = count_distinct_reachable_positions(targets)
    ctx.add_metric("jik_distinct_reachable_targets", distinct_reachable)
    if num_targets > 1 and distinct_reachable < 2:
        ctx.fail(
            "INTERNAL: JIK sampled %d reachable joint configurations but "
            "observed fewer than two distinct live end-effector positions. "
            "This run cannot prove travel to distinct IK targets. Check pose freshness, "
            "sampled joint configurations, kinematics, constraints and scene setup; "
            "this observation alone does not establish a stale source or an asset defect." % num_targets
        )
        return

    # ---- Target sphere visualization (gray = pending) -----------------
    show_spheres = bool(cfg.get("show_target_spheres", True))
    sphere_scope = str(cfg.get("target_sphere_scope", "/World/IK_Targets"))
    sphere_radius = float(cfg.get("target_sphere_radius", 0.04))
    target_sphere_prims = []  # type: list[Any]
    if show_spheres:
        target_sphere_prims = create_target_spheres_from_targets(
            stage=stage,
            parent_path=sphere_scope,
            targets=targets,
            radius=sphere_radius,
        )

    # ---- Baseline bbox (explode canary) -------------------------------
    baseline_bbox = None  # type: Optional[BBoxSnapshot]
    if asset_prim is not None or robot_root_prim is not None:
        baseline_bbox = freeze_bbox_reference(
            compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "jik"
        )
        ctx.add_metric("jik_bbox_baseline_volume", round(baseline_bbox.volume, 6))

    # ---- Precompute solver solutions ----------------------------------
    ctx.step("JIK: precompute phase begin (%d targets)" % len(targets))
    solutions = await _precompute_solutions(
        ctx=ctx,
        robot=robot,
        solver=solver,
        targets=targets,
        home_joints=home_joints,
        home_orientation=home_orientation,
        pos_tol=pos_tol,
        orient_tol_rad=orient_tol_rad,
        max_iterations=max_solver_iterations,
    )
    # Playback remains under the registered whole-test ceiling, not the
    # search allowance. The completed search cannot earn an asset verdict.
    ctx.check()
    ctx.finish("search_completed")

    # ---- Motion playback for each solution ----------------------------
    capture_frames = []  # type: list[str]
    ctx.step("JIK: motion phase begin (%d solutions)" % len(solutions))
    per_target_results = await _run_motion_for_solutions(
        ctx=ctx,
        robot=robot,
        solver=solver,
        scene_info=scene_info,
        solutions=solutions,
        home_joints=home_joints,
        cfg=cfg,
        capture_frames=capture_frames,
        capture_interval=capture_interval,
        baseline_bbox=baseline_bbox,
        target_sphere_prims=target_sphere_prims,
        locked_indices=locked_indices,
    )

    # Sphere cleanup -- so the asset stage stays clean between tests.
    if show_spheres:
        cleanup_target_spheres(stage, sphere_scope)

    # ---- Encode video --------------------------------------------------
    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="jacobian_ik", role="summary")

    # ---- Aggregate + gate ---------------------------------------------
    summary = aggregate_jik_summary(per_target_results)
    _record_phase_metrics(ctx, summary, ee_link_path)

    if summary["in_reach_total"] <= 0:
        # No in-reach targets means the bbox-based reach estimate is
        # degenerate -- typically an asset-authoring problem (wrong scale,
        # missing geometry under the articulation root) rather than a
        # framework bug. Treat as skip to mirror v1's defensive path.
        asset_path = (
            str(asset_prim.GetPath()) if asset_prim is not None and asset_prim.IsValid() else str(robot.prim_path)
        )
        ctx.skip(
            _fix_message_no_in_reach_targets(
                robot_reach=robot_reach,
                asset_prim_path=asset_path,
            )
        )
        return

    if summary["pass_rate"] < min_pass_rate:
        ctx.fail(
            _fix_message_pass_rate_below_min(
                pass_rate=summary["pass_rate"],
                min_pass_rate=min_pass_rate,
                in_reach_passed=summary["in_reach_passed"],
                in_reach_total=summary["in_reach_total"],
                in_reach_solver_failed=summary["in_reach_solver_failed"],
                in_reach_motion_failed=summary["in_reach_motion_failed"],
                max_pos_err=summary["max_position_error_m"],
                max_orient_err_deg=summary["max_orientation_error_deg"],
                pos_tol=pos_tol,
                orient_tol_deg=orient_tol_deg,
                failure_names=summary["failure_names"],
                ee_link_path=ee_link_path,
            )
        )

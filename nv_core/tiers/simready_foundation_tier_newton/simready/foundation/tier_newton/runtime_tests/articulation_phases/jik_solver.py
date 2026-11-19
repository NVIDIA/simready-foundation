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
"""
Jacobian-based IK solver utilities (Framework 2.0 port from v1.6).

Implements a damped least-squares Jacobian solver that uses USD-based FK
combined with finite-difference Jacobian collection. The pure-math pieces
(DLS step, joint clamping, pose error) are exposed as module-level
helpers for unit testing without a Kit install.

V1 source: test_definitions/isaac_sim/shared_phases/jik_solver.py.
The DLS math, clamping logic, and pose-error formulation are preserved
verbatim from v1; the API is simplified to a sync ``solve()`` (the
caller is responsible for physics stepping via ``ctx.step_one()`` after
setting joint targets).
"""

import math
from dataclasses import dataclass

import numpy as np
from simready.foundation.tier_newton.runtime_tests.articulation_phases._diagnostic_notes import (
    note_secondary_error,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases._independent_dofs import (
    require_indexed_control,
    validate_indices,
    write_probe_state,
)

# Local imports (kept ASCII, Python 3.9 typing).
from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_utils import (
    get_dof_property,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    as_real_array as _as_real_array,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    require_vector as _require_vector,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    required_link_pose as _required_link_pose,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    required_positions as _required_positions,
)

# =============================================================================
# Result dataclass
# =============================================================================


@dataclass
class JacobianIKResult:
    """Result of a Jacobian IK solve attempt."""

    success: bool
    iterations: int
    final_position: np.ndarray
    final_orientation: np.ndarray
    final_pos_error: float
    final_orient_error_deg: float
    converged_joints: np.ndarray


# =============================================================================
# Pure-math helpers (module level, for unit testing)
# =============================================================================


def _compute_dls_step(jacobian, error_vector, damping_lambda):
    # type: (np.ndarray, np.ndarray, float) -> np.ndarray
    """Compute one damped-least-squares delta-q step.

    Solves ``(J J^T + lambda^2 I) y = error`` then returns ``J^T y``.
    Falls back to ``pinv(J) @ error`` when the linear solve is singular.

    Args:
        jacobian: nonempty M x N finite real Jacobian matrix, typically 6 x N.
        error_vector: finite real length-M vector matching the Jacobian rows.
        damping_lambda: non-negative damping factor.

    Returns:
        delta_q vector of length N.

    Raises:
        np.linalg.LinAlgError: when both the damped solve and pinv fail.
        FloatingPointError: when required DLS arithmetic overflows or is invalid.
        ValueError: when the Jacobian or damping is malformed or nonfinite.
        RequiredReadbackError: when an error vector or result is malformed.
    """
    jacobian = _as_real_array(jacobian).astype(np.float64)
    if jacobian.ndim != 2 or not all(jacobian.shape) or not np.isfinite(jacobian).all():
        raise ValueError("DLS requires a nonempty finite real Jacobian matrix")
    error_vector = _require_vector(error_vector, "JIK", "solver error vector", jacobian.shape[0]).astype(np.float64)
    if (
        isinstance(damping_lambda, (bool, np.bool_))
        or not isinstance(damping_lambda, (int, float, np.integer, np.floating))
        or not math.isfinite(float(damping_lambda))
        or damping_lambda < 0.0
    ):
        raise ValueError("DLS requires finite nonnegative damping")
    # A nonfinite intermediate can still produce a finite-looking zero step.
    # Trap it synchronously before that response is mistaken for nonconvergence.
    # Underflow remains allowed so singular tiny Jacobians retain pinv fallback.
    with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
        JJT = jacobian @ jacobian.T
        damping_matrix = (damping_lambda**2) * np.eye(JJT.shape[0])
        try:
            y = np.linalg.solve(JJT + damping_matrix, error_vector)
            y = _require_vector(y, "JIK", "DLS linear solution", jacobian.shape[0]).astype(np.float64)
            delta_q = jacobian.T @ y
        except np.linalg.LinAlgError:
            delta_q = np.linalg.pinv(jacobian) @ error_vector
    return _require_vector(delta_q, "JIK", "solver joint step", jacobian.shape[1]).astype(np.float64)


def _clamp_joints_to_limits(joints, lower_limits, upper_limits):
    # type: (np.ndarray, np.ndarray, np.ndarray) -> np.ndarray
    """Clamp each joint position into its [lower, upper] range elementwise.

    NaN limits are treated as unbounded (no clamp on that side). Operates
    on a copy; original ``joints`` is left untouched.
    """
    out = np.array(joints, dtype=np.float64).copy()
    n = min(len(out), len(lower_limits), len(upper_limits))
    for i in range(n):
        lo = float(lower_limits[i])
        up = float(upper_limits[i])
        v = float(out[i])
        if math.isfinite(lo) and v < lo:
            v = lo
        if math.isfinite(up) and v > up:
            v = up
        out[i] = v
    return out


def _quat_multiply(q1, q2):
    # type: (np.ndarray, np.ndarray) -> np.ndarray
    """Multiply two quaternions in (w, x, y, z) order."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=np.float64,
    )


def _normalize_quat(quat):
    # type: (np.ndarray) -> np.ndarray
    """Normalize a quaternion; returns the original when the norm is zero."""
    q = np.asarray(quat, dtype=np.float64).flatten()
    norm = float(np.linalg.norm(q))
    if norm <= 0.0:
        return q
    return q / norm


def _pose_error(current_pos, current_orient, target_pos, target_orient):
    # type: (np.ndarray, np.ndarray, np.ndarray, np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]
    """Compute position + orientation error vectors.

    Position error is ``target_pos - current_pos``.
    Orientation error is ``2 * vector_part(q_target * conj(q_current))``,
    flipped to the shorter rotation when the scalar part is negative.

    Args:
        current_pos: length-3 array.
        current_orient: length-4 quaternion (w, x, y, z).
        target_pos: length-3 array.
        target_orient: length-4 quaternion (w, x, y, z).

    Returns:
        Tuple of:
          * position_error_vec (3,)
          * orientation_error_vec (3,) -- angular velocity to rotate current to target
          * position_error_norm (float, meters)
          * orientation_error_rad (float, magnitude in radians)
    """
    cur_pos = np.asarray(current_pos, dtype=np.float64).flatten()
    tgt_pos = np.asarray(target_pos, dtype=np.float64).flatten()
    pos_err = tgt_pos - cur_pos
    pos_err_norm = float(np.linalg.norm(pos_err))

    cur_quat = _normalize_quat(current_orient)
    tgt_quat = _normalize_quat(target_orient)
    cur_conj = np.array(
        [cur_quat[0], -cur_quat[1], -cur_quat[2], -cur_quat[3]],
        dtype=np.float64,
    )
    q_err = _quat_multiply(tgt_quat, cur_conj)
    if q_err[0] < 0:
        q_err = -q_err
    ori_err_vec = 2.0 * q_err[1:4]
    ori_err_norm = float(np.linalg.norm(ori_err_vec))
    return pos_err, ori_err_vec, pos_err_norm, ori_err_norm


# =============================================================================
# Solver class
# =============================================================================


class JacobianIKSolver:
    """Damped least-squares Jacobian-based IK solver with async live probes.

    Uses live articulation-link poses and finite-difference Jacobian
    collection. The caller supplies an async physics-step function to
    ``solve()`` and ``compute_jacobian()`` so the tensor view reflects the
    current articulation state after each synchronized probe.
    """

    EPSILON = 1e-5

    def __init__(
        self,
        robot,
        ee_link_path,
        damping_lambda=0.05,
        locked_indices=None,
        finite_difference_epsilon=None,
        jacobian_propagation_steps=1,
    ):
        # type: (Any, str, float, Any) -> None
        """Build a solver bound to a robot + end-effector link.

        Args:
            robot: ``RobotHandle`` wrapping the SingleArticulation.
            ee_link_path: USD prim path of the end-effector link (used for FK).
            damping_lambda: DLS damping factor (lambda); 0.05 is a good default.
            locked_indices: DOF indices the solver must NOT command -- closed-loop
                / parallel-linkage joints whose motion is dictated by the loop
                constraint, not by an independent target. Their Jacobian columns
                are held at zero so DLS never requests motion on them, and they
                are not written by probe, target or velocity dispatch. Live
                state remains required. Empty/None on unconstrained robots.
        """
        self.robot = robot
        self.ee_link_path = str(ee_link_path)
        self.damping_lambda = float(damping_lambda)
        self._locked = set(locked_indices or ())
        self._finite_difference_epsilon = float(
            self.EPSILON if finite_difference_epsilon is None else finite_difference_epsilon
        )
        if not math.isfinite(self._finite_difference_epsilon) or self._finite_difference_epsilon <= 0.0:
            raise ValueError("finite_difference_epsilon must be positive and finite")
        self._jacobian_propagation_steps = max(1, int(jacobian_propagation_steps))

        # Keep the RobotHandle boundary: it converts host arrays to the active
        # backend's tensor/device representation. Bypassing it and calling the
        # underlying SingleArticulation directly breaks on Newton's CUDA/Torch
        # pipeline even though the same NumPy calls happen to work on PhysX.
        self._articulation = robot
        self._stage = getattr(robot, "_stage", None)

        # Cache dof count and joint limits at construction time.
        names = getattr(robot, "dof_names", None)
        self.dof_count = len(names) if names is not None else 0
        self._locked = validate_indices(self._locked, self.dof_count)
        require_indexed_control(robot, self._locked)

        self._lower_limits, self._upper_limits = self._extract_limits()

    # -- Limits --------------------------------------------------------

    def _extract_limits(self):
        # type: () -> tuple[np.ndarray, np.ndarray]
        """Pull joint position limits via RobotHandle accessor or dof_properties."""
        getter = getattr(self.robot, "get_joint_position_limits", None)
        try:
            if callable(getter):
                lowers, uppers = getter()
            else:
                props = getattr(self._articulation, "dof_properties", None)
                if isinstance(props, (list, tuple)):
                    # The legacy helper float-coerces mapping records. Preserve
                    # types here so bool/string stops cannot become evidence.
                    lowers = [entry["lower"] for entry in props]
                    uppers = [entry["upper"] for entry in props]
                else:
                    lowers = get_dof_property(props, "lower")
                    uppers = get_dof_property(props, "upper")
            if lowers is None or uppers is None:
                raise ValueError("joint-limit observation is unavailable")
            raw_lower, raw_upper = _as_real_array(lowers), _as_real_array(uppers)
            with np.errstate(over="raise", invalid="raise"):
                lower = raw_lower.astype(np.float64)
                upper = raw_upper.astype(np.float64)
            if lower.shape != (self.dof_count,) or upper.shape != (self.dof_count,):
                raise ValueError("joint-limit observation has an invalid shape")
            active = [i for i in range(self.dof_count) if i not in self._locked]
            for index in active:
                lo, hi = float(lower[index]), float(upper[index])
                if (
                    math.isnan(lo)
                    or math.isnan(hi)
                    or lo > hi
                    or lo == math.inf
                    or hi == -math.inf
                    or (np.isfinite(raw_lower[index]) and not math.isfinite(lo))
                    or (np.isfinite(raw_upper[index]) and not math.isfinite(hi))
                ):
                    raise ValueError("active joint limits are unknown or unordered")
            # Correctly signed infinities are explicit unlimited stops, not a
            # substitute for an unavailable required read. Excluded coordinates
            # can remain unavailable because no probe writes those coordinates.
            return lower, upper
        except Exception as error:
            raise RequiredReadbackError(
                "JIK runtime error: required joint-limit readback is unavailable or invalid; "
                "no unbounded fallback probe was issued"
            ) from error

    # -- Forward kinematics ---------------------------------------------

    def _write_joint_pose(self, joints):
        """Keep the Newton backend boundary and motor target consistent with a probe."""
        joints = _require_vector(joints, "JIK", "probe configuration", self.dof_count).astype(np.float64)
        try:
            write_probe_state(self.robot, joints, self._locked)
        except Exception as exc:
            raise RequiredReadbackError(
                "JIK runtime error: failed to establish the required probe configuration"
            ) from exc

    async def _propagate_probe(self, step_fn):
        try:
            await step_fn()
        except RequiredReadbackError:
            raise
        except Exception as exc:
            raise RequiredReadbackError("JIK runtime error: required probe propagation failed") from exc

    def get_ee_pose(self):
        # type: () -> tuple[np.ndarray, np.ndarray]
        """Return (position, quaternion) of the EE link in world frame.

        Uses the articulation physics tensor view through ``RobotHandle``.
        Dynamic articulation link poses are not written back to USD by every
        backend (notably Newton), so ``UsdGeom.XformCache`` can return the
        same authored pose after every joint command and make IK vacuously
        pass without motion.
        """
        position, quat_xyzw = _required_link_pose(self.robot, self.ee_link_path, "JIK")
        # Physics tensor views use scalar-last XYZW; the JIK math uses WXYZ.
        quat_wxyz = quat_xyzw[[3, 0, 1, 2]]
        return position.copy(), _normalize_quat(quat_wxyz)

    # -- Jacobian -------------------------------------------------------

    async def compute_jacobian(self, joints, step_fn):
        """Restore synchronized joint state if a pose probe fails or is cancelled."""
        joints = _require_vector(joints, "JIK", "probe configuration", self.dof_count).astype(np.float64).copy()
        try:
            return await self._compute_jacobian(joints, step_fn)
        except BaseException as primary:
            try:
                self._write_joint_pose(joints)
            except BaseException as secondary:
                note_secondary_error(
                    primary, lambda secondary=secondary: "JIK probe restoration also failed: %r" % secondary
                )
            raise

    async def _compute_jacobian(self, joints, step_fn):
        # type: (np.ndarray, Any) -> np.ndarray
        """Compute a 6 x dof_count Jacobian at the given joint configuration.

        Uses finite differences against live articulation FK.
        After each ``set_joint_positions`` we ``await step_fn()`` (typically
        ``ctx.step_one``) so the active physics backend propagates the new
        joint state into its tensor view before ``get_ee_pose`` reads it.
        """
        joints = np.asarray(joints, dtype=np.float64).copy()
        jacobian = np.zeros((6, self.dof_count), dtype=np.float64)

        # Establish base pose at *joints* (caller may have already stepped,
        # but we step once more here to guarantee xform cache freshness).
        self._write_joint_pose(joints)
        for _ in range(self._jacobian_propagation_steps):
            await self._propagate_probe(step_fn)
        base_pos, base_quat = self.get_ee_pose()

        for i in range(self.dof_count):
            # Locked (closed-loop) DOFs are never commanded: leaving their
            # Jacobian column at zero means the DLS step requests no motion on
            # them, so the solve runs over the main open chain only.
            if i in self._locked:
                continue
            eps_i = self._finite_difference_epsilon
            if i < len(self._lower_limits):
                up = self._upper_limits[i]
                if math.isfinite(up) and joints[i] >= up:
                    eps_i = -self._finite_difference_epsilon
            perturbed = joints.copy()
            perturbed[i] += eps_i
            if i < len(self._lower_limits):
                perturbed[i] = float(np.clip(perturbed[i], self._lower_limits[i], self._upper_limits[i]))
            displacement = float(perturbed[i] - joints[i])
            if not math.isfinite(displacement):
                raise RequiredReadbackError("JIK runtime error: finite-difference probe displacement is non-finite")
            if displacement == 0.0:
                continue  # Locked/narrow coordinates cannot provide a derivative.

            # Write perturbed joints; STEP PHYSICS so live poses update; read EE.
            self._write_joint_pose(perturbed)
            for _ in range(self._jacobian_propagation_steps):
                await self._propagate_probe(step_fn)
            pert_pos, pert_quat = self.get_ee_pose()

            jacobian[0:3, i] = (pert_pos - base_pos) / displacement
            # Orientation rows MUST use the same formulation as the error
            # vector in `_pose_error` (2 * vec(q_b * conj(q_a)) -- a world-frame
            # rotation vector). A raw component difference (pert_quat -
            # base_quat) is only correct when base_quat is identity, which it
            # never is for a real EE pose; using it leaves the orientation
            # gradient in a different representation than the error, so DLS
            # reduces position but cannot drive orientation down (the EE
            # reaches the target point but stays tens of degrees mis-rotated).
            base_conj = np.array(
                [base_quat[0], -base_quat[1], -base_quat[2], -base_quat[3]],
                dtype=np.float64,
            )
            q_inc = _quat_multiply(pert_quat, base_conj)
            if q_inc[0] < 0.0:
                q_inc = -q_inc
            jacobian[3:6, i] = 2.0 * q_inc[1:4] / displacement

        # Restore original joints + step so caller sees a clean state.
        self._write_joint_pose(joints)
        for _ in range(self._jacobian_propagation_steps):
            await self._propagate_probe(step_fn)
        return jacobian

    # -- Solve loop -----------------------------------------------------

    async def solve(
        self,
        target_pos,
        target_orient,
        step_fn,
        max_iterations=200,
        pos_tol=0.02,
        orient_tol_rad=0.0873,
        heartbeat_fn=None,
    ):
        # type: (np.ndarray, np.ndarray, Any, int, float, float, Any) -> JacobianIKResult
        """Damped least-squares iteration toward the target pose.

        ``step_fn`` is an async callable (typically ``ctx.step_one``) invoked
        after every ``set_joint_positions`` so PhysX propagates the new joint
        state into the USD xform cache before the next pose read.

        ``heartbeat_fn`` is an optional callable invoked roughly every 10
        iterations with a status string. The phase passes ``ctx.step`` so
        the runner's session-inactivity watchdog sees progress even when
        a single solve runs for many seconds, avoiding the configured
        timeout for prolonged stdout silence.
        """
        target_pos = np.asarray(target_pos, dtype=np.float64).flatten()
        target_orient = _normalize_quat(target_orient)

        joints = np.array(_required_positions(self._articulation, "JIK"), dtype=np.float64)
        best_joints = joints.copy()
        best_pos_err = float("inf")
        best_ori_err = float("inf")
        last_pos = best_joints
        last_quat = target_orient
        iterations_used = 0

        for iteration in range(max_iterations):
            iterations_used = iteration + 1

            # Heartbeat every 10 iterations so the runner watchdog stays
            # happy when a solve runs to max_iterations (~50 * 7 phys
            # steps per Jacobian = several seconds per solve).
            if heartbeat_fn is not None and iteration % 10 == 0:
                try:
                    heartbeat_fn("JIK solver iter=%d/%d pos_err=%.3f" % (iteration, max_iterations, best_pos_err))
                except Exception:
                    pass

            # Locked (closed-loop) DOFs are owned by the loop constraint, not
            # the solver: refresh them from the live articulation state so we
            # write back whatever PhysX last produced rather than forcing a
            # stale value that would fight the constraint.
            if self._locked:
                live = np.asarray(_required_positions(self._articulation, "JIK"), dtype=np.float64)
                for li in self._locked:
                    if li < len(joints) and li < len(live):
                        joints[li] = live[li]

            # Apply current joints + step physics so the tensor view reflects them.
            self._write_joint_pose(joints)
            await self._propagate_probe(step_fn)
            cur_pos, cur_quat = self.get_ee_pose()
            last_pos = cur_pos
            last_quat = cur_quat

            pos_err_vec, ori_err_vec, pos_err_norm, ori_err_norm = _pose_error(
                cur_pos, cur_quat, target_pos, target_orient
            )
            error_vec = np.concatenate([pos_err_vec, ori_err_vec])

            if pos_err_norm < best_pos_err:
                best_pos_err = pos_err_norm
                best_ori_err = ori_err_norm
                best_joints = joints.copy()

            if pos_err_norm < pos_tol and ori_err_norm < orient_tol_rad:
                return self._build_result(
                    success=True,
                    iterations=iterations_used,
                    final_position=cur_pos,
                    final_orientation=cur_quat,
                    final_pos_error=pos_err_norm,
                    final_ori_error_rad=ori_err_norm,
                    converged_joints=joints,
                )

            # Build Jacobian + DLS step.
            jacobian = await self.compute_jacobian(joints, step_fn)
            # The helper already falls back to a pseudoinverse for singular
            # solves. Failure of that fallback is an execution error, not
            # evidence that an out-of-reach target was correctly rejected.
            delta_q = _compute_dls_step(jacobian, error_vec, self.damping_lambda)
            # Reject numerical overflow before locks or limit clamping can
            # disguise an invalid step as a finite, nonconvergent response.
            delta_q = _require_vector(delta_q, "JIK", "solver joint step", self.dof_count).astype(np.float64)

            # Never command locked (closed-loop) DOFs (belt-and-suspenders on
            # top of their zero Jacobian columns).
            for li in self._locked:
                if li < len(delta_q):
                    delta_q[li] = 0.0

            with np.errstate(over="raise", invalid="raise"):
                candidate_joints = joints + delta_q
            candidate_joints = _require_vector(
                candidate_joints, "JIK", "computed probe configuration", self.dof_count
            ).astype(np.float64)
            joints = _clamp_joints_to_limits(candidate_joints, self._lower_limits, self._upper_limits)

        # Did not converge within max_iterations.
        success = best_pos_err < pos_tol and best_ori_err < orient_tol_rad
        # Restore best joints + step so result reflects best attempt.
        self._write_joint_pose(best_joints)
        await self._propagate_probe(step_fn)
        try:
            final_pos, final_quat = self.get_ee_pose()
        except RequiredReadbackError:
            raise
        except Exception:
            final_pos, final_quat = last_pos, last_quat

        return self._build_result(
            success=success,
            iterations=iterations_used,
            final_position=final_pos,
            final_orientation=final_quat,
            final_pos_error=best_pos_err,
            final_ori_error_rad=best_ori_err,
            converged_joints=best_joints,
        )

    # -- Result helpers -------------------------------------------------

    def _build_result(
        self,
        success,
        iterations,
        final_position,
        final_orientation,
        final_pos_error,
        final_ori_error_rad,
        converged_joints,
    ):
        # type: (bool, int, np.ndarray, np.ndarray, float, float, np.ndarray) -> JacobianIKResult
        """Build a JacobianIKResult, converting orientation error to degrees."""
        ori_err_deg = float(math.degrees(final_ori_error_rad))
        return JacobianIKResult(
            success=bool(success),
            iterations=int(iterations),
            final_position=np.asarray(final_position, dtype=np.float64),
            final_orientation=np.asarray(final_orientation, dtype=np.float64),
            final_pos_error=float(final_pos_error),
            final_orient_error_deg=ori_err_deg,
            converged_joints=np.asarray(converged_joints, dtype=np.float64),
        )

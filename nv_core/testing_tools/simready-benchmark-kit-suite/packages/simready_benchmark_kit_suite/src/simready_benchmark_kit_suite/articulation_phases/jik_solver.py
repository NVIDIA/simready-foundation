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

# Local imports (kept ASCII, Python 3.9 typing).
from simready_benchmark_kit_suite.articulation_phases.motion_utils import (
    get_dof_property,
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
        jacobian: 6 x N (or 3 x N) Jacobian matrix.
        error_vector: length-6 (or length-3) error vector matching jacobian rows.
        damping_lambda: non-negative damping factor.

    Returns:
        delta_q vector of length N.

    Raises:
        np.linalg.LinAlgError: when both the damped solve and pinv fail.
    """
    JJT = jacobian @ jacobian.T
    damping_matrix = (damping_lambda**2) * np.eye(JJT.shape[0])
    try:
        y = np.linalg.solve(JJT + damping_matrix, error_vector)
        return jacobian.T @ y
    except np.linalg.LinAlgError:
        return np.linalg.pinv(jacobian) @ error_vector


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
    # type: (np.ndarray, np.ndarray, np.ndarray, np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, float]
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
    """Damped least-squares Jacobian-based IK solver (sync, Framework 2.0).

    Uses USD forward-kinematics and finite-difference Jacobian collection.
    The caller (the JIK phase) is responsible for stepping physics around
    each ``solve()`` call so USD xform caches reflect the current
    articulation state.
    """

    EPSILON = 1e-5

    def __init__(self, robot, ee_link_path, damping_lambda=0.05, locked_indices=None):
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
                are written back from the live articulation state each step so
                they passively follow the loop. Empty/None on open-chain robots.
        """
        self.robot = robot
        self.ee_link_path = str(ee_link_path)
        self.damping_lambda = float(damping_lambda)
        self._locked = set(int(i) for i in (locked_indices or set()))

        articulation = getattr(robot, "articulation", None)
        if articulation is None:
            articulation = robot
        self._articulation = articulation
        self._stage = getattr(robot, "_stage", None)

        # Cache dof count and joint limits at construction time.
        names = getattr(articulation, "dof_names", None)
        self.dof_count = len(names) if names is not None else 0

        self._lower_limits, self._upper_limits = self._extract_limits()

    # -- Limits --------------------------------------------------------

    def _extract_limits(self):
        # type: () -> Tuple[np.ndarray, np.ndarray]
        """Pull joint position limits via RobotHandle accessor or dof_properties."""
        getter = getattr(self.robot, "get_joint_position_limits", None)
        if callable(getter):
            try:
                lo, up = getter()
                return np.asarray(lo, dtype=np.float64), np.asarray(up, dtype=np.float64)
            except Exception:
                pass
        props = getattr(self._articulation, "dof_properties", None)
        lowers = get_dof_property(props, "lower")
        uppers = get_dof_property(props, "upper")
        if lowers is None:
            lowers = np.full(self.dof_count, -math.inf, dtype=np.float64)
        if uppers is None:
            uppers = np.full(self.dof_count, math.inf, dtype=np.float64)
        return np.asarray(lowers, dtype=np.float64), np.asarray(uppers, dtype=np.float64)

    # -- Forward kinematics ---------------------------------------------

    def get_ee_pose(self):
        # type: () -> Tuple[np.ndarray, np.ndarray]
        """Return (position, quaternion) of the EE link in world frame.

        Uses ``UsdGeom.XformCache`` against the current stage. The caller
        must ensure the articulation has been physics-stepped so USD
        xforms reflect current joint state.
        """
        from pxr import Usd, UsdGeom

        if self._stage is None:
            raise ValueError("JacobianIKSolver: robot has no associated USD stage")
        ee_prim = self._stage.GetPrimAtPath(self.ee_link_path)
        if not ee_prim or not ee_prim.IsValid():
            raise ValueError("End-effector prim not found: %s" % self.ee_link_path)
        xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        world_transform = xform_cache.GetLocalToWorldTransform(ee_prim)
        position = np.array(world_transform.ExtractTranslation(), dtype=np.float64)
        rotation = world_transform.ExtractRotationQuat()
        quat = np.array(
            [
                rotation.GetReal(),
                rotation.GetImaginary()[0],
                rotation.GetImaginary()[1],
                rotation.GetImaginary()[2],
            ],
            dtype=np.float64,
        )
        return position, quat

    # -- Jacobian -------------------------------------------------------

    async def compute_jacobian(self, joints, step_fn):
        # type: (np.ndarray, Any) -> np.ndarray
        """Compute a 6 x dof_count Jacobian at the given joint configuration.

        Uses finite differences against USD-FK -- preserves v1's approach.
        After each ``set_joint_positions`` we ``await step_fn()`` (typically
        ``ctx.step_one``) so PhysX propagates the new joint state into the
        USD xform cache before ``get_ee_pose`` reads it. Without this the
        XformCache returns the same pose for every perturbation and the
        Jacobian collapses to zero -- causing the solver to loop the full
        max_iterations without converging.
        """
        joints = np.asarray(joints, dtype=np.float64).copy()
        jacobian = np.zeros((6, self.dof_count), dtype=np.float64)

        # Establish base pose at *joints* (caller may have already stepped,
        # but we step once more here to guarantee xform cache freshness).
        self._articulation.set_joint_positions(joints)
        try:
            self._articulation.set_joint_velocities(np.zeros(self.dof_count, dtype=np.float64))
        except Exception:
            pass
        await step_fn()
        base_pos, base_quat = self.get_ee_pose()

        for i in range(self.dof_count):
            # Locked (closed-loop) DOFs are never commanded: leaving their
            # Jacobian column at zero means the DLS step requests no motion on
            # them, so the solve runs over the main open chain only.
            if i in self._locked:
                continue
            eps_i = self.EPSILON
            if i < len(self._lower_limits):
                up = self._upper_limits[i]
                if math.isfinite(up) and joints[i] + eps_i > up:
                    eps_i = -self.EPSILON
            perturbed = joints.copy()
            perturbed[i] += eps_i
            if i < len(self._lower_limits):
                perturbed[i] = float(np.clip(perturbed[i], self._lower_limits[i], self._upper_limits[i]))

            # Write perturbed joints; STEP PHYSICS so xforms update; read EE.
            self._articulation.set_joint_positions(perturbed)
            try:
                # Zero velocities on each teleport so PhysX does not
                # accumulate spurious dynamics between iterations. With
                # 7 teleports per Jacobian column * many iterations,
                # leftover velocities cascade and eventually invalidate
                # the tensor view.
                self._articulation.set_joint_velocities(np.zeros(self.dof_count, dtype=np.float64))
            except Exception:
                pass
            await step_fn()
            pert_pos, pert_quat = self.get_ee_pose()

            jacobian[0:3, i] = (pert_pos - base_pos) / eps_i
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
            jacobian[3:6, i] = 2.0 * q_inc[1:4] / eps_i

        # Restore original joints + step so caller sees a clean state.
        self._articulation.set_joint_positions(joints)
        try:
            self._articulation.set_joint_velocities(np.zeros(self.dof_count, dtype=np.float64))
        except Exception:
            pass
        await step_fn()
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
        a single solve runs for many seconds (otherwise Kit gets killed
        after ~60 s of silence on stdout).
        """
        target_pos = np.asarray(target_pos, dtype=np.float64).flatten()
        target_orient = _normalize_quat(target_orient)

        joints = np.array(self._articulation.get_joint_positions(), dtype=np.float64)
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
                live = np.asarray(self._articulation.get_joint_positions(), dtype=np.float64)
                for li in self._locked:
                    if li < len(joints) and li < len(live):
                        joints[li] = live[li]

            # Apply current joints + step physics so xform cache reflects them.
            self._articulation.set_joint_positions(joints)
            try:
                self._articulation.set_joint_velocities(np.zeros(self.dof_count, dtype=np.float64))
            except Exception:
                pass
            await step_fn()
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
            try:
                delta_q = _compute_dls_step(jacobian, error_vec, self.damping_lambda)
            except np.linalg.LinAlgError:
                break

            # Never command locked (closed-loop) DOFs (belt-and-suspenders on
            # top of their zero Jacobian columns).
            for li in self._locked:
                if li < len(delta_q):
                    delta_q[li] = 0.0

            joints = _clamp_joints_to_limits(joints + delta_q, self._lower_limits, self._upper_limits)

        # Did not converge within max_iterations.
        success = best_pos_err < pos_tol and best_ori_err < orient_tol_rad
        # Restore best joints + step so result reflects best attempt.
        self._articulation.set_joint_positions(best_joints)
        try:
            self._articulation.set_joint_velocities(np.zeros(self.dof_count, dtype=np.float64))
        except Exception:
            pass
        await step_fn()
        try:
            final_pos, final_quat = self.get_ee_pose()
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

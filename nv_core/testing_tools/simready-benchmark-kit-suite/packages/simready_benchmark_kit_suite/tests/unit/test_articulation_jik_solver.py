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
"""Tests for articulation_phases.jik_solver pure-math helpers.

The full ``JacobianIKSolver`` class needs Kit (USD stage + articulation),
so it is exercised only by the manual Kit smoke run. These unit tests
cover the pure module-level helpers (DLS step, joint clamping, pose
error, quaternion utilities) plus the dataclass shape.
"""
import math

import numpy as np
import pytest
from simready_benchmark_kit_suite.articulation_phases.jik_solver import (
    JacobianIKResult,
    _clamp_joints_to_limits,
    _compute_dls_step,
    _normalize_quat,
    _pose_error,
    _quat_multiply,
)

# -----------------------------------------------------------------------------
# JacobianIKResult dataclass
# -----------------------------------------------------------------------------


def test_jacobian_ik_result_round_trips():
    """All fields populate and survive a round trip."""
    pos = np.array([1.0, 2.0, 3.0])
    ori = np.array([1.0, 0.0, 0.0, 0.0])
    joints = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    r = JacobianIKResult(
        success=True,
        iterations=12,
        final_position=pos,
        final_orientation=ori,
        final_pos_error=0.005,
        final_orient_error_deg=1.5,
        converged_joints=joints,
    )
    assert r.success is True
    assert r.iterations == 12
    assert np.array_equal(r.final_position, pos)
    assert np.array_equal(r.final_orientation, ori)
    assert r.final_pos_error == pytest.approx(0.005)
    assert r.final_orient_error_deg == pytest.approx(1.5)
    assert np.array_equal(r.converged_joints, joints)


# -----------------------------------------------------------------------------
# DLS step
# -----------------------------------------------------------------------------


def test_compute_dls_step_returns_correct_shape():
    """A 6 x N Jacobian + length-6 error yields a length-N delta_q."""
    n_joints = 6
    jacobian = np.random.RandomState(0).randn(6, n_joints)
    error = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0])
    dq = _compute_dls_step(jacobian, error, damping_lambda=0.05)
    assert dq.shape == (n_joints,)


def test_compute_dls_step_position_only_2x6_jacobian():
    """A 2 x 6 (or 3 x 6) Jacobian returns the expected length-6 delta."""
    jacobian = np.random.RandomState(42).randn(2, 6)
    error = np.array([0.05, -0.02])
    dq = _compute_dls_step(jacobian, error, damping_lambda=0.05)
    assert dq.shape == (6,)
    # With nonzero error, dq must be nonzero somewhere.
    assert not np.allclose(dq, 0.0)


def test_compute_dls_step_zero_error_yields_zero_delta():
    """No error means no joint update."""
    jacobian = np.random.RandomState(1).randn(6, 4)
    error = np.zeros(6)
    dq = _compute_dls_step(jacobian, error, damping_lambda=0.1)
    assert np.allclose(dq, 0.0)


def test_compute_dls_step_singular_jacobian_falls_back_to_pinv():
    """A rank-deficient Jacobian still produces a delta via pinv fallback."""
    # All columns identical -> J J^T is rank 1 (singular when damping is zero).
    jacobian = np.tile(np.array([[1.0, 0.0, 0.0]]).T, (1, 4)).T.T
    # jacobian shape: (3, 4) all-ones first row -- still solvable with damping.
    # Force a true singular case: all-zero Jacobian + zero damping -> pinv path.
    jacobian = np.zeros((3, 4))
    error = np.array([0.1, 0.0, 0.0])
    dq = _compute_dls_step(jacobian, error, damping_lambda=0.0)
    # pinv of zero matrix is zero matrix -> dq is all zeros, but call must not raise.
    assert dq.shape == (4,)


def test_compute_dls_step_higher_damping_shrinks_delta():
    """Increasing damping decreases the magnitude of the joint update."""
    jacobian = np.random.RandomState(7).randn(6, 5)
    error = np.array([0.1, 0.1, 0.1, 0.0, 0.0, 0.0])
    dq_low = _compute_dls_step(jacobian, error, damping_lambda=0.001)
    dq_high = _compute_dls_step(jacobian, error, damping_lambda=10.0)
    assert np.linalg.norm(dq_high) < np.linalg.norm(dq_low)


# -----------------------------------------------------------------------------
# Joint clamping
# -----------------------------------------------------------------------------


def test_clamp_joints_below_lower():
    """Values below lower bounds get raised to the lower bound."""
    joints = np.array([-5.0, -10.0, 0.0])
    lo = np.array([-1.0, -2.0, -3.0])
    up = np.array([1.0, 2.0, 3.0])
    out = _clamp_joints_to_limits(joints, lo, up)
    assert out[0] == -1.0
    assert out[1] == -2.0
    assert out[2] == 0.0


def test_clamp_joints_above_upper():
    """Values above upper bounds get pulled to the upper bound."""
    joints = np.array([5.0, 10.0, 0.0])
    lo = np.array([-1.0, -2.0, -3.0])
    up = np.array([1.0, 2.0, 3.0])
    out = _clamp_joints_to_limits(joints, lo, up)
    assert out[0] == 1.0
    assert out[1] == 2.0
    assert out[2] == 0.0


def test_clamp_joints_in_range_unchanged():
    """In-range values pass through untouched."""
    joints = np.array([0.5, -1.5, 2.0])
    lo = np.array([-1.0, -2.0, -3.0])
    up = np.array([1.0, 2.0, 3.0])
    out = _clamp_joints_to_limits(joints, lo, up)
    assert np.allclose(out, joints)


def test_clamp_joints_does_not_mutate_input():
    """Original joints array is untouched."""
    joints = np.array([5.0, -5.0])
    lo = np.array([-1.0, -1.0])
    up = np.array([1.0, 1.0])
    _ = _clamp_joints_to_limits(joints, lo, up)
    assert joints[0] == 5.0
    assert joints[1] == -5.0


def test_clamp_joints_handles_inf_limits():
    """Infinite limits act as 'no clamp' on that side."""
    joints = np.array([1e9, -1e9])
    lo = np.array([-math.inf, -math.inf])
    up = np.array([math.inf, math.inf])
    out = _clamp_joints_to_limits(joints, lo, up)
    assert out[0] == 1e9
    assert out[1] == -1e9


# -----------------------------------------------------------------------------
# Pose error
# -----------------------------------------------------------------------------


def test_pose_error_zero_when_poses_match():
    """Identical current and target poses yield zero error."""
    pos = np.array([0.5, 1.0, 1.5])
    quat = np.array([1.0, 0.0, 0.0, 0.0])
    pos_vec, ori_vec, pos_n, ori_n = _pose_error(pos, quat, pos, quat)
    assert np.allclose(pos_vec, 0.0)
    assert np.allclose(ori_vec, 0.0)
    assert pos_n == pytest.approx(0.0)
    assert ori_n == pytest.approx(0.0)


def test_pose_error_position_offset():
    """A pure position offset produces a positive position-error norm."""
    cur_pos = np.array([0.0, 0.0, 0.0])
    tgt_pos = np.array([0.1, 0.2, 0.2])
    quat = np.array([1.0, 0.0, 0.0, 0.0])
    _, _, pos_n, ori_n = _pose_error(cur_pos, quat, tgt_pos, quat)
    assert pos_n == pytest.approx(0.3)
    assert ori_n == pytest.approx(0.0)


def test_pose_error_orientation_offset_90deg_about_x():
    """A 90-deg rotation about X yields ori-error magnitude ~ pi (or ~2*sin(pi/4))."""
    cur_quat = np.array([1.0, 0.0, 0.0, 0.0])
    # 90 deg rotation about X -> w = cos(pi/4), x = sin(pi/4).
    s = math.sin(math.pi / 4.0)
    c = math.cos(math.pi / 4.0)
    tgt_quat = np.array([c, s, 0.0, 0.0])
    pos = np.array([0.0, 0.0, 0.0])
    _, ori_vec, pos_n, ori_n = _pose_error(pos, cur_quat, pos, tgt_quat)
    # ori_vec = 2 * vec(q_target * conj(q_current)) = 2 * (s, 0, 0)
    assert ori_vec[0] == pytest.approx(2.0 * s, abs=1e-9)
    assert ori_n == pytest.approx(2.0 * s, abs=1e-9)
    assert pos_n == pytest.approx(0.0)


def test_pose_error_quaternion_double_cover_uses_short_path():
    """Negating the target quat (same rotation) yields the same error sign."""
    cur_quat = np.array([1.0, 0.0, 0.0, 0.0])
    s = math.sin(math.pi / 4.0)
    c = math.cos(math.pi / 4.0)
    tgt_quat_pos = np.array([c, s, 0.0, 0.0])
    tgt_quat_neg = -tgt_quat_pos  # represents the SAME rotation
    pos = np.array([0.0, 0.0, 0.0])
    _, ori_vec_pos, _, _ = _pose_error(pos, cur_quat, pos, tgt_quat_pos)
    _, ori_vec_neg, _, _ = _pose_error(pos, cur_quat, pos, tgt_quat_neg)
    # Both should give the same shorter-rotation error.
    assert np.allclose(ori_vec_pos, ori_vec_neg)


# -----------------------------------------------------------------------------
# Quaternion helpers
# -----------------------------------------------------------------------------


def test_quat_multiply_identity():
    """Multiplying by identity is a no-op."""
    q = np.array([0.5, 0.5, 0.5, 0.5])
    identity = np.array([1.0, 0.0, 0.0, 0.0])
    out = _quat_multiply(q, identity)
    assert np.allclose(out, q)


def test_normalize_quat_unit_length():
    """Normalized quaternion has unit norm."""
    q = np.array([3.0, 0.0, 4.0, 0.0])
    out = _normalize_quat(q)
    assert float(np.linalg.norm(out)) == pytest.approx(1.0)


def test_normalize_quat_zero_returns_input():
    """Zero quaternion is returned unchanged (no division by zero)."""
    q = np.zeros(4)
    out = _normalize_quat(q)
    assert np.array_equal(out, q)

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
"""Tests for articulation_phases.ik_targets (algorithmic core)."""

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.ik_targets import (
    IKTarget,
    LegendCounts,
    _fibonacci_sphere_points,
    _interleave_targets,
    _order_for_max_movement,
    generate_ik_targets,
    generate_scara_ik_targets,
)

# -----------------------------------------------------------------------------
# Fibonacci sphere
# -----------------------------------------------------------------------------


def test_fibonacci_sphere_returns_n_points():
    """A request for N points returns a list of length N."""
    pts = _fibonacci_sphere_points(25, hemisphere_only=False)
    assert len(pts) == 25
    for p in pts:
        assert isinstance(p, np.ndarray)
        assert p.shape == (3,)


def test_fibonacci_sphere_unit_vectors_full_sphere():
    """All generated vectors are on the unit sphere."""
    pts = _fibonacci_sphere_points(40, hemisphere_only=False)
    for p in pts:
        assert abs(float(np.linalg.norm(p)) - 1.0) < 1e-9


def test_fibonacci_sphere_hemisphere_only_has_nonneg_z():
    """When hemisphere_only=True, no point has negative Z."""
    pts = _fibonacci_sphere_points(50, hemisphere_only=True)
    assert len(pts) == 50
    for p in pts:
        assert p[2] >= 0.0
        # After hemisphere mirroring the magnitude is still 1 because we only
        # flip the sign of z which preserves |v|.
        assert abs(float(np.linalg.norm(p)) - 1.0) < 1e-9


def test_fibonacci_sphere_zero_or_negative_returns_empty():
    assert _fibonacci_sphere_points(0) == []
    assert _fibonacci_sphere_points(-3) == []


def test_fibonacci_sphere_is_deterministic():
    """Same n produces identical points across calls."""
    a = _fibonacci_sphere_points(17, hemisphere_only=True)
    b = _fibonacci_sphere_points(17, hemisphere_only=True)
    assert len(a) == len(b)
    for pa, pb in zip(a, b):
        assert np.allclose(pa, pb)


# -----------------------------------------------------------------------------
# Farthest-next ordering
# -----------------------------------------------------------------------------


def test_order_for_max_movement_short_inputs():
    assert _order_for_max_movement([]) == []
    only = [np.array([1.0, 2.0, 3.0])]
    out = _order_for_max_movement(only)
    assert len(out) == 1
    assert np.allclose(out[0], only[0])


def test_order_for_max_movement_consecutive_far_apart():
    """Consecutive points after ordering are spread out for typical inputs."""
    # 30 evenly-spread points on the unit hemisphere (diameter ~= 2.0).
    points = _fibonacci_sphere_points(30, hemisphere_only=False)
    ordered = _order_for_max_movement(points)
    assert len(ordered) == len(points)

    # Compute mean consecutive distance and require it to be substantially
    # larger than the average pairwise nearest-neighbor distance of the input
    # set. For a Fibonacci sphere of 30 points the mean nearest-neighbor
    # distance is ~0.45; farthest-next ordering should produce hops well
    # above 1.0 on average.
    consecutive = [float(np.linalg.norm(ordered[i + 1] - ordered[i])) for i in range(len(ordered) - 1)]
    assert np.mean(consecutive) >= 1.0


def test_order_for_max_movement_preserves_set_membership():
    """Ordering only permutes points; no point is dropped or invented."""
    points = _fibonacci_sphere_points(8, hemisphere_only=True)
    ordered = _order_for_max_movement(points)
    assert len(ordered) == len(points)
    # Each ordered point must match exactly one input point.
    for op in ordered:
        match = sum(1 for p in points if np.allclose(p, op))
        assert match == 1


# -----------------------------------------------------------------------------
# Interleave
# -----------------------------------------------------------------------------


def _mk(idx, reachable):
    return IKTarget(position=np.array([float(idx), 0.0, 0.0]), is_reachable=reachable, index=idx)


def test_interleave_targets_pattern_4_reachable_2_oor():
    r = [_mk(i, True) for i in range(1, 5)]  # r1..r4
    o = [_mk(i, False) for i in range(101, 103)]  # o1, o2
    out = _interleave_targets(r, o)
    flags = [t.is_reachable for t in out]
    # interval = max(1, 4 // (2 + 1)) = 1, so an OOR is appended after every
    # reachable until the OOR list is exhausted, then trailing reachables.
    # Expected pattern: r o r o r r
    assert flags == [True, False, True, False, True, True]
    # Total length is reachable + out_of_reach.
    assert len(out) == 6


def test_interleave_targets_only_reachable():
    r = [_mk(i, True) for i in range(3)]
    out = _interleave_targets(r, [])
    assert [t.is_reachable for t in out] == [True, True, True]


def test_interleave_targets_only_out_of_reach():
    o = [_mk(i, False) for i in range(2)]
    out = _interleave_targets([], o)
    assert [t.is_reachable for t in out] == [False, False]


# -----------------------------------------------------------------------------
# IKTarget dataclass round-trip
# -----------------------------------------------------------------------------


def test_iktarget_dataclass_roundtrip():
    pos = np.array([1.5, -2.0, 3.25], dtype=np.float64)
    t = IKTarget(position=pos, is_reachable=True, index=7)
    assert np.allclose(t.position, pos)
    assert t.is_reachable is True
    assert t.index == 7

    t2 = IKTarget(position=np.array([0.0, 0.0, 0.0]), is_reachable=False, index=0)
    assert t2.is_reachable is False
    assert t2.index == 0


def test_legend_counts_as_tuple():
    lc = LegendCounts(pending=22, reached=3, solve_failed=1, motion_failed=0, out_of_reach=2)
    assert lc.as_tuple() == (22, 3, 1, 0, 2)
    # Default-constructed counts are all zero.
    assert LegendCounts().as_tuple() == (0, 0, 0, 0, 0)


# -----------------------------------------------------------------------------
# generate_ik_targets invariants
# -----------------------------------------------------------------------------


def test_generate_ik_targets_counts_and_radii():
    base = np.array([1.0, 2.0, 0.5])
    reach = 0.8
    radius_factors = (0.5, 0.7, 0.9)
    out_of_reach_factor = 1.3
    num_reachable = 22
    num_out_of_reach = 3

    targets = generate_ik_targets(
        robot_reach=reach,
        base_position=base,
        num_reachable=num_reachable,
        num_out_of_reach=num_out_of_reach,
        radius_factors=radius_factors,
        out_of_reach_factor=out_of_reach_factor,
        hemisphere_only=True,
    )

    assert len(targets) == num_reachable + num_out_of_reach

    max_in_reach = reach * max(radius_factors)
    min_oor = reach * out_of_reach_factor
    eps = 1e-6

    n_reach = 0
    n_oor = 0
    for t in targets:
        d = float(np.linalg.norm(t.position - base))
        if t.is_reachable:
            assert d <= max_in_reach + eps, "Reachable target distance %.4f exceeds max in-reach radius %.4f" % (
                d,
                max_in_reach,
            )
            n_reach += 1
        else:
            assert d >= min_oor - eps, "Out-of-reach target distance %.4f below out-of-reach radius %.4f" % (d, min_oor)
            n_oor += 1

    assert n_reach == num_reachable
    assert n_oor == num_out_of_reach

    # Final indices must be a contiguous 0..N-1 sequence in order.
    assert [t.index for t in targets] == list(range(len(targets)))


def test_generate_ik_targets_hemisphere_keeps_z_above_base():
    base = np.array([0.0, 0.0, 0.0])
    reach = 1.0
    targets = generate_ik_targets(
        robot_reach=reach,
        base_position=base,
        num_reachable=12,
        num_out_of_reach=2,
        hemisphere_only=True,
    )
    # Hemisphere-only generation has unit vectors with z >= 0, scaled and
    # offset by base -- so target z must be >= base z.
    for t in targets:
        assert t.position[2] >= base[2] - 1e-9


def test_generate_ik_targets_empty_when_zero_counts():
    out = generate_ik_targets(
        robot_reach=1.0,
        base_position=np.array([0.0, 0.0, 0.0]),
        num_reachable=0,
        num_out_of_reach=0,
    )
    assert out == []


def test_generate_ik_targets_only_out_of_reach():
    base = np.array([0.0, 0.0, 0.0])
    reach = 1.0
    out = generate_ik_targets(
        robot_reach=reach,
        base_position=base,
        num_reachable=0,
        num_out_of_reach=4,
        out_of_reach_factor=1.5,
    )
    assert len(out) == 4
    for t in out:
        assert t.is_reachable is False
        d = float(np.linalg.norm(t.position - base))
        assert abs(d - reach * 1.5) < 1e-9


# -----------------------------------------------------------------------------
# SCARA generator -- light invariants
# -----------------------------------------------------------------------------


def test_generate_scara_ik_targets_invariants():
    base = np.array([0.0, 0.0, 0.0])
    ee = np.array([0.6, 0.0, 0.4])
    z_limits = (-0.1, 0.1)
    targets = generate_scara_ik_targets(
        robot_reach=1.0,
        base_position=base,
        ee_position=ee,
        z_limits=z_limits,
        num_reachable=5,
        num_out_of_reach=2,
        out_of_reach_factor=1.3,
    )
    assert len(targets) == 7
    n_reach = sum(1 for t in targets if t.is_reachable)
    n_oor = sum(1 for t in targets if not t.is_reachable)
    assert n_reach == 5
    assert n_oor == 2

    # Out-of-reach targets sit on a horizontal ring at robot_reach * factor in XY.
    for t in targets:
        if not t.is_reachable:
            xy = float(np.linalg.norm(t.position[:2] - base[:2]))
            assert abs(xy - 1.3) < 1e-6

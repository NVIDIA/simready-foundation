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
"""Tests for multi_joint_coordination pure helpers."""
import math
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_targets import (
    bounded_joint_range,
    joint_is_angular,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.multi_joint_coordination import (
    _run_iteration,
    aggregate_mjc_summary,
    compute_factor_target,
    get_defaults,
    run_multi_joint_coordination,
)


def test_defaults_shape():
    d = get_defaults()
    assert d["num_iterations"] == 3
    assert d["target_factors"] == [0.3, 0.6, 0.5]
    assert d["position_tolerance_deg"] == 1.0
    assert d["target_margin_ratio"] == 0.10
    assert d["capture_fps"] == 15


def test_compute_factor_target_at_low_factor():
    # range [-1, 1], margin 0.10 -> [-0.8, 0.8], factor 0.0 -> -0.8
    assert abs(compute_factor_target(-1.0, 1.0, 0.10, 0.0) - (-0.8)) < 1e-9


def test_compute_factor_target_at_high_factor():
    assert abs(compute_factor_target(-1.0, 1.0, 0.10, 1.0) - 0.8) < 1e-9


def test_compute_factor_target_midpoint():
    assert abs(compute_factor_target(-1.0, 1.0, 0.10, 0.5) - 0.0) < 1e-9


def test_compute_factor_target_v1_factors():
    # V1 default factors land within [-0.8, 0.8] for symmetric range.
    for f in (0.3, 0.6, 0.5):
        t = compute_factor_target(-1.0, 1.0, 0.10, f)
        assert -0.8 <= t <= 0.8


def test_compute_factor_target_collapses_when_margin_too_large():
    # margin 0.5 across range 1.0 -> span <= 0 -> midpoint
    assert abs(compute_factor_target(0.0, 1.0, 0.5, 0.3) - 0.5) < 1e-9


@pytest.mark.parametrize("bounds", [(1.0e308, 1.1e308), (-1.1e308, -1.0e308)])
def test_compute_factor_target_collapsed_extreme_finite_range_stays_finite(bounds):
    target = compute_factor_target(*bounds, 0.5, 0.5)
    assert math.isfinite(target)
    assert bounds[0] <= target <= bounds[1]
    assert target == pytest.approx(bounds[0] + (bounds[1] - bounds[0]) * 0.5)


def test_aggregate_mjc_summary_all_pass():
    per_iter = [
        {"iteration": 0, "ok": True, "converged_count": 6, "errors": []},
        {"iteration": 1, "ok": True, "converged_count": 6, "errors": []},
        {"iteration": 2, "ok": True, "converged_count": 6, "errors": []},
    ]
    s = aggregate_mjc_summary(per_iter)
    assert s["iterations_passed"] == 3
    assert s["iterations_failed"] == 0
    assert s["failed_iterations"] == []


def test_aggregate_mjc_summary_partial():
    per_iter = [
        {"iteration": 0, "ok": True, "converged_count": 6, "errors": []},
        {"iteration": 1, "ok": False, "converged_count": 4, "errors": []},
        {"iteration": 2, "ok": True, "converged_count": 6, "errors": []},
    ]
    s = aggregate_mjc_summary(per_iter)
    assert s["iterations_passed"] == 2
    assert s["iterations_failed"] == 1
    assert s["failed_iterations"] == [1]


@pytest.mark.parametrize("bounds", [(-math.inf, math.inf), (-3.402823e38, 3.402823e38)])
def test_mjc_unlimited_angular_targets_are_local_and_finite(bounds):
    target = compute_factor_target(*bounds, 0.1, 0.3, center=1.25, angular=True)
    assert 1.25 - math.pi < target < 1.25 + math.pi
    with pytest.raises(ValueError, match="safe target"):
        compute_factor_target(*bounds, 0.1, 0.3, center=1.25)


@pytest.mark.parametrize("bounds,center", [((-math.inf, 0.1), 0.0), ((0.5, math.inf), 0.75), ((0.5, math.inf), 0.0)])
def test_angular_one_sided_ranges_retain_the_real_stop(bounds, center):
    for factor in (0.0, 0.3, 0.5, 1.0):
        target = compute_factor_target(*bounds, 0.1, factor, center=center, angular=True)
        assert bounds[0] <= target <= bounds[1]


@pytest.mark.parametrize("lo,hi", [(float("nan"), 1), (1, 0), (0, 0), (math.inf, math.inf)])
def test_malformed_ranges_are_not_unlimited(lo, hi):
    assert bounded_joint_range(lo, hi, 0, angular=True) is None


@pytest.mark.parametrize("limit", [1.0e12, 1.0e38])
def test_real_large_finite_limits_are_not_float32_sentinels(limit):
    assert bounded_joint_range(-limit, limit, 0, angular=True) == (-limit, limit)


def test_joint_type_is_explicit_and_unique_inside_asset():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joints/rotate")
    UsdPhysics.PrismaticJoint.Define(stage, "/Asset/joints/slide")
    UsdPhysics.RevoluteJoint.Define(stage, "/Other/slide")
    scene = {"asset_prim": root}
    assert joint_is_angular(scene, "rotate")
    assert not joint_is_angular(scene, "slide")
    assert not joint_is_angular(scene, "missing")
    UsdPhysics.RevoluteJoint.Define(stage, "/Asset/duplicate/rotate")
    assert not joint_is_angular(scene, "rotate")


@pytest.mark.asyncio
async def test_iteration_metrics_reuse_required_readback_without_diagnostic_read(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        multi_joint_coordination as phase,
    )

    reads = []
    metrics = {}
    warnings = []

    def read_positions():
        reads.append(True)
        return np.array([0.0])

    async def step():
        pass

    async def capture(**kwargs):
        return None

    robot = SimpleNamespace(
        get_joint_positions=read_positions, dof_count=1, set_joint_position_targets=lambda value: None
    )
    ctx = SimpleNamespace(
        step_one=step,
        capture_frame=capture,
        step=lambda message: None,
        add_metric=lambda key, value: metrics.__setitem__(key, value),
        warn=warnings.append,
        scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None),
    )
    monkeypatch.setattr(phase, "compute_world_aligned_bbox", lambda prim: None)
    monkeypatch.setattr(phase, "check_bbox_explode", lambda *args: None)
    ok, _, _ = await _run_iteration(
        ctx,
        robot,
        {},
        [{"index": 0, "name": "j", "lower": -1, "upper": 1}],
        0.75,
        0,
        0.01,
        2,
        1,
        [],
        None,
        10,
        0.1,
        240,
        1,
    )
    assert not ok
    assert len(reads) == 3  # initial + existing two post-step reads only
    record = metrics["mjc_iteration_0_joints"][0]
    assert record["final_position"] == 0.0 and record["target"] == pytest.approx(0.4)
    assert record["entered_tolerance"] is False
    assert "joints never entered tolerance" in warnings[0]


@pytest.mark.asyncio
async def test_mjc_inapplicable_empty_articulation_does_not_require_live_state():
    context = SimpleNamespace(skip_message=None)
    context.step = context.warn = lambda message: None
    context.add_metric = lambda key, value: None
    context.skip = lambda message: setattr(context, "skip_message", message)

    def forbidden_read():
        raise AssertionError("inapplicable articulation must not perform a verdict read")

    robot = SimpleNamespace(
        dof_names=[], get_joint_position_limits=lambda: ([], []), get_joint_positions=forbidden_read
    )
    await run_multi_joint_coordination(context, robot, {}, {})
    assert context.skip_message is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [math.inf, 3.402823e38])
async def test_mjc_skip_reports_qualified_unbounded_angular_excursion_not_finite_limits(limit):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joint")
    metrics, skipped = {}, []
    context = SimpleNamespace(
        step=lambda message: None,
        warn=lambda message: None,
        add_metric=lambda key, value: metrics.__setitem__(key, value),
        skip=skipped.append,
    )
    robot = SimpleNamespace(
        dof_names=["joint"],
        get_joint_position_limits=lambda: ([-limit], [limit]),
        get_joint_positions=lambda: pytest.fail("inapplicable coordination must not read required state"),
    )
    await run_multi_joint_coordination(context, robot, {"asset_prim": root}, {})
    assert metrics["mjc_valid_joints"] == 1 and len(skipped) == 1
    assert "1/1 joints with qualified bounded excursions" in skipped[0]
    assert "unbounded revolute" in skipped[0] and "local +/-pi" in skipped[0]
    assert "with finite position limits" not in skipped[0]
    assert "so it cannot participate" not in skipped[0]

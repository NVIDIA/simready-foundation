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

import asyncio
import math
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_targets import (
    bounded_joint_range,
)


def _iteration(monkeypatch, limits, start, factor, *, dtype=np.float64, angular=False, frames=1):
    lo, hi = limits
    initial = np.array([-0.0, start, 42.125], dtype=dtype)
    position = initial.copy()
    reads = []
    commands = []
    steps = []
    metrics = {}
    warnings = []
    bounds = bounded_joint_range(lo, hi, float(initial[1]), angular=angular)
    assert bounds is not None

    def read_positions():
        reads.append(True)
        return position.copy()

    def command(targets):
        nonlocal position
        assert targets.dtype.kind == "f"
        assert bounds[0] <= targets[1] <= bounds[1]
        assert np.array_equal(targets[[0, 2]], initial[[0, 2]])
        assert np.signbit(targets[0]) == np.signbit(initial[0])
        commands.append(targets.copy())
        position = targets.copy()

    async def step():
        steps.append(True)

    async def capture(**_kwargs):
        return None

    robot = SimpleNamespace(dof_count=3, get_joint_positions=read_positions, set_joint_position_targets=command)
    ctx = SimpleNamespace(
        step_one=step,
        capture_frame=capture,
        step=lambda _message: None,
        warn=warnings.append,
        add_metric=lambda name, value: metrics.update({name: value}),
        scene=SimpleNamespace(update_camera_follow=lambda **_kwargs: None),
    )
    monkeypatch.setattr(mjc, "compute_world_aligned_bbox", lambda _prim: None)
    monkeypatch.setattr(mjc, "check_bbox_explode", lambda *_args: None)
    result = asyncio.run(
        mjc._run_iteration(
            ctx,
            robot,
            {},
            [{"index": 1, "name": "selected", "lower": lo, "upper": hi, "angular": angular}],
            factor=factor,
            iteration_idx=0,
            pos_tol_rad=0.0,
            max_frames=frames,
            capture_interval=1,
            capture_frames=[],
            baseline_bbox=None,
            bbox_ratio_limit=10.0,
            margin_ratio=0.0,
            physics_fps=240.0,
            motion_frames=frames,
        )
    )
    assert result == (True, {"selected"}, [])
    assert len(commands) == len(steps) == frames
    assert len(reads) == frames + 1  # Existing initial and post-step reads only.
    assert not warnings
    return commands, metrics, bounds


@pytest.mark.parametrize(
    ("limits", "start"),
    [
        ((-3.14159, 3.14159), -3.139705046),
        ((-math.pi / 2, 1.5 * math.pi), -math.pi / 2 + 0.001),
        ((0.2, 12.3), 0.20001),
        ((-12.3, -0.2), -12.29999),
    ],
)
@pytest.mark.parametrize("factor", [0.0, 1.0])
@pytest.mark.parametrize("frames", [1, 5])
def test_actual_ramp_and_endpoint_commands_remain_legal(monkeypatch, limits, start, factor, frames):
    if factor == 0.0:
        start = limits[1] - (start - limits[0])
    commands, metrics, _bounds = _iteration(monkeypatch, limits, start, factor, frames=frames)
    expected = limits[int(factor)]
    assert commands[-1][1] == expected
    assert metrics["mjc_iteration_0_joints"][0]["target"] == expected


@pytest.mark.parametrize("dtype", [np.float32, np.int32])
def test_floating_command_construction_does_not_truncate_or_round_goals_past_stops(monkeypatch, dtype):
    limits = (-1.0, 0.3)
    commands, metrics, _bounds = _iteration(monkeypatch, limits, 0.0, 1.0, dtype=dtype)
    assert commands[-1][1] == 0.3
    assert metrics["mjc_iteration_0_joints"][0]["target"] == 0.3


@pytest.mark.parametrize(
    ("limits", "start"),
    [
        ((-math.inf, math.inf), 1.25),
        ((-float.fromhex("0x1.fffffep+127"), float.fromhex("0x1.fffffep+127")), 1.25),
        ((-math.inf, 0.1), 0.0),
        ((0.5, math.inf), 0.75),
        ((0.5, float.fromhex("0x1.fffffep+127")), 0.75),
    ],
)
@pytest.mark.parametrize("factor", [0.0, 1.0])
def test_qualified_unbounded_and_one_sided_policy_is_preserved(monkeypatch, limits, start, factor):
    commands, _metrics, bounds = _iteration(monkeypatch, limits, start, factor, angular=True, frames=5)
    assert commands[-1][1] == bounds[int(factor)]
    for targets in commands:
        assert limits[0] <= targets[1] <= limits[1]
        assert bounds[0] <= targets[1] <= bounds[1]

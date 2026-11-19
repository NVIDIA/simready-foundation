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
from importlib import import_module
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import full_range_sweep as frs


def _parameters(lo, hi, *, cap=math.tau, margin=0.1):
    return frs.compute_sweep_parameters(
        lo,
        hi,
        margin_ratio=margin,
        max_sweep_range=cap,
        speed_scale=1.0,
        pause_seconds=0.5,
        physics_fps=240.0,
        joint_name="joint_5_b",
    )


def test_default_cap_is_a_precise_full_turn():
    assert frs.get_defaults()["max_sweep_range"] == math.tau


def test_registration_version_and_defaults_match_the_pending_procedure():
    registration = import_module("simready.foundation.tier_core.runtime_tests.fet022_driven_joints.full_range_sweep")
    assert registration.FULL_RANGE_SWEEP_KWARGS["version"] == "1.5.6"
    assert registration.FULL_RANGE_SWEEP_KWARGS["config_defaults"]["max_sweep_range"] == math.tau


@pytest.mark.parametrize("cap", [math.tau, 2 * 3.14159])
@pytest.mark.parametrize(
    ("lower_degrees", "upper_degrees", "expected_degrees"),
    [
        (-90.0, 270.0, (-54.0, 234.0)),
        (-270.0, 90.0, (-234.0, 54.0)),
        (90.0, 450.0, (126.0, 414.0)),
        (-450.0, -90.0, (-414.0, -126.0)),
    ],
)
@pytest.mark.parametrize("import_float32", [False, True])
def test_offset_full_turn_keeps_the_imported_interval(
    cap, lower_degrees, upper_degrees, expected_degrees, import_float32
):
    limits = np.radians([lower_degrees, upper_degrees])
    if import_float32:
        limits = limits.astype(np.float32)
    lo, hi = map(float, limits)
    params = _parameters(lo, hi, cap=cap)
    assert math.degrees(params["min_target"]) == pytest.approx(expected_degrees[0], abs=1e-5)
    assert math.degrees(params["max_target"]) == pytest.approx(expected_degrees[1], abs=1e-5)
    # The cap tolerance preserves this specific imported interval, not just
    # endpoints vaguely close to the intended full turn.
    assert params["min_target"] == pytest.approx(lo + 0.1 * (hi - lo), abs=1e-12)
    assert params["max_target"] == pytest.approx(hi - 0.1 * (hi - lo), abs=1e-12)
    for name in ("min_target", "max_target", "zero_target"):
        assert lo <= params[name] <= hi


@pytest.mark.parametrize(
    ("lower_degrees", "upper_degrees", "expected_degrees"),
    [
        (-90.0, 630.0, (-54.0, 234.0)),
        (-630.0, 90.0, (-234.0, 54.0)),
        (90.0, 810.0, (126.0, 414.0)),
        (-810.0, -90.0, (-414.0, -126.0)),
        (-720.0, 720.0, (-144.0, 144.0)),
    ],
)
def test_genuine_cap_shifts_its_window_inside_asymmetric_limits(lower_degrees, upper_degrees, expected_degrees):
    lo, hi = map(math.radians, (lower_degrees, upper_degrees))
    params = _parameters(lo, hi)
    assert math.degrees(params["min_target"]) == pytest.approx(expected_degrees[0])
    assert math.degrees(params["max_target"]) == pytest.approx(expected_degrees[1])
    assert params["max_target"] - params["min_target"] == pytest.approx(0.8 * math.tau)
    for name in ("min_target", "max_target", "zero_target"):
        assert lo <= params[name] <= hi


@pytest.mark.parametrize("cap", [0.0, -1.0])
@pytest.mark.parametrize("limits", [(-2.0, 8.0), (1.0, 1.002), (-1.002, -1.0)])
def test_disabled_cap_and_narrow_ranges_preserve_legal_insets(cap, limits):
    lo, hi = limits
    params = _parameters(lo, hi, cap=cap)
    assert params["min_target"] == pytest.approx(lo + 0.1 * (hi - lo))
    assert params["max_target"] == pytest.approx(hi - 0.1 * (hi - lo))
    assert lo <= params["zero_target"] <= hi


@pytest.mark.parametrize("margin", [0.0, 0.1, 0.49])
@pytest.mark.parametrize("cap", [0.0, 2 * 3.14159, math.tau, 1.0])
@pytest.mark.parametrize(
    "limits", [(-math.pi / 2, 1.5 * math.pi), (-9.0, 0.3), (0.2, 12.0), (-12.0, -0.2), (-0.001, 0.002)]
)
def test_every_segment_command_stays_legal_from_a_valid_start(margin, cap, limits):
    lo, hi = limits
    params = _parameters(lo, hi, cap=cap, margin=margin)
    assert lo <= params["min_target"] <= params["max_target"] <= hi
    for start in (lo, hi, min(hi, max(lo, 0.0))):
        for seg_start, seg_end, _name in frs.build_sweep_segments(start, params):
            assert lo <= seg_start <= hi
            assert lo <= seg_end <= hi
            for profile in ("linear", "smoothstep", "smootherstep", "trapezoidal"):
                for t in (0.0, 0.1, 0.5, 0.9, 1.0):
                    alpha = frs.interpolate_profile(profile, t)
                    command = frs.interpolate_sweep_target(seg_start, seg_end, alpha, lo, hi)
                    assert lo <= command <= hi


@pytest.mark.parametrize("margin", [-0.1, 0.5, 1.0, float("nan"), float("inf")])
def test_invalid_margins_do_not_produce_unsafe_or_zero_excursion_targets(margin):
    with pytest.raises(ValueError, match="sweep_margin_ratio"):
        _parameters(-1.0, 1.0, margin=margin)


@pytest.mark.parametrize("cap", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_caps_are_rejected(cap):
    with pytest.raises(ValueError, match="max_sweep_range"):
        _parameters(-1.0, 1.0, cap=cap)


@pytest.mark.parametrize(
    "limits", [(0.0, 0.0), (1.0, -1.0), (float("nan"), 1.0), (-1.0, float("inf")), (-1e308, 1e308)]
)
def test_invalid_runtime_limits_are_rejected(limits):
    with pytest.raises(ValueError, match="position"):
        _parameters(*limits)


@pytest.mark.parametrize("cap", [None, 2 * 3.14159, math.tau, 1.0])
@pytest.mark.parametrize("margin", [0.0, 0.1])
@pytest.mark.parametrize("limits", [(-math.pi / 2, 1.5 * math.pi), (-9.0, 0.3), (0.2, 12.0)])
def test_runtime_phase_never_issues_out_of_range_commands(monkeypatch, cap, margin, limits):
    """Exercise the actual command/hold path, including omitted-cap fallback."""
    lo, hi = limits
    commands = []
    position = [min(hi, max(lo, 0.0))]

    def issue(index, target):
        assert index == 0
        assert lo <= target <= hi
        commands.append(target)
        position[0] = target

    robot = SimpleNamespace(
        dof_names=["joint_5_b"],
        dof_count=1,
        get_joint_position_limits=lambda: (np.array([lo]), np.array([hi])),
        get_joint_positions=lambda: np.array(position),
        set_joint_position_target=issue,
    )

    async def no_steps(*_args, **_kwargs):
        return None

    def no_log(*_args, **_kwargs):
        return None

    def fail(message):
        raise AssertionError(message)

    metrics = {}
    ctx = SimpleNamespace(
        add_metric=lambda name, value: metrics.update({name: value}),
        step=no_log,
        log=no_log,
        warn=fail,
        skip=fail,
        fail=fail,
        physics_steps=no_steps,
        step_one=no_steps,
        capture_frame=no_steps,
        scene=SimpleNamespace(update_camera_follow=no_log),
    )
    monkeypatch.setattr(frs, "compute_world_aligned_bbox", lambda _prim: SimpleNamespace(volume=1.0))
    monkeypatch.setattr(frs, "check_bbox_explode", lambda *_args: None)
    history = import_module("simready.foundation.tier_core.runtime_tests.articulation_phases.motion_history")
    monkeypatch.setattr(
        history,
        "make_joint_observer",
        lambda *_args, **_kwargs: SimpleNamespace(history=None, finish=no_log),
    )
    config = {
        "physics_fps": 4,
        "capture_fps": 4,
        "settle_seconds": 0,
        "sweep_speed_scale": 2,
        "pause_at_limits_seconds": 0.25,
        "sweep_margin_ratio": margin,
    }
    if cap is not None:
        config["max_sweep_range"] = cap
    asyncio.run(frs.run_full_range_sweep(ctx, robot, {}, config))
    assert len(commands) == 9
    assert metrics["frs_joints_passed"] == 1
    assert metrics["frs_joints_failed"] == 0
    if cap in (None, 2 * 3.14159, math.tau) and limits == (-math.pi / 2, 1.5 * math.pi):
        assert max(commands) == pytest.approx(hi - margin * (hi - lo))
        assert min(commands) == pytest.approx(lo + margin * (hi - lo))

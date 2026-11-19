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
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    coordination_timing as timing,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
    resolve_velocity_hints,
)


def _joints(count=2):
    return [{"name": "joint_%d" % i, "index": i, "lower": -1.0, "upper": 1.0} for i in range(count)]


def test_shared_smoothstep_pacing_uses_slowest_joint_and_preserves_hold():
    policy = timing.CoordinationTiming(mjc.get_defaults())
    plan = policy.plan_iteration([0, 0], [1, 0.5], _joints(), [(10, "native"), (0.1, "native")])
    assert plan["ramp_seconds"] == pytest.approx(9.625)
    assert plan["hold_seconds"] == 6
    assert plan["observation_seconds"] == pytest.approx(15.625)
    for row in plan["joints"]:
        assert row["estimated_command_peak_speed"] <= row["velocity_hint"] * 0.8


def test_each_iteration_uses_current_start_not_preceding_requested_goal():
    policy = timing.CoordinationTiming(mjc.get_defaults())
    first = policy.plan_iteration([0, 0], [0.1, 0.1], _joints(), [(0.1, "native")] * 2)
    second = policy.plan_iteration([-0.5, -0.5], [0.1, 0.1], _joints(), [(0.1, "native")] * 2)
    assert first["ramp_seconds"] == 2.125
    assert second["joints"][0]["displacement"] == pytest.approx(0.6)
    assert second["ramp_seconds"] == 11.5


@pytest.mark.parametrize("fps", [23.4, 30.3, 239.8])
def test_fractional_tick_rounding_never_shortens_ramp_or_double_rounds_fallback(fps):
    policy = timing.CoordinationTiming({**mjc.get_defaults(), "physics_fps": fps})
    base = policy.plan_iteration([0, 0], [1, 1], _joints(), [(None, "fallback")] * 2)
    assert base["ramp_frames"] == math.ceil(2 * fps)
    adapted = policy.plan_iteration([0, 0], [1, 1], _joints(), [(0.2, "native")] * 2)
    expected = 1.5 / (0.2 * 0.8) + 0.25
    assert expected <= adapted["ramp_seconds"] < expected + 1 / fps + 1e-12


@pytest.mark.parametrize("value", [None, [True, True], ["2", "2"], [math.nan, math.inf], [[1], [1]], [1]])
def test_malformed_optional_speed_values_use_explicit_fallback(value):
    robot = SimpleNamespace(dof_names=["a", "b"], get_joint_velocity_limits=lambda: value)
    hints = resolve_velocity_hints(robot, {})
    plan = timing.CoordinationTiming(mjc.get_defaults()).plan_iteration([0, 0], [1, 1], _joints(), hints)
    assert plan["ramp_seconds"] == 2
    assert all(
        row["velocity_hint"] is None and row["velocity_hint_source"] == "configured fallback duration"
        for row in plan["joints"]
    )


def test_absent_speed_getter_uses_explicit_fallback():
    assert (
        resolve_velocity_hints(SimpleNamespace(dof_names=["a", "b"]), {})
        == [(None, "configured fallback duration")] * 2
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("coordination_speed_scale", 0),
        ("coordination_speed_scale", 1.01),
        ("coordination_speed_scale", True),
        ("coordination_speed_scale", "0.8"),
        ("coordination_settling_allowance_seconds", -0.1),
        ("coordination_settling_allowance_seconds", math.nan),
        ("max_coordination_ramp_seconds", 0),
        ("max_coordination_ramp_seconds", math.inf),
        ("max_settling_seconds", 1),
        ("motion_seconds", math.nan),
    ],
)
def test_invalid_policy_rejected_before_physics(key, value):
    with pytest.raises(ValueError):
        timing.CoordinationTiming({**mjc.get_defaults(), key: value})


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_coordination_simulation_seconds", 0),
        ("max_coordination_simulation_seconds", math.inf),
        ("max_coordination_wall_seconds", 3541),
        ("max_coordination_wall_seconds", True),
    ],
)
def test_invalid_execution_budget_rejected(key, value):
    with pytest.raises(ValueError):
        timing.CoordinationBudget({**mjc.get_defaults(), key: value})


def test_guard_rejects_too_slow_or_underflowing_speed_without_shortening():
    policy = timing.CoordinationTiming(mjc.get_defaults())
    with pytest.raises(RuntimeError, match="execution budget is insufficient"):
        policy.plan_iteration([0, 0], [1, 1], _joints(), [(0.001, "native")] * 2)
    policy = timing.CoordinationTiming({**mjc.get_defaults(), "coordination_speed_scale": 1e-300})
    with pytest.raises(RuntimeError, match="execution budget is insufficient"):
        policy.plan_iteration([0, 0], [1, 1], _joints(), [(1e-300, "native")] * 2)


def test_overflowing_displacement_cannot_become_an_asset_verdict():
    policy = timing.CoordinationTiming(mjc.get_defaults())
    with pytest.raises(ValueError, match="displacement must be finite"):
        policy.plan_iteration([-1e308, 0], [1e308, 0], _joints(), [(None, "fallback")] * 2)


def test_timing_joint_rows_are_bounded_without_ignoring_omitted_slow_joint():
    count = timing.MAX_TIMING_JOINTS + 1
    policy = timing.CoordinationTiming(mjc.get_defaults())
    hints = [(10, "native")] * count
    hints[-1] = (0.1, "slow native")
    plan = policy.plan_iteration([0] * count, [1] * count, _joints(count), hints)
    assert plan["ramp_seconds"] == 19
    assert len(plan["joints"]) == timing.MAX_TIMING_JOINTS and plan["joints_omitted"] == 1


def _fixture(monkeypatch, overrides=None, *, track=True, initial=None):
    config = {
        **mjc.get_defaults(),
        "physics_fps": 20,
        "capture_fps": 10,
        "settle_seconds": 0.1,
        "position_tolerance_deg": 0,
        **(overrides or {}),
    }
    positions = np.array([0.0, 0.0, 42.125] if initial is None else initial, dtype=float)
    targets = positions.copy()
    commands, failures, messages = [], [], []
    metrics = {}
    steps = [0]
    getter_calls = [0]

    def command(values):
        nonlocal targets
        assert np.all(values[:2] >= -1) and np.all(values[:2] <= 1)
        assert values[2] == 42.125
        targets = values.copy()
        commands.append(values.copy())

    def hints():
        getter_calls[0] += 1
        return np.array([0.1, 0.5, 1])

    async def tick():
        steps[0] += 1
        if track:
            positions[:] = targets

    async def capture(**_kwargs):
        return None

    def indexed_command(values, indices):
        assert list(indices) == [0, 1]
        merged = targets.copy()
        merged[indices] = values
        command(merged)

    def unused_write(*_args):
        raise AssertionError("MJC does not write state or velocities")

    robot = SimpleNamespace(
        dof_names=["a", "b", "excluded"],
        dof_count=3,
        get_joint_positions=lambda: positions.copy(),
        get_joint_position_limits=lambda: (np.array([-1, -1, 0]), np.array([1, 1, 50])),
        get_joint_velocity_limits=hints,
        set_joint_position_targets=command,
        set_joint_position_targets_indexed=indexed_command,
        set_joint_positions_indexed=unused_write,
        set_joint_velocities_indexed=unused_write,
    )
    ctx = SimpleNamespace(
        step_one=tick,
        capture_frame=capture,
        add_metric=lambda key, value: metrics.update({key: value}),
        warn=messages.append,
        step=messages.append,
        fail=failures.append,
        skip=failures.append,
        encode_video=lambda *_args, **_kwargs: None,
        scene=SimpleNamespace(update_camera_follow=lambda **_kwargs: None),
    )
    monkeypatch.setattr(mjc, "compute_world_aligned_bbox", lambda _prim: None)
    monkeypatch.setattr(mjc, "check_bbox_explode", lambda *_args: None)
    return ctx, robot, {"passive_joint_indices": [2]}, config, commands, failures, metrics, steps, getter_calls


def test_actual_phase_shared_commands_stay_legal_and_slow_enough_with_no_extra_ticks(monkeypatch):
    ctx, robot, scene, config, commands, failures, metrics, steps, getter_calls = _fixture(monkeypatch)
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures and getter_calls[0] == 1
    records = metrics["mjc_timing_iterations"]
    assert [row["ramp_seconds"] for row in records] == pytest.approx([6.25, 9.25, 3.25])
    assert steps[0] == 2 + len(commands) == metrics["mjc_completed_nominal_ticks"]
    assert sum(row["completed_iteration_ticks"] for row in records) == len(commands)
    previous = np.zeros(2)
    for command in commands:
        assert abs(command[0] - previous[0]) * config["physics_fps"] <= 0.1 * 0.8 + 1e-12
        assert abs(command[1] - previous[1]) * config["physics_fps"] <= 0.5 * 0.8 + 1e-12
        previous = command[:2]


def test_stuck_joint_still_fails_using_actual_adapted_window_and_preserved_hold(monkeypatch):
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(
        monkeypatch, {"num_iterations": 1}, track=False
    )
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert failures and metrics["mjc_iterations_failed"] == 1
    plan = metrics["mjc_timing_iterations"][0]
    assert plan["hold_seconds"] == 6 and plan["observation_seconds"] == 12.25
    assert len(commands) == plan["total_frames"] and steps[0] == 2 + plan["total_frames"]
    assert "6.25 / 6 / 12.2" in failures[0] and "within 8.0s" not in failures[0]


def test_huge_iteration_preflight_rejects_even_if_tracking_would_finish_immediately(monkeypatch):
    ctx, robot, scene, config, commands, failures, _metrics, steps, _calls = _fixture(
        monkeypatch, {"num_iterations": 10**20}
    )
    with pytest.raises(RuntimeError, match="next complete window"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and steps[0] == 0


def test_actual_phase_getter_failure_preserved_before_initial_settle(monkeypatch):
    ctx, robot, scene, config, commands, failures, _metrics, steps, _calls = _fixture(monkeypatch)

    def failed_getter():
        raise RuntimeError("velocity getter failed")

    robot.get_joint_velocity_limits = failed_getter
    with pytest.raises(RuntimeError, match="velocity getter failed"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and steps[0] == 0


def test_actual_phase_absent_hint_is_visible_and_falls_back_without_failure(monkeypatch):
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(monkeypatch, {"num_iterations": 1})
    del robot.get_joint_velocity_limits
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert commands and steps[0] > 0 and not failures
    assert metrics["mjc_velocity_hint_fallback_joints"] == 2
    assert all(row["velocity_hint"] is None for row in metrics["mjc_timing_iterations"][0]["joints"])


def test_outside_start_requiring_excessive_first_legal_step_is_setup_error(monkeypatch):
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(
        monkeypatch, {"settle_seconds": 0}, initial=[-1.1, 0, 42.125]
    )
    with pytest.raises(RuntimeError, match="first legal command.*runtime/setup error"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and steps[0] == 0
    row = metrics["mjc_timing_iterations"][0]["joints"][0]
    assert row["initial_command_clipped"] is True
    assert row["estimated_initial_command_step_speed"] == pytest.approx(2)
    assert metrics["mjc_timing_iterations"][0]["completed_iteration_ticks"] == 0


def test_tiny_outside_start_still_uses_legal_clip_when_first_step_fits_speed(monkeypatch):
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(
        monkeypatch, {"settle_seconds": 0, "num_iterations": 1}, initial=[-1.0001, 0, 42.125]
    )
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert commands and steps[0] > 0 and not failures
    assert commands[0][0] == -1
    row = metrics["mjc_timing_iterations"][0]["joints"][0]
    assert row["initial_command_clipped"] is True
    assert row["estimated_initial_command_step_speed"] == pytest.approx(0.002)
    assert row["estimated_initial_command_step_speed"] <= row["velocity_hint"] * config["coordination_speed_scale"]


def test_actual_phase_iteration_records_are_bounded_and_omission_is_visible(monkeypatch):
    count = timing.MAX_TIMING_ITERATIONS + 1
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(
        monkeypatch,
        {
            "num_iterations": count,
            "target_factors": [0.5],
            "settle_seconds": 0,
            "motion_seconds": 0.01,
            "max_settling_seconds": 0.01,
        },
    )
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures and steps[0] == len(commands) == count
    assert len(metrics["mjc_timing_iterations"]) == timing.MAX_TIMING_ITERATIONS
    assert metrics["mjc_timing_iterations_omitted"] == 1


def test_adapted_full_window_is_reserved_before_commands(monkeypatch):
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(
        monkeypatch, {"num_iterations": 1, "max_coordination_simulation_seconds": 9}
    )
    with pytest.raises(RuntimeError, match="next complete window"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert steps[0] == 2 and not commands and not failures
    record = metrics["mjc_timing_iterations"][0]
    assert record["observation_seconds"] == 12.25 and record["completed_iteration_ticks"] == 0
    assert metrics["mjc_completed_nominal_ticks"] == 2


def test_completed_tick_clock_does_not_advance_after_failed_tick():
    budget = timing.CoordinationBudget(mjc.get_defaults())

    async def failed_tick():
        raise RuntimeError("tick failed")

    with pytest.raises(RuntimeError, match="tick failed"):
        asyncio.run(budget.step_one(SimpleNamespace(step_one=failed_tick)))
    assert budget.ticks == 0


def test_wall_guard_counts_capture_time_not_nominal_ticks(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
    ctx, robot, scene, config, commands, failures, metrics, steps, _calls = _fixture(
        monkeypatch, {"max_coordination_wall_seconds": 2}
    )

    async def delayed_capture(**_kwargs):
        clock[0] += 2
        return None

    ctx.capture_frame = delayed_capture
    with pytest.raises(RuntimeError, match="wall_seconds exhausted"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert len(commands) == 1 and steps[0] == 3 and not failures
    assert metrics["mjc_completed_nominal_ticks"] == 3
    assert metrics["mjc_timing_iterations"][0]["completed_iteration_ticks"] == 1


def test_diagnostic_metric_failure_cannot_replace_required_tick_error(monkeypatch):
    ctx, robot, scene, config, commands, failures, _metrics, steps, _calls = _fixture(monkeypatch)
    original_metric = ctx.add_metric

    def failed_metric(key, value):
        if key.startswith("mjc_timing") or key == "mjc_completed_nominal_ticks":
            raise RuntimeError("optional timing metric unavailable")
        original_metric(key, value)

    async def failed_tick():
        raise RuntimeError("required physics tick unavailable")

    ctx.add_metric = failed_metric
    ctx.step_one = failed_tick
    config["settle_seconds"] = 0
    with pytest.raises(RuntimeError, match="required physics tick unavailable"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert len(commands) == 1 and steps[0] == 0 and not failures


def test_registration_exposes_timing_policy_and_config_preflight_before_setup():
    registration = import_module("simready.foundation.tier_core.runtime_tests.fet022_driven_joints.multi_joint_coordination")
    assert registration.MULTI_JOINT_COORDINATION_KWARGS["version"] == "1.2.6"
    assert registration.MULTI_JOINT_COORDINATION_KWARGS["max_duration"] == 3600
    assert (
        registration.MULTI_JOINT_COORDINATION_KWARGS["config_defaults"]["coordination_settling_allowance_seconds"]
        == 0.25
    )
    with pytest.raises(ValueError, match="max_settling_seconds"):
        asyncio.run(registration.run_multi_joint_coordination(SimpleNamespace(config={"max_settling_seconds": 1})))

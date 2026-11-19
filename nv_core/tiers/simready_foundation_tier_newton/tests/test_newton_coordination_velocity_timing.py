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
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    coordination_timing as timing,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc,
)


def _config(**changes):
    return {**mjc.get_defaults(), **changes}


def _joints(count=2):
    return [{"index": index, "name": "joint_%d" % index, "lower": 0.0, "upper": 1.0} for index in range(count)]


def test_shared_ramp_uses_slowest_joint_peak_and_retains_the_old_hold():
    policy = timing.CoordinationTiming(_config())
    record = policy.plan_iteration([0.0, 0.0], [0.25, 1.0], _joints(), [(2.0, "native"), (0.1, "native")])
    assert record["ramp_seconds"] == pytest.approx(19.0)
    assert record["hold_seconds"] == 6.0
    assert record["observation_seconds"] == 25.0
    assert policy.minimum_total_frames == 240 + 3 * 1920
    for joint in record["joints"]:
        assert joint["estimated_command_peak_speed"] <= joint["velocity_hint"] * 0.8


@pytest.mark.parametrize("fps", [23.4, 30.3, 239.8, 240.0])
def test_derived_ticks_round_up_without_lengthening_unchanged_fallback(fps):
    policy = timing.CoordinationTiming(_config(physics_fps=fps))
    fallback = policy.plan_iteration([0, 0], [1, 1], _joints(), [(None, "fallback")] * 2)
    assert fallback["ramp_frames"] == math.ceil(2.0 * fps)
    adapted = policy.plan_iteration([0, 0], [1, 1], _joints(), [(0.1, "native")] * 2)
    assert adapted["ramp_frames"] == math.ceil(19.0 * fps)
    assert adapted["hold_frames"] == fallback["hold_frames"]


def test_legacy_sixty_observation_floor_is_preserved_in_hold():
    policy = timing.CoordinationTiming(_config(physics_fps=10, motion_seconds=0.1, max_settling_seconds=0.2))
    assert policy.base_ramp_frames == 1
    assert policy.hold_frames == 59


def test_timing_records_are_bounded_and_disclose_omitted_joint_evidence():
    count = timing.MAX_TIMING_JOINTS + 1
    record = timing.CoordinationTiming(_config()).plan_iteration(
        [0] * count, [1] * count, _joints(count), [(None, "fallback")] * count
    )
    assert len(record["joints"]) == timing.MAX_TIMING_JOINTS
    assert record["joints_omitted"] == 1


def test_joint_beyond_diagnostic_cap_still_controls_shared_ramp():
    count = timing.MAX_TIMING_JOINTS + 1
    hints = [(None, "fallback")] * count
    hints[-1] = (0.1, "native")
    record = timing.CoordinationTiming(_config()).plan_iteration([0] * count, [1] * count, _joints(count), hints)
    assert record["ramp_seconds"] == 19
    assert record["joints_omitted"] == 1


@pytest.mark.parametrize("hint", [None, (math.nan, "bad"), (True, "bad"), (0, "bad"), ("1", "bad"), (1,), (1, 2, 3)])
def test_malformed_private_hint_retains_fallback(hint):
    record = timing.CoordinationTiming(_config()).plan_iteration([0, 0], [1, 1], _joints(), [hint])
    assert record["ramp_seconds"] == 2
    assert all(joint["velocity_hint"] is None for joint in record["joints"])


def test_diagnostic_identity_and_source_lengths_are_bounded():
    joints = _joints()
    joints[0]["name"] = "j" * 1000
    record = timing.CoordinationTiming(_config()).plan_iteration([0, 0], [1, 1], joints, [(1, "s" * 1000)] * 2)
    assert len(record["joints"][0]["name"]) == 256
    assert len(record["joints"][0]["velocity_hint_source"]) == 256


@pytest.mark.parametrize(
    "key,value",
    [
        ("coordination_speed_scale", 0),
        ("coordination_speed_scale", 1.1),
        ("coordination_speed_scale", True),
        ("coordination_speed_scale", "0.8"),
        ("coordination_settling_allowance_seconds", -0.1),
        ("coordination_settling_allowance_seconds", math.nan),
        ("max_coordination_ramp_seconds", 0),
        ("num_iterations", 2.5),
        ("physics_fps", math.inf),
        ("physics_fps", 1e308),
        ("max_settling_seconds", 1),
    ],
)
def test_invalid_timing_config_is_rejected(key, value):
    with pytest.raises((ValueError, RuntimeError)):
        timing.CoordinationTiming(_config(**{key: value}))


@pytest.mark.parametrize(
    "key,value", [("max_coordination_wall_seconds", 3541), ("max_coordination_simulation_seconds", math.nan)]
)
def test_invalid_budget_config_is_rejected(key, value):
    with pytest.raises(ValueError):
        timing.CoordinationBudget(_config(**{key: value}))


@pytest.mark.parametrize("velocity", [1e-300, 0.001])
def test_too_slow_hint_is_execution_error_not_shortened_ramp(velocity):
    with pytest.raises(RuntimeError, match="timing budget is insufficient"):
        timing.CoordinationTiming(_config(coordination_speed_scale=1e-300)).plan_iteration(
            [0, 0], [1, 1], _joints(), [(velocity, "native")] * 2
        )


def test_nonfinite_derived_travel_is_rejected():
    with pytest.raises(ValueError, match="finite goal travel"):
        timing.CoordinationTiming(_config()).plan_iteration(
            [-1e308, 0], [1e308, 1], _joints(), [(None, "fallback")] * 2
        )


def _fixture(monkeypatch, overrides=None, *, track=True):
    config = _config(physics_fps=20, capture_fps=20, settle_seconds=0, num_iterations=1, **(overrides or {}))
    position = np.zeros(3)
    position[2] = 42.125
    target = position.copy()
    commands, failures, warnings, steps = [], [], [], [0]
    metrics = {}

    def command(values):
        assert values.dtype.kind == "f"
        assert np.all(values[:2] >= 0) and np.all(values[:2] <= 1)
        assert values[2] == 42.125
        target[:] = values
        commands.append(values.copy())

    async def step():
        steps[0] += 1
        if track:
            position[:] = target

    async def capture(**_kwargs):
        return None

    def indexed_command(values, indices):
        assert list(indices) == [0, 1]
        merged = target.copy()
        merged[indices] = values
        command(merged)

    def unused_write(*_args):
        raise AssertionError("MJC does not write state or velocities")

    robot = SimpleNamespace(
        dof_names=["joint_0", "joint_1", "excluded"],
        dof_count=3,
        get_joint_positions=lambda: position.copy(),
        get_joint_position_limits=lambda: (np.array([0, 0, -100.0]), np.array([1, 1, 100.0])),
        get_joint_velocity_limits=lambda: np.array([1.0, 0.1, 1.0]),
        set_joint_position_targets=command,
        set_joint_position_targets_indexed=indexed_command,
        set_joint_positions_indexed=unused_write,
        set_joint_velocities_indexed=unused_write,
    )
    ctx = SimpleNamespace(
        step_one=step,
        capture_frame=capture,
        encode_video=lambda *_args, **_kwargs: None,
        step=lambda *_args: None,
        warn=warnings.append,
        fail=failures.append,
        skip=failures.append,
        add_metric=lambda name, value: metrics.update({name: value}),
        scene=SimpleNamespace(update_camera_follow=lambda **_kwargs: None),
    )
    monkeypatch.setattr(mjc, "compute_world_aligned_bbox", lambda *_args: None)
    monkeypatch.setattr(mjc, "check_bbox_explode", lambda *_args: None)
    monkeypatch.setattr(
        mjc,
        "make_joint_observer",
        lambda *_args, **_kwargs: SimpleNamespace(
            sample=lambda *_args, **_kwargs: None, finish=lambda *_args: None, record_capture=lambda *_args: None
        ),
    )
    return ctx, robot, {"passive_joint_indices": [2]}, config, metrics, commands, failures, warnings, steps, position


def _iteration(ctx, robot, config, records, index=0):
    policy = timing.CoordinationTiming(config)
    budget = timing.CoordinationBudget(config)
    return asyncio.run(
        mjc._run_iteration(
            ctx,
            robot,
            {},
            _joints(),
            factor=0.5,
            iteration_idx=index,
            pos_tol_rad=0,
            max_frames=policy.base_ramp_frames + policy.hold_frames,
            capture_interval=1,
            capture_frames=[],
            baseline_bbox=None,
            bbox_ratio_limit=10,
            margin_ratio=0,
            physics_fps=policy.fps,
            motion_frames=policy.base_ramp_frames,
            timing=policy,
            budget=budget,
            velocity_hints=[(1.0, "native"), (0.1, "native"), (1.0, "native")],
            timing_records=records,
        )
    )


def test_each_iteration_uses_required_changed_live_start_and_legal_commands(monkeypatch):
    ctx, robot, _scene, config, _metrics, commands, failures, _warnings, _steps, position = _fixture(monkeypatch)
    records = []
    assert _iteration(ctx, robot, config, records)[0]
    assert records[0]["ramp_seconds"] == pytest.approx(9.65)
    first_commands = len(commands)
    position[:2] = [0.8, 0.4]
    assert _iteration(ctx, robot, config, records, 1)[0]
    assert records[1]["ramp_seconds"] == pytest.approx(2.15)
    assert [row["displacement"] for row in records[1]["joints"]] == pytest.approx([0.3, 0.1])
    assert len(commands) - first_commands == records[1]["ramp_frames"]
    assert not failures


def test_actual_phase_extends_slow_joint_window_preserving_goal_and_criterion(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _warnings, steps, _position = _fixture(
        monkeypatch, {"position_tolerance_deg": 0}
    )
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures and commands
    assert commands[-1][:2] == pytest.approx([0.34, 0.34])
    record = metrics["mjc_timing_iterations"][0]
    assert record["ramp_seconds"] == pytest.approx(6.65)
    assert record["hold_seconds"] == 6.0
    assert record["completed_iteration_ticks"] == steps[0] == record["ramp_frames"]
    assert metrics["mjc_completed_nominal_seconds"] == steps[0] / 20
    assert metrics["mjc_iterations_passed"] == 1


def test_stuck_joint_still_fails_and_guidance_uses_actual_windows(monkeypatch):
    ctx, robot, scene, config, metrics, _commands, failures, _warnings, steps, _position = _fixture(
        monkeypatch, track=False
    )
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert failures and metrics["mjc_iterations_failed"] == 1
    assert "velocity-aware ramp plus preserved hold" in failures[0]
    assert "8.0s of physics" not in failures[0]
    assert steps[0] == metrics["mjc_timing_iterations"][0]["total_frames"]


@pytest.mark.parametrize(
    "values", [None, np.array([math.nan] * 3), np.array([True] * 3), np.array([[1], [2], [3]]), np.array([1])]
)
def test_absent_or_malformed_hints_keep_visible_configured_fallback(monkeypatch, values):
    ctx, robot, scene, config, metrics, commands, failures, warnings, _steps, _position = _fixture(monkeypatch)
    robot.get_joint_velocity_limits = lambda: values
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures and commands
    assert metrics["mjc_velocity_hint_fallback_joints"] == 2
    assert any("no usable qualified velocity hint" in message for message in warnings)
    assert metrics["mjc_timing_iterations"][0]["ramp_seconds"] == 2


def test_present_hint_getter_exception_remains_execution_error_before_ticks(monkeypatch):
    ctx, robot, scene, config, _metrics, commands, failures, _warnings, steps, _position = _fixture(monkeypatch)

    def broken():
        raise RuntimeError("native getter unavailable")

    robot.get_joint_velocity_limits = broken
    with pytest.raises(RuntimeError, match="native getter unavailable"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and steps[0] == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"num_iterations": 1e100},
        {"motion_seconds": 3, "max_settling_seconds": 2},
        {"max_coordination_simulation_seconds": 1},
    ],
)
def test_preflight_rejects_bad_minimum_budget_before_discovery_or_ticks(monkeypatch, overrides):
    ctx, robot, scene, config, metrics, commands, failures, _warnings, steps, _position = _fixture(monkeypatch)
    config.update(overrides)
    robot.get_joint_position_limits = lambda: (_ for _ in ()).throw(AssertionError("preflight must precede discovery"))
    with pytest.raises((RuntimeError, ValueError)):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and not metrics and steps[0] == 0


def test_dynamic_complete_window_budget_rejects_before_any_command(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _warnings, steps, _position = _fixture(monkeypatch)
    config["max_coordination_simulation_seconds"] = 9
    with pytest.raises(RuntimeError, match="next complete window"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and steps[0] == 0
    record = metrics["mjc_timing_iterations"][0]
    assert record["observation_seconds"] > 9
    assert record["completed_iteration_ticks"] == 0
    assert metrics["mjc_completed_nominal_seconds"] == 0


def test_failed_physics_tick_is_not_counted_as_completed():
    budget = timing.CoordinationBudget(_config())

    async def broken():
        raise RuntimeError("tick failed")

    with pytest.raises(RuntimeError, match="tick failed"):
        asyncio.run(budget.step_one(SimpleNamespace(step_one=broken)))
    assert budget.ticks == 0


def test_wall_guard_includes_capture_delay_without_counting_render_ticks(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
    budget = timing.CoordinationBudget(_config(max_coordination_wall_seconds=2))

    async def step():
        clock[0] += 1.0

    asyncio.run(budget.step_one(SimpleNamespace(step_one=step)))
    assert budget.ticks == 1
    clock[0] += 1.0
    with pytest.raises(RuntimeError, match="wall_seconds exhausted"):
        budget.check_wall()
    assert budget.ticks == 1


def test_required_tick_exception_retains_planned_window_without_asset_fail(monkeypatch):
    ctx, robot, scene, config, metrics, _commands, failures, _warnings, _steps, _position = _fixture(monkeypatch)

    async def broken():
        raise RuntimeError("required tick failed")

    ctx.step_one = broken
    with pytest.raises(RuntimeError, match="required tick failed"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures
    assert metrics["mjc_timing_iterations"][0]["completed_iteration_ticks"] == 0
    assert metrics["mjc_completed_nominal_seconds"] == 0


def test_registration_exposes_local_bounded_coordination_policy():
    registration = import_module("simready.foundation.tier_newton.runtime_tests.fet022_driven_joints.multi_joint_coordination")
    metadata = registration.MULTI_JOINT_COORDINATION_KWARGS
    assert metadata["version"] == "1.2.6"
    assert metadata["max_duration"] == 3600
    assert metadata["config_defaults"]["max_coordination_wall_seconds"] == 3360


def test_diagnostic_metric_failure_cannot_mask_required_tick_exception(monkeypatch):
    ctx, robot, scene, config, _metrics, _commands, failures, warnings, _steps, _position = _fixture(monkeypatch)

    async def broken():
        raise RuntimeError("original tick error")

    ordinary_metric = ctx.add_metric

    def metric(name, value):
        if name.startswith("mjc_timing") or name == "mjc_completed_nominal_seconds":
            raise RuntimeError("optional timing metric error")
        ordinary_metric(name, value)

    ctx.add_metric = metric
    ctx.step_one = broken
    with pytest.raises(RuntimeError, match="original tick error"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures and any("timing diagnostics" in warning for warning in warnings)


def test_wall_error_after_successful_tick_retains_actual_completed_count(monkeypatch):
    ctx, robot, scene, config, metrics, _commands, failures, _warnings, _steps, _position = _fixture(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
    config["max_coordination_wall_seconds"] = 1

    async def slow_tick():
        clock[0] += 1

    ctx.step_one = slow_tick
    with pytest.raises(RuntimeError, match="wall_seconds exhausted"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not failures
    assert metrics["mjc_timing_iterations"][0]["completed_iteration_ticks"] == 1
    assert metrics["mjc_completed_nominal_seconds"] == 1 / 20


def test_far_illegal_start_cannot_be_clipped_into_an_unpaced_first_command(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _warnings, steps, position = _fixture(monkeypatch)
    position[1] = -0.1
    with pytest.raises(RuntimeError, match="initial legal-command correction"):
        asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert not commands and not failures and steps[0] == 0
    joint = metrics["mjc_timing_iterations"][0]["joints"][1]
    assert joint["initial_command_clipped"]
    assert joint["estimated_initial_command_step_speed"] == 2
    assert metrics["mjc_timing_iterations"][0]["completed_iteration_ticks"] == 0


def test_tiny_outside_start_within_first_tick_pacing_keeps_legal_commands(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _warnings, steps, position = _fixture(monkeypatch)
    position[1] = -0.0001
    asyncio.run(mjc.run_multi_joint_coordination(ctx, robot, scene, config))
    assert commands and not failures and steps[0] > 0
    joint = metrics["mjc_timing_iterations"][0]["joints"][1]
    assert joint["initial_command_clipped"]
    assert joint["estimated_initial_command_step_speed"] <= joint["velocity_hint"] * 0.8

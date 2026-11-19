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
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import full_range_sweep as frs
from simready.foundation.tier_newton.runtime_tests.articulation_phases import sweep_timing as timing


def _qualify(monkeypatch):
    observer = import_module("simready.foundation.tier_newton.runtime_tests.motion_observer")
    monkeypatch.setattr(observer, "_newton_version_for_units", lambda: ("1.2.1", "test-qualified"))


@pytest.mark.parametrize(
    "value", [None, 0, -1, math.nan, math.inf, -math.inf, True, "2", complex(2, 0), 3.402823466e38, 3.402823e38]
)
def test_unusable_velocity_uses_a_bounded_fallback(value):
    assert timing.usable_velocity(value) is None
    config = frs.get_defaults()
    assert timing.segment_frames(0, 10, 0, None, config, 300) == 300


def test_large_finite_velocity_is_not_an_unlimited_sentinel():
    assert timing.usable_velocity(1e38) == 1e38


def test_fallback_preserves_legacy_integer_tick_count():
    for fps in (23.4, 30.3, 239.8):
        config = {**frs.get_defaults(), "physics_fps": fps}
        for frames in (2, 29, 299):
            assert timing.segment_frames(0, 1, 0, None, config, frames) == frames


def test_underflowing_speed_budget_is_bounded_execution_error():
    config = {**frs.get_defaults(), "sweep_speed_scale": 1e-300}
    with pytest.raises(RuntimeError, match="timing budget is insufficient"):
        timing.segment_frames(0, 1, 0, 1e-300, config, 300)


@pytest.mark.parametrize(
    "profile,peak", [("linear", 1), ("smoothstep", 1.5), ("smootherstep", 1.875), ("trapezoidal", 2)]
)
def test_real_jaco_reversal_respects_profile_peak_speed(profile, peak):
    config = {**frs.get_defaults(), "interpolation_profile": profile}
    frames = timing.segment_frames(
        math.radians(300), math.radians(60), math.radians(300), math.radians(36), config, 300
    )
    expected = peak * 240 / (36 * 0.8) + 0.25
    assert frames / 240 >= expected
    assert frames / 240 <= expected + 1 / 240 + 1e-12
    if profile == "smoothstep":
        assert frames / 240 == pytest.approx(12.75)


def test_current_position_and_speed_scale_above_one_cannot_shorten_required_travel():
    config = {**frs.get_defaults(), "sweep_speed_scale": 5, "sweep_settling_allowance_seconds": 0}
    frames = timing.segment_frames(0, 1, -1, 0.25, config, 300)
    assert frames / 240 == pytest.approx(12)


def test_nominal_jaco_cap_estimate_fits_the_whole_simulation_budget():
    # Two authored 30..330-degree arm joints; five unlimited arm joints may
    # present finite SDK sentinels and use the existing full-turn cap. Assume
    # zero start and include all six independently eligible finger coordinates.
    total = 1.0
    for lower, upper, speed in (
        [(30, 330, 36)] * 2
        + [(-180, 180, 36)] * 2
        + [(-180, 180, 48)] * 3
        + [(0, 86.51662445, 57.29578018)] * 3
        + [(0, 114.59155273, 57.29578018)] * 3
    ):
        params = frs.compute_sweep_parameters(
            math.radians(lower), math.radians(upper), 0.1, math.tau, 0.8, 0.15, 240, "joint"
        )
        for start, goal, _name in frs.build_sweep_segments(0, params):
            total += (
                timing.segment_frames(start, goal, start, math.radians(speed), frs.get_defaults(), params["seg_frames"])
                / 240
            )
            total += params["pause_frames"] / 240
    assert 180 < total < 300
    assert total < frs.get_defaults()["max_sweep_simulation_seconds"]


def _scene(joint_type=UsdPhysics.RevoluteJoint):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    joint = joint_type.Define(stage, "/Asset/hinge").GetPrim()
    joint.CreateAttribute("physxJoint:maxJointVelocity", Sdf.ValueTypeNames.Float).Set(36)
    return stage, root, joint


def test_angular_usd_hint_converts_degrees_once_and_uses_the_smaller_native_hint(monkeypatch):
    _qualify(monkeypatch)
    stage, root, _joint = _scene()
    robot = SimpleNamespace(dof_names=["hinge"], get_joint_velocity_limits=lambda: np.array([2.0]))
    hint, source = timing.resolve_velocity_hints(robot, {"stage": stage, "asset_prim": root})[0]
    assert hint == pytest.approx(math.radians(36))
    assert "USD physxJoint:maxJointVelocity" == source
    robot.get_joint_velocity_limits = lambda: np.array([0.1])
    hint, source = timing.resolve_velocity_hints(robot, {"stage": stage, "asset_prim": root})[0]
    assert hint == 0.1 and source.startswith("runtime")


def test_ambiguous_authored_joint_identity_does_not_supply_a_hint(monkeypatch):
    _qualify(monkeypatch)
    stage, root, _joint = _scene()
    UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Other/hinge")
    robot = SimpleNamespace(dof_names=["hinge"])
    assert timing.resolve_velocity_hints(robot, {"stage": stage, "asset_prim": root}) == [
        (None, "configured fallback duration")
    ]


@pytest.mark.parametrize(
    "values",
    [None, np.array([math.nan]), np.array([True]), np.array(["2"]), np.array([[2]]), np.array([1, 2]), [[1], [2, 3]]],
)
def test_optional_invalid_velocity_hints_do_not_fabricate_a_speed(values):
    robot = SimpleNamespace(dof_names=["hinge"], get_joint_velocity_limits=lambda: values)
    assert timing.resolve_velocity_hints(robot, {}) == [(None, "configured fallback duration")]


def test_present_velocity_getter_errors_are_preserved():
    def unavailable():
        raise RuntimeError("native velocity getter unavailable")

    with pytest.raises(RuntimeError, match="native velocity getter"):
        timing.resolve_velocity_hints(SimpleNamespace(dof_names=["hinge"], get_joint_velocity_limits=unavailable), {})


def test_native_prismatic_distance_over_speed_needs_no_stage_unit_guess():
    config = {**frs.get_defaults(), "interpolation_profile": "linear", "sweep_settling_allowance_seconds": 0}
    frames = timing.segment_frames(0, 2, 0, 0.2, config, 300)
    assert frames / 240 == pytest.approx(12.5)


@pytest.mark.parametrize("version,expected", [("1.2.1", 36), ("1.5.0", None), (None, None)])
def test_linear_authored_hint_requires_the_qualified_actual_newton_sdk(monkeypatch, version, expected):
    observer = import_module("simready.foundation.tier_newton.runtime_tests.motion_observer")
    monkeypatch.setattr(observer, "_newton_version_for_units", lambda: (version, "test"))
    stage, root, joint = _scene(UsdPhysics.PrismaticJoint)
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    joint.CreateAttribute("newton:velocityLimit", Sdf.ValueTypeNames.Float).Set(0.01)
    robot = SimpleNamespace(dof_names=["hinge"])
    assert timing.resolve_velocity_hints(robot, {"stage": stage, "asset_prim": root})[0][0] == expected


def test_newton_actuator_saturation_and_physx_envelope_are_not_qualified_timing_ceilings(monkeypatch):
    _qualify(monkeypatch)
    stage, root, joint = _scene()
    joint.RemoveProperty("physxJoint:maxJointVelocity")
    joint.CreateAttribute("newton:velocityLimit", Sdf.ValueTypeNames.Float).Set(0.01)
    joint.CreateAttribute("physxDrivePerformanceEnvelope:angular:maxActuatorVelocity", Sdf.ValueTypeNames.Float).Set(
        0.01
    )
    assert (
        timing.resolve_velocity_hints(SimpleNamespace(dof_names=["hinge"]), {"stage": stage, "asset_prim": root})[0][0]
        is None
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("physics_fps", 0),
        ("physics_fps", math.nan),
        ("physics_fps", math.inf),
        ("sweep_speed_scale", 0),
        ("sweep_speed_scale", math.nan),
        ("settle_seconds", -1),
        ("pause_at_limits_seconds", math.nan),
        ("sweep_settling_allowance_seconds", -1),
        ("max_sweep_wall_seconds", 14341),
        ("max_sweep_simulation_seconds", math.inf),
    ],
)
def test_invalid_timing_configuration_is_an_execution_configuration_error(key, value):
    with pytest.raises(ValueError):
        timing.SweepBudget({**frs.get_defaults(), key: value})


def test_too_slow_segment_budget_is_not_silently_shortened():
    with pytest.raises(RuntimeError, match="timing budget is insufficient"):
        timing.segment_frames(0, 10, 0, 0.001, frs.get_defaults(), 300)


def test_whole_window_budget_rejects_before_submission():
    budget = timing.SweepBudget({**frs.get_defaults(), "max_sweep_simulation_seconds": 1})
    with pytest.raises(RuntimeError, match="next complete window"):
        budget.reserve(241)
    assert budget.ticks == 0


def test_wall_guard_uses_monotonic_time_independently_of_nominal_ticks(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
    budget = timing.SweepBudget({**frs.get_defaults(), "max_sweep_wall_seconds": 2})
    clock[0] += 2
    with pytest.raises(RuntimeError, match="wall_seconds exhausted"):
        budget.check_wall()
    assert budget.ticks == 0


def _run_fixture(monkeypatch, overrides=None, *, unavailable_position=False):
    config = {**frs.get_defaults(), "physics_fps": 20, "capture_fps": 30, "settle_seconds": 0.1, **(overrides or {})}
    position = np.array([0.0, 0.4])
    targets = position.copy()
    commands, hold_reads, messages, failures = [], [], [], []
    metrics = {}
    step_count = [0]

    def command(index, target):
        assert index == 0
        assert -0.1 <= target <= 0.1
        targets[index] = target
        commands.append(target)

    def read():
        if unavailable_position and commands:
            raise RuntimeError("required live position unavailable")
        hold_reads.append(position.copy())
        return position.copy()

    async def step_one():
        step_count[0] += 1
        position[0] += np.clip(targets[0] - position[0], -0.1 / 20, 0.1 / 20)

    async def capture_frame(**_kwargs):
        return None

    robot = SimpleNamespace(
        dof_names=["hinge", "excluded"],
        dof_count=2,
        get_joint_position_limits=lambda: (np.array([-0.1, -1]), np.array([0.1, 1])),
        get_joint_velocity_limits=lambda: np.array([0.1, 1]),
        get_joint_positions=read,
        set_joint_position_target=command,
    )
    ctx = SimpleNamespace(
        add_metric=lambda key, value: metrics.update({key: value}),
        step=messages.append,
        log=messages.append,
        warn=messages.append,
        fail=failures.append,
        skip=failures.append,
        step_one=step_one,
        capture_frame=capture_frame,
        scene=SimpleNamespace(update_camera_follow=lambda **_kwargs: None),
        physics_steps=lambda *_args: (_ for _ in ()).throw(AssertionError("settle must advance real ticks")),
    )
    monkeypatch.setattr(frs, "compute_world_aligned_bbox", lambda _prim: SimpleNamespace(volume=1))
    monkeypatch.setattr(frs, "check_bbox_explode", lambda *_args: None)
    history = import_module("simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_history")
    monkeypatch.setattr(
        history,
        "make_joint_observer",
        lambda *_args, **_kwargs: SimpleNamespace(history=None, finish=lambda *_args: None),
    )
    scene = {"passive_joint_indices": [1]}
    return ctx, robot, scene, config, metrics, commands, failures, step_count, position


def test_actual_runner_slow_joint_reaches_unchanged_targets_and_holds(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, steps, position = _run_fixture(monkeypatch)
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not failures
    assert max(commands) == pytest.approx(0.08) and min(commands) == pytest.approx(-0.08)
    assert position[0] == pytest.approx(0, abs=config["zero_return_tolerance"])
    assert position[1] == 0.4
    records = metrics["frs_segment_timing"]
    assert [record["ramp_seconds"] for record in records] == pytest.approx([1.75, 3.25, 1.75])
    assert steps[0] == 2 + len(commands)
    assert metrics["frs_joints_passed"] == 1 and metrics["frs_joints_failed"] == 0


def test_actual_runner_stuck_joint_still_fails_the_unchanged_hold_criterion(monkeypatch):
    ctx, robot, scene, config, metrics, _commands, failures, _steps, _position = _run_fixture(
        monkeypatch, {"rest_tolerance": 0.01}
    )

    async def no_response():
        return None

    ctx.step_one = no_response
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert failures and metrics["frs_joints_failed"] == 1 and metrics["frs_joints_passed"] == 0


def test_missed_endpoint_rebases_next_ramp_on_live_position(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _steps, _position = _run_fixture(
        monkeypatch, {"rest_tolerance": 0.01}
    )

    async def no_response():
        return None

    ctx.step_one = no_response
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    records = metrics["frs_segment_timing"]
    second_start = int(round(records[0]["ramp_seconds"] * config["physics_fps"])) + int(
        round(config["pause_at_limits_seconds"] * config["physics_fps"])
    )
    assert records[1]["requested_start"] == pytest.approx(0.08)
    assert records[1]["observed_start"] == pytest.approx(0)
    assert commands[second_start] < 0
    assert records[1]["estimated_initial_command_step_speed"] <= 0.08 + 1e-12
    assert failures and metrics["frs_joints_failed"] == 1


def test_out_of_bounds_live_start_requires_legal_first_step_pacing(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _steps, position = _run_fixture(
        monkeypatch, {"settle_seconds": 0}
    )
    position[0] = 0.2
    with pytest.raises(RuntimeError, match="first legal command.*runtime/setup error"):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not commands and not failures
    assert metrics["frs_segment_timing"][0]["initial_command_clipped"] is True


def test_tiny_out_of_bounds_start_can_clip_at_a_paced_first_step(monkeypatch):
    ctx, robot, scene, config, metrics, commands, _failures, _steps, position = _run_fixture(
        monkeypatch, {"settle_seconds": 0}
    )
    position[0] = 0.1001
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert commands[0] == pytest.approx(0.1)
    assert metrics["frs_segment_timing"][0]["initial_command_clipped"] is True


@pytest.mark.parametrize("key", ["rest_check_enabled", "rest_check_fatal"])
@pytest.mark.parametrize("value", [None, "", "false", "true", 0, 1, 0.0, math.nan, math.inf, [], {}, np.bool_(False)])
def test_malformed_hold_policy_is_rejected_before_any_motion_or_metrics(monkeypatch, key, value):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(
        monkeypatch, {key: value, "rest_tolerance": 0.01}
    )
    with pytest.raises(ValueError, match=key):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not commands and steps[0] == 0 and not failures and not metrics


@pytest.mark.parametrize("key", ["rest_check_enabled", "rest_check_fatal"])
@pytest.mark.parametrize("value", [True, False])
def test_explicit_boolean_hold_policy_preserves_stationary_joint_verdict(monkeypatch, key, value):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(
        monkeypatch, {key: value, "rest_tolerance": 0.01}
    )
    warnings = []
    ctx.warn = warnings.append

    async def stationary_step():
        steps[0] += 1

    ctx.step_one = stationary_step
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert commands and steps[0] > 0
    if value:
        assert failures and metrics["frs_joints_failed"] == 1 and metrics["frs_joints_passed"] == 0
    else:
        # Explicitly disabled/nonfatal hold checks remain a diagnostic policy,
        # not an excuse to accept malformed configuration as the same policy.
        assert not failures and metrics["frs_joints_failed"] == 0 and metrics["frs_joints_passed"] == 1
        if key == "rest_check_fatal":
            assert any("failed hold check" in message for message in warnings)


@pytest.mark.parametrize("key", ["rest_tolerance", "zero_return_tolerance", "bbox_explode_ratio"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -0.1, True, False, "0.1", None])
def test_invalid_verdict_threshold_is_rejected_before_motion(monkeypatch, key, value):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(
        monkeypatch, {key: value, "settle_seconds": 0.1}
    )
    with pytest.raises(ValueError, match=key):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not commands and steps[0] == 0 and not failures
    assert "frs_joints_passed" not in metrics


@pytest.mark.parametrize(
    "key,value",
    [
        ("bbox_explode_ratio", 0),
        ("sweep_margin_ratio", math.nan),
        ("sweep_margin_ratio", math.inf),
        ("sweep_margin_ratio", -0.1),
        ("sweep_margin_ratio", 0.5),
        ("sweep_margin_ratio", True),
        ("sweep_margin_ratio", "0.1"),
        ("max_sweep_range", math.nan),
        ("max_sweep_range", math.inf),
        ("max_sweep_range", True),
        ("max_sweep_range", "6.28"),
    ],
)
def test_invalid_sweep_verdict_configuration_is_rejected_before_motion(monkeypatch, key, value):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(monkeypatch, {key: value})
    with pytest.raises(ValueError, match=key):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not commands and steps[0] == 0 and not failures
    assert "frs_joints_passed" not in metrics


@pytest.mark.parametrize("zero", [0, 0.0])
def test_exact_zero_verdict_tolerances_remain_supported(monkeypatch, zero):
    ctx, robot, scene, config, metrics, commands, failures, steps, position = _run_fixture(
        monkeypatch, {"rest_tolerance": zero, "zero_return_tolerance": zero}
    )

    async def exact_tracking():
        steps[0] += 1
        if commands:
            position[0] = commands[-1]

    ctx.step_one = exact_tracking
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert commands and steps[0] > 0 and not failures
    assert metrics["frs_joints_passed"] == 1 and metrics["frs_joints_failed"] == 0


@pytest.mark.parametrize(
    "key,value",
    [("newton_zero_max_settling_seconds", value) for value in (math.nan, math.inf, -math.inf, -1, True, "2", None)]
    + [
        ("newton_zero_consecutive_frames", value)
        for value in (math.nan, math.inf, -math.inf, -1, 0, 5.5, True, "8", None)
    ],
)
def test_invalid_newton_convergence_configuration_is_rejected_before_motion(monkeypatch, key, value):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(monkeypatch, {key: value})
    scene["active_physics_engine"] = "newton"
    with pytest.raises(ValueError, match=key):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not commands and steps[0] == 0 and not failures
    assert "frs_joints_passed" not in metrics


@pytest.mark.parametrize("frames", [1, 6, 6.0])
@pytest.mark.parametrize("seconds", [0, 0.0, 0.5])
def test_valid_newton_convergence_configuration_keeps_its_policy(monkeypatch, frames, seconds):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(
        monkeypatch, {"newton_zero_max_settling_seconds": seconds, "newton_zero_consecutive_frames": frames}
    )
    scene["active_physics_engine"] = "newton"
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert commands and steps[0] > 0 and not failures
    assert metrics["frs_joints_passed"] == 1 and metrics["frs_joints_failed"] == 0


def test_actual_runner_budget_exhaustion_is_an_exception_before_joint_commands(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, _steps, _position = _run_fixture(
        monkeypatch, {"max_sweep_segment_seconds": 1}
    )
    with pytest.raises(RuntimeError, match="timing budget is insufficient"):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not commands and not failures and "frs_joints_passed" not in metrics


def test_actual_runner_required_readback_error_remains_execution_error(monkeypatch):
    ctx, robot, scene, config, metrics, _commands, failures, _steps, _position = _run_fixture(
        monkeypatch, unavailable_position=True
    )
    with pytest.raises(RuntimeError, match="required live position unavailable"):
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not failures and "frs_joints_passed" not in metrics


def test_registration_exposes_bounded_timing_policy():
    registration = import_module("simready.foundation.tier_newton.runtime_tests.fet022_driven_joints.full_range_sweep")
    assert registration.FULL_RANGE_SWEEP_KWARGS["version"] == "1.5.7"
    assert registration.FULL_RANGE_SWEEP_KWARGS["max_duration"] == 14400
    assert registration.FULL_RANGE_SWEEP_KWARGS["config_defaults"]["max_sweep_wall_seconds"] == 3360


def test_explicit_longer_wall_budget_is_bounded_without_extending_the_default():
    assert frs.get_defaults()["max_sweep_wall_seconds"] == 3360
    assert timing.SweepBudget({**frs.get_defaults(), "max_sweep_wall_seconds": 14340}).wall_seconds == 14340
    for invalid in (14340.001, math.inf, math.nan, True, "14340"):
        with pytest.raises(ValueError):
            timing.SweepBudget({**frs.get_defaults(), "max_sweep_wall_seconds": invalid})


def test_diagnostics_preserve_commands_native_reads_steps_and_capture_cadence(monkeypatch):
    from contextlib import nullcontext

    original = frs.SweepDiagnostics

    class NoTiming:
        def __init__(self, _ctx):
            pass

        def measure(self, _name):
            return nullcontext()

        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: None

    def run(recording):
        clock = [10.0]
        monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
        monkeypatch.setattr(frs, "SweepDiagnostics", original if recording else NoTiming)
        ctx, robot, scene, config, metrics, commands, failures, steps, position = _run_fixture(monkeypatch)
        captures, camera, videos = [], [], []
        queries = {"positions": 0, "limits": 0, "speeds": 0}
        for name, key in (
            ("get_joint_positions", "positions"),
            ("get_joint_position_limits", "limits"),
            ("get_joint_velocity_limits", "speeds"),
        ):
            getter = getattr(robot, name)

            def counted(getter=getter, key=key):
                queries[key] += 1
                return getter()

            setattr(robot, name, counted)
        tick = ctx.step_one

        async def step():
            await tick()
            clock[0] += 0.03

        async def capture(**kwargs):
            captures.append(kwargs)
            clock[0] += 0.2
            return str(len(captures))

        def follow(**kwargs):
            camera.append(kwargs)
            clock[0] += 0.005

        def encode(frames, **kwargs):
            videos.append((list(frames), kwargs))
            clock[0] += 0.5

        ctx.step_one, ctx.capture_frame, ctx.encode_video = step, capture, encode
        ctx.scene.update_camera_follow = follow
        history = import_module(frs.__name__.rsplit(".", 1)[0] + ".motion_history")
        monkeypatch.setattr(
            history,
            "make_joint_observer",
            lambda *_args, **_kwargs: SimpleNamespace(
                history=None,
                record_capture=lambda *_args: None,
                finish=lambda *_args: None,
            ),
        )
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config, started_at=5.0))
        assert not failures
        return commands, steps[0], captures, camera, videos, queries, position, metrics

    baseline = run(False)
    observed = run(True)
    assert observed[:6] == baseline[:6]
    np.testing.assert_array_equal(observed[6], baseline[6])
    row = observed[7]["frs_execution_timing"]
    assert row["stop_reason"] == "procedure_completed"
    assert row["completed_nominal_ticks"] == observed[1] == row["planned_nominal_ticks_estimate"]
    assert row["setup_elapsed_wall_seconds"] == 5.0
    assert row["costs"]["stepping"]["wall_seconds"] == pytest.approx(observed[1] * 0.03)
    assert row["costs"]["captures"]["wall_seconds"] == pytest.approx(len(observed[2]) * 0.2)
    assert row["costs"]["camera"]["wall_seconds"] == pytest.approx(len(observed[3]) * 0.005)
    assert row["costs"]["encoding"]["wall_seconds"] == pytest.approx(0.5)
    assert row["observed_service_seconds_per_nominal_tick"] > 0.03
    assert row["estimated_remaining_wall_seconds"] == 0
    assert "not native solver CPU time" in row["cost_basis"]


@pytest.mark.parametrize("kind", ["segment", "simulation", "wall"])
def test_budget_interruptions_keep_original_error_and_partial_context(monkeypatch, kind):
    overrides = {
        "segment": {"max_sweep_segment_seconds": 1},
        "simulation": {"max_sweep_simulation_seconds": 0.01},
        "wall": {"max_sweep_wall_seconds": 0.1},
    }[kind]
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(monkeypatch, overrides)
    clock = [0.0]
    monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
    tick = ctx.step_one

    async def costly_tick():
        await tick()
        clock[0] += 0.2

    ctx.step_one = costly_tick
    with pytest.raises(timing.SweepBudgetExceeded) as raised:
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    row = metrics["frs_execution_timing"]
    assert row["stop_reason"] == raised.value.reason == kind + "_budget"
    assert row["completed_nominal_ticks"] == steps[0]
    assert metrics["frs_completed_nominal_simulation_seconds"] == steps[0] / config["physics_fps"]
    assert not failures and not commands and "frs_joints_passed" not in metrics


@pytest.mark.parametrize("error", [RuntimeError("required tick failed"), asyncio.CancelledError(), SystemExit(7)])
def test_tick_failure_or_cancellation_is_not_masked_by_diagnostics(monkeypatch, error):
    ctx, robot, scene, config, metrics, _commands, failures, _steps, _position = _run_fixture(monkeypatch)

    async def broken():
        raise error

    ctx.step_one = broken
    with pytest.raises(type(error)) as raised:
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert raised.value is error
    row = metrics["frs_execution_timing"]
    assert row["completed_nominal_ticks"] == 0
    assert row["costs"]["stepping"]["attempts"] == 1
    assert row["stop_reason"] == ("cancelled" if isinstance(error, asyncio.CancelledError) else "execution_error")
    assert not failures and "frs_joints_passed" not in metrics


def test_optional_metric_failure_warns_once_without_changing_execution(monkeypatch):
    ctx, robot, scene, config, metrics, commands, failures, steps, _position = _run_fixture(monkeypatch)
    add_metric = ctx.add_metric
    warnings = []
    ctx.warn = warnings.append

    def selective(key, value):
        if key == "frs_execution_timing":
            raise RuntimeError("optional sink unavailable")
        else:
            add_metric(key, value)

    ctx.add_metric = selective
    asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert not failures and commands and steps[0] == 2 + len(commands)
    assert metrics["frs_joints_passed"] == 1
    assert len(warnings) == 1 and "diagnostics unavailable" in warnings[0]


def test_diagnostic_state_and_cost_faults_cannot_replace_an_operation_error(monkeypatch):
    ctx = SimpleNamespace(warn=lambda _message: None, add_metric=lambda *_args: None)
    diagnostic = frs.SweepDiagnostics(ctx)

    class BadName:
        def __str__(self):
            raise ValueError("bad diagnostic name")

    diagnostic.position(BadName(), "segment")
    assert diagnostic.active_joint is None and diagnostic.warned
    diagnostic.attach(SimpleNamespace(started_at=object()))
    original = RuntimeError("native command failed")
    with pytest.raises(RuntimeError) as raised:
        with diagnostic.measure("not-a-cost-bucket"):
            raise original
    assert raised.value is original


def test_remaining_budget_estimate_is_advisory_not_a_control_or_verdict(monkeypatch):
    metrics = {}
    diagnostic = frs.SweepDiagnostics(
        SimpleNamespace(
            warn=lambda _message: None,
            add_metric=lambda key, value: metrics.update({key: value}),
        )
    )
    clock = [0.0]
    monkeypatch.setattr(timing.time, "monotonic", lambda: clock[0])
    budget = timing.SweepBudget({**frs.get_defaults(), "max_sweep_wall_seconds": 10})
    diagnostic.attach(budget)
    diagnostic.planned_ticks = 100
    budget.ticks = 10
    clock[0] = 2.0
    diagnostic.publish()
    row = metrics["frs_execution_timing"]
    assert row["observed_service_seconds_per_nominal_tick"] == 0.2
    assert row["estimated_remaining_wall_seconds"] == 18.0
    assert row["estimated_budget_insufficient"] is True
    assert row["stop_reason"] == "running" and budget.wall_seconds == 10
    budget.check_wall()
    diagnostic.finish()
    final = metrics["frs_execution_timing"]
    assert final["planned_nominal_ticks_estimate"] == 100
    assert final["completed_nominal_ticks"] == 10
    assert final["estimated_remaining_wall_seconds"] == 0
    assert final["estimated_budget_insufficient"] is False


def test_plan_estimate_uses_no_queries_and_is_bounded_for_large_joint_lists(monkeypatch):
    diagnostic = frs.SweepDiagnostics(SimpleNamespace(warn=lambda _message: None))
    budget = timing.SweepBudget(frs.get_defaults())
    diagnostic.attach(budget)

    def no_planning(*_args):
        raise AssertionError("large diagnostic estimate must be omitted")

    diagnostic.estimate_plan([(0, "joint")] * 1025, None, None, None, None, {}, no_planning, no_planning, no_planning)
    assert diagnostic.planned_ticks is None and diagnostic.planning_omitted_joints == 1025


@pytest.mark.parametrize("error", [RuntimeError("required tick failed"), asyncio.CancelledError(), SystemExit(7)])
def test_rejected_structured_metric_preserves_numeric_progress_and_original_interruption(monkeypatch, error):
    ctx, robot, scene, config, metrics, _commands, failures, steps, _position = _run_fixture(monkeypatch)
    add_metric = ctx.add_metric
    warnings = []
    ctx.warn = warnings.append

    def reject_structured(key, value):
        if key == "frs_execution_timing":
            raise RuntimeError("structured sink unavailable")
        add_metric(key, value)

    ctx.add_metric = reject_structured
    tick = ctx.step_one

    async def interrupt_second_tick():
        if steps[0] == 1:
            raise error
        await tick()

    ctx.step_one = interrupt_second_tick
    with pytest.raises(type(error)) as raised:
        asyncio.run(frs.run_full_range_sweep(ctx, robot, scene, config))
    assert raised.value is error
    assert metrics["frs_completed_nominal_simulation_seconds"] == 1 / config["physics_fps"]
    assert "frs_execution_timing" not in metrics and "frs_joints_passed" not in metrics
    assert not failures and len(warnings) == 1


def test_failed_structured_calculation_still_attempts_the_numeric_progress_metric():
    metrics = {}
    diagnostic = frs.SweepDiagnostics(
        SimpleNamespace(
            warn=lambda _message: None,
            add_metric=lambda key, value: metrics.update({key: value}),
        )
    )
    budget = timing.SweepBudget(frs.get_defaults())
    diagnostic.attach(budget)
    budget.ticks = 12
    diagnostic.planned_ticks = object()  # Optional structured calculation cannot subtract this value.
    diagnostic.publish()
    assert metrics["frs_completed_nominal_simulation_seconds"] == 12 / budget.fps
    assert "frs_execution_timing" not in metrics and diagnostic.warned

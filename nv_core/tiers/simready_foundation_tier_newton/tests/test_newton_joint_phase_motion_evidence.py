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

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    effort_limit,
    full_range_sweep,
    motion_history,
    state_accuracy,
    velocity_limit,
)


class _Motion:
    def __init__(self, active=True):
        self.history = object() if active else None
        self.samples = []
        self.captures = []
        self.reasons = []
        self.warnings = 0

    def sample(self, values, time_s, phase):
        self.samples.append((dict(values), time_s, phase))

    def record_capture(self, path):
        self.captures.append((path, len(self.samples)))

    def finish(self, reason):
        self.reasons.append(reason)

    def _warn(self):
        self.warnings += 1


class _Context:
    def __init__(self, video=True):
        self.steps = 0
        self.setup_steps = []
        self.metrics = {}
        self.messages = []
        self.video = video
        self.frames = []
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)

    async def step_one(self):
        self.steps += 1

    async def physics_steps(self, count):
        self.setup_steps.append(count)

    async def capture_frame(self, **kwargs):
        if not self.video:
            return None
        path = "frame_%03d.png" % len(self.frames)
        self.frames.append(path)
        return path

    def add_metric(self, name, value):
        self.metrics[name] = value

    def step(self, message):
        self.messages.append(message)

    log = step
    warn = step

    def skip(self, message):
        raise AssertionError("unexpected skip: " + message)

    def fail(self, message):
        raise AssertionError("unexpected failure: " + message)

    def encode_video(self, *args, **kwargs):
        pass


class _Robot:
    dof_names = ["hinge"]
    dof_count = 1
    prim_path = "/Robot"

    def __init__(self):
        self.position = 0.0
        self.velocity = 1.0
        self.commands = []
        self.forces = []
        self.read_count = 0
        self.fail_reads = set()

    def get_joint_positions(self):
        self.read_count += 1
        if self.read_count in self.fail_reads:
            raise RuntimeError("required or optional position view unavailable")
        return np.array([self.position], dtype=float)

    def get_joint_velocities(self):
        return np.array([self.velocity], dtype=float)

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def get_joint_effort_limits(self):
        return np.array([10.0])

    def set_joint_position_target(self, index, target):
        assert index == 0
        self.position = float(target)
        self.commands.append(float(target))

    def set_joint_position_targets(self, targets):
        self.set_joint_position_target(0, targets[0])

    def apply_velocity_limits_to_tensor_view(self, values):
        self.velocity_limits = values.copy()

    def get_child_body_path(self, index):
        assert index == 0
        return "/Robot/child"


def _recording(monkeypatch, active=True):
    observers = []

    def begin(ctx, scene, joint_name, name, channels, metadata=None, **kwargs):
        observer = _Motion(active=active)
        observer.name = name
        observer.channels = channels
        observer.metadata = metadata
        observers.append(observer)
        return observer

    monkeypatch.setattr(motion_history, "make_joint_observer", begin)
    return observers


def _bounds(monkeypatch, module):
    monkeypatch.setattr(module, "compute_world_aligned_bbox", lambda prim: SimpleNamespace(volume=1.0))
    monkeypatch.setattr(module, "check_bbox_explode", lambda *args: None)


def _assert_clock(observer, step_count, fps=4.0):
    assert len(observer.samples) == step_count
    assert [sample[1] for sample in observer.samples] == pytest.approx(
        [(index + 1) / fps for index in range(step_count)]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("video", [True, False])
async def test_full_range_clock_and_actual_targets_cover_three_segments(monkeypatch, video):
    observers = _recording(monkeypatch)
    _bounds(monkeypatch, full_range_sweep)
    ctx, robot = _Context(video=video), _Robot()
    await full_range_sweep.run_full_range_sweep(
        ctx,
        robot,
        {},
        {
            "physics_fps": 4,
            "capture_fps": 4,
            "settle_seconds": 0,
            "sweep_speed_scale": 2,
            "pause_at_limits_seconds": 0.25,
        },
    )
    observer = observers[0]
    assert ctx.steps == 9
    assert len(robot.commands) == 9
    _assert_clock(observer, 9)
    assert [sample[0]["target"] for sample in observer.samples] == robot.commands
    assert {sample[2] for sample in observer.samples} == {
        "to_max",
        "to_max_hold",
        "to_min",
        "to_min_hold",
        "to_zero",
        "to_zero_hold",
    }
    assert observer.samples[0][0]["target"] != observer.samples[0][0]["final_goal"]
    assert observer.reasons == ["sweep_sequence_completed"]
    assert observer.metadata["runtime_lower"] == -1.0
    assert observer.metadata["runtime_upper"] == 1.0
    assert "RobotHandle.get_joint_position_limits()" in observer.metadata["runtime_limit_source"]
    assert "not raw USD authored limits" in observer.metadata["runtime_limit_source"]
    assert "authored_lower" not in observer.metadata and "authored_upper" not in observer.metadata
    assert bool(observer.captures) is video
    assert ctx.metrics["frs_joints_failed"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_read,partial", [(2, True), (3, False)])
async def test_full_range_optional_read_failure_does_not_hide_required_read_failure(monkeypatch, failing_read, partial):
    observers = _recording(monkeypatch)
    _bounds(monkeypatch, full_range_sweep)
    ctx, robot = _Context(video=False), _Robot()
    robot.fail_reads = {failing_read}
    config = {"physics_fps": 4, "settle_seconds": 0, "sweep_speed_scale": 2, "pause_at_limits_seconds": 0.25}
    if partial:
        await full_range_sweep.run_full_range_sweep(ctx, robot, {}, config)
        assert observers[0].warnings == 1
        assert observers[0].samples[0][0]["position"] is None
        assert ctx.metrics["frs_joints_failed"] == 0
    else:
        with pytest.raises(RuntimeError, match="position view unavailable"):
            await full_range_sweep.run_full_range_sweep(ctx, robot, {}, config)
        assert observers[0].reasons == []


@pytest.mark.asyncio
async def test_full_range_old_runner_does_not_add_diagnostic_readbacks(monkeypatch):
    observers = _recording(monkeypatch, active=False)
    _bounds(monkeypatch, full_range_sweep)
    ctx, robot = _Context(video=False), _Robot()
    await full_range_sweep.run_full_range_sweep(
        ctx,
        robot,
        {},
        {"physics_fps": 4, "settle_seconds": 0, "sweep_speed_scale": 2, "pause_at_limits_seconds": 0.25},
    )
    assert ctx.steps == 9
    # Initial pose, three heartbeat reads, three required holds, two required
    # live segment starts, and final pose. None are diagnostic-only reads.
    assert robot.read_count == 10
    assert observers[0].samples == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_read", [4, 7])
async def test_full_range_live_segment_start_read_is_required_without_recording(monkeypatch, failing_read):
    observers = _recording(monkeypatch, active=False)
    _bounds(monkeypatch, full_range_sweep)
    ctx, robot = _Context(video=False), _Robot()
    robot.fail_reads = {failing_read}
    with pytest.raises(RuntimeError, match="position view unavailable"):
        await full_range_sweep.run_full_range_sweep(
            ctx,
            robot,
            {},
            {"physics_fps": 4, "settle_seconds": 0, "sweep_speed_scale": 2, "pause_at_limits_seconds": 0.25},
        )
    assert "frs_joints_passed" not in ctx.metrics
    assert observers[0].samples == []
    assert observers[0].reasons == []


@pytest.mark.asyncio
async def test_state_accuracy_records_smoothstep_commands_and_cumulative_waypoint_clock(monkeypatch):
    _bounds(monkeypatch, state_accuracy)
    ctx, robot, observer = _Context(), _Robot(), _Motion()
    clock = {"steps": 0, "physics_fps": 4, "issued_target": None}
    joint = {"index": 0, "name": "hinge"}
    frames = []
    for number, goal in enumerate([1.0, -0.5]):
        phase = "waypoint_%03d" % number
        await state_accuracy._run_motion_to_target(
            ctx,
            robot,
            joint,
            goal,
            4,
            1,
            frames,
            SimpleNamespace(volume=1),
            10,
            None,
            None,
            1,
            motion=observer,
            motion_clock=clock,
            motion_phase=phase,
        )
        await state_accuracy._run_settle_to_target(
            ctx,
            robot,
            joint,
            goal,
            2,
            1,
            frames,
            1,
            phase,
            motion=observer,
            motion_clock=clock,
            motion_phase=phase,
        )
    assert ctx.steps == 12
    assert len(robot.commands) == 8
    _assert_clock(observer, 12)
    assert [sample[0]["target"] for sample in observer.samples[:4]] == pytest.approx([0.15625, 0.5, 0.84375, 1.0])
    assert observer.samples[0][0]["final_goal"] == 1.0
    assert observer.samples[0][0]["error"] == 0.0
    assert observer.samples[0][0]["goal_error"] == pytest.approx(0.84375)
    assert observer.samples[4][2] == "waypoint_000_settle"
    assert observer.samples[6][2] == "waypoint_001_ramp"
    assert observer.captures[0][1] == 0  # Readback follows capture in the original ramp.


@pytest.mark.asyncio
async def test_state_accuracy_early_response_records_the_complete_issued_ramp(monkeypatch):
    _bounds(monkeypatch, state_accuracy)
    ctx, robot, observer = _Context(video=False), _Robot(), _Motion()
    robot.velocity = 0.0
    original_command = robot.set_joint_position_targets

    def early_arrival(targets):
        original_command(targets)
        robot.position = 1.0

    monkeypatch.setattr(robot, "set_joint_position_targets", early_arrival)
    clock = {"steps": 0, "physics_fps": 4, "issued_target": None}
    joint = {"index": 0, "name": "hinge"}
    await state_accuracy._run_motion_to_target(
        ctx,
        robot,
        joint,
        1.0,
        4,
        1,
        [],
        SimpleNamespace(volume=1),
        10,
        None,
        None,
        1,
        motion=observer,
        motion_clock=clock,
    )
    await state_accuracy._run_settle_to_target(
        ctx,
        robot,
        joint,
        1.0,
        2,
        1,
        [],
        1,
        "trial",
        motion=observer,
        motion_clock=clock,
    )
    assert robot.commands == [0.15625, 0.5, 0.84375, 1.0]
    assert ctx.steps == 6
    _assert_clock(observer, 6)
    assert [sample[0]["target"] for sample in observer.samples] == [0.15625, 0.5, 0.84375, 1.0, 1.0, 1.0]
    assert all(sample[0]["final_goal"] == 1.0 for sample in observer.samples)


@pytest.mark.asyncio
async def test_velocity_reuses_signed_readback_and_keeps_existing_stop_condition(monkeypatch):
    observers = _recording(monkeypatch)
    _bounds(monkeypatch, velocity_limit)
    monkeypatch.setattr(velocity_limit, "resolve_usd_max_velocities", lambda **kwargs: {})
    joint = {
        "index": 0,
        "name": "hinge",
        "lower": -1,
        "upper": 1,
        "max_velocity": 1.0,
        "max_velocity_source": "physxJoint:maxJointVelocity",
    }
    monkeypatch.setattr(velocity_limit, "find_joints_with_velocity_limits", lambda *args, **kwargs: [joint])
    ctx, robot = _Context(), _Robot()
    velocities = iter([-0.2, -0.01, 0.0])
    monkeypatch.setattr(robot, "get_joint_velocities", lambda: np.array([next(velocities)]))
    await velocity_limit.run_velocity_limit(
        ctx,
        robot,
        {},
        {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "capture_settled_grace_frames": 2},
    )
    observer = observers[0]
    assert ctx.steps == 3
    assert len(robot.commands) == 1
    _assert_clock(observer, 3)
    assert [sample[0]["velocity"] for sample in observer.samples] == [-0.2, -0.01, 0.0]
    assert all(sample[0]["position_target"] == robot.commands[0] for sample in observer.samples)
    assert all(sample[0]["allowed_speed"] == 1.05 for sample in observer.samples)
    assert observer.channels["speed_limit"]["source"] == "resolved comparison ceiling; see limit_source/provenance"
    assert observer.metadata["limit_source"] == "physxJoint:maxJointVelocity"
    assert observer.reasons == ["velocity_stop_condition"]
    assert ctx.metrics["vel_joints_failed"] == 0


@pytest.mark.asyncio
async def test_effort_records_external_world_forces_and_cumulative_direction_clock(monkeypatch):
    observers = _recording(monkeypatch)
    _bounds(monkeypatch, effort_limit)

    vectors = [SimpleNamespace(label="+x", direction=(1, 0, 0)), SimpleNamespace(label="-x", direction=(-1, 0, 0))]
    monkeypatch.setattr(effort_limit, "generate_12_force_directions", lambda: vectors)
    monkeypatch.setattr(effort_limit, "visualize_force_arrow", lambda *args: None)
    monkeypatch.setattr(effort_limit, "clear_force_visualization", lambda *args: None)
    monkeypatch.setattr(effort_limit, "clear_external_force", lambda *args: None)
    ctx, robot = _Context(), _Robot()

    def apply_force(body, direction, magnitude):
        robot.forces.append(tuple(component * magnitude for component in direction))
        return True

    monkeypatch.setattr(robot, "apply_external_force", apply_force, raising=False)
    await effort_limit.run_effort_limit(
        ctx,
        robot,
        {"active_physics_engine": "newton"},
        {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
    )
    observer = observers[0]
    assert ctx.steps == 60  # Existing minimum force-probe budget; recording adds no ticks.
    assert len(robot.forces) == 60
    _assert_clock(observer, 60)
    observed_forces = [
        (sample[0]["external_force_x"], sample[0]["external_force_y"], sample[0]["external_force_z"])
        for sample in observer.samples
    ]
    assert observed_forces == robot.forces
    assert observer.samples[0][2] == "force_+x"
    assert observer.samples[30][2] == "force_-x"
    assert all(
        observer.channels[channel]["unit"] == "N"
        for channel in ["external_force_x", "external_force_y", "external_force_z"]
    )
    assert "not measured actuator torque" in observer.metadata["force_basis"]
    assert observer.metadata["runtime_lower"] == -1.0
    assert observer.metadata["runtime_upper"] == 1.0
    assert "RobotHandle.get_joint_position_limits()" in observer.metadata["runtime_limit_source"]
    assert "not raw USD authored limits" in observer.metadata["runtime_limit_source"]
    assert "authored_lower" not in observer.metadata and "authored_upper" not in observer.metadata
    assert observer.reasons == ["force_directions_completed"]
    assert ctx.metrics["eff_joints_failed"] == 0


def _effort_probe(monkeypatch, robot, submitted=True):
    observers = _recording(monkeypatch)
    _bounds(monkeypatch, effort_limit)
    vectors = [SimpleNamespace(label="+x", direction=(1, 0, 0)), SimpleNamespace(label="-x", direction=(-1, 0, 0))]
    monkeypatch.setattr(effort_limit, "generate_12_force_directions", lambda: vectors)
    monkeypatch.setattr(effort_limit, "visualize_force_arrow", lambda *args: None)
    monkeypatch.setattr(effort_limit, "clear_force_visualization", lambda *args: None)
    monkeypatch.setattr(effort_limit, "clear_external_force", lambda *args: None)

    def submit(body, direction, magnitude):
        if submitted:
            robot.forces.append(tuple(component * magnitude for component in direction))
        return submitted

    monkeypatch.setattr(robot, "apply_external_force", submit, raising=False)
    return observers


@pytest.mark.asyncio
@pytest.mark.parametrize("refinement_requested", [False, True])
async def test_effort_failed_force_is_not_fabricated_bisection_threshold(monkeypatch, refinement_requested):
    ctx, robot = _Context(video=False), _Robot()
    robot.position = 2.0  # Beyond [-1, 1] plus the unchanged allowance.
    observers = _effort_probe(monkeypatch, robot)
    failures = []
    ctx.fail = failures.append

    await effort_limit.run_effort_limit(
        ctx,
        robot,
        {},
        {
            "physics_fps": 4,
            "capture_fps": 4,
            "settle_seconds": 0,
            "test_duration_seconds": 0.1,
            "force_magnitude_newtons": 10.0,
            "bisection_enabled": refinement_requested,
            "bisection_min_newtons": 123.0,
            "bisection_max_iterations": 50,
        },
    )

    assert len(failures) == 1 and ctx.metrics["eff_joints_failed"] == 1
    assert ctx.steps == 30 and len(robot.forces) == 30  # Same first-direction budget; no refinement.
    (record,) = ctx.metrics["eff_joint_results"]
    assert record["min_break_force_newtons"] is None
    assert record["commanded_force_at_failure_newtons"] == 10.0
    assert record["bisection_refinement_requested"] is refinement_requested
    assert record["bisection_refinement_available"] is False
    assert record["broke_directions"] == ["+x"]
    assert record["ok"] is False
    assert (
        any("refinement was requested but is not implemented" in message for message in ctx.messages)
        is refinement_requested
    )
    assert any("Minimum failure threshold: unavailable" in message for message in ctx.messages)
    assert observers[0].reasons == ["first_break_detected"]


class _TwoEffortJoints(_Robot):
    dof_names = ["mapped", "unmapped"]
    dof_count = 2

    def get_joint_position_limits(self):
        return np.array([-1.0, -1.0]), np.array([1.0, 1.0])

    def get_joint_effort_limits(self):
        return np.array([10.0, 10.0])

    def get_joint_positions(self):
        return np.array([self.position, self.position])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["submit", "tick", "read", "invalid", "bounds", "reset", "cancel", "capture", "cleanup", "encode"]
)
@pytest.mark.parametrize("bad_sink", [False, True])
async def test_whole_eff_probe_retains_prior_and_partial_evidence(monkeypatch, failure, bad_sink):
    import asyncio

    ctx, robot = _Context(video=True), _TwoEffortJoints()
    vectors = effort_limit.generate_12_force_directions
    observers = _effort_probe(monkeypatch, robot)
    monkeypatch.setattr(effort_limit, "generate_12_force_directions", vectors)
    robot.get_child_body_path = lambda index: "/Robot/child" + str(index)
    primary = asyncio.CancelledError("stop") if failure == "cancel" else RuntimeError("required " + failure)
    submit = robot.apply_external_force
    tick = ctx.step_one
    bounds = effort_limit.compute_world_aligned_bbox

    def ready():
        return ctx.steps >= 65

    def force(*args):
        if ready() and failure == "submit":
            raise primary
        return submit(*args)

    async def step():
        if ready() and failure in ("tick", "cancel"):
            raise primary
        await tick()

    def read():
        if ctx.steps > 65 and failure == "read":
            raise primary
        return [0.0, float("nan") if ctx.steps > 65 and failure == "invalid" else 0.0]

    def bbox(*args):
        if ready() and failure == "bounds":
            raise primary
        return bounds(*args)

    async def reset(*args, **kwargs):
        if ready() and failure == "reset":
            raise primary

    async def capture(**kwargs):
        if ctx.steps > 65 and failure == "capture":
            raise primary
        return "frame.png"

    def cleanup(*args):
        if ready() and failure == "cleanup":
            raise primary

    def encode(*args, **kwargs):
        if failure == "encode":
            raise primary
        return None

    original_metric = ctx.add_metric

    def publish(name, value):
        if bad_sink and name == "eff_joints_passed":
            raise OSError("optional sink")
        original_metric(name, value)

    robot.apply_external_force, robot.get_joint_positions = force, read
    ctx.step_one, ctx.capture_frame, ctx.encode_video, ctx.add_metric = step, capture, encode, publish
    monkeypatch.setattr(effort_limit, "compute_world_aligned_bbox", bbox)
    monkeypatch.setattr(effort_limit, "reset_to_default", reset)
    monkeypatch.setattr(effort_limit, "clear_external_force", cleanup)
    with pytest.raises(BaseException) as caught:
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {"default_state": object()},
            {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
        )
    if failure != "invalid":
        cause = caught.value
        while cause is not primary and cause.__cause__ is not None:
            cause = cause.__cause__
        assert cause is primary
    else:
        assert "nonfinite" in str(caught.value)
    assert ctx.metrics["eff_joints_tested"] == (2 if failure == "encode" else 1)
    assert ctx.metrics["eff_joint_results"][0]["name"] == "mapped"
    if failure != "encode":
        partial = ctx.metrics["eff_incomplete_joint_evidence"]
        assert partial["name"] == "unmapped" and partial["status"] == "incomplete"
        assert partial["evaluated_directions"]
        assert "ok" not in partial
    assert observers[0].reasons == ["force_directions_completed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_index", [0, 1])
async def test_effort_unmapped_required_body_is_error_without_false_pass(monkeypatch, missing_index):
    ctx, robot = _Context(video=False), _TwoEffortJoints()
    observers = _effort_probe(monkeypatch, robot)
    robot._child_body_resolve_detail = "test fixture: imported child mapping unavailable"
    monkeypatch.setattr(robot, "get_child_body_path", lambda index: None if index == missing_index else "/Robot/child")

    with pytest.raises(RuntimeError, match="required child-body mapping is unresolved") as error:
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
        )

    assert "imported child mapping unavailable" in str(error.value)
    assert ctx.metrics["eff_joints_tested"] == missing_index
    assert ctx.metrics["eff_joints_passed"] == missing_index
    assert ctx.metrics["eff_joints_failed"] == 0
    assert len(ctx.metrics["eff_joint_results"]) == missing_index
    assert ctx.steps == missing_index * 60 and len(robot.forces) == missing_index * 60
    assert all(record["name"] != "unmapped" for record in ctx.metrics["eff_joint_results"])
    assert all(observer.reasons == ["force_directions_completed"] for observer in observers)


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable_metric", [None, "eff_joint_results"])
async def test_effort_mapping_exception_keeps_prior_evidence_and_primary(monkeypatch, unavailable_metric):
    ctx, robot = _Context(video=False), _TwoEffortJoints()
    _effort_probe(monkeypatch, robot)
    primary = RuntimeError("selected downstream identity unavailable")

    def resolve(index):
        if index == 1:
            raise primary
        return "/Robot/child"

    original = ctx.add_metric

    def publish(name, value):
        if name == unavailable_metric:
            raise OSError("optional metric sink unavailable")
        original(name, value)

    monkeypatch.setattr(robot, "get_child_body_path", resolve)
    monkeypatch.setattr(ctx, "add_metric", publish)
    with pytest.raises(RuntimeError) as caught:
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
        )
    assert caught.value is primary
    assert ctx.metrics["eff_joints_tested"] == 1
    assert ctx.metrics["eff_joints_passed"] == 1
    assert ctx.metrics["eff_joints_failed"] == 0
    if unavailable_metric is None:
        assert [record["name"] for record in ctx.metrics["eff_joint_results"]] == ["mapped"]
    else:
        assert any("optional metric sink unavailable" in note for note in primary.__notes__)
    assert ctx.steps == 60 and len(robot.forces) == 60


@pytest.mark.asyncio
async def test_effort_rejected_force_submission_is_error_before_observation(monkeypatch):
    ctx, robot = _Context(video=False), _Robot()
    observers = _effort_probe(monkeypatch, robot, submitted=False)

    with pytest.raises(RuntimeError, match="required external force could not be submitted"):
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
        )

    assert ctx.steps == 0 and not robot.forces
    assert ctx.metrics["eff_joint_results"] == []
    assert observers[0].samples == []
    assert observers[0].warnings == 1
    assert observers[0].reasons == ["force_application_unavailable"]


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [float("nan"), float("inf"), float("-inf")])
async def test_effort_invalid_pose_is_runtime_error_without_fake_measurement(monkeypatch, position):
    ctx, robot = _Context(video=False), _Robot()
    robot.position = position
    observers = _effort_probe(monkeypatch, robot)
    failures = []
    ctx.fail = failures.append

    with pytest.raises(RuntimeError, match="required position readback is nonfinite"):
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
        )

    assert not failures
    assert ctx.steps == 1 and len(robot.forces) == 1
    assert observers[0].samples == [] and observers[0].warnings == 1
    assert ctx.metrics["eff_joint_results"] == []
    assert observers[0].reasons == ["required_position_nonfinite"]


@pytest.mark.asyncio
@pytest.mark.parametrize("positions", [None, np.array([])])
async def test_effort_missing_pose_is_runtime_error_without_fake_measurement(monkeypatch, positions):
    ctx, robot = _Context(video=False), _Robot()
    observers = _effort_probe(monkeypatch, robot)
    monkeypatch.setattr(robot, "get_joint_positions", lambda: positions)

    with pytest.raises(RuntimeError, match="required position readback is unavailable"):
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1},
        )

    assert ctx.steps == 1 and len(robot.forces) == 1
    assert observers[0].samples == [] and observers[0].warnings == 1
    assert ctx.metrics["eff_joint_results"] == []
    assert observers[0].reasons == ["required_position_unavailable"]

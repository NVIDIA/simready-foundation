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

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    effort_limit,
    full_range_sweep,
    motion_history,
    state_accuracy,
    velocity_limit,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


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

    def get_child_body_world_com(self, body_path):
        assert body_path == "/Robot/child"
        return (1.0, 2.0, 3.0)


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
async def test_effort_requires_physx_force_interface_before_simulation(monkeypatch):
    monkeypatch.setitem(sys.modules, "omni.physx", SimpleNamespace(get_physx_simulation_interface=lambda: None))
    ctx, robot = _Context(), _Robot()
    with pytest.raises(RuntimeError, match="setup error") as error:
        await effort_limit.run_effort_limit(ctx, robot, {"active_physics_engine": "physx"}, {})

    assert "simulation interface is not available" in str(error.value)
    assert "asset was not evaluated" in str(error.value)
    assert ctx.steps == 0 and not ctx.setup_steps
    assert not robot.forces and not robot.commands


@pytest.mark.asyncio
async def test_effort_records_external_world_forces_and_cumulative_direction_clock(monkeypatch):
    observers = _recording(monkeypatch)
    _bounds(monkeypatch, effort_limit)
    monkeypatch.setitem(sys.modules, "omni.physx", SimpleNamespace(get_physx_simulation_interface=lambda: object()))
    vectors = [SimpleNamespace(label="+x", direction=(1, 0, 0)), SimpleNamespace(label="-x", direction=(-1, 0, 0))]
    monkeypatch.setattr(effort_limit, "generate_12_force_directions", lambda: vectors)
    monkeypatch.setattr(effort_limit, "visualize_force_arrow", lambda *args, **kwargs: None)
    monkeypatch.setattr(effort_limit, "clear_force_visualization", lambda *args: None)
    monkeypatch.setattr(effort_limit, "clear_external_force", lambda *args: None)
    ctx, robot = _Context(), _Robot()

    def unexpected_native_force(*args, **kwargs):
        raise AssertionError("Core effort probes must use the PhysX simulation interface")

    monkeypatch.setattr(robot, "apply_external_force", unexpected_native_force, raising=False)
    monkeypatch.setattr(
        effort_limit,
        "apply_external_force",
        lambda stage, body, direction, magnitude, point: robot.forces.append(
            (tuple(component * magnitude for component in direction), tuple(point))
        )
        or True,
    )
    await effort_limit.run_effort_limit(
        ctx,
        robot,
        {"active_physics_engine": "physx"},
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
    assert observed_forces == [force for force, _point in robot.forces]
    assert all(point == (1.0, 2.0, 3.0) for _force, point in robot.forces)
    assert observer.metadata["force_point_basis"] == "live child-body center of mass"
    assert observer.samples[0][0]["force_point_x"] == 1.0
    assert observer.samples[0][0]["force_point_y"] == 2.0
    assert observer.samples[0][0]["force_point_z"] == 3.0
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
    monkeypatch.setattr(effort_limit, "visualize_force_arrow", lambda *args, **kwargs: None)
    monkeypatch.setattr(effort_limit, "clear_force_visualization", lambda *args: None)
    monkeypatch.setattr(effort_limit, "clear_external_force", lambda *args: None)

    def submit(body, direction, magnitude, point):
        if submitted:
            robot.forces.append((tuple(component * magnitude for component in direction), tuple(point)))
        return submitted

    monkeypatch.setitem(sys.modules, "omni.physx", SimpleNamespace(get_physx_simulation_interface=lambda: object()))
    monkeypatch.setattr(
        effort_limit,
        "apply_external_force",
        lambda stage, body, direction, magnitude, point: submit(body, direction, magnitude, point),
    )
    return observers


@pytest.mark.asyncio
@pytest.mark.parametrize("read_failure", ["exception", "nonfinite"])
@pytest.mark.parametrize("optional_failure", [None, "warn", "finish", "cleanup", "metric"])
async def test_required_position_failure_preserves_prior_joint_and_evaluated_direction(
    monkeypatch, read_failure, optional_failure
):
    ctx, robot = _Context(video=False), _TwoEffortJoints()
    observers = _effort_probe(monkeypatch, robot)
    primary = OSError("required native position lost")
    reads = 0
    attempts = []

    def positions():
        nonlocal reads
        reads += 1
        if reads == 91:
            if read_failure == "exception":
                raise primary
            return np.array([0.0, float("nan")])
        return np.array([0.0, 2.0])

    def warn(observer):
        attempts.append("warn")
        if optional_failure == "warn":
            raise ValueError("optional warning failed")

    original_finish = _Motion.finish

    def finish(observer, reason):
        if reason.startswith("required_position"):
            attempts.append("finish")
            if optional_failure == "finish":
                raise ValueError("optional finish failed")
        original_finish(observer, reason)

    original_metric = ctx.add_metric

    def metric(name, value):
        if reads == 91 and name == "eff_joints_tested" and optional_failure == "metric":
            raise ValueError("optional metric sink failed")
        original_metric(name, value)

    def cleanup(*args):
        if reads == 91:
            attempts.append("cleanup")
            if optional_failure == "cleanup":
                raise ValueError("optional cleanup failed")

    monkeypatch.setattr(robot, "get_joint_positions", positions)
    monkeypatch.setattr(_Motion, "_warn", warn)
    monkeypatch.setattr(_Motion, "finish", finish)
    monkeypatch.setattr(effort_limit, "clear_force_visualization", cleanup)
    ctx.add_metric = metric
    with pytest.raises(RuntimeError, match="required position readback") as caught:
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {
                "physics_fps": 4,
                "capture_fps": 4,
                "settle_seconds": 0,
                "test_duration_seconds": 0.1,
                "stop_on_first_break": False,
            },
        )
    if read_failure == "exception":
        assert caught.value.__cause__ is primary
    assert len(ctx.metrics["eff_joint_results"]) == 1
    assert ctx.metrics["eff_joints_passed"] == 1
    assert ctx.metrics["eff_joints_failed"] == 0
    partial = ctx.metrics["eff_incomplete_joint_evidence"]
    assert partial["name"] == "unmapped"
    assert partial["status"] == "incomplete"
    assert partial["broke_directions"] == ["+x"]
    assert "exceeded upper limit" in partial["broke_reasons"]["+x"]
    assert partial["interrupted_direction"] == "-x"
    assert len(observers[1].samples) == 30
    assert attempts == ["warn", "finish", "cleanup"]


@pytest.mark.asyncio
async def test_effort_missing_cooked_link_paths_stops_before_force_submission(monkeypatch):
    ctx, robot = _Context(video=False), _Robot()
    observers = _effort_probe(monkeypatch, robot)
    stage = Usd.Stage.CreateInMemory()
    UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Robot/child").GetPrim())
    handle = RobotHandle.__new__(RobotHandle)
    handle._stage = stage
    handle._articulation = SimpleNamespace(
        _articulation_view=SimpleNamespace(
            body_names=["child"],
            _physics_view=SimpleNamespace(
                get_link_transforms=lambda: [[[1, 2, 3, 0, 0, 0, 1]]],
                get_coms=lambda: [[[0, 0, 0, 0, 0, 0, 1]]],
            ),
        )
    )
    monkeypatch.setattr(robot, "get_child_body_world_com", handle.get_child_body_world_com)

    with pytest.raises(RuntimeError, match="COM.*link path"):
        await effort_limit.run_effort_limit(
            ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
        )

    assert ctx.steps == 0 and robot.forces == []
    assert ctx.metrics["eff_joint_results"] == []
    assert ctx.metrics["eff_joints_tested"] == 0
    assert observers[0].reasons == ["required_com_unavailable"]


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
    assert "exceeded upper limit" in record["broke_reasons"]["+x"]
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

    def get_child_body_path(self, index):
        assert index in (0, 1)
        return "/Robot/child"

    def get_joint_position_limits(self):
        return np.array([-1.0, -1.0]), np.array([1.0, 1.0])

    def get_joint_effort_limits(self):
        return np.array([10.0, 10.0])

    def get_joint_positions(self):
        return np.array([self.position, self.position])

    def get_child_body_world_com(self, body_path):
        assert body_path == "/Robot/child"
        return (1.0, 2.0, 3.0)


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


@pytest.mark.asyncio
async def test_effort_uses_refreshed_com_on_every_force_tick(monkeypatch):
    ctx, robot = _Context(video=False), _Robot()
    observers = _effort_probe(monkeypatch, robot)
    reads = []

    def live_com(body_path):
        reads.append(body_path)
        return (float(len(reads)), 2.0, 3.0)

    monkeypatch.setattr(robot, "get_child_body_world_com", live_com)
    await effort_limit.run_effort_limit(
        ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
    )
    assert len(reads) == 60
    assert [point[0] for _force, point in robot.forces] == list(range(1, 61))
    assert observers[0].samples[0][0]["force_point_x"] == 1.0
    assert observers[0].samples[-1][0]["force_point_x"] == 60.0


@pytest.mark.asyncio
async def test_effort_com_failure_keeps_completed_joint_metrics_and_partial_history(monkeypatch):
    ctx, robot = _Context(video=False), _TwoEffortJoints()
    observers = _effort_probe(monkeypatch, robot)
    reads = 0

    def live_com(body_path):
        nonlocal reads
        reads += 1
        if reads == 63:
            raise RuntimeError("lost cooked COM row")
        return (1.0, 2.0, 3.0)

    monkeypatch.setattr(robot, "get_child_body_world_com", live_com)
    with pytest.raises(RuntimeError, match="lost cooked COM row"):
        await effort_limit.run_effort_limit(
            ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
        )
    assert ctx.metrics["eff_joints_tested"] == 1
    assert ctx.metrics["eff_joints_passed"] == 1
    assert ctx.metrics["eff_joints_failed"] == 0
    assert len(ctx.metrics["eff_joint_results"]) == 1
    assert len(observers[1].samples) == 2
    assert observers[1].reasons == ["required_com_unavailable"]
    assert ctx.metrics["eff_force_point_observation"]["world_com"] is None
    assert ctx.metrics["eff_force_point_observation"]["basis"] == "live child-body center of mass"


@pytest.mark.asyncio
async def test_effort_cleanup_and_diagnostic_failure_keep_original_com_cause(monkeypatch):
    ctx, robot = _Context(video=False), _Robot()
    observers = _effort_probe(monkeypatch, robot)
    original = RuntimeError("original cooked COM failure")
    monkeypatch.setattr(robot, "get_child_body_world_com", lambda body: (_ for _ in ()).throw(original))
    monkeypatch.setattr(
        effort_limit, "clear_force_visualization", lambda *args: (_ for _ in ()).throw(ValueError("cleanup failed"))
    )
    original_add = ctx.add_metric

    def add_metric(name, value):
        if name == "eff_force_point_observation":
            raise ValueError("optional diagnostic failed")
        original_add(name, value)

    ctx.add_metric = add_metric
    with pytest.raises(RuntimeError, match="original cooked COM failure") as error:
        await effort_limit.run_effort_limit(
            ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
        )
    assert error.value.__cause__ is original
    assert ctx.metrics["eff_joints_tested"] == 0
    assert observers[0].reasons == ["required_com_unavailable"]


@pytest.mark.asyncio
async def test_effort_optional_motion_sample_failure_does_not_stop_required_probe(monkeypatch):
    ctx, robot = _Context(video=False), _Robot()
    observers = _effort_probe(monkeypatch, robot)
    observations = []
    original_com = robot.get_child_body_world_com

    def read_com(body_path):
        observations.append(body_path)
        return original_com(body_path)

    monkeypatch.setattr(robot, "get_child_body_world_com", read_com)
    monkeypatch.setattr(_Motion, "sample", lambda *args: (_ for _ in ()).throw(ValueError("optional recorder failed")))
    await effort_limit.run_effort_limit(
        ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
    )
    assert ctx.steps == 60
    assert len(observations) == 60
    assert len(robot.forces) == 60
    assert ctx.metrics["eff_joints_passed"] == 1
    assert observers[0].warnings > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["com", "submission"])
async def test_effort_keeps_evaluated_break_reason_if_later_direction_is_incomplete(monkeypatch, failure_kind):
    ctx, robot = _Context(video=False), _Robot()
    robot.position = 2.0
    observers = _effort_probe(monkeypatch, robot)
    failures = []
    ctx.fail = failures.append
    calls = 0
    original_com = robot.get_child_body_world_com
    original_submit = effort_limit.apply_external_force

    def live_com(body_path):
        nonlocal calls
        calls += 1
        if failure_kind == "com" and calls == 31:
            raise RuntimeError("later COM row missing")
        return original_com(body_path)

    def submit(stage, body, direction, magnitude, point):
        if failure_kind == "submission" and calls == 31:
            return False
        return original_submit(stage, body, direction, magnitude, point)

    monkeypatch.setattr(robot, "get_child_body_world_com", live_com)
    monkeypatch.setattr(effort_limit, "apply_external_force", submit)
    with pytest.raises(RuntimeError, match="COM|could not be submitted"):
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {},
            {
                "physics_fps": 4,
                "capture_fps": 4,
                "settle_seconds": 0,
                "test_duration_seconds": 0.1,
                "stop_on_first_break": False,
                "bisection_enabled": False,
            },
        )
    assert not failures
    assert ctx.metrics["eff_joints_tested"] == 0
    assert ctx.metrics["eff_joints_failed"] == 0
    assert ctx.metrics["eff_joint_results"] == []
    partial = ctx.metrics["eff_incomplete_joint_evidence"]
    assert partial["name"] == "hinge"
    assert partial["status"] == "incomplete"
    assert partial["broke_directions"] == ["+x"]
    assert "exceeded upper limit" in partial["broke_reasons"]["+x"]
    assert len(observers[0].samples) == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["bbox", "step", "reset", "cancel"])
@pytest.mark.parametrize("optional_failure", [False, True])
async def test_whole_effort_probe_preserves_completed_and_partial_evidence(monkeypatch, failure_kind, optional_failure):
    import asyncio

    ctx, robot = _Context(video=False), _TwoEffortJoints()
    directions = effort_limit.generate_12_force_directions
    observers = _effort_probe(monkeypatch, robot)
    monkeypatch.setattr(effort_limit, "generate_12_force_directions", directions)
    monkeypatch.setattr(robot, "get_joint_positions", lambda: np.array([0.0, 2.0]))
    primary = (
        asyncio.CancelledError("required cancellation")
        if failure_kind == "cancel"
        else RuntimeError("required operation canary")
    )
    bbox_calls, reset_calls = 0, 0
    attempts = []
    interrupted = False

    def bbox(prim):
        nonlocal bbox_calls, interrupted
        bbox_calls += 1
        if failure_kind == "bbox" and bbox_calls == 15:
            interrupted = True
            raise primary
        return SimpleNamespace(volume=1.0)

    async def step():
        nonlocal interrupted
        ctx.steps += 1
        if failure_kind in ("step", "cancel") and ctx.steps == 66:
            interrupted = True
            raise primary

    async def reset(*args, **kwargs):
        nonlocal reset_calls, interrupted
        reset_calls += 1
        if failure_kind == "reset" and reset_calls == 13:
            interrupted = True
            raise primary

    def optional(name):
        if interrupted:
            attempts.append(name)
            if optional_failure:
                raise ValueError("optional canary")

    monkeypatch.setattr(effort_limit, "compute_world_aligned_bbox", bbox)
    monkeypatch.setattr(effort_limit, "reset_to_default", reset)
    monkeypatch.setattr(effort_limit, "clear_external_force", lambda *args: optional("force"))
    monkeypatch.setattr(effort_limit, "clear_force_visualization", lambda *args: optional("visual"))
    monkeypatch.setattr(_Motion, "_warn", lambda self: optional("warn"))
    monkeypatch.setattr(_Motion, "finish", lambda self, reason: optional("finish"))
    ctx.step_one = step
    with pytest.raises(BaseException) as caught:
        await effort_limit.run_effort_limit(
            ctx,
            robot,
            {"default_state": object()},
            {
                "physics_fps": 4,
                "capture_fps": 4,
                "settle_seconds": 0,
                "test_duration_seconds": 0.1,
                "stop_on_first_break": False,
                "bisection_enabled": False,
            },
        )
    assert caught.value is primary
    assert ctx.metrics["eff_joints_tested"] == 1
    assert ctx.metrics["eff_joints_passed"] == 1
    assert ctx.metrics["eff_joints_failed"] == 0
    assert len(ctx.metrics["eff_joint_results"]) == 1
    partial = ctx.metrics["eff_incomplete_joint_evidence"]
    assert len(partial["broke_directions"]) == 1
    assert "exceeded upper limit" in next(iter(partial["broke_reasons"].values()))
    assert partial["status"] == "incomplete"
    assert all(name in attempts for name in ("warn", "finish", "force", "visual"))
    assert len(observers) == 2


@pytest.mark.asyncio
async def test_effort_recoverable_capture_none_does_not_interrupt_completed_probe(monkeypatch):
    ctx, robot = _Context(video=False), _Robot()
    _effort_probe(monkeypatch, robot)

    async def capture(**kwargs):
        return None

    ctx.capture_frame = capture
    await effort_limit.run_effort_limit(
        ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
    )
    assert ctx.steps == 60
    assert ctx.metrics["eff_joints_passed"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera", "capture", "encode"])
@pytest.mark.parametrize("kind", ["ordinary", "cancel", "unsafe"])
async def test_effort_diagnostic_control_flow_and_required_media_errors(monkeypatch, operation, kind):
    import asyncio

    from simready.evaluate.core.output_layout import UnsafeEvidencePathError

    ctx, robot = _Context(video=True), _TwoEffortJoints()
    _effort_probe(monkeypatch, robot)
    primary = {
        "ordinary": OSError("delivery failed"),
        "cancel": asyncio.CancelledError("stop"),
        "unsafe": UnsafeEvidencePathError("unsafe"),
    }[kind]

    def fail(*args, **kwargs):
        if ctx.steps > 60:
            raise primary

    if operation == "camera":
        ctx.scene.update_camera_follow = fail
    elif operation == "encode":
        ctx.encode_video = fail
    else:

        async def capture(**kwargs):
            fail()
            return "frame.png"

        ctx.capture_frame = capture
    call = effort_limit.run_effort_limit(
        ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
    )
    if operation == "camera" and kind == "ordinary":
        await call
        assert ctx.metrics["eff_joints_tested"] == 2
    else:
        with pytest.raises(type(primary)) as caught:
            await call
        assert caught.value is primary
        assert ctx.metrics["eff_joints_tested"] == (2 if operation == "encode" else 1)

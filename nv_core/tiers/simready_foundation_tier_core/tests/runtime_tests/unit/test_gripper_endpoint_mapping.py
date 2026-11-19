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
"""Real USD geometry + stepped fake drives; no Kit/GPU required."""

import ast
import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_close_lift as phase
from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
    FingertipSet,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_close_lift import (
    _authored_hand_orientation,
    _detect_open_closed_positions,
    _infer_hand_grasp_specs,
    _pad_world_tips,
    _prepare_gripper_ground,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
    GripperMappingError,
    GripperProbe,
    _owned_geometry_points,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


def _stage(paths, scale=1.0):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, scale)
    for path in paths:
        body = UsdGeom.Xform.Define(stage, path).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        geometry = UsdGeom.Cube.Define(stage, path + "/shape")
        geometry.CreateSizeAttr(0.002 / scale)
    return stage


class _Robot:
    def __init__(self, paths, geometry, leaders=1):
        self.paths, self.geometry = paths, geometry
        self.dof_count = leaders + 1
        self.dof_names = [f"q{index}" for index in range(self.dof_count)]
        self.actual = np.full(self.dof_count, 0.4)
        self.targets = np.full(self.dof_count, 0.45)
        self.targets[-1] = 77.0  # Carrier command must never be replaced.
        self.actions = []
        self.reads = 0
        self.partial = False
        self.nonfinite = False

    def get_joint_positions(self):
        return self.actual.copy()

    def get_joint_position_targets(self):
        return self.targets.copy()

    def get_joint_position_limits(self):
        return np.zeros(self.dof_count), np.ones(self.dof_count)

    def set_joint_position_target(self, index, target):
        self.actions.append((index, target))
        self.targets[index] = target

    def set_joint_positions(self, positions):
        raise AssertionError("Four-bar state must never be teleported")

    def set_joint_velocities(self, velocities):
        raise AssertionError("Probe must not override velocities")

    def get_link_world_transforms(self, paths):
        self.reads += 1
        positions = self.geometry(self.actual)
        result = {path: (np.asarray(positions[path]), np.array([0.0, 0.0, 0.0, 1.0])) for path in paths}
        if self.partial:
            result.pop(next(iter(result)))
        if self.nonfinite:
            result[next(iter(result))][0][0] = np.nan
        return result


class _Context:
    def __init__(self, robot, fail_step=None, cancel_step=None):
        self.robot = robot
        self.steps = 0
        self.metrics = {}
        self.fail_step, self.cancel_step = fail_step, cancel_step

    async def step_one(self):
        self.steps += 1
        self.robot.actual[:-1] = self.robot.targets[:-1]
        if self.steps == self.fail_step:
            raise RuntimeError("injected step failure")
        if self.steps == self.cancel_step:
            raise asyncio.CancelledError()

    def log(self, message):
        pass

    def add_metric(self, name, value):
        self.metrics[name] = value


_CONFIG = {"open_close_detect_steps": 3, "detect_limit_inset_frac": 0.05}
_PADS = ["/Asset/a", "/Asset/b"]


def _fingertips(paths=_PADS, leaders=1):
    return FingertipSet(
        "mimic_parallel_jaw",
        list(paths[:2]),
        0,
        None,
        None,
        candidate_tip_paths=list(paths),
        tips_from_grip_line=True,  # This retired hint must not short-circuit probes.
        mimic_master_dofs=list(range(leaders)),
        candidate_branches={path: index for index, path in enumerate(paths)},
    )


@pytest.mark.parametrize("upper_open", [False, True])
def test_live_mapping_supports_both_limit_conventions_and_sparse_restoration(upper_open):
    def geometry(q):
        opening = 0.02 + 0.08 * (q[0] if upper_open else 1 - q[0])
        return {_PADS[0]: [-opening / 2, 0, -0.1], _PADS[1]: [opening / 2, 0, -0.1]}

    robot = _Robot(_PADS, geometry)
    before = robot.targets.copy()
    ctx, fingertips = _Context(robot), _fingertips()
    result = asyncio.run(_detect_open_closed_positions(ctx, robot, fingertips, _stage(_PADS), _CONFIG, 0.1))
    assert result == ((1.0, 0.0) if upper_open else (0.0, 1.0))
    assert robot.reads == 2  # One geometry snapshot per endpoint, not four sweeps.
    assert ctx.steps == 9  # Two probes + one bounded return, no duplicate restore.
    assert robot.actual[0] == pytest.approx(0.4)
    assert np.array_equal(robot.targets, before)
    assert {index for index, _ in robot.actions} == {0}
    assert ctx.metrics["detect_used_authored_grip_line"] is False


def test_dual_leaders_with_opposite_conventions_are_mapped_independently():
    def geometry(q):
        return {_PADS[0]: [-0.01 - 0.04 * q[0], 0, -0.1], _PADS[1]: [0.01 + 0.04 * (1 - q[1]), 0, -0.1]}

    robot = _Robot(_PADS, geometry, leaders=2)
    ctx, fingertips = _Context(robot), _fingertips(leaders=2)
    asyncio.run(_detect_open_closed_positions(ctx, robot, fingertips, _stage(_PADS), _CONFIG, 0.1))
    assert fingertips.master_open_closed_positions == {0: (1.0, 0.0), 1: (0.0, 1.0)}
    assert robot.reads == 4
    assert np.allclose(robot.actual[:2], 0.4)
    assert np.allclose(robot.targets[:2], 0.45)
    assert robot.targets[-1] == 77


@pytest.mark.parametrize("stale", [False, True])
def test_failed_mapping_retains_numeric_probe_evidence_without_extra_commands_or_reads(stale):
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.025, 0, -0.1], _PADS[1]: [0.025, 0, -0.1]})
    ctx = _Context(robot)
    if stale:

        async def step_one():
            ctx.steps += 1  # Stale tensor state, not a fabricated successful drive.

        ctx.step_one = step_one
    with pytest.raises(GripperMappingError, match="achieved endpoint motion" if stale else "unchanged/ambiguous"):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    evidence = ctx.metrics["detect_probe_evidence_0"]
    assert evidence["prior_target"] == 0.45 and evidence["original_position"] == 0.4
    assert evidence["lower_limit"] == 0.0 and evidence["upper_limit"] == 1.0
    endpoints = evidence["endpoints"]
    assert endpoints["lower"]["commanded"] == pytest.approx(0.05)
    assert endpoints["upper"]["commanded"] == pytest.approx(0.95)
    assert endpoints["lower"]["achieved"] == pytest.approx(0.4 if stale else 0.05)
    assert endpoints["upper"]["achieved"] == pytest.approx(0.4 if stale else 0.95)
    row = endpoints["lower"]["geometry"]["candidates"][0]
    assert row["body_path"] == _PADS[0]
    assert row["tip_position_world"] == pytest.approx([-0.025, 0, -0.101])
    assert row["geometry_min_world"] == pytest.approx([-0.026, -0.001, -0.101])
    assert row["geometry_max_world"] == pytest.approx([-0.024, 0.001, -0.099])
    assert "not contacts" in endpoints["lower"]["geometry"]["coordinate_basis"]
    assert evidence["ramps"][0]["samples"][-1] == pytest.approx(
        {"step": 3, "commanded": 0.05, "achieved": 0.4 if stale else 0.05}
    )
    if stale:
        assert evidence["achieved_endpoint_delta"] == 0.0
        assert "pair_observations" not in evidence
    else:
        pair = evidence["pair_observations"][0]
        assert pair["body_paths"] == _PADS
        assert pair["lower_m"] == pytest.approx(0.05)
        assert pair["upper_m"] == pytest.approx(0.05)
        assert pair["change_m"] == 0.0
    assert ctx.steps == 9 and robot.reads == 2
    assert len(robot.actions) == 11 and {index for index, _ in robot.actions} == {0}
    assert robot.targets[0] == 0.45 and robot.targets[-1] == 77.0
    assert robot.actual[0] == pytest.approx(0.4)


def test_probe_recording_failure_cannot_replace_mapping_failure_or_restoration():
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.025, 0, -0.1], _PADS[1]: [0.025, 0, -0.1]})
    ctx = _Context(robot)

    def unavailable_metric(*args):
        raise RuntimeError("injected optional metric failure")

    ctx.add_metric = unavailable_metric
    with pytest.raises(GripperMappingError, match="unchanged/ambiguous"):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    assert ctx.steps == 9 and robot.reads == 2 and len(robot.actions) == 11
    assert robot.targets[0] == 0.45 and robot.actual[0] == pytest.approx(0.4)


@pytest.mark.parametrize("cancel", [False, True])
def test_interrupted_probe_retains_only_observed_values_and_original_exception(cancel):
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.01 - q[0] * 0.04, 0, -0.1], _PADS[1]: [0.05, 0, -0.1]})
    ctx = _Context(robot, cancel_step=2 if cancel else None, fail_step=None if cancel else 2)
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    evidence = ctx.metrics["detect_probe_evidence_0"]
    ramp = evidence["ramps"][0]
    assert ramp["steps_attempted"] == 2 and ramp["steps_observed"] == 1
    assert len(ramp["samples"]) == 1 and ramp["last_achieved_position"] == pytest.approx(ramp["samples"][0]["achieved"])
    assert evidence["endpoints"] == {}  # No endpoint geometry was measured.
    assert ctx.steps == 5 and robot.reads == 0
    assert robot.targets[0] == 0.45 and robot.actual[0] == pytest.approx(0.4)


def test_long_probe_numeric_trace_is_bounded_with_explicit_omissions():
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.01 - q[0] * 0.04, 0, -0.1], _PADS[1]: [0.05, 0, -0.1]})
    ctx = _Context(robot)
    config = dict(_CONFIG, open_close_detect_steps=100)
    asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), config, 0.1))
    evidence = ctx.metrics["detect_probe_evidence_0"]
    assert len(evidence["ramps"]) == 3 and ctx.steps == 300 and robot.reads == 2
    for ramp in evidence["ramps"]:
        assert len(ramp["samples"]) <= 34
        assert len(ramp["samples"]) + ramp["samples_omitted"] == 100
        assert ramp["samples"][0]["step"] == 1 and ramp["samples"][-1]["step"] == 100
        assert ramp["steps_requested"] == ramp["steps_attempted"] == ramp["steps_observed"] == 100


@pytest.mark.parametrize("recording_failure", [None, "construct", "sample", "finish"])
def test_optional_probe_motion_uses_existing_readbacks_without_affecting_controls(monkeypatch, recording_failure):
    from simready.foundation.tier_core.runtime_tests import motion_observer

    observers = []

    class Observer:
        def __init__(self, ctx, name, channels, metadata, sample_stride):
            if recording_failure == "construct":
                raise RuntimeError("injected recording construction failure")
            self.name, self.channels, self.metadata = name, channels, metadata
            self.history = SimpleNamespace(mark_partial=lambda reason: None)
            self.samples, self.stop_reason = [], None
            observers.append(self)

        def sample(self, values, phase):
            if recording_failure == "sample":
                raise RuntimeError("injected optional recording sample failure")
            self.samples.append((dict(values), phase))

        def finish(self, reason):
            if recording_failure == "finish":
                raise RuntimeError("injected optional recording finish failure")
            self.stop_reason = reason

    monkeypatch.setattr(motion_observer, "MotionObserver", Observer)
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.01 - q[0] * 0.04, 0, -0.1], _PADS[1]: [0.05, 0, -0.1]})
    ctx = _Context(robot)
    ctx.begin_motion_history = lambda *args, **kwargs: None
    assert asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1)) == (
        1.0,
        0.0,
    )
    assert ctx.steps == 9 and robot.reads == 2 and len(robot.actions) == 11
    assert robot.targets[0] == 0.45 and robot.targets[-1] == 77.0 and robot.actual[0] == pytest.approx(0.4)
    if recording_failure is None:
        assert len(observers) == 1
        observer = observers[0]
        assert observer.name == "gripper_probe_joint_000" and observer.stop_reason == "mapping_completed"
        assert "not a solver" in observer.metadata["clock_basis"]
        assert len(observer.samples) == 9
        assert {phase for _, phase in observer.samples} == {"lower_endpoint", "upper_endpoint", "restore"}
        assert [row["target"] for row, _ in observer.samples] == pytest.approx(
            [target for _, target in robot.actions[1:-1]]
        )
        assert all(row["position"] == pytest.approx(row["target"]) for row, _ in observer.samples)


def test_failed_probe_optional_motion_is_marked_partial_before_finish(monkeypatch):
    from simready.foundation.tier_core.runtime_tests import motion_observer

    events = []

    class Observer:
        def __init__(self, *args, **kwargs):
            self.history = SimpleNamespace(mark_partial=lambda reason: events.append(("partial", reason)))

        def sample(self, *args, **kwargs):
            pass

        def finish(self, reason):
            events.append(("finish", reason))

    monkeypatch.setattr(motion_observer, "MotionObserver", Observer)
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.025, 0, -0.1], _PADS[1]: [0.025, 0, -0.1]})
    ctx = _Context(robot)
    ctx.begin_motion_history = lambda *args, **kwargs: None
    with pytest.raises(GripperMappingError, match="unchanged/ambiguous"):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    assert events == [("partial", "endpoint mapping did not complete"), ("finish", "mapping_interrupted")]
    assert ctx.steps == 9 and robot.reads == 2 and robot.targets[0] == 0.45


def test_multi_shape_trials_keep_distinct_probe_metrics_and_histories_without_default_identity_churn(monkeypatch):
    from simready.foundation.tier_core.runtime_tests import motion_observer

    histories = {}

    class Observer:
        def __init__(self, ctx, name, channels, metadata, **kwargs):
            assert name not in histories
            self.name = name
            self.samples = []
            histories[name] = (metadata, self.samples)

        def sample(self, values, phase):
            self.samples.append((dict(values), phase))

        def finish(self, reason):
            assert reason == "mapping_completed"

    monkeypatch.setattr(motion_observer, "MotionObserver", Observer)
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.01 - q[0] * 0.04, 0, -0.1], _PADS[1]: [0.05, 0, -0.1]})
    ctx = _Context(robot)
    ctx.begin_motion_history = lambda *args, **kwargs: None
    for index, shape in enumerate(("sphere", "cube")):
        config = dict(_CONFIG, _probe_trial_index=index, _probe_trial_shape=shape)
        assert asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), config, 0.1)) == (
            1.0,
            0.0,
        )
    assert set(histories) == {"gripper_probe_joint_000", "gripper_probe_joint_000_trial_002"}
    assert ctx.metrics["detect_probe_evidence_0"]["trial_shape"] == "sphere"
    assert ctx.metrics["detect_probe_evidence_0_trial_002"]["trial_shape"] == "cube"
    for index, name in enumerate(histories):
        metadata, samples = histories[name]
        assert metadata["trial_index"] == index
        assert metadata["trial_shape"] == ("sphere" if index == 0 else "cube")
        assert metadata["trial_number"] == index + 1
        assert metadata["shape"] == metadata["trial_shape"]
        assert len(samples) == 9
    assert ctx.steps == 18 and robot.reads == 4 and len(robot.actions) == 22
    assert robot.actual[0] == pytest.approx(0.4) and robot.targets[0] == 0.45 and robot.targets[-1] == 77.0


def test_proximal_knuckles_never_override_distal_pads():
    paths = _PADS + ["/Asset/c", "/Asset/d"]

    def geometry(q):
        opening = 0.02 + 0.08 * q[0]
        return {
            paths[0]: [-opening / 2, 0, -0.15],
            paths[1]: [opening / 2, 0, -0.15],
            paths[2]: [-0.07 + q[0] * 0.02, 0, 0.1],
            paths[3]: [0.07 - q[0] * 0.02, 0, 0.1],
        }

    robot = _Robot(paths, geometry)
    fingertips = _fingertips(paths)
    fingertips.tip_link_paths = paths[2:]  # Wrong static rest-pose hint.
    assert asyncio.run(
        _detect_open_closed_positions(_Context(robot), robot, fingertips, _stage(paths), _CONFIG, 0.1)
    ) == (
        1.0,
        0.0,
    )
    assert set(fingertips.tip_link_paths) == set(_PADS)


def test_centric_three_fingers_use_collective_motion():
    paths = _PADS + ["/Asset/c"]

    def geometry(q):
        radius = 0.01 + 0.04 * q[0]
        return {
            path: [radius * np.cos(angle), radius * np.sin(angle), -0.1]
            for path, angle in zip(paths, (0, 2 * np.pi / 3, 4 * np.pi / 3), strict=True)
        }

    robot = _Robot(paths, geometry)
    assert asyncio.run(
        _detect_open_closed_positions(_Context(robot), robot, _fingertips(paths), _stage(paths), _CONFIG, 0.1)
    ) == (
        1.0,
        0.0,
    )


@pytest.mark.parametrize("failure", ["partial", "nonfinite", "unchanged", "missing_target"])
def test_mapping_refuses_incomplete_or_ambiguous_evidence(failure):
    def geometry(q):
        opening = 0.05 if failure == "unchanged" else 0.02 + 0.08 * q[0]
        return {_PADS[0]: [-opening / 2, 0, -0.1], _PADS[1]: [opening / 2, 0, -0.1]}

    robot = _Robot(_PADS, geometry)
    robot.partial = failure == "partial"
    robot.nonfinite = failure == "nonfinite"
    if failure == "missing_target":
        robot.targets[0] = np.nan
    ctx = _Context(robot)
    with pytest.raises(GripperMappingError):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    assert all(index == 0 for index, _ in robot.actions)
    if failure != "missing_target":
        assert robot.targets[0] == 0.45
        assert robot.actual[0] == pytest.approx(0.4)
    else:
        assert not robot.actions


@pytest.mark.parametrize("cancel", [False, True])
def test_exception_or_cancellation_restores_sparse_commands(cancel):
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.01 - q[0] * 0.04, 0, -0.1], _PADS[1]: [0.05, 0, -0.1]})
    ctx = _Context(robot, cancel_step=2 if cancel else None, fail_step=None if cancel else 2)
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    assert robot.targets[0] == 0.45
    assert robot.targets[-1] == 77
    assert robot.actual[0] == pytest.approx(0.4)


def test_independent_upper_open_finger_is_measured_without_teleport():
    paths = _PADS

    def geometry(q):
        return {paths[0]: [0.01 + 0.08 * q[0], 0, 0], paths[1]: [0.01 + 0.08 * q[1], 0, 0]}

    robot = _Robot(paths, geometry, leaders=2)
    fingertips = FingertipSet("independent_fingers", paths, None, None, [[0], [1]])
    specs, diagnostics = asyncio.run(
        _infer_hand_grasp_specs(_Context(robot), robot, fingertips, _stage(paths), _CONFIG, np.zeros(3))
    )
    assert [(spec["open"], spec["closed"]) for spec in specs] == [(1.0, 0.0), (1.0, 0.0)]
    assert all(row[1] == "closure" for row in diagnostics)
    assert np.allclose(robot.actual[:2], 0.4)
    assert np.allclose(robot.targets[:2], 0.45)


def test_owned_geometry_excludes_nested_bodies_and_preserves_nonuniform_scale():
    stage = _stage(["/Asset/a", "/Asset/a/nested"])
    root = UsdGeom.Xformable(stage.GetPrimAtPath("/Asset/a"))
    root.AddScaleOp().Set((2.0, 3.0, 4.0))
    nested = UsdGeom.Xformable(stage.GetPrimAtPath("/Asset/a/nested"))
    nested.AddTranslateOp().Set((100, 0, 0))
    points = _owned_geometry_points(stage, "/Asset/a")
    assert np.allclose(points.min(axis=0), (-0.002, -0.003, -0.004))
    assert np.allclose(points.max(axis=0), (0.002, 0.003, 0.004))


@pytest.mark.parametrize("scale", [0.001, 1, 100])
def test_aperture_metrics_use_physical_meters(scale):
    robot = _Robot(
        _PADS,
        lambda q: {
            _PADS[0]: [-(0.01 + q[0] * 0.04) / scale, 0, -0.1 / scale],
            _PADS[1]: [0.05 / scale, 0, -0.1 / scale],
        },
    )
    ctx = _Context(robot)
    asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS, scale), _CONFIG, 0.1))
    assert ctx.metrics["detect_aperture_lower_m_dof_0"] == pytest.approx(0.062)
    assert ctx.metrics["detect_aperture_upper_m_dof_0"] == pytest.approx(0.098)


@pytest.mark.parametrize("indices", [None, [1, 0], [0], [0, 0], [0.5, 1]])
def test_target_readback_uses_complete_public_applied_action_not_state(indices):
    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = None
    action = SimpleNamespace(joint_positions=[0.7, 0.2], joint_indices=indices)
    handle._articulation = SimpleNamespace(dof_names=["a", "b"], get_applied_action=lambda: action)
    result = handle.get_joint_position_targets()
    if indices is None:
        assert np.allclose(result, [0.7, 0.2])
    elif indices == [1, 0]:
        assert np.allclose(result, [0.2, 0.7])
    else:
        assert np.isnan(result).all()


def test_missing_target_api_does_not_substitute_actual_joint_positions():
    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = None
    handle._articulation = SimpleNamespace(dof_names=["a", "b"], get_joint_positions=lambda: [0.3, 0.4])
    assert np.isnan(handle.get_joint_position_targets()).all()


@pytest.mark.parametrize("global_only", [False, True])
def test_hand_mapping_removes_carrier_translation_and_rotation(global_only):
    base = "/Asset/base"
    stage = _stage(_PADS + [base])

    class MovingRobot(_Robot):
        def get_link_world_transforms(self, paths):
            angle = float(ctx.steps) * 0.12
            rotation = Gf.Rotation(Gf.Vec3d(0, 1, 0), angle * 180 / np.pi)
            quaternion = rotation.GetQuat()
            imaginary = quaternion.GetImaginary()
            xyzw = np.array([*imaginary, quaternion.GetReal()])
            offset = np.array([ctx.steps * 0.03, ctx.steps * 0.02, ctx.steps * 0.04])
            result = {}
            for path in paths:
                if path == base:
                    local = np.zeros(3)
                else:
                    index = _PADS.index(path)
                    radial = 0.05 if global_only else 0.01 + 0.08 * self.actual[index]
                    local = np.array([0, (-1 if index else 1) * radial, 0])
                position = np.asarray(rotation.TransformDir(Gf.Vec3d(*local)), dtype=np.float64) + offset
                result[path] = (position, xyzw)
            return result

    robot = MovingRobot(_PADS, None, leaders=2)
    ctx = _Context(robot)
    fingertips = FingertipSet("independent_fingers", _PADS, None, None, [[0], [1]])
    specs, diagnostics = asyncio.run(_infer_hand_grasp_specs(ctx, robot, fingertips, stage, _CONFIG, np.zeros(3), base))
    if global_only:
        assert not specs
        assert all(row[1] == "unresolved" for row in diagnostics)
    else:
        assert [(spec["open"], spec["closed"]) for spec in specs] == [(1.0, 0.0), (1.0, 0.0)]
    assert robot.targets[-1] == 77


def test_four_bar_pad_geometry_can_move_opposite_link_origins():
    stage = _stage(_PADS)
    for path in _PADS:
        UsdGeom.Xformable(stage.GetPrimAtPath(path + "/shape")).AddTranslateOp().Set((0, 0, -0.1))

    class FourBarRobot(_Robot):
        def get_link_world_transforms(self, paths):
            result = {}
            for path in paths:
                side = -1 if path == _PADS[0] else 1
                angle = side * float(self.actual[0]) * np.pi / 4
                position = np.array([side * (0.05 + self.actual[0] * 0.02), 0, 0])
                xyzw = np.array([0, np.sin(angle / 2), 0, np.cos(angle / 2)])
                result[path] = (position, xyzw)
            return result

    robot = FourBarRobot(_PADS, None)
    result = asyncio.run(_detect_open_closed_positions(_Context(robot), robot, _fingertips(), stage, _CONFIG, 0.1))
    assert result == (0.0, 1.0)  # Origins spread toward upper; pads converge.


def test_invalidated_public_target_readback_is_not_replaced_by_state():
    def invalidated():
        raise RuntimeError("physics view invalidated")

    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = None
    handle._articulation = SimpleNamespace(dof_names=["a", "b"], get_applied_action=invalidated)
    assert np.isnan(handle.get_joint_position_targets()).all()


def test_cuda_applied_target_buffer_is_copied_to_host():
    class Tensor:
        def __init__(self, values):
            self.values = np.asarray(values)

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = None
    action = SimpleNamespace(joint_positions=Tensor([0.7, 0.2]), joint_indices=None)
    handle._articulation = SimpleNamespace(dof_names=["a", "b"], get_applied_action=lambda: action)
    assert np.allclose(handle.get_joint_position_targets(), [0.7, 0.2])


def test_reflected_rigid_body_frame_is_an_explicit_setup_limitation():
    stage = _stage(_PADS)
    UsdGeom.Xformable(stage.GetPrimAtPath(_PADS[0])).AddScaleOp().Set((-1, 1, 1))
    with pytest.raises(GripperMappingError, match="reflected.*unsupported"):
        _owned_geometry_points(stage, _PADS[0])


@pytest.mark.parametrize("cancel", [False, True])
def test_interrupted_pose_return_still_restores_all_original_commands(cancel):
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-0.01 - q[0] * 0.04, 0, -0.1], _PADS[1]: [0.05, 0, -0.1]})

    class FailedReturn(_Context):
        async def step_one(self):
            await super().step_one()
            if self.steps >= 7:
                if cancel:
                    raise asyncio.CancelledError()
                raise RuntimeError("return interrupted")

    ctx = FailedReturn(robot)
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(), _stage(_PADS), _CONFIG, 0.1))
    assert ctx.metrics["detect_restoration_incomplete"] is True
    assert robot.targets[0] == 0.45
    assert robot.targets[-1] == 77
    assert {index for index, _ in robot.actions} == {0}


def test_hand_orientation_rotates_authored_center_from_base_local_frame():
    stage = Usd.Stage.CreateInMemory()
    base = UsdGeom.Xform.Define(stage, "/Base")
    offset = np.array([3.0, 4.0, 5.0])
    base.AddTranslateOp().Set(tuple(offset))
    base.AddRotateZOp().Set(90)
    site = SimpleNamespace(
        forward_axis_world=np.array([0.0, 1.0, 0.0]),
        grip_line_world=[np.zeros(3), np.array([-1.0, 0.0, 0.0])],
        grasp_center_world_initial=lambda: offset + [0.0, 2.0, 0.0],
    )
    _, center, forward = _authored_hand_orientation(stage, "/Base", site)
    assert np.allclose(center, offset + [2.0, 0.0, 0.0])
    assert np.allclose(forward, [1.0, 0.0, 0.0])


def test_large_inherited_guide_annotation_does_not_change_pad_geometry():
    stage = _stage(_PADS)
    original = _owned_geometry_points(stage, _PADS[0])
    guides = UsdGeom.Xform.Define(stage, _PADS[0] + "/Annotations")
    guides.CreatePurposeAttr(UsdGeom.Tokens.guide)
    guide = UsdGeom.Cube.Define(stage, _PADS[0] + "/Annotations/Huge")
    guide.CreateSizeAttr(1000)
    assert np.allclose(_owned_geometry_points(stage, _PADS[0]), original)


def test_explicit_enabled_guide_collider_remains_physical_proxy():
    stage = _stage(_PADS)
    guide = UsdGeom.Cube.Define(stage, _PADS[0] + "/Collider")
    guide.CreateSizeAttr(0.02)
    guide.CreatePurposeAttr(UsdGeom.Tokens.guide)
    UsdPhysics.CollisionAPI.Apply(guide.GetPrim()).CreateCollisionEnabledAttr(True)
    assert len(_owned_geometry_points(stage, _PADS[0])) == 16


def test_descent_uses_owned_pad_geometry_and_preserves_nonuniform_scale():
    stage = _stage(_PADS)
    shape = UsdGeom.Cube(stage.GetPrimAtPath(_PADS[0] + "/shape"))
    shape.CreateSizeAttr(2)
    UsdGeom.Xformable(stage.GetPrimAtPath(_PADS[0])).AddScaleOp().Set((2, 3, 4))
    nested = UsdGeom.Xform.Define(stage, _PADS[0] + "/OtherBody")
    UsdPhysics.RigidBodyAPI.Apply(nested.GetPrim())
    nested.AddTranslateOp().Set((0, 0, -100))
    UsdGeom.Cube.Define(stage, _PADS[0] + "/OtherBody/Shape").CreateSizeAttr(2)
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [0, 0, 10], _PADS[1]: [0, 0, -50]})
    tips = _pad_world_tips(robot, stage, [_PADS[0]], (0, 0, -1))
    assert list(tips) == [_PADS[0]]
    assert np.allclose(tips[_PADS[0]], [0, 0, 6])


def test_cancel_only_during_clean_context_exit_propagates_and_restores_commands():
    robot = _Robot(_PADS, lambda q: {_PADS[0]: [-q[0], 0, 0], _PADS[1]: [q[0], 0, 0]})
    ctx = _Context(robot, cancel_step=7)

    async def run():
        async with GripperProbe(ctx, robot, _stage(_PADS), _PADS, [0], _CONFIG, (0, 0, -1)) as probe:
            await probe.endpoints(0)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
    assert robot.targets.tolist() == [0.45, 77.0]
    assert ctx.metrics["detect_restoration_incomplete"] is True


def test_original_target_setter_failure_does_not_skip_other_selected_leaders():
    class RobotWithFailedRestore(_Robot):
        def set_joint_position_target(self, index, target):
            if index == 0 and target == 0.45:
                raise RuntimeError("first leader restore failed")
            return super().set_joint_position_target(index, target)

    robot = RobotWithFailedRestore(
        _PADS,
        lambda q: {_PADS[0]: [-0.01 - q[0] * 0.03, 0, -0.1], _PADS[1]: [0.01 + (1 - q[1]) * 0.03, 0, -0.1]},
        leaders=2,
    )
    ctx = _Context(robot)
    with pytest.raises(GripperMappingError, match="restoration was incomplete"):
        asyncio.run(_detect_open_closed_positions(ctx, robot, _fingertips(leaders=2), _stage(_PADS), _CONFIG, 0.08))
    assert robot.targets[1] == 0.45
    assert robot.targets[-1] == 77
    assert ctx.metrics["detect_restoration_incomplete"] is True


@pytest.mark.parametrize("failure", ["mapping", "readback", "ambiguous"])
def test_actual_hand_branch_preserves_mapping_errors_without_asset_precheck(failure):
    source_path = Path(phase.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    branch = next(
        node.orelse
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and node.orelse
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_infer_hand_grasp_specs"
            for statement in node.orelse
            for child in ast.walk(statement)
        )
    )

    async def infer(*args):
        if failure == "mapping":
            raise GripperMappingError("live mapping unavailable")
        if failure == "readback":
            raise RuntimeError("runtime view unavailable")
        return [], []

    def unexpected(*args):
        raise AssertionError("mapping/setup errors must not become validated asset failures")

    body = ast.AsyncFunctionDef(
        name="run_branch",
        args=ast.arguments(
            posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=branch,
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[body], type_ignores=[]))
    namespace = {
        "ctx": SimpleNamespace(precheck_failure=unexpected, fail=unexpected, log=lambda message: None),
        "robot": SimpleNamespace(dof_names=["finger"]),
        "fingertip_set": SimpleNamespace(finger_chains=[[0]]),
        "stage": None,
        "config": {},
        "probe_config": {},
        "grasp_center_for_test": np.zeros(3),
        "gripper_base_path": "/base",
        "np": np,
        "_infer_hand_grasp_specs": infer,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    with pytest.raises(RuntimeError if failure == "readback" else GripperMappingError):
        asyncio.run(namespace["run_branch"]())


@pytest.mark.parametrize("with_room", [False, True])
def test_required_gripper_floor_failure_propagates(with_room):
    def failing_ground(*args, **kwargs):
        raise RuntimeError("required floor unavailable")

    scene = SimpleNamespace(enable_ground_plane=failing_ground)
    if with_room:
        scene._room_handle = SimpleNamespace(show_ground=failing_ground)
    with pytest.raises(RuntimeError, match="required floor unavailable"):
        _prepare_gripper_ground(SimpleNamespace(scene=scene))


def test_cosmetic_wall_color_can_warn_only_after_required_floor_succeeds():
    events = []

    def failing_color(*args):
        events.append("color")
        raise RuntimeError("cosmetic material unavailable")

    room = SimpleNamespace(show_ground=lambda **kwargs: events.append("ground"), set_color=failing_color)
    ctx = SimpleNamespace(scene=SimpleNamespace(_room_handle=room), warn=lambda message: events.append("warning"))
    _prepare_gripper_ground(ctx)
    assert events == ["ground", "color", "warning"]


@pytest.mark.parametrize("floor_state", ["missing", "noncolliding", "disabled", "enabled"])
def test_actual_room_floor_collision_is_a_required_setup_postcondition(floor_state):
    stage = Usd.Stage.CreateInMemory()
    if floor_state != "missing":
        floor = UsdGeom.Cube.Define(stage, "/Room/Floor")
        if floor_state != "noncolliding":
            UsdPhysics.CollisionAPI.Apply(floor.GetPrim()).CreateCollisionEnabledAttr(floor_state == "enabled")
    room = SimpleNamespace(_room_path="/Room", show_ground=lambda **kwargs: None, set_color=lambda *args: None)
    ctx = SimpleNamespace(scene=SimpleNamespace(stage=stage, _room_handle=room))
    if floor_state == "enabled":
        _prepare_gripper_ground(ctx)
    else:
        with pytest.raises(RuntimeError, match="Floor is missing or its collision"):
            _prepare_gripper_ground(ctx)


@pytest.mark.parametrize("entry", ["registration", "procedure"])
def test_core_gripper_rejects_newton_before_any_context_or_scene_access(monkeypatch, entry):
    from simready.foundation.tier_core.runtime_tests.engine_guard import PhysicsTestEngineMismatchError
    from simready.foundation.tier_core.runtime_tests.fet028_gripper import (
        gripper_close_lift as registration,
    )

    physics_utils = ModuleType("simready.evaluate_engine_kit.physics_utils")
    physics_utils.active_physics_engine = lambda: "newton"
    monkeypatch.setitem(sys.modules, physics_utils.__name__, physics_utils)

    class UntouchedContext:
        def __getattribute__(self, name):
            raise AssertionError("Misrouted gripper accessed context: " + name)

    call = (
        registration.run(UntouchedContext())
        if entry == "registration"
        else phase.run_gripper_close_lift(UntouchedContext(), None, {}, {})
    )
    with pytest.raises(PhysicsTestEngineMismatchError, match="setup mismatch"):
        asyncio.run(call)


def test_physx_gripper_procedure_does_not_import_or_branch_into_newton():
    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    procedure = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_gripper_close_lift"
    )
    for node in ast.walk(procedure):
        if isinstance(node, ast.ImportFrom):
            assert "newton" not in (node.module or "").split(".")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in {"newton", "prebuilt_fet028_test_object", "stationary_gripper_load_test"}


@pytest.mark.parametrize("positions", [None, [np.nan], [np.inf], [], [[0.0]]])
def test_required_grasp_state_cannot_invent_a_finite_verdict_readback(positions):
    robot = SimpleNamespace(dof_count=1, get_joint_positions=lambda: positions)
    with pytest.raises(RuntimeError, match="required post-open joint readback"):
        phase._required_grasp_positions(robot, [{"idx": 0}], "post-open")


@pytest.mark.parametrize("index", [-1, 2, 0.5, True, "0", np.nan, np.inf])
def test_required_grasp_state_rejects_invalid_selected_indices(index):
    robot = SimpleNamespace(dof_count=2, get_joint_positions=lambda: [0.2, 0.3])
    with pytest.raises(RuntimeError, match="required post-open joint readback"):
        phase._required_grasp_positions(robot, [{"idx": index}], "post-open")


def test_required_grasp_state_preserves_selected_order_without_rejecting_unselected_nulls():
    robot = SimpleNamespace(dof_count=3, get_joint_positions=lambda: [0.2, np.nan, 0.7])
    assert phase._required_grasp_positions(robot, [{"idx": 2}, {"idx": 0}], "post-open") == [0.7, 0.2]


def _close_trial(monkeypatch, final_positions):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import force_utils

    readings = iter([[0.0], [0.0], [0.1], final_positions])
    commands, steps = [], []
    robot = SimpleNamespace(dof_count=1, get_joint_positions=lambda: next(readings))
    monkeypatch.setattr(
        phase, "_command_grasp_targets", lambda *args, **kwargs: commands.append(kwargs["target_values"])
    )
    monkeypatch.setattr(force_utils, "read_contact_force_magnitude", lambda *args: None)

    async def step_one():
        steps.append("physics")

    def unexpected_fail(*args, **kwargs):
        raise AssertionError("required readback failure must not become asset FAIL")

    ctx = SimpleNamespace(step_one=step_one, log=lambda message: None, fail=unexpected_fail)
    call = phase._drive_to_close(
        ctx,
        robot,
        [{"idx": 0, "open": 0.0, "closed": 1.0}],
        SimpleNamespace(tip_link_paths=["/left", "/right"]),
        {"close_steps": 2, "close_ramp_steps": 2, "jik_contact_force_threshold_n": 1.0},
    )
    return call, commands, steps


@pytest.mark.parametrize("positions", [None, [np.nan], [np.inf]])
def test_actual_close_cannot_return_positive_proxy_after_required_readback_is_lost(monkeypatch, positions):
    call, commands, steps = _close_trial(monkeypatch, positions)
    with pytest.raises(RuntimeError, match="required close joint readback"):
        asyncio.run(call)
    assert commands == [[0.5], [1.0]] and len(steps) == 2


@pytest.mark.parametrize("positions,expected", [([0.3], True), ([1.0], False)])
def test_actual_finite_close_preserves_proxy_and_command_ramp(monkeypatch, positions, expected):
    call, commands, steps = _close_trial(monkeypatch, positions)
    assert asyncio.run(call) is expected
    assert commands == [[0.5], [1.0]] and len(steps) == 2


@pytest.mark.parametrize("positions", [None, [np.nan], [np.inf]])
def test_actual_open_unavailable_required_state_is_setup_error(monkeypatch, positions):
    commands, steps = [], []
    monkeypatch.setattr(phase, "_command_grasp_targets", lambda *args: commands.append(args[2]))

    async def step_one():
        steps.append("physics")

    ctx = SimpleNamespace(step_one=step_one)
    robot = SimpleNamespace(dof_count=1, get_joint_positions=lambda: positions)
    with pytest.raises(RuntimeError, match="required open joint readback"):
        asyncio.run(
            phase._drive_to_open(
                ctx,
                robot,
                [{"idx": 0, "open": 0.2, "closed": 1.0}],
                None,
                {"open_steps_max": 2},
            )
        )
    assert commands == ["open"] and len(steps) == 1


def test_actual_finite_open_keeps_existing_command_and_step_budget(monkeypatch):
    commands, steps = [], []
    monkeypatch.setattr(phase, "_command_grasp_targets", lambda *args: commands.append(args[2]))

    async def step_one():
        steps.append("physics")

    ctx = SimpleNamespace(step_one=step_one)
    robot = SimpleNamespace(dof_count=1, get_joint_positions=lambda: [0.2])
    result = asyncio.run(
        phase._drive_to_open(ctx, robot, [{"idx": 0, "open": 0.2, "closed": 1.0}], None, {"open_steps_max": 2})
    )
    assert result is None and commands == ["open", "open"] and len(steps) == 2


@pytest.mark.parametrize("positions", [None, [np.nan, 0.7], [0.2, np.inf], [0.2]])
def test_actual_post_open_check_cannot_pass_or_asset_fail_on_invalid_readback(positions):
    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_required_grasp_positions"
        and any(isinstance(arg, ast.Constant) and arg.value == "post-open" for arg in node.value.args)
    )
    namespace = {
        "robot": SimpleNamespace(dof_count=2, get_joint_positions=lambda: positions),
        "grasp_specs": [{"idx": 0}, {"idx": 1}],
        "_required_grasp_positions": phase._required_grasp_positions,
    }
    with pytest.raises(RuntimeError, match="required post-open joint readback"):
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(phase.__file__), "exec"), namespace)


@pytest.mark.parametrize("actual_lift", [np.nan, np.inf, -np.inf, 0.03, 0.10, 0.20])
def test_actual_required_carrier_lift_guard_is_setup_error_with_same_finite_boundary(actual_lift):
    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    guards = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and (
            isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "actual_translate"
            or isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.operand, ast.Call)
            and any(isinstance(arg, ast.Name) and arg.id == "actual_translate" for arg in node.test.operand.args)
        )
    ]
    assert len(guards) == 2
    namespace = {"actual_translate": actual_lift, "min_lift": 0.10, "commanded_translate": 0.20, "np": np}
    code = compile(ast.Module(body=guards, type_ignores=[]), str(phase.__file__), "exec")
    if not np.isfinite(actual_lift) or actual_lift < 0.10:
        with pytest.raises(RuntimeError, match="FET028 setup"):
            exec(code, namespace)
    else:
        exec(code, namespace)


@pytest.mark.parametrize("position", [None, [np.nan, 0.0, 0.0], [0.0, np.inf, 0.0], [0.0, 0.0]])
def test_diagnostic_pad_separation_never_invents_zero_for_unavailable_geometry(position):
    robot = SimpleNamespace(get_link_world_positions=lambda paths: {"/left": position, "/right": np.zeros(3)})
    assert phase._measure_finger_separation(robot, SimpleNamespace(tip_link_paths=["/left", "/right"])) is None


def test_diagnostic_pad_separation_preserves_finite_distance_and_incomplete_pad_set():
    robot = SimpleNamespace(
        get_link_world_positions=lambda paths: {"/left": np.array([0.0, 3.0, 0.0]), "/right": np.array([4.0, 0.0, 0.0])}
    )
    assert phase._measure_finger_separation(robot, SimpleNamespace(tip_link_paths=["/left", "/right"])) == 5.0
    assert phase._measure_finger_separation(robot, SimpleNamespace(tip_link_paths=["/left"])) is None


@pytest.mark.parametrize("translation", [None, (np.nan, 0.0, 0.0), (0.0, np.inf, 0.0), (1.0, 2.0, 3.0)])
def test_required_object_pose_cannot_produce_asset_verdict_from_missing_or_nonfinite_state(translation):
    stage = Usd.Stage.CreateInMemory()
    if translation is not None:
        obj = UsdGeom.Xform.Define(stage, "/Object")
        obj.AddTranslateOp().Set(Gf.Vec3d(*translation))
    if translation is None or not np.all(np.isfinite(translation)):
        with pytest.raises(RuntimeError, match="FET028 setup: required test-object"):
            phase._read_object_position(stage, "/Object")
    else:
        assert np.array_equal(phase._read_object_position(stage, "/Object"), translation)


@pytest.mark.parametrize("failure", ["object_missing", "object_nonfinite", "carrier_nonfinite", "finite"])
def test_actual_shake_callback_cannot_hide_required_state_loss_as_zero_slip(monkeypatch, failure):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_carrier

    stage = Usd.Stage.CreateInMemory()
    if failure != "object_missing":
        obj = UsdGeom.Xform.Define(stage, "/Object")
        obj.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, np.nan if failure == "object_nonfinite" else 0.28))
    carrier_position = [0.0, 0.0, np.nan if failure == "carrier_nonfinite" else 0.2]
    monkeypatch.setattr(gripper_carrier, "carrier_world_position", lambda carrier: carrier_position)
    captures = []

    async def capture(*args):
        captures.append(args)

    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    callback = next(
        node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "_shake_video"
    )
    factory = ast.parse("def factory():\n" "    shake_min_z = 0.2\n" "    shake_max_rel_slip = 0.0\n").body[0]
    factory.body.append(callback)
    factory.body.extend(ast.parse("return _shake_video, lambda: (shake_min_z, shake_max_rel_slip)").body)
    namespace = {
        "stage": stage,
        "carrier": object(),
        "offset_pre_shake": 0.1,
        "_object_z_runtime": lambda: float(phase._read_object_position(stage, "/Object")[2]),
        "_read_carrier_z": phase._read_carrier_z,
        "_video_capture": capture,
    }
    module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    exec(compile(module, str(phase.__file__), "exec"), namespace)
    call, measured = namespace["factory"]()
    if failure != "finite":
        with pytest.raises(RuntimeError, match="FET028 setup: required"):
            asyncio.run(call(0))
        assert measured() == (0.2, 0.0) and captures == []
    else:
        asyncio.run(call(0))
        assert measured() == pytest.approx((0.2, 0.02)) and captures == [(0, None)]


@pytest.mark.parametrize("topology", ["asymmetric", "mixed", "multi_master", "independent", "symmetric", "owned_dual"])
def test_production_discovery_never_promotes_active_mimic_followers_to_independent_commands(monkeypatch, topology):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        fingertip_discovery,
        mimic_joints,
    )

    count = 4 if topology in ("multi_master", "owned_dual") else 3 if topology == "mixed" else 2
    paths = [f"/Hand/pad{index}" for index in range(count)]
    stage = _stage(paths)
    UsdGeom.Xform.Define(stage, "/Hand/palm")
    UsdPhysics.RigidBodyAPI.Apply(stage.GetPrimAtPath("/Hand/palm"))
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Hand/palm"))
    for index, path in enumerate(paths):
        joint = UsdPhysics.PrismaticJoint.Define(stage, f"/Hand/q{index}")
        joint.GetBody0Rel().SetTargets(["/Hand/palm"])
        joint.GetBody1Rel().SetTargets([path])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear").CreateStiffnessAttr(100.0)
    robot = SimpleNamespace(prim_path="/Hand", dof_names=[f"q{index}" for index in range(count)])
    bindings = []
    if topology != "independent":
        bindings.append(
            SimpleNamespace(
                follower_joint_path="/Hand/q1",
                reference_joint_path="/Hand/q0",
                follower_dof_index=1,
                reference_dof_index=0,
                gear=2.0 if topology == "asymmetric" else -1.0,
                offset=0.0,
            )
        )
    if topology in ("multi_master", "owned_dual"):
        bindings.append(
            SimpleNamespace(
                follower_joint_path="/Hand/q3",
                reference_joint_path="/Hand/q2",
                follower_dof_index=3,
                reference_dof_index=2,
                gear=-1.0,
                offset=0.0,
            )
        )
    if topology == "owned_dual":
        for index in (0, 2):
            stage.DefinePrim(f"/Hand/actuator{index}", "NewtonActuator").CreateRelationship(
                "newton:targets"
            ).SetTargets([f"/Hand/q{index}"])
    monkeypatch.setattr(mimic_joints, "detect_mimic_joints", lambda *args, **kwargs: bindings)
    if topology in ("asymmetric", "mixed", "multi_master"):

        # These fixture followers sit on separate palm branches from their
        # references. Validated leader-chain fallback must still reject them.
        with pytest.raises(fingertip_discovery.GripperTopologyError, match="active mimic topology"):
            fingertip_discovery.discover_fingertips(stage, robot, object())
    else:
        result = fingertip_discovery.discover_fingertips(stage, robot, object())
        if topology == "independent":
            assert result.kind == "independent_fingers" and result.finger_chains == [[0], [1]]
        else:
            assert result.kind == "mimic_parallel_jaw"
            assert result.mimic_master_dofs == ([0, 2] if topology == "owned_dual" else [0])


def test_actual_gripper_discovery_setup_error_propagates_without_asset_failure_or_applicability_skip(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import fingertip_discovery

    error = fingertip_discovery.GripperTopologyError("unsupported active mimic topology")

    def unavailable(*args):
        raise error

    monkeypatch.setattr(fingertip_discovery, "discover_fingertips", unavailable)
    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "discover_fingertips"
    )
    namespace = {"discover_fingertips": unavailable, "stage": object(), "robot": object(), "site": object()}
    with pytest.raises(fingertip_discovery.GripperTopologyError) as caught:
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(phase.__file__), "exec"), namespace)
    assert caught.value is error

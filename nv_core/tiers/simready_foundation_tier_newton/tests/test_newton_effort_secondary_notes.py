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
import pytest
from test_newton_joint_phase_motion_evidence import (
    _Context,
    _effort_probe,
    _TwoEffortJoints,
    effort_limit,
)


class _MissingEffortNote(OSError):
    def __getattribute__(self, name):
        if name == "add_note":
            raise AttributeError("note unavailable")
        return super().__getattribute__(name)


class _BrokenEffortNoteAttribute(OSError):
    def __getattribute__(self, name):
        if name == "add_note":
            raise ValueError("note lookup failed")
        return super().__getattribute__(name)


class _BrokenEffortNoteSink(OSError):
    def add_note(self, text):
        raise ValueError("note sink failed")


class _BrokenEffortSecondaryRepr(OSError):
    def __repr__(self):
        raise ValueError("secondary repr failed")


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["metric", "cleanup"])
@pytest.mark.parametrize("fault", ["ordinary", "missing", "attribute", "sink", "repr"])
async def test_effort_secondary_note_fault_cannot_replace_required_tick(monkeypatch, boundary, fault):
    ctx, robot = _Context(video=False), _TwoEffortJoints()
    observers = _effort_probe(monkeypatch, robot)
    monkeypatch.setattr(robot, "get_child_body_path", lambda index: "/Robot/child")
    primary_type = {
        "missing": _MissingEffortNote,
        "attribute": _BrokenEffortNoteAttribute,
        "sink": _BrokenEffortNoteSink,
    }.get(fault, OSError)
    primary = primary_type("required second-joint tick failed")
    secondary = (_BrokenEffortSecondaryRepr if fault == "repr" else OSError)("secondary delivery failed")
    attempts = []
    original_metric = ctx.add_metric

    async def step_one():
        ctx.steps += 1
        if ctx.steps == 61:
            raise primary

    def metric(name, value):
        if ctx.steps == 61:
            attempts.append(name)
            if boundary == "metric" and name == "eff_joint_results":
                raise secondary
        original_metric(name, value)

    def cleanup(*args):
        if ctx.steps == 61:
            attempts.append("force_cleanup")
            if boundary == "cleanup":
                raise secondary

    def clear_arrow(*args):
        if ctx.steps == 61:
            attempts.append("arrow_cleanup")

    ctx.step_one, ctx.add_metric = step_one, metric
    monkeypatch.setattr(effort_limit, "clear_external_force", cleanup)
    monkeypatch.setattr(effort_limit, "clear_force_visualization", clear_arrow)
    with pytest.raises(BaseException) as caught:
        await effort_limit.run_effort_limit(
            ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
        )
    assert caught.value is primary
    assert ctx.steps == 61
    assert {
        "eff_joints_tested",
        "eff_joints_passed",
        "eff_joints_failed",
        "eff_joint_results",
        "eff_incomplete_joint_evidence",
        "force_cleanup",
        "arrow_cleanup",
    }.issubset(attempts)
    assert ctx.metrics["eff_incomplete_joint_evidence"]["status"] == "incomplete"
    assert observers[0].reasons == ["force_directions_completed"]
    assert observers[1].reasons
    if fault == "ordinary":
        assert any("secondary delivery failed" in note for note in primary.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["cancellation", "safety", "capture", "ordinary_optional", "first_cleanup"])
async def test_effort_no_primary_control_flow_is_not_silenced(monkeypatch, kind):
    import asyncio

    ctx, robot = _Context(video=False), _TwoEffortJoints()
    _effort_probe(monkeypatch, robot)
    monkeypatch.setattr(robot, "get_child_body_path", lambda index: "/Robot/child")
    expected = (
        asyncio.CancelledError("requested cancellation")
        if kind == "cancellation"
        else (
            effort_limit.UnsafeEvidencePathError("unsafe evidence path")
            if kind == "safety"
            else (
                RuntimeError("unknown capture engine failure")
                if kind == "capture"
                else (
                    OSError("required first cleanup failed")
                    if kind == "first_cleanup"
                    else OSError("ordinary optional camera unavailable")
                )
            )
        )
    )
    attempts = []

    def fail_once(*args, **kwargs):
        attempts.append(kind)
        if len(attempts) == 1:
            raise expected

    async def fail_capture(**kwargs):
        attempts.append(kind)
        raise expected

    if kind == "capture":
        ctx.capture_frame = fail_capture
    elif kind == "first_cleanup":
        monkeypatch.setattr(effort_limit, "clear_external_force", fail_once)
    else:
        ctx.scene.update_camera_follow = fail_once
    call = effort_limit.run_effort_limit(
        ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
    )
    if kind == "ordinary_optional":
        await call
        assert ctx.steps == 120
        assert ctx.metrics["eff_joints_tested"] == 2
    else:
        with pytest.raises(BaseException) as caught:
            await call
        assert caught.value is expected
    assert attempts


@pytest.mark.asyncio
@pytest.mark.parametrize("joint_number", [1, 2])
@pytest.mark.parametrize("signal", ["cancel", "exit", "keyboard", "unsafe"])
@pytest.mark.parametrize("secondary", ["none", "metric", "broken_note"])
async def test_early_progress_retains_primary_and_current_joint_evidence(monkeypatch, joint_number, signal, secondary):
    import asyncio

    ctx, robot = _Context(video=False), _TwoEffortJoints()
    observers = _effort_probe(monkeypatch, robot)
    robot.position = 2.0  # Existing range criterion records a +x break on joint 1.
    primary_type = {
        "cancel": asyncio.CancelledError,
        "exit": SystemExit,
        "keyboard": KeyboardInterrupt,
        "unsafe": effort_limit.UnsafeEvidencePathError,
    }[signal]
    primary = primary_type("interrupted before current joint setup")
    if secondary == "broken_note":

        def broken_note(_text):
            raise ValueError("note sink unavailable")

        primary.add_note = broken_note
    cleanup, mapped, metric_attempts = [], [], []
    old_mapping = robot.get_child_body_path
    old_metric = ctx.add_metric

    def mapping(index):
        mapped.append(index)
        return old_mapping(index)

    def step(message):
        if message.startswith(f"EFF joint {joint_number}/"):
            raise primary

    def metric(name, value):
        metric_attempts.append(name)
        if secondary != "none" and name == "eff_joints_tested":
            raise OSError("secondary metrics unavailable")
        old_metric(name, value)

    ctx.step, ctx.add_metric = step, metric
    monkeypatch.setattr(robot, "get_child_body_path", mapping)
    monkeypatch.setattr(effort_limit, "clear_external_force", lambda *args: cleanup.append(args[-1]))
    with pytest.raises(BaseException) as caught:
        await effort_limit.run_effort_limit(
            ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 0.1}
        )
    assert caught.value is primary
    incomplete = ctx.metrics["eff_incomplete_joint_evidence"]
    assert incomplete["status"] == "incomplete"
    assert incomplete["evaluated_directions"] == []
    assert incomplete["broke_directions"] == []
    assert incomplete["interrupted_direction"] is None
    assert len(mapped) == joint_number - 1
    assert cleanup == (["/Robot/child"] if joint_number == 2 else [])
    completed = ctx.metrics["eff_joint_results"]
    assert len(completed) == joint_number - 1
    if completed:
        assert completed[0]["broke_directions"] == ["+x"]
        assert completed[0]["name"] != incomplete["name"]
    assert len(observers) == joint_number - 1
    assert "eff_incomplete_joint_evidence" in metric_attempts

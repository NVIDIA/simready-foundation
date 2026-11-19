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

"""FET028 diagnostic-only fractions and capture associations, without Kit."""

import ast
import asyncio
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_close_lift as phase
from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver

SOURCE = Path(phase.__file__)


def _nested_callback(name, namespace):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[callback], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize(
    "position,opening,closing,expected",
    [(0.5, 0, 1, 0.5), (0.5, 1, 0, 0.5), (0, 1, 0, 1), (1, 1, 0, 0), (-0.2, 1, 0, 1.2)],
)
def test_closed_fraction_preserves_signed_range_and_overshoot(position, opening, closing, expected):
    assert phase._closed_fraction(position, opening, closing) == pytest.approx(expected)


@pytest.mark.parametrize(
    "position,opening,closing",
    [(0.2, 0.2, 0.2), (None, 0, 1), (math.nan, 0, 1), (0, math.inf, 1), (0, 1, -math.inf), (True, 0, 1)],
)
def test_closed_fraction_does_not_invent_progress_for_held_or_unavailable_dofs(position, opening, closing):
    assert phase._closed_fraction(position, opening, closing) is None


@pytest.mark.parametrize("positions,expected", [([0.5, 0.5, 0.2], 0.5), ([None, math.nan, 0.2], None)])
def test_close_diagnostic_ignores_held_and_unavailable_dofs_without_a_false_zero(positions, expected):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    diagnostic = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and any(
            isinstance(child, ast.Constant) and child.value == "Close diagnostic skipped: %s"
            for handler in node.handlers
            for child in ast.walk(handler)
        )
    )
    metrics, logs = {}, []
    namespace = {
        "robot": SimpleNamespace(get_joint_positions=lambda: positions),
        "grasp_specs": [
            {"idx": 0, "name": "positive", "open": 0, "closed": 1},
            {"idx": 1, "name": "negative", "open": 1, "closed": 0},
            {"idx": 2, "name": "held", "open": 0.2, "closed": 0.2},
        ],
        "shape": "cube",
        "close_contact": False,
        "ctx": SimpleNamespace(add_metric=lambda name, value: metrics.update({name: value}), log=logs.append),
        "np": np,
        "math": math,
        "_closed_fraction": phase._closed_fraction,
    }
    exec(compile(ast.Module(body=[diagnostic], type_ignores=[]), str(SOURCE), "exec"), namespace)
    assert metrics["close_joint_fraction_cube"] == expected
    assert "reopening and setup" in logs[-1]
    if expected is None:
        assert metrics["close_joint_actual_cube_positive"] is None
        assert metrics["close_joint_actual_cube_negative"] is None
        assert "mean n/a" in logs[-1]


@pytest.mark.parametrize("heuristic", [False, True])
def test_failure_guidance_does_not_attribute_proxy_trial_failure_to_the_asset(heuristic):
    message = phase._fix_message_failed_to_lift(3.4, heuristic, ["cube"], 0.85)
    assert "does not establish an asset defect" in message
    assert "heuristic payload is not a rated capability" in message
    assert "placement" in message and "reopening" in message and "backend" in message
    assert "unmeasured, not zero" in message
    assert "so the failure is in the asset" not in message
    assert "below ~0.8" not in message
    assert "1000.0-5000.0" not in message
    if heuristic:
        assert "custom:maxPayload was not authored" in message


def test_capture_association_is_optional_and_cannot_change_execution():
    recorded, warnings = [], []
    good = SimpleNamespace(record_capture=recorded.append)
    broken = SimpleNamespace(
        record_capture=lambda path: (_ for _ in ()).throw(RuntimeError("evidence unavailable")),
        _warn=lambda: warnings.append("partial"),
    )
    phase._record_gripper_capture(None, good, {"joint": good})
    assert recorded == []
    phase._record_gripper_capture("frame.png", None, {"legacy": SimpleNamespace(), "broken": broken, "good": good})
    assert recorded == ["frame.png"] and warnings == ["partial"]


@pytest.mark.parametrize("record_markers", [False, True])
def test_video_hook_keeps_capture_cadence_and_nullable_readbacks_without_stepping(monkeypatch, record_markers):
    evidence = pytest.importorskip("simready.evaluate.runner.motion_evidence")
    clock = SimpleNamespace(time=0.0)
    timeline = ModuleType("omni.timeline")
    timeline.get_timeline_interface = lambda: SimpleNamespace(get_current_time=lambda: clock.time)
    omni = ModuleType("omni")
    omni.timeline = timeline
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.timeline", timeline)
    histories, warnings, capture_calls, camera_calls, video_frames = [], [], [], [], []

    def begin(name, channels, metadata):
        history = evidence.MotionEvidence(name, channels, metadata=metadata)
        histories.append(history)
        return history

    async def capture_frame(**kwargs):
        capture_calls.append(kwargs)
        # Existing render stabilization can advance timeline time. The marker
        # must still associate with a retained pre-capture observation.
        clock.time += 2 / 240
        return "frame_%d.png" % len(capture_calls)

    ctx = SimpleNamespace(
        begin_motion_history=begin,
        warn=warnings.append,
        capture_frame=capture_frame,
        scene=SimpleNamespace(update_camera_follow=lambda **kwargs: camera_calls.append(kwargs)),
    )
    motion = MotionObserver(
        ctx, "object", {"object_z": {"unit": "stage_length", "source": "readback"}}, sample_stride=4
    )
    # The real callback records more channels; retain the schema it declares.
    motion.history.channels = {
        key: {"unit": "stage_length", "source": "readback"}
        for key in (
            "object_x",
            "object_y",
            "object_z",
            "carrier_x",
            "carrier_y",
            "carrier_z",
            "relative_z",
            "finger_separation",
        )
    }
    joint = MotionObserver(ctx, "joint", {"position": {"unit": "rad", "source": "readback"}})
    joint.sample({"position": None}, time_s=0, phase="open")
    namespace = {
        "motion": motion,
        "motion_joints": {"joint": joint},
        "motion_object_reader": lambda: np.array([1, 2, 3]),
        "carrier": object(),
        "carrier_world_position": lambda carrier: np.array([1, 2, 2]),
        "robot": SimpleNamespace(get_link_world_positions=lambda paths: {}),
        "fingertip_set": SimpleNamespace(tip_link_paths=["left", "right"]),
        "motion_phase": "open",
        "motion_last_targets": None,
        "config": {"disable_capture": False},
        "np": np,
        "ctx": ctx,
        "video_capture_every": 8,
        "video_label_prefix": "cube_v",
        "video_frames": video_frames,
        "_record_gripper_capture": phase._record_gripper_capture if record_markers else lambda *args: None,
    }
    callback = _nested_callback("_video_capture", namespace)

    async def run_callbacks():
        for index in range(17):
            clock.time += 1 / 240
            await callback(index)

    asyncio.run(run_callbacks())
    assert capture_calls == [{"label": "cube_v", "stabilize_frames": 1}] * 3
    assert len(camera_calls) == 17
    assert len(video_frames) == 3
    assert len(motion.history.samples) == 5
    assert all(row["finger_separation"] is None for row in motion.history.samples)
    assert len(motion.history.captures) == (3 if record_markers else 0)
    assert len(joint.history.captures) == (1 if record_markers else 0)  # coalesced retained observation
    assert not warnings
    for marker in motion.history.captures:
        assert any(row["time_s"] == marker["observation_time_s"] for row in motion.history.samples)
    assert motion.history.clock_source == "timeline"
    # Fake context exposes no step/drive methods; callback did not add either.


@pytest.mark.parametrize("outcome", ["success", "missing", "raises", "disabled"])
def test_keyframe_marks_only_successful_capture_and_preserves_exception(outcome):
    calls, markers = [], []

    async def capture_frame(**kwargs):
        calls.append(kwargs)
        if outcome == "raises":
            raise RuntimeError("capture failed")
        return "keyframe.png" if outcome == "success" else None

    observer = SimpleNamespace(record_capture=markers.append)
    namespace = {
        "config": {"disable_capture": outcome == "disabled"},
        "ctx": SimpleNamespace(
            scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None), capture_frame=capture_frame
        ),
        "motion": observer,
        "motion_joints": {},
        "_record_gripper_capture": phase._record_gripper_capture,
    }
    callback = _nested_callback("_capture", namespace)
    if outcome == "raises":
        with pytest.raises(RuntimeError, match="capture failed"):
            asyncio.run(callback("closed"))
    else:
        assert asyncio.run(callback("closed")) == ("keyframe.png" if outcome == "success" else None)
    assert markers == (["keyframe.png"] if outcome == "success" else [])
    assert len(calls) == (0 if outcome == "disabled" else 1)


def test_diagnostic_fraction_is_not_a_lift_verdict_input(monkeypatch):
    def unexpected(*args):
        raise AssertionError("a diagnostic fraction must not influence the lift verdict")

    monkeypatch.setattr(phase, "_closed_fraction", unexpected)
    cfg = phase.get_defaults()
    kwargs = {
        "object_pre_close_xy": np.array([0, 0]),
        "object_pre_close_z": 0.5,
        "object_pre_lift_z": 0.5,
        "carrier_pre_lift_z": 0.5,
        "carrier_post_lift_z": 0.7,
        "config": cfg,
    }
    assert phase.evaluate_pass_criterion(object_post_lift=np.array([0, 0, 0.7]), **kwargs).passed
    assert not phase.evaluate_pass_criterion(object_post_lift=np.array([0, 0, 0.5]), **kwargs).passed


@pytest.mark.parametrize("configured_fps", [17.5, 20.0, 30.4])
def test_history_encoding_fps_matches_existing_encoder_request(configured_fps):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    metadata_fps = next(
        value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "encoded_video_fps"
    )
    forwarded_fps = next(
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_cleanup_gripper_trial"
        for keyword in node.keywords
        if keyword.arg == "video_fps"
    )
    namespace = {"video_fps_max": configured_fps}
    recorded = eval(compile(ast.Expression(metadata_fps), str(SOURCE), "eval"), namespace)
    forwarded = eval(compile(ast.Expression(forwarded_fps), str(SOURCE), "eval"), namespace)
    requests = []
    ctx = SimpleNamespace(encode_video=lambda frames, **kwargs: requests.append(kwargs["fps"]))
    asyncio.run(
        phase._cleanup_gripper_trial(
            ctx,
            None,
            carrier=None,
            support_pause=None,
            obj=None,
            object_edit_target=None,
            contact_collector=None,
            contact_enabled=False,
            contact_metric="native_contact_diagnostics",
            stop_reason="completed",
            video_frames=["frame.png"],
            video_fps=forwarded,
            shape="cube",
        )
    )
    assert recorded == requests[0] == int(round(configured_fps))


def test_emitted_close_guidance_does_not_assert_a_contact_or_gain_cause():
    source = SOURCE.read_text(encoding="utf-8")
    assert "Asset tuning issue" not in source
    assert "contact established " not in source
    assert "grip-confirmed[%s]: contact=" not in source
    assert "This carrier-axis drift alone does " in source
    assert "before attributing a cause or changing gains." in source

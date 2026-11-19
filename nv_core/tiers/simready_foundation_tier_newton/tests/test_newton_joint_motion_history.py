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

import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import motion_history


def test_legacy_runner_does_not_read_usd(monkeypatch):
    def unexpected(*args):
        raise AssertionError("legacy recording must not inspect USD")

    monkeypatch.setattr(motion_history, "joint_metadata", unexpected)
    observer = motion_history.make_joint_observer(SimpleNamespace(), {}, "joint", "trial", {})
    assert observer.history is None


@pytest.mark.parametrize("unit", ["rad", "stage_length", "unknown_native"])
def test_identity_controls_units_without_mutating_input(monkeypatch, unit):
    recorded = {}
    history = SimpleNamespace(mark_partial=lambda reason: None)
    ctx = SimpleNamespace(
        begin_motion_history=lambda name, channels, metadata: recorded.update(channels=channels, metadata=metadata)
        or history,
        warn=lambda message: None,
    )
    monkeypatch.setattr(
        motion_history,
        "joint_metadata",
        lambda *args, **kwargs: {
            "joint_name": "joint",
            "unit": unit,
            "identity_resolved": True,
            "prim_path": "/Robot/joint",
        },
    )
    specs = {
        "position": {"unit": "{joint}", "source": "readback"},
        "velocity": {"unit": "{joint}/s", "source": "readback"},
        "force": {"unit": "N", "source": "applied external force"},
    }
    motion_history.make_joint_observer(ctx, {}, "joint", "trial", specs)
    assert recorded["channels"]["position"]["unit"] == unit
    assert recorded["channels"]["velocity"]["unit"] == unit + "/s"
    assert recorded["channels"]["force"]["unit"] == "N"
    assert recorded["metadata"]["prim_path"] == "/Robot/joint"
    assert specs["position"]["unit"] == "{joint}"


def test_metadata_failure_is_partial_not_a_test_failure(monkeypatch):
    recorded, limitations, warnings = {}, [], []
    history = SimpleNamespace(mark_partial=limitations.append)
    ctx = SimpleNamespace(
        begin_motion_history=lambda name, channels, metadata: recorded.update(channels=channels, metadata=metadata)
        or history,
        warn=warnings.append,
    )

    def missing_identity(*args):
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(motion_history, "joint_metadata", missing_identity)
    motion_history.make_joint_observer(ctx, {}, "joint", "trial", {"position": {"unit": "{joint}"}})
    assert recorded["channels"]["position"]["unit"] == "unknown_native"
    assert recorded["metadata"]["context_partial"]
    assert limitations and len(warnings) == 1


@pytest.mark.parametrize("position", [float("nan"), float("inf"), None])
def test_optional_readback_gaps_are_nullable_and_partial(position):
    samples, warnings = [], []

    def read_positions():
        if position is None:
            raise RuntimeError("readback unavailable")
        return [position]

    observer = SimpleNamespace(
        history=True,
        sample=lambda values, **kwargs: samples.append(values),
        _warn=lambda: warnings.append("partial"),
    )
    motion_history.sample_joint_observers(
        SimpleNamespace(get_joint_positions=read_positions), {0: observer}, [1], 0.1, "hold"
    )
    assert samples == [{"position": None, "target": 1.0, "error": None}]
    assert warnings


def test_inactive_observers_do_not_request_optional_readback():
    def unexpected():
        raise AssertionError("unused observation must not request positions")

    motion_history.sample_joint_observers(
        SimpleNamespace(get_joint_positions=unexpected), {0: SimpleNamespace(history=None)}, None, 0.1, "hold"
    )

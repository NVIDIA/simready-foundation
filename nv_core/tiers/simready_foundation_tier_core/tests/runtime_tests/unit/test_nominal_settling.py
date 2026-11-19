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
"""Nominal robot settling requests complete ticks, not processing-only updates."""

import asyncio
import importlib
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.coordination_timing import (
    CoordinationBudget,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
    settle_nominal,
)

PHASES = (
    "effort_limit",
    "drive_gain_validation",
    "jacobian_ik",
    "ik_target_reach",
    "multi_joint_coordination",
    "state_accuracy",
    "mimic_joint",
    "velocity_limit",
)


@pytest.mark.parametrize(
    ("seconds", "fps", "expected"),
    [(0.0, 240.0, 0), (1.0, 240.0, 240), (0.5, 240.0, 120), (0.01, 240.0, 3), (1e-320, 1e-320, 1)],
)
def test_nominal_settle_count(seconds, fps, expected):
    assert nominal_settle_steps(seconds, fps) == expected


@pytest.mark.parametrize(
    ("seconds", "fps"),
    [
        (False, 240.0),
        ("1", 240.0),
        (None, 240.0),
        (-1.0, 240.0),
        (math.nan, 240.0),
        (math.inf, 240.0),
        (1.0, False),
        (1.0, "240"),
        (1.0, None),
        (1.0, 0.0),
        (1.0, -1.0),
        (1.0, math.nan),
        (1.0, math.inf),
        (1e308, 1e308),
        (10**1000, 240.0),
    ],
)
def test_nominal_settle_rejects_invalid_configuration(seconds, fps):
    with pytest.raises(ValueError):
        nominal_settle_steps(seconds, fps)


@pytest.mark.parametrize(("count", "heartbeats"), [(0, []), (1, [1]), (40, [40]), (81, [40, 80, 81])])
def test_settle_uses_complete_ticks_and_periodic_progress(count, heartbeats):
    completed = []
    messages = []

    async def step_one():
        completed.append(len(completed) + 1)

    async def forbidden_processing_only(*_args):
        pytest.fail("Nominal settling must not use processing-only physics updates")

    context = SimpleNamespace(step_one=step_one, physics_steps=forbidden_processing_only, step=messages.append)
    assert asyncio.run(settle_nominal(context, count, 1.0, phase="STA")) == count
    assert len(completed) == count
    assert messages == [f"STA: nominal settle {tick}/{count} ticks" for tick in heartbeats]


@pytest.mark.parametrize("failure", [RuntimeError("tick failed"), asyncio.CancelledError("cancelled")])
def test_settle_preserves_step_failure_and_cancellation(failure):
    calls = []
    messages = []

    async def step_one():
        calls.append(True)
        if len(calls) == 50:
            raise failure

    context = SimpleNamespace(step_one=step_one, step=messages.append)
    with pytest.raises(type(failure)) as error:
        asyncio.run(settle_nominal(context, 100.0, 1.0, phase="IK"))
    assert error.value is failure
    assert len(calls) == 50
    assert messages == ["IK: nominal settle 40/100 ticks"]


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize(
    "config", [{"physics_fps": 0.0}, {"physics_fps": True}, {"settle_seconds": -1.0}, {"settle_seconds": "1"}]
)
def test_each_phase_validates_raw_settle_config_before_discovery_or_skip(phase, config):
    module = importlib.import_module("simready.foundation.tier_core.runtime_tests.articulation_phases." + phase)
    run = getattr(module, "run_" + phase)
    with pytest.raises(ValueError):
        asyncio.run(run(None, None, {}, config))


@pytest.mark.parametrize("phase", PHASES)
def test_each_phase_uses_owned_complete_tick_helper(phase):
    module = importlib.import_module("simready.foundation.tier_core.runtime_tests.articulation_phases." + phase)
    if phase == "multi_joint_coordination":
        assert module.CoordinationBudget is CoordinationBudget
    else:
        assert module.settle_nominal is settle_nominal


@pytest.mark.parametrize("phase", PHASES + ("coordination_timing",))
def test_framework_file_discovery_loads_owned_settling_without_package_context(phase):
    from simready.evaluate.core.discovery import _import_test_file

    source_module = importlib.import_module("simready.foundation.tier_core.runtime_tests.articulation_phases." + phase)
    source_path = source_module.__file__
    before = set(sys.modules)
    try:
        diagnostic = _import_test_file(source_path, import_root=str(Path(source_path).parents[1]))
        assert diagnostic is None, diagnostic
        loaded = [
            module
            for name, module in sys.modules.items()
            if name not in before
            and name.startswith("_simready_evaluate_")
            and getattr(module, "__file__", None) == source_path
        ]
        assert len(loaded) == 1
        assert loaded[0].__package__ == ""
        if phase == "coordination_timing":
            # Helper files are scanned too. They must import in the same
            # package-less mode as executable procedures.
            assert loaded[0].nominal_settle_steps is nominal_settle_steps
            assert callable(loaded[0].CoordinationBudget.step_one)
        elif phase == "multi_joint_coordination":
            assert loaded[0].CoordinationBudget is CoordinationBudget
        else:
            assert loaded[0].settle_nominal is settle_nominal
        if phase != "coordination_timing":
            assert callable(getattr(loaded[0], "run_" + phase))
    finally:
        # Remove only this successful package-less scan entry. Qualified helper
        # imports belong to the ordinary provider and must not be rolled back.
        for name in set(sys.modules) - before:
            if (
                name.startswith("_simready_evaluate_")
                and getattr(sys.modules.get(name), "__file__", None) == source_path
            ):
                sys.modules.pop(name, None)

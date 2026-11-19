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

import importlib
import json
from types import SimpleNamespace

import pytest
from simready.evaluate.core import decorator
from simready.evaluate.runner.test_context import RunContext
from simready.evaluate_engine_kit.execution import _result_status_and_message
from simready.foundation.tier_core.runtime_tests import engine_guard
from simready.foundation.tier_core.runtime_tests.fet003_physics import (
    _drop_config,
    ground_drop,
    slope_drop,
)

GATES = [
    ("ground_drop", "floor_margin"),
    ("ground_drop", "rest_tolerance"),
    ("ground_drop", "rest_detection_hold_seconds"),
    ("ground_drop", "penetration_check_seconds"),
    ("slope_drop", "maximum_slope_separation"),
    ("slope_drop", "horizontal_movement_threshold"),
    ("slope_drop", "slope_contact_tolerance"),
    ("slope_drop", "slope_penetration_tolerance"),
    ("slope_drop", "separation_confirmation_seconds"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,key", GATES)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "0.1", -0.1])
async def test_official_drop_gate_errors_before_scene_work(monkeypatch, module_name, key, value):
    monkeypatch.setattr(decorator, "_REGISTRY", [])
    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None)
    importlib.reload(ground_drop if module_name == "ground_drop" else slope_drop)
    definition = decorator.get_registered_tests()[-1]
    config = dict(definition.config_defaults)
    config[key] = json.loads(json.dumps(value))
    ctx = RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir="unused-output",
        test_name=definition.name,
        test_version=definition.version,
        feature_id=definition.features[0].id,
        engine_name="kit",
        engine_version="6.1.0",
        session_id="drop-preflight",
        scene=None,
        config=config,
    )
    with pytest.raises(RuntimeError, match=key) as caught:
        await definition.func(ctx)
    status, message = _result_status_and_message(ctx, test_exception=caught.value)
    assert status == "error" and key in message and not ctx.failed


@pytest.mark.parametrize("module,slope", [(ground_drop, False), (slope_drop, True)])
def test_defaults_and_existing_zero_policies_remain_valid(module, slope):
    config = dict(
        module.GROUND_DROP_KWARGS["config_defaults"] if not slope else module.SLOPE_DROP_KWARGS["config_defaults"]
    )
    _drop_config.validate_drop_config(config, slope=slope)
    for key in config:
        if key not in {"physics_fps", "capture_fps", "asset_load_timeout"}:
            config[key] = 0
    config["floor_level"] = -3
    if slope:
        config["slope_angle_deg"] = -45
    _drop_config.validate_drop_config(config, slope=slope)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "0.05", -0.01])
async def test_actual_slope_loop_rejects_unqualified_separation_before_stepping(value):
    config = {
        "pen_threshold": -0.1,
        "horiz_threshold": 0.01,
        "contact_tolerance": 0.02,
        "slope_penetration_tolerance": 0.02,
        "max_slope_separation": value,
    }
    steps = []

    async def step():
        steps.append(True)

    with pytest.raises(RuntimeError, match="max_slope_separation"):
        await slope_drop._run_simulation(SimpleNamespace(physics_step=step), config)
    assert not steps


@pytest.mark.parametrize("key", ["physics_fps", "capture_fps"])
@pytest.mark.parametrize("value", [0, -1, 1.5, True, float("inf")])
def test_rates_are_positive_whole_real_counts(key, value):
    config = dict(ground_drop.GROUND_DROP_KWARGS["config_defaults"])
    config[key] = value
    with pytest.raises(RuntimeError, match=key):
        _drop_config.validate_drop_config(config)

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
import ast
import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_SOURCE = Path(__file__).parents[3] / "simready_benchmark_kit_suite" / "fet003_physics" / "slope_drop.py"


def _registration():
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != "test_slope_drop":
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == "test":
                return {keyword.arg: ast.literal_eval(keyword.value) for keyword in decorator.keywords}
    raise AssertionError("slope_drop @test registration not found")


def _run_simulation_function():
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_slope_plane_distance_interval", "_run_simulation"}
    ]
    namespace = {"Any": Any, "math": __import__("math"), "time": time}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(_SOURCE), "exec"), namespace)
    return namespace["_run_simulation"]


class _FakeContext:
    def __init__(self, samples):
        self._samples = iter(samples)
        self.scene = SimpleNamespace(update_camera_follow=lambda: None)
        self.steps = []

    async def physics_step(self):
        return None

    async def physics_advance(self):
        return None

    async def capture_frame(self, **_kwargs):
        return b"frame"

    def get_asset_bounds(self):
        cy, z_min = next(self._samples)
        return SimpleNamespace(min=(-0.1, cy - 0.1, z_min), max=(0.1, cy + 0.1, z_min + 0.2))

    def step(self, message):
        self.steps.append(message)

    def fail(self, message):
        raise AssertionError(message)


def _simulation_config():
    return {
        "total_frames": 3,
        "capture_interval": 10,
        "pen_threshold": -0.1,
        "horiz_threshold": 0.01,
        "post_horiz_frames": 1,
        "slope_min_y": -10.0,
        "slope_max_y": 10.0,
        "slope_center_z": 0.0,
        "slope_tangent": 1.0,
        "contact_tolerance": 0.02,
        "slope_penetration_tolerance": 0.02,
        "max_slope_separation": 0.05,
        "separation_confirmation_frames": 2,
    }


def test_slope_drop_requires_minimum_spawn_clearance():
    registration = _registration()

    assert registration["version"] == "3.3.0"
    assert registration["max_duration"] == 300
    assert registration["config_defaults"]["minimum_slope_clearance"] == 0.1
    assert registration["config_defaults"]["slope_contact_tolerance"] == 0.02
    assert registration["config_defaults"]["slope_penetration_tolerance"] == 0.02
    assert registration["config_defaults"]["maximum_slope_separation"] == 0.05
    assert registration["config_defaults"]["separation_confirmation_seconds"] == 0.1


def test_slope_drop_requires_contact_and_downhill_motion():
    run_simulation = _run_simulation_function()
    _frames, state = asyncio.run(
        run_simulation(_FakeContext([(-1.0, 1.01), (-0.98, 0.99), (-0.96, 0.97)]), _simulation_config())
    )

    assert state["contact_detected"] is True
    assert state["horiz_detected"] is True
    assert state["excessive_separation"] is False
    assert state["uphill_motion"] is False


def test_slope_drop_detects_tangent_curved_body_contact():
    run_simulation = _run_simulation_function()
    # A radius-0.1 sphere tangent to z=-y has bbox.min.z 0.0414 m above
    # the plane at its centre Y. The former centre-Y/min-Z heuristic therefore
    # missed contact with its 0.02 m tolerance even as the sphere moved 4 m.
    radius = 0.1
    tangent_offset = radius * (2.0**0.5) - radius
    _frames, state = asyncio.run(
        run_simulation(
            _FakeContext(
                [
                    (-4.0, 4.0 + tangent_offset),
                    (-2.0, 2.0 + tangent_offset),
                    (0.0, tangent_offset),
                ]
            ),
            _simulation_config(),
        )
    )

    assert state["contact_detected"] is True
    assert state["horiz_detected"] is True
    assert state["slope_penetrated"] is False


def test_slope_drop_rejects_post_contact_launch():
    run_simulation = _run_simulation_function()
    _frames, state = asyncio.run(
        run_simulation(_FakeContext([(-1.0, 1.01), (-0.98, 1.5), (-0.96, 1.5)]), _simulation_config())
    )

    assert state["contact_detected"] is True
    assert state["excessive_separation"] is True
    assert state["separation_frames"] == 2
    assert state["separation_frame"] == 2


def test_slope_drop_rejects_tunnelling_below_ramp_as_penetration():
    run_simulation = _run_simulation_function()
    _frames, state = asyncio.run(
        run_simulation(_FakeContext([(-1.0, 0.5), (-0.98, 0.5), (-0.96, 0.5)]), _simulation_config())
    )

    assert state["slope_penetrated"] is True
    assert state["contact_detected"] is False
    assert state["horiz_detected"] is False


def test_slope_drop_ignores_single_frame_separation_spike():
    run_simulation = _run_simulation_function()
    config = _simulation_config()
    config["post_horiz_frames"] = 2
    _frames, state = asyncio.run(run_simulation(_FakeContext([(-1.0, 1.01), (-0.98, 1.5), (-0.96, 0.97)]), config))

    assert state["contact_detected"] is True
    assert state["horiz_detected"] is True
    assert state["excessive_separation"] is False
    assert state["separation_frames"] == 0


def test_slope_drop_ignores_separation_after_bbox_reaches_ramp_edge():
    run_simulation = _run_simulation_function()
    config = _simulation_config()
    config["slope_max_y"] = -0.9
    config["post_horiz_frames"] = 2
    _frames, state = asyncio.run(run_simulation(_FakeContext([(-1.0, 1.01), (-0.85, 1.5), (-0.75, 1.6)]), config))

    assert state["contact_detected"] is True
    assert state["horiz_detected"] is True
    assert state["excessive_separation"] is False
    assert state["left_slope_frame"] == 1


def test_slope_drop_records_uphill_rebound_without_counting_it_as_slide():
    run_simulation = _run_simulation_function()
    _frames, state = asyncio.run(
        run_simulation(_FakeContext([(-1.0, 1.01), (-1.02, 1.03), (-1.02, 1.03)]), _simulation_config())
    )

    assert state["contact_detected"] is True
    assert state["uphill_motion"] is True
    assert state["horiz_detected"] is False

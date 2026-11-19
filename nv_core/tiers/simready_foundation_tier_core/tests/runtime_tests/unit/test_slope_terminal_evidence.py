# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Terminal slope-drop capture regressions for both engine procedures."""

import ast
import asyncio
import math
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from simready.evaluate.core.output_layout import UnsafeEvidencePathError

_TIERS = Path(__file__).parents[4]


def _run_simulation(tier):
    source = (
        _TIERS
        / f"simready_foundation_tier_{tier}"
        / "simready"
        / "foundation"
        / f"tier_{tier}"
        / "runtime_tests"
        / "fet003_physics"
        / "slope_drop.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_slope_plane_distance_interval", "_run_simulation"}
    ]
    namespace = {"Any": Any, "math": math, "time": time, "UnsafeEvidencePathError": UnsafeEvidencePathError}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["_run_simulation"]


class _Context:
    def __init__(self, samples, fail_capture_number=None):
        self._samples = iter(samples)
        self.fail_capture_number = fail_capture_number
        self.capture_attempts = 0
        self.warnings = []
        self.scene = SimpleNamespace(update_camera_follow=lambda: None)

    async def physics_step(self):
        pass

    async def physics_advance(self):
        pass

    def get_asset_bounds(self):
        cy, z_min = next(self._samples)
        return SimpleNamespace(min=(-0.1, cy - 0.1, z_min), max=(0.1, cy + 0.1, z_min + 0.2))

    async def capture_frame(self, **_kwargs):
        self.capture_attempts += 1
        if self.capture_attempts == self.fail_capture_number:
            raise RuntimeError("native capture unavailable")
        return f"frame-{self.capture_attempts}"

    def step(self, _message):
        pass

    def warn(self, message):
        self.warnings.append(message)


def _config():
    return {
        "total_frames": 3,
        "physics_fps": 240,
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


@pytest.mark.parametrize("tier", ["core", "newton"])
@pytest.mark.parametrize(
    ("samples", "config_changes", "state_key", "expected_captures"),
    [
        ([(-1.0, 0.5)], {}, "slope_penetrated", 1),
        ([(-1.0, 1.01), (-0.98, 1.5), (-0.96, 1.5)], {}, "excessive_separation", 2),
        (
            [(-1.0, 1.01), (-0.98, 0.99), (-0.96, -0.2)],
            {"slope_max_y": -0.97},
            "penetrated",
            2,
        ),
    ],
)
def test_terminal_failure_observation_gets_final_capture(tier, samples, config_changes, state_key, expected_captures):
    config = {**_config(), **config_changes}
    ctx = _Context(samples)
    frames, state = asyncio.run(_run_simulation(tier)(ctx, config))

    assert state[state_key] is True
    assert ctx.capture_attempts == expected_captures
    assert frames[-1] == f"frame-{expected_captures}"


@pytest.mark.parametrize("tier", ["core", "newton"])
def test_terminal_capture_error_keeps_measured_slope_failure(tier):
    ctx = _Context([(-1.0, 0.5)], fail_capture_number=1)
    frames, state = asyncio.run(_run_simulation(tier)(ctx, _config()))

    assert state["slope_penetrated"] is True
    assert frames == []
    assert ctx.capture_attempts == 1
    assert any("terminal" in warning.lower() for warning in ctx.warnings)


@pytest.mark.parametrize("tier", ["core", "newton"])
@pytest.mark.parametrize("failure_at", ["capture", "warning"])
def test_terminal_unsafe_evidence_path_error_propagates(tier, failure_at):
    ctx = _Context([(-1.0, 0.5)], fail_capture_number=1 if failure_at == "warning" else None)
    failure = UnsafeEvidencePathError("redirected capture path")

    async def unsafe_capture(**_kwargs):
        raise failure

    def unsafe_warning(_message):
        raise failure

    if failure_at == "capture":
        ctx.capture_frame = unsafe_capture
    else:
        ctx.warn = unsafe_warning

    with pytest.raises(UnsafeEvidencePathError) as caught:
        asyncio.run(_run_simulation(tier)(ctx, _config()))
    assert caught.value is failure


@pytest.mark.parametrize("tier", ["core", "newton"])
def test_terminal_capture_cancellation_is_not_swallowed(tier):
    ctx = _Context([(-1.0, 0.5)])

    async def cancelled_capture(**_kwargs):
        raise asyncio.CancelledError()

    ctx.capture_frame = cancelled_capture
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run_simulation(tier)(ctx, _config()))


@pytest.mark.parametrize("tier", ["core", "newton"])
def test_terminal_warning_sink_failure_does_not_replace_measured_result(tier):
    ctx = _Context([(-1.0, 0.5)], fail_capture_number=1)

    def broken_warning(_message):
        raise RuntimeError("warning sink unavailable")

    ctx.warn = broken_warning
    frames, state = asyncio.run(_run_simulation(tier)(ctx, _config()))
    assert state["slope_penetrated"] is True
    assert frames == []


@pytest.mark.parametrize("tier", ["core", "newton"])
def test_terminal_capture_returning_none_is_not_added_to_video(tier):
    ctx = _Context([(-1.0, 0.5)])

    async def unavailable_capture(**_kwargs):
        return None

    ctx.capture_frame = unavailable_capture
    frames, state = asyncio.run(_run_simulation(tier)(ctx, _config()))

    assert state["slope_penetrated"] is True
    assert frames == []

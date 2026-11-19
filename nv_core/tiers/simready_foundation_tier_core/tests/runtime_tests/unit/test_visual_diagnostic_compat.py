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

"""Presentation callbacks cannot obscure encoding failures or measured verdicts."""

import asyncio
import sys
from types import SimpleNamespace

import pytest
from simready.evaluate.core.output_layout import UnsafeEvidencePathError
from simready.evaluate.runner.test_context import RunContext
from simready.foundation.tier_core.runtime_tests._visual_diagnostics import encode_visual_video


@pytest.fixture(autouse=True)
def fresh_engine_state(monkeypatch):
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)


def _context(engine):
    ctx = RunContext(
        asset_path="fixture.usda",
        asset_rel_path="fixture.usda",
        output_dir="unused-output",
        test_name="visual",
        test_version="1",
        feature_id="fixture",
        engine_name="kit",
        engine_version="1",
        session_id="diagnostic-compatibility",
        scene=None,
        config={},
    )
    ctx._engine_session = SimpleNamespace(encode_video=engine)
    return ctx


@pytest.mark.parametrize("hook", ["warn", "_refresh_timing_metrics"])
def test_optional_callback_failure_isolated_and_exact_override_restored(hook):
    ctx = _context(lambda *args, **kwargs: None)

    def unavailable(*args, **kwargs):
        raise OSError("optional publication failed")

    setattr(ctx, hook, unavailable)
    assert encode_visual_video(ctx, ["frame.png"]) is None
    assert vars(ctx)[hook] is unavailable
    assert ctx.warnings


def test_inherited_diagnostic_methods_are_not_left_shadowed():
    ctx = _context(lambda *args, **kwargs: None)
    assert "warn" not in vars(ctx) and "_refresh_timing_metrics" not in vars(ctx)
    encode_visual_video(ctx, ["frame.png"])
    assert "warn" not in vars(ctx) and "_refresh_timing_metrics" not in vars(ctx)


def test_engine_error_remains_primary_when_optional_timing_also_fails():
    primary = OSError("native encoder failed")

    def encode(*args, **kwargs):
        raise primary

    ctx = _context(encode)

    def unavailable():
        raise RuntimeError("optional timing failed")

    ctx._refresh_timing_metrics = unavailable
    with pytest.raises(OSError) as caught:
        encode_visual_video(ctx, ["frame.png"])
    assert caught.value is primary
    assert ctx._refresh_timing_metrics is unavailable


@pytest.mark.parametrize("hook", ["warn", "_refresh_timing_metrics"])
@pytest.mark.parametrize("error", [UnsafeEvidencePathError("unsafe evidence"), asyncio.CancelledError()])
def test_unsafe_diagnostic_and_cancellation_propagate(hook, error):
    ctx = _context(lambda *args, **kwargs: None)

    def unsafe(*args, **kwargs):
        raise error

    setattr(ctx, hook, unsafe)
    with pytest.raises(type(error)) as caught:
        encode_visual_video(ctx, ["frame.png"])
    assert caught.value is error
    assert vars(ctx)[hook] is unsafe


def test_retirement_during_diagnostic_failure_is_not_suppressed(monkeypatch):
    ctx = _context(lambda *args, **kwargs: None)
    primary = RuntimeError("retired engine")

    def retired(*args, **kwargs):
        monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", True, raising=False)
        raise primary

    ctx.warn = retired
    with pytest.raises(RuntimeError) as caught:
        encode_visual_video(ctx, ["frame.png"])
    assert caught.value is primary
    assert ctx.warn is retired

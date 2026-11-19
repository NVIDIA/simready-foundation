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
"""Completed pivot advice requires every required measurement and cleanup."""

import asyncio
from types import SimpleNamespace

import pytest
from simready.evaluate.reporter.view_model import build_view_model
from simready.evaluate_engine_kit.execution import _result_status_and_message
from test_visual_required_gate_preflight import _definition, _render_context


def _pivot_context(monkeypatch, *, position=(0.0, 0.0, 0.5)):
    """Keep the real declaration, context, scoring and status; stub native I/O."""
    definition = _definition(monkeypatch, "fet001_visual.pivot")
    ctx = _render_context(monkeypatch, definition, ["native-frame.png"] * 4)
    ctx.config.update(steps=2, video_capture_interval=1)
    bounds = SimpleNamespace(min=(-0.5, -0.5, 0.0), max=(0.5, 0.5, 1.0))
    ctx.get_asset_bounds = lambda *, authored: bounds
    ctx.get_asset_position = lambda *, authored: position
    return definition, ctx, bounds


def test_completed_advisory_has_successor_result_identity(monkeypatch):
    definition = _definition(monkeypatch, "fet001_visual.pivot")
    assert definition.version == "2.0.4"


@pytest.mark.asyncio
async def test_completed_subthreshold_score_is_explicit_advice_without_pass(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch)
    await definition.func(ctx)
    assert _result_status_and_message(ctx)[0] == "skipped"
    assert ctx.metrics["pivot_score"]["value"] == 0.3
    assert ctx.metrics["pivot_passed"]["value"] == 0
    expected_reason = (
        "Completed pivot measurements are below the recommended score; " "origin placement depends on object type."
    )
    assert ctx.metrics["assessment_advisory"]["value"] == {
        "status": "completed",
        "reason_code": "pivot_score_below_recommendation",
        "reason": expected_reason,
    }
    assert "assessment_applicability" not in ctx.metrics


@pytest.mark.asyncio
async def test_completed_passing_score_does_not_become_advice(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch, position=(0.0, 0.0, 0.0))
    await definition.func(ctx)
    assert _result_status_and_message(ctx)[0] == "pass"
    assert ctx.metrics["pivot_passed"]["value"] == 1
    assert "assessment_advisory" not in ctx.metrics


@pytest.mark.asyncio
async def test_early_invisibility_is_unmarked_unavailable_skip(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch)

    async def invisible(*_args, **_kwargs):
        return False

    monkeypatch.setitem(definition.func.__globals__, "ensure_asset_visible", invisible)
    await definition.func(ctx)
    assert _result_status_and_message(ctx)[0] == "skipped"
    assert "pivot_score" not in ctx.metrics
    assert "assessment_advisory" not in ctx.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("read", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("invalid", ["nan", "infinite", "inverted", "empty", "flat"])
async def test_invalid_required_geometry_cannot_claim_completed_advice(monkeypatch, read, invalid):
    definition, ctx, bounds = _pivot_context(monkeypatch)
    invalid_bounds = {
        "nan": SimpleNamespace(min=(float("nan"), -0.5, 0.0), max=(0.5, 0.5, 1.0)),
        "infinite": SimpleNamespace(min=(-0.5, -0.5, 0.0), max=(float("inf"), 0.5, 1.0)),
        "inverted": SimpleNamespace(min=(0.6, -0.5, 0.0), max=(0.5, 0.5, 1.0)),
        "empty": SimpleNamespace(min=(0.0, 0.0, 0.0), max=(0.0, 0.0, 0.0)),
        "flat": SimpleNamespace(min=(-0.5, -0.5, 0.0), max=(0.5, 0.5, 0.0)),
    }[invalid]
    observations = iter([invalid_bounds if index == read else bounds for index in range(5)])
    ctx.get_asset_bounds = lambda *, authored: next(observations)
    await definition.func(ctx)
    assert "assessment_advisory" not in ctx.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
async def test_invalid_origin_cannot_claim_completed_advice(monkeypatch, value):
    definition, ctx, _ = _pivot_context(monkeypatch, position=(value, 0.0, 0.5))
    await definition.func(ctx)
    assert "assessment_advisory" not in ctx.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "get_asset_bounds",
        "get_asset_position",
        "settle",
        "capture_frame",
        "reset_asset_transform",
        "encode_video",
        "skip",
    ],
)
@pytest.mark.parametrize("exception", [RuntimeError("native operation failed"), asyncio.CancelledError()])
async def test_required_error_or_interruption_never_publishes_completed_advice(monkeypatch, operation, exception):
    definition, ctx, _ = _pivot_context(monkeypatch)

    def fail(*args, **kwargs):
        raise exception

    async def fail_async(*args, **kwargs):
        raise exception

    owner = ctx.scene if operation == "reset_asset_transform" else ctx
    setattr(owner, operation, fail_async if operation in ("settle", "capture_frame") else fail)
    with pytest.raises(type(exception)):
        await definition.func(ctx)
    assert "assessment_advisory" not in ctx.metrics
    assert _result_status_and_message(ctx, test_exception=exception)[0] == "error"


@pytest.mark.asyncio
async def test_second_reset_failure_cannot_claim_completed_advice(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch)
    resets = []

    def reset():
        resets.append(True)
        if len(resets) == 2:
            raise RuntimeError("spin cleanup failed")

    ctx.scene.reset_asset_transform = reset
    with pytest.raises(RuntimeError, match="spin cleanup failed"):
        await definition.func(ctx)
    assert "assessment_advisory" not in ctx.metrics


@pytest.mark.asyncio
async def test_advice_has_no_logging_dependency_or_optional_video_requirement(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch)

    def unavailable(*args, **kwargs):
        raise RuntimeError("logging unavailable")

    ctx.log = ctx.warn = unavailable
    ctx.encode_video = lambda *args, **kwargs: None
    await definition.func(ctx)
    assert _result_status_and_message(ctx)[0] == "skipped"
    assert ctx.metrics["assessment_advisory"]["value"]["status"] == "completed"


@pytest.mark.asyncio
async def test_failed_context_does_not_publish_completed_advice(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch)
    ctx.fail("preexisting required failure")
    await definition.func(ctx)
    assert _result_status_and_message(ctx)[0] == "fail"
    assert "assessment_advisory" not in ctx.metrics


def _reported_pivot(ctx, *, behavioral_pass=False, veto=None, static_failure=False):
    """Pass actual producer metrics through the current report projection."""
    status, message = _result_status_and_message(ctx)
    cell = {"engine": "physx", "status": status, "message": message, "metrics": ctx.metrics}
    if veto == "unhealthy":
        cell["engine_unhealthy"] = "Native worker retired after unsafe cleanup"
    elif veto == "error":
        cell.update(status="error", execution_status="error", failure_category="engine_runtime")
    tests = [{"name": "pivot", "provider": "core", "version": ctx.test_version, "status": status, "engines": [cell]}]
    if behavioral_pass:
        tests.append(
            {
                "name": "presence",
                "provider": "core",
                "version": "1",
                "status": "pass",
                "engines": [{"engine": "physx", "status": "pass"}],
            }
        )
    report = {
        "metadata": {"schema_version": 5},
        "assets": {
            "asset.usda": {
                "profiles": [
                    {
                        "id": "profile",
                        "features": [
                            {
                                "id": "FET001_MinimalPlaceableVisual.1-0-1",
                                "foundations_contract": 2,
                                "source": True,
                                "status": (
                                    "validation_failed" if static_failure else "pass" if behavioral_pass else status
                                ),
                                "tests": tests,
                            }
                        ],
                    }
                ],
            },
        },
    }
    return build_view_model(report)["assets"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("behavioral_pass", [False, True])
async def test_actual_completed_producer_is_nonblocking_in_report_without_becoming_pass(monkeypatch, behavioral_pass):
    definition, ctx, _ = _pivot_context(monkeypatch)
    await definition.func(ctx)
    asset = _reported_pivot(ctx, behavioral_pass=behavioral_pass)
    cell = next(test for test in asset["features"][0]["tests"] if test["name"] == "pivot")["engines"][0]
    assert cell["status"] == "skipped"
    if "assessment" not in asset:
        # Older supported reporters retain raw skips rather than the newer
        # completed-advisory presentation. The producer contract stays identical.
        assert ctx.metrics["assessment_advisory"]["value"]["status"] == "completed"
        assert asset["verdict"] == ("pass" if behavioral_pass else "skipped")
        assert asset["has_incomplete_evidence"] is False
        return
    assert cell["assessment"]["state"] == "advisory"
    assert asset["assessment"]["advisory_count"] == 1
    assert asset["assessment"]["outcome"] == ("pass" if behavioral_pass else "no_verdict")
    assert asset["assessment"]["has_coverage_gaps"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("veto", ["unhealthy", "error"])
async def test_final_execution_failure_vetoes_actual_completed_producer_in_report(monkeypatch, veto):
    definition, ctx, _ = _pivot_context(monkeypatch)
    await definition.func(ctx)
    asset = _reported_pivot(ctx, veto=veto)
    cell = asset["features"][0]["tests"][0]["engines"][0]
    if "assessment" not in asset:
        assert cell["status"] == "incomplete"
        assert cell["execution_status"] == "error"
        assert asset["verdict"] == "incomplete"
        assert asset["has_incomplete_evidence"] is True
        return
    assert cell["assessment"]["state"] == "not_assessed"
    assert asset["assessment"]["outcome"] == "no_verdict"
    assert asset["assessment"]["has_coverage_gaps"] is True
    assert asset["assessment"]["advisory_count"] == 0


@pytest.mark.asyncio
async def test_completed_pivot_advice_cannot_discharge_recorded_static_failure(monkeypatch):
    definition, ctx, _ = _pivot_context(monkeypatch)
    await definition.func(ctx)
    asset = _reported_pivot(ctx, behavioral_pass=True, static_failure=True)
    assert asset["features"][0]["status"] == "validation_failed"
    if "assessment" not in asset:
        assert asset["verdict"] != "pass"
        assert asset["feat_validation_failed"] == 1
        return
    assert asset["assessment"]["outcome"] == "fail"
    assert any(reason["code"] == "static_validation_failed" for reason in asset["assessment"]["reasons"])

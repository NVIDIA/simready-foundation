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
"""Required semantic native attachment cleanup is not optional evidence."""

import asyncio
import importlib
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from simready.evaluate.core import decorator
from simready.evaluate.runner.test_context import RunContext
from simready.evaluate_engine_kit.execution import (
    _merge_config,
    _result_status_and_message,
)
from simready.foundation.tier_core.runtime_tests.fet011_semantics import _seg_common


def _native_boundary(monkeypatch, phase=None, primary=None, detach_error=None):
    calls = []

    class Annotator:
        def attach(self, path):
            calls.append("attach")
            if phase == "attach":
                raise primary

        def get_data(self):
            calls.append("read")
            if phase == "read":
                raise primary
            return np.zeros((2, 2, 3), dtype=np.uint8)

        def detach(self):
            calls.append("detach")
            if detach_error is not None:
                raise detach_error

    async def step(**kwargs):
        calls.append("step")
        if phase == "step":
            raise primary

    for name in ("omni", "omni.kit", "omni.kit.viewport", "omni.replicator"):
        module = ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    viewport = ModuleType("omni.kit.viewport.utility")
    viewport.get_active_viewport = lambda: SimpleNamespace(render_product_path="/test")
    monkeypatch.setitem(sys.modules, viewport.__name__, viewport)
    rep = ModuleType("omni.replicator.core")
    rep.AnnotatorRegistry = SimpleNamespace(get_annotator=lambda *a, **k: Annotator())
    rep.orchestrator = SimpleNamespace(step_async=step)
    monkeypatch.setitem(sys.modules, rep.__name__, rep)
    return calls


@pytest.mark.asyncio
async def test_required_detach_failure_is_not_a_usable_aov(monkeypatch):
    calls = _native_boundary(monkeypatch, detach_error=RuntimeError("native detach failed"))
    with pytest.raises(RuntimeError, match="Required semantic annotator cleanup failed") as caught:
        await _seg_common.read_segmentation(None, 4)
    assert calls == ["attach", "step", "read", "detach"]
    assert str(caught.value.__cause__) == "native detach failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["attach", "step", "read"])
@pytest.mark.parametrize("cancelled", [False, True])
async def test_partial_attachment_cleanup_preserves_original_error_or_cancel(monkeypatch, phase, cancelled):
    primary = asyncio.CancelledError("original cancellation") if cancelled else RuntimeError("original native failure")
    calls = _native_boundary(monkeypatch, phase, primary, RuntimeError("secondary detach failure"))
    with pytest.raises(type(primary)) as caught:
        await _seg_common.read_segmentation(None, 4)
    assert caught.value is primary and calls[0] == "attach" and calls[-1] == "detach"
    assert any("cleanup also failed" in note for note in primary.__notes__)


@pytest.mark.asyncio
async def test_successful_void_native_cleanup_returns_observed_aov(monkeypatch):
    calls = _native_boundary(monkeypatch)
    observed = await _seg_common.read_segmentation(None, 4)
    assert observed.shape == (2, 2, 3) and calls == ["attach", "step", "read", "detach"]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["seg_labelled", "seg_stripped"])
async def test_official_semantic_entry_publishes_error_after_detach_failure(monkeypatch, name):
    monkeypatch.setattr(decorator, "_REGISTRY", [])
    module = importlib.import_module("simready.foundation.tier_core.runtime_tests.fet011_semantics." + name)
    importlib.reload(module)
    definition = decorator.get_registered_tests()[-1]
    ctx = RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir="unused-output",
        test_name=definition.name,
        test_version=definition.version,
        feature_id=definition.features[0].id,
        engine_name="kit",
        engine_version="6.1.0",
        session_id="semantic-cleanup-regression",
        scene=None,
        config=_merge_config(definition.config_defaults, {}),
    )

    async def build(*args):
        return None, object()

    async def capture(*args, **kwargs):
        return "capture.png"

    monkeypatch.setattr(_seg_common, "build_scene", build)
    monkeypatch.setattr(_seg_common, "strip_semantics", lambda *args: 1)
    monkeypatch.setattr(ctx, "capture_frame", capture)
    _native_boundary(monkeypatch, detach_error=RuntimeError("native detach failed"))
    with pytest.raises(RuntimeError, match="Required semantic annotator cleanup failed") as caught:
        await definition.func(ctx)
    assert not ctx.failed and _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"


@pytest.mark.asyncio
async def test_failed_native_detach_latches_actual_adapter_worker_retirement(monkeypatch, tmp_path):
    from simready.evaluate_engine_kit.kit_engine_proxy import KitEngineProxy

    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)
    monkeypatch.setattr(KitEngineProxy, "_apply_enforced_render_settings", lambda self: None)
    proxy = KitEngineProxy(str(tmp_path))
    ctx = SimpleNamespace(_engine_session=proxy)
    _native_boundary(monkeypatch, detach_error=RuntimeError("native detach failed"))
    with pytest.raises(RuntimeError, match="Required semantic annotator cleanup failed"):
        await _seg_common.read_segmentation(ctx, 4)
    assert proxy.required_cleanup_failures == ["Required semantic-segmentation annotator cleanup failed."]
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.asyncio
async def test_failed_cleanup_health_callback_cannot_replace_original_native_failure(monkeypatch):
    primary = RuntimeError("original native observation failed")

    def retirement(reason):
        raise KeyboardInterrupt("health callback interrupted")

    ctx = SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=retirement))
    _native_boundary(monkeypatch, "read", primary, RuntimeError("native detach failed"))
    with pytest.raises(RuntimeError) as caught:
        await _seg_common.read_segmentation(ctx, 4)
    assert caught.value is primary
    assert any("health reporting also failed" in note for note in primary.__notes__)

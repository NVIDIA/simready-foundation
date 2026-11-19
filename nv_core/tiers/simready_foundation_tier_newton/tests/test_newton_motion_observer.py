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

import sys
from types import ModuleType, SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.motion_observer import (
    MotionObserver,
    drop_metadata,
)


class History:
    def __init__(self):
        self.samples = []
        self.captures = []
        self.limitations = []
        self.reason = None

    def sample(self, time_s, values, **kwargs):
        self.samples.append((time_s, values, kwargs))

    def mark_partial(self, reason):
        self.limitations.append(reason)

    def finish(self, reason):
        self.reason = reason

    def record_capture(self, time_s):
        if self.captures and time_s <= self.captures[-1]:
            raise ValueError("capture associations must increase")
        self.captures.append(time_s)


class Context:
    def __init__(self):
        self.history = History()
        self.warnings = []

    def begin_motion_history(self, *args, **kwargs):
        return self.history

    def warn(self, message):
        self.warnings.append(message)


def test_legacy_runner_has_no_observation_side_effects():
    observer = MotionObserver(SimpleNamespace(), "trial", {})
    observer.sample({"position": 1}, 0)
    observer.finish("done")
    assert observer.history is None


def test_nominal_samples_are_labelled_estimated_and_missing_values_preserved():
    ctx = Context()
    observer = MotionObserver(ctx, "trial", {})
    observer.sample({"position": None}, 0, "open")
    observer.sample({"position": 0.1}, 0.1, "close")
    observer.finish("done")
    assert ctx.history.samples[0][1]["position"] is None
    assert ctx.history.samples[0][2]["clock_source"] == "estimated"
    assert ctx.history.reason == "done"
    assert not ctx.warnings


def test_clock_gap_is_visible_but_preserves_stop_reason():
    ctx = Context()
    observer = MotionObserver(ctx, "trial", {})
    observer.sample({"position": 1}, 0)
    observer.sample({"position": 2}, 0)
    observer.finish("velocity_stop_condition")
    assert len(ctx.history.samples) == 1
    assert ctx.history.limitations
    assert ctx.history.reason == "velocity_stop_condition"
    assert len(ctx.warnings) == 1


def test_sampling_stride_keeps_phase_transition():
    ctx = Context()
    observer = MotionObserver(ctx, "trial", {}, sample_stride=4)
    for index in range(6):
        observer.sample({}, index, "open" if index < 3 else "close")
    assert [row[0] for row in ctx.history.samples] == [0, 3, 4]


def test_nonfinite_retained_measurement_is_nullable_and_partial():
    ctx = Context()
    observer = MotionObserver(ctx, "trial", {})
    observer.sample({"position": float("nan"), "target": 1.0}, 0)
    observer.finish("window_completed")
    assert ctx.history.samples[0][1] == {"position": None, "target": 1.0}
    assert ctx.history.limitations and len(ctx.warnings) == 1
    assert ctx.history.reason == "window_completed"


@pytest.mark.parametrize("real_recorder", [False, True])
def test_capture_associations_coalesce_at_240_step_30_capture_cadence(real_recorder):
    history = History()
    if real_recorder:
        # Recording is optional: older supported runners need not ship this API.
        module = pytest.importorskip("simready.evaluate.runner.motion_evidence")
        history = module.MotionEvidence("trial", {"position": {"unit": "rad", "source": "readback"}})
    warnings = []
    ctx = SimpleNamespace(begin_motion_history=lambda *args, **kwargs: history, warn=warnings.append)
    observer = MotionObserver(ctx, "trial", {})
    for step in range(41):
        if step % 10 == 0:
            observer.sample({"position": float(step)}, (step + 1) / 240.0)
        if step % 8 == 0:
            observer.record_capture("frame.png")
    observer.finish("window_completed")
    assert len(history.captures) == 5
    assert not history.limitations
    assert not warnings


def _drop_context(monkeypatch, stage):
    """Replace only Kit's context seam; collider discovery uses a real USD stage."""
    omni = ModuleType("omni")
    omni.__path__ = []
    usd = ModuleType("omni.usd")
    usd.get_context = lambda: SimpleNamespace(get_stage=lambda: stage)
    omni.usd = usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    ctx = Context()
    ctx.get_asset_bounds = lambda: SimpleNamespace(min=(0.0, 0.0, 0.0), max=(1.0, 1.0, 1.0))
    return ctx


def test_drop_metadata_includes_root_and_excludes_non_asset_colliders(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    for path in (
        "/World/AssetRoot",
        "/World/AssetRoot/Child",
        "/World/AssetRootOther",
        "/World/Room/Collider",
    ):
        UsdPhysics.CollisionAPI.Apply(UsdGeom.Cube.Define(stage, path).GetPrim())
    ctx = _drop_context(monkeypatch, stage)

    info = drop_metadata(ctx, 240, 15)

    assert [collider["prim_path"] for collider in info["authored_colliders"]] == [
        "/World/AssetRoot",
        "/World/AssetRoot/Child",
    ]
    assert info["authored_collider_count"] == 2
    assert info["collider_context_omitted"] == 0
    assert not info.get("context_partial")
    assert not ctx.warnings


@pytest.mark.parametrize("instance_on_root", [False, True])
def test_drop_metadata_includes_instanced_collider_proxies(monkeypatch, instance_on_root):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Prototype")
    UsdPhysics.CollisionAPI.Apply(UsdGeom.Cube.Define(stage, "/Prototype/Collider").GetPrim())
    root = UsdGeom.Xform.Define(stage, "/World/AssetRoot").GetPrim()
    instance = root if instance_on_root else UsdGeom.Xform.Define(stage, "/World/AssetRoot/Instance").GetPrim()
    instance.GetReferences().AddInternalReference("/Prototype")
    instance.SetInstanceable(True)
    proxy_path = str(instance.GetPath()) + "/Collider"
    proxy = stage.GetPrimAtPath(proxy_path)
    assert proxy.IsInstanceProxy() and proxy.HasAPI(UsdPhysics.CollisionAPI)
    ctx = _drop_context(monkeypatch, stage)

    info = drop_metadata(ctx, 240, 15)

    assert [collider["prim_path"] for collider in info["authored_colliders"]] == [proxy_path]
    assert info["authored_collider_count"] == 1
    assert info["collider_context_omitted"] == 0
    assert not info.get("context_partial")
    assert not ctx.warnings


def test_drop_metadata_preserves_eight_collider_cap_and_counts_omissions(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World/AssetRoot")
    for index in range(12):
        path = f"/World/AssetRoot/Collider{index:02d}"
        UsdPhysics.CollisionAPI.Apply(UsdGeom.Cube.Define(stage, path).GetPrim())
    ctx = _drop_context(monkeypatch, stage)

    info = drop_metadata(ctx, 240, 15)

    assert len(info["authored_colliders"]) == 8
    assert info["authored_collider_count"] == 12
    assert info["collider_context_omitted"] == 4
    assert not info.get("context_partial")
    assert not ctx.warnings


def test_drop_metadata_missing_asset_subtree_marks_context_partial(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    ctx = _drop_context(monkeypatch, stage)

    info = drop_metadata(ctx, 240, 15)

    assert info["context_partial"]
    assert "authored_collider_count" not in info
    assert len(ctx.warnings) == 1


def test_drop_metadata_legacy_runner_needs_no_kit_context():
    assert drop_metadata(SimpleNamespace(), 240, 15) == {}

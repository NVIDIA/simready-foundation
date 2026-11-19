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

"""Check official procedure verdicts and probe cleanup without native Kit claims."""

import asyncio
from types import SimpleNamespace

import pytest
from pxr import Gf, Usd, UsdGeom
from simready.foundation.tier_core.runtime_tests.fet008_object_forward import camera_response, contract


class Context:
    def __init__(self, path):
        self.asset_path = str(path)
        self.config = {"asset_load_timeout": 30, "camera_distance": 3.0, "pose_tolerance": 1e-5}
        self.failures, self.metrics, self.captures = [], {}, []
        self.scene = self

    def load_asset(self, path, timeout):
        self.stage = Usd.Stage.Open(path)
        self.asset = SimpleNamespace(prim_path=str(self.stage.GetDefaultPrim().GetPath()))

    def fail(self, message):
        self.failures.append(message)

    def add_metric(self, name, value):
        self.metrics[name] = value

    def auto_frame_camera(self):
        pass

    async def settle(self, count):
        pass

    async def capture_frame(self, **kwargs):
        self.captures.append(kwargs)


@pytest.fixture
def sample(tmp_path):
    from simready.foundation.tier_core.asset_frame import author_forward_direction

    path = tmp_path / "facing.usda"
    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    author_forward_direction(root, (1, 0, 0))
    stage.GetRootLayer().Save()
    return path


def test_camera_response_records_two_poses_and_cleans_probes(sample):
    ctx = Context(sample)
    asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert not ctx.failures
    assert len(ctx.captures) == 2
    assert ctx.captures[0]["camera"] != ctx.captures[1]["camera"]
    assert len(ctx.metrics) == 4
    assert max(ctx.metrics.values()) < 1e-5
    assert not ctx.stage.GetPrimAtPath("/SimReadyForwardProbe")
    assert ctx.stage.GetSessionLayer().empty


def test_camera_canary_rejects_fixed_pose_and_cleans_up(sample, monkeypatch):
    monkeypatch.setattr(camera_response, "facing_camera_transform", lambda *args: Gf.Matrix4d(1))
    ctx = Context(sample)
    asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert ctx.failures
    assert not ctx.stage.GetPrimAtPath("/SimReadyForwardProbe")


def test_camera_canary_cleans_up_on_capture_failure(sample):
    ctx = Context(sample)

    async def broken_capture(**kwargs):
        raise RuntimeError("capture failed")

    ctx.capture_frame = broken_capture
    with pytest.raises(RuntimeError, match="capture failed"):
        asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert not ctx.stage.GetPrimAtPath("/SimReadyForwardProbe")


@pytest.mark.parametrize("error_type", [ValueError, OSError, asyncio.CancelledError])
def test_required_camera_capture_errors_never_become_asset_failures(sample, error_type):
    ctx = Context(sample)

    async def broken_capture(**kwargs):
        raise error_type("required capture failed")

    ctx.capture_frame = broken_capture
    with pytest.raises(error_type, match="required capture failed"):
        asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert not ctx.failures
    assert not ctx.stage.GetPrimAtPath("/SimReadyForwardProbe")


@pytest.mark.parametrize("position_error,view_error", [(float("nan"), 0), (0, float("inf"))])
def test_nonfinite_required_camera_pose_is_error_not_asset_failure(sample, monkeypatch, position_error, view_error):
    monkeypatch.setattr(camera_response, "pose_error", lambda *args: (position_error, view_error))
    ctx = Context(sample)
    with pytest.raises(RuntimeError, match="pose measurement is nonfinite"):
        asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert not ctx.failures and ctx.stage.GetSessionLayer().empty


@pytest.mark.parametrize("primary", [False, True])
def test_rejected_required_probe_cleanup_is_error_and_retirement_receipt(sample, monkeypatch, primary):
    ctx = Context(sample)
    receipts = []
    ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=receipts.append)
    original = Usd.Stage.RemovePrim

    def rejected(stage, path):
        if str(path).startswith("/SimReadyForwardProbe"):
            return False
        return original(stage, path)

    monkeypatch.setattr(Usd.Stage, "RemovePrim", rejected)
    if primary:

        async def broken_capture(**kwargs):
            raise ValueError("original capture failure")

        ctx.capture_frame = broken_capture
    with pytest.raises(
        ValueError if primary else RuntimeError,
        match="original capture failure" if primary else "cleanup was not acknowledged",
    ) as caught:
        asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert receipts == ["Required object-forward probe cleanup failed."]
    assert not ctx.failures
    if primary:
        assert any("cleanup also failed" in note for note in caught.value.__notes__)


@pytest.mark.parametrize(
    "key,value", [("camera_distance", True), ("pose_tolerance", float("nan")), ("asset_load_timeout", 0)]
)
def test_invalid_camera_configuration_rejected_before_scene_load(key, value):
    ctx = Context("not-loaded.usda")
    ctx.config[key] = value
    with pytest.raises(RuntimeError, match="Invalid visual measurement configuration"):
        asyncio.run(camera_response.test_object_forward_camera_response(ctx))
    assert not hasattr(ctx, "stage") and not ctx.failures


def test_runtime_contract_records_authored_facing(sample):
    ctx = Context(sample)
    asyncio.run(contract.test_object_forward_contract(ctx))
    assert not ctx.failures
    assert ctx.metrics["object_forward_local_vectors"] == {"/Asset": [1, 0, 0]}


def test_runtime_contract_rejects_missing_facing(tmp_path):
    path = tmp_path / "bad.usda"
    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    stage.GetRootLayer().Save()
    ctx = Context(path)
    asyncio.run(contract.test_object_forward_contract(ctx))
    assert ctx.failures
    assert not ctx.captures

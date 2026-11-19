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
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pxr import Usd, UsdGeom


@pytest.fixture
def production_scene(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset/Body")
    carb = ModuleType("carb")
    omni = ModuleType("omni")
    omni.kit = ModuleType("omni.kit")
    omni.kit.app = ModuleType("omni.kit.app")
    omni.usd = ModuleType("omni.usd")
    omni.usd.get_context = lambda: SimpleNamespace(get_stage=lambda: stage)
    omni.physx = ModuleType("omni.physx")
    omni.physx.get_physx_scene_query_interface = lambda: None
    isaac = ModuleType("isaacsim")
    isaac.core = ModuleType("isaacsim.core")
    isaac.core.utils = ModuleType("isaacsim.core.utils")
    isaac.core.utils.stage = ModuleType("isaacsim.core.utils.stage")

    async def update_stage_async():
        pass

    isaac.core.utils.stage.update_stage_async = update_stage_async
    robot_module = ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_robot")
    robot_module.GraspRobot = SimpleNamespace()
    for module in (
        carb,
        omni,
        omni.kit,
        omni.kit.app,
        omni.usd,
        omni.physx,
        isaac,
        isaac.core,
        isaac.core.utils,
        isaac.core.utils.stage,
        robot_module,
    ):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    path = Path(__file__).resolve().parents[3] / "simready/foundation/tier_core/runtime_tests/fet005_grasp/grasp_scene.py"
    spec = importlib.util.spec_from_file_location("_fet005_terminal_media_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harness(module, monkeypatch, *, operation, error, error_frame=0, verdict_frame=0, failed=True, warning_error=None):
    class Context:
        def __init__(self):
            self.frame = -1
            self.ticks = 0
            self.advances = 0
            self.warnings = []
            self.metrics = {}
            self.cameras = []
            self.captures = []
            self.videos = []
            self.scene = SimpleNamespace(update_camera_follow=self.camera)

        async def physics_step(self):
            self.frame += 1
            self.ticks += 1

        async def physics_advance(self):
            self.advances += 1

        def camera(self, **_kwargs):
            self.cameras.append(self.frame)
            if operation == "camera follow" and self.frame == error_frame:
                raise error

        async def capture_frame(self, **_kwargs):
            self.captures.append(self.frame)
            if operation == "frame capture" and self.frame == error_frame:
                raise error
            return "frame_%d.png" % self.frame

        def encode_video(self, frames, **kwargs):
            self.videos.append((list(frames), kwargs))

        def warn(self, message):
            self.warnings.append(message)
            if warning_error is not None:
                raise warning_error

        def add_metric(self, name, value):
            self.metrics[name] = value

        def log(self, _message):
            pass

        step = log

    class Tracker:
        def record_frame(self, _prim, _time):
            pass

    phase_calls = []
    measured_result = {
        "phase_name": "Lifting" if failed else "GraspAndLift",
        "message": "Measured object did not lift" if failed else "All phases completed",
        "failed": failed,
    }

    def check_frame(frame, _time, _scene, _tracker):
        phase_calls.append(frame)
        return measured_result if frame == verdict_frame else None

    phases = SimpleNamespace(
        tracking_active=False,
        stability_complete=False,
        capture_active=True,
        check_frame=check_frame,
    )
    monkeypatch.setattr(module, "AssetPoseTracker", lambda _fps: Tracker())
    monkeypatch.setattr(module, "GraspPhaseManager", lambda _cfg: phases)
    ctx = Context()
    scene = module.GraspScene(ctx, "/Asset/Body/grasp_identifier_1", "/Asset")
    scene._parent_body_path = "/Asset/Body"
    return scene, ctx, measured_result, phase_calls


CONFIG = {
    "physics_fps": 10,
    "capture_fps": 10,
    "simulation_seconds": 0.3,
    "post_failure_observation_seconds": 0.2,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera follow", "frame capture"])
@pytest.mark.parametrize("error_frame", [0, 1])
@pytest.mark.parametrize("error", [RuntimeError("native media unavailable"), OSError("renderer unavailable")])
async def test_terminal_media_failure_preserves_measured_verdict_and_bounds_tail(
    production_scene, monkeypatch, operation, error_frame, error
):
    scene, ctx, measured, phase_calls = harness(
        production_scene, monkeypatch, operation=operation, error=error, error_frame=error_frame
    )

    result = await scene.run_simulation(CONFIG, "id")

    assert result is measured
    assert result["failed"] is True
    assert result["message"] == "Measured object did not lift"
    assert result["failure_media_limited"] is True
    assert operation in result["failure_media_limitation"]
    assert type(error).__name__ in result["failure_media_limitation"]
    assert result["post_failure_observation_seconds"] == error_frame / 10.0
    assert ctx.ticks == error_frame + 1
    assert ctx.advances == error_frame
    assert phase_calls == [0]
    assert len(ctx.warnings) == 1
    if error_frame:
        assert ctx.videos[0][0] == ["frame_0.png"]
    else:
        assert ctx.videos == []


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera follow", "frame capture"])
async def test_terminal_media_warning_sink_cannot_replace_original_result(production_scene, monkeypatch, operation):
    scene, ctx, measured, _calls = harness(
        production_scene,
        monkeypatch,
        operation=operation,
        error=OSError("private-host-path" * 5000),
        warning_error=RuntimeError("warning sink unavailable"),
    )

    result = await scene.run_simulation(CONFIG, "id")

    assert result is measured and result["failed"] is True
    assert len(result["failure_media_limitation"]) < 150
    assert "private-host-path" not in result["failure_media_limitation"]
    assert len(ctx.warnings) <= 2


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera follow", "frame capture"])
@pytest.mark.parametrize("failed", [False, True])
async def test_media_failure_without_latched_failed_verdict_preserves_execution_policy(
    production_scene, monkeypatch, operation, failed
):
    error = OSError("original media error")
    scene, _ctx, _measured, _calls = harness(
        production_scene,
        monkeypatch,
        operation=operation,
        error=error,
        verdict_frame=2 if failed else 0,
        failed=failed,
    )
    with pytest.raises(OSError) as captured:
        await scene.run_simulation(CONFIG, "id")
    assert captured.value is error


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera follow", "frame capture"])
@pytest.mark.parametrize("error", [asyncio.CancelledError(), KeyboardInterrupt(), SystemExit(2)])
async def test_terminal_media_cancellation_or_interrupt_is_never_swallowed(
    production_scene, monkeypatch, operation, error
):
    scene, ctx, measured, _calls = harness(production_scene, monkeypatch, operation=operation, error=error)
    with pytest.raises(type(error)) as captured:
        await scene.run_simulation(CONFIG, "id")
    assert captured.value is error
    assert "failure_media_limited" not in measured
    assert ctx.advances == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["camera follow", "frame capture"])
async def test_usable_terminal_media_keeps_existing_observation_work(production_scene, monkeypatch, operation):
    scene, ctx, measured, phase_calls = harness(
        production_scene, monkeypatch, operation=operation, error=RuntimeError("not reached"), error_frame=99
    )

    result = await scene.run_simulation(CONFIG, "id")

    assert result is measured
    assert result["post_failure_observation_seconds"] == 0.2
    assert "failure_media_limited" not in result
    assert ctx.ticks == ctx.advances == 3
    assert phase_calls == [0]
    assert ctx.videos[0][0] == ["frame_0.png", "frame_1.png", "frame_2.png"]

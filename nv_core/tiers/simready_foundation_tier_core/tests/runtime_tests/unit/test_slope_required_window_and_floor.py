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
"""Official slope-loop and USD fixture regressions; no native contact qualification."""

from types import SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
from simready.evaluate.runner.test_context import RunContext
from simready.evaluate_engine_kit.execution import _result_status_and_message
from simready.foundation.tier_core.runtime_tests.fet003_physics import slope_drop as phase


def _context(tmp_path):
    return RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir=str(tmp_path),
        test_name="slope_drop",
        test_version="3.3.6",
        feature_id="FET003",
        engine_name="kit",
        engine_version="6.1.0",
        session_id="slope-window-regression",
        scene=SimpleNamespace(update_camera_follow=lambda: None),
        config={"capture_fps": 15},
    )


async def _observations(ctx, positions, *, post_frames, floor_violation=False):
    positions = iter(positions)
    count = 0

    async def step():
        nonlocal count
        count += 1

    async def noop(*_args, **_kwargs):
        return None

    def bounds():
        y = next(positions)
        z = -0.2 if floor_violation and count == 3 else 0.0
        return SimpleNamespace(min=(-0.01, y - 0.01, z), max=(0.01, y + 0.01, z + 0.02))

    ctx.physics_step = step
    ctx.physics_advance = noop
    ctx.capture_frame = noop
    ctx.get_asset_bounds = bounds
    config = {
        "total_frames": 3,
        "physics_fps": 240,
        "capture_interval": 16,
        "pen_threshold": -0.1,
        "horiz_threshold": 0.01,
        "post_horiz_frames": post_frames,
        "separation_confirmation_frames": 24,
        "slope_min_y": -10,
        "slope_max_y": 10,
        "slope_center_z": 0.0,
        "slope_tangent": 1.0,
        "contact_tolerance": 0.02,
        "slope_penetration_tolerance": 0.02,
        "max_slope_separation": 0.05,
    }
    _frames, state = await phase._run_simulation(ctx, config)
    return count, state


@pytest.mark.asyncio
@pytest.mark.parametrize("post_frames", [1, 720])
async def test_late_downhill_travel_without_required_tail_is_error_not_pass(tmp_path, post_frames):
    ctx = _context(tmp_path)
    count, state = await _observations(ctx, [0.0, 0.0, 0.1], post_frames=post_frames)
    with pytest.raises(RuntimeError, match="observation incomplete") as raised:
        phase._report_result(ctx, state, 240, 3 / 240)
    status, message = _result_status_and_message(ctx, test_exception=raised.value)
    assert status == "error" and "not an asset-response failure" in message
    assert not ctx.failed and count == 3
    assert state["post_slide_observed_frames"] == 0
    assert state["post_slide_required_frames"] == post_frames
    assert not state["post_slide_completed"]
    assert ctx.metrics["slope_drop_passed"]["value"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("positions", "post_frames", "expected_steps"),
    [
        ([0.0, 0.1, 0.1], 1, 3),
        ([0.0, 0.0, 0.1], 0, 3),
        ([0.0, 0.1, 0.1], 0, 2),
    ],
)
async def test_complete_tail_and_explicit_zero_window_keep_existing_pass(
    tmp_path, positions, post_frames, expected_steps
):
    ctx = _context(tmp_path)
    count, state = await _observations(ctx, positions, post_frames=post_frames)
    phase._report_result(ctx, state, 240, 3 / 240)
    assert _result_status_and_message(ctx)[0] == "pass"
    assert count == expected_steps
    assert state["post_slide_completed"]
    assert state["post_slide_observed_frames"] == post_frames


@pytest.mark.asyncio
async def test_measured_overlap_failure_is_not_hidden_by_incomplete_tail(tmp_path):
    ctx = _context(tmp_path)
    _count, state = await _observations(ctx, [0.0, 0.1, 0.1], post_frames=720, floor_violation=True)
    assert not state["post_slide_completed"]
    phase._report_result(ctx, state, 240, 3 / 240)
    status, message = _result_status_and_message(ctx)
    assert status == "fail"
    assert "Bounding-box floor overlap" in message or "entire bounding box fell below" in message


def _floor_stage(monkeypatch):
    import sys

    stage = Usd.Stage.CreateInMemory()
    mesh = UsdGeom.Cube.Define(stage, "/World/GroundPlane/CollisionMesh").GetPrim()
    UsdPhysics.CollisionAPI.Apply(mesh).CreateCollisionEnabledAttr(True)
    usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
    monkeypatch.setitem(sys.modules, "omni", SimpleNamespace(usd=usd))
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    return stage, mesh


def test_official_slope_floor_has_typed_material_and_effective_coefficients(monkeypatch):
    stage, mesh = _floor_stage(monkeypatch)
    phase._apply_ground_friction()
    material, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial(materialPurpose="physics")
    assert material.GetPath() == stage.GetPrimAtPath("/World/GroundPlane/PhysMaterial").GetPath()
    assert material.GetPrim().IsA(UsdShade.Material)
    physics = UsdPhysics.MaterialAPI(material.GetPrim())
    assert physics.GetStaticFrictionAttr().Get() == pytest.approx(0.5)
    assert physics.GetDynamicFrictionAttr().Get() == pytest.approx(0.4)
    assert physics.GetRestitutionAttr().Get() == 0.0


@pytest.mark.parametrize(
    "fault",
    [
        "collision_disabled",
        "collision_missing",
        "coefficient_rejected",
        "coefficient_wrong",
        "binding_rejected",
        "binding_ineffective",
    ],
)
def test_required_floor_setup_failure_is_never_silently_accepted(monkeypatch, tmp_path, fault):
    stage, mesh = _floor_stage(monkeypatch)
    if fault == "collision_disabled":
        UsdPhysics.CollisionAPI(mesh).GetCollisionEnabledAttr().Set(False)
    elif fault == "collision_missing":
        stage.RemovePrim(mesh.GetPath())
    elif fault == "coefficient_rejected":
        monkeypatch.setattr(Usd.Attribute, "Set", lambda *_args, **_kwargs: False)
    elif fault == "coefficient_wrong":
        original = Usd.Attribute.Get
        monkeypatch.setattr(
            Usd.Attribute,
            "Get",
            lambda attr, *args: (0.75 if attr.GetName() == "physics:staticFriction" else original(attr, *args)),
        )
    else:
        monkeypatch.setattr(UsdShade.MaterialBindingAPI, "Bind", lambda *_args, **_kwargs: fault != "binding_rejected")
    with pytest.raises(RuntimeError) as raised:
        phase._apply_ground_friction()
    ctx = _context(tmp_path)
    assert _result_status_and_message(ctx, test_exception=raised.value)[0] == "error"
    assert not ctx.failed

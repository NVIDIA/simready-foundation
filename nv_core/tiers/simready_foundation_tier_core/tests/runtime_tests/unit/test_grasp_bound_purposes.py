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

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.evaluate_engine_kit import physics_utils
from simready.evaluate_engine_kit.fabric_utils import LiveBoundsReadError
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_utils import AssetPoseTracker


@pytest.mark.parametrize("purpose", ["default", "render", "proxy"])
def test_physx_tracker_observes_supported_body_purposes(monkeypatch, purpose):
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "physx")
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/Body").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    cube = UsdGeom.Cube.Define(stage, "/Body/Cube")
    cube.CreateSizeAttr(2.0)
    cube.CreatePurposeAttr(purpose)
    tracker = AssetPoseTracker(240)
    tracker.record_frame(body, 0.0)
    assert tracker.center_history == [(0.0, 0.0, 0.0)]
    assert tracker.min_z_history == [-1.0]
    assert tracker.pose_source == "usd"


def test_guide_only_body_cannot_manufacture_observed_geometry(monkeypatch):
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "physx")
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/Body").GetPrim()
    cube = UsdGeom.Cube.Define(stage, "/Body/Guide")
    cube.CreatePurposeAttr("guide")
    tracker = AssetPoseTracker(240)
    with pytest.raises(LiveBoundsReadError, match="empty"):
        tracker.record_frame(body, 0.0)
    assert not tracker.center_history
    assert not tracker.times

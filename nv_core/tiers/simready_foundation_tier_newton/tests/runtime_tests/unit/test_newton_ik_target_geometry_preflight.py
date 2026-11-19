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
"""IK target generation requires measured asset geometry and a measured base."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    ik_target_reach as phase,
)


def _robot_stage(translation=(2.0, 3.0, 4.0)):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot")
    root.AddTranslateOp().Set(Gf.Vec3d(*translation))
    return stage, SimpleNamespace(prim_path="/Robot")


def test_base_position_requires_finite_loaded_robot_root():
    stage, robot = _robot_stage()
    assert np.allclose(phase._get_robot_base_position(robot, {"stage": stage}), [2.0, 3.0, 4.0])

    with pytest.raises(phase.RequiredReadbackError, match="robot base"):
        phase._get_robot_base_position(robot, {"stage": None})
    with pytest.raises(phase.RequiredReadbackError, match="robot base"):
        phase._get_robot_base_position(SimpleNamespace(prim_path="/Missing"), {"stage": stage})

    nonfinite_stage, nonfinite_robot = _robot_stage((float("nan"), 0.0, 0.0))
    with pytest.raises(phase.RequiredReadbackError, match="robot base"):
        phase._get_robot_base_position(nonfinite_robot, {"stage": nonfinite_stage})


@pytest.mark.parametrize(
    "empty,size", [(True, (1.0, 1.0, 1.0)), (False, (0.0, 0.0, 1.0)), (False, (float("nan"), 1.0, 1.0))]
)
def test_reach_rejects_unmeasured_geometry(monkeypatch, empty, size):
    box = SimpleNamespace(IsEmpty=lambda: empty, GetSize=lambda: size)
    bounds = SimpleNamespace(ComputeAlignedBox=lambda: box)
    cache = SimpleNamespace(ComputeWorldBound=lambda prim: bounds)
    monkeypatch.setattr(UsdGeom, "BBoxCache", lambda *args, **kwargs: cache)
    asset = SimpleNamespace(IsValid=lambda: True)
    with pytest.raises(phase.RequiredReadbackError, match="robot reach"):
        phase._compute_robot_reach({"asset_prim": asset})


def test_reach_requires_asset_and_preserves_qualified_clamp(monkeypatch):
    with pytest.raises(phase.RequiredReadbackError, match="robot reach"):
        phase._compute_robot_reach({"asset_prim": None})

    box = SimpleNamespace(IsEmpty=lambda: False, GetSize=lambda: (0.01, 0.0, 1.0))
    bounds = SimpleNamespace(ComputeAlignedBox=lambda: box)
    cache = SimpleNamespace(ComputeWorldBound=lambda prim: bounds)
    monkeypatch.setattr(UsdGeom, "BBoxCache", lambda *args, **kwargs: cache)
    assert phase._compute_robot_reach({"asset_prim": SimpleNamespace(IsValid=lambda: True)}) == 0.1


def test_phase_propagates_missing_reach_as_execution_error(monkeypatch):
    stage, robot = _robot_stage()
    ctx = SimpleNamespace(
        asset_validated_features=None,
        asset_path="asset.usd",
        step=lambda message: None,
        log=lambda message: None,
        add_metric=lambda name, value: None,
        fail=lambda message: pytest.fail("missing reach was misclassified as asset failure"),
        skip=lambda message: pytest.fail("missing reach was misclassified as not applicable"),
    )
    monkeypatch.setattr(phase, "is_standalone_gripper", lambda *args, **kwargs: False)
    monkeypatch.setattr(phase, "_try_build_ik_solver", lambda *args: (object(), "tip", "robot"))
    monkeypatch.setattr(phase, "_lula_controlled_robot", lambda robot, art_ik, scene_info: robot)
    monkeypatch.setattr(phase, "_get_ee_position", lambda art_ik, ctx: np.zeros(3))

    async def no_settle(*args, **kwargs):
        return None

    monkeypatch.setattr(phase, "settle_nominal", no_settle)
    with pytest.raises(phase.RequiredReadbackError, match="robot reach"):
        asyncio.run(phase.run_ik_target_reach(ctx, robot, {"stage": stage, "asset_prim": None}, phase.get_defaults()))

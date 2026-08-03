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
"""Tests for articulation_phases.motion_utils."""
import math

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.articulation_phases.motion_utils import (
    get_dof_property,
    get_limits,
    merge_velocity_limits,
    resolve_usd_max_velocities,
)

try:
    from pxr import PhysxSchema  # noqa: F401

    _HAS_PHYSX_SCHEMA = True
except ImportError:
    _HAS_PHYSX_SCHEMA = False


def test_get_dof_property_returns_none_for_missing():
    assert get_dof_property(None, "lower") is None


def test_get_dof_property_returns_array_from_list_of_dicts():
    props = [{"lower": -1.0, "upper": 1.0}, {"lower": -2.0, "upper": 2.0}]
    out = get_dof_property(props, "lower")
    assert out is not None
    assert list(out) == [-1.0, -2.0]


def test_get_limits_returns_tuple():
    lowers = np.array([-1.0, -2.0])
    uppers = np.array([1.0, 2.0])
    assert get_limits(lowers, uppers, 0) == (-1.0, 1.0)
    assert get_limits(lowers, uppers, 1) == (-2.0, 2.0)


def test_get_limits_returns_none_for_missing_array():
    assert get_limits(None, None, 0) == (None, None)


def test_get_limits_out_of_range_returns_none():
    lowers = np.array([-1.0])
    uppers = np.array([1.0])
    assert get_limits(lowers, uppers, 5) == (None, None)


def test_merge_velocity_limits_prefers_min():
    dof = np.array([10.0, 20.0, float("nan")])
    usd = np.array([5.0, float("nan"), 15.0])
    merged = merge_velocity_limits(dof, usd, use_min_when_both=True)
    assert merged is not None
    assert merged[0] == 5.0
    assert merged[1] == 20.0
    assert merged[2] == 15.0


def test_merge_velocity_limits_returns_none_when_both_none():
    assert merge_velocity_limits(None, None) is None


def test_merge_velocity_limits_returns_dof_when_usd_none():
    dof = np.array([10.0, 20.0])
    merged = merge_velocity_limits(dof, None)
    assert merged is not None
    assert list(merged) == [10.0, 20.0]


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_resolve_usd_max_velocities_reads_physx_joint_api():
    from pxr import PhysxSchema

    stage = Usd.Stage.CreateInMemory()
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/World/joints/shoulder_joint")
    physx_api = PhysxSchema.PhysxJointAPI.Apply(joint.GetPrim())
    physx_api.CreateMaxJointVelocityAttr(1.5)

    asset_prim = UsdGeom.Xform.Define(stage, "/World").GetPrim()

    out = resolve_usd_max_velocities(
        stage=stage,
        robot_prim_path="/World",
        dof_names=["shoulder_joint"],
        asset_prim=asset_prim,
        robot_root_prim=asset_prim,
    )
    assert out is not None
    assert abs(out[0] - 1.5) < 1e-6


def test_resolve_usd_max_velocities_returns_nan_without_authored_limits():
    stage = Usd.Stage.CreateInMemory()
    UsdPhysics.RevoluteJoint.Define(stage, "/World/joint_a")
    asset_prim = UsdGeom.Xform.Define(stage, "/World").GetPrim()

    out = resolve_usd_max_velocities(
        stage=stage,
        robot_prim_path="/World",
        dof_names=["joint_a"],
        asset_prim=asset_prim,
        robot_root_prim=asset_prim,
    )
    if out is not None:
        assert all(not math.isfinite(float(v)) for v in out)

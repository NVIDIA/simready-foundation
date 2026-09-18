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
"""Tests for articulation_phases.gripper_sites."""
import math

import numpy as np
from pxr import Sdf, Usd, UsdGeom
from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
    GripperSite,
    discover_gripper_sites,
)
from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
    _has_gripper_signals,
)


def test_gripper_site_dataclass_round_trips():
    site = GripperSite(
        prim_path="/World/Asset/gripper_01",
        pose_world_initial=np.eye(4),
        forward_axis_world=np.array([0.0, 1.0, 0.0]),
        grip_line_world=(np.array([-0.04, 0.0, 0.0]), np.array([0.04, 0.0, 0.0])),
        max_opening=0.085,
        max_payload=5.0,
    )
    assert site.prim_path == "/World/Asset/gripper_01"
    assert site.max_opening == 0.085
    assert site.max_payload == 5.0


def _stage_with_asset():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset_prim = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    return stage, asset_prim


def _add_basis_curves(stage, parent_path, name, p0, p1):
    path = "%s/%s" % (parent_path, name)
    curves = UsdGeom.BasisCurves.Define(stage, path)
    curves.CreatePointsAttr().Set([p0, p1])
    curves.CreateCurveVertexCountsAttr().Set([2])
    curves.CreateTypeAttr().Set("linear")
    return curves


def _add_gripper_site(
    stage,
    parent_path,
    name="gripper_01",
    apply_isaac_site_api=True,
    forward_axis=((0.0, -0.15, 0.0), (0.0, 0.15, 0.0)),
    grip_line=((-0.04, 0.0, 0.0), (0.04, 0.0, 0.0)),
    max_opening=0.085,
    max_payload=None,
):
    site_path = "%s/%s" % (parent_path, name)
    xform = UsdGeom.Xform.Define(stage, site_path)
    prim = xform.GetPrim()
    if apply_isaac_site_api:
        # AddAppliedSchema (vs ApplyAPI) writes the schema name to the prim's
        # apiSchemas metadata without requiring the schema to be registered.
        # In pure-Python USD test environments (no Kit/Isaac loaded),
        # IsaacSiteAPI is not registered, so ApplyAPI raises. The validator
        # code reads schemas via GetAppliedSchemas(), so AddAppliedSchema is
        # functionally equivalent for our purposes.
        prim.AddAppliedSchema("IsaacSiteAPI")
    _add_basis_curves(stage, site_path, "gripper_forward_axis", *forward_axis)
    _add_basis_curves(stage, site_path, "gripper_grip_line", *grip_line)
    attr = prim.CreateAttribute("gripper_maxOpening", Sdf.ValueTypeNames.Float)
    attr.Set(float(max_opening))
    if max_payload is not None:
        pl = prim.CreateAttribute("gripper_maxPayload", Sdf.ValueTypeNames.Float)
        pl.Set(float(max_payload))
    return prim


def test_discover_returns_empty_when_no_gripper_prims():
    stage, asset_prim = _stage_with_asset()
    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_skips_gripper_without_isaac_site_api():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(stage, "/World/Asset", apply_isaac_site_api=False)
    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_finds_one_valid_gripper():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(stage, "/World/Asset", max_payload=5.0)
    sites = discover_gripper_sites(stage, asset_prim)
    assert len(sites) == 1
    s = sites[0]
    assert s.prim_path == "/World/Asset/gripper_01"
    # gripper_maxOpening is float32; read-back is float64 with epsilon noise
    assert math.isclose(s.max_opening, 0.085, abs_tol=1e-6)
    assert math.isclose(s.max_payload, 5.0, abs_tol=1e-6)
    # Verify every parsed field — these would silently default to garbage if the
    # impl drops a field.
    assert np.allclose(s.pose_world_initial, np.eye(4), atol=1e-6)
    # gripper_forward_axis points (0,-0.15,0)→(0,0.15,0) → unit +Y
    assert np.allclose(s.forward_axis_world, np.array([0.0, 1.0, 0.0]), atol=1e-6)
    # gripper_grip_line endpoints (-0.04,0,0) and (+0.04,0,0)
    assert np.allclose(s.grip_line_world[0], np.array([-0.04, 0.0, 0.0]), atol=1e-6)
    assert np.allclose(s.grip_line_world[1], np.array([0.04, 0.0, 0.0]), atol=1e-6)


def test_legacy_isaac_site_with_arbitrary_name_is_classified_as_gripper():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(stage, "/World/Asset", name="tool_contact_site")

    assert _has_gripper_signals(stage, asset_prim)


def test_discover_accepts_attachment_socket_without_isaac_api():
    stage, asset_prim = _stage_with_asset()
    prim = _add_gripper_site(stage, "/World/Asset", apply_isaac_site_api=False)
    prim.CreateAttribute("simready:attachment:socketType", Sdf.ValueTypeNames.Token).Set("Gripper")

    sites = discover_gripper_sites(stage, asset_prim)

    assert len(sites) == 1
    assert sites[0].prim_path == "/World/Asset/gripper_01"


def test_discover_rejects_non_finite_site_data():
    stage, asset_prim = _stage_with_asset()
    prim = _add_gripper_site(stage, "/World/Asset")
    prim.GetAttribute("gripper_maxOpening").Set(float("nan"))

    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_applies_world_transform_to_site():
    """Rotated/translated gripper — ensures transforms are actually applied."""
    stage, asset_prim = _stage_with_asset()
    site = _add_gripper_site(stage, "/World/Asset")
    # Translate site to (1, 2, 3); no rotation for now (rotation auth via xformOps
    # is verbose — translation is sufficient to catch impl that drops the xform).
    UsdGeom.XformCommonAPI(site).SetTranslate((1.0, 2.0, 3.0))
    sites = discover_gripper_sites(stage, asset_prim)
    assert len(sites) == 1
    assert np.allclose(sites[0].pose_world_initial[3, :3], np.array([1.0, 2.0, 3.0]), atol=1e-6)
    # grip_line endpoints in world space should be translated too
    assert np.allclose(sites[0].grip_line_world[0], np.array([0.96, 2.0, 3.0]), atol=1e-6)
    assert np.allclose(sites[0].grip_line_world[1], np.array([1.04, 2.0, 3.0]), atol=1e-6)


def test_discover_skips_gripper_with_zero_max_opening():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(stage, "/World/Asset", max_opening=0.0)
    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_skips_gripper_with_negative_max_opening():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(stage, "/World/Asset", max_opening=-0.01)
    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_skips_gripper_with_missing_forward_axis():
    """Malformed asset: no gripper_forward_axis child."""
    stage, asset_prim = _stage_with_asset()
    site_path = "/World/Asset/gripper_01"
    UsdGeom.Xform.Define(stage, site_path).GetPrim().AddAppliedSchema("IsaacSiteAPI")
    _add_basis_curves(stage, site_path, "gripper_grip_line", (-0.04, 0, 0), (0.04, 0, 0))
    stage.GetPrimAtPath(site_path).CreateAttribute("gripper_maxOpening", Sdf.ValueTypeNames.Float).Set(0.085)
    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_skips_surface_gripper_on_site():
    stage, asset_prim = _stage_with_asset()
    prim = _add_gripper_site(stage, "/World/Asset")
    prim.AddAppliedSchema("IsaacSurfaceGripperAPI")
    assert discover_gripper_sites(stage, asset_prim) == []


def test_discover_skips_surface_gripper_on_parent_body():
    stage, asset_prim = _stage_with_asset()
    body = UsdGeom.Xform.Define(stage, "/World/Asset/wrist").GetPrim()
    body.AddAppliedSchema("IsaacSurfaceGripperAPI")
    _add_gripper_site(stage, "/World/Asset/wrist")
    assert discover_gripper_sites(stage, asset_prim) == []


def test_gripper_site_closure_axis_perpendicular_to_authored_curves():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(
        stage,
        "/World/Asset",
        forward_axis=((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),  # +Z
        grip_line=((-0.04, 0.0, 0.0), (0.04, 0.0, 0.0)),  # +X
    )
    sites = discover_gripper_sites(stage, asset_prim)
    axis = sites[0].closure_axis_world()
    expected = np.array([0.0, 1.0, 0.0])
    assert math.isclose(abs(np.dot(axis, expected)), 1.0, abs_tol=1e-6)


def test_gripper_site_grasp_center_world_initial_returns_origin():
    stage, asset_prim = _stage_with_asset()
    _add_gripper_site(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset_prim)
    assert np.allclose(sites[0].grasp_center_world_initial(), np.zeros(3), atol=1e-6)

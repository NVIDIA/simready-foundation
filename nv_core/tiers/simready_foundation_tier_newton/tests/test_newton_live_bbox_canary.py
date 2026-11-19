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
"""Newton's required runtime canary measures live geometry, not authored poses."""

import ast
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.evaluate_engine_kit import fabric_utils
from simready.foundation.tier_newton.runtime_tests.articulation_phases import joint_utils
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)


@pytest.mark.parametrize("baseline_side,current_side", [(1e104, 1e106), (2.0, 1e104), (0.0, 1e104)])
def test_overflowing_required_volumes_are_not_a_stability_pass(baseline_side, current_side):
    baseline = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (baseline_side,) * 3)
    current = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (current_side,) * 3)
    with pytest.raises(RequiredReadbackError, match="derived geometry volumes must be finite"):
        joint_utils.check_bbox_explode(current, baseline, 10.0)


def test_finite_ratio_does_not_overflow_the_bbox_allowance():
    baseline = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (2.0,) * 3)
    current = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (1e100,) * 3)
    assert joint_utils.check_bbox_explode(current, baseline, 1e308) is None
    assert joint_utils.check_bbox_explode(current, baseline, 1e298)


@pytest.mark.parametrize("ratio", [math.nan, math.inf, -math.inf, 0.0, -1.0, True, "10"])
def test_bbox_canary_rejects_invalid_direct_ratio(ratio):
    snapshot = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (1.0,) * 3)
    with pytest.raises(ValueError):
        joint_utils.check_bbox_explode(snapshot, snapshot, ratio)


def test_bbox_allowance_boundary_and_degenerate_policy_are_preserved():
    baseline = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (1.0,) * 3)
    current = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (2.0,) * 3)
    assert joint_utils.check_bbox_explode(current, baseline, 8.0) is None
    assert joint_utils.check_bbox_explode(current, baseline, 7.99)
    zero = joint_utils.BBoxSnapshot((0.0, 0.0, 0.0), (0.0,) * 3)
    assert joint_utils.check_bbox_explode(current, zero, 8.0) is None


class _RTStage:
    def __init__(self, matrices):
        self.matrices = matrices
        self.reads = []

    def GetPrimAtPath(self, path):
        self.reads.append(path)
        matrix = self.matrices.get(path)
        if matrix is None:
            return None
        attribute = SimpleNamespace(HasValue=lambda: True, Get=lambda: matrix)
        return SimpleNamespace(GetAttribute=lambda name: attribute)


def _fabric(monkeypatch, stage, matrices):
    """Replace only Kit's unavailable SDK seams; execute the production reader."""
    rt_stage = _RTStage(matrices)
    omni = ModuleType("omni")
    omni.__path__ = []
    usd = ModuleType("omni.usd")
    usd.get_context = lambda: SimpleNamespace(get_stage_id=lambda: 17, get_stage=lambda: stage)
    omni.usd = usd
    usdrt = ModuleType("usdrt")
    usdrt.Usd = SimpleNamespace(Stage=SimpleNamespace(Attach=lambda stage_id: rt_stage))
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    monkeypatch.setitem(sys.modules, "usdrt", usdrt)
    return rt_stage


def _translation(x=0, y=0, z=0):
    return Gf.Matrix4d(1).SetTranslate(Gf.Vec3d(x, y, z))


def _scene():
    stage = Usd.Stage.CreateInMemory()
    return stage, UsdGeom.Xform.Define(stage, "/Robot").GetPrim()


def _body(stage, path, authored_x=0, enabled=True):
    prim = UsdGeom.Xform.Define(stage, path).GetPrim()
    UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(authored_x, 0, 0))
    UsdPhysics.RigidBodyAPI.Apply(prim).CreateRigidBodyEnabledAttr(enabled)
    return prim


def _cube(stage, path):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(2)
    return cube.GetPrim()


def test_runtime_canary_follows_live_links_and_detects_growth(monkeypatch):
    stage, root = _scene()
    _body(stage, "/Robot/A")
    _body(stage, "/Robot/B", authored_x=2)
    _cube(stage, "/Robot/A/Visual")
    _cube(stage, "/Robot/B/Visual")
    matrices = {"/Robot/A": _translation(), "/Robot/B": _translation(2)}
    rt = _fabric(monkeypatch, stage, matrices)
    baseline = joint_utils.compute_world_aligned_bbox(root)
    matrices["/Robot/B"] = _translation(10)
    current = joint_utils.compute_world_aligned_bbox(root)
    authored = joint_utils.compute_world_aligned_bbox(root, authored=True)
    assert baseline.max_point == authored.max_point == (3, 1, 1)
    assert current.max_point == (11, 1, 1)
    assert joint_utils.check_bbox_explode(current, baseline, 2) is not None
    assert rt.reads == ["/Robot/A", "/Robot/B", "/Robot/A", "/Robot/B"]


@pytest.mark.parametrize(
    "name",
    [
        "robot_scene",
        "drive_gain_validation",
        "effort_limit",
        "full_range_sweep",
        "state_accuracy",
        "velocity_limit",
        "mimic_joint",
        "multi_joint_coordination",
        "ik_target_reach",
        "jacobian_ik",
    ],
)
def test_native_joint_leaf_layout_all_canary_callers_measure_loaded_asset(monkeypatch, name):
    stage, asset = _scene()
    leaf = UsdPhysics.FixedJoint.Define(stage, "/Robot/root_joint").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(leaf)
    _body(stage, "/Robot/Base")
    _body(stage, "/Robot/Tip", authored_x=2)
    _cube(stage, "/Robot/Base/Visual")
    _cube(stage, "/Robot/Tip/Visual")
    # Test-owned room geometry must not pollute the robot canary.
    _cube(stage, "/Room/Visual")
    UsdGeom.Xformable(stage.GetPrimAtPath("/Room")).AddTranslateOp().Set(Gf.Vec3d(10000, 0, 0))
    matrices = {"/Robot/Base": _translation(), "/Robot/Tip": _translation(2)}
    _fabric(monkeypatch, stage, matrices)
    with pytest.raises(RequiredReadbackError, match="no eligible geometry"):
        joint_utils.compute_world_aligned_bbox(leaf)

    source = Path(joint_utils.__file__).resolve().parent / (name + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "compute_world_aligned_bbox"
        and not any(keyword.arg == "authored" for keyword in node.keywords)
    ]
    assert calls
    namespace = {
        "asset_prim": asset,
        "robot_root_prim": leaf,
        "content_root_prim": leaf,
        "geometry_root_prim": asset,
    }
    for call in calls:
        selected = eval(compile(ast.Expression(call.args[0]), str(source), "eval"), namespace)
        assert selected == asset
        baseline = joint_utils.compute_world_aligned_bbox(selected)
        assert baseline.max_point == (3, 1, 1)
        matrices["/Robot/Tip"] = _translation(10)
        current = joint_utils.compute_world_aligned_bbox(selected)
        assert current.max_point == (11, 1, 1)
        assert joint_utils.check_bbox_explode(current, baseline, 2) is not None
        matrices["/Robot/Tip"] = _translation(2)

    if name == "ik_target_reach":
        dispatch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_interpolate_ik_motion"
        )
        selected_argument = next(keyword.value for keyword in dispatch.keywords if keyword.arg == "geometry_root_prim")
        selected = eval(
            compile(ast.Expression(selected_argument), str(source), "eval"),
            {"inputs": {"asset_prim": asset, "robot_root_prim": leaf}},
        )
        assert selected == asset


def test_authored_setup_never_requests_live_sdk(monkeypatch):
    stage, root = _scene()
    _body(stage, "/Robot/Body", authored_x=7)
    _cube(stage, "/Robot/Body/Visual")

    def forbidden(*args, **kwargs):
        pytest.fail("setup heuristic must not demand a live physics view")

    monkeypatch.setattr(fabric_utils, "live_world_aabb", forbidden)
    snapshot = joint_utils.compute_world_aligned_bbox(root, authored=True)
    assert snapshot.min_point == (6, -1, -1)
    assert snapshot.max_point == (8, 1, 1)


def test_nested_independent_body_contributes_at_live_pose_only(monkeypatch):
    stage, root = _scene()
    _body(stage, "/Robot/Parent")
    _cube(stage, "/Robot/Parent/Visual")
    _body(stage, "/Robot/Parent/Child", authored_x=-100)
    _cube(stage, "/Robot/Parent/Child/Visual")
    rt = _fabric(monkeypatch, stage, {"/Robot/Parent": _translation(), "/Robot/Parent/Child": _translation(10)})
    current = joint_utils.compute_world_aligned_bbox(root)
    assert current.min_point == (-1, -1, -1)
    assert current.max_point == (11, 1, 1)
    assert rt.reads == ["/Robot/Parent", "/Robot/Parent/Child"]


@pytest.mark.parametrize("enabled_parent", [False, True])
def test_disabled_body_uses_enabled_ancestor_or_authored_static(monkeypatch, enabled_parent):
    stage, root = _scene()
    _body(stage, "/Robot/Parent", authored_x=3, enabled=enabled_parent)
    _body(stage, "/Robot/Parent/Disabled", authored_x=2, enabled=False)
    _cube(stage, "/Robot/Parent/Disabled/Visual")
    rt = _fabric(monkeypatch, stage, {"/Robot/Parent": _translation(20)} if enabled_parent else {})
    current = joint_utils.compute_world_aligned_bbox(root)
    assert current.min_point == ((21 if enabled_parent else 4), -1, -1)
    assert current.max_point == ((23 if enabled_parent else 6), 1, 1)
    assert rt.reads == (["/Robot/Parent"] if enabled_parent else [])


def test_missing_required_body_rejects_partial_union(monkeypatch):
    stage, root = _scene()
    for body in ("A", "B"):
        _body(stage, "/Robot/" + body)
        _cube(stage, "/Robot/" + body + "/Visual")
    _fabric(monkeypatch, stage, {"/Robot/A": _translation()})
    with pytest.raises(RequiredReadbackError, match="required live geometry") as caught:
        joint_utils.compute_world_aligned_bbox(root)
    assert isinstance(caught.value.__cause__, fabric_utils.LiveBoundsReadError)
    assert "/Robot/B" in str(caught.value.__cause__)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_live_matrix_is_setup_error(monkeypatch, bad):
    stage, root = _scene()
    _body(stage, "/Robot/Body")
    _cube(stage, "/Robot/Body/Visual")
    rows = [[float(value) for value in row] for row in _translation()]
    rows[3][0] = bad
    _fabric(monkeypatch, stage, {"/Robot/Body": rows})
    with pytest.raises(RequiredReadbackError, match="required live geometry"):
        joint_utils.compute_world_aligned_bbox(root)


def test_zero_thickness_geometry_keeps_degenerate_canary_policy(monkeypatch):
    stage, root = _scene()
    _body(stage, "/Robot/Body")
    mesh = UsdGeom.Mesh.Define(stage, "/Robot/Body/Visual")
    mesh.CreateExtentAttr([(-1, -1, 0), (1, 1, 0)])
    _fabric(monkeypatch, stage, {"/Robot/Body": _translation()})
    snapshot = joint_utils.compute_world_aligned_bbox(root)
    assert snapshot.volume == 0
    assert joint_utils.check_bbox_explode(snapshot, snapshot, 2) is None


@pytest.mark.parametrize(
    "result", [None, ((0, 0), (1, 1, 1)), ((float("nan"), 0, 0), (1, 1, 1)), ((2, 0, 0), (1, 1, 1))]
)
def test_owned_boundary_requests_strict_reader_and_validates_result(monkeypatch, result):
    stage, root = _scene()
    calls = []

    def reader(selected_stage, selected_path, select, require_complete=False):
        calls.append((selected_stage, selected_path, select, require_complete))
        return result

    monkeypatch.setattr(fabric_utils, "live_world_aabb", reader)
    with pytest.raises(RequiredReadbackError):
        joint_utils.compute_world_aligned_bbox(root)
    assert calls == [(stage, "/Robot", fabric_utils.is_rigid_body, True)]


def test_empty_or_missing_runtime_geometry_never_fabricates_zero(monkeypatch):
    stage, root = _scene()
    _fabric(monkeypatch, stage, {})
    with pytest.raises(RequiredReadbackError, match="no eligible geometry"):
        joint_utils.compute_world_aligned_bbox(root)
    with pytest.raises(RequiredReadbackError, match="selected geometry root unavailable"):
        joint_utils.compute_world_aligned_bbox(stage.GetPrimAtPath("/Missing"))


@pytest.mark.parametrize("name", ["ground_drop", "slope_drop", "ground_stability"])
def test_drop_initial_setup_bounds_are_explicitly_authored(name):
    suite = Path(joint_utils.__file__).resolve().parent.parent
    filename = "slope_drop.py" if name == "slope_drop" else "_ground_trial.py"
    tree = ast.parse((suite / "fet003_physics" / filename).read_text(encoding="utf-8"))
    initial = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "init_bounds" for target in node.targets)
    )
    assert isinstance(initial, ast.Call)
    assert any(keyword.arg == "authored" and ast.literal_eval(keyword.value) is True for keyword in initial.keywords)
    runtime = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_asset_bounds"
        and node is not initial
    ]
    assert runtime
    assert all(not any(keyword.arg == "authored" for keyword in node.keywords) for node in runtime)

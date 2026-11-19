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
"""Core canaries use complete loaded geometry, not articulation-leaf zeros."""

import ast
import json
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.evaluate.runner.test_context import RunContext
from simready.evaluate_engine_kit import fabric_utils
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    joint_utils,
    passive_joints,
    state_accuracy,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)
from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver


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


def _translation(x=0):
    return Gf.Matrix4d(1).SetTranslate(Gf.Vec3d(x, 0, 0))


def _fabric(monkeypatch, stage, matrices):
    reads = []

    def read_prim(path):
        reads.append(path)
        matrix = matrices.get(path)
        if matrix is None:
            return None
        attribute = SimpleNamespace(HasValue=lambda: True, Get=lambda: matrix)
        return SimpleNamespace(GetAttribute=lambda name: attribute)

    omni = ModuleType("omni")
    omni.__path__ = []
    usd = ModuleType("omni.usd")
    usd.get_context = lambda: SimpleNamespace(get_stage_id=lambda: 17, get_stage=lambda: stage)
    omni.usd = usd
    usdrt = ModuleType("usdrt")
    usdrt.Usd = SimpleNamespace(Stage=SimpleNamespace(Attach=lambda stage_id: SimpleNamespace(GetPrimAtPath=read_prim)))
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    monkeypatch.setitem(sys.modules, "usdrt", usdrt)
    return reads


def _scene():
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    leaf = UsdPhysics.FixedJoint.Define(stage, "/Robot/root_joint").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(leaf)
    for name, x in (("Base", 0), ("Tip", 2)):
        body = UsdGeom.Xform.Define(stage, "/Robot/" + name).GetPrim()
        UsdGeom.Xformable(body).AddTranslateOp().Set(Gf.Vec3d(x, 0, 0))
        UsdPhysics.RigidBodyAPI.Apply(body)
        UsdGeom.Cube.Define(stage, "/Robot/" + name + "/Visual").CreateSizeAttr(2)
    room = UsdGeom.Xform.Define(stage, "/Room")
    room.AddTranslateOp().Set(Gf.Vec3d(10000, 0, 0))
    UsdGeom.Cube.Define(stage, "/Room/Visual").CreateSizeAttr(100)
    return stage, asset, leaf, {"/Robot/Base": _translation(), "/Robot/Tip": _translation(2)}


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
def test_all_production_canaries_select_loaded_asset_and_follow_live_growth(monkeypatch, name):
    stage, asset, leaf, matrices = _scene()
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
        assert baseline.min_point == (-1, -1, -1) and baseline.max_point == (3, 1, 1)
        matrices["/Robot/Tip"] = _translation(10)
        current = joint_utils.compute_world_aligned_bbox(selected)
        assert current.max_point == (11, 1, 1)
        assert joint_utils.check_bbox_explode(current, baseline, 2)
        matrices["/Robot/Tip"] = _translation(2)
    if name == "ik_target_reach":
        dispatch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_interpolate_ik_motion"
        )
        expression = next(keyword.value for keyword in dispatch.keywords if keyword.arg == "geometry_root_prim")
        assert (
            eval(
                compile(ast.Expression(expression), str(source), "eval"),
                {"inputs": {"asset_prim": asset, "robot_root_prim": leaf}},
            )
            == asset
        )


@pytest.mark.parametrize("prebuilt_carrier", [False, True])
def test_scene_preparation_keeps_articulation_identity_and_discovers_asset_sibling_joints(
    monkeypatch, prebuilt_carrier
):
    stage, asset, leaf, matrices = _scene()
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joints/hinge")
    joint.CreateBody0Rel().SetTargets(["/Robot/Base"])
    joint.CreateBody1Rel().SetTargets(["/Robot/Tip"])
    UsdPhysics.Joint(leaf).CreateBody1Rel().SetTargets(["/Robot/Base"])
    _fabric(monkeypatch, stage, matrices)
    source = Path(joint_utils.__file__).resolve().parent / "robot_scene.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    # The public entrypoint owns global-hook restoration; the implementation
    # builds the scene and computes the geometry/discovery inputs checked here.
    setup = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_setup_robot_test_scene"
    )
    targets = {"content_root_path", "content_root_prim", "initial_bbox", "passive_indices"}
    block = [
        node
        for node in setup.body
        if isinstance(node, ast.Assign)
        and any(
            (isinstance(target, ast.Name) and target.id in targets)
            or (
                isinstance(target, ast.Tuple)
                and any(isinstance(item, ast.Name) and item.id in targets for item in target.elts)
            )
            for target in node.targets
        )
    ]
    assert len(block) == 4
    namespace = {
        "stage": stage,
        "asset_prim": asset,
        "robot_root_path": "/Carrier" if prebuilt_carrier else str(leaf.GetPath()),
        "prebuilt_gripper_carrier": {"asset_robot_root_path": str(leaf.GetPath())} if prebuilt_carrier else None,
        "robot": SimpleNamespace(dof_names=["hinge"]),
        "compute_world_aligned_bbox": joint_utils.compute_world_aligned_bbox,
        "detect_passive_joints": passive_joints.detect_passive_joints,
    }
    exec(compile(ast.Module(body=block, type_ignores=[]), str(source), "exec"), namespace)
    assert namespace["content_root_path"] == str(leaf.GetPath())
    assert namespace["content_root_prim"] == leaf
    assert namespace["initial_bbox"].volume == 16
    assert namespace["passive_indices"] == frozenset({0})


@pytest.mark.parametrize("failure", ["missing", "nan", "empty", "invalid_root"])
def test_required_complete_geometry_error_never_fabricates_zero_or_partial_union(monkeypatch, failure):
    stage, asset, leaf, matrices = _scene()
    if failure == "missing":
        del matrices["/Robot/Tip"]
    elif failure == "nan":
        rows = [[float(value) for value in row] for row in _translation()]
        rows[3][0] = float("nan")
        matrices["/Robot/Tip"] = rows
    elif failure == "empty":
        asset = leaf
    else:
        asset = stage.GetPrimAtPath("/Missing")
    _fabric(monkeypatch, stage, matrices)
    with pytest.raises(RequiredReadbackError):
        joint_utils.compute_world_aligned_bbox(asset)


def test_valid_zero_thickness_geometry_keeps_existing_degenerate_volume_policy(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    body = UsdGeom.Xform.Define(stage, "/Robot/Body").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    UsdGeom.Mesh.Define(stage, "/Robot/Body/Visual").CreateExtentAttr([(-1, -1, 0), (1, 1, 0)])
    _fabric(monkeypatch, stage, {"/Robot/Body": _translation()})
    snapshot = joint_utils.compute_world_aligned_bbox(root)
    assert snapshot.volume == 0
    assert joint_utils.check_bbox_explode(snapshot, snapshot, 2) is None


def test_authored_reach_setup_is_explicit_and_does_not_request_live_sdk(monkeypatch):
    stage, asset, _, _ = _scene()
    assert asset.GetStage() == stage

    def forbidden(*args, **kwargs):
        pytest.fail("static setup heuristic must not require a live physics view")

    monkeypatch.setattr(fabric_utils, "live_world_aabb", forbidden)
    snapshot = joint_utils.compute_world_aligned_bbox(asset, authored=True)
    assert snapshot.max_point == (3, 1, 1)
    source = Path(joint_utils.__file__).resolve().parent / "jacobian_ik.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    authored_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "compute_world_aligned_bbox"
        and any(keyword.arg == "authored" and ast.literal_eval(keyword.value) is True for keyword in node.keywords)
    ]
    assert len(authored_calls) == 1


@pytest.mark.asyncio
async def test_real_canary_error_retains_prior_motion_and_original_cause_not_asset_failure(monkeypatch, tmp_path):
    stage, asset, leaf, matrices = _scene()
    _fabric(monkeypatch, stage, matrices)
    baseline = joint_utils.compute_world_aligned_bbox(asset)
    commands, steps = [], []
    robot = SimpleNamespace(
        dof_count=1,
        get_joint_positions=lambda: np.zeros(1),
        get_joint_velocities=lambda: np.ones(1),
        set_joint_position_targets=lambda values: commands.append(values.copy()),
    )
    ctx = RunContext(
        asset_path="/Robot.usd",
        asset_rel_path="Robot.usd",
        output_dir=str(tmp_path),
        test_name="state_accuracy",
        test_version="1.2.2",
        feature_id="feature",
        engine_name="kit",
        engine_version="test",
        session_id="session",
        scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None),
    )

    async def step_one():
        steps.append(None)
        if len(steps) == 21:
            del matrices["/Robot/Tip"]

    async def capture_frame(**kwargs):
        return None

    ctx.step_one = step_one
    ctx.capture_frame = capture_frame
    motion = MotionObserver(
        ctx,
        "trial",
        {
            name: {"unit": "rad/s" if name == "velocity" else "rad", "source": "existing phase observation"}
            for name in ("position", "velocity", "target", "final_goal", "error", "goal_error")
        },
        sample_stride=1,
    )
    with pytest.raises(RequiredReadbackError) as caught:
        await state_accuracy._run_motion_to_target(
            ctx,
            robot,
            {"index": 0, "name": "hinge"},
            0.9,
            25,
            100,
            [],
            baseline,
            10,
            leaf,
            asset,
            1,
            motion=motion,
            motion_clock={"steps": 0, "physics_fps": 4, "issued_target": 0.9},
        )
    assert isinstance(caught.value.__cause__, fabric_utils.LiveBoundsReadError)
    assert "/Robot/Tip" in str(caught.value.__cause__)
    ctx.finalize_motion_evidence()
    metadata = ctx.metrics["motion_history_trial"]["value"]
    assert metadata["partial"] and metadata["sample_count"] == 20
    payload = json.loads((tmp_path / metadata["json"]).read_text(encoding="utf-8"))
    assert len(payload["samples"]) == 20
    assert len(steps) == len(commands) == 21
    assert not ctx.failed and not ctx.skipped

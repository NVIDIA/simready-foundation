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
import builtins
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    _independent_dofs as ownership,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    drive_gain_validation,
    joint_utils,
    mimic_joint,
    mimic_joints,
    multi_joint_coordination,
    robot_scene,
    robot_state,
    state_accuracy,
    velocity_limit,
)

_PHASES = [multi_joint_coordination, state_accuracy, drive_gain_validation, velocity_limit, mimic_joint]


class _Robot:
    dof_names = ["master", "follower", "passive", "loop", "independent"]
    dof_count = 5
    prim_path = "/Robot"
    articulation = None

    def __init__(self, unsupported=False):
        self.position = np.array([0.0, 0.1, 0.2, 0.5, 0.3])
        self.target = self.position.copy()
        self.velocity = np.zeros(5)
        self.writes = []
        self.unsupported = unsupported
        self.capability_checks = 0

    def require_indexed_joint_control(self):
        self.capability_checks += 1
        if self.unsupported:
            raise RuntimeError("native indexed capability unavailable")

    def get_joint_positions(self):
        return self.position.copy()

    def get_joint_velocities(self):
        return self.velocity.copy()

    def get_joint_position_limits(self):
        return np.full(5, -1.0), np.full(5, 1.0)

    def get_joint_velocity_limits(self):
        return np.ones(5)

    def apply_velocity_limits_to_tensor_view(self, values):
        assert np.isnan(values[[1, 2, 3]]).all()
        return True

    def set_joint_position_targets(self, values):
        raise AssertionError("A full target vector commands dependent coordinates")

    def set_joint_positions(self, values):
        raise AssertionError("A full state vector overwrites dependent coordinates")

    def set_joint_velocities(self, values):
        raise AssertionError("A full velocity vector overwrites dependent coordinates")

    def _write(self, field, values, indices):
        assert list(indices) == [0, 4]
        self.writes.append((field, list(indices), np.asarray(values).copy()))
        getattr(self, field)[indices] = values

    def set_joint_position_targets_indexed(self, values, indices):
        self._write("target", values, indices)

    def set_joint_positions_indexed(self, values, indices):
        self._write("position", values, indices)

    def set_joint_velocities_indexed(self, values, indices):
        self._write("velocity", values, indices)


class _Context:
    begin_motion_history = None

    def __init__(self, robot):
        self.robot = robot
        self.ticks = 0
        self.metrics = {}
        self.failed = []
        self.skipped = []
        self.scene = SimpleNamespace(update_camera_follow=lambda **_kwargs: None)

    async def step_one(self):
        self.ticks += 1
        self.robot.position[[0, 4]] = self.robot.target[[0, 4]]
        self.robot.position[1] = 2 * self.robot.position[0] + 0.1
        self.robot.position[2] += 0.001
        self.robot.position[3] = 0.5 - self.robot.position[0]

    async def settle(self, count=1):
        for _ in range(count):
            await self.step_one()

    async def capture_frame(self, **_kwargs):
        return None

    def add_metric(self, key, value):
        self.metrics[key] = value

    def step(self, *_args):
        pass

    log = step
    warn = step
    encode_video = step

    def fail(self, message):
        self.failed.append(message)

    def skip(self, message):
        self.skipped.append(message)


def _scene(robot, *, reset=False):
    result = {"passive_joint_indices": [2], "mimic_follower_indices": [1], "loop_joint_indices": [3]}
    if reset:
        result["default_state"] = robot_state.RobotDefaultState(
            joint_positions=robot.position.copy(),
            joint_velocities=robot.velocity.copy(),
            root_position=(0, 0, 0),
            root_orientation=(1, 0, 0, 0),
        )
    return result


def _run(phase, monkeypatch, *, unsupported=False, skip=False):
    robot = _Robot(unsupported=unsupported)
    ctx = _Context(robot)
    scene = _scene(robot, reset=phase is drive_gain_validation)
    monkeypatch.setattr(phase, "compute_world_aligned_bbox", lambda _prim: None)
    monkeypatch.setattr(phase, "check_bbox_explode", lambda *_args: None)
    if phase is mimic_joint:
        pair = SimpleNamespace(reference_dof_index=0, follower_dof_index=1, gear=-2.0, offset=0.0, backend="physx")
        monkeypatch.setattr(phase, "detect_mimic_joints", lambda **_kwargs: [] if skip else [pair])
        if skip:
            scene["mimic_follower_indices"] = []
    elif skip:
        scene["passive_joint_indices"] = [0, 2, 3, 4]
    config = {
        **phase.get_defaults(),
        "settle_seconds": 0,
        "physics_fps": 20,
        "capture_fps": 10,
        "num_iterations": 1,
        "motion_seconds": 0.05,
        "test_duration_seconds": 0.1,
        "sweep_seconds": 2,
    }
    runner = getattr(phase, "run_" + phase.__name__.rsplit(".", 1)[-1])
    return robot, ctx, runner(ctx, robot, scene, config)


@pytest.mark.parametrize("phase", _PHASES)
def test_each_phase_leaves_dependent_control_buffers_untouched(monkeypatch, phase):
    robot, ctx, run = _run(phase, monkeypatch)
    untouched_targets = robot.target[[1, 2, 3]].copy()
    untouched_velocity = robot.velocity[[1, 2, 3]].copy()
    asyncio.run(run)
    assert robot.writes and ctx.ticks > 0
    assert not ctx.failed and not ctx.skipped
    assert all(indices == [0, 4] for _, indices, _ in robot.writes)
    np.testing.assert_array_equal(robot.target[[1, 2, 3]], untouched_targets)
    np.testing.assert_array_equal(robot.velocity[[1, 2, 3]], untouched_velocity)
    assert robot.position[1] == pytest.approx(2 * robot.position[0] + 0.1)
    if phase is drive_gain_validation:
        assert {"position", "velocity"} <= {field for field, _, _ in robot.writes}


@pytest.mark.parametrize("phase", _PHASES)
def test_unqualified_sparse_backend_is_execution_error_before_excitation(monkeypatch, phase):
    robot, ctx, run = _run(phase, monkeypatch, unsupported=True)
    with pytest.raises(RuntimeError, match="indexed capability unavailable"):
        asyncio.run(run)
    assert robot.capability_checks > 0 and robot.writes == [] and ctx.ticks == 0
    assert ctx.failed == []


@pytest.mark.parametrize("phase", _PHASES)
def test_applicability_skip_precedes_sparse_capability_check(monkeypatch, phase):
    robot, ctx, run = _run(phase, monkeypatch, unsupported=True, skip=True)
    asyncio.run(run)
    assert ctx.skipped and not ctx.failed
    assert robot.capability_checks == 0 and robot.writes == [] and ctx.ticks == 0


def test_mimic_chain_dependent_reference_is_explicit_limitation_not_fake_control(monkeypatch):
    robot, ctx, run = _run(mimic_joint, monkeypatch)
    pairs = [
        SimpleNamespace(reference_dof_index=0, follower_dof_index=1),
        SimpleNamespace(reference_dof_index=1, follower_dof_index=4),
    ]
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **_kwargs: pairs)
    with pytest.raises(RuntimeError, match="chained coupling is not qualified"):
        asyncio.run(run)
    assert robot.writes == [] and ctx.ticks == 0 and ctx.failed == []


@pytest.mark.parametrize("schema", ["NewtonMimicAPI", "PhysxMimicJointAPI:rotX", "PhysxMimicJointAPI:futureAxis"])
def test_raw_authored_ownership_does_not_need_coefficient_sdk_axis_or_reference(schema):
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    stage.SetDefaultPrim(world)
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/World/Asset/follower").GetPrim()
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit([schema]))
    assert mimic_joints.detect_mimic_follower_indices(stage, asset, str(asset.GetPath()), ["master", "follower"]) == {1}
    with pytest.raises(RuntimeError, match="cannot be uniquely mapped"):
        mimic_joints.detect_mimic_follower_indices(stage, asset, str(asset.GetPath()), ["master"])
    with pytest.raises(RuntimeError, match="cannot be uniquely mapped"):
        mimic_joints.detect_mimic_follower_indices(stage, asset, str(asset.GetPath()), ["follower", "follower"])


def test_successfully_observed_no_mimic_is_empty_ownership():
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    assert mimic_joints.detect_mimic_follower_indices(stage, asset, "/Asset", ["master"]) == set()


def test_missing_required_usd_import_is_not_successful_empty_ownership(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    original_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "pxr":
            raise ImportError("required USD APIs unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    with pytest.raises(ImportError, match="required USD"):
        mimic_joints.detect_mimic_follower_indices(stage, asset, "/Asset", ["master"])


@pytest.mark.parametrize("query", ["mimic", "loop"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
def test_required_ownership_query_errors_never_clear_exclusions(monkeypatch, query, error_type):
    error = error_type("ownership unavailable")
    monkeypatch.setattr(mimic_joints, "detect_mimic_follower_indices", lambda *_args: {1})
    monkeypatch.setattr(joint_utils, "detect_loop_joints", lambda *_args, **_kwargs: ({2}, ["loop"]))

    def failed(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(
        mimic_joints if query == "mimic" else joint_utils,
        "detect_mimic_follower_indices" if query == "mimic" else "detect_loop_joints",
        failed,
    )
    if error_type is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError) as caught:
            ownership.control_ownership(None, None, "/Robot", ["master", "follower", "loop"])
        assert caught.value is error
    else:
        with pytest.raises(RuntimeError, match="Required " + query + " control ownership") as caught:
            ownership.control_ownership(None, None, "/Robot", ["master", "follower", "loop"])
        assert caught.value.__cause__ is error


def test_required_ownership_names_come_from_validated_runtime_mapping(monkeypatch):
    monkeypatch.setattr(mimic_joints, "detect_mimic_follower_indices", lambda *_args: {1})
    monkeypatch.setattr(joint_utils, "detect_loop_joints", lambda *_args, **_kwargs: ({2}, ["wrong alias"]))
    assert ownership.control_ownership(None, None, "/Robot", ["master", "follower", "loop"]) == (
        {1},
        ["follower"],
        {2},
        ["loop"],
    )


@pytest.mark.parametrize("schema", ["NewtonMimicAPI", "PhysxMimicJointAPI:rotX", "PhysxMimicJointAPI:futureAxis"])
def test_disabled_authored_mimic_is_not_an_active_unmapped_follower_or_response_pair(schema):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/unused_follower")
    follower.GetPrim().SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit([schema]))
    follower.CreateJointEnabledAttr(False)
    assert mimic_joints.detect_mimic_follower_indices(stage, asset, "/Asset", ["arm"]) == set()
    assert mimic_joints.detect_mimic_joints(stage, asset, "/Asset", ["arm"]) == []


@pytest.mark.parametrize("disabled_joint", ["closure", "arm1"])
def test_disabled_loop_closure_or_tree_edge_does_not_create_active_cycle(disabled_joint):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    for body in ("a", "b", "c"):
        UsdGeom.Xform.Define(stage, "/Asset/" + body)
    joints = {}
    for name, body0, body1 in [("arm0", "a", "b"), ("arm1", "b", "c"), ("closure", "c", "a")]:
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/" + name)
        joint.CreateBody0Rel().SetTargets(["/Asset/" + body0])
        joint.CreateBody1Rel().SetTargets(["/Asset/" + body1])
        joints[name] = joint
    joints["closure"].CreateExcludeFromArticulationAttr(True)
    assert joint_utils.detect_loop_joints(stage, "/Asset", ["arm0", "arm1"])[0] == {0, 1}
    joints[disabled_joint].CreateJointEnabledAttr(False)
    assert joint_utils.detect_loop_joints(stage, "/Asset", ["arm0", "arm1"]) == (set(), [])


def _loop_asset(*, instanceable=False, actuator=False):
    stage = Usd.Stage.CreateInMemory()
    prototype = UsdGeom.Xform.Define(stage, "/Prototype").GetPrim()
    for body in ("a", "b", "c"):
        UsdGeom.Xform.Define(stage, "/Prototype/" + body)
    for path, body0, body1 in [("a/arm0", "a", "b"), ("arm1", "b", "c"), ("closure", "c", "a")]:
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Prototype/" + path)
        joint.CreateBody0Rel().SetTargets(["/Prototype/" + body0])
        joint.CreateBody1Rel().SetTargets(["/Prototype/" + body1])
        if path == "closure":
            joint.CreateExcludeFromArticulationAttr(True)
    if actuator:
        control = stage.DefinePrim("/Prototype/control", "NewtonActuator")
        control.CreateRelationship("newton:targets").SetTargets(["/Prototype/a/arm0"])
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    asset.GetReferences().AddInternalReference(prototype.GetPath())
    asset.SetInstanceable(instanceable)
    return stage, asset


@pytest.mark.parametrize("instanceable", [False, True])
def test_required_loop_ownership_uses_entire_verified_asset_not_partial_body(instanceable):
    stage, asset = _loop_asset(instanceable=instanceable)
    assert ownership.control_ownership(stage, asset, "/Asset/a", ["arm0", "arm1"]) == (
        set(),
        [],
        {0, 1},
        ["arm0", "arm1"],
    )


@pytest.mark.parametrize("instanceable", [False, True])
def test_loop_actuator_owner_is_found_in_instance_proxies(instanceable):
    stage, asset = _loop_asset(instanceable=instanceable, actuator=True)
    assert ownership.control_ownership(stage, asset, "/Asset/a", ["arm0", "arm1"]) == (set(), [], {1}, ["arm1"])


def test_empty_verified_asset_never_climbs_into_unrelated_loop_or_mimic_content():
    stage, _other = _loop_asset()
    asset = UsdGeom.Xform.Define(stage, "/Empty").GetPrim()
    assert ownership.control_ownership(stage, asset, "/Empty", ["arm0", "arm1"]) == (set(), [], set(), [])
    nested_asset = UsdGeom.Xform.Define(stage, "/Container/Empty").GetPrim()
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Container/Other/follower").GetPrim()
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["PhysxMimicJointAPI:rotX"]))
    assert ownership.control_ownership(stage, nested_asset, "/Container/Empty", ["arm0", "arm1"]) == (
        set(),
        [],
        set(),
        [],
    )


def test_loop_boundary_rejects_a_root_outside_verified_asset():
    stage, asset = _loop_asset()
    with pytest.raises(RuntimeError, match="outside the verified loaded asset"):
        joint_utils.detect_loop_joints(stage, "/Prototype", ["arm0", "arm1"], asset_prim=asset)


def test_authored_ownership_without_qualified_response_is_execution_limitation(monkeypatch):
    robot, ctx, run = _run(mimic_joint, monkeypatch)
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **_kwargs: [])
    with pytest.raises(RuntimeError, match="authored mimic followers exist"):
        asyncio.run(run)
    assert robot.writes == [] and ctx.ticks == 0 and not ctx.failed and not ctx.skipped


@pytest.mark.parametrize(
    "limits",
    [
        (-np.inf, np.inf),
        (-float(np.finfo(np.float32).max), float(np.finfo(np.float32).max)),
        (-3.402823e38, 3.402823e38),
        (-np.inf, 1.0),
        (-1.0, float(np.finfo(np.float32).max)),
        (0.0, 5e-7),
        (0.0, 0.0),
        (1.0, -1.0),
    ],
)
def test_unlimited_mimic_window_is_execution_limitation_without_commands_or_asset_verdict(monkeypatch, limits):
    robot, ctx, run = _run(mimic_joint, monkeypatch)
    lower, upper = np.full(5, -1.0), np.full(5, 1.0)
    lower[0], upper[0] = limits
    robot.get_joint_position_limits = lambda: (lower, upper)
    with pytest.raises(RuntimeError, match="MIM runtime error:.*finite runtime sweep interval"):
        asyncio.run(run)
    assert robot.writes == [] and ctx.ticks == 0
    assert ctx.failed == [] and ctx.skipped == []
    assert "mim_pairs_failed" not in ctx.metrics and "mim_pairs_passed" not in ctx.metrics


def test_later_unavailable_mimic_window_retains_completed_finite_pair_measurements(monkeypatch):
    robot, ctx, run = _run(mimic_joint, monkeypatch)
    pairs = [
        SimpleNamespace(reference_dof_index=0, follower_dof_index=1, gear=-2.0, offset=0.0, backend="physx"),
        SimpleNamespace(reference_dof_index=4, follower_dof_index=2, gear=-1.0, offset=0.0, backend="physx"),
    ]
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **_kwargs: pairs)
    lower, upper = np.full(5, -1.0), np.full(5, 1.0)
    lower[4], upper[4] = -np.inf, np.inf
    robot.get_joint_position_limits = lambda: (lower, upper)
    with pytest.raises(RuntimeError, match="finite runtime sweep interval"):
        asyncio.run(run)
    assert robot.writes and ctx.ticks > 0 and not ctx.failed
    assert ctx.metrics["mim_pair_follower_gear_ratio_error"] == pytest.approx(0)
    assert "mim_pair_passive_gear_ratio_error" not in ctx.metrics
    assert all(abs(values[0]) <= 1.0 for field, _, values in robot.writes if field == "target")


def test_real_run_context_keeps_unlimited_window_out_of_validated_asset_failure(monkeypatch, tmp_path):
    from simready.evaluate.runner.test_context import RunContext

    robot, fake_ctx, unused_run = _run(mimic_joint, monkeypatch)
    unused_run.close()
    feature = (
        "FET022_DrivenJoints.Newton.0-1-0" if "newton" in mimic_joint.__name__ else "FET022_DrivenJoints.PhysX.0-1-0"
    )
    ctx = RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir=str(tmp_path),
        test_name="mimic_joint",
        test_version="1.1.7",
        feature_id=feature,
        engine_name="kit",
        engine_version="host canary",
        session_id="host",
        scene=fake_ctx.scene,
        test_feature_names=[feature],
        asset_validated_features=[feature],
    )
    ctx.begin_motion_history = None
    ctx.step_one = fake_ctx.step_one
    ctx.capture_frame = fake_ctx.capture_frame
    lower, upper = np.full(5, -1.0), np.full(5, 1.0)
    lower[0], upper[0] = -np.finfo(np.float32).max, np.finfo(np.float32).max
    robot.get_joint_position_limits = lambda: (lower, upper)
    with pytest.raises(RuntimeError, match="MIM runtime error"):
        asyncio.run(
            mimic_joint.run_mimic_joint(
                ctx, robot, _scene(robot), {**mimic_joint.get_defaults(), "settle_seconds": 0, "physics_fps": 20}
            )
        )
    assert not ctx.failed and not ctx.skipped
    assert robot.writes == [] and fake_ctx.ticks == 0
    assert "mim_pairs_failed" not in ctx.metrics


def test_invalid_loaded_prim_guidance_preserves_root_type_units_and_loader_diagnosis():
    message = robot_scene._fix_message_asset_load_failed("asset.usda")
    assert "invalid loaded asset prim" in message and "DIAGNOSE:" in message
    assert "UsdGeomXformable" in message and "loader" in message
    for unsafe in (
        "defaultPrim is missing or invalid",
        "TEMPLATE --",
        "prepend apiSchemas",
        'defaultPrim = "Robot"',
        "metersPerUnit = 1",
        'upAxis = "Z"',
    ):
        assert unsafe not in message


@pytest.mark.parametrize(
    "message",
    [
        robot_scene._fix_message_robot_type_unauthored_gripper_signals(),
        robot_scene._fix_message_robot_type_unauthored_default_arm(),
    ],
)
def test_robot_type_heuristic_does_not_prescribe_its_token_as_asset_truth(message):
    assert "DIAGNOSE:" in message and "actual mechanism" in message
    assert "example only" in message and "provenance" in message
    assert "FIX: Author" not in message and "prepend apiSchemas" not in message
    assert "token isaac:robotType =" not in message.partition("REFERENCE:")[0]


@pytest.mark.parametrize(
    "message",
    [
        robot_scene._fix_message_zero_dofs("/Robot/joints/root_joint"),
        robot_scene._fix_message_no_root_body_for_pin("/Robot/joints/root_joint"),
    ],
)
def test_root_mapping_guidance_does_not_invent_invalid_leaf_topology_or_mass(message):
    assert "DIAGNOSE:" in message and "sibling" in message
    assert "physics:body0/body1" in message
    for unsafe in (
        "PhysX cooked",
        "successfully but",
        "root has no child",
        "exists at or below",
        "physics:mass = 0.85",
        "TEMPLATE --",
        "lowerLimit == upperLimit",
    ):
        assert unsafe not in message
    assert "Do not relocate" in message


def test_coordination_skip_does_not_ban_valid_continuous_revolute_limits():
    message = multi_joint_coordination._build_skip_message_no_movable_joints(2, 1)
    assert "do NOT use +-inf" not in message
    assert "signed infinite endpoints" in message and "unbounded revolute" in message


def test_empty_mimic_guidance_is_not_an_api_count_or_blanket_authoring_prescription():
    message = mimic_joint._msg_no_mimic_authored()
    assert "no active authored mimic" in message
    assert "Disabled joints" in message
    assert "Do not add a mimic" in message or "do not add a mimic" in message
    assert "0 joints with" not in message and "Paste-ready" not in message


@pytest.mark.parametrize(
    "schemas",
    [
        ["NewtonMimicAPI"],
        ["NewtonMimicAPI", "PhysxMimicJointAPI:rotX"],
        ["NewtonMimicAPI", "PhysxMimicJointAPI:rotX", "MjcEqualityJointAPI"],
        ["PhysxMimicJointAPI:rotX", "MjcEqualityJointAPI"],
    ],
)
def test_raw_newton_ownership_preserves_defined_disabled_mimic_and_equality_precedence(schemas):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/follower").GetPrim()
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(schemas))
    follower.CreateAttribute("newton:mimicEnabled", Sdf.ValueTypeNames.Bool).Set(False)
    assert mimic_joints.detect_mimic_follower_indices(stage, asset, "/Asset", ["arm"]) == set()

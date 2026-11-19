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

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach,
    jacobian_ik,
    robot_scene,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import (
    RobotType,
    has_standalone_gripper_topology,
    is_standalone_gripper,
)

_RECEIPTS = ["FET022_DrivenJoints.PhysX.0-2-0", "FET028_Gripper.Isaac.0-1-0"]
_LEGACY = ["FET_022_PHYSX", "FET_028_ISAAC"]


@pytest.mark.parametrize("receipts", [_RECEIPTS, _LEGACY])
@pytest.mark.parametrize("kind", [RobotType.ARM, RobotType.COMPOSITE, None])
def test_receipts_do_not_classify_six_independent_dofs_as_standalone(receipts, kind):
    robot = SimpleNamespace(dof_count=7)
    scene = {"robot_type": kind, "has_gripper_signals": True, "mimic_follower_indices": [6]}
    assert not is_standalone_gripper(robot, scene, receipts)


@pytest.mark.parametrize("receipts", [_RECEIPTS, _LEGACY])
def test_receipts_plus_one_independent_motion_identify_mistagged_mimic_gripper(receipts):
    robot = SimpleNamespace(dof_count=6)
    scene = {"robot_type": RobotType.ARM, "mimic_follower_indices": [1, 2, 3, 4, 5]}
    assert is_standalone_gripper(robot, scene, receipts)


def test_explicit_gripper_type_does_not_require_arm_topology():
    assert is_standalone_gripper(object(), {"robot_type": RobotType.GRIPPER}, _RECEIPTS)


def test_inferred_gripper_type_still_requires_native_independent_topology():
    scene = {"robot_type": RobotType.GRIPPER, "robot_type_authored": False, "has_gripper_signals": True}
    assert not is_standalone_gripper(SimpleNamespace(dof_count=6), scene, _RECEIPTS)
    assert not is_standalone_gripper(object(), scene, _RECEIPTS)
    assert is_standalone_gripper(SimpleNamespace(dof_count=1), scene, _RECEIPTS)


@pytest.mark.parametrize("count", [None, True, -1, 0, 1.5, "1"])
def test_unknown_dof_topology_does_not_supply_standalone_proof(count):
    assert not is_standalone_gripper(SimpleNamespace(dof_count=count), {}, _RECEIPTS)


@pytest.mark.parametrize("indices", [[True], [1.0], ["1"], [-1], [6], 1, np.array([True])])
def test_ambiguous_exclusion_indices_do_not_supply_standalone_proof(indices):
    robot = SimpleNamespace(dof_count=6)
    scene = {"has_gripper_signals": True, "mimic_follower_indices": indices}
    assert not is_standalone_gripper(robot, scene, _RECEIPTS)


def test_exclusions_are_a_union_and_numpy_integer_indices_are_supported():
    robot = SimpleNamespace(dof_count=np.int64(4))
    scene = {
        "has_gripper_signals": True,
        "passive_joint_indices": [1],
        "mimic_follower_indices": np.array([1, 2], dtype=np.int64),
        "loop_joint_indices": [3],
    }
    assert is_standalone_gripper(robot, scene, _RECEIPTS)


def test_low_dof_count_without_any_gripper_signal_is_not_standalone_proof():
    assert not is_standalone_gripper(SimpleNamespace(dof_count=1), {})
    assert not is_standalone_gripper(
        SimpleNamespace(dof_count=1),
        {},
        ["FET022_DrivenJointsOther.PhysX.0-2-0", "FET028_Gripper.Isaac.0-1-0"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("receipts", [_RECEIPTS, _LEGACY])
@pytest.mark.parametrize("phase_name", ["jacobian", "lula"])
async def test_real_phase_entry_keeps_arm_with_gripper_applicable(monkeypatch, receipts, phase_name):
    messages = []
    ctx = SimpleNamespace(asset_validated_features=receipts, skip=messages.append, step=lambda message: None)
    robot = SimpleNamespace(dof_count=7, prim_path="/Arm")
    scene = {"robot_type": RobotType.ARM, "stage": object(), "mimic_follower_indices": [6]}
    reached = RuntimeError("arm IK setup was reached")

    if phase_name == "jacobian":

        def discover(**kwargs):
            raise reached

        monkeypatch.setattr(jacobian_ik, "discover_end_effector_link", discover)
        with pytest.raises(RuntimeError) as caught:
            await jacobian_ik.run_jacobian_ik(ctx, robot, scene, {})
    else:

        async def setup(*args):
            raise reached

        monkeypatch.setattr(ik_target_reach, "_setup_ik_phase", setup)
        with pytest.raises(RuntimeError) as caught:
            await ik_target_reach.run_ik_target_reach(ctx, robot, scene, {})

    assert caught.value is reached
    assert messages == []


@pytest.mark.asyncio
@pytest.mark.parametrize("phase_name", ["jacobian", "lula"])
async def test_real_phase_entry_still_skips_proven_standalone_gripper(monkeypatch, phase_name):
    messages = []
    metrics = {}
    ctx = SimpleNamespace(
        asset_validated_features=_RECEIPTS,
        skip=messages.append,
        add_metric=lambda name, value: metrics.update({name: value}),
    )
    stage, asset, names = _authored_scene()
    robot = SimpleNamespace(dof_count=len(names), dof_names=names, prim_path=str(asset.GetPath()))
    scene = {
        "robot_type": RobotType.ARM,
        "mimic_follower_indices": [1],
        "stage": stage,
        "asset_prim": asset,
        "robot_root_prim": asset,
    }
    if phase_name == "jacobian":
        await jacobian_ik.run_jacobian_ik(ctx, robot, scene, {})
    else:
        await ik_target_reach.run_ik_target_reach(ctx, robot, scene, {})
    assert len(messages) == 1
    assert "not applicable to standalone grippers" in messages[0]
    assert metrics["assessment_applicability"]["status"] == "not_applicable"


def _authored_scene(arm_joints=0, explicit_type=None):
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(asset)
    UsdPhysics.ArticulationRootAPI.Apply(asset)
    if explicit_type:
        asset.CreateAttribute("isaac:robotType", Sdf.ValueTypeNames.Token).Set(explicit_type)
    names = []
    body_path = "/Asset/Housing"
    UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, body_path).GetPrim())
    for index in range(arm_joints):
        next_body = "/Asset/Segment_%d" % index
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, next_body).GetPrim())
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/hinge_%d" % index)
        joint.CreateBody0Rel().SetTargets([body_path])
        joint.CreateBody1Rel().SetTargets([next_body])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100)
        names.append(joint.GetPrim().GetName())
        body_path = next_body
    jaw_prims = []
    for name in ("jaw_leader", "jaw_follower"):
        jaw_body = "/Asset/" + name + "_body"
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, jaw_body).GetPrim())
        joint = UsdPhysics.PrismaticJoint.Define(stage, "/Asset/" + name)
        joint.CreateBody0Rel().SetTargets([body_path])
        joint.CreateBody1Rel().SetTargets([jaw_body])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear").CreateStiffnessAttr(100)
        names.append(name)
        jaw_prims.append(joint.GetPrim())
    # Inspect genuine composed USD data without requiring Isaac's native
    # extension registry. Both locally owned detectors understand this API.
    jaw_prims[1].SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
    jaw_prims[1].CreateRelationship("newton:mimicJoint").SetTargets([jaw_prims[0].GetPath()])
    jaw_prims[1].CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(-1.0)
    jaw_prims[1].CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Float).Set(0.0)
    site = UsdGeom.Xform.Define(stage, body_path + "/Socket").GetPrim()
    site.CreateAttribute("simready:attactment:socketType", Sdf.ValueTypeNames.Token).Set("Gripper")
    return stage, asset, names


def test_authored_topology_distinguishes_an_arm_with_attached_gripper_from_one_leader_jaw():
    stage, asset, _ = _authored_scene(arm_joints=6)
    assert not has_standalone_gripper_topology(stage, asset)
    stage, asset, _ = _authored_scene()
    assert has_standalone_gripper_topology(stage, asset)


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_names",
        "unsupported_joint",
        "outside_reference",
        "cyclic_mimic",
        "disabled_mimic",
        "missing_reference",
        "multiple_references",
        "nonfinite_gear",
        "self_reference",
    ],
)
def test_ambiguous_authored_topology_does_not_reclassify_entire_asset(case):
    from pxr import Sdf, UsdPhysics

    stage, asset, _ = _authored_scene()
    if case == "duplicate_names":
        UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Extra/jaw_leader")
    elif case == "unsupported_joint":
        UsdPhysics.SphericalJoint.Define(stage, "/Asset/Ball")
    else:
        leader = stage.GetPrimAtPath("/Asset/jaw_leader")
        follower = stage.GetPrimAtPath("/Asset/jaw_follower")
        follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
        follower.CreateRelationship("newton:mimicJoint").SetTargets([leader.GetPath()])
        if case == "outside_reference":
            outside = UsdPhysics.PrismaticJoint.Define(stage, "/Elsewhere")
            follower.GetRelationship("newton:mimicJoint").SetTargets([outside.GetPath()])
        elif case == "disabled_mimic":
            follower.CreateAttribute("newton:mimicEnabled", Sdf.ValueTypeNames.Bool).Set(False)
        elif case == "missing_reference":
            follower.GetRelationship("newton:mimicJoint").ClearTargets(True)
        elif case == "multiple_references":
            follower.GetRelationship("newton:mimicJoint").SetTargets([leader.GetPath(), follower.GetPath()])
        elif case == "nonfinite_gear":
            follower.GetAttribute("newton:mimicCoef1").Set(float("nan"))
        elif case == "self_reference":
            follower.GetRelationship("newton:mimicJoint").SetTargets([follower.GetPath()])
        elif case == "cyclic_mimic":
            leader.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
            leader.CreateRelationship("newton:mimicJoint").SetTargets([follower.GetPath()])
    assert not has_standalone_gripper_topology(stage, asset)


def test_one_joint_with_unresolved_mimic_is_ambiguous_not_one_independent_leader():
    from pxr import Sdf, Usd, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    asset = stage.DefinePrim("/Asset", "Xform")
    follower = UsdPhysics.PrismaticJoint.Define(stage, "/Asset/jaw").GetPrim()
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
    assert not has_standalone_gripper_topology(stage, asset)


@pytest.mark.asyncio
@pytest.mark.parametrize("hidden_follower", [False, True])
@pytest.mark.parametrize(
    "arm_joints, explicit_type, expected_type, source, expected_pins",
    [
        (6, None, RobotType.ARM, "structural_or_default", 0),
        (0, None, RobotType.GRIPPER, "inferred_gripper_topology", 1),
        (6, "End Effector", RobotType.GRIPPER, "authored", 1),
    ],
)
async def test_scene_classification_happens_before_pin_and_preserves_provenance(
    monkeypatch, arm_joints, explicit_type, expected_type, source, expected_pins, hidden_follower
):
    from simready.evaluate_engine_kit import physics_utils
    from simready.foundation.tier_core.runtime_tests import engine_guard

    stage, asset, names = _authored_scene(arm_joints, explicit_type)
    if hidden_follower:
        names.remove("jaw_follower")
    pins = []
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(physics_utils, "cook_skip_message", lambda result: None)
    monkeypatch.setattr(physics_utils, "pin_body_to_world", lambda *args: pins.append(args) or True)
    monkeypatch.setattr(engine_guard, "newton_scene_initialized", lambda: True)
    monkeypatch.setattr(robot_scene, "capture_default_state", lambda robot: object())
    monkeypatch.setattr(robot_scene, "compute_world_aligned_bbox", lambda prim: object())

    class Robot:
        dof_count = len(names)
        dof_names = names

        def __init__(self, **kwargs):
            self.prim_path = kwargs["robot_prim_path"]

        async def initialize_newton(self, ctx):
            pass

    monkeypatch.setattr(robot_scene, "RobotHandle", Robot)

    class Scene:
        def __init__(self):
            self.stage = stage
            self.lighting = SimpleNamespace(add_dome=lambda **kwargs: None)

        def load_asset(self, *args, **kwargs):
            return SimpleNamespace(prim_path=str(asset.GetPath()))

        def add_room(self):
            from simready.evaluate_engine_kit.room import RoomHandle

            room = RoomHandle(stage)
            room.set_size(20, 30, 10)
            monkeypatch.setattr(room, "auto_size", lambda *args: None)
            return room

        def add_physics(self, **kwargs):
            return SimpleNamespace(play=lambda: None)

        def setup_camera_follow(self, config):
            pass

        async def prepare_physics(self):
            return None

    class Context:
        config = {}
        asset_path = "asset.usd"

        def __init__(self):
            self.scene = Scene()
            self.warnings = []

        def set_settle_frames(self, frames):
            pass

        def step(self, message):
            pass

        def warn(self, message):
            self.warnings.append(message)

        async def settle(self, **kwargs):
            pass

    robot, info = await robot_scene.setup_robot_test_scene(Context())
    assert info["robot_type"] == expected_type
    assert info["robot_type_authored"] is bool(explicit_type)
    assert info["robot_type_source"] == source
    assert len(pins) == expected_pins
    assert is_standalone_gripper(robot, info, _RECEIPTS) is (expected_type == RobotType.GRIPPER)

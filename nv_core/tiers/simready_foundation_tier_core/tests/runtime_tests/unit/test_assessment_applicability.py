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

"""Prerequisite gaps cannot masquerade as proven behavioral inapplicability."""

from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach,
    jacobian_ik,
    mimic_joint,
    multi_joint_coordination,
    velocity_limit,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import RobotType


class Context:
    asset_path = "asset.usda"
    asset_validated_features = None

    def __init__(self):
        self.recorded = {}
        self.skipped = []
        self.events = []

    @property
    def metrics(self):
        # The framework exposes a copy; marker publication must use add_metric.
        return dict(self.recorded)

    def add_metric(self, name, value):
        self.recorded[name] = value
        self.events.append(("metric", name))

    def skip(self, message):
        self.skipped.append(message)
        self.events.append(("skip", message))

    def fail(self, message):
        pytest.fail("No asset response was evaluated: " + message)

    def step(self, message):
        pass

    log = warn = step

    async def step_one(self):
        pytest.fail("No physics tick is justified before prerequisites are met")


def scene(count=1, unbounded=False):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    names = [f"slide_{i:d}" for i in range(count)]
    for name in names:
        UsdPhysics.PrismaticJoint.Define(stage, "/Robot/" + name)
    robot = SimpleNamespace(
        prim_path="/Robot",
        dof_count=count,
        dof_names=names,
        get_joint_position_limits=lambda: (
            np.array([-1.0] * count),
            np.array([float("inf") if unbounded and i else 1.0 for i in range(count)]),
        ),
        get_joint_velocity_limits=lambda: np.full(count, float("nan")),
    )
    return robot, {"stage": stage, "asset_prim": root, "robot_root_prim": root}


def assert_not_applicable(ctx, reason_code):
    assert len(ctx.skipped) == 1
    assert ctx.recorded["assessment_applicability"] == {
        "status": "not_applicable",
        "reason_code": reason_code,
        "reason": ctx.skipped[0],
    }
    assert ctx.events.index(("metric", "assessment_applicability")) < next(
        i for i, event in enumerate(ctx.events) if event[0] == "skip"
    )


def _coordinate_scene(count, *, passive_indices=(), follower_indices=()):
    """Build an owned body graph and obtain exclusions from real USD discovery."""
    from pxr import Sdf
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    robot, info = scene(count)
    stage, root = info["stage"], info["asset_prim"]
    UsdPhysics.ArticulationRootAPI.Apply(root)
    for index in range(count + 1):
        body = UsdGeom.Xform.Define(stage, f"/Robot/body_{index}").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
    for index, name in enumerate(robot.dof_names):
        joint = UsdPhysics.PrismaticJoint(stage.GetPrimAtPath("/Robot/" + name))
        joint.CreateBody0Rel().SetTargets([f"/Robot/body_{index}"])
        joint.CreateBody1Rel().SetTargets([f"/Robot/body_{index + 1}"])
        if index in follower_indices:
            prim = joint.GetPrim()
            prim.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
            prim.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Float).Set(0)
            prim.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(1)
            prim.CreateRelationship("newton:mimicJoint").SetTargets(["/Robot/" + robot.dof_names[0]])
        elif index not in passive_indices:
            UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear").CreateStiffnessAttr(100)
    passive, _ = detect_passive_joints(stage, robot.prim_path, robot.dof_names, root)
    followers, _, loops, _ = control_ownership(stage, root, robot.prim_path, robot.dof_names)
    info.update(passive_joint_indices=passive, mimic_follower_indices=followers, loop_joint_indices=loops)
    return robot, info


def _actuator_contract_scene(contract):
    stage, asset, arm, robot = _controlled_arm_scene("loaded")
    if contract != "newton":
        for name in robot.dof_names:
            actuator = stage.GetPrimAtPath("/Asset/controllers/servo_" + name)
            actuator.SetTypeName("MjcActuator")
            actuator.RemoveProperty("newton:targets")
            target = stage.GetPrimAtPath("/Asset/arm/" + name)
            if contract == "mjc_tendon":
                tendon = stage.DefinePrim("/Asset/controllers/tendon_" + name, "MjcTendon")
                tendon.CreateRelationship("mjc:path").SetTargets([target.GetPath()])
                target = tendon
            actuator.CreateRelationship("mjc:target").SetTargets([target.GetPath()])
    return stage, asset, arm, robot


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contract,source,fault",
    [
        ("newton", "newton:targets", "query"),
        ("mjc_direct", "mjc:target", "query"),
        ("mjc_tendon", "mjc:path", "query"),
        ("mjc_tendon", "mjc:target", "query"),
        ("newton", "newton:targets", "missing"),
        ("mjc_direct", "mjc:target", "missing"),
        ("mjc_tendon", "mjc:path", "missing"),
        ("mobility", "newton:jointsAddMobility", "none"),
        ("mobility", "newton:jointsAddMobility", "zero"),
        ("mobility", "newton:jointsAddMobility", "empty"),
    ],
)
@pytest.mark.parametrize("broken_logger", [False, True])
@pytest.mark.parametrize(
    "phase",
    [
        velocity_limit.run_velocity_limit,
        multi_joint_coordination.run_multi_joint_coordination,
        ik_target_reach.run_ik_target_reach,
        jacobian_ik.run_jacobian_ik,
    ],
)
async def test_unreadable_passive_sources_retain_unmarked_skip(
    monkeypatch, contract, source, fault, broken_logger, phase
):
    from pxr import Sdf
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    if contract == "mobility":
        robot, info = _coordinate_scene(3, passive_indices=[0, 1, 2])
        stage, asset, arm = info["stage"], info["asset_prim"], info["robot_root_prim"]
        value_type = {
            "none": Sdf.ValueTypeNames.Bool,
            "zero": Sdf.ValueTypeNames.Int,
            "empty": Sdf.ValueTypeNames.String,
        }[fault]
        attribute = arm.CreateAttribute(source, value_type)
        if fault != "none":
            attribute.Set(0 if fault == "zero" else "")
        assert attribute.Get() == {"none": None, "zero": 0, "empty": ""}[fault]
    else:
        stage, asset, arm, robot = _actuator_contract_scene(contract)
        assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset)[0] == frozenset()
        if fault == "query":
            original = Usd.Relationship.GetTargets

            def failed_targets(relationship):
                if (
                    str(relationship.GetPrim().GetPath()).startswith("/Asset/controllers/")
                    and relationship.GetName() == source
                ):
                    raise OSError("required actuator source query failed")
                return original(relationship)

            monkeypatch.setattr(Usd.Relationship, "GetTargets", failed_targets)
        else:
            for prim in stage.Traverse():
                prim.RemoveProperty(source)
    # Historical discovery still supplies the legacy skip classification.
    passive, _ = detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset)
    assert passive == frozenset({0, 1, 2})
    followers, _, loops, _ = control_ownership(stage, asset, robot.prim_path, robot.dof_names)
    info = {
        "stage": stage,
        "asset_prim": asset,
        "robot_root_prim": arm,
        "passive_joint_indices": passive,
        "mimic_follower_indices": followers,
        "loop_joint_indices": loops,
        "has_gripper_signals": True,
        "robot_type_authored": False,
    }
    ctx, messages = Context(), []

    def log(message):
        if broken_logger:
            raise RuntimeError("diagnostic sink unavailable")
        messages.append(message)

    ctx.log = log
    before = _stage_state(stage)
    await phase(ctx, robot, info, {})
    assert len(ctx.skipped) == 1
    assert "assessment_applicability" not in ctx.recorded
    assert _stage_state(stage) == before
    if not broken_logger:
        assert any("Could not assess" in message for message in messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("broken_logger", [False, True])
@pytest.mark.parametrize(
    "phase",
    [
        velocity_limit.run_velocity_limit,
        multi_joint_coordination.run_multi_joint_coordination,
        ik_target_reach.run_ik_target_reach,
        jacobian_ik.run_jacobian_ik,
    ],
)
async def test_late_loop_actuator_query_failure_retains_unmarked_skip(monkeypatch, broken_logger, phase):
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    robot, info = _coordinate_scene(2, passive_indices=[0, 1])
    stage, asset = info["stage"], info["asset_prim"]
    closure = UsdPhysics.FixedJoint.Define(stage, "/Robot/closure")
    closure.CreateBody0Rel().SetTargets(["/Robot/body_2"])
    closure.CreateBody1Rel().SetTargets(["/Robot/body_0"])
    closure.CreateExcludeFromArticulationAttr(True)
    actuator = stage.DefinePrim("/Robot/controller", "NewtonActuator")
    actuator.CreateRelationship("newton:targets").SetTargets(["/Robot/slide_0"])
    assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset)[0] == frozenset({1})
    assert control_ownership(stage, asset, robot.prim_path, robot.dof_names)[2] == {1}
    original = Usd.Relationship.GetTargets
    reads = []

    def intermittent_targets(relationship):
        if str(relationship.GetPath()) == "/Robot/controller.newton:targets":
            reads.append(len(reads) + 1)
            if len(reads) % 2 == 0:
                raise OSError("loop-only actuator source query failed")
        return original(relationship)

    monkeypatch.setattr(Usd.Relationship, "GetTargets", intermittent_targets)
    passive, _ = detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset)
    followers, _, loops, _ = control_ownership(stage, asset, robot.prim_path, robot.dof_names)
    assert passive == frozenset({1}) and loops == {0, 1}
    info.update(
        passive_joint_indices=passive,
        mimic_follower_indices=followers,
        loop_joint_indices=loops,
        has_gripper_signals=True,
        robot_type_authored=False,
    )
    ctx, messages = Context(), []

    def log(message):
        if broken_logger:
            raise RuntimeError("diagnostic sink unavailable")
        messages.append(message)

    ctx.log = log
    before = _stage_state(stage)
    await phase(ctx, robot, info, {})
    assert reads == [1, 2, 3, 4]
    assert len(ctx.skipped) == 1
    assert "assessment_applicability" not in ctx.recorded
    assert _stage_state(stage) == before
    if not broken_logger:
        assert any("Could not assess" in message for message in messages)


@pytest.mark.parametrize("contract", ["newton", "mjc_direct", "mjc_tendon"])
def test_strict_passive_sources_preserve_healthy_actuator_ownership(contract):
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    stage, asset, arm, robot = _actuator_contract_scene(contract)
    before = _stage_state(stage)
    assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset) == (frozenset(), [])
    assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset, strict_sources=True) == (
        frozenset(),
        [],
    )
    assert control_ownership(stage, asset, robot.prim_path, robot.dof_names, strict_sources=True) == control_ownership(
        stage, asset, robot.prim_path, robot.dof_names
    )
    assert _stage_state(stage) == before


@pytest.mark.parametrize("enabled", [False, True])
def test_strict_passive_sources_preserve_boolean_mobility_policy(enabled):
    from pxr import Sdf
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    robot, info = _coordinate_scene(3, passive_indices=[0, 1, 2])
    stage, asset = info["stage"], info["asset_prim"]
    asset.CreateAttribute("newton:jointsAddMobility", Sdf.ValueTypeNames.Bool).Set(enabled)
    before = _stage_state(stage)
    expected = (frozenset(), []) if enabled else (frozenset({0, 1, 2}), robot.dof_names)
    assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset) == expected
    assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset, strict_sources=True) == expected
    assert _stage_state(stage) == before


def _stage_state(stage):
    return (
        stage.GetRootLayer().ExportToString(),
        stage.GetSessionLayer().ExportToString(),
        str(stage.GetPopulationMask()),
        tuple(sorted(str(path) for path in stage.GetLoadSet())),
        stage.GetEditTarget().GetLayer().identifier,
    )


def _controlled_arm_scene(controller_state):
    from pxr import Sdf

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    arm = UsdGeom.Xform.Define(stage, "/Asset/arm").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(arm)
    bodies, names = ["base", "one", "two", "three"], ["a", "b", "c"]
    for body in bodies:
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Asset/arm/" + body).GetPrim())
    UsdGeom.Xform.Define(stage, "/ControllerDefinition")
    for index, name in enumerate(names):
        joint = UsdPhysics.PrismaticJoint.Define(stage, "/Asset/arm/" + name)
        joint.CreateBody0Rel().SetTargets(["/Asset/arm/" + bodies[index]])
        joint.CreateBody1Rel().SetTargets(["/Asset/arm/" + bodies[index + 1]])
        actuator = stage.DefinePrim("/ControllerDefinition/servo_" + name, "NewtonActuator")
        actuator.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonPDControlAPI"]))
        actuator.CreateAttribute("newton:kp", Sdf.ValueTypeNames.Float).Set(100)
        actuator.CreateAttribute("newton:kd", Sdf.ValueTypeNames.Float).Set(1)
        actuator.CreateRelationship("newton:targets").SetTargets([joint.GetPath()])
    site = UsdGeom.Xform.Define(stage, "/Asset/arm/grasp").GetPrim()
    site.CreateAttribute("simready:attactment:socketType", Sdf.ValueTypeNames.Token).Set("Gripper")
    controllers = UsdGeom.Xform.Define(stage, "/Asset/controllers").GetPrim()
    if controller_state == "proxy":
        controllers.GetReferences().AddInternalReference("/ControllerDefinition")
        controllers.SetInstanceable(True)
        assert stage.GetPrimAtPath("/Asset/controllers/servo_a").IsInstanceProxy()
    else:
        controllers.GetPayloads().AddInternalPayload("/ControllerDefinition")
        if controller_state == "unloaded":
            stage.Unload("/Asset/controllers")
        elif controller_state == "masked":
            stage.SetPopulationMask(Usd.StagePopulationMask(["/Asset/arm"]))
    assert asset.IsLoaded()  # The controller sibling, not the robot root, is incomplete.
    robot = SimpleNamespace(
        prim_path="/Asset/arm",
        dof_names=names,
        dof_count=3,
        get_joint_position_limits=lambda: (np.full(3, -np.inf), np.full(3, np.inf)),
        get_joint_velocity_limits=lambda: np.full(3, np.nan),
    )
    return stage, asset, arm, robot


@pytest.mark.asyncio
@pytest.mark.parametrize("controller_state", ["unloaded", "masked", "loaded", "proxy", "cached_proxy", "cached_loaded"])
@pytest.mark.parametrize("phase_name", ["velocity_limit", "multi_joint_coordination", "ik_target_reach", "jacobian_ik"])
async def test_absence_markers_require_complete_sibling_controller_scope(monkeypatch, controller_state, phase_name):
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
        detect_passive_joints,
    )

    stage, asset, arm, robot = _controlled_arm_scene(
        "unloaded" if controller_state in ("cached_proxy", "cached_loaded") else controller_state
    )
    passive, _ = detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset)
    followers, _, loops, _ = control_ownership(stage, asset, robot.prim_path, robot.dof_names)
    assert passive == (
        frozenset({0, 1, 2})
        if controller_state in ("unloaded", "masked", "cached_proxy", "cached_loaded")
        else frozenset()
    )
    if controller_state in ("cached_proxy", "cached_loaded"):
        # Real discovery preceded a composition change. Loaded proxy-aware
        # composition alone cannot revalidate cached exclusion classifications.
        stage.Load("/Asset/controllers")
        if controller_state == "cached_proxy":
            stage.GetPrimAtPath("/Asset/controllers").SetInstanceable(True)
        assert stage.GetPrimAtPath("/Asset/controllers/servo_a").IsInstanceProxy() == (
            controller_state == "cached_proxy"
        )
        assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, asset)[0] == frozenset()
    info = {
        "stage": stage,
        "asset_prim": asset,
        "robot_root_prim": arm,
        "passive_joint_indices": passive,
        "mimic_follower_indices": followers,
        "loop_joint_indices": loops,
        "has_gripper_signals": True,
        "robot_type_authored": False,
    }
    phase = {
        "velocity_limit": velocity_limit,
        "multi_joint_coordination": multi_joint_coordination,
        "ik_target_reach": ik_target_reach,
        "jacobian_ik": jacobian_ik,
    }[phase_name]
    ctx = Context()
    before = _stage_state(stage)
    if controller_state in ("unloaded", "masked", "cached_proxy", "cached_loaded"):
        await getattr(phase, "run_" + phase_name)(ctx, robot, info, {})
        assert len(ctx.skipped) == 1
    else:
        # Native setup is deliberately unavailable: a loaded arm must not be
        # silently reclassified as standalone/excluded before that boundary.
        async def required_ik_setup(*args, **kwargs):
            raise RuntimeError("applicable arm reached required IK setup")

        def required_endpoint(**kwargs):
            raise RuntimeError("applicable arm reached required endpoint discovery")

        monkeypatch.setattr(ik_target_reach, "_setup_ik_phase", required_ik_setup)
        monkeypatch.setattr(jacobian_ik, "discover_end_effector_link", required_endpoint)
        with pytest.raises(RuntimeError):
            await getattr(phase, "run_" + phase_name)(ctx, robot, info, {})
        assert not ctx.skipped
    assert _stage_state(stage) == before
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize("broken_logger", [False, True])
@pytest.mark.parametrize(
    "phase",
    [
        velocity_limit.run_velocity_limit,
        multi_joint_coordination.run_multi_joint_coordination,
        ik_target_reach.run_ik_target_reach,
        jacobian_ik.run_jacobian_ik,
    ],
)
async def test_current_exclusion_query_failure_retains_unmarked_skip(phase, broken_logger):
    robot, info = _coordinate_scene(3, passive_indices=[0, 1, 2])
    info.update(has_gripper_signals=True, robot_type_authored=False)
    joint = info["stage"].GetPrimAtPath("/Robot/slide_1")
    UsdPhysics.DriveAPI.Apply(joint, "linear").CreateStiffnessAttr(float("nan"))
    messages = []
    ctx = Context()

    def log(message):
        if broken_logger:
            raise RuntimeError("diagnostic sink unavailable")
        messages.append(message)

    ctx.log = log
    before = _stage_state(info["stage"])
    await phase(ctx, robot, info, {})
    assert len(ctx.skipped) == 1
    assert "assessment_applicability" not in ctx.recorded
    assert _stage_state(info["stage"]) == before
    if not broken_logger:
        assert any(
            "control ownership could not be established" in message and "Could not assess" in message
            for message in messages
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "gap",
    [
        "missing_stage",
        "missing_asset",
        "wrong_stage",
        "class_root",
        "missing_reference",
        "missing_payload",
        "undefined_child",
        "proxy_sources",
    ],
)
async def test_unverified_asset_scope_never_authorizes_an_exclusion_marker(gap):
    ctx = Context()
    robot, info = scene()
    info["passive_joint_indices"] = [0]
    stage = info["stage"]
    if gap == "missing_stage":
        info.pop("stage")
    elif gap == "missing_asset":
        info.pop("asset_prim")
    elif gap == "wrong_stage":
        info["stage"] = Usd.Stage.CreateInMemory()
    elif gap == "class_root":
        stage.RemovePrim("/Robot")
        info["asset_prim"] = stage.CreateClassPrim("/Robot")
    elif gap in ("missing_reference", "missing_payload"):
        missing = UsdGeom.Xform.Define(stage, "/Robot/missing").GetPrim()
        if gap == "missing_reference":
            missing.GetReferences().AddReference("outcome-r3-known-missing-reference.usda")
        else:
            missing.GetPayloads().AddPayload("outcome-r3-known-missing-payload.usda")
        assert stage.GetCompositionErrors()
    elif gap == "undefined_child":
        stage.OverridePrim("/Robot/unknown")
    else:
        UsdGeom.Xform.Define(stage, "/Definition/body")
        instance = UsdGeom.Xform.Define(stage, "/Robot/source").GetPrim()
        instance.GetReferences().AddInternalReference("/Definition")
        instance.SetInstanceable(True)
        assert stage.GetPrimAtPath("/Robot/source/body").IsInstanceProxy()
    await velocity_limit.run_velocity_limit(ctx, robot, info, {})
    assert len(ctx.skipped) == 1
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize("mimic_state", ["unloaded", "masked", "loaded", "proxy"])
async def test_mimic_absence_requires_complete_owned_payload(monkeypatch, mimic_state):
    from pxr import Sdf
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(asset)
    UsdGeom.Xform.Define(stage, "/Definition")
    UsdPhysics.PrismaticJoint.Define(stage, "/Definition/leader")
    follower = UsdPhysics.PrismaticJoint.Define(stage, "/Definition/follower").GetPrim()
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
    follower.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Float).Set(0)
    follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(1)
    follower.CreateRelationship("newton:mimicJoint").SetTargets(["/Definition/leader"])
    if mimic_state == "proxy":
        asset.GetReferences().AddInternalReference("/Definition")
        asset.SetInstanceable(True)
        assert stage.GetPrimAtPath("/Asset/follower").IsInstanceProxy()
    else:
        asset.GetPayloads().AddInternalPayload("/Definition")
        if mimic_state == "unloaded":
            stage.Unload("/Asset")
        elif mimic_state == "masked":
            stage.SetPopulationMask(Usd.StagePopulationMask(["/Asset/leader"]))
    names = ["leader", "follower"]
    robot = SimpleNamespace(prim_path="/Asset", dof_names=names, dof_count=2)
    followers, _, loops, _ = control_ownership(stage, asset, robot.prim_path, names)
    info = {
        "stage": stage,
        "asset_prim": asset,
        "robot_root_prim": asset,
        "mimic_follower_indices": followers,
        "loop_joint_indices": loops,
    }
    ctx = Context()
    if mimic_state == "masked":
        # The visible leader alone has no follower; complete scope is still required.
        assert not followers
    if mimic_state in ("unloaded", "masked"):
        await mimic_joint.run_mimic_joint(ctx, robot, info, {})
        assert len(ctx.skipped) == 1
    else:
        specs = mimic_joint.detect_mimic_joints(stage, asset, robot.prim_path, names)
        assert len(specs) == 1 and specs[0].follower_dof_index == 1

        def required_control():
            raise RuntimeError("resolved mimic reached required native control")

        robot.require_indexed_joint_control = required_control
        with pytest.raises(RuntimeError, match="required native control"):
            await mimic_joint.run_mimic_joint(ctx, robot, info, {})
        assert ctx.recorded["mim_mimic_pairs_detected"] == 1
        assert not ctx.skipped
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize("broken_logger", [False, True])
async def test_incomplete_marker_proof_logs_without_changing_legacy_skip(broken_logger):
    robot, info = scene()
    info["passive_joint_indices"] = [0]
    stage = info["stage"]
    UsdGeom.Xform.Define(stage, "/Definition")
    child = UsdGeom.Xform.Define(stage, "/Robot/hidden").GetPrim()
    child.GetPayloads().AddInternalPayload("/Definition")
    stage.Unload("/Robot/hidden")
    messages = []
    ctx = Context()

    def log(message):
        if broken_logger:
            raise RuntimeError("diagnostic sink unavailable")
        messages.append(message)

    ctx.log = log
    await velocity_limit.run_velocity_limit(ctx, robot, info, {})
    assert len(ctx.skipped) == 1
    assert "assessment_applicability" not in ctx.recorded
    if not broken_logger:
        assert any("unloaded" in message and "Could not assess" in message for message in messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["newton", "physx"])
@pytest.mark.parametrize("source_state", ["active", "disabled_joint", "absent"])
async def test_empty_mapped_mimics_do_not_prove_raw_authored_absence(backend, source_state):
    from pxr import Sdf
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_identity import (
        selected_joint_prims,
    )

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(asset)
    base = UsdGeom.Xform.Define(stage, "/Asset/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(base)
    for name in ("leader", "follower"):
        body = UsdGeom.Xform.Define(stage, "/External/" + name + "_body").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        joint = UsdPhysics.PrismaticJoint.Define(stage, "/Asset/" + name)
        joint.CreateBody0Rel().SetTargets([base.GetPath()])
        joint.CreateBody1Rel().SetTargets([body.GetPath()])
    follower = stage.GetPrimAtPath("/Asset/follower")
    if source_state != "absent":
        schema = "NewtonMimicAPI" if backend == "newton" else "PhysxMimicJointAPI:transX"
        follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit([schema]))
        if backend == "newton":
            follower.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Float).Set(0)
            follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(1)
            follower.CreateRelationship("newton:mimicJoint").SetTargets(["/Asset/leader"])
    if source_state == "disabled_joint":
        UsdPhysics.Joint(follower).CreateJointEnabledAttr(False)
    robot = SimpleNamespace(prim_path="/Asset", dof_names=["leader", "follower"], dof_count=2)
    assert selected_joint_prims(stage, robot.prim_path, robot.dof_names, asset) == []
    followers, _, loops, _ = control_ownership(stage, asset, robot.prim_path, robot.dof_names)
    assert not followers and not loops
    info = {
        "stage": stage,
        "asset_prim": asset,
        "robot_root_prim": asset,
        "mimic_follower_indices": followers,
        "loop_joint_indices": loops,
    }
    ctx = Context()
    before = _stage_state(stage)
    await mimic_joint.run_mimic_joint(ctx, robot, info, {})
    assert _stage_state(stage) == before
    assert len(ctx.skipped) == 1
    if source_state == "active":
        assert "assessment_applicability" not in ctx.recorded
    else:
        assert_not_applicable(ctx, "no_active_mimic_followers")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "binding,dependency",
    [
        ("direct", "unloaded"),
        ("direct", "masked"),
        ("direct", "dangling"),
        ("direct", "undefined"),
        ("inherited", "unloaded"),
        ("direct", "ancestor_unloaded"),
        ("collection", "unloaded"),
        ("collection", "masked"),
        ("collection", "collection_masked"),
        ("collection", "collection_missing"),
        ("subset", "unloaded"),
        ("subset", "masked"),
        ("subset", "loaded"),
        ("subset_collection", "loaded"),
        ("direct", "clean"),
        ("inherited", "clean"),
        ("collection", "clean"),
    ],
)
async def test_zero_strip_requires_complete_actual_binding_dependencies(monkeypatch, binding, dependency):
    from pxr import Sdf, UsdShade
    from simready.foundation.tier_core.runtime_tests.fet011_semantics import seg_stripped

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    cube = UsdGeom.Cube.Define(stage, "/Asset/cube").GetPrim()
    looks = UsdGeom.Scope.Define(stage, "/Looks").GetPrim()
    material = UsdShade.Material.Define(stage, "/Looks/Mat")
    definition = UsdShade.Material.Define(stage, "/MaterialDefinition").GetPrim()
    if dependency not in ("clean", "ancestor_unloaded"):
        definition.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["SemanticsLabelsAPI:class"]))
    material.GetPrim().GetPayloads().AddInternalPayload("/MaterialDefinition")
    binder = cube
    if binding == "inherited":
        binder = asset
    elif binding == "subset":
        binder = UsdGeom.Subset.Define(stage, "/Asset/cube/part").GetPrim()
    binding_api = UsdShade.MaterialBindingAPI.Apply(binder)
    if binding in ("collection", "subset_collection"):
        collections = UsdGeom.Scope.Define(stage, "/Collections").GetPrim()
        collection = Usd.CollectionAPI.Apply(collections, "selected")
        included = cube
        if binding == "subset_collection":
            included = UsdGeom.Subset.Define(stage, "/Asset/cube/faces").GetPrim()
        collection.CreateIncludesRel().SetTargets([included.GetPath()])
        UsdShade.MaterialBindingAPI.Apply(asset).Bind(collection, material, bindingName="selected")
    else:
        binding_api.Bind(material)
    if dependency == "unloaded":
        stage.Unload(material.GetPath())
    elif dependency in ("masked", "collection_masked"):
        included = ["/Asset", "/Collections"] if dependency == "masked" else ["/Asset", "/Looks"]
        stage.SetPopulationMask(Usd.StagePopulationMask(included))
    elif dependency == "collection_missing":
        stage.RemovePrim("/Collections")
    elif dependency == "dangling":
        binding_api.GetDirectBindingRel().SetTargets(["/Looks/missing"])
    elif dependency == "undefined":
        stage.OverridePrim("/Looks/unknown")
        binding_api.GetDirectBindingRel().SetTargets(["/Looks/unknown"])
    elif dependency == "ancestor_unloaded":
        ancestor_definition = UsdGeom.Scope.Define(stage, "/AncestorDefinition").GetPrim()
        ancestor_definition.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["SemanticsLabelsAPI:class"]))
        looks.GetPayloads().AddInternalPayload("/AncestorDefinition")
        stage.Unload(looks.GetPath())

    ctx = Context()
    ctx.config = dict(seg_stripped.common.SHARED_CONFIG, off_coverage_max=0.002)
    room = SimpleNamespace(auto_size=lambda *args: None, set_color=lambda *args: None, hide_ground=lambda: None)
    ctx.scene = SimpleNamespace(
        stage=stage,
        asset=SimpleNamespace(prim_path="/Asset"),
        load_asset=lambda *args, **kwargs: None,
        add_room=lambda: room,
        lighting=SimpleNamespace(add_dome=lambda **kwargs: None),
        auto_frame_camera=lambda **kwargs: None,
    )

    async def settle(**kwargs):
        pass

    ctx.settle = settle
    before = _stage_state(stage)
    await seg_stripped.test_semantic_labels_seg_stripped(ctx)
    assert _stage_state(stage) == before
    assert ctx.recorded["semantic_labels_stripped_prims"] == 0
    assert len(ctx.skipped) == 1
    if dependency == "clean":
        assert_not_applicable(ctx, "no_applicable_semantics")
    else:
        assert "assessment_applicability" not in ctx.recorded
    if dependency in ("unloaded", "masked", "collection_masked", "ancestor_unloaded"):
        stage.SetPopulationMask(Usd.StagePopulationMask.All())
        stage.Load()
        # The historical stripper does not follow a Subset's material.
        assert seg_stripped.common.strip_semantics(stage, asset) == (0 if binding == "subset" else 1)


@pytest.fixture
def movement_probe(monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path

    # Reuse the existing Kit-boundary adapters; the production precheck and
    # composed USD inventory remain real in these marker regressions.
    path = Path(__file__).with_name("test_fet004_joint_movement.py")
    spec = importlib.util.spec_from_file_location("_assessment_fet004_test_helpers_core", path)
    helpers = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, helpers)
    spec.loader.exec_module(helpers)
    procedure = helpers.joint_movement.__wrapped__(monkeypatch)
    ctx, stage = helpers._assessment_movement_scene(monkeypatch, procedure)
    return procedure, ctx, stage


def _joint_definition(stage):
    UsdGeom.Xform.Define(stage, "/Definition")
    for name in ("a", "b"):
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Definition/" + name).GetPrim())
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Definition/hinge")
    joint.CreateJointEnabledAttr(True)
    joint.CreateBody0Rel().SetTargets(["/Definition/a"])
    joint.CreateBody1Rel().SetTargets(["/Definition/b"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "layout",
    [
        "empty",
        "fixed",
        "instance_root",
        "fixed_with_instance",
        "unloaded_payload",
        "partial_mask",
        "full_mask",
        "missing_reference",
        "missing_payload",
        "class_root",
        "undefined_child",
    ],
)
async def test_fet004_absence_marker_requires_complete_owned_proxy_inventory(movement_probe, layout):
    procedure, ctx, stage = movement_probe
    _joint_definition(stage)
    root = stage.GetPrimAtPath("/Asset")
    if layout in ("fixed", "fixed_with_instance"):
        UsdPhysics.FixedJoint.Define(stage, "/Asset/directFixed")
    if layout in ("instance_root", "fixed_with_instance"):
        instance = root
        if layout == "fixed_with_instance":
            instance = UsdGeom.Xform.Define(stage, "/Asset/part").GetPrim()
        instance.GetReferences().AddInternalReference("/Definition")
        instance.SetInstanceable(True)
    elif layout == "unloaded_payload":
        root.GetPayloads().AddInternalPayload("/Definition")
        stage.Unload("/Asset")
    elif layout == "partial_mask":
        root.GetReferences().AddInternalReference("/Definition")
        assert stage.GetPrimAtPath("/Asset/hinge").IsA(UsdPhysics.RevoluteJoint)
        stage.SetPopulationMask(Usd.StagePopulationMask(["/Asset/a"]))
        assert not stage.GetPrimAtPath("/Asset/hinge")
    elif layout == "full_mask":
        stage.SetPopulationMask(Usd.StagePopulationMask(["/Asset"]))
    elif layout in ("missing_reference", "missing_payload"):
        missing = UsdGeom.Xform.Define(stage, "/Asset/missing").GetPrim()
        if layout == "missing_reference":
            missing.GetReferences().AddReference("outcome-r3-known-missing-reference.usda")
        else:
            missing.GetPayloads().AddPayload("outcome-r3-known-missing-payload.usda")
        assert stage.GetCompositionErrors()
    elif layout == "class_root":
        stage.RemovePrim("/Asset")
        root = stage.CreateClassPrim("/Asset")
        assert root.IsAbstract() and root.IsDefined()
    elif layout == "undefined_child":
        stage.OverridePrim("/Asset/unknown")
    if layout in ("instance_root", "fixed_with_instance"):
        actual = [
            prim for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()) if prim.IsA(UsdPhysics.RevoluteJoint)
        ]
        assert len(actual) == 1 and actual[0].IsInstanceProxy()

    original = procedure.run_pre_checks(ctx)
    assert original.startswith(
        "SKIP: All joints are FixedJoint" if layout in ("fixed", "fixed_with_instance") else "SKIP: No joints found"
    )
    await procedure.run_joint_movement(ctx)
    assert ctx.skipped == [original[5:].strip()]
    if layout in ("empty", "fixed", "full_mask"):
        assert ctx.recorded["assessment_applicability"] == {
            "status": "not_applicable",
            "reason_code": "no_movable_joints",
            "reason": ctx.skipped[0],
        }
        assert ctx.events.index("metric") < ctx.events.index("skip")
    else:
        assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing_stage", "invalid_root", "query_error"])
async def test_fet004_inventory_read_gap_retains_unmarked_legacy_skip(movement_probe, monkeypatch, fault):
    import sys

    procedure, ctx, _ = movement_probe
    original = procedure.run_pre_checks

    def precheck_then_lose_inventory(context):
        result = original(context)
        assert result.startswith("SKIP: No joints found")
        if fault == "missing_stage":
            usd = sys.modules["omni.usd"]
            monkeypatch.setattr(usd, "get_context", lambda: SimpleNamespace(get_stage=lambda: None))
        elif fault == "invalid_root":
            context.scene.asset.prim_path = "/MissingAsset"
        else:

            def failed_query(*args, **kwargs):
                raise RuntimeError("USD inventory query unavailable")

            monkeypatch.setattr(Usd.Stage, "GetPrimAtPath", failed_query)
        return result

    monkeypatch.setattr(procedure, "run_pre_checks", precheck_then_lose_inventory)
    await procedure.run_joint_movement(ctx)
    assert len(ctx.skipped) == 1 and ctx.skipped[0].startswith("No joints found")
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
async def test_velocity_missing_comparison_ceiling_is_execution_gap():
    ctx = Context()
    robot, info = scene()
    with pytest.raises(RuntimeError, match="VEL:"):
        await velocity_limit.run_velocity_limit(ctx, robot, info, {})
    assert not ctx.skipped
    assert "assessment_applicability" not in ctx.recorded
    assert ctx.recorded["vel_joints_not_evaluated"] == 1


@pytest.mark.asyncio
async def test_velocity_all_coordinates_excluded_is_proven_not_applicable():
    ctx = Context()
    robot, info = _coordinate_scene(1, passive_indices=[0])
    await velocity_limit.run_velocity_limit(ctx, robot, info, {})
    assert_not_applicable(ctx, "no_independent_coordinates")


@pytest.mark.asyncio
async def test_coordination_one_independent_coordinate_is_proven_not_applicable():
    ctx = Context()
    robot, info = _coordinate_scene(2, follower_indices=[1])
    await multi_joint_coordination.run_multi_joint_coordination(ctx, robot, info, {})
    assert_not_applicable(ctx, "fewer_than_two_independent_coordinates")


@pytest.mark.asyncio
async def test_coordination_two_coordinates_with_unqualified_range_is_execution_gap():
    ctx = Context()
    robot, info = scene(2, unbounded=True)
    with pytest.raises(RuntimeError, match="MJC"):
        await multi_joint_coordination.run_multi_joint_coordination(ctx, robot, info, {})
    assert not ctx.skipped
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", [ik_target_reach.run_ik_target_reach, jacobian_ik.run_jacobian_ik])
async def test_standalone_gripper_is_proven_not_applicable(phase):
    from pxr import Sdf

    ctx = Context()
    robot, info = _coordinate_scene(1)
    info["asset_prim"].CreateAttribute("isaac:robotType", Sdf.ValueTypeNames.Token).Set("gripper")
    info["robot_type"] = RobotType.GRIPPER
    await phase(ctx, robot, info, {})
    assert_not_applicable(ctx, "standalone_gripper")


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
async def test_jacobian_description_matches_qualified_gripper_applicability(monkeypatch, standalone):
    from simready.foundation.tier_core.runtime_tests.fet022_driven_joints import (
        jacobian_ik as registration,
    )

    ctx = Context()
    count = 2 if standalone else 3
    robot, info = _coordinate_scene(count, follower_indices=[count - 1])
    info.update(has_gripper_signals=True)
    discovery_reached = RuntimeError("independent arm end-effector discovery reached")

    def discover(**kwargs):
        raise discovery_reached

    monkeypatch.setattr(jacobian_ik, "discover_end_effector_link", discover)
    if standalone:
        await jacobian_ik.run_jacobian_ik(ctx, robot, info, {})
        assert_not_applicable(ctx, "standalone_gripper")
    else:
        with pytest.raises(RuntimeError) as raised:
            await jacobian_ik.run_jacobian_ik(ctx, robot, info, {})
        assert raised.value is discovery_reached
        assert not ctx.skipped
    description = registration.JACOBIAN_IK_KWARGS["description"].casefold()
    assert "qualified standalone grippers" in description
    assert "attached gripper" in description and "remain applicable" in description


@pytest.mark.asyncio
async def test_jacobian_missing_stage_is_execution_gap():
    ctx = Context()
    with pytest.raises(RuntimeError, match="no USD stage"):
        await jacobian_ik.run_jacobian_ik(ctx, SimpleNamespace(prim_path="/Robot"), {}, {})
    assert not ctx.skipped


@pytest.mark.asyncio
async def test_jacobian_missing_live_endpoint_is_execution_gap(monkeypatch):
    ctx = Context()
    robot, info = scene()
    monkeypatch.setattr(jacobian_ik, "discover_end_effector_link", lambda **kwargs: "/Robot/tool")
    monkeypatch.setattr(jacobian_ik, "resolve_live_end_effector_link", lambda *args: None)
    with pytest.raises(RuntimeError, match="live articulation link"):
        await jacobian_ik.run_jacobian_ik(ctx, robot, info, {})
    assert not ctx.skipped


@pytest.mark.asyncio
async def test_lula_missing_descriptor_is_execution_gap(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.fet022_driven_joints import (
        ik_target_reach as registration,
    )

    ctx = Context()
    robot, info = scene()
    monkeypatch.setattr(ik_target_reach, "_try_build_ik_solver", lambda *args: None)
    with pytest.raises(RuntimeError, match="descriptor"):
        await ik_target_reach.run_ik_target_reach(ctx, robot, info, {})
    assert not ctx.skipped
    description = registration.IK_TARGET_REACH_KWARGS["description"].casefold()
    assert "standalone grippers" in description
    assert "missing" in description and "descriptor" in description and "no verdict" in description


@pytest.mark.asyncio
async def test_lula_missing_required_pose_is_execution_gap(monkeypatch):
    ctx = Context()
    robot, info = scene()
    monkeypatch.setattr(ik_target_reach, "_try_build_ik_solver", lambda *args: (object(), "tool", "robot"))
    monkeypatch.setattr(ik_target_reach, "_lula_controlled_robot", lambda *args: robot)
    monkeypatch.setattr(ik_target_reach, "_get_ee_position", lambda *args: None)
    with pytest.raises(RuntimeError, match="pose"):
        await ik_target_reach.run_ik_target_reach(ctx, robot, info, {"settle_seconds": 0})
    assert not ctx.skipped


@pytest.mark.asyncio
async def test_absent_active_mimic_behavior_is_proven_not_applicable():
    ctx = Context()
    robot, info = scene()
    info["mimic_follower_indices"] = []
    await mimic_joint.run_mimic_joint(ctx, robot, info, {})
    assert_not_applicable(ctx, "no_active_mimic_followers")


@pytest.mark.asyncio
async def test_unknown_mimic_presence_is_execution_gap():
    ctx = Context()
    robot, _ = scene()
    with pytest.raises(RuntimeError, match="authored mimic presence"):
        await mimic_joint.run_mimic_joint(ctx, robot, {}, {})
    assert not ctx.skipped


@pytest.mark.asyncio
async def test_unmapped_authored_mimic_pair_is_execution_gap(monkeypatch):
    ctx = Context()
    robot, info = scene()
    pair = SimpleNamespace(
        follower_dof_index=0,
        reference_dof_index=None,
        follower_joint_path="/Robot/slide_0",
        reference_joint_path="/Robot/missing",
        follower_dof_name="slide_0",
        reference_dof_name="missing",
    )
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **kwargs: [pair])
    with pytest.raises(RuntimeError, match="MIM:"):
        await mimic_joint.run_mimic_joint(ctx, robot, info, {})
    assert not ctx.skipped


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["solver_construction", "empty_targets"])
async def test_jacobian_setup_failures_cannot_be_applicability_skips(monkeypatch, boundary):
    ctx = Context()
    robot, info = scene()
    robot.get_joint_positions = lambda: np.zeros(1)
    failure = OSError("native solver unavailable")
    monkeypatch.setattr(jacobian_ik, "discover_end_effector_link", lambda **kwargs: "/Robot/tool")
    monkeypatch.setattr(jacobian_ik, "resolve_live_end_effector_link", lambda *args: "/Robot/tool")

    def solver(**kwargs):
        if boundary == "solver_construction":
            raise failure
        return SimpleNamespace(get_ee_pose=lambda: (np.zeros(3), np.array([1, 0, 0, 0])))

    async def targets(**kwargs):
        return [], 0.0

    monkeypatch.setattr(jacobian_ik, "JacobianIKSolver", solver)
    monkeypatch.setattr(jacobian_ik, "_generate_fk_targets", targets)
    with pytest.raises(RuntimeError) as raised:
        await jacobian_ik.run_jacobian_ik(ctx, robot, info, {"settle_seconds": 0})
    if boundary == "solver_construction":
        assert raised.value.__cause__ is failure
    else:
        assert "zero targets" in str(raised.value)
    assert not ctx.skipped
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
async def test_lula_empty_targets_is_execution_gap(monkeypatch):
    ctx = Context()
    robot, info = scene()
    UsdGeom.Cube.Define(info["stage"], info["asset_prim"].GetPath().AppendChild("Geometry"))
    monkeypatch.setattr(ik_target_reach, "_try_build_ik_solver", lambda *args: (object(), "tool", "robot"))
    monkeypatch.setattr(ik_target_reach, "_lula_controlled_robot", lambda *args: robot)
    monkeypatch.setattr(ik_target_reach, "_get_ee_position", lambda *args: np.zeros(3))
    monkeypatch.setattr(ik_target_reach, "generate_ik_targets", lambda **kwargs: [])
    with pytest.raises(RuntimeError, match="target generator returned 0 targets"):
        await ik_target_reach.run_ik_target_reach(ctx, robot, info, {"settle_seconds": 0})
    assert ctx.recorded["ik_targets_total"] == 0
    assert not ctx.skipped


@pytest.mark.parametrize("owned_side", [0, 1])
@pytest.mark.parametrize("endpoint_form", ["forwarded_owned", "instance_proxy"])
def test_world_anchor_marker_supports_forwarded_and_instance_endpoints(monkeypatch, owned_side, endpoint_form):
    import sys

    from simready.foundation.tier_core.runtime_tests.fet003_physics.physics_checks import (
        has_active_owned_world_anchor,
    )

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    template = "/Template" if endpoint_form == "instance_proxy" else "/Robot"
    UsdGeom.Xform.Define(stage, template)
    body = UsdGeom.Xform.Define(stage, template + "/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    anchor = UsdPhysics.FixedJoint.Define(stage, template + "/world")
    sides = [anchor.CreateBody0Rel(), anchor.CreateBody1Rel()]
    sides[1 - owned_side].SetTargets([])
    if endpoint_form == "forwarded_owned":
        forwarded = root.CreateRelationship("forwardedBody")
        forwarded.SetTargets([body.GetPath()])
        sides[owned_side].SetTargets([forwarded.GetPath()])
    else:
        sides[owned_side].SetTargets([body.GetPath()])
        instance = UsdGeom.Xform.Define(stage, "/Robot/instance").GetPrim()
        instance.GetReferences().AddInternalReference(template)
        instance.SetInstanceable(True)
        assert stage.GetPrimAtPath("/Robot/instance/world").IsInstanceProxy()
    usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
    monkeypatch.setitem(sys.modules, "omni", SimpleNamespace(usd=usd))
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    ctx = Context()
    ctx.scene = SimpleNamespace(asset=SimpleNamespace(prim_path=str(root.GetPath())))
    assert has_active_owned_world_anchor(ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("trial", ["ground", "stability", "slope"])
@pytest.mark.parametrize("owned_side", [0, 1])
@pytest.mark.parametrize(
    "anchor_state",
    [
        "owned",
        "static",
        "disabled",
        "unrelated",
        "missing_target",
        "disabled_body",
        "multiple_targets",
        "forwarded_dynamic",
        "unloaded_sibling",
        "unresolved_sibling",
        "external_unloaded",
        "external_ancestor_unloaded",
        "external_forwarded_unloaded",
        "external_forwarding_owner_unloaded",
        "external_class",
        "external_class_ancestor",
        "external_undefined_ancestor",
        "external_static",
        "external_proxy_static",
        "sentinel_chain",
        "breakable_chain",
    ],
)
async def test_world_anchored_trials_only_mark_qualified_owned_anchor(monkeypatch, trial, owned_side, anchor_state):
    import sys

    from simready.foundation.tier_core.runtime_tests import engine_guard
    from simready.foundation.tier_core.runtime_tests.fet003_physics import (
        ground_drop,
        ground_stability,
        slope_drop,
    )

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    owner = "/Elsewhere" if anchor_state == "unrelated" else "/Robot"
    body = UsdGeom.Xform.Define(stage, owner + "/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    anchor = UsdPhysics.FixedJoint.Define(stage, owner + "/world")
    sides = [anchor.CreateBody0Rel(), anchor.CreateBody1Rel()]
    sides[owned_side].SetTargets([body.GetPath()])
    sides[1 - owned_side].SetTargets([])
    if anchor_state in ("sentinel_chain", "breakable_chain"):
        tip = UsdGeom.Xform.Define(stage, owner + "/tip").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(tip)
        edge = UsdPhysics.RevoluteJoint.Define(stage, owner + "/connection")
        edge.CreateBody0Rel().SetTargets([body.GetPath()])
        edge.CreateBody1Rel().SetTargets([tip.GetPath()])
        maximum = float.fromhex("0x1.fffffep+127")
        edge.CreateBreakForceAttr(maximum)
        edge.CreateBreakTorqueAttr(maximum if anchor_state == "sentinel_chain" else 1.0)
    elif anchor_state == "disabled":
        anchor.CreateJointEnabledAttr(False)
    elif anchor_state == "static":
        frame = UsdGeom.Xform.Define(stage, owner + "/frame").GetPrim()
        sides[1 - owned_side].SetTargets([frame.GetPath()])
    elif anchor_state == "missing_target":
        sides[1 - owned_side].SetTargets(["/Robot/missing"])
    elif anchor_state == "disabled_body":
        UsdPhysics.RigidBodyAPI(body).CreateRigidBodyEnabledAttr(False)
    elif anchor_state.startswith("external_"):
        from pxr import Sdf

        external = UsdGeom.Xform.Define(stage, "/External").GetPrim()
        endpoint = external
        if anchor_state in ("external_class_ancestor", "external_undefined_ancestor"):
            endpoint = UsdGeom.Xform.Define(stage, "/External/frame").GetPrim()
        if anchor_state == "external_class":
            external.SetSpecifier(Sdf.SpecifierClass)
        elif anchor_state == "external_class_ancestor":
            external.SetSpecifier(Sdf.SpecifierClass)
        elif anchor_state == "external_undefined_ancestor":
            external.SetSpecifier(Sdf.SpecifierOver)
            assert endpoint.GetSpecifier() == Sdf.SpecifierDef and not endpoint.IsDefined() and not external.IsDefined()
        elif anchor_state in ("external_unloaded", "external_ancestor_unloaded", "external_forwarded_unloaded"):
            definition = UsdGeom.Xform.Define(stage, "/DynamicDefinition").GetPrim()
            UsdPhysics.RigidBodyAPI.Apply(definition)
            if anchor_state == "external_ancestor_unloaded":
                endpoint = UsdGeom.Xform.Define(stage, "/External/frame").GetPrim()
            external.GetPayloads().AddInternalPayload("/DynamicDefinition")
            stage.Unload(external.GetPath())
        elif anchor_state == "external_proxy_static":
            UsdGeom.Xform.Define(stage, "/StaticDefinition/frame")
            external.GetReferences().AddInternalReference("/StaticDefinition")
            external.SetInstanceable(True)
            endpoint = stage.GetPrimAtPath("/External/frame")
            assert endpoint.IsInstanceProxy()
        if anchor_state in ("external_forwarded_unloaded", "external_forwarding_owner_unloaded"):
            forwarding_owner = root
            if anchor_state == "external_forwarding_owner_unloaded":
                forwarding_owner = UsdGeom.Xform.Define(stage, "/Alias").GetPrim()
                UsdGeom.Xform.Define(stage, "/AliasDefinition")
                forwarding_owner.GetPayloads().AddInternalPayload("/AliasDefinition")
            forwarded = forwarding_owner.CreateRelationship("externalFrame")
            forwarded.SetTargets([endpoint.GetPath()])
            sides[1 - owned_side].SetTargets([forwarded.GetPath()])
            if anchor_state == "external_forwarding_owner_unloaded":
                stage.Unload("/Alias")
        else:
            sides[1 - owned_side].SetTargets([endpoint.GetPath()])
    elif anchor_state in ("unloaded_sibling", "unresolved_sibling"):
        sibling = UsdGeom.Xform.Define(stage, "/Robot/controller").GetPrim()
        if anchor_state == "unloaded_sibling":
            UsdGeom.Xform.Define(stage, "/ControllerDefinition")
            sibling.GetPayloads().AddInternalPayload("/ControllerDefinition")
            stage.Unload("/Robot/controller")
        else:
            sibling.GetReferences().AddReference("outcome-r3-known-missing-reference.usda")
    elif anchor_state in ("multiple_targets", "forwarded_dynamic"):
        tip = UsdGeom.Xform.Define(stage, "/Robot/tip").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(tip)
        if anchor_state == "multiple_targets":
            sides[owned_side].SetTargets([body.GetPath(), tip.GetPath()])
        else:
            forwarded = root.CreateRelationship("forwardedBody")
            forwarded.SetTargets([tip.GetPath()])
            sides[1 - owned_side].SetTargets([forwarded.GetPath()])
    usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
    monkeypatch.setitem(sys.modules, "omni", SimpleNamespace(usd=usd))
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None, raising=False)
    room = SimpleNamespace(
        auto_size=lambda *args: None,
        set_color=lambda *args: None,
        show_ground=lambda **kwargs: None,
        add_slope=lambda **kwargs: None,
        place_asset_above_ground=lambda **kwargs: None,
        place_asset_on_slope=lambda **kwargs: None,
        _slope_high_end_y=1.0,
        _slope_half_len=1.0,
        _slope_angle_rad=0.5,
        _slope_sink=0.0,
    )
    ctx = Context()
    ctx.set_settle_frames = lambda count: None
    ctx.scene = SimpleNamespace(
        asset=SimpleNamespace(prim_path=str(root.GetPath())),
        load_asset=lambda *args, **kwargs: None,
        add_room=lambda: room,
    )
    kwargs, run = {
        "ground": (ground_drop.GROUND_DROP_KWARGS, ground_drop.run_ground_drop),
        "stability": (ground_stability.GROUND_STABILITY_KWARGS, ground_stability.run_ground_stability),
        "slope": (slope_drop.SLOPE_DROP_KWARGS, slope_drop.run_slope_drop),
    }[trial]
    ctx.config = dict(kwargs["config_defaults"])
    before = _stage_state(stage)
    await run(ctx)
    assert _stage_state(stage) == before
    if anchor_state in ("owned", "static", "external_static", "external_proxy_static", "sentinel_chain"):
        assert_not_applicable(ctx, "world_anchored")
    else:
        assert len(ctx.skipped) == 1
        assert "assessment_applicability" not in ctx.recorded
    if anchor_state in ("external_unloaded", "external_ancestor_unloaded", "external_forwarded_unloaded"):
        from simready.foundation.tier_core.runtime_tests.fet003_physics.physics_checks import (
            check_world_anchor,
            has_active_owned_world_anchor,
        )

        stage.Load("/External")
        assert not has_active_owned_world_anchor(ctx)
        # The historical precheck deliberately keeps its raw GetTargets policy.
        assert check_world_anchor(ctx) is (anchor_state == "external_forwarded_unloaded")


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["complete", "unloaded", "partial", "masked", "loaded_labels", "proxy_labels"])
async def test_no_semantics_in_renderable_sources_requires_complete_inspection(monkeypatch, scope):
    from pxr import Sdf
    from simready.foundation.tier_core.runtime_tests.fet011_semantics import seg_stripped

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdGeom.Cube.Define(stage, "/Asset/body")
    if scope != "complete":
        UsdGeom.Xform.Define(stage, "/Definition")
        labelled = UsdGeom.Cube.Define(stage, "/Definition/labelled").GetPrim()
        labelled.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["SemanticsLabelsAPI:class"]))
        owner = root if scope == "unloaded" else UsdGeom.Xform.Define(stage, "/Asset/labels").GetPrim()
        if scope == "proxy_labels":
            owner.GetReferences().AddInternalReference("/Definition")
            owner.SetInstanceable(True)
            assert stage.GetPrimAtPath("/Asset/labels/labelled").IsInstanceProxy()
        else:
            owner.GetPayloads().AddInternalPayload("/Definition")
        if scope in ("unloaded", "partial"):
            stage.Unload(owner.GetPath())
        elif scope == "masked":
            stage.SetPopulationMask(Usd.StagePopulationMask(["/Asset/body"]))

    ctx = Context()
    ctx.config = dict(seg_stripped.common.SHARED_CONFIG, off_coverage_max=0.002)
    room = SimpleNamespace(auto_size=lambda *args: None, set_color=lambda *args: None, hide_ground=lambda: None)
    ctx.scene = SimpleNamespace(
        stage=stage,
        asset=SimpleNamespace(prim_path="/Asset"),
        load_asset=lambda *args, **kwargs: None,
        add_room=lambda: room,
        lighting=SimpleNamespace(add_dome=lambda **kwargs: None),
        auto_frame_camera=lambda **kwargs: None,
    )

    async def settle(**kwargs):
        pass

    ctx.settle = settle
    if scope in ("loaded_labels", "proxy_labels"):

        async def required_render(*args):
            raise RuntimeError("stripped real labels reached required renderer")

        monkeypatch.setattr(seg_stripped.common, "read_segmentation", required_render)
        with pytest.raises(RuntimeError, match="required renderer"):
            await seg_stripped.test_semantic_labels_seg_stripped(ctx)
        assert ctx.recorded["semantic_labels_stripped_prims"] == 1
        assert not ctx.skipped
        assert "assessment_applicability" not in ctx.recorded
        return
    await seg_stripped.test_semantic_labels_seg_stripped(ctx)
    if scope == "complete":
        assert_not_applicable(ctx, "no_applicable_semantics")
    else:
        assert ctx.recorded["semantic_labels_stripped_prims"] == 0
        assert len(ctx.skipped) == 1
        assert "assessment_applicability" not in ctx.recorded

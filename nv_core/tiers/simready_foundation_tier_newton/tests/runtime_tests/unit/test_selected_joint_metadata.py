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
import math
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases._independent_dofs import (
    control_ownership,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.mimic_joints import (
    detect_mimic_joints,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_utils import (
    resolve_usd_max_velocities,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.passive_joints import (
    detect_passive_joints,
)


def physical_asset(active=True, foreign_kind="container"):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    UsdPhysics.ArticulationRootAPI.Apply(asset)
    for prefix, gain, speed in (
        ("/Asset", 100.0 if active else 0.0, 60.0),
        ("/Asset/Foreign", 0.0 if active else 100.0, 600.0),
    ):
        for name in ("base", "left", "right"):
            UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, prefix + "/" + name).GetPrim())
        if prefix.endswith("Foreign"):
            UsdPhysics.ArticulationRootAPI.Apply(
                stage.GetPrimAtPath(prefix + ("/base" if foreign_kind == "body" else ""))
            )
        for name, tip in (("leader", "left"), ("follower", "right")):
            joint = UsdPhysics.RevoluteJoint.Define(stage, prefix + "/Constraints/" + name)
            endpoints = [prefix + "/base", prefix + "/" + tip]
            if prefix.endswith("Foreign"):
                endpoints.reverse()
            joint.CreateBody0Rel().SetTargets([endpoints[0]])
            joint.CreateBody1Rel().SetTargets([endpoints[1]])
            UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(gain)
            joint.GetPrim().CreateAttribute(
                "physxDrivePerformanceEnvelope:angular:maxActuatorVelocity", Sdf.ValueTypeNames.Float
            ).Set(speed)
    return stage, SimpleNamespace(prim_path="/Asset", asset_prim=asset, dof_names=["follower", "leader"])


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("foreign_kind", ["body", "container"])
def test_passive_consumer_uses_selected_effective_gains(active, foreign_kind):
    stage, robot = physical_asset(active, foreign_kind)
    indices, names = detect_passive_joints(stage, robot.prim_path, robot.dof_names, robot.asset_prim)
    assert indices == (frozenset() if active else frozenset({0, 1}))
    assert names == ([] if active else ["follower", "leader"])


@pytest.mark.parametrize("qualified", [False, True])
def test_velocity_consumer_uses_selected_joint_not_foreign_duplicate(qualified):
    stage, robot = physical_asset()
    result = resolve_usd_max_velocities(
        stage, robot.prim_path, robot.dof_names, robot.asset_prim, robot.asset_prim, reject_unlimited=qualified
    )
    assert np.allclose(result, [math.pi / 3, math.pi / 3])


def test_foreign_only_coupling_never_enters_mim_phase_or_setup():
    stage, robot = physical_asset()
    follower = stage.GetPrimAtPath("/Asset/Foreign/Constraints/follower")
    follower.AddAppliedSchema("NewtonMimicAPI")
    follower.CreateRelationship("newton:mimicJoint").SetTargets(["/Asset/Foreign/Constraints/leader"])
    follower.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Double).Set(0.0)
    follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Double).Set(1.0)
    assert detect_mimic_joints(stage, robot.asset_prim, robot.prim_path, robot.dof_names) == []
    assert control_ownership(stage, robot.asset_prim, robot.prim_path, robot.dof_names) == (set(), [], set(), [])


@pytest.mark.asyncio
async def test_newton_default_ikr_consumes_selected_velocity_in_actual_target_playback(monkeypatch):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
        ik_target_reach as phase,
    )
    from test_jik_velocity_playback import Context, Robot

    stage, selected = physical_asset(foreign_kind="body")
    robot = Robot()
    robot.dof_names = selected.dof_names
    robot.prim_path = selected.prim_path
    robot.hints = [20.0, 20.0]
    robot.get_joint_position_limits = lambda: (np.full(2, -10.0), np.full(2, 10.0))
    robot.set_joint_position_targets = lambda values: setattr(robot, "target", np.asarray(values).copy())
    ctx = Context(robot)
    scene = {"stage": stage, "asset_prim": selected.asset_prim, "robot_root_prim": selected.asset_prim}
    monkeypatch.setattr(phase, "compute_world_aligned_bbox", lambda *args: None)
    monkeypatch.setattr(phase, "freeze_bbox_reference", lambda *args: None)
    inputs = await phase._gather_motion_inputs(ctx, robot, scene, [])
    np.testing.assert_allclose(inputs["merged_vels"], [math.pi / 3, math.pi / 3])
    observed = []
    original = phase._compute_motion_duration_seconds

    def duration(**kwargs):
        observed.append(kwargs["max_velocities"].copy())
        return original(**kwargs)

    monkeypatch.setattr(phase, "_compute_motion_duration_seconds", duration)
    monkeypatch.setattr(phase, "_compute_target_error", lambda *args: 1.0)

    async def no_reset(*args, **kwargs):
        pass

    monkeypatch.setattr(phase, "_teleport_to_joints", no_reset)
    monkeypatch.setattr(phase, "_capture_and_step_burst", no_reset)
    target = SimpleNamespace(index=0, is_reachable=True, position=np.zeros(3))
    solution = phase._IKPrecomputeSolution(target, np.array([1.0, 1.0]), True, "ok")
    metrics = {
        "wraparound_corrections": 0,
        "joint_limit_violations": 0,
        "motion_timeouts": 0,
        "motion_failed_reachable": 0,
    }
    result = await phase._execute_one_target(
        ctx,
        robot,
        object(),
        solution,
        [],
        10000,
        inputs,
        metrics,
        phase._build_motion_cfg(phase.get_defaults(), 240),
        scene,
    )
    assert not result["ok"]  # Required live EE error still governs the unchanged verdict.
    assert ctx.steps == 360  # Existing default 1.5-second min/max remains unchanged.
    np.testing.assert_allclose(observed[0], [math.pi / 3, math.pi / 3])


@pytest.mark.parametrize("path_alias", [False, True])
def test_native_aliases_keep_selected_mimic_and_velocity_identity(path_alias):
    stage, robot = physical_asset()
    prefix = "/Asset/Constraints/" if path_alias else ""
    robot.dof_names = [prefix + "follower:0", prefix + "leader:0"]
    follower = stage.GetPrimAtPath("/Asset/Constraints/follower")
    follower.AddAppliedSchema("NewtonMimicAPI")
    follower.CreateRelationship("newton:mimicJoint").SetTargets(["/Asset/Constraints/leader"])
    follower.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Double).Set(0.0)
    follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Double).Set(1.0)
    assert detect_passive_joints(stage, robot.prim_path, robot.dof_names, robot.asset_prim)[0] == frozenset()
    np.testing.assert_allclose(
        resolve_usd_max_velocities(stage, robot.prim_path, robot.dof_names, robot.asset_prim, robot.asset_prim),
        [math.pi / 3] * 2,
    )
    pairs = detect_mimic_joints(stage, robot.asset_prim, robot.prim_path, robot.dof_names)
    assert len(pairs) == 1 and pairs[0].follower_dof_index == 0 and pairs[0].reference_dof_index == 1
    assert control_ownership(stage, robot.asset_prim, robot.prim_path, robot.dof_names)[0] == {0}

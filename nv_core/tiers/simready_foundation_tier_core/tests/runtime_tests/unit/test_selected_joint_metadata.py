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
from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
    control_ownership,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.mimic_joints import (
    detect_mimic_joints,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_utils import (
    resolve_usd_max_velocities,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
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
async def test_core_initialize_writes_selected_authored_caps_to_native_adapter(monkeypatch):
    import sys

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )
    from test_robot_handle_authored_scale import _fake_isaac

    stage, selected = physical_asset(foreign_kind="body")
    _fake_isaac(monkeypatch, stage)
    writes = []
    adapter = SimpleNamespace(
        dof_names=selected.dof_names,
        get_max_joint_velocities=lambda: writes[-1] if writes else np.array([20.0, 20.0]),
        set_max_joint_velocities=lambda values: writes.append(np.asarray(values).copy()),
    )
    monkeypatch.setattr(sys.modules["isaacsim.core.prims"], "SingleArticulation", lambda **kwargs: adapter)
    robot = RobotHandle(stage, selected.prim_path, selected.asset_prim, None)
    warnings = []
    await robot.initialize(SimpleNamespace(step=lambda *args: None, warn=warnings.append))
    assert not warnings
    assert len(writes) == 1
    np.testing.assert_allclose(writes[0].ravel(), [math.pi / 3, math.pi / 3], rtol=1e-6)


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["reject", "partial", "nonfinite", "read_error", "healthy", "no_getter", "legacy", "mixed", "no_hints"]
)
async def test_authored_cap_initialize_requires_complete_acknowledgement(monkeypatch, mode):
    import sys

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )
    from test_robot_handle_authored_scale import _fake_isaac

    stage, selected = physical_asset()
    calls, _ = _fake_isaac(monkeypatch, stage)
    primary = OSError("required native cap operation failed")
    writes = []

    def setter(values, *args):
        writes.append(np.asarray(values).copy())
        if mode == "reject":
            raise primary

    def getter():
        if mode == "read_error":
            raise primary
        values = writes[-1].ravel().copy()
        if mode == "partial":
            return values[:1]
        if mode == "nonfinite":
            values[-1] = np.nan
        return values

    adapter = SimpleNamespace(dof_names=selected.dof_names, set_max_joint_velocities=setter)
    if mode != "no_getter":
        adapter.get_max_joint_velocities = getter
    if mode == "legacy":
        del adapter.set_max_joint_velocities
        del adapter.get_max_joint_velocities
        adapter._physics_view = SimpleNamespace(set_dof_max_velocities=setter, get_dof_max_velocities=getter)
    if mode in ("mixed", "no_hints"):
        for name in (["leader"] if mode == "mixed" else ["leader", "follower"]):
            stage.GetPrimAtPath("/Asset/Constraints/" + name).RemoveProperty(
                "physxDrivePerformanceEnvelope:angular:maxActuatorVelocity"
            )
        adapter._articulation_view = SimpleNamespace(get_joint_max_velocities=lambda: np.array([20.0, 30.0]))
    monkeypatch.setattr(sys.modules["isaacsim.core.prims"], "SingleArticulation", lambda **kwargs: adapter)
    robot = RobotHandle(stage, selected.prim_path, selected.asset_prim, None)
    session = SimpleNamespace(_world_managed_timeline=False)
    ctx = SimpleNamespace(step=lambda *args: None, warn=lambda *args: None, _engine_session=session)
    if mode in ("reject", "partial", "nonfinite", "read_error"):
        with pytest.raises(Exception) as caught:
            await robot.initialize(ctx)
        if mode in ("reject", "read_error"):
            assert caught.value is primary
        assert not robot._initialized
        assert session._world_managed_timeline
        robot.teardown(required=True)
        assert robot._world is None and robot._articulation is None
        assert sum(call[0] == "clear" for call in calls) >= 2
    else:
        await robot.initialize(ctx)
        assert robot._initialized
        if mode == "no_hints":
            assert not writes
        else:
            expected = [math.pi / 3, 30.0 if mode == "mixed" else math.pi / 3]
            np.testing.assert_allclose(writes[-1].ravel(), expected, rtol=1e-6)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_rejected_initial_cap_preserves_primary_and_retires_failed_cleanup(monkeypatch, cancel):
    import sys

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )
    from test_robot_handle_authored_scale import _fake_isaac

    stage, selected = physical_asset()
    _fake_isaac(monkeypatch, stage)
    primary = KeyboardInterrupt("cancel cap setup") if cancel else OSError("cap setter rejected")
    cleanup = OSError("required world cleanup rejected")

    def reject(*args):
        raise primary

    adapter = SimpleNamespace(dof_names=selected.dof_names, set_max_joint_velocities=reject)
    monkeypatch.setattr(sys.modules["isaacsim.core.prims"], "SingleArticulation", lambda **kwargs: adapter)
    attempts = []

    def teardown(self, required=False):
        attempts.append(required)
        raise cleanup

    monkeypatch.setattr(RobotHandle, "teardown", teardown)
    retired = []
    session = SimpleNamespace(_world_managed_timeline=False, record_required_cleanup_failure=retired.append)
    robot = RobotHandle(stage, selected.prim_path, selected.asset_prim, None)
    with pytest.raises(BaseException) as caught:
        await robot.initialize(SimpleNamespace(step=lambda *args: None, _engine_session=session))
    assert caught.value is primary
    assert attempts == [True] and len(retired) == 1
    assert session._world_managed_timeline and not robot._initialized
    assert "required world cleanup rejected" in "\n".join(primary.__notes__)


@pytest.mark.parametrize("throwing_getter", [False, True])
def test_legacy_cap_fallback_cannot_evade_available_required_readback(throwing_getter):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )

    stage, selected = physical_asset()
    primary = OSError("public setter rejected")
    read_error = OSError("public getter rejected")
    writes = []

    def reject(*args):
        raise primary

    def getter():
        if throwing_getter:
            raise read_error
        return writes[-1]

    adapter = SimpleNamespace(
        dof_names=selected.dof_names,
        set_max_joint_velocities=reject,
        get_max_joint_velocities=getter,
        _physics_view=SimpleNamespace(set_dof_max_velocities=lambda values, indices: writes.append(values)),
    )
    robot = RobotHandle(stage, selected.prim_path, selected.asset_prim, None)
    robot._articulation = adapter
    if throwing_getter:
        with pytest.raises(OSError) as caught:
            robot.apply_velocity_limits_to_tensor_view(np.array([1.0, 1.0]))
        assert caught.value is primary
    else:
        assert robot.apply_velocity_limits_to_tensor_view(np.array([1.0, 1.0]))
    assert len(writes) == 1

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

import builtins
import math
from types import SimpleNamespace

import numpy as np
import pxr
import pytest
from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach,
    motion_utils,
    velocity_limit,
)
from test_selected_joint_metadata import physical_asset


def velocity_asset(monkeypatch, form, path_alias=False):
    stage, robot = physical_asset(foreign_kind="body")
    name = (
        "physxJoint:maxJointVelocity"
        if form == "legacy"
        else "physxDrivePerformanceEnvelope:angular:maxActuatorVelocity"
    )
    if form == "legacy":
        for prefix in ("/Asset", "/Asset/Foreign"):
            for joint_name in ("leader", "follower"):
                prim = stage.GetPrimAtPath(prefix + "/Constraints/" + joint_name)
                prim.RemoveProperty("physxDrivePerformanceEnvelope:angular:maxActuatorVelocity")
                prim.CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(60.0 if prefix == "/Asset" else 600.0)
    # Legacy schema adapter delegates to actual USD, not fabricated limit arrays.
    schema = SimpleNamespace(
        PhysxJointAPI=SimpleNamespace(
            Get=lambda st, path: SimpleNamespace(
                GetMaxJointVelocityAttr=lambda: st.GetPrimAtPath(path).GetAttribute("physxJoint:maxJointVelocity")
            )
        )
    )
    monkeypatch.setattr(pxr, "PhysxSchema", schema, raising=False)
    if path_alias:
        robot.dof_names = ["/Asset/Constraints/follower:0", "/Asset/Constraints/leader:0"]
    robot.dof_count = 2
    robot.get_joint_position_limits = lambda: (np.full(2, -1.0), np.full(2, 1.0))
    robot.get_joint_velocity_limits = lambda: np.full(2, 20.0)
    return stage, robot, name


def fail_query(monkeypatch, name, method, primary, prefix="/Asset/Constraints/"):
    owner = Usd.Prim if method == "GetAttribute" else Usd.Attribute
    original = getattr(owner, method)

    def query(obj, *args, **kwargs):
        path = str(obj.GetPath()) + ("." + args[0] if method == "GetAttribute" else "")
        if path.startswith(prefix) and path.endswith("." + name):
            raise primary
        return original(obj, *args, **kwargs)

    monkeypatch.setattr(owner, method, query)


def resolve(stage, robot, qualified=True):
    return motion_utils.resolve_usd_max_velocities(
        stage,
        robot.prim_path,
        robot.dof_names,
        robot.asset_prim,
        robot.asset_prim,
        reject_unlimited=qualified,
    )


async def gather(monkeypatch, stage, robot):
    monkeypatch.setattr(ik_target_reach, "compute_world_aligned_bbox", lambda *args: None)
    monkeypatch.setattr(ik_target_reach, "freeze_bbox_reference", lambda *args: None)

    async def capture(**kwargs):
        return None

    ctx = SimpleNamespace(capture_frame=capture, scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None))
    return await ik_target_reach._gather_motion_inputs(ctx, robot, {"stage": stage, "asset_prim": robot.asset_prim}, [])


@pytest.mark.asyncio
@pytest.mark.parametrize("form", ["legacy", "envelope"])
@pytest.mark.parametrize("method", ["Get", "HasAuthoredValue", "GetAttribute"])
@pytest.mark.parametrize("path_alias", [False, True])
@pytest.mark.parametrize("consumer", ["resolver", "vel", "ikr"])
async def test_selected_query_error_cannot_become_native_ceiling(monkeypatch, form, method, path_alias, consumer):
    stage, robot, name = velocity_asset(monkeypatch, form, path_alias)
    primary = OSError("selected authored query failed")
    fail_query(monkeypatch, name, method, primary)
    with pytest.raises(OSError) as caught:
        if consumer == "resolver":
            resolve(stage, robot)
        elif consumer == "vel":
            find_candidates = velocity_limit.find_joints_with_velocity_limits

            def stop_after_eligibility(*args, **kwargs):
                candidates = find_candidates(*args, **kwargs)
                raise OSError("VEL incorrectly continued with ceilings: " + repr(candidates))

            monkeypatch.setattr(velocity_limit, "find_joints_with_velocity_limits", stop_after_eligibility)
            await velocity_limit.run_velocity_limit(
                SimpleNamespace(step=lambda *args: None),
                robot,
                {"stage": stage, "asset_prim": robot.asset_prim},
                velocity_limit.get_defaults(),
            )
        else:
            await gather(monkeypatch, stage, robot)
    assert caught.value is primary
    assert "/Asset/Constraints/follower." + name in "\n".join(primary.__notes__)


@pytest.mark.parametrize("method", [None, "Get", "HasAuthoredValue"])
def test_installed_legacy_schema_reads_real_usd_and_preserves_query_failure(monkeypatch, method):
    PhysxSchema = pytest.importorskip("physx_usd_schemas.PhysxSchema")
    if not Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("PhysxJointAPI"):
        pytest.skip("PhysX plugin was not available when this process initialized the USD schema registry")

    stage, robot = physical_asset()
    for name in ("leader", "follower"):
        prim = stage.GetPrimAtPath("/Asset/Constraints/" + name)
        PhysxSchema.PhysxJointAPI.Apply(prim).CreateMaxJointVelocityAttr(30.0)
    monkeypatch.setattr(pxr, "PhysxSchema", PhysxSchema, raising=False)
    if method is None:
        np.testing.assert_allclose(resolve(stage, robot), [math.pi / 6] * 2)
    else:
        primary = OSError("installed schema attribute query failed")
        fail_query(monkeypatch, "physxJoint:maxJointVelocity", method, primary)
        with pytest.raises(OSError) as caught:
            resolve(stage, robot)
        assert caught.value is primary


@pytest.mark.parametrize("form", ["legacy", "envelope"])
@pytest.mark.parametrize("method", ["Get", "HasAuthoredValue"])
def test_independent_direct_timing_reader_keeps_qualified_query_errors(monkeypatch, form, method):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import sweep_timing

    stage, robot, name = velocity_asset(monkeypatch, form)
    primary = OSError("direct timing read failed")
    fail_query(monkeypatch, name, method, primary)
    with pytest.raises(OSError) as caught:
        sweep_timing.resolve_velocity_hints(robot, {"stage": stage, "asset_prim": robot.asset_prim})
    assert caught.value is primary


@pytest.mark.parametrize("form", ["legacy", "envelope"])
@pytest.mark.parametrize("method", ["Get", "HasAuthoredValue", "GetAttribute"])
def test_foreign_shadow_query_failure_is_not_selected(monkeypatch, form, method):
    stage, robot, name = velocity_asset(monkeypatch, form, True)
    fail_query(monkeypatch, name, method, OSError("foreign query"), "/Asset/Foreign/")
    np.testing.assert_allclose(resolve(stage, robot), [math.pi / 3] * 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("form", ["legacy", "envelope"])
@pytest.mark.parametrize("value", ["absent", "blocked", "bad_string", 0.0, -1.0, float("nan"), float("inf"), 60.0])
async def test_optional_values_preserve_eligibility_and_ikr_policy(monkeypatch, form, value):
    stage, robot, name = velocity_asset(monkeypatch, form)
    prim = stage.GetPrimAtPath("/Asset/Constraints/follower")
    if value == "absent":
        prim.RemoveProperty(name)
    elif value == "blocked":
        prim.GetAttribute(name).Block()
    elif value == "bad_string":
        prim.RemoveProperty(name)
        prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set("not a speed")
    else:
        prim.GetAttribute(name).Set(value)
    expected = math.pi / 3 if value == 60.0 else 20.0
    candidates = velocity_limit.find_joints_with_velocity_limits(robot, resolve(stage, robot))
    assert candidates[0]["max_velocity"] == pytest.approx(expected)
    assert candidates[0]["max_velocity_source"] == ("dof_or_usd_min" if value == 60.0 else "dof")
    inputs = await gather(monkeypatch, stage, robot)
    np.testing.assert_allclose(inputs["merged_vels"], [expected, math.pi / 3])


@pytest.mark.parametrize("qualified", [False, True])
def test_legacy_precedence_conversion_and_unlimited_policy(monkeypatch, qualified):
    stage, robot, name = velocity_asset(monkeypatch, "legacy")
    prim = stage.GetPrimAtPath("/Asset/Constraints/follower")
    prim.CreateAttribute("physxDrivePerformanceEnvelope:angular:maxActuatorVelocity", Sdf.ValueTypeNames.Float).Set(
        30.0
    )
    assert resolve(stage, robot, qualified)[0] == pytest.approx(math.pi / 3)
    prim.GetAttribute(name).Set(3.4028234663852886e38)
    expected = math.pi / 6 if qualified else 3.4028234663852886e38 * math.pi / 180
    assert resolve(stage, robot, qualified)[0] == pytest.approx(expected)
    UsdPhysics.PrismaticJoint.Define(stage, prim.GetPath())
    prim.GetAttribute(name).Set(60.0)
    assert resolve(stage, robot, qualified)[0] == 60.0


def test_missing_optional_schema_support_keeps_envelope(monkeypatch):
    stage, robot, _ = velocity_asset(monkeypatch, "envelope")
    original = builtins.__import__

    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "physx_usd_schemas" or (name == "pxr" and "PhysxSchema" in fromlist):
            raise ImportError("optional schema unavailable")
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", importing)
    np.testing.assert_allclose(resolve(stage, robot), [math.pi / 3] * 2)


@pytest.mark.parametrize("form", ["legacy", "envelope"])
@pytest.mark.parametrize("error_type", [TypeError, ValueError])
def test_query_type_and_value_errors_are_not_numeric_conversion_absence(monkeypatch, form, error_type):
    stage, robot, name = velocity_asset(monkeypatch, form)
    primary = error_type("required query failed before numeric conversion")
    fail_query(monkeypatch, name, "Get", primary)
    with pytest.raises(error_type) as caught:
        resolve(stage, robot, qualified=False)
    assert caught.value is primary


@pytest.mark.parametrize("value", ["malformed", 0.0, float("nan")])
def test_envelope_conversion_failure_preserves_instance_fallback_boundary(monkeypatch, value):
    stage, robot, name = velocity_asset(monkeypatch, "envelope")
    prim = stage.GetPrimAtPath("/Asset/Constraints/follower")
    if value == "malformed":
        prim.RemoveProperty(name)
        prim.CreateAttribute(name, Sdf.ValueTypeNames.String).Set(value)
    else:
        prim.GetAttribute(name).Set(value)
    prim.CreateAttribute("physxDrivePerformanceEnvelope:linear:maxActuatorVelocity", Sdf.ValueTypeNames.Float).Set(30.0)
    # Existing unqualified IKR/setup policy: failed conversion ends Form2;
    # numeric unusable values still allow its historical next-instance lookup.
    actual = resolve(stage, robot, qualified=False)[0]
    if value == "malformed":
        assert np.isnan(actual)
    else:
        assert actual == pytest.approx(math.pi / 6)


def test_supported_legacy_schema_access_error_preserves_first_cause(monkeypatch):
    stage, robot, name = velocity_asset(monkeypatch, "legacy")
    primary = OSError("supported schema query failed")

    def get(*args):
        raise primary

    monkeypatch.setattr(pxr.PhysxSchema.PhysxJointAPI, "Get", get)
    with pytest.raises(OSError) as caught:
        resolve(stage, robot)
    assert caught.value is primary
    assert "/Asset/Constraints/follower." + name in "\n".join(primary.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("form", ["legacy", "envelope"])
@pytest.mark.parametrize("method", ["Get", "HasAuthoredValue"])
@pytest.mark.parametrize("fault", ["ordinary", "cleanup", "diagnostics", "cancel"])
async def test_initialize_query_failure_tears_down_and_preserves_primary(monkeypatch, form, method, fault):
    import sys

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )
    from test_robot_handle_authored_scale import _fake_isaac

    stage, selected, name = velocity_asset(monkeypatch, form)
    calls, world = _fake_isaac(monkeypatch, stage)

    class BadNoteError(OSError):
        def add_note(self, message):
            raise RuntimeError("note unavailable")

    primary = (
        KeyboardInterrupt("cancel query")
        if fault == "cancel"
        else BadNoteError("query failed") if fault == "diagnostics" else OSError("query failed")
    )
    fail_query(monkeypatch, name, method, primary)
    writes, messages, retired = [], [], []
    adapter = SimpleNamespace(
        dof_names=selected.dof_names, set_max_joint_velocities=lambda values: writes.append(values)
    )
    monkeypatch.setattr(sys.modules["isaacsim.core.prims"], "SingleArticulation", lambda **kwargs: adapter)
    if fault in ("cleanup", "diagnostics"):
        original_clear = world.clear_instance

        def clear():
            original_clear()
            if sum(call[0] == "clear" for call in calls) > 1:
                raise OSError("world cleanup failed")

        monkeypatch.setattr(world, "clear_instance", staticmethod(clear))
    session = SimpleNamespace(_world_managed_timeline=False, record_required_cleanup_failure=retired.append)
    robot = RobotHandle(stage, selected.prim_path, selected.asset_prim, None)
    with pytest.raises(BaseException) as caught:
        await robot.initialize(SimpleNamespace(step=messages.append, _engine_session=session))
    assert caught.value is primary
    assert not robot._initialized and not writes
    assert robot._world is None and robot._articulation is None
    assert sum(call[0] == "clear" for call in calls) >= 2
    assert session._world_managed_timeline
    assert not any("no joint authored" in message for message in messages)
    assert bool(retired) == (fault in ("cleanup", "diagnostics"))

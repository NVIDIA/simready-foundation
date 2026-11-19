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
import sys
from types import SimpleNamespace

import pytest
from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_core.runtime_tests.fet004_multibody import _drive_state, joint_movement


@pytest.fixture(autouse=True)
def _isolated_host_retirement_latch(monkeypatch):
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)


def _rig(existing=False, session=False):
    stage = Usd.Stage.CreateInMemory()
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/World/Asset/Joint")
    if existing:
        drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular")
        drive.CreateStiffnessAttr(123.0)
        drive.CreateDampingAttr(4.0)
        drive.CreateTargetVelocityAttr().Set(5.0, 1.0)  # Preserve samples, not a guessed default.
        joint.GetPrim().GetAttribute("drive:angular:physics:stiffness").SetCustomDataByKey("owner", "asset")
    if session:
        stage.SetEditTarget(stage.GetSessionLayer())
    return stage, str(joint.GetPath())


def _snapshot(stage):
    return stage.GetRootLayer().ExportToString(), stage.GetSessionLayer().ExportToString()


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("session", [False, True])
def test_actual_scalar_controls_restore_exact_local_specs_and_absence(existing, session):
    stage, path = _rig(existing, session)
    before = _snapshot(stage)
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 12.3, max_force=100.0)
    joint_movement._set_drive_damping(stage, path, "angular", 37.5, saved=saved)
    joint_movement._deactivate_drive_axis(stage, path, "angular", saved)
    assert _snapshot(stage) == before
    joint_movement._deactivate_drive_axis(stage, path, "angular", saved)  # Already restored is a no-op.
    assert _snapshot(stage) == before


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure_type", [RuntimeError, asyncio.CancelledError])
def test_partial_direct_activation_rolls_back_exact_state(monkeypatch, existing, failure_type):
    stage, path = _rig(existing, True)
    before = _snapshot(stage)
    primary = failure_type("required damping creation failed")

    def broken(*args, **kwargs):
        raise primary

    monkeypatch.setattr(UsdPhysics.DriveAPI, "CreateDampingAttr", broken)
    with pytest.raises(failure_type) as caught:
        joint_movement._activate_drive_axis(stage, path, "angular", 10.0)
    assert caught.value is primary and _snapshot(stage) == before


def test_rejected_actual_attribute_control_write_cannot_continue(monkeypatch):
    stage, path = _rig()
    before = _snapshot(stage)
    actual_set = Usd.Attribute.Set

    def reject(self, *args, **kwargs):
        if self.GetName() == "drive:angular:physics:damping":
            return False
        return actual_set(self, *args, **kwargs)

    monkeypatch.setattr(Usd.Attribute, "Set", reject)
    with pytest.raises(RuntimeError, match="control write was rejected"):
        joint_movement._activate_drive_axis(stage, path, "angular", 10.0)
    assert _snapshot(stage) == before


@pytest.mark.parametrize("field", ["targetVelocity", "damping", "maxForce"])
def test_stronger_zero_opinion_cannot_acknowledge_nonzero_tiny_control(field):
    stage, path = _rig()
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        api = UsdPhysics.DriveAPI.Apply(stage.GetPrimAtPath(path), "angular")
        creator = {
            "targetVelocity": api.CreateTargetVelocityAttr,
            "damping": api.CreateDampingAttr,
            "maxForce": api.CreateMaxForceAttr,
        }[field]
        creator(0.0)
    before = _snapshot(stage)
    state = _drive_state.capture_drive_state(stage, path, "angular")
    with pytest.raises(RuntimeError, match="readback disagrees"):
        _drive_state.activate_drive_state(state, 1e-8, 1e-8, max_force=1e-8)
    _drive_state.restore_drive_state(state)
    assert _snapshot(stage) == before


@pytest.mark.parametrize("field", ["stiffness", "damping", "targetVelocity", "maxForce"])
def test_valid_controls_use_native_float_representation(field):
    stage, path = _rig()
    api = UsdPhysics.DriveAPI.Apply(stage.GetPrimAtPath(path), "angular")
    _drive_state.required_drive_value(api, field, 12.3456789)


def test_originally_absent_target_stays_absent_after_restore():
    stage, path = _rig(True)
    api = UsdPhysics.DriveAPI(stage.GetPrimAtPath(path), "angular")
    api.GetTargetVelocityAttr().Clear()
    stage.GetPrimAtPath(path).RemoveProperty("drive:angular:physics:targetVelocity")
    before = _snapshot(stage)
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 0.1)
    joint_movement._deactivate_drive_axis(stage, path, "angular", saved)
    assert _snapshot(stage) == before
    assert not stage.GetPrimAtPath(path).GetAttribute("drive:angular:physics:targetVelocity").HasAuthoredValueOpinion()


def test_conflicting_owned_opinion_is_preserved_not_overwritten():
    stage, path = _rig(True)
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 0.1)
    UsdPhysics.DriveAPI(stage.GetPrimAtPath(path), "angular").GetDampingAttr().Set(333.0)
    with pytest.raises(RuntimeError, match="concurrent opinions"):
        joint_movement._deactivate_drive_axis(stage, path, "angular", saved)
    assert UsdPhysics.DriveAPI(stage.GetPrimAtPath(path), "angular").GetDampingAttr().Get() == 333.0


def test_partial_copy_restoration_can_retry_without_rewriting_completed_opinions(monkeypatch):
    stage, path = _rig(True, True)
    before = _snapshot(stage)
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 0.1)
    actual_copy = Sdf.CopySpec
    calls = []

    def reject_first(*args, **kwargs):
        calls.append(str(args[1]))
        if len(calls) == 1:
            return False
        return actual_copy(*args, **kwargs)

    # Session originally has no opinions, so use a root-authored target to exercise CopySpec.
    stage2, path2 = _rig(True)
    before2 = _snapshot(stage2)
    saved2 = joint_movement._activate_drive_axis(stage2, path2, "angular", 0.1)
    monkeypatch.setattr(Sdf, "CopySpec", reject_first)
    with pytest.raises(RuntimeError, match="original drive property restoration failed"):
        joint_movement._deactivate_drive_axis(stage2, path2, "angular", saved2)
    completed = {name for name, item in saved2["_undo"]["properties"].items() if item["restored"]}
    assert completed and not saved2["_undo"]["restored"]
    monkeypatch.setattr(Sdf, "CopySpec", actual_copy)
    joint_movement._deactivate_drive_axis(stage2, path2, "angular", saved2)
    assert _snapshot(stage2) == before2
    joint_movement._deactivate_drive_axis(stage, path, "angular", saved)
    assert _snapshot(stage) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("batched", [False, True])
@pytest.mark.parametrize("primary_type", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("cleanup_type", [None, RuntimeError, asyncio.CancelledError])
async def test_actual_trial_restores_only_after_qualified_stop_and_preserves_primary(
    monkeypatch, batched, primary_type, cleanup_type
):
    stage, path = _rig(True, True)
    before = _snapshot(stage)
    primary = primary_type("required native body observation failed")
    secondary = cleanup_type("native cleanup stop failed") if cleanup_type else None
    calls, retired = [], []

    def stop():
        calls.append("stop")
        if calls.count("stop") == 2 and secondary is not None:
            raise secondary

    async def settle(**kwargs):
        return None

    async def step():
        raise primary

    ctx = SimpleNamespace(
        settle=settle,
        physics_step=step,
        _engine_session=SimpleNamespace(record_required_cleanup_failure=retired.append),
    )
    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "JointTracker", lambda *args: None)
    physics = SimpleNamespace(stop=stop, play=lambda: calls.append("play"))
    joint = {"name": "joint", "prim_path": path, "type_name": "PhysicsRevoluteJoint"}
    with pytest.raises(primary_type) as caught:
        if batched:
            await joint_movement._run_batched_drive_sim(
                ctx, stage, [joint], {}, physics, 1, 10, 0.1, 10, 50, 1, 1, False, False, 1
            )
        else:
            await joint_movement._run_drive_sim(ctx, stage, [joint], {}, physics, "angular", 10, 1, 1, False, False, 1)
    assert caught.value is primary and calls == ["stop", "play", "stop"]
    if secondary is None:
        assert _snapshot(stage) == before and not retired
    else:
        # Do not alter schema/property topology while native stop remains unqualified.
        assert _snapshot(stage) != before and retired == ["Required Core scalar drive restoration failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize("batched", [False, True])
async def test_partial_runtime_activation_uses_caller_stop_barrier_before_undo(monkeypatch, batched):
    stage, path = _rig()
    before = _snapshot(stage)
    primary = RuntimeError("required damping creation failed")
    calls = []

    async def settle(**kwargs):
        return None

    def broken(*args, **kwargs):
        raise primary

    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(UsdPhysics.DriveAPI, "CreateDampingAttr", broken)
    ctx = SimpleNamespace(settle=settle)
    physics = SimpleNamespace(stop=lambda: calls.append("stop"), play=lambda: calls.append("play"))
    joint = {"name": "joint", "prim_path": path, "type_name": "PhysicsRevoluteJoint"}
    with pytest.raises(RuntimeError) as caught:
        if batched:
            await joint_movement._run_batched_drive_sim(
                ctx, stage, [joint], {}, physics, 1, 10, 0.1, 10, 50, 1, 1, False, False, 1
            )
        else:
            await joint_movement._run_drive_sim(ctx, stage, [joint], {}, physics, "angular", 10, 1, 1, False, False, 1)
    assert caught.value is primary and calls == ["stop", "play", "stop"] and _snapshot(stage) == before


@pytest.mark.parametrize("callback", ["missing", "raises", "rejects"])
@pytest.mark.parametrize("primary_type", [RuntimeError, asyncio.CancelledError])
def test_failed_stop_retires_process_independently_of_optional_callback(callback, primary_type):
    stage, path = _rig()
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 1.0)
    dirty = _snapshot(stage)
    primary = primary_type("original required observation failed")

    def rejected(reason):
        if callback == "raises":
            raise RuntimeError("optional retirement callback failed")
        return False

    def stop():
        raise RuntimeError("required native stop failed")

    ctx = SimpleNamespace(
        _engine_session=None if callback == "missing" else SimpleNamespace(record_required_cleanup_failure=rejected)
    )
    joint_movement._cleanup_drive_trials(ctx, stage, SimpleNamespace(stop=stop), {path: ("angular", saved)}, primary)
    assert sys._simready_evaluate_kit_engine_retired is True and _snapshot(stage) == dirty
    assert str(primary) == "original required observation failed"


def test_false_stop_acknowledgement_blocks_topology_undo_and_retires():
    stage, path = _rig()
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 1.0)
    dirty = _snapshot(stage)
    with pytest.raises(RuntimeError, match="Core scalar drive restoration") as caught:
        joint_movement._cleanup_drive_trials(
            None, stage, SimpleNamespace(stop=lambda: False), {path: ("angular", saved)}
        )
    assert "stop was rejected" in str(caught.value.__cause__)
    assert sys._simready_evaluate_kit_engine_retired is True and _snapshot(stage) == dirty


@pytest.mark.asyncio
async def test_failed_cleanup_latch_refuses_actual_execution_retry():
    from simready.evaluate_engine_kit.execution import execute_single_test

    stage, path = _rig()
    saved = joint_movement._activate_drive_axis(stage, path, "angular", 1.0)
    primary = RuntimeError("original required observation failed")
    joint_movement._cleanup_drive_trials(
        None, stage, SimpleNamespace(stop=lambda: False), {path: ("angular", saved)}, primary
    )
    result = await execute_single_test(
        SimpleNamespace(description="test", expected_video="test", version="1.0.0"), "asset", "out", {}
    )
    assert result["status"] == "error" and result["failure_category"] == "engine_runtime"
    assert "Restart Kit" in result["message"]

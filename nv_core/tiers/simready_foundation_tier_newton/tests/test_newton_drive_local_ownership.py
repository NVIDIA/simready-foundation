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
from simready.foundation.tier_newton.runtime_tests.fet004_multibody import (
    joint_movement,
    newton_drive,
)


@pytest.fixture(autouse=True)
def _isolate_retirement(monkeypatch):
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)


def _layers(stage):
    return stage.GetRootLayer().ExportToString(), stage.GetSessionLayer().ExportToString()


def _fixture(session=False, existing=False, linear=False):
    stage = Usd.Stage.CreateInMemory()
    joint_type = UsdPhysics.PrismaticJoint if linear else UsdPhysics.RevoluteJoint
    prim = joint_type.Define(stage, "/Assembly/Joint").GetPrim()
    dof = "linear" if linear else "angular"
    if existing:
        api = UsdPhysics.DriveAPI.Apply(prim, dof)
        api.CreateStiffnessAttr(123.0).SetCustomData({"owner": "source"})
        api.CreateTargetPositionAttr(0.25)
    if session:
        stage.SetEditTarget(stage.GetSessionLayer())
    return stage, prim, [{"prim_path": str(prim.GetPath()), "type_name": prim.GetTypeName()}]


@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("linear", [False, True])
def test_exact_local_opinions_and_absence_restore(session, existing, linear):
    stage, _prim, joints = _fixture(session, existing, linear)
    before = _layers(stage)
    saved = newton_drive.activate_newton_position_drives(stage, joints, {})
    # Restoration must use the saved edit layer, not the caller's new target.
    stage.SetEditTarget(stage.GetRootLayer() if session else stage.GetSessionLayer())
    newton_drive.restore_newton_position_drives(stage, saved)
    newton_drive.restore_newton_position_drives(stage, saved)
    assert _layers(stage) == before
    assert sys._simready_evaluate_kit_engine_retired is False


@pytest.mark.parametrize("session", [False, True])
def test_inherited_drive_is_restored_without_flattening(session):
    source, source_prim, _ = _fixture(existing=True)
    before_source = _layers(source)
    stage = Usd.Stage.CreateInMemory()
    prim = UsdPhysics.RevoluteJoint.Define(stage, "/Joint").GetPrim()
    prim.GetReferences().AddReference(source.GetRootLayer().identifier, source_prim.GetPath())
    if session:
        stage.SetEditTarget(stage.GetSessionLayer())
    before = _layers(stage)
    saved = newton_drive.activate_newton_position_drives(
        stage, [{"prim_path": "/Joint", "type_name": "PhysicsRevoluteJoint"}], {}
    )
    newton_drive.restore_newton_position_drives(stage, saved)
    assert _layers(stage) == before and _layers(source) == before_source
    assert UsdPhysics.DriveAPI(prim, "angular").GetStiffnessAttr().Get() == 123.0


@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize("changed_path", ["/Assembly", "/Assembly/Joint"])
@pytest.mark.parametrize("specifier", [Sdf.SpecifierDef, Sdf.SpecifierClass])
def test_concurrent_unowned_prim_specifier_survives_empty_over_cleanup(session, changed_path, specifier):
    source, _prim, _joints = _fixture()
    source_before = source.GetRootLayer().ExportToString()
    stage = Usd.Stage.CreateInMemory()
    stage.GetRootLayer().subLayerPaths = [source.GetRootLayer().identifier]
    selected = stage.GetSessionLayer() if session else stage.GetRootLayer()
    stage.SetEditTarget(selected)
    expected = Sdf.Layer.CreateAnonymous("expected-unowned-specifier")
    expected.TransferContent(selected)
    expected_spec = Sdf.CreatePrimInLayer(expected, changed_path)
    expected_spec.specifier = specifier
    saved = newton_drive.activate_newton_position_drives(
        stage, [{"prim_path": "/Assembly/Joint", "type_name": "PhysicsRevoluteJoint"}], {}
    )
    selected.GetPrimAtPath(changed_path).specifier = specifier
    newton_drive.restore_newton_position_drives(stage, saved)
    assert selected.GetPrimAtPath(changed_path).specifier == specifier
    assert selected.ExportToString() == expected.ExportToString()
    assert source.GetRootLayer().ExportToString() == source_before
    assert sys._simready_evaluate_kit_engine_retired is False


@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize("stop_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt])
def test_partial_activation_rolls_back_every_prior_local_opinion(monkeypatch, session, stop_type):
    stage, _prim, joints = _fixture(session=session)
    # Define the second source joint before taking the owned-layer snapshot.
    second = UsdPhysics.RevoluteJoint.Define(stage, "/Assembly/Second").GetPrim()
    joints.append({"prim_path": str(second.GetPath()), "type_name": second.GetTypeName()})
    before = _layers(stage)
    original = stop_type("required damping authoring rejected")
    real_create = UsdPhysics.DriveAPI.CreateDampingAttr

    def rejected(api, *args, **kwargs):
        if str(api.GetPrim().GetPath()).endswith("Second"):
            raise original
        return real_create(api, *args, **kwargs)

    monkeypatch.setattr(UsdPhysics.DriveAPI, "CreateDampingAttr", rejected)
    with pytest.raises(stop_type) as caught:
        newton_drive.activate_newton_position_drives(stage, joints, {})
    assert caught.value is original and _layers(stage) == before
    assert sys._simready_evaluate_kit_engine_retired is False


@pytest.mark.parametrize("session", [False, True])
def test_rejected_required_control_write_cannot_become_response_verdict(monkeypatch, session):
    stage, _prim, joints = _fixture(session=session, existing=True)
    before = _layers(stage)
    actual = Usd.Attribute.Set

    def rejected(attr, *args, **kwargs):
        if attr.GetName().endswith("stiffness"):
            return False
        return actual(attr, *args, **kwargs)

    monkeypatch.setattr(Usd.Attribute, "Set", rejected)
    with pytest.raises(RuntimeError, match="write was not acknowledged"):
        newton_drive.activate_newton_position_drives(stage, joints, {})
    assert _layers(stage) == before


@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize("rejected_operation", ["copy", "remove", "metadata"])
def test_restore_rejected_ack_retires_and_retry_accepts_original_opinions(monkeypatch, session, rejected_operation):
    stage, prim, joints = _fixture(session=session, existing=rejected_operation == "copy")
    if rejected_operation == "copy":
        # Exercise a saved attribute spec in the selected layer, not inheritance.
        UsdPhysics.DriveAPI(prim, "angular").GetStiffnessAttr().Set(456.0)
    before = _layers(stage)
    saved = newton_drive.activate_newton_position_drives(stage, joints, {})
    reasons = []
    ctx = SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=reasons.append))
    if rejected_operation == "copy":
        target = Sdf
        name = "CopySpec"
    else:
        target = Sdf.PrimSpec
        name = "RemoveProperty" if rejected_operation == "remove" else "ClearInfo"
    actual = getattr(target, name)
    monkeypatch.setattr(target, name, lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError) as first:
        newton_drive.restore_newton_position_drives(stage, saved, ctx=ctx)
    assert first.value and reasons and sys._simready_evaluate_kit_engine_retired is True
    monkeypatch.setattr(target, name, actual)
    newton_drive.restore_newton_position_drives(stage, saved, ctx=ctx)
    assert _layers(stage) == before
    assert sys._simready_evaluate_kit_engine_retired is True  # Retry is not fresh-worker qualification.


@pytest.mark.parametrize("session", [False, True])
def test_concurrent_owned_edit_is_preserved_with_required_cleanup_error(session):
    stage, prim, joints = _fixture(session=session, existing=True)
    saved = newton_drive.activate_newton_position_drives(stage, joints, {})
    UsdPhysics.DriveAPI(prim, "angular").GetStiffnessAttr().Set(55.0)
    before_restore = _layers(stage)
    with pytest.raises(RuntimeError, match="changed concurrently"):
        newton_drive.restore_newton_position_drives(stage, saved)
    assert _layers(stage) == before_restore
    assert sys._simready_evaluate_kit_engine_retired is True


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("rejection", [False, RuntimeError, asyncio.CancelledError])
async def test_actual_caller_rejected_stop_never_authorizes_control_edits(monkeypatch, initial, rejection):
    stage, _prim, joints = _fixture(session=True)
    before = _layers(stage)
    at_trial = []
    calls = []
    stop_error = rejection("required stop failed") if rejection is not False else None
    ctx = SimpleNamespace()

    def stop():
        calls.append("stop")
        if initial or len(calls) > 1:
            if stop_error is not None:
                raise stop_error
            return False
        return None

    async def trial(*args):
        at_trial.append(_layers(stage))
        return "observed", []

    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "_run_newton_drive_sim_impl", trial)
    with pytest.raises(type(stop_error) if stop_error is not None else RuntimeError) as caught:
        await joint_movement._run_newton_drive_sim(
            ctx, stage, "/Assembly", joints, {}, SimpleNamespace(stop=stop), {}, 1, 1, False, 1
        )
    assert sys._simready_evaluate_kit_engine_retired is True
    if initial:
        assert calls == ["stop"] and not at_trial and _layers(stage) == before
        if stop_error is not None:
            assert caught.value is stop_error
    else:
        assert calls == ["stop", "stop"] and _layers(stage) == at_trial[0]


@pytest.mark.parametrize("session", [False, True])
def test_duplicate_owner_does_not_replace_earliest_undo(session):
    stage, _prim, joints = _fixture(session=session)
    before = _layers(stage)
    with pytest.raises(RuntimeError, match="Duplicate"):
        newton_drive.activate_newton_position_drives(stage, joints + joints, {})
    assert _layers(stage) == before


@pytest.mark.parametrize("value", [True, "10", float("nan"), -float("inf"), 1.0e40, 1.0e-50])
def test_invalid_control_input_is_rejected_before_mutation(value):
    stage, _prim, joints = _fixture()
    before = _layers(stage)
    with pytest.raises(RuntimeError, match="Invalid Newton"):
        newton_drive.activate_newton_position_drives(stage, joints, {"newton_drive_damping": value})
    assert _layers(stage) == before


def test_explicit_unlimited_force_and_valid_zero_gain_are_preserved():
    stage, prim, joints = _fixture()
    before = _layers(stage)
    saved = newton_drive.activate_newton_position_drives(
        stage, joints, {"drive_max_force": float("inf"), "newton_drive_stiffness_angular": 0.0}
    )
    api = UsdPhysics.DriveAPI(prim, "angular")
    assert api.GetMaxForceAttr().Get() == float("inf")
    assert api.GetStiffnessAttr().Get() == 0.0
    newton_drive.restore_newton_position_drives(stage, saved)
    assert _layers(stage) == before


@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize(
    "key",
    [
        "newton_drive_stiffness_angular",
        "newton_drive_stiffness_linear",
        "newton_drive_damping",
        "drive_max_force",
    ],
)
def test_negative_temporary_control_is_setup_error_before_mutation(session, key):
    stage, _prim, joints = _fixture(session=session, existing=True)
    before = _layers(stage)
    with pytest.raises(RuntimeError, match="nonnegative"):
        newton_drive.activate_newton_position_drives(stage, joints, {key: -1.0})
    assert _layers(stage) == before
    assert sys._simready_evaluate_kit_engine_retired is False


@pytest.mark.asyncio
@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize("stop_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize("primary_type", [None, RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("callback", ["missing", "rejected", "accepted"])
async def test_actual_caller_stop_barrier_preserves_owned_graph_and_primary(
    monkeypatch, session, stop_type, primary_type, callback
):
    stage, _prim, joints = _fixture(session=session)
    primary = primary_type("first required observation failed") if primary_type else None
    stop_error = stop_type("required stop rejected")
    calls = []
    at_trial = []
    reasons = []

    def stop():
        calls.append("stop")
        if len(calls) > 1:
            raise stop_error

    def rejected(_reason):
        raise KeyboardInterrupt("optional health delivery rejected")

    adapter = SimpleNamespace()
    if callback != "missing":
        adapter.record_required_cleanup_failure = reasons.append if callback == "accepted" else rejected
    ctx = SimpleNamespace(_engine_session=adapter)

    async def trial(*args):
        at_trial.append(_layers(stage))
        if primary is not None:
            raise primary
        return "observed", []

    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "_run_newton_drive_sim_impl", trial)
    with pytest.raises(primary_type if primary is not None else stop_type) as caught:
        await joint_movement._run_newton_drive_sim(
            ctx, stage, "/Assembly", joints, {}, SimpleNamespace(stop=stop), {}, 1, 1, False, 1
        )
    if primary is not None:
        assert caught.value is primary
    elif not isinstance(stop_error, Exception):
        assert caught.value is stop_error
    else:
        assert caught.value.__cause__ is stop_error
    assert calls == ["stop", "stop"] and _layers(stage) == at_trial[0]
    assert sys._simready_evaluate_kit_engine_retired is True

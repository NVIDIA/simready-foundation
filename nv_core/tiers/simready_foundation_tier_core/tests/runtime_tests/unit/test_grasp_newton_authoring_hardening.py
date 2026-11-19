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
import sys
import types

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.fet005_grasp import newton_articulation as native

try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema


def _stage(two_roots=False, reference_layer=None):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset")
    if reference_layer is not None:
        root.GetPrim().GetReferences().AddReference(reference_layer.identifier, "/Asset")
        return stage
    for name in ("a", "b") if two_roots else ("a",):
        parent = UsdGeom.Xform.Define(stage, "/Asset/" + name)
        child = UsdGeom.Xform.Define(stage, "/Asset/" + name + "_child")
        UsdPhysics.RigidBodyAPI.Apply(parent.GetPrim())
        UsdPhysics.RigidBodyAPI.Apply(child.GetPrim())
        joint = UsdPhysics.FixedJoint.Define(stage, "/Asset/" + name + "_joint")
        joint.GetBody0Rel().SetTargets([parent.GetPath()])
        joint.GetBody1Rel().SetTargets([child.GetPath()])
    return stage


def test_cleanup_restores_exact_reference_layer_and_local_opinions():
    source = _stage()
    root = source.GetPrimAtPath("/Asset/a")
    PhysxSchema.PhysxArticulationAPI.Apply(root).CreateEnabledSelfCollisionsAttr(True)
    original_source = source.GetRootLayer().ExportToString()
    stage = _stage(reference_layer=source.GetRootLayer())
    original_overlay = stage.GetRootLayer().ExportToString()
    mutations = native.apply_temporary_newton_articulations(stage, "/Asset")
    assert stage.GetPrimAtPath("/Asset/a").HasAPI(UsdPhysics.ArticulationRootAPI)
    assert (
        PhysxSchema.PhysxArticulationAPI(stage.GetPrimAtPath("/Asset/a")).GetEnabledSelfCollisionsAttr().Get() is False
    )
    native.remove_temporary_newton_articulations(stage, mutations)
    assert stage.GetRootLayer().ExportToString() == original_overlay
    assert source.GetRootLayer().ExportToString() == original_source


def test_cleanup_uses_captured_edit_target_and_preserves_local_property_metadata():
    stage = _stage()
    root = stage.GetPrimAtPath("/Asset/a")
    attr = PhysxSchema.PhysxArticulationAPI.Apply(root).CreateEnabledSelfCollisionsAttr(True)
    attr.SetDocumentation("Existing authored setting")
    before = stage.GetRootLayer().ExportToString()
    mutations = native.apply_temporary_newton_articulations(stage, "/Asset")
    stage.SetEditTarget(stage.GetSessionLayer())
    native.remove_temporary_newton_articulations(stage, mutations)
    assert stage.GetRootLayer().ExportToString() == before
    assert stage.GetSessionLayer().empty
    assert stage.GetEditTarget().GetLayer() == stage.GetSessionLayer()


@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt])
def test_partial_multiple_root_apply_rolls_back_without_masking_cause(monkeypatch, failure_type):
    stage = _stage(two_roots=True)
    before = stage.GetRootLayer().ExportToString()
    primary = failure_type("Second root write failed")
    original = Usd.Attribute.Set

    def set_value(attr, value, *args, **kwargs):
        if str(attr.GetPrim().GetPath()) == "/Asset/b" and attr.GetName() == "physxArticulation:enabledSelfCollisions":
            raise primary
        return original(attr, value, *args, **kwargs)

    monkeypatch.setattr(Usd.Attribute, "Set", set_value)
    with pytest.raises(failure_type) as captured:
        native.apply_temporary_newton_articulations(stage, "/Asset")
    assert captured.value is primary
    assert stage.GetRootLayer().ExportToString() == before


def test_rejected_temporary_root_write_rolls_back(monkeypatch):
    stage = _stage()
    before = stage.GetRootLayer().ExportToString()
    original = Usd.Attribute.Set

    def set_value(attr, value, *args, **kwargs):
        if attr.GetName() == "physxArticulation:enabledSelfCollisions":
            return False
        return original(attr, value, *args, **kwargs)

    monkeypatch.setattr(Usd.Attribute, "Set", set_value)
    with pytest.raises(RuntimeError, match="self-collision write"):
        native.apply_temporary_newton_articulations(stage, "/Asset")
    assert stage.GetRootLayer().ExportToString() == before


def test_rejected_root_api_removal_is_required_cleanup_failure(monkeypatch):
    stage = _stage()
    mutations = native.apply_temporary_newton_articulations(stage, "/Asset")
    monkeypatch.setattr(Usd.Prim, "RemoveAPI", lambda *_args: False)
    with pytest.raises(RuntimeError, match="root schema removal") as captured:
        native.remove_temporary_newton_articulations(stage, mutations)
    assert captured.value._fet005_required_cleanup_failed is True


def test_cleanup_missing_mutated_body_is_not_success():
    stage = _stage()
    mutations = native.apply_temporary_newton_articulations(stage, "/Asset")
    stage.RemovePrim("/Asset/a")
    with pytest.raises(RuntimeError, match="root is unavailable"):
        native.remove_temporary_newton_articulations(stage, mutations)


def test_failed_rollback_preserves_setup_cause_and_signals_retirement(monkeypatch):
    stage = _stage(two_roots=True)
    primary = RuntimeError("Second root failed")
    original = Usd.Attribute.Set

    def set_value(attr, value, *args, **kwargs):
        if str(attr.GetPrim().GetPath()) == "/Asset/b" and attr.GetName() == "physxArticulation:enabledSelfCollisions":
            raise primary
        return original(attr, value, *args, **kwargs)

    monkeypatch.setattr(Usd.Attribute, "Set", set_value)
    monkeypatch.setattr(Usd.Prim, "RemoveAPI", lambda *_args: False)
    with pytest.raises(RuntimeError) as captured:
        native.apply_temporary_newton_articulations(stage, "/Asset")
    assert captured.value is primary
    assert primary._fet005_required_cleanup_failed is True
    assert any("rollback failed" in note for note in primary.__notes__)


@pytest.mark.parametrize("failure_operation", ["Set", "Clear"])
def test_failed_self_collision_restoration_is_not_success(monkeypatch, failure_operation):
    stage = _stage()
    root = stage.GetPrimAtPath("/Asset/a")
    api = PhysxSchema.PhysxArticulationAPI.Apply(root)
    if failure_operation == "Set":
        api.CreateEnabledSelfCollisionsAttr(True)
    mutations = native.apply_temporary_newton_articulations(stage, "/Asset")
    monkeypatch.setattr(Usd.Attribute, failure_operation, lambda *_args: False)
    with pytest.raises(RuntimeError, match="self-collision"):
        native.remove_temporary_newton_articulations(stage, mutations)


class _Property:
    def __init__(self, value=None, rejects=False, stale=False):
        self.value = value
        self.rejects = rejects
        self.stale = stale

    def Set(self, value):
        if self.rejects:
            return False
        if not self.stale:
            self.value = value
        return True

    def Get(self):
        return self.value

    def SetTargets(self, value):
        return self.Set(value)

    def GetTargets(self):
        return self.Get()


class _Prim:
    def __init__(self, rejects=None, stale=None):
        self.rejects = rejects
        self.stale = stale
        self.attributes = {}
        self.schemas = []
        self.metadata = {}

    def IsValid(self):
        return True

    def ApplyAPI(self, name):
        if self.rejects == name:
            return False
        if self.stale != name:
            self.schemas.append(name)
        return True

    def HasAPI(self, name):
        return name in self.schemas

    def CreateAttribute(self, name, _value_type):
        return self.attributes.setdefault(name, _Property(rejects=self.rejects == name, stale=self.stale == name))

    def CreateRelationship(self, name):
        return self.CreateAttribute(name, None)

    def SetMetadata(self, name, value):
        if self.rejects == name:
            return False
        if self.stale != name:
            self.metadata[name] = value
        return True

    def GetMetadata(self, name):
        return self.metadata.get(name)


@pytest.fixture(autouse=True)
def newton_schema_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "newton_usd_schemas", types.ModuleType("newton_usd_schemas"))


@pytest.mark.parametrize("operation", ["NewtonCollisionAPI", "newton:contactMargin", "newton:contactGap"])
@pytest.mark.parametrize("failure", ["rejects", "stale"])
def test_fixture_contact_authoring_rejects_false_success(operation, failure):
    with pytest.raises(RuntimeError):
        native.author_newton_fixture_collision(_Prim(**{failure: operation}), 0.002)


@pytest.mark.parametrize("gap", [True, "0", -1.0, float("nan"), float("inf")])
def test_invalid_contact_gap_is_rejected_before_schema_apply(gap):
    prim = _Prim()
    with pytest.raises(ValueError):
        native.author_newton_fixture_collision(prim, gap)
    assert prim.schemas == []


@pytest.mark.parametrize(
    "operation",
    [
        "apiSchemas",
        "newton:velocityLimit",
        "NewtonPDControlAPI",
        "NewtonMaxEffortClampingAPI",
        "newton:targets",
        "newton:kp",
        "newton:kd",
        "newton:maxEffort",
        "visibility",
    ],
)
@pytest.mark.parametrize("failure", ["rejects", "stale"])
def test_fixture_actuator_authoring_rejects_false_success(operation, failure):
    joint = _Prim(**{failure: operation})
    actuator = _Prim(**{failure: operation})
    stage = types.SimpleNamespace(GetPrimAtPath=lambda _path: joint, DefinePrim=lambda *_args: actuator)
    with pytest.raises(RuntimeError):
        native.author_newton_pd_actuator(stage, "/actuator", "/joint", 100.0, 2.0, 5.0, 0.2)

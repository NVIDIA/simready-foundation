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
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases.passive_joints import (
    detect_passive_joints,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import RobotHandle


def physical_handle(names=None, reverse=False, forwarded=False):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    paths = ["/Asset/base", "/Asset/left", "/Asset/right"]
    for path in paths:
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, path).GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath(paths[0]))
    for name, path in zip(("j", "k"), paths[1:], strict=True):
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Joints/" + name)
        tip = path
        if forwarded:
            tip = str(UsdGeom.Xform.Define(stage, path + "/shape").GetPath())
            rel = asset.CreateRelationship("endpoint_" + name)
            rel.SetTargets([tip])
            tip = str(rel.GetPath())
        endpoints = [paths[0], tip]
        if reverse:
            endpoints.reverse()
        joint.CreateBody0Rel().SetTargets([endpoints[0]])
        joint.CreateBody1Rel().SetTargets([endpoints[1]])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    shadow = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/base/j")
    shadow.CreateBody0Rel().SetTargets([paths[0]])
    shadow.CreateBody1Rel().SetTargets([paths[2]])
    shadow.CreateJointEnabledAttr(False)
    poses = np.array([[[0, 0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 0, 1], [2, 0, 0, 0, 0, 0, 1]]], dtype=float)
    coms = np.zeros((1, 3, 7))
    coms[:, :, 6] = 1
    forces = []
    native = SimpleNamespace(
        link_paths=[paths],
        get_link_transforms=lambda: poses.copy(),
        get_coms=lambda: coms.copy(),
        apply_forces_and_torques_at_position=lambda force, *args, **kwargs: forces.append(force.copy()),
    )
    view = SimpleNamespace(body_names=["base", "left", "right"], _physics_view=native)
    handle = RobotHandle(stage, paths[0], asset, None)
    handle._articulation = SimpleNamespace(dof_names=names or ["j", "k"], _articulation_view=view)
    return handle, native, poses, forces


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("forwarded", [False, True])
@pytest.mark.parametrize("names", [["j", "k"], ["j:0", "k:0"], ["/Asset/Joints/j:0", "/Asset/Joints/k:0"]])
def test_selected_force_identity_survives_disabled_shadow_endpoints_and_aliases(reverse, forwarded, names):
    handle, native, poses, forces = physical_handle(names, reverse, forwarded)
    path = handle.get_child_body_path(0)
    assert path == "/Asset/left"
    assert handle.apply_external_force(path, (1, 0, 0), 10.0)
    np.testing.assert_array_equal(forces[-1], [[[0, 0, 0], [10, 0, 0], [0, 0, 0]]])


def test_selected_force_mapping_rejects_detached_and_foreign_rebound_view():
    handle, native, poses, forces = physical_handle()
    assert handle.get_child_body_path(0) == "/Asset/left"
    handle._articulation._articulation_view._physics_view = None
    with pytest.raises(RequiredReadbackError):
        handle.get_child_body_path(0)
    native.link_paths = [["/Foreign/base", "/Foreign/left", "/Foreign/right"]]
    handle._articulation._articulation_view._physics_view = native
    with pytest.raises(RequiredReadbackError):
        handle.get_child_body_path(0)


@pytest.mark.parametrize("bad", ["exception", float("nan"), float("inf"), True, "100"])
def test_selected_gain_readback_failure_is_not_passive(monkeypatch, bad):
    handle, native, poses, forces = physical_handle()
    original = Usd.Attribute.Get
    primary = RuntimeError("required gain unavailable")

    def get(attr, *args):
        if str(attr.GetPath()) == "/Asset/Joints/k.drive:angular:physics:stiffness":
            if bad == "exception":
                raise primary
            return bad
        return original(attr, *args)

    monkeypatch.setattr(Usd.Attribute, "Get", get)
    with pytest.raises(RequiredReadbackError) as caught:
        detect_passive_joints(handle._stage, handle.prim_path, handle.dof_names, handle.asset_prim)
    if bad == "exception":
        assert caught.value.__cause__ is primary


def test_loop_eligibility_does_not_swallow_required_gain_failure(monkeypatch):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_utils import (
        detect_loop_joints,
    )

    handle, native, poses, forces = physical_handle()
    closure = UsdPhysics.RevoluteJoint.Define(handle._stage, "/Asset/Joints/closure")
    closure.CreateBody0Rel().SetTargets(["/Asset/left"])
    closure.CreateBody1Rel().SetTargets(["/Asset/right"])
    closure.CreateExcludeFromArticulationAttr(True)
    original = Usd.Attribute.Get
    primary = RuntimeError("loop drive gain unavailable")

    def get(attr, *args):
        if str(attr.GetPath()) == "/Asset/Joints/j.drive:angular:physics:stiffness":
            raise primary
        return original(attr, *args)

    monkeypatch.setattr(Usd.Attribute, "Get", get)
    with pytest.raises(RequiredReadbackError) as caught:
        detect_loop_joints(handle._stage, "/Asset", handle.dof_names, handle.asset_prim)
    assert caught.value.__cause__ is primary


@pytest.mark.parametrize("parents", [None, {"left": 2, "right": 2, "base": -1}, {"left": 1, "right": 0, "base": -1}])
def test_container_root_uses_qualified_cooked_parent_identity_not_first_link(parents):
    handle, native, poses, forces = physical_handle(reverse=True)
    base = handle._stage.GetPrimAtPath("/Asset/base")
    base.RemoveAPI(UsdPhysics.ArticulationRootAPI)
    UsdPhysics.ArticulationRootAPI.Apply(handle.asset_prim)
    handle._robot_prim_path = "/Asset"
    native.link_paths = [["/Asset/left", "/Asset/right", "/Asset/base"]]
    native.dof_paths = [["/Asset/Joints/j", "/Asset/Joints/k"]]
    native.get_metatype = lambda index: SimpleNamespace(
        link_names=["left", "right", "base"],
        link_indices={"left": 0, "right": 1, "base": 2},
        link_parent_indices=parents,
    )
    if parents is not None and parents["left"] == 2:
        assert handle.get_child_body_path(0) == "/Asset/left"
    else:
        with pytest.raises(RequiredReadbackError):
            handle.get_child_body_path(0)


@pytest.mark.parametrize("invalid", ["disabled", "excluded", "foreign"])
def test_force_identity_rejects_nonselected_joint_and_never_submits(invalid):
    handle, native, poses, forces = physical_handle()
    path = "/Asset/Joints/j"
    if invalid == "disabled":
        UsdPhysics.Joint(handle._stage.GetPrimAtPath(path)).CreateJointEnabledAttr(False)
    elif invalid == "excluded":
        UsdPhysics.Joint(handle._stage.GetPrimAtPath(path)).CreateExcludeFromArticulationAttr(True)
    else:
        path = "/Foreign/Joints/j"
    handle._articulation.dof_names = [path, "k"]
    with pytest.raises(RequiredReadbackError):
        handle.get_child_body_path(0)
    assert not forces


def test_foreign_duplicate_joint_does_not_override_selected_force_identity():
    handle, native, poses, forces = physical_handle()
    stage = handle._stage
    for name in ("base", "tip"):
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Asset/Foreign/" + name).GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset/Foreign/base"))
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Foreign/j")
    joint.CreateBody0Rel().SetTargets(["/Asset/Foreign/base"])
    joint.CreateBody1Rel().SetTargets(["/Asset/Foreign/tip"])
    assert handle.get_child_body_path(0) == "/Asset/left"


def test_newton_force_submission_uses_exact_cooked_path_even_when_names_alias():
    handle, native, poses, forces = physical_handle()
    handle._articulation._articulation_view.body_names = ["base", "same", "same"]
    path = handle.get_child_body_path(0)
    assert handle.apply_external_force(path, (1, 0, 0), 10)
    np.testing.assert_array_equal(forces[-1], [[[0, 0, 0], [10, 0, 0], [0, 0, 0]]])
    native.link_paths = [["/Asset/base", "/Foreign/left", "/Asset/right"]]
    assert not handle.apply_external_force(path, (1, 0, 0), 10)
    assert len(forces) == 1


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("pin_side", [0, 1])
def test_downstream_identity_uses_recorded_external_fixture_pin(reverse, pin_side):
    from simready.evaluate_engine_kit.physics_utils import (
        WORLD_PIN_PATH,
        pin_body_to_world,
    )

    handle, native, poses, forces = physical_handle(reverse=reverse)
    stage = handle._stage
    base = stage.GetPrimAtPath("/Asset/base")
    base.RemoveAPI(UsdPhysics.ArticulationRootAPI)
    UsdPhysics.ArticulationRootAPI.Apply(handle.asset_prim)
    handle._robot_prim_path = "/Asset"
    assert pin_body_to_world(stage, str(base.GetPath()))
    pin = UsdPhysics.FixedJoint(stage.GetPrimAtPath(WORLD_PIN_PATH))
    if pin_side == 0:
        pin.GetBody1Rel().ClearTargets(True)
        pin.GetBody0Rel().SetTargets([base.GetPath()])
    articulation = handle._articulation
    handle = RobotHandle(
        stage, "/Asset", handle.asset_prim, None, setup_world_pin=(WORLD_PIN_PATH, str(base.GetPath()))
    )
    handle._articulation = articulation
    # Current Newton metadata has fixed_base but no link_parent_indices.
    native.get_metatype = lambda index: SimpleNamespace(fixed_base=True)
    before = stage.GetRootLayer().ExportToString()
    assert handle.get_child_body_path(0) == "/Asset/left"
    assert handle.get_child_body_path(1) == "/Asset/right"
    assert not forces
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("fallback_root", [False, True])
@pytest.mark.parametrize(
    "invalid",
    [
        "unrecorded",
        "malformed",
        "removed",
        "disabled",
        "animated",
        "excluded",
        "breakable",
        "blocked",
        "rebound",
        "foreign",
        "disabled_body",
        "animated_body",
        "non_world",
        "unloaded_source",
        "not_compiled",
        "conflicting_pin",
    ],
)
def test_fixture_pin_identity_rejects_unqualified_receipts_even_with_fallback_root(fallback_root, invalid):
    from simready.evaluate_engine_kit.physics_utils import (
        WORLD_PIN_PATH,
        pin_body_to_world,
    )

    handle, native, poses, forces = physical_handle()
    stage = handle._stage
    assert pin_body_to_world(stage, "/Asset/base")
    pin = UsdPhysics.FixedJoint(stage.GetPrimAtPath(WORLD_PIN_PATH))
    handle._setup_world_pin = (WORLD_PIN_PATH, "/Asset/base")
    if not fallback_root:
        stage.GetPrimAtPath("/Asset/base").RemoveAPI(UsdPhysics.ArticulationRootAPI)
        UsdPhysics.ArticulationRootAPI.Apply(handle.asset_prim)
        handle._robot_prim_path = "/Asset"
    if invalid == "unrecorded":
        handle._setup_world_pin = None
        if fallback_root:
            assert handle.get_child_body_path(0) == "/Asset/left"
            return
    elif invalid == "malformed":
        handle._setup_world_pin = (WORLD_PIN_PATH,)
    elif invalid == "removed":
        stage.RemovePrim(WORLD_PIN_PATH)
    elif invalid == "disabled":
        pin.CreateJointEnabledAttr(False)
    elif invalid == "animated":
        pin.CreateJointEnabledAttr().Set(True, 1)
    elif invalid == "excluded":
        pin.CreateExcludeFromArticulationAttr(True)
    elif invalid == "breakable":
        pin.CreateBreakTorqueAttr(1.0)
    elif invalid == "blocked":
        pin.GetBreakForceAttr().Block()
    elif invalid == "rebound":
        pin.GetBody1Rel().SetTargets(["/Asset/left"])
    elif invalid == "foreign":
        foreign = UsdGeom.Xform.Define(stage, "/Foreign/base").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(foreign)
        pin.GetBody1Rel().SetTargets([foreign.GetPath()])
        handle._setup_world_pin = (WORLD_PIN_PATH, str(foreign.GetPath()))
    elif invalid == "disabled_body":
        UsdPhysics.RigidBodyAPI(stage.GetPrimAtPath("/Asset/base")).CreateRigidBodyEnabledAttr(False)
    elif invalid == "animated_body":
        UsdPhysics.RigidBodyAPI(stage.GetPrimAtPath("/Asset/base")).CreateRigidBodyEnabledAttr().Set(True, 1)
    elif invalid == "non_world":
        frame = UsdGeom.Xform.Define(stage, "/Fixture/frame").GetPrim()
        pin.GetBody0Rel().SetTargets([frame.GetPath()])
    elif invalid == "not_compiled":
        native.get_metatype = lambda index: SimpleNamespace(fixed_base=False)
    elif invalid == "conflicting_pin":
        conflicting = UsdPhysics.FixedJoint.Define(stage, "/Asset/other_pin")
        conflicting.CreateBody1Rel().SetTargets(["/Asset/right"])
    elif invalid == "unloaded_source":
        alias = UsdGeom.Xform.Define(stage, "/Alias").GetPrim()
        UsdGeom.Xform.Define(stage, "/AliasDefinition")
        alias.GetPayloads().AddInternalPayload("/AliasDefinition")
        forwarded = alias.CreateRelationship("body")
        forwarded.SetTargets(["/Asset/base"])
        pin.GetBody1Rel().SetTargets([forwarded.GetPath()])
        stage.Unload("/Alias")
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RequiredReadbackError):
        handle.get_child_body_path(0)
    assert not forces
    assert stage.GetRootLayer().ExportToString() == before


def test_fixture_pin_cannot_contradict_selected_authored_body_root():
    from simready.evaluate_engine_kit.physics_utils import (
        WORLD_PIN_PATH,
        pin_body_to_world,
    )

    handle, native, poses, forces = physical_handle()
    assert pin_body_to_world(handle._stage, "/Asset/right")
    handle._setup_world_pin = (WORLD_PIN_PATH, "/Asset/right")
    with pytest.raises(RequiredReadbackError):
        handle.get_child_body_path(0)
    assert not forces

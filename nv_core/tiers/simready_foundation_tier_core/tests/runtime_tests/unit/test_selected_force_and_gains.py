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
from simready.foundation.tier_core.runtime_tests.articulation_phases.passive_joints import (
    detect_passive_joints,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


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
    assert handle.get_child_body_world_com(path) == (1.0, 0.0, 0.0)
    poses[0, 1, 0] = 4.0
    assert handle.get_child_body_world_com(path) == (4.0, 0.0, 0.0)


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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
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


@pytest.mark.parametrize(
    "names", [["j:0", "k:0"], ["/Asset/Joints/j", "/Asset/Joints/k"], ["j", "k:0"], ["k:0", "/Asset/Joints/j"]]
)
def test_hand_mapper_keeps_native_aliases_through_trial_remap(names):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        discover_fingertips,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_close_lift import (
        _capture_gripper_dof_names,
        _resolve_gripper_dof_names,
    )

    handle, native, poses, forces = physical_handle(names)
    result = discover_fingertips(handle._stage, handle, None)
    assert result.kind == "independent_fingers"
    assert sorted(index for chain in result.finger_chains for index in chain) == [0, 1]
    identities = _capture_gripper_dof_names(result, names)
    resolved = _resolve_gripper_dof_names(result, identities, list(reversed(names)))
    assert [[list(reversed(names))[i] for i in chain] for chain in resolved.finger_chains] == [
        list(chain) for chain in identities.chains
    ]


def test_hand_mapper_does_not_drop_a_selected_drive_with_failed_gain(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        discover_fingertips,
    )

    handle, native, poses, forces = physical_handle()
    original = Usd.Attribute.Get
    primary = RuntimeError("required hand gain unavailable")

    def get(attr, *args):
        if str(attr.GetPath()) == "/Asset/Joints/k.drive:angular:physics:stiffness":
            raise primary
        return original(attr, *args)

    monkeypatch.setattr(Usd.Attribute, "Get", get)
    with pytest.raises(RequiredReadbackError) as caught:
        discover_fingertips(handle._stage, handle, None)
    assert caught.value.__cause__ is primary


@pytest.mark.parametrize("same_basename", [False, True])
def test_three_branch_hand_alias_identity_is_complete_through_consumer_remap(same_basename):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        discover_fingertips,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_close_lift import (
        _capture_gripper_dof_names,
        _resolve_gripper_dof_names,
    )

    handle, native, poses, forces = physical_handle()
    stage = handle._stage
    third = UsdGeom.Xform.Define(stage, "/Asset/third").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(third)
    path = "/Asset/Other/j" if same_basename else "/Asset/Joints/m"
    joint = UsdPhysics.RevoluteJoint.Define(stage, path)
    joint.CreateBody0Rel().SetTargets(["/Asset/base"])
    joint.CreateBody1Rel().SetTargets(["/Asset/third"])
    UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    names = [path + ":0", "k:0", "/Asset/Joints/j"]
    handle._articulation.dof_names = names
    result = discover_fingertips(stage, handle, None)
    assert result.kind == "independent_fingers"
    assert len(result.finger_chains) == 3
    assert sorted(index for chain in result.finger_chains for index in chain) == [0, 1, 2]
    assert set(result.tip_link_paths) == {"/Asset/left", "/Asset/right", "/Asset/third"}
    identities = _capture_gripper_dof_names(result, names)
    reordered = [names[1], names[2], names[0]]
    mapped = _resolve_gripper_dof_names(result, identities, reordered)
    assert [[reordered[index] for index in chain] for chain in mapped.finger_chains] == [
        list(chain) for chain in identities.chains
    ]


def test_hand_mapper_requires_all_selected_independent_drives():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        GripperTopologyError,
        discover_fingertips,
    )

    handle, native, poses, forces = physical_handle(["j"])
    with pytest.raises(GripperTopologyError):
        discover_fingertips(handle._stage, handle, None)

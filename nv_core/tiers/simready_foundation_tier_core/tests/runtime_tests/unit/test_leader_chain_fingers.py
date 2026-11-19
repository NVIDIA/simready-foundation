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
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_close_lift as phase
from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
    GripperTopologyError,
    discover_fingertips,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.hand_controls import (
    normalize_hand_trial_controls,
    resolve_hand_trial_specs,
)
from test_articulation_fingertip_discovery import PhysxSchema
from test_gripper_endpoint_mapping import _CONFIG, _Context, _Robot, _stage


def _couple(prim, reference, gear=-2.0, offset=0.1, backend="newton"):
    if backend == "physx":
        mimic = PhysxSchema.PhysxMimicJointAPI.Apply(prim, UsdPhysics.Tokens.rotX)
        mimic.CreateReferenceJointRel().SetTargets([reference])
        mimic.CreateGearingAttr().Set(gear)
        mimic.CreateOffsetAttr().Set(offset)
        return
    prim.AddAppliedSchema("NewtonMimicAPI")
    prim.CreateRelationship("newton:mimicJoint").SetTargets([reference])
    prim.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Double).Set(offset)
    prim.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Double).Set(gear)


def _hand(visible=True, free=False, backend="newton"):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Hand")
    palm = UsdGeom.Xform.Define(stage, "/Hand/palm").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(palm)
    UsdPhysics.ArticulationRootAPI.Apply(palm)
    names = []
    for digit, gear in (("a", -2.0), ("b", 0.5), ("c", -1.5)):
        previous = "/Hand/palm"
        for segment in ("leader", "follower", "tip"):
            body = f"/Hand/{digit}_{segment}_body"
            UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, body).GetPrim())
            name = f"{digit}_{segment}"
            joint = (UsdPhysics.FixedJoint if segment == "tip" else UsdPhysics.RevoluteJoint).Define(
                stage, f"/Hand/joints/{name}"
            )
            joint.CreateBody0Rel().SetTargets([previous])
            joint.CreateBody1Rel().SetTargets([body])
            if segment != "tip":
                UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
                if segment == "follower" and not (free and digit == "c"):
                    _couple(joint.GetPrim(), f"/Hand/joints/{digit}_leader", gear, backend=backend)
                if visible or segment == "leader" or (free and digit == "c"):
                    names.append(name)
            previous = body
    return stage, SimpleNamespace(prim_path="/Hand/palm", dof_names=names, asset_prim=stage.GetPrimAtPath("/Hand"))


@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("free", [False, True])
@pytest.mark.parametrize(
    "backend",
    [
        "newton",
        pytest.param("physx", marks=pytest.mark.skipif(PhysxSchema is None, reason="PhysxSchema unavailable")),
    ],
)
def test_independent_mimic_branches_keep_only_leaders_and_distal_passive_tips(visible, free, backend):
    stage, robot = _hand(visible, free, backend)
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "independent_fingers"
    assert [[robot.dof_names[i] for i in chain] for chain in result.finger_chains] == [
        ["a_leader"],
        ["b_leader"],
        ["c_leader", "c_follower"] if free else ["c_leader"],
    ]
    assert result.tip_link_paths == [f"/Hand/{digit}_tip_body" for digit in "abc"]


@pytest.mark.parametrize(
    "fault",
    [
        "unknown",
        "foreign",
        "cycle",
        "double_api",
        "duplicate_name",
        "duplicate_native",
        "nan",
        "missing_coefficient",
        "cross_branch",
        "missing_tip",
        "ambiguous_parent",
        "ambiguous_tip",
    ],
)
def test_unsafe_leader_chain_ownership_stays_a_mapping_limitation(fault):
    stage, robot = _hand()
    follower = stage.GetPrimAtPath("/Hand/joints/a_follower")
    if fault in ("unknown", "foreign"):
        reference = "/Missing/joint"
        if fault == "foreign":
            reference = str(UsdPhysics.RevoluteJoint.Define(stage, "/Foreign/q").GetPath())
        follower.GetRelationship("newton:mimicJoint").SetTargets([reference])
    elif fault == "cycle":
        _couple(stage.GetPrimAtPath("/Hand/joints/a_leader"), follower.GetPath())
    elif fault == "double_api":
        follower.AddAppliedSchema("PhysxMimicJointAPI:rotX")
    elif fault == "duplicate_name":
        duplicate = UsdPhysics.RevoluteJoint.Define(stage, "/Hand/other/a_leader")
        duplicate.CreateBody0Rel().SetTargets(["/Hand/palm"])
        duplicate.CreateBody1Rel().SetTargets(["/Hand/c_tip_body"])
        UsdPhysics.DriveAPI.Apply(duplicate.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    elif fault == "duplicate_native":
        robot.dof_names.append("a_leader")
    elif fault == "nan":
        follower.GetAttribute("newton:mimicCoef1").Set(float("nan"))
    elif fault == "missing_coefficient":
        follower.RemoveProperty("newton:mimicCoef1")
    elif fault == "cross_branch":
        follower.GetRelationship("newton:mimicJoint").SetTargets(["/Hand/joints/b_leader"])
    elif fault == "missing_tip":
        stage.RemovePrim("/Hand/a_tip_body")
    elif fault == "ambiguous_parent":
        joint = UsdPhysics.FixedJoint.Define(stage, "/Hand/joints/extra")
        joint.CreateBody0Rel().SetTargets(["/Hand/b_follower_body"])
        joint.CreateBody1Rel().SetTargets(["/Hand/a_follower_body"])
    elif fault == "ambiguous_tip":
        UsdGeom.Xform.Define(stage, "/Hand/equal_tip")
        joint = UsdPhysics.FixedJoint.Define(stage, "/Hand/joints/other_tip")
        joint.CreateBody0Rel().SetTargets(["/Hand/a_follower_body"])
        joint.CreateBody1Rel().SetTargets(["/Hand/equal_tip"])
    with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
        discover_fingertips(stage, robot, None)


def test_plausible_jaw_subset_cannot_hide_unresolved_extra_selected_mimic():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Hand")
    for name in ("a", "b", "extra"):
        UsdGeom.Xform.Define(stage, "/Hand/" + name)
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Hand/joints/" + name)
        joint.CreateBody1Rel().SetTargets(["/Hand/" + name])
    _couple(stage.GetPrimAtPath("/Hand/joints/b"), "/Hand/joints/a", -1.0, 0.0)
    _couple(stage.GetPrimAtPath("/Hand/joints/extra"), "/Unknown/joint")
    robot = SimpleNamespace(prim_path="/Hand", dof_names=["a", "b"])
    with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
        discover_fingertips(stage, robot, None)


@pytest.mark.parametrize("state", ["disabled_joint", "disabled_mimic", "inactive", "excluded"])
def test_inactive_selected_couplings_do_not_own_commands(state):
    stage, robot = _hand()
    follower = stage.GetPrimAtPath("/Hand/joints/a_follower")
    if state == "disabled_joint":
        UsdPhysics.Joint(follower).CreateJointEnabledAttr().Set(False)
    elif state == "disabled_mimic":
        follower.CreateAttribute("newton:mimicEnabled", Sdf.ValueTypeNames.Bool).Set(False)
    elif state == "inactive":
        follower.SetActive(False)
    else:
        UsdPhysics.Joint(follower).CreateExcludeFromArticulationAttr().Set(True)
    follower.GetRelationship("newton:mimicJoint").SetTargets(["/Unknown/joint"])
    result = discover_fingertips(stage, robot, None)
    names = [[robot.dof_names[i] for i in chain] for chain in result.finger_chains]
    assert names[0] == (["a_leader", "a_follower"] if state == "disabled_mimic" else ["a_leader"])


def test_discovered_leader_identity_controls_and_remapping_stay_sparse():
    stage, robot = _hand()
    discovered = discover_fingertips(stage, robot, None)
    identity = phase._capture_gripper_dof_names(discovered, robot.dof_names)
    current = ["carrier", "c_follower", "b_leader", "a_follower", "c_leader", "a_leader", "b_follower"]
    mapped = phase._resolve_gripper_dof_names(discovered, identity, current)
    assert mapped.finger_chains == [[5], [2], [4]]
    specs = [{"idx": i, "name": current[i], "open": 0.0, "closed": 1.0} for i in (5, 2, 4)]
    eligible = {row["name"]: dict(row, unit="rad", identity_resolved=True) for row in specs}
    controls = normalize_hand_trial_controls(
        {
            "joints": {
                "a_leader": {"hold_rad": 0.3},
                "b_leader": {"open_rad": 0.9, "closed_rad": 0.2},
            }
        }
    )
    resolved = resolve_hand_trial_specs(specs, controls, eligible, (np.zeros(7), np.ones(7)))
    assert [(s["idx"], s["open"], s["closed"]) for s in resolved] == [(5, 0.3, 0.3), (2, 0.9, 0.2), (4, 0.0, 1.0)]
    bad = normalize_hand_trial_controls({"joints": {"a_follower": {"hold_rad": 0.3}}})
    with pytest.raises(ValueError, match="independently driven angular"):
        resolve_hand_trial_specs(specs, bad, eligible, (np.zeros(7), np.ones(7)))


@pytest.mark.parametrize("order", ["forward", "reverse", "mixed"])
@pytest.mark.parametrize("multilevel", [False, True])
def test_rooted_hand_discovery_and_mapper_ignore_endpoint_order(order, multilevel):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        map_hand_endpoints,
    )

    stage, discovery_robot = _hand()
    discovery_robot.asset_prim = stage.GetPrimAtPath("/Hand")
    for prim in stage.Traverse():
        if prim.GetName() == "palm" or prim.GetName().endswith("_body"):
            UsdPhysics.RigidBodyAPI.Apply(prim)
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Hand/palm"))
    discovery_robot.prim_path = "/Hand/palm"
    if multilevel:
        for digit in "ab":
            joint = stage.GetPrimAtPath(f"/Hand/joints/{digit}_tip")
            joint.SetTypeName("PhysicsRevoluteJoint")
            _couple(joint, f"/Hand/joints/{digit}_follower")
    for index, prim in enumerate(p for p in stage.Traverse() if p.IsA(UsdPhysics.Joint)):
        if order == "reverse" or (order == "mixed" and index % 2):
            joint = UsdPhysics.Joint(prim)
            first, second = joint.GetBody0Rel().GetTargets(), joint.GetBody1Rel().GetTargets()
            joint.GetBody0Rel().SetTargets(second)
            joint.GetBody1Rel().SetTargets(first)
    result = discover_fingertips(stage, discovery_robot, None)
    assert result.finger_chains == [[0], [2], [4]]
    paths = [f"/Hand/{digit}_tip_body" for digit in "abc"]
    assert result.tip_link_paths == paths
    for path in paths:
        UsdGeom.Cube.Define(stage, path + "/shape").CreateSizeAttr(0.002)
    robot = _Robot(
        paths, lambda q: {path: [0, 0.02 + 0.04 * q[index * 2], 0] for index, path in enumerate(paths)}, leaders=6
    )
    robot.dof_names = discovery_robot.dof_names + ["carrier"]
    before = robot.targets.copy()
    specs, _ = asyncio.run(
        map_hand_endpoints(
            _Context(robot),
            robot,
            result,
            stage,
            _CONFIG,
            np.zeros(3),
            lambda displacement, radial: ("closure", "lower" if radial > 0 else "upper"),
        )
    )
    assert [row["idx"] for row in specs] == [0, 2, 4]
    assert {index for index, _ in robot.actions} == {0, 2, 4}
    np.testing.assert_array_equal(robot.targets, before)


@pytest.mark.parametrize("fault", ["missing", "ambiguous"])
def test_independent_hand_requires_qualified_unambiguous_root(fault):
    stage, robot = _hand()
    robot.prim_path = "/Hand"
    if fault == "missing":
        stage.GetPrimAtPath("/Hand/palm").RemoveAPI(UsdPhysics.ArticulationRootAPI)
    else:
        UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Hand/a_tip_body"))
    with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
        discover_fingertips(stage, robot, None)


@pytest.mark.parametrize("order", ["forward", "reverse", "mixed"])
@pytest.mark.parametrize("fault", [None, "multiple_roots", "foreign_edge"])
def test_container_hand_uses_only_complete_qualified_cooked_root(order, fault):
    stage, robot = _hand()
    robot.prim_path = "/Hand"
    stage.GetPrimAtPath("/Hand/palm").RemoveAPI(UsdPhysics.ArticulationRootAPI)
    paths = [str(prim.GetPath()) for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.RigidBodyAPI)]
    paths.reverse()  # The first native link is deliberately not the root.
    names = [path.rsplit("/", 1)[1] for path in paths]
    parents = dict.fromkeys(names, -1)
    for index, prim in enumerate(p for p in stage.Traverse() if p.IsA(UsdPhysics.Joint)):
        joint = UsdPhysics.Joint(prim)
        first, second = joint.GetBody0Rel().GetTargets(), joint.GetBody1Rel().GetTargets()
        parents[str(second[0]).rsplit("/", 1)[1]] = paths.index(str(first[0]))
        if order == "reverse" or (order == "mixed" and index % 2):
            joint.GetBody0Rel().SetTargets(second)
            joint.GetBody1Rel().SetTargets(first)
    if fault == "multiple_roots":
        parents["a_tip_body"] = -1
    elif fault == "foreign_edge":
        parents["a_tip_body"] = paths.index("/Hand/b_tip_body")
    meta = SimpleNamespace(
        link_names=names, link_indices=dict(zip(names, range(len(paths)), strict=True)), link_parent_indices=parents
    )
    view = SimpleNamespace(link_paths=[paths], get_metatype=lambda index: meta)
    robot.articulation = SimpleNamespace(_articulation_view=SimpleNamespace(_physics_view=view))
    if fault:
        with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
            discover_fingertips(stage, robot, None)
    else:
        result = discover_fingertips(stage, robot, None)
        assert result.finger_chains == [[0], [2], [4]]
        assert result.tip_link_paths == [f"/Hand/{digit}_tip_body" for digit in "abc"]


def test_live_hand_probe_uses_owned_tip_even_when_another_branch_moves_more():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        map_hand_endpoints,
    )

    paths = ["/Hand/a_tip_body", "/Hand/b_tip_body", "/Hand/c_tip_body"]
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        FingertipSet,
    )

    fingertips = FingertipSet("independent_fingers", paths, None, None, [[0], [1], [2]])

    def geometry(q):
        return {
            paths[0]: [0, 0.02 + 0.04 * q[0], 0],
            paths[1]: [0, 0.10 - 0.08 * q[0] + 0.04 * q[1], 0],
            paths[2]: [0, 0.02 + 0.04 * q[2], 0],
        }

    robot = _Robot(paths, geometry, leaders=3)
    robot.dof_names = ["a_leader", "b_leader", "c_leader", "carrier"]
    before = robot.targets.copy()
    specs, diagnostics = asyncio.run(
        map_hand_endpoints(
            _Context(robot),
            robot,
            fingertips,
            _stage(paths),
            _CONFIG,
            np.zeros(3),
            lambda displacement, radial: ("closure", "lower" if radial > 0 else "upper"),
        )
    )
    assert [(s["idx"], s["open"], s["closed"]) for s in specs] == [(0, 1.0, 0.0), (1, 1.0, 0.0), (2, 1.0, 0.0)]
    assert [row[1] for row in diagnostics] == ["closure"] * 3
    assert {i for i, _ in robot.actions} == {0, 1, 2}
    assert np.array_equal(robot.targets, before)
    assert np.allclose(robot.actual[:3], 0.4)


@pytest.mark.parametrize("visible", [False, True])
def test_multilevel_follower_references_resolve_to_unique_native_leaders(visible):
    stage, robot = _hand(visible)
    for digit in "abc":
        old = stage.GetPrimAtPath(f"/Hand/joints/{digit}_tip")
        old.SetTypeName("PhysicsRevoluteJoint")
        _couple(old, f"/Hand/joints/{digit}_follower", 0.75, -0.2)
        UsdPhysics.DriveAPI.Apply(old, "angular").CreateStiffnessAttr(100.0)
        if visible:
            robot.dof_names.append(f"{digit}_tip")
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "independent_fingers"
    assert [[robot.dof_names[i] for i in chain] for chain in result.finger_chains] == [
        ["a_leader"],
        ["b_leader"],
        ["c_leader"],
    ]
    assert result.tip_link_paths == [f"/Hand/{digit}_tip_body" for digit in "abc"]


def test_selected_joint_root_jaw_also_requires_complete_raw_coupling_coverage():
    from test_articulation_fingertip_discovery import _joint_root_fingers

    stage, robot = _joint_root_fingers()
    _couple(stage.GetPrimAtPath("/Asset/joints/b"), "/Asset/joints/a", -1.0, 0.0)
    body = UsdGeom.Xform.Define(stage, "/Asset/extra").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    extra = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joints/extra")
    extra.CreateBody0Rel().SetTargets(["/Asset/base"])
    extra.CreateBody1Rel().SetTargets([body.GetPath()])
    _couple(extra.GetPrim(), "/Asset/missing")
    with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
        discover_fingertips(stage, robot, None)


def _physical_jaw(stage, prefix, names, backend):
    for body in ("base", "left", "right"):
        prim = UsdGeom.Xform.Define(stage, prefix + "/" + body).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath(prefix + "/base"))
    for name, body in zip(names, ("left", "right"), strict=True):
        joint = UsdPhysics.RevoluteJoint.Define(stage, prefix + "/joints/" + name)
        joint.CreateBody0Rel().SetTargets([prefix + "/base"])
        joint.CreateBody1Rel().SetTargets([prefix + "/" + body])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    _couple(
        stage.GetPrimAtPath(prefix + "/joints/" + names[1]), prefix + "/joints/" + names[0], -1.0, 0.0, backend=backend
    )


def _physical_selected_jaw(root_kind, backend, foreign=False, same_names=False):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    _physical_jaw(stage, "/Asset", ("leader", "follower"), backend)
    root_path = "/Asset/base"
    if root_kind == "container":
        stage.GetPrimAtPath(root_path).RemoveAPI(UsdPhysics.ArticulationRootAPI)
        UsdPhysics.ArticulationRootAPI.Apply(asset)
        root_path = "/Asset"
    if foreign:
        names = ("leader", "follower") if same_names else ("foreign_leader", "foreign_follower")
        _physical_jaw(stage, "/Asset/Foreign", names, backend)
    robot = SimpleNamespace(prim_path=root_path, dof_names=["leader"], asset_prim=asset)
    if root_kind == "container":
        # A floating container needs complete native parent evidence to orient
        # its selected graph. The first native link is deliberately not root.
        paths = ["/Asset/right", "/Asset/base", "/Asset/left"]
        meta = SimpleNamespace(
            link_names=["right", "base", "left"],
            link_indices={"right": 0, "base": 1, "left": 2},
            link_parent_indices={"right": 1, "base": -1, "left": 1},
        )
        view = SimpleNamespace(link_paths=[paths], get_metatype=lambda index: meta)
        robot.articulation = SimpleNamespace(_articulation_view=SimpleNamespace(_physics_view=view))
    return stage, robot


@pytest.mark.parametrize(
    "backend",
    [
        "newton",
        pytest.param("physx", marks=pytest.mark.skipif(PhysxSchema is None, reason="PhysxSchema unavailable")),
    ],
)
@pytest.mark.parametrize("search_path", [None, "/Asset", "/Asset/joints"])
def test_body_root_jaw_keeps_sibling_mimic_joints_and_respects_explicit_narrow_scope(backend, search_path):
    stage, robot = _physical_selected_jaw("body", backend)
    result = discover_fingertips(stage, robot, None, robot_prim_path=search_path)
    assert result.kind == "mimic_parallel_jaw"
    assert result.mimic_master_dofs == [0]
    assert set(result.candidate_tip_paths) == {"/Asset/left", "/Asset/right"}
    assert discover_fingertips(stage, robot, None, robot_prim_path="/Asset/base").kind == "unsupported"


@pytest.mark.parametrize("root_kind", ["body", "container"])
def test_narrow_follower_scope_does_not_import_its_out_of_scope_mimic_leader(root_kind):
    stage, robot = _physical_selected_jaw(root_kind, "newton")
    with pytest.raises(GripperTopologyError, match="references a joint outside its articulation"):
        discover_fingertips(stage, robot, None, robot_prim_path="/Asset/joints/follower")


@pytest.mark.parametrize(
    "backend",
    [
        "newton",
        pytest.param("physx", marks=pytest.mark.skipif(PhysxSchema is None, reason="PhysxSchema unavailable")),
    ],
)
def test_body_root_unresolved_selected_sibling_edge_cannot_hide_behind_jaw(backend):
    stage, robot = _physical_selected_jaw("body", backend)
    body = UsdGeom.Xform.Define(stage, "/Asset/extra").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    extra = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joints/extra")
    extra.CreateBody0Rel().SetTargets(["/Asset/base"])
    extra.CreateBody1Rel().SetTargets([body.GetPath()])
    _couple(extra.GetPrim(), "/Asset/missing", backend=backend)
    with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
        discover_fingertips(stage, robot, None)


@pytest.mark.parametrize("root_kind", ["body", "container"])
@pytest.mark.parametrize("search_path", [None, "/Asset", "/Asset/joints"])
@pytest.mark.parametrize("same_names", [False, True])
def test_selected_jaw_ignores_unrelated_foreign_local_jaw(root_kind, search_path, same_names):
    stage, robot = _physical_selected_jaw(root_kind, "newton", foreign=True, same_names=same_names)
    result = discover_fingertips(stage, robot, None, robot_prim_path=search_path)
    assert result.kind == "mimic_parallel_jaw"
    assert set(result.candidate_tip_paths) == {"/Asset/left", "/Asset/right"}


@pytest.mark.parametrize(
    "backend",
    [
        "newton",
        pytest.param("physx", marks=pytest.mark.skipif(PhysxSchema is None, reason="PhysxSchema unavailable")),
    ],
)
@pytest.mark.parametrize("explicit", [False, True])
def test_foreign_hidden_follower_cannot_supply_selected_jaw_candidates(backend, explicit):
    stage, robot = _physical_selected_jaw("container", backend, foreign=True)
    stage.GetPrimAtPath("/Asset/Foreign/joints/foreign_leader").SetActive(False)
    follower = stage.GetPrimAtPath("/Asset/Foreign/joints/foreign_follower")
    if backend == "newton":
        follower.GetRelationship("newton:mimicJoint").SetTargets(["/Asset/joints/leader"])
    else:
        PhysxSchema.PhysxMimicJointAPI(follower, UsdPhysics.Tokens.rotX).GetReferenceJointRel().SetTargets(
            ["/Asset/joints/leader"]
        )
    result = discover_fingertips(stage, robot, None, robot_prim_path="/Asset" if explicit else None)
    assert result.kind == "mimic_parallel_jaw"
    assert set(result.candidate_tip_paths) == {"/Asset/left", "/Asset/right"}


def test_selected_follower_cannot_reference_foreign_articulation_inside_same_asset():
    stage, robot = _physical_selected_jaw("container", "newton", foreign=True)
    stage.GetPrimAtPath("/Asset/joints/follower").GetRelationship("newton:mimicJoint").SetTargets(
        ["/Asset/Foreign/joints/foreign_leader"]
    )
    with pytest.raises(GripperTopologyError, match="outside its articulation"):
        discover_fingertips(stage, robot, None)


@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("foreign_loop", [False, True])
@pytest.mark.parametrize("foreign_ignored", [False, True])
def test_extra_independent_coordinate_cannot_borrow_jaw_or_foreign_loop_ownership(
    visible, foreign_loop, foreign_ignored
):
    stage, robot = _physical_selected_jaw("container", "newton")
    UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Asset/extra").GetPrim())
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joints/extra")
    joint.CreateBody0Rel().SetTargets(["/Asset/base"])
    joint.CreateBody1Rel().SetTargets(["/Asset/extra"])
    UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    robot.dof_names = ["leader", "follower", "extra"] if visible else ["leader", "extra"]
    if foreign_loop:
        for name in ("base", "middle", "end"):
            UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Asset/Foreign/" + name).GetPrim())
        UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset/Foreign/base"))
        for name, first, last, excluded in (
            ("extra", "base", "middle", False),
            ("bar", "middle", "end", False),
            ("closure", "end", "base", True),
        ):
            joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Foreign/joints/" + name)
            joint.CreateBody0Rel().SetTargets(["/Asset/Foreign/" + first])
            joint.CreateBody1Rel().SetTargets(["/Asset/Foreign/" + last])
            joint.CreateExcludeFromArticulationAttr().Set(excluded)
    with pytest.raises(GripperTopologyError, match="mapping/setup limitation"):
        discover_fingertips(
            stage, robot, None, ignored_joint_paths=["/Asset/Foreign/joints/extra"] if foreign_ignored else []
        )


@pytest.mark.parametrize("root_kind", ["body", "container"])
def test_foreign_container_reversed_endpoints_do_not_poison_selected_identity(root_kind):
    stage, robot = _physical_selected_jaw(root_kind, "newton", foreign=True, same_names=True)
    stage.GetPrimAtPath("/Asset/Foreign/base").RemoveAPI(UsdPhysics.ArticulationRootAPI)
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset/Foreign"))
    for name, body in (("leader", "left"), ("follower", "right")):
        joint = UsdPhysics.Joint(stage.GetPrimAtPath("/Asset/Foreign/joints/" + name))
        joint.CreateBody0Rel().SetTargets(["/Asset/Foreign/" + body])
        joint.CreateBody1Rel().SetTargets(["/Asset/Foreign/base"])
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "mimic_parallel_jaw"
    assert set(result.candidate_tip_paths) == {"/Asset/left", "/Asset/right"}


@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("multilevel", [False, True])
def test_required_setup_ownership_accepts_valid_hidden_dependents(visible, multilevel):
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )

    stage, robot = _hand(visible)
    if multilevel:
        for digit in "abc":
            joint = stage.GetPrimAtPath(f"/Hand/joints/{digit}_tip")
            joint.SetTypeName("PhysicsRevoluteJoint")
            _couple(joint, f"/Hand/joints/{digit}_follower")
    followers, names, loops, _ = control_ownership(
        stage, stage.GetPrimAtPath("/Hand"), robot.prim_path, robot.dof_names
    )
    assert followers == ({1, 3, 5} if visible else set())
    assert names == (["a_follower", "b_follower", "c_follower"] if visible else [])
    assert loops == set()


@pytest.mark.parametrize("same_names", [False, True])
def test_required_setup_ownership_excludes_disconnected_foreign_followers(same_names):
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )

    stage, robot = _physical_selected_jaw("container", "newton", foreign=True, same_names=same_names)
    robot.dof_names = ["leader", "follower"]
    assert control_ownership(stage, robot.asset_prim, robot.prim_path, robot.dof_names) == (
        {1},
        ["follower"],
        set(),
        [],
    )


@pytest.mark.parametrize(
    "fault",
    ["missing_reference", "missing_coefficient", "cycle", "duplicate_native", "missing_leader", "foreign_reference"],
)
def test_required_setup_rejects_unqualified_selected_couplings(fault):
    from simready.foundation.tier_core.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )

    stage, robot = _physical_selected_jaw("container", "newton", foreign=fault == "foreign_reference")
    robot.dof_names = ["leader", "follower"]
    follower = stage.GetPrimAtPath("/Asset/joints/follower")
    if fault == "missing_reference":
        follower.GetRelationship("newton:mimicJoint").SetTargets(["/Missing/joint"])
    elif fault == "missing_coefficient":
        follower.RemoveProperty("newton:mimicCoef1")
    elif fault == "cycle":
        _couple(stage.GetPrimAtPath("/Asset/joints/leader"), follower.GetPath())
    elif fault == "duplicate_native":
        robot.dof_names.append("follower")
    elif fault == "missing_leader":
        robot.dof_names = ["follower"]
    else:
        follower.GetRelationship("newton:mimicJoint").SetTargets(["/Asset/Foreign/joints/foreign_leader"])
    with pytest.raises(RuntimeError, match="Required mimic control ownership"):
        control_ownership(stage, robot.asset_prim, robot.prim_path, robot.dof_names)


def test_passive_distal_drive_api_is_geometry_only_in_actual_mapper():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        map_hand_endpoints,
    )

    stage, identity = _hand(free=True)
    for digit in "abc":
        UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"/Hand/joints/{digit}_leader"), "angular").CreateStiffnessAttr(100)
    UsdPhysics.DriveAPI(stage.GetPrimAtPath("/Hand/joints/c_follower"), "angular").CreateStiffnessAttr(0)
    discovered = discover_fingertips(stage, identity, None)
    paths = discovered.tip_link_paths
    robot = _Robot(paths, lambda q: {path: [0, 0.02 + 0.04 * q[i * 2], 0] for i, path in enumerate(paths)}, leaders=6)
    robot.dof_names = identity.dof_names + ["carrier"]
    specs, _ = asyncio.run(
        map_hand_endpoints(
            _Context(robot),
            robot,
            discovered,
            _stage(paths),
            _CONFIG,
            np.zeros(3),
            lambda displacement, radial: ("closure", "lower" if radial > 0 else "upper"),
        )
    )
    assert [spec["idx"] for spec in specs] == [0, 2, 4]
    assert {index for index, _ in robot.actions} == {0, 2, 4}
    assert paths == [f"/Hand/{digit}_tip_body" for digit in "abc"]

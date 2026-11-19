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
"""Tests for articulation_phases.ee_discovery."""
import pytest
from pxr import Tf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.ee_discovery import (
    _find_ee_from_robot_links,
    _find_fixed_ee_child,
    discover_end_effector_link,
)

try:
    from pxr import PhysxSchema  # noqa: F401
except ImportError:
    try:
        from physx_usd_schemas import PhysxSchema  # noqa: F401
    except ImportError:
        PhysxSchema = None

_HAS_PHYSX_SCHEMA = PhysxSchema is not None


def _make_robot_stage_with_flange():
    """Stage layout:

    /World (Xform)
        /robot (Xform, has isaac:physics:robotLinks rel)
            /link0 (Xform)
            /link1 (Xform)
            /J6_link (Xform, last in robotLinks)
                /flange (Xform)        <- expected EE
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    robot = UsdGeom.Xform.Define(stage, "/World/robot").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/robot/link0")
    UsdGeom.Xform.Define(stage, "/World/robot/link1")
    j6 = UsdGeom.Xform.Define(stage, "/World/robot/J6_link").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/robot/J6_link/flange")

    rel = robot.CreateRelationship("isaac:physics:robotLinks", custom=False)
    rel.AddTarget("/World/robot/link0")
    rel.AddTarget("/World/robot/link1")
    rel.AddTarget("/World/robot/J6_link")
    return stage, robot, j6


def test_find_fixed_ee_child_returns_flange_path():
    _stage, _robot, j6 = _make_robot_stage_with_flange()
    result = _find_fixed_ee_child(j6)
    assert result == "/World/robot/J6_link/flange"


def test_find_fixed_ee_child_returns_none_when_no_match():
    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/World/parent").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/parent/random_child")
    assert _find_fixed_ee_child(parent) is None


def test_discover_end_effector_link_uses_robot_links_rel_and_flange():
    stage, _robot, _j6 = _make_robot_stage_with_flange()
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/robot")
    assert result == "/World/robot/J6_link/flange"


def test_find_ee_from_robot_links_returns_last_target_when_no_flange():
    """No fixed EE child -> falls back to the last articulated link itself."""
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    robot = UsdGeom.Xform.Define(stage, "/World/robot").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/robot/link0")
    UsdGeom.Xform.Define(stage, "/World/robot/link1")
    UsdGeom.Xform.Define(stage, "/World/robot/some_terminal_link")

    rel = robot.CreateRelationship("isaac:physics:robotLinks", custom=False)
    rel.AddTarget("/World/robot/link0")
    rel.AddTarget("/World/robot/link1")
    rel.AddTarget("/World/robot/some_terminal_link")

    result = _find_ee_from_robot_links(stage, robot)
    assert result == "/World/robot/some_terminal_link"


def test_discover_end_effector_link_returns_none_for_missing_root():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/does_not_exist")
    assert result is None


def test_discover_end_effector_link_empty_stage_returns_none():
    stage = Usd.Stage.CreateInMemory()
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/robot")
    assert result is None


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_end_effector_link_with_physx_schema_present():
    """Smoke test: same flange-discovery path still works when PhysxSchema
    is importable in the environment."""
    stage, _robot, _j6 = _make_robot_stage_with_flange()
    result = discover_end_effector_link(stage, robot=None, robot_root_path="/World/robot")
    assert result == "/World/robot/J6_link/flange"


def _graph_stage(edges):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    for index, (parent, child, fixed) in enumerate(edges):
        for name in (parent, child):
            if name:
                prim = UsdGeom.Xform.Define(stage, "/Robot/" + name).GetPrim()
                UsdPhysics.RigidBodyAPI.Apply(prim)
        schema = UsdPhysics.FixedJoint if fixed else UsdPhysics.RevoluteJoint
        joint = schema.Define(stage, "/Robot/joints/j%d" % index)
        if parent:
            joint.GetBody0Rel().SetTargets(["/Robot/" + parent])
        if child:
            joint.GetBody1Rel().SetTargets(["/Robot/" + child])
    return stage, root


def test_graph_endpoint_outranks_unordered_robot_links():
    stage, root = _graph_stage([(None, "base", True), ("base", "link", False), ("link", "hand", False)])
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Robot/hand", "/Robot/base"])
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/hand"


@pytest.mark.parametrize("excluded", [False, True])
def test_sanctioned_parallel_linkage_closure_preserves_main_chain_endpoint(excluded):
    stage, _ = _graph_stage(
        [
            (None, "base", True),
            ("base", "shoulder", False),
            ("shoulder", "elbow", False),
            ("elbow", "wrist", False),
            ("base", "counterweight", False),
        ]
    )
    closure = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joints/closure")
    closure.CreateBody0Rel().SetTargets(["/Robot/counterweight"])
    closure.CreateBody1Rel().SetTargets(["/Robot/elbow"])
    closure.CreateExcludeFromArticulationAttr(excluded)
    assert discover_end_effector_link(stage, None, "/Robot") == ("/Robot/wrist" if excluded else None)


@pytest.mark.parametrize("defect", ["dangling", "foreign", "multiple", "disconnected", "self"])
def test_excluded_closure_does_not_hide_invalid_or_unowned_body_identity(defect):
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    closure = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joints/closure")
    closure.CreateExcludeFromArticulationAttr(True)
    closure.CreateBody0Rel().SetTargets(["/Robot/base"])
    if defect == "dangling":
        targets = ["/Robot/missing"]
    elif defect == "foreign":
        body = UsdGeom.Xform.Define(stage, "/Foreign/body").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        targets = [body.GetPath()]
    elif defect == "multiple":
        targets = ["/Robot/base", "/Robot/wrist"]
    elif defect == "disconnected":
        body = UsdGeom.Xform.Define(stage, "/Robot/unconnected").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        targets = [body.GetPath()]
    else:
        targets = ["/Robot/base"]
    closure.CreateBody1Rel().SetTargets(targets)
    assert discover_end_effector_link(stage, None, "/Robot") is None


def test_world_anchor_supports_reversed_body_relationship_orientation():
    stage, root = _graph_stage([("base", None, True), ("right_hand", "base", False)])
    assert discover_end_effector_link(stage, None, str(root.GetPath())) == "/Robot/right_hand"


@pytest.mark.parametrize(
    "edges",
    [
        [(None, "base", True), ("base", "tip1", False), ("base", "tip2", False)],
        [(None, "base", True), ("base", "a", False), ("a", "b", False), ("b", "base", False)],
        [(None, "base", True), ("base", "tip", False), ("outside", "other", False)],
        [(None, "base", True), ("base", "tip", False), ("base", "tip", False)],
    ],
)
def test_invalid_or_ambiguous_graph_does_not_fallback_to_metadata(edges):
    stage, root = _graph_stage(edges)
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Robot/base"])
    assert discover_end_effector_link(stage, None, "/Robot") is None


def test_explicit_endpoint_wins_but_cannot_escape_loaded_asset():
    stage, root = _graph_stage([(None, "base", True), ("base", "tip", False)])
    UsdGeom.Xform.Define(stage, "/Other/tool")
    assert discover_end_effector_link(stage, None, "/Robot", explicit_path="/Robot/base") == "/Robot/base"
    assert discover_end_effector_link(stage, None, "/Robot", explicit_path="/Other/tool") is None


def test_disabled_joint_does_not_block_metadata_only_asset():
    stage, root = _graph_stage([("base", "tip", False)])
    stage.GetPrimAtPath("/Robot/joints/j0").GetAttribute("physics:jointEnabled").Set(False)
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Robot/tip"])
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/tip"


def test_tool_named_dynamic_child_is_not_treated_as_fixed_marker():
    stage, root = _graph_stage([(None, "base", True), ("base", "hand", False)])
    hand = stage.GetPrimAtPath("/Robot/hand")
    tool = UsdGeom.Xform.Define(stage, "/Robot/hand/tool0").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(tool)
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joints/dynamic_tool")
    joint.GetBody0Rel().SetTargets([hand.GetPath()])
    joint.GetBody1Rel().SetTargets([tool.GetPath()])
    assert _find_fixed_ee_child(hand) is None


def test_metadata_endpoint_outside_asset_is_not_resolved_by_basename():
    stage, root = _graph_stage([])
    UsdGeom.Xform.Define(stage, "/Other/tip")
    UsdGeom.Xform.Define(stage, "/Robot/tip")
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Other/tip"])
    assert _find_ee_from_robot_links(stage, root) is None


def test_long_joint_chain_is_walked_without_python_recursion_limit():
    edges = [(None, "base", True), ("base", "link0", False)]
    edges.extend(("link%d" % i, "link%d" % (i + 1), False) for i in range(1050))
    stage, root = _graph_stage(edges)
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/link1050"


def test_forwarded_body_relationships_resolve_composed_topology():
    stage, root = _graph_stage([(None, "base", True), ("base", "tip", False)])
    root.CreateRelationship("forwardedTip").SetTargets(["/Robot/tip"])
    stage.GetPrimAtPath("/Robot/joints/j1").GetRelationship("physics:body1").SetTargets(["/Robot.forwardedTip"])
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/tip"


def test_two_different_tcp_markers_require_explicit_endpoint():
    stage, root = _graph_stage([(None, "base", True), ("base", "tip", False)])
    UsdGeom.Xform.Define(stage, "/Robot/tip/tool0")
    UsdGeom.Xform.Define(stage, "/Robot/tip/tcp")
    assert discover_end_effector_link(stage, None, "/Robot") is None
    assert discover_end_effector_link(stage, None, "/Robot", explicit_path="/Robot/tip/tcp") == "/Robot/tip/tcp"


@pytest.mark.parametrize("middle", ["inner_link", "outer_arm", "gripper_mount", "paddle", "finger_link"])
def test_serial_arm_names_do_not_prune_a_non_finger_endpoint(middle):
    stage, _ = _graph_stage([(None, "base", True), ("base", middle, False), (middle, "wrist", False)])
    UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0")
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/wrist/tool0"


def test_terminal_finger_subtrees_do_not_override_the_wrist_marker():
    stage, _ = _graph_stage(
        [
            (None, "base", True),
            ("base", "wrist", False),
            ("wrist", "left_finger", False),
            ("wrist", "right_knuckle", False),
            ("right_knuckle", "finger_pad", False),
        ]
    )
    UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0")
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/wrist/tool0"


@pytest.mark.parametrize("forwarded", [False, True])
def test_joint_child_frames_resolve_to_their_owning_rigid_bodies(forwarded):
    stage, root = _graph_stage([(None, "base", True), ("base", "link", False), ("link", "wrist", False)])
    for body in ("base", "link", "wrist"):
        for frame in ("in", "out"):
            UsdGeom.Xform.Define(stage, f"/Robot/{body}/{frame}")
    for index, (parent, child) in enumerate(
        [(None, "/Robot/base/in"), ("/Robot/base/out", "/Robot/link/in"), ("/Robot/link/out", "/Robot/wrist/in")]
    ):
        joint = stage.GetPrimAtPath(f"/Robot/joints/j{index}")
        joint.GetRelationship("physics:body0").SetTargets([parent] if parent else [])
        joint.GetRelationship("physics:body1").SetTargets([child])
    if forwarded:
        root.CreateRelationship("wristFrame").SetTargets(["/Robot/wrist/in"])
        stage.GetPrimAtPath("/Robot/joints/j2").GetRelationship("physics:body1").SetTargets(["/Robot.wristFrame"])
    UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0")
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/wrist/tool0"


def test_bounded_static_joint_frame_is_a_world_anchor_not_an_arm_body():
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    UsdGeom.Xform.Define(stage, "/Robot/world_frame")
    stage.GetPrimAtPath("/Robot/joints/j0").GetRelationship("physics:body0").SetTargets(["/Robot/world_frame"])
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/wrist"


def test_nested_body_owns_its_frames_instead_of_the_parent_body():
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    nested = UsdGeom.Xform.Define(stage, "/Robot/base/nested").GetPrim()
    UsdGeom.Xformable(nested).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(nested)
    UsdGeom.Xform.Define(stage, "/Robot/base/nested/frame")
    stage.GetPrimAtPath("/Robot/joints/j0").GetRelationship("physics:body1").SetTargets(["/Robot/base/nested/frame"])
    stage.GetPrimAtPath("/Robot/joints/j1").GetRelationship("physics:body0").SetTargets(["/Robot/base/nested/frame"])
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/wrist"


@pytest.mark.parametrize("target", ["/Other/wrist/frame", "/Robot/base/out", "/Robot.invalidProperty"])
def test_invalid_body_identity_cannot_be_promoted_or_recovered_from_inventory(target):
    stage, root = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    foreign = UsdGeom.Xform.Define(stage, "/Other/wrist").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(foreign)
    UsdGeom.Xform.Define(stage, "/Other/wrist/frame")
    UsdGeom.Xform.Define(stage, "/Robot/base/out")
    stage.GetPrimAtPath("/Robot/joints/j1").GetRelationship("physics:body1").SetTargets([target])
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Robot/wrist"])
    assert discover_end_effector_link(stage, None, "/Robot") is None


def test_body_owner_outside_the_loaded_root_is_not_a_world_anchor():
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/Parent").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    UsdGeom.Xform.Define(stage, "/Parent/Robot/frame")
    tip = UsdGeom.Xform.Define(stage, "/Parent/Robot/tip").GetPrim()
    UsdGeom.Xformable(tip).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tip)
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Parent/Robot/joint")
    joint.GetBody0Rel().SetTargets(["/Parent/Robot/frame"])
    joint.GetBody1Rel().SetTargets([tip.GetPath()])
    assert discover_end_effector_link(stage, None, "/Parent/Robot") is None


def test_non_body_tcp_remains_fixed_when_a_joint_targets_its_frame():
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0")
    stage.GetPrimAtPath("/Robot/joints/j1").GetRelationship("physics:body1").SetTargets(["/Robot/wrist/tool0"])
    assert discover_end_effector_link(stage, None, "/Robot") == "/Robot/wrist/tool0"


def test_independent_tcp_body_with_dynamic_child_frame_joint_is_not_a_fixed_marker():
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    wrist = stage.GetPrimAtPath("/Robot/wrist")
    tcp = UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0").GetPrim()
    UsdGeom.Xformable(tcp).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tcp)
    UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0/frame")
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Foreign/dynamic_tcp")
    joint.GetBody0Rel().SetTargets([wrist.GetPath()])
    joint.GetBody1Rel().SetTargets(["/Robot/wrist/tool0/frame"])
    assert _find_fixed_ee_child(wrist) is None


@pytest.mark.parametrize("defect", ["empty", "cycle", "multi", "scope"])
def test_malformed_forwarded_joint_body_does_not_become_a_world_anchor(defect):
    stage, root = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    forwarded = root.CreateRelationship("forwardedBody")
    if defect == "cycle":
        forwarded.SetTargets(["/Robot.forwardedAgain"])
        root.CreateRelationship("forwardedAgain").SetTargets(["/Robot.forwardedBody"])
    elif defect == "multi":
        UsdGeom.Xform.Define(stage, "/Robot/base/frame")
        forwarded.SetTargets(["/Robot/base", "/Robot/base/frame"])
    elif defect == "scope":
        UsdGeom.Scope.Define(stage, "/Robot/scope")
        forwarded.SetTargets(["/Robot/scope"])
    stage.GetPrimAtPath("/Robot/joints/j0").GetRelationship("physics:body1").SetTargets(["/Robot.forwardedBody"])
    root.CreateRelationship("isaac:physics:robotLinks").SetTargets(["/Robot/wrist"])
    assert discover_end_effector_link(stage, None, "/Robot") is None


@pytest.mark.parametrize("connection", ["parent", "other", "world", "multi"])
def test_independent_tcp_child_frame_requires_a_unique_fixed_parent_connection(connection):
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    wrist = stage.GetPrimAtPath("/Robot/wrist")
    tcp = UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0").GetPrim()
    UsdGeom.Xformable(tcp).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tcp)
    UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0/frame")
    joint = UsdPhysics.FixedJoint.Define(stage, "/Foreign/fixed_tcp")
    if connection == "parent":
        UsdGeom.Xform.Define(stage, "/Robot/wrist/frame")
        joint.GetBody0Rel().SetTargets(["/Robot/wrist/frame"])
    elif connection == "other":
        other = UsdGeom.Xform.Define(stage, "/Foreign/body").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(other)
        joint.GetBody0Rel().SetTargets([other.GetPath()])
    elif connection == "multi":
        joint.GetBody0Rel().SetTargets(["/Robot/wrist", "/Robot/base"])
    joint.GetBody1Rel().SetTargets(["/Robot/wrist/tool0/frame"])
    assert _find_fixed_ee_child(wrist) == (str(tcp.GetPath()) if connection == "parent" else None)


def test_native_relationship_resolution_error_fails_closed(monkeypatch):
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    original = Usd.Relationship.GetForwardedTargets

    def unavailable(relationship):
        if str(relationship.GetPath()) == "/Robot/joints/j0.physics:body1":
            Tf.RaiseCodingError("Relationship resolution unavailable")
        return original(relationship)

    monkeypatch.setattr(Usd.Relationship, "GetForwardedTargets", unavailable)
    assert discover_end_effector_link(stage, None, "/Robot") is None


def test_unresolved_enabled_constraint_cannot_certify_an_independent_tcp_marker():
    stage, _ = _graph_stage([(None, "base", True), ("base", "wrist", False)])
    wrist = stage.GetPrimAtPath("/Robot/wrist")
    tcp = UsdGeom.Xform.Define(stage, "/Robot/wrist/tool0").GetPrim()
    UsdGeom.Xformable(tcp).SetResetXformStack(True)
    UsdPhysics.RigidBodyAPI.Apply(tcp)
    fixed = UsdPhysics.FixedJoint.Define(stage, "/Foreign/fixed_tcp")
    fixed.GetBody0Rel().SetTargets([wrist.GetPath()])
    fixed.GetBody1Rel().SetTargets([tcp.GetPath()])
    malformed = UsdPhysics.RevoluteJoint.Define(stage, "/Foreign/malformed_tcp")
    malformed.GetBody0Rel().SetTargets([wrist.GetPath()])
    malformed.GetBody1Rel().SetTargets([tcp.GetPath(), "/Robot/base"])
    assert _find_fixed_ee_child(wrist) is None

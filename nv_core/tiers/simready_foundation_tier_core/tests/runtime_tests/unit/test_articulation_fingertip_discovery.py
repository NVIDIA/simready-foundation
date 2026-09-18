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
"""Tests for articulation_phases.fingertip_discovery."""
import numpy as np  # noqa: F401  (kept for parity with sibling tests)
import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

# pxr.PhysxSchema is only available when omni.physx is loaded. Mimic-driven
# tests skip when it isn't, matching test_articulation_mimic_joints.py.
try:
    from pxr import PhysxSchema  # noqa: F401

    _HAS_PHYSX_SCHEMA = True
except ImportError:
    _HAS_PHYSX_SCHEMA = False

from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
    FingertipSet,
    discover_fingertips,
)


def test_fingertip_set_dataclass_round_trips_mimic():
    fs = FingertipSet(
        kind="mimic_parallel_jaw",
        tip_link_paths=["/World/Asset/finger_left_pad", "/World/Asset/finger_right_pad"],
        mimic_master_dof=0,
        mimic_follower_dof=1,
        finger_chains=None,
    )
    assert fs.kind == "mimic_parallel_jaw"
    assert len(fs.tip_link_paths) == 2
    assert fs.mimic_master_dof == 0


def test_fingertip_set_dataclass_round_trips_independent():
    fs = FingertipSet(
        kind="independent_fingers",
        tip_link_paths=["/W/A/f1", "/W/A/f2", "/W/A/f3"],
        mimic_master_dof=None,
        mimic_follower_dof=None,
        finger_chains=[[0, 1], [2, 3], [4, 5]],
    )
    assert fs.kind == "independent_fingers"
    assert len(fs.tip_link_paths) == 3


class _StubRobot:
    """Minimal RobotHandle stand-in for unit tests.

    Real ``RobotHandle`` (articulation_phases/robot_handle.py) has many more
    fields and methods. The stub only exposes the two fields ``discover_fingertips``
    actually reads in the parallel-jaw branch: ``dof_names`` and ``prim_path``
    (the asset's articulation root prim path)."""

    def __init__(self, dof_names, prim_path):
        self.dof_names = dof_names
        self.prim_path = prim_path


def _add_basis_curves(stage, parent_path, name, p0, p1):
    path = "%s/%s" % (parent_path, name)
    curves = UsdGeom.BasisCurves.Define(stage, path)
    curves.CreatePointsAttr().Set([p0, p1])
    curves.CreateCurveVertexCountsAttr().Set([2])
    curves.CreateTypeAttr().Set("linear")


def _add_gripper_site_simple(stage, parent_path, name="gripper_01"):
    """Minimal gripper site -- used only to satisfy `discover_fingertips`'s
    parameter list. The function does not currently consume site fields,
    but tests pass a real one to mirror runtime usage.

    NOTE: ``AddAppliedSchema`` (vs ``ApplyAPI``) writes the schema name to the
    prim's apiSchemas metadata without requiring the schema to be registered.
    In pure-Python USD test environments (no Kit/Isaac loaded), IsaacSiteAPI
    is not registered, so ``ApplyAPI`` raises ``Tf.ErrorException``. The
    discovery code reads schemas via ``GetAppliedSchemas()`` /
    ``GetPrimTypeInfo().GetAppliedAPISchemas()``, so ``AddAppliedSchema`` is
    functionally equivalent for our purposes (Lesson 1 from Wave 1).
    """
    site_path = "%s/%s" % (parent_path, name)
    xform = UsdGeom.Xform.Define(stage, site_path)
    prim = xform.GetPrim()
    prim.AddAppliedSchema("IsaacSiteAPI")
    _add_basis_curves(stage, site_path, "gripper_forward_axis", (0.0, -0.15, 0.0), (0.0, 0.15, 0.0))
    _add_basis_curves(stage, site_path, "gripper_grip_line", (-0.04, 0.0, 0.0), (0.04, 0.0, 0.0))
    attr = prim.CreateAttribute("gripper_maxOpening", Sdf.ValueTypeNames.Float)
    attr.Set(0.085)
    return prim


def _build_parallel_jaw_stage():
    """Asset with a base, two finger pads, two prismatic joints, and a
    PhysxMimicJointAPI tying the second joint to the first.

    PhysxMimicJointAPI is a multi-apply schema (instance name = axis token).
    We use ``PhysxSchema.PhysxMimicJointAPI.Apply(prim, axis_token)`` and the
    schema setter accessors so values are read back by the
    ``mimic_joints.detect_mimic_joints`` accessor-based reader.
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/Asset/base")
    UsdGeom.Xform.Define(stage, "/World/Asset/finger_left_pad")
    UsdGeom.Xform.Define(stage, "/World/Asset/finger_right_pad")

    j_master = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_left")
    j_master.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    body1_rel = j_master.GetPrim().CreateRelationship("physics:body1")
    body1_rel.SetTargets(["/World/Asset/finger_left_pad"])

    j_follower = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_right")
    j_follower.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    body1_rel = j_follower.GetPrim().CreateRelationship("physics:body1")
    body1_rel.SetTargets(["/World/Asset/finger_right_pad"])

    # Apply PhysxMimicJointAPI as a multi-apply schema on the follower joint
    # pointing at the master (reference) joint with gear=-1.0.
    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(j_follower.GetPrim(), UsdPhysics.Tokens.transX)
    mimic.CreateReferenceJointRel().SetTargets(["/World/Asset/joint_left"])
    mimic.CreateGearingAttr().Set(-1.0)
    mimic.CreateOffsetAttr().Set(0.0)

    return stage, asset


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_recognizes_parallel_jaw_mimic():
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset = _build_parallel_jaw_stage()
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["joint_left", "joint_right"],
        prim_path="/World/Asset",
    )

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "mimic_parallel_jaw"
    assert fs.mimic_master_dof == 0  # joint_left = the reference (master)
    assert fs.mimic_follower_dof == 1  # joint_right = the follower
    assert len(fs.tip_link_paths) == 2
    assert fs.tip_link_paths[0] == "/World/Asset/finger_left_pad"
    assert fs.tip_link_paths[1] == "/World/Asset/finger_right_pad"


def test_discover_fingertips_returns_unsupported_for_zero_mimic_zero_chain():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    _add_gripper_site_simple(stage, "/World/Asset")
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    asset = stage.GetPrimAtPath("/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=[], prim_path="/World/Asset")

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "unsupported"


def test_discover_fingertips_uses_exact_carrier_path_and_keeps_asset_joint_z():
    """Test-owned carrier filtering must not hide an asset DOF with a common name."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    UsdGeom.Xform.Define(stage, "/World/Asset/base")
    UsdGeom.Xform.Define(stage, "/World/Asset/left_pad")
    UsdGeom.Xform.Define(stage, "/World/Asset/right_pad")

    # Mirror the live FET028 scene with deliberately unrelated asset names.
    # One real finger is named ``joint_z``: filtering that basename would hide
    # valid robot motion. Only the exact, uniquely named carrier path is ignored.
    UsdGeom.Xform.Define(stage, "/World/Asset/carrier")
    carrier_path = "/World/Asset/_FET028_Carrier_a1b2/_fet028_carrier_z_a1b2"
    rail = UsdPhysics.PrismaticJoint.Define(stage, carrier_path)
    rail.GetPrim().CreateRelationship("physics:body0").SetTargets(["/World/Asset/carrier"])
    rail.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/base"])
    rail_actuator = stage.DefinePrim(
        carrier_path + "_actuator",
        "NewtonActuator",
    )
    rail_actuator.CreateRelationship("newton:targets").SetTargets([rail.GetPath()])

    for joint_name, side in (("joint_z", "left"), ("closing_axis_b", "right")):
        joint_path = "/World/Asset/Mechanism/{}".format(joint_name)
        joint = UsdPhysics.PrismaticJoint.Define(stage, joint_path)
        joint.GetPrim().CreateRelationship("physics:body0").SetTargets(["/World/Asset/base"])
        joint.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/{}_pad".format(side)])
        actuator = stage.DefinePrim(
            "/World/Asset/Actuators/{}_command".format(side),
            "NewtonActuator",
        )
        actuator.CreateRelationship("newton:targets").SetTargets([joint_path])

    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["_fet028_carrier_z_a1b2", "joint_z", "closing_axis_b"],
        prim_path="/World/Asset/base",
    )

    fs = discover_fingertips(
        stage,
        robot,
        sites[0],
        robot_prim_path="/World/Asset",
        ignored_joint_paths=(carrier_path,),
    )

    assert fs.kind == "independent_fingers"
    assert fs.finger_chains == [[1], [2]]
    assert fs.tip_link_paths == ["/World/Asset/left_pad", "/World/Asset/right_pad"]


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_rejects_mixed_3finger_with_one_mimic():
    """3 DOFs + 1 mimic is NOT a parallel-jaw -- should fall through."""
    stage, asset = _build_parallel_jaw_stage()
    # Add a third independent prismatic joint with no mimic.
    third = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_third")
    third.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    UsdGeom.Xform.Define(stage, "/World/Asset/finger_third_pad")
    third.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/finger_third_pad"])
    _add_gripper_site_simple(stage, "/World/Asset")
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["joint_left", "joint_right", "joint_third"],
        prim_path="/World/Asset",
    )
    fs = discover_fingertips(stage, robot, sites[0])
    # 3 DOFs but only 1 mimic pair -- must NOT be classified as parallel-jaw.
    assert fs.kind != "mimic_parallel_jaw"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_rejects_non_symmetric_gear():
    """gear=2.0 implies asymmetric closure -- reject for v1."""
    stage, asset = _build_parallel_jaw_stage()
    follower = stage.GetPrimAtPath("/World/Asset/joint_right")
    # Read attribute via the schema accessor name used by ``mimic_joints``.
    # The multi-apply schema authors ``physxMimic:transX:gearing`` (or similar)
    # so we look it up via the schema rather than guessing the attribute name.
    mimic_api = PhysxSchema.PhysxMimicJointAPI(follower, UsdPhysics.Tokens.transX)
    mimic_api.GetGearingAttr().Set(2.0)
    _add_gripper_site_simple(stage, "/World/Asset")
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["joint_left", "joint_right"],
        prim_path="/World/Asset",
    )
    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind != "mimic_parallel_jaw"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_falls_back_to_body0_when_body1_empty():
    """Some assets author the convention reversed: body0 is the moving link."""
    stage, asset = _build_parallel_jaw_stage()
    # Reverse the right-finger joint: clear body1, set body0 as the tip.
    j_right = stage.GetPrimAtPath("/World/Asset/joint_right")
    j_right.GetRelationship("physics:body1").ClearTargets(removeSpec=True)
    j_right.CreateRelationship("physics:body0").SetTargets(["/World/Asset/finger_right_pad"])
    _add_gripper_site_simple(stage, "/World/Asset")
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["joint_left", "joint_right"],
        prim_path="/World/Asset",
    )
    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "mimic_parallel_jaw"
    assert "/World/Asset/finger_right_pad" in fs.tip_link_paths


def _build_robotiq_style_stage(master_visible_only: bool = False):
    """Asset with one master joint and three follower joints, all referencing
    the master. Mimics the topology of a Robotiq 2F-85's 4-bar linkage:
    one driven joint, several mechanical-linkage followers, all with |gear|=1.

    Body layout puts the two contact-pad bodies on the X extremes (left/right)
    so ``_pick_two_furthest_apart`` selects them rather than the central
    linkage bodies that cluster near origin.
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()

    # Helper: create an Xform body at a given X offset.
    def _body(name, x):
        xform = UsdGeom.Xform.Define(stage, "/World/Asset/" + name)
        xform.AddTranslateOp().Set((x, 0.0, 0.0))
        return xform.GetPrim()

    # Two contact pads at the extremes.
    _body("pad_left", -0.05)
    _body("pad_right", +0.05)
    # Two internal linkage bodies near origin (not real contact pads).
    _body("linkage_a", -0.01)
    _body("linkage_b", +0.01)

    # Master joint targeting pad_left.
    j_master = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_master")
    j_master.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    j_master.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/pad_left"])

    # Three follower joints targeting pad_right and the two linkage bodies.
    follower_targets = [
        ("joint_follower_a", "linkage_a"),
        ("joint_follower_b", "linkage_b"),
        ("joint_follower_pad", "pad_right"),
    ]
    follower_paths = []
    for jn, target in follower_targets:
        j = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/" + jn)
        j.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
        j.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/" + target])
        # Apply the mimic API on each follower, all referencing the master.
        mimic = PhysxSchema.PhysxMimicJointAPI.Apply(j.GetPrim(), UsdPhysics.Tokens.transX)
        mimic.CreateReferenceJointRel().SetTargets(["/World/Asset/joint_master"])
        mimic.CreateGearingAttr().Set(-1.0)
        mimic.CreateOffsetAttr().Set(0.0)
        follower_paths.append(jn)

    if master_visible_only:
        dof_names = ["joint_master"]
    else:
        dof_names = ["joint_master"] + follower_paths
    return stage, asset, dof_names


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_recognizes_multi_mimic_single_master():
    """Robotiq-style: 1 master + 3 followers, all sharing the master and
    symmetric. Discovery should classify as parallel_jaw, picking the two
    body candidates furthest apart at rest as the tip pads."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage()
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=dof_names, prim_path="/World/Asset")

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "mimic_parallel_jaw"
    # The two extreme pads -- not the internal linkage bodies -- are tips.
    assert set(fs.tip_link_paths) == {
        "/World/Asset/pad_left",
        "/World/Asset/pad_right",
    }


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_recognizes_multi_mimic_when_followers_hidden():
    """Same Robotiq-style asset but the articulation has been initialized
    with use_mimic_joints=True, so only the master DOF is visible. Discovery
    must still classify cleanly (don't reject just because dof_names is short)."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage(master_visible_only=True)
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=dof_names, prim_path="/World/Asset")
    assert len(robot.dof_names) == 1  # mimic followers hidden by Isaac

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "mimic_parallel_jaw"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_rejects_multi_mimic_with_extra_independent_dof():
    """Robotiq-style + one extra non-mimic'd DOF should NOT classify as
    parallel_jaw -- there's a free joint we're not modelling."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage()
    # Add a sixth body + an independent joint with no mimic API.
    UsdGeom.Xform.Define(stage, "/World/Asset/free_link")
    j_free = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_free")
    j_free.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    j_free.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/free_link"])
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=dof_names + ["joint_free"],
        prim_path="/World/Asset",
    )

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind != "mimic_parallel_jaw"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_rejects_multi_mimic_with_two_distinct_masters():
    """Two independent mimic chains -- each with its own master -- is NOT a
    parallel-jaw gripper (could be e.g. a two-axis gripper or two separate
    grippers on one articulation). Reject."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage()
    # Re-target one of the followers' reference joint to a different master
    # (a synthetic second master joint).
    second_master = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_master_2")
    second_master.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    UsdGeom.Xform.Define(stage, "/World/Asset/extra_pad")
    second_master.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/extra_pad"])
    follower_a = stage.GetPrimAtPath("/World/Asset/joint_follower_a")
    mimic_a = PhysxSchema.PhysxMimicJointAPI(follower_a, UsdPhysics.Tokens.transX)
    mimic_a.CreateReferenceJointRel().SetTargets(["/World/Asset/joint_master_2"])
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=dof_names + ["joint_master_2"],
        prim_path="/World/Asset",
    )

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind != "mimic_parallel_jaw"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_accepts_two_newton_actuator_owned_jaw_leaders():
    """A Newton-native parallel jaw may split effort across one leader per side.

    Acceptance requires explicit Newton actuators for both leaders and an
    authored grip line that resolves their two opposed pad branches.
    """
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage()
    second_master = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_master_right")
    second_master.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    second_master.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/pad_right"])

    for follower_name in ("joint_follower_b", "joint_follower_pad"):
        follower = stage.GetPrimAtPath("/World/Asset/" + follower_name)
        mimic = PhysxSchema.PhysxMimicJointAPI(follower, UsdPhysics.Tokens.transX)
        mimic.CreateReferenceJointRel().SetTargets([second_master.GetPath()])

    for actuator_name, joint_path in (
        ("left_actuator", "/World/Asset/joint_master"),
        ("right_actuator", "/World/Asset/joint_master_right"),
    ):
        actuator = stage.DefinePrim("/World/Asset/" + actuator_name, "NewtonActuator")
        actuator.CreateRelationship("newton:targets").SetTargets([joint_path])

    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=dof_names + ["joint_master_right"],
        prim_path="/World/Asset",
    )

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "mimic_parallel_jaw"
    assert fs.mimic_master_dof == 0
    assert fs.mimic_master_dofs == [0, 4]
    assert set(fs.tip_link_paths) == {
        "/World/Asset/pad_left",
        "/World/Asset/pad_right",
    }


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="pxr.PhysxSchema unavailable")
def test_discover_fingertips_rejects_multi_mimic_with_one_asymmetric_gear():
    """Even one asymmetric mimic gear in the chain disqualifies the whole
    assembly -- closure is no longer guaranteed symmetric."""
    from simready_benchmark_kit_suite.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage()
    bad = stage.GetPrimAtPath("/World/Asset/joint_follower_a")
    PhysxSchema.PhysxMimicJointAPI(bad, UsdPhysics.Tokens.transX).GetGearingAttr().Set(2.5)
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=dof_names, prim_path="/World/Asset")

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind != "mimic_parallel_jaw"


def test_deepest_leaf_follows_chain_to_end():
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _deepest_leaf,
    )

    # a -> b -> c (c is the leaf, depth 2 from a).
    child_map = {"a": ["b"], "b": ["c"]}
    assert _deepest_leaf(child_map, "a") == ("c", 2)
    # A link with no children is its own leaf at depth 0.
    assert _deepest_leaf(child_map, "c") == ("c", 0)


def test_reachable_descendants_is_stable_and_cycle_safe():
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _reachable_descendants,
    )

    child_map = {"left": ["middle"], "middle": ["left", "pad"]}
    assert _reachable_descendants(child_map, "left") == ["middle", "pad"]


def test_parallel_jaw_accepts_only_detected_passive_linkage_dofs(monkeypatch):
    """Newton exposes passive four-bar DOFs that are not independent fingers."""
    from simready_benchmark_kit_suite.articulation_phases import joint_utils
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _classify_parallel_jaw_mimic,
    )
    from simready_benchmark_kit_suite.articulation_phases.mimic_joints import (
        MimicJointSpec,
    )

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    for name, x in (
        ("base", 0.0),
        ("left_driver", -0.02),
        ("right_driver", 0.02),
        ("left_pad", -0.05),
        ("right_pad", 0.05),
    ):
        body = UsdGeom.Xform.Define(stage, "/Asset/" + name)
        body.AddTranslateOp().Set((x, 0.0, 0.0))

    def _joint(name, body0, body1):
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/" + name)
        joint.CreateBody0Rel().SetTargets([body0])
        joint.CreateBody1Rel().SetTargets([body1])
        return joint

    _joint("master", "/Asset/base", "/Asset/left_driver")
    _joint("follower", "/Asset/base", "/Asset/right_driver")
    _joint("left_link", "/Asset/left_driver", "/Asset/left_pad")
    _joint("right_link", "/Asset/right_driver", "/Asset/right_pad")

    mimic = MimicJointSpec(
        follower_joint_path="/Asset/follower",
        reference_joint_path="/Asset/master",
        gear=1.0,
        offset=0.0,
        follower_dof_index=1,
        reference_dof_index=0,
        backend="newton",
    )
    robot = _StubRobot(
        dof_names=["master", "follower", "left_link", "right_link"],
        prim_path="/Asset",
    )
    monkeypatch.setattr(
        joint_utils,
        "detect_loop_joints",
        lambda *_args: (frozenset({1, 2, 3}), ["follower", "left_link", "right_link"]),
    )

    result = _classify_parallel_jaw_mimic(stage, robot, [mimic])
    assert isinstance(result, FingertipSet)
    assert result.kind == "mimic_parallel_jaw"
    assert "/Asset/left_pad" in result.candidate_tip_paths
    assert "/Asset/right_pad" in result.candidate_tip_paths


def test_independent_fingers_require_two_distinct_resolved_tips():
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _distinct_resolved_tip_paths,
    )

    assert _distinct_resolved_tip_paths(["thumb"], {"thumb": "/Hand/thumb_tip"}) is None
    assert (
        _distinct_resolved_tip_paths(
            ["thumb", "index"],
            {"thumb": "/Hand/shared_tip", "index": "/Hand/shared_tip"},
        )
        is None
    )
    assert _distinct_resolved_tip_paths(
        ["thumb", "index"],
        {"thumb": "/Hand/thumb_tip", "index": "/Hand/index_tip"},
    ) == ["/Hand/thumb_tip", "/Hand/index_tip"]


def test_actuated_branches_are_grouped_by_graph_not_joint_names():
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _group_actuated_joint_branches,
    )

    records = [
        {"path": "/J/a7", "body0": "/Palm", "body1": "/A", "idx": 0, "name": "q7"},
        {"path": "/J/a2", "body0": "/A", "body1": "/A_tip", "idx": 1, "name": "q2"},
        {"path": "/J/b9", "body0": "/Palm", "body1": "/B", "idx": 2, "name": "q9"},
    ]
    groups = _group_actuated_joint_branches(
        records,
        {"/A": "/Palm", "/A_tip": "/A", "/B": "/Palm"},
    )

    assert list(groups) == ["/J/a7", "/J/b9"]
    assert [[record["idx"] for record in branch] for branch in groups.values()] == [[0, 1], [2]]


def test_deepest_leaf_is_cycle_safe_and_still_finds_exit_leaf():
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _deepest_leaf,
    )

    child_map = {"a": ["b"], "b": ["a", "c"], "c": ["leaf"]}
    assert _deepest_leaf(child_map, "a") == ("leaf", 3)


def test_child_link_map_traverses_fixed_and_spherical_joints():
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _build_child_link_map,
        _resolve_joint_child_link_from_path,
    )

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    for name in ("base", "fixed_child", "spherical_child"):
        UsdGeom.Xform.Define(stage, f"/Asset/{name}")

    fixed = UsdPhysics.FixedJoint.Define(stage, "/Asset/fixed")
    fixed.CreateBody0Rel().SetTargets(["/Asset/base"])
    fixed.CreateBody1Rel().SetTargets(["/Asset/fixed_child"])
    spherical = UsdPhysics.SphericalJoint.Define(stage, "/Asset/spherical")
    spherical.CreateBody0Rel().SetTargets(["/Asset/fixed_child"])
    spherical.CreateBody1Rel().SetTargets(["/Asset/spherical_child"])

    assert _build_child_link_map(stage, asset) == {
        "/Asset/base": ["/Asset/fixed_child"],
        "/Asset/fixed_child": ["/Asset/spherical_child"],
    }
    assert _resolve_joint_child_link_from_path(stage, "/Asset/fixed") == "/Asset/fixed_child"


def test_distal_tip_picks_deeper_branch_over_shorter():
    """SVH thumb shape: the opposition joint's child link is a shallow leaf,
    the flexion joint's child continues through passive links to the real tip.
    The resolver must pick the deeper (flexion-chain) leaf, name-agnostically."""
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _distal_tip_of_finger,
    )

    # Actuated joints: opposition (e1 -> z), flexion (virtual_a -> a).
    joints = [
        ("/J/Thumb_Opposition", "e1", "z", "left_hand_thumb_opposition"),
        ("/J/Thumb_Flexion", "virtual_a", "a", "left_hand_thumb_flexion"),
    ]
    # Full link graph: z is a leaf; a -> b -> c via passive joints.
    child_map = {"a": ["b"], "b": ["c"]}
    assert _distal_tip_of_finger(joints, child_map) == "c"


def test_distal_tip_extends_past_last_actuated_joint():
    """A finger whose last actuated joint's child has a further PASSIVE link
    resolves to that passive leaf (the real fingertip), not the actuated link."""
    from simready_benchmark_kit_suite.articulation_phases.fingertip_discovery import (
        _distal_tip_of_finger,
    )

    joints = [
        ("/J/Index_Proximal", "palm", "p_prox", "left_hand_index_finger_proximal"),
        ("/J/Index_Distal", "p_prox", "p", "left_hand_index_finger_distal"),
    ]
    child_map = {"p_prox": ["p"], "p": ["t"]}  # p -> t is a passive extension
    assert _distal_tip_of_finger(joints, child_map) == "t"

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

from types import SimpleNamespace

import numpy as np  # noqa: F401  (kept for parity with sibling tests)
import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

# Kit binds PhysxSchema into pxr; outside Kit it comes from physx-usd-schemas.
# Mimic-driven tests skip without either, matching test_articulation_mimic_joints.py.
try:
    from pxr import PhysxSchema
except ImportError:
    try:
        from physx_usd_schemas import PhysxSchema
    except ImportError:
        PhysxSchema = None

_HAS_PHYSX_SCHEMA = PhysxSchema is not None

from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
    FingertipSet,
    GripperTopologyError,
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


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_recognizes_parallel_jaw_mimic():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    asset = stage.GetPrimAtPath("/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=[], prim_path="/World/Asset")

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "unsupported"


def test_discover_fingertips_uses_exact_carrier_path_and_keeps_asset_joint_z():
    """Test-owned carrier filtering must not hide an asset DOF with a common name."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_rejects_mixed_3finger_with_one_mimic():
    """3 DOFs + 1 mimic cannot fall through to independent follower commands."""
    stage, asset = _build_parallel_jaw_stage()
    # Add a third independent prismatic joint with no mimic.
    third = UsdPhysics.PrismaticJoint.Define(stage, "/World/Asset/joint_third")
    third.GetPrim().CreateAttribute("physxJoint:axis", Sdf.ValueTypeNames.Token).Set("X")
    UsdGeom.Xform.Define(stage, "/World/Asset/finger_third_pad")
    third.GetPrim().CreateRelationship("physics:body1").SetTargets(["/World/Asset/finger_third_pad"])
    _add_gripper_site_simple(stage, "/World/Asset")
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["joint_left", "joint_right", "joint_third"],
        prim_path="/World/Asset",
    )
    with pytest.raises(GripperTopologyError, match="active mimic topology"):
        discover_fingertips(stage, robot, sites[0])


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(
        dof_names=["joint_left", "joint_right"],
        prim_path="/World/Asset",
    )
    with pytest.raises(GripperTopologyError, match="active mimic topology"):
        discover_fingertips(stage, robot, sites[0])


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_falls_back_to_body0_when_body1_empty():
    """Some assets author the convention reversed: body0 is the moving link."""
    stage, asset = _build_parallel_jaw_stage()
    # Reverse the right-finger joint: clear body1, set body0 as the tip.
    j_right = stage.GetPrimAtPath("/World/Asset/joint_right")
    j_right.GetRelationship("physics:body1").ClearTargets(removeSpec=True)
    j_right.CreateRelationship("physics:body0").SetTargets(["/World/Asset/finger_right_pad"])
    _add_gripper_site_simple(stage, "/World/Asset")
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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

    Body layout puts the two contact-pad bodies on the X extremes (left/right),
    nearest the grip line's endpoints, so discovery selects them rather than the
    central linkage bodies that cluster near origin.
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()

    # Helper: create a body at a given X offset. Pads are matched to the grip
    # line by their world bounds, so each body needs geometry.
    def _body(name, x):
        xform = UsdGeom.Xform.Define(stage, "/World/Asset/" + name)
        xform.AddTranslateOp().Set((x, 0.0, 0.0))
        UsdGeom.Cube.Define(stage, "/World/Asset/%s/geom" % name).CreateSizeAttr(0.01)
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


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_recognizes_multi_mimic_single_master():
    """Robotiq-style: 1 master + 3 followers, all sharing the master and
    symmetric. Discovery should classify as parallel_jaw, picking the two
    body candidates furthest apart at rest as the tip pads."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_recognizes_multi_mimic_when_followers_hidden():
    """Same Robotiq-style asset but the articulation has been initialized
    with use_mimic_joints=True, so only the master DOF is visible. Discovery
    must still classify cleanly (don't reject just because dof_names is short)."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage(master_visible_only=True)
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=dof_names, prim_path="/World/Asset")
    assert len(robot.dof_names) == 1  # mimic followers hidden by Isaac

    fs = discover_fingertips(stage, robot, sites[0])
    assert fs.kind == "mimic_parallel_jaw"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_rejects_multi_mimic_with_extra_independent_dof():
    """Robotiq-style + one extra non-mimic'd DOF should NOT classify as
    parallel_jaw -- there's a free joint we're not modelling."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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

    with pytest.raises(GripperTopologyError, match="active mimic topology"):
        discover_fingertips(stage, robot, sites[0])


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_rejects_multi_mimic_with_two_distinct_masters():
    """Two independent mimic chains -- each with its own master -- is NOT a
    parallel-jaw gripper (could be e.g. a two-axis gripper or two separate
    grippers on one articulation). Reject."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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

    with pytest.raises(GripperTopologyError, match="active mimic topology"):
        discover_fingertips(stage, robot, sites[0])


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_accepts_two_newton_actuator_owned_jaw_leaders():
    """A Newton-native parallel jaw may split effort across one leader per side.

    Acceptance requires explicit Newton actuators for both leaders and an
    authored grip line that resolves their two opposed pad branches.
    """
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
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


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_discover_fingertips_rejects_multi_mimic_with_one_asymmetric_gear():
    """Even one asymmetric mimic gear in the chain disqualifies the whole
    assembly -- closure is no longer guaranteed symmetric."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_sites import (
        discover_gripper_sites,
    )

    stage, asset, dof_names = _build_robotiq_style_stage()
    bad = stage.GetPrimAtPath("/World/Asset/joint_follower_a")
    PhysxSchema.PhysxMimicJointAPI(bad, UsdPhysics.Tokens.transX).GetGearingAttr().Set(2.5)
    _add_gripper_site_simple(stage, "/World/Asset")
    sites = discover_gripper_sites(stage, asset)
    robot = _StubRobot(dof_names=dof_names, prim_path="/World/Asset")

    with pytest.raises(GripperTopologyError, match="active mimic topology"):
        discover_fingertips(stage, robot, sites[0])


def test_deepest_leaf_follows_chain_to_end():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _deepest_leaf,
    )

    # a -> b -> c (c is the leaf, depth 2 from a).
    child_map = {"a": ["b"], "b": ["c"]}
    assert _deepest_leaf(child_map, "a") == ("c", 2)
    # A link with no children is its own leaf at depth 0.
    assert _deepest_leaf(child_map, "c") == ("c", 0)


def test_reachable_descendants_is_stable_and_cycle_safe():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _reachable_descendants,
    )

    child_map = {"left": ["middle"], "middle": ["left", "pad"]}
    assert _reachable_descendants(child_map, "left") == ["middle", "pad"]


def test_parallel_jaw_accepts_only_detected_passive_linkage_dofs(monkeypatch):
    """Newton exposes passive four-bar DOFs that are not independent fingers."""
    from simready.foundation.tier_core.runtime_tests.articulation_phases import joint_utils
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _classify_parallel_jaw_mimic,
    )
    from simready.foundation.tier_core.runtime_tests.articulation_phases.mimic_joints import (
        MimicJointSpec,
    )

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
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
        lambda *_args, **_kwargs: (frozenset({1, 2, 3}), ["follower", "left_link", "right_link"]),
    )

    result = _classify_parallel_jaw_mimic(stage, robot, [mimic])
    assert isinstance(result, FingertipSet)
    assert result.kind == "mimic_parallel_jaw"
    assert "/Asset/left_pad" in result.candidate_tip_paths
    assert "/Asset/right_pad" in result.candidate_tip_paths


def test_independent_fingers_require_two_distinct_resolved_tips():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _deepest_leaf,
    )

    child_map = {"a": ["b"], "b": ["a", "c"], "c": ["leaf"]}
    assert _deepest_leaf(child_map, "a") == ("leaf", 3)


def test_child_link_map_traverses_fixed_and_spherical_joints():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
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
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _distal_tip_of_finger,
    )

    joints = [
        ("/J/Index_Proximal", "palm", "p_prox", "left_hand_index_finger_proximal"),
        ("/J/Index_Distal", "p_prox", "p", "left_hand_index_finger_distal"),
    ]
    child_map = {"p_prox": ["p"], "p": ["t"]}  # p -> t is a passive extension
    assert _distal_tip_of_finger(joints, child_map) == "t"


def _joint_root_fingers(world_body="body1", child_targets=False):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    base = UsdGeom.Xform.Define(stage, "/Asset/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(base)
    root = UsdPhysics.FixedJoint.Define(stage, "/Asset/joints/root_pin")
    getattr(root, f"Create{world_body.capitalize()}Rel")().SetTargets([base.GetPath()])
    UsdPhysics.ArticulationRootAPI.Apply(root.GetPrim())
    for digit in ("a", "b"):
        body = UsdGeom.Xform.Define(stage, "/Asset/" + digit).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        target = body.GetPath()
        if child_targets:
            target = UsdGeom.Cube.Define(stage, str(target) + "/shape").GetPath()
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joints/" + digit)
        joint.CreateBody0Rel().SetTargets([base.GetPath()])
        if child_targets:
            forwarded = asset.CreateRelationship("endpoint_" + digit)
            forwarded.SetTargets([target])
            target = forwarded.GetPath()
        joint.CreateBody1Rel().SetTargets([target])
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    robot = _StubRobot(["a", "b"], str(root.GetPath()))
    robot.asset_prim = asset
    return stage, robot


@pytest.mark.parametrize("world_body", ["body0", "body1"])
@pytest.mark.parametrize("child_targets", [False, True])
def test_joint_root_discovery_finds_sibling_fingers_and_owning_bodies(world_body, child_targets):
    stage, robot = _joint_root_fingers(world_body, child_targets)
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "independent_fingers"
    assert result.finger_chains == [[0], [1]]
    assert result.tip_link_paths == ["/Asset/a", "/Asset/b"]
    assert discover_fingertips(stage, robot, None, robot_prim_path=robot.prim_path).kind == "unsupported"


@pytest.mark.skipif(not _HAS_PHYSX_SCHEMA, reason="PhysxSchema unavailable")
def test_joint_root_discovery_preserves_selected_mimic_leader_and_branches():
    stage, robot = _joint_root_fingers(child_targets=True)
    follower = stage.GetPrimAtPath("/Asset/joints/b")
    mimic = PhysxSchema.PhysxMimicJointAPI.Apply(follower, UsdPhysics.Tokens.rotX)
    mimic.CreateReferenceJointRel().SetTargets(["/Asset/joints/a"])
    mimic.CreateGearingAttr().Set(-1)
    mimic.CreateOffsetAttr().Set(0)
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "mimic_parallel_jaw"
    assert result.mimic_master_dofs == [0]
    assert result.mimic_follower_dof == 1
    assert set(result.candidate_tip_paths) == {"/Asset/a", "/Asset/b"}
    assert len(set(result.candidate_branches.values())) == 2


@pytest.mark.parametrize("foreign_state", ["disconnected", "disabled", "inactive", "excluded"])
def test_joint_root_discovery_excludes_foreign_same_named_branches(foreign_state):
    stage, robot = _joint_root_fingers()
    palm = UsdGeom.Xform.Define(stage, "/Asset/Foreign/palm").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(palm)
    body = UsdGeom.Xform.Define(stage, "/Asset/Foreign/finger").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Foreign/joints/a")
    joint.CreateBody0Rel().SetTargets([palm.GetPath() if foreign_state == "disconnected" else "/Asset/base"])
    joint.CreateBody1Rel().SetTargets([body.GetPath()])
    UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    if foreign_state == "disabled":
        joint.CreateJointEnabledAttr().Set(False)
    elif foreign_state == "inactive":
        joint.GetPrim().SetActive(False)
    elif foreign_state == "excluded":
        joint.CreateExcludeFromArticulationAttr().Set(True)
    result = discover_fingertips(stage, robot, None)
    assert result.finger_chains == [[0], [1]]
    assert result.tip_link_paths == ["/Asset/a", "/Asset/b"]


def test_joint_root_discovery_rejects_an_unrelated_loaded_boundary():
    stage, robot = _joint_root_fingers()
    robot.asset_prim = UsdGeom.Xform.Define(stage, "/Other").GetPrim()
    with pytest.raises(GripperTopologyError, match="verified loaded asset boundary"):
        discover_fingertips(stage, robot, None)


def test_joint_root_discovery_excludes_same_named_constraint_between_selected_bodies():
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _discovery_scope,
    )

    stage, robot = _joint_root_fingers()
    constraint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Foreign/joints/b")
    constraint.CreateBody0Rel().SetTargets(["/Asset/base"])
    constraint.CreateBody1Rel().SetTargets(["/Asset/a"])
    constraint.CreateExcludeFromArticulationAttr().Set(True)
    UsdPhysics.DriveAPI.Apply(constraint.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    _, geometry_joints = _discovery_scope(stage, robot, None)
    assert str(constraint.GetPath()) in geometry_joints  # Geometry is retained, actuator ownership is not.
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "independent_fingers"
    assert result.finger_chains == [[0], [1]]
    assert result.tip_link_paths == ["/Asset/a", "/Asset/b"]


def test_joint_root_discovery_keeps_a_fixed_non_dof_tip_extension():
    stage, robot = _joint_root_fingers()
    tip = UsdGeom.Xform.Define(stage, "/Asset/distal_tip").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(tip)
    extension = UsdPhysics.FixedJoint.Define(stage, "/Asset/joints/tip_extension")
    extension.CreateBody0Rel().SetTargets(["/Asset/a"])
    extension.CreateBody1Rel().SetTargets([tip.GetPath()])
    result = discover_fingertips(stage, robot, None)
    assert result.kind == "independent_fingers"
    assert result.finger_chains == [[0], [1]]
    assert result.tip_link_paths == ["/Asset/distal_tip", "/Asset/b"]


@pytest.mark.parametrize("native_names", [["a", "b", "b"], ["a", "b", "c"]])
def test_joint_root_discovery_rejects_duplicate_selected_driven_identity_before_probing(native_names):
    stage, robot = _joint_root_fingers()
    third = UsdGeom.Xform.Define(stage, "/Asset/c").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(third)
    duplicate = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Other/joints/b")
    duplicate.CreateBody0Rel().SetTargets(["/Asset/base"])
    duplicate.CreateBody1Rel().SetTargets([third.GetPath()])
    UsdPhysics.DriveAPI.Apply(duplicate.GetPrim(), "angular").CreateStiffnessAttr(100.0)
    robot.dof_names = native_names
    with pytest.raises(GripperTopologyError, match="selected driven joint name 'b' is ambiguous"):
        discover_fingertips(stage, robot, None)


def test_joint_root_discovery_ignores_duplicate_native_names_not_used_by_selected_drives():
    stage, robot = _joint_root_fingers()
    robot.dof_names = ["a", "b", "unused", "unused"]
    result = discover_fingertips(stage, robot, None)
    assert result.finger_chains == [[0], [1]]
    assert result.tip_link_paths == ["/Asset/a", "/Asset/b"]


def test_joint_root_discovery_filters_foreign_mimics_and_rejects_external_selected_coupling(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import mimic_joints

    stage, robot = _joint_root_fingers()
    foreign = SimpleNamespace(follower_joint_path="/Asset/Foreign/joint", reference_joint_path="/Asset/Foreign/master")
    monkeypatch.setattr(mimic_joints, "detect_mimic_joints", lambda *args: [foreign])
    assert discover_fingertips(stage, robot, None).kind == "independent_fingers"
    selected = SimpleNamespace(follower_joint_path="/Asset/joints/a", reference_joint_path="/Asset/Foreign/master")
    monkeypatch.setattr(mimic_joints, "detect_mimic_joints", lambda *args: [selected])
    with pytest.raises(GripperTopologyError, match="outside its articulation"):
        discover_fingertips(stage, robot, None)

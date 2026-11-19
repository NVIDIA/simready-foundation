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
from types import SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.fet003_physics.physics_checks import (
    check_world_anchor,
    has_active_owned_world_anchor,
)


@pytest.mark.parametrize("owned_side", [0, 1])
@pytest.mark.parametrize(
    ("connection", "expected"),
    [
        ("disconnected", False),
        ("fixed", True),
        ("revolute", True),
        ("spherical", True),
        ("bounded_prismatic", True),
        ("unbounded_prismatic", False),
        ("generic", False),
        ("disabled_joint", False),
        ("disabled_body", True),
        ("blocked_body", False),
        ("breakable_anchor", False),
        ("animated_anchor", False),
        ("animated_body", False),
        ("animated_limits", False),
    ],
)
def test_world_anchor_proof_covers_every_enabled_owned_component(monkeypatch, owned_side, connection, expected):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Assembly").GetPrim()
    bodies = []
    for name in ("base", "part"):
        body = UsdGeom.Xform.Define(stage, "/Assembly/" + name).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        bodies.append(body)
    anchor = UsdPhysics.FixedJoint.Define(stage, "/Assembly/pin")
    sides = [anchor.CreateBody0Rel(), anchor.CreateBody1Rel()]
    sides[owned_side].SetTargets([bodies[0].GetPath()])
    sides[1 - owned_side].SetTargets([])
    joint_types = {
        "fixed": UsdPhysics.FixedJoint,
        "revolute": UsdPhysics.RevoluteJoint,
        "spherical": UsdPhysics.SphericalJoint,
        "bounded_prismatic": UsdPhysics.PrismaticJoint,
        "unbounded_prismatic": UsdPhysics.PrismaticJoint,
        "animated_limits": UsdPhysics.PrismaticJoint,
        "generic": UsdPhysics.Joint,
        "disabled_joint": UsdPhysics.FixedJoint,
    }
    if connection in joint_types:
        edge = joint_types[connection].Define(stage, "/Assembly/connection")
        edge.CreateBody0Rel().SetTargets([bodies[0].GetPath()])
        edge.CreateBody1Rel().SetTargets([bodies[1].GetPath()])
        if connection in ("bounded_prismatic", "animated_limits"):
            edge.CreateLowerLimitAttr(-1.0)
            edge.CreateUpperLimitAttr(1.0)
            if connection == "animated_limits":
                edge.GetUpperLimitAttr().Set(float("inf"), 1)
        if connection == "disabled_joint":
            edge.CreateJointEnabledAttr(False)
    if connection == "disabled_body":
        UsdPhysics.RigidBodyAPI(bodies[1]).CreateRigidBodyEnabledAttr(False)
    elif connection == "blocked_body":
        UsdPhysics.RigidBodyAPI(bodies[1]).GetRigidBodyEnabledAttr().Block()
    elif connection == "breakable_anchor":
        anchor.CreateBreakForceAttr(1.0)
    elif connection == "animated_anchor":
        anchor.CreateJointEnabledAttr().Set(False, 1)
    elif connection == "animated_body":
        UsdPhysics.RigidBodyAPI(bodies[1]).CreateRigidBodyEnabledAttr().Set(False, 1)
    usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
    monkeypatch.setitem(sys.modules, "omni", SimpleNamespace(usd=usd))
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    ctx = SimpleNamespace(
        scene=SimpleNamespace(asset=SimpleNamespace(prim_path=str(root.GetPath()))), log=lambda *a: None
    )
    before = stage.GetRootLayer().ExportToString()
    assert check_world_anchor(ctx)  # Existing precheck/skip semantics are unchanged.
    assert has_active_owned_world_anchor(ctx) is expected
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("joint_type", ["FixedJoint", "RevoluteJoint", "SphericalJoint", "PrismaticJoint"])
@pytest.mark.parametrize("threshold_owner", ["anchor", "connection"])
@pytest.mark.parametrize("threshold_name", ["BreakForce", "BreakTorque"])
@pytest.mark.parametrize(
    ("threshold", "expected"),
    [
        ("infinity", True),
        ("float32_max", True),
        ("float32_predecessor", False),
        ("finite", False),
        ("zero", False),
        ("negative", False),
        ("nan", False),
        ("negative_infinity", False),
        ("blocked", False),
        ("animated_max", False),
        ("animated_infinity", False),
    ],
)
def test_world_anchor_break_thresholds_preserve_whole_chain_proof(
    monkeypatch, joint_type, threshold_owner, threshold_name, threshold, expected
):
    # IEEE-754 binary32's largest finite value and its actual binary32 neighbor;
    # a binary64 nextafter would round back to max when written to USD float.
    maximum = float.fromhex("0x1.fffffep+127")
    predecessor = float.fromhex("0x1.fffffcp+127")
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Assembly").GetPrim()
    bodies = []
    for name in ("base", "middle", "tip"):
        body = UsdGeom.Xform.Define(stage, "/Assembly/" + name).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        bodies.append(body)
    anchor = UsdPhysics.FixedJoint.Define(stage, "/Assembly/pin")
    anchor.CreateBody1Rel().SetTargets([bodies[0].GetPath()])
    joints = [anchor]
    for index, (parent, child) in enumerate(zip(bodies, bodies[1:], strict=False)):
        joint = getattr(UsdPhysics, joint_type).Define(stage, "/Assembly/connection" + str(index))
        joint.CreateBody0Rel().SetTargets([parent.GetPath()])
        joint.CreateBody1Rel().SetTargets([child.GetPath()])
        if joint_type == "PrismaticJoint":
            joint.CreateLowerLimitAttr(-1.0)
            joint.CreateUpperLimitAttr(1.0)
        joints.append(joint)
    for joint in joints:
        joint.CreateBreakForceAttr(maximum)
        joint.CreateBreakTorqueAttr(maximum)
    owner = joints[0] if threshold_owner == "anchor" else joints[-1]
    attr = getattr(owner, "Get" + threshold_name + "Attr")()
    values = {
        "infinity": float("inf"),
        "float32_max": maximum,
        "float32_predecessor": predecessor,
        "finite": 1.0,
        "zero": 0.0,
        "negative": -1.0,
        "nan": float("nan"),
        "negative_infinity": -float("inf"),
    }
    if threshold == "blocked":
        attr.Block()
    elif threshold.startswith("animated_"):
        attr.Set(maximum if threshold == "animated_max" else float("inf"), 1)
    else:
        attr.Set(values[threshold])
        if threshold == "float32_predecessor":
            assert attr.Get() == predecessor < maximum
    usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
    monkeypatch.setitem(sys.modules, "omni", SimpleNamespace(usd=usd))
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    ctx = SimpleNamespace(
        scene=SimpleNamespace(asset=SimpleNamespace(prim_path=str(root.GetPath()))), log=lambda *a: None
    )
    before = stage.GetRootLayer().ExportToString()
    assert check_world_anchor(ctx)
    assert has_active_owned_world_anchor(ctx) is expected
    assert stage.GetRootLayer().ExportToString() == before

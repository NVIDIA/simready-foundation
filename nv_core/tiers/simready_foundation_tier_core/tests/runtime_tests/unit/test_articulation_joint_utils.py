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
"""Tests for articulation_phases.joint_utils."""
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    BBoxSnapshot,
    check_bbox_explode,
    compute_world_aligned_bbox,
    detect_loop_joints,
    safe_len,
)


def test_bbox_snapshot_volume():
    s = BBoxSnapshot(
        min_point=(0.0, 0.0, 0.0),
        max_point=(2.0, 3.0, 4.0),
    )
    assert abs(s.volume - 24.0) < 1e-9


def test_bbox_snapshot_zero_volume_for_degenerate():
    s = BBoxSnapshot(
        min_point=(0.0, 0.0, 0.0),
        max_point=(0.0, 0.0, 0.0),
    )
    assert s.volume == 0.0


def test_check_bbox_explode_returns_none_when_within_ratio():
    baseline = BBoxSnapshot((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    current = BBoxSnapshot((0.0, 0.0, 0.0), (2.0, 2.0, 2.0))
    assert check_bbox_explode(current, baseline, ratio=10.0) is None


def test_check_bbox_explode_returns_message_when_exceeds_ratio():
    baseline = BBoxSnapshot((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    current = BBoxSnapshot((0.0, 0.0, 0.0), (3.0, 3.0, 3.0))
    msg = check_bbox_explode(current, baseline, ratio=10.0)
    assert msg is not None
    assert "explode" in msg.lower() or "bbox" in msg.lower()


def test_check_bbox_explode_handles_zero_baseline():
    baseline = BBoxSnapshot((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    current = BBoxSnapshot((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    assert check_bbox_explode(current, baseline, ratio=10.0) is None


def test_compute_world_aligned_bbox_ignores_non_geometry_control_prims():
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.DefinePrim("/Robot/Actuators", "Scope")
    actuator = stage.DefinePrim("/Robot/Actuators/finger_actuator")
    actuator.SetTypeName("NewtonActuator")
    cube = UsdGeom.Cube.Define(stage, "/Robot/Geometry/cube")
    cube.GetSizeAttr().Set(2.0)

    bounds = compute_world_aligned_bbox(root)

    assert bounds.min_point == (-1.0, -1.0, -1.0)
    assert bounds.max_point == (1.0, 1.0, 1.0)


def test_compute_world_aligned_bbox_returns_zero_for_control_only_prim():
    from pxr import Usd

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.DefinePrim("/Robot/Actuators/finger_actuator", "NewtonActuator")

    bounds = compute_world_aligned_bbox(root)

    assert bounds.min_point == (0.0, 0.0, 0.0)
    assert bounds.max_point == (0.0, 0.0, 0.0)


def test_detect_loop_joints_keeps_native_newton_actuated_four_bar_driver():
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    for name in ("base", "outer", "inner", "finger"):
        UsdGeom.Xform.Define(stage, "/Robot/Links/%s" % name)

    def add_joint(name, body0, body1, excluded=False):
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/Joints/%s" % name)
        joint.CreateBody0Rel().SetTargets([Sdf.Path("/Robot/Links/%s" % body0)])
        joint.CreateBody1Rel().SetTargets([Sdf.Path("/Robot/Links/%s" % body1)])
        if excluded:
            joint.GetPrim().CreateAttribute("physics:excludeFromArticulation", Sdf.ValueTypeNames.Bool).Set(True)
        return joint

    add_joint("driver", "base", "outer")
    add_joint("outer_follower", "outer", "finger")
    add_joint("inner_follower", "finger", "inner")
    add_joint("closure", "inner", "base", excluded=True)
    actuator = stage.DefinePrim("/Robot/Actuators/fingers", "NewtonActuator")
    actuator.CreateRelationship("newton:targets").SetTargets(["/Robot/Joints/driver"])

    indices, names = detect_loop_joints(
        stage,
        str(root.GetPath()),
        ["driver", "outer_follower", "inner_follower"],
    )

    assert "driver" not in names
    assert 0 not in indices
    assert set(names) == {"outer_follower", "inner_follower"}


def test_detect_loop_joints_keeps_mjc_tendon_actuated_four_bar_driver():
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    for name in ("base", "outer", "inner", "finger"):
        UsdGeom.Xform.Define(stage, "/Robot/Links/%s" % name)

    def add_joint(name, body0, body1, excluded=False):
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/Joints/%s" % name)
        joint.CreateBody0Rel().SetTargets([Sdf.Path("/Robot/Links/%s" % body0)])
        joint.CreateBody1Rel().SetTargets([Sdf.Path("/Robot/Links/%s" % body1)])
        if excluded:
            joint.GetPrim().CreateAttribute("physics:excludeFromArticulation", Sdf.ValueTypeNames.Bool).Set(True)
        return joint

    add_joint("driver", "base", "outer")
    add_joint("outer_follower", "outer", "finger")
    add_joint("inner_follower", "finger", "inner")
    add_joint("closure", "inner", "base", excluded=True)
    tendon = stage.DefinePrim("/Robot/Actuators/tendon", "MjcTendon")
    tendon.CreateRelationship("mjc:path").SetTargets(["/Robot/Joints/driver"])
    actuator = stage.DefinePrim("/Robot/Actuators/fingers", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets([tendon.GetPath()])

    indices, names = detect_loop_joints(
        stage,
        str(root.GetPath()),
        ["driver", "outer_follower", "inner_follower"],
    )

    assert "driver" not in names
    assert 0 not in indices
    assert set(names) == {"outer_follower", "inner_follower"}


def test_detect_loop_joints_maps_all_axes_of_excluded_spherical_closure():
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    for name in ("base", "driver", "spring", "follower", "coupler"):
        UsdGeom.Xform.Define(stage, "/Robot/Links/%s" % name)

    def connect(joint, body0, body1, excluded=False):
        joint.CreateBody0Rel().SetTargets([Sdf.Path("/Robot/Links/%s" % body0)])
        joint.CreateBody1Rel().SetTargets([Sdf.Path("/Robot/Links/%s" % body1)])
        if excluded:
            joint.GetPrim().CreateAttribute("physics:excludeFromArticulation", Sdf.ValueTypeNames.Bool).Set(True)

    driver = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/Joints/driver")
    connect(driver, "base", "driver")
    fixed = UsdPhysics.FixedJoint.Define(stage, "/Robot/Joints/coupler_fixed")
    connect(fixed, "driver", "coupler")
    spring = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/Joints/spring")
    connect(spring, "base", "spring")
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/Joints/follower")
    connect(follower, "spring", "follower")
    closure = UsdPhysics.SphericalJoint.Define(stage, "/Robot/Joints/closure")
    connect(closure, "follower", "coupler", excluded=True)
    actuator = stage.DefinePrim("/Robot/Actuators/fingers", "NewtonActuator")
    actuator.CreateRelationship("newton:targets").SetTargets(["/Robot/Joints/driver"])

    indices, names = detect_loop_joints(
        stage,
        str(root.GetPath()),
        ["driver", "spring", "follower", "closure:0", "closure:1", "closure:2"],
    )

    assert "driver" not in names
    assert set(names) == {"spring", "follower", "closure"}
    assert indices == frozenset({1, 2, 3, 4, 5})


def test_safe_len_of_none_is_zero():
    assert safe_len(None) == 0


def test_safe_len_of_list():
    assert safe_len([1, 2, 3]) == 3


def test_safe_len_of_non_sized_object_is_zero():
    class NoLen:
        pass

    assert safe_len(NoLen()) == 0

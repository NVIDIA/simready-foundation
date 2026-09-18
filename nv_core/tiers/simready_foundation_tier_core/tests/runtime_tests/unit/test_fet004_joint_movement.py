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

"""Focused tests for FET004 joint-movement excitation and measurement."""

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from pxr import Gf, Usd, UsdPhysics


# The focused helpers below are pure USD logic, but their production module also
# imports Kit-only visualization/runtime helpers. Keep this unit test runnable in
# the normal Python test environment without requiring a Kit process.
@pytest.fixture()
def joint_movement(monkeypatch):
    """Load the production module without leaking Kit stubs into pytest."""
    fabric_utils = types.ModuleType("simready_benchmark_engine_kit.fabric_utils")
    fabric_utils.live_world_matrix = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "simready_benchmark_engine_kit.fabric_utils", fabric_utils)

    force_display = types.ModuleType("simready_benchmark_engine_kit.force_display")
    force_display.clear_visuals = lambda *_args, **_kwargs: None
    force_display.compute_arrow_length = lambda *_args, **_kwargs: 0.0
    force_display.draw_force_arrow = lambda *_args, **_kwargs: None
    force_display.get_prim_world_position = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "simready_benchmark_engine_kit.force_display", force_display)

    physics_utils = types.ModuleType("simready_benchmark_engine_kit.physics_utils")
    physics_utils.active_physics_engine = lambda *_args, **_kwargs: "physx"
    physics_utils.find_root_body = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "simready_benchmark_engine_kit.physics_utils", physics_utils)

    decorator_module = types.ModuleType("simready_benchmark.core.decorator")
    decorator_module.test = lambda *_args, **_kwargs: lambda fn: fn
    monkeypatch.setitem(sys.modules, "simready_benchmark.core.decorator", decorator_module)

    source = (
        Path(__file__).resolve().parents[3]
        / "simready_benchmark_kit_suite"
        / "fet004_multibody"
        / "joint_movement.py"
    )
    module_name = "_test_fet004_joint_movement_impl"
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _rigid_body(stage, path):
    prim = stage.DefinePrim(path, "Xform")
    UsdPhysics.RigidBodyAPI.Apply(prim)
    return prim


def test_spherical_drive_axes_exclude_authored_primary_axis(joint_movement):
    assert joint_movement._spherical_drive_axes({"axis": "X"}) == ("rotY", "rotZ")
    assert joint_movement._spherical_drive_axes({"axis": "Y"}) == ("rotX", "rotZ")
    assert joint_movement._spherical_drive_axes({"axis": "Z"}) == ("rotX", "rotY")


def test_external_spherical_driver_copies_frame_and_locks_other_dofs(joint_movement):
    stage = Usd.Stage.CreateInMemory()
    _rigid_body(stage, "/Asset/parent")
    _rigid_body(stage, "/Asset/child")
    spherical = UsdPhysics.SphericalJoint.Define(stage, "/Asset/spherical")
    spherical.CreateAxisAttr("X")
    spherical.CreateBody0Rel().SetTargets(["/Asset/parent"])
    spherical.CreateBody1Rel().SetTargets(["/Asset/child"])
    spherical.CreateLocalPos0Attr(Gf.Vec3f(1, 2, 3))
    spherical.CreateLocalRot0Attr(Gf.Quatf(1.0))
    spherical.CreateLocalPos1Attr(Gf.Vec3f(4, 5, 6))
    spherical.CreateLocalRot1Attr(Gf.Quatf(0.0, Gf.Vec3f(1, 0, 0)))
    record = {
        "prim_path": "/Asset/spherical",
        "type_name": "PhysicsSphericalJoint",
        "axis": "X",
    }

    driver_path = joint_movement._create_external_spherical_driver(
        stage, record, "rotY", 30.0, 40.0, 50.0
    )

    driver = UsdPhysics.Joint.Get(stage, driver_path)
    assert driver.GetExcludeFromArticulationAttr().Get() is True
    assert driver.GetBody0Rel().GetTargets() == spherical.GetBody0Rel().GetTargets()
    assert driver.GetBody1Rel().GetTargets() == spherical.GetBody1Rel().GetTargets()
    assert driver.GetLocalPos0Attr().Get() == spherical.GetLocalPos0Attr().Get()
    assert driver.GetLocalRot0Attr().Get() == spherical.GetLocalRot0Attr().Get()
    assert driver.GetLocalPos1Attr().Get() == spherical.GetLocalPos1Attr().Get()
    assert driver.GetLocalRot1Attr().Get() == spherical.GetLocalRot1Attr().Get()
    for axis in ("transX", "transY", "transZ", "rotX", "rotZ"):
        limit = UsdPhysics.LimitAPI.Get(driver.GetPrim(), axis)
        assert limit.GetLowAttr().Get() == 1.0
        assert limit.GetHighAttr().Get() == -1.0
    assert not driver.GetPrim().HasAPI(UsdPhysics.LimitAPI, "rotY")
    drive = UsdPhysics.DriveAPI.Get(driver.GetPrim(), "rotY")
    assert drive.GetTypeAttr().Get() == "force"
    assert drive.GetStiffnessAttr().Get() == 0.0
    assert drive.GetDampingAttr().Get() == 40.0
    assert drive.GetTargetVelocityAttr().Get() == 30.0
    assert drive.GetMaxForceAttr().Get() == 50.0


def test_joint_tracker_detects_child_rotation_relative_to_parent(monkeypatch, joint_movement):
    stage = Usd.Stage.CreateInMemory()
    _rigid_body(stage, "/Asset/parent")
    _rigid_body(stage, "/Asset/child")
    matrices = {
        "/Asset/parent": Gf.Matrix4d(1.0),
        "/Asset/child": Gf.Matrix4d(1.0),
    }
    monkeypatch.setattr(joint_movement, "_get_world_matrix", lambda _stage, path: matrices[path])
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda _stage, _path: 1.0)
    tracker = joint_movement.JointTracker(
        stage,
        {
            "child_body_path": "/Asset/child",
            "parent_body_path": "/Asset/parent",
            "_rot_thresh_deg": 1.0,
            "_trans_thresh_pct": 2.0,
        },
    )

    common_rotation = Gf.Matrix4d(1.0)
    common_rotation.SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 25.0))
    relative_rotation = Gf.Matrix4d(1.0)
    relative_rotation.SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), 8.0))
    matrices["/Asset/parent"] = common_rotation
    matrices["/Asset/child"] = relative_rotation * common_rotation

    tracker.update()

    result = tracker.result()
    assert result["rotation_deg"] == pytest.approx(8.0, abs=0.001)
    assert result["translation_m"] == 0.0
    assert result["moved"] is True


def test_perpendicular_force_directions_prioritize_largest_lever_torque(joint_movement):
    directions = joint_movement._perpendicular_force_directions((2.0, 0.0, 0.0))

    assert directions == [(0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


def test_newton_link_mass_reads_selected_runtime_body(joint_movement):
    class PhysicsView:
        def get_masses(self):
            return np.asarray([[4.0, 0.125, 8.0]], dtype=np.float32)

    force_view = {"physics_view": PhysicsView(), "body_index": 1}

    assert joint_movement._newton_link_mass(force_view) == pytest.approx(0.125)


def test_newton_force_probe_balances_child_and_parent_wrench(joint_movement):
    class PhysicsView:
        def apply_forces_and_torques_at_position(
            self, forces, torques, positions, indices, is_global
        ):
            self.call = (forces, torques, positions, indices, is_global)

    physics_view = PhysicsView()
    force_view = {
        "art": object(),
        "physics_view": physics_view,
        "body_count": 3,
        "body_index": 2,
        "parent_index": 0,
    }

    joint_movement._apply_newton_force_at_position(
        force_view,
        direction=(0.0, 1.0, 0.0),
        magnitude=0.25,
        position=(1.0, 2.0, 3.0),
    )

    forces, torques, positions, indices, is_global = physics_view.call
    assert torques is None
    assert is_global is True
    assert indices.tolist() == [0]
    assert forces[0, 2].tolist() == pytest.approx([0.0, 0.25, 0.0])
    assert forces[0, 0].tolist() == pytest.approx([0.0, -0.25, 0.0])
    assert np.allclose(np.sum(forces, axis=1), 0.0)
    assert positions[0, 2].tolist() == pytest.approx([1.0, 2.0, 3.0])
    assert positions[0, 0].tolist() == pytest.approx([1.0, 2.0, 3.0])

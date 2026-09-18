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
"""Tests for articulation_phases.object_spawning."""
import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.articulation_phases.object_spawning import (
    SpawnedObject,
    spawn_test_object,
)


def _empty_stage():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    return stage


def test_spawn_sphere_creates_rigid_body_with_mass_and_pose():
    stage = _empty_stage()
    pose = np.eye(4)
    pose[3, 0] = 0.5
    pose[3, 1] = -0.25
    pose[3, 2] = 1.0
    obj = spawn_test_object(
        stage=stage,
        parent_path="/World",
        shape="sphere",
        size_m=0.05,
        mass_kg=2.0,
        static_friction=2.0,
        dynamic_friction=2.0,
        restitution=0.0,
        pose_world=pose,
    )
    assert isinstance(obj, SpawnedObject)
    assert obj.shape == "sphere"
    prim = stage.GetPrimAtPath(obj.prim_path)
    assert prim.IsValid()
    sphere = UsdGeom.Sphere(prim)
    assert sphere
    assert sphere.GetRadiusAttr().Get() == 0.025
    assert prim.HasAPI(UsdPhysics.CollisionAPI)
    assert prim.HasAPI(UsdPhysics.RigidBodyAPI)
    assert prim.HasAPI(UsdPhysics.MassAPI)
    assert abs(prim.GetAttribute("physics:mass").Get() - 2.0) < 1e-6
    # Pose: prim's local-to-world translation matches input.
    cache = UsdGeom.XformCache()
    final = np.array(cache.GetLocalToWorldTransform(prim)).reshape(4, 4)
    assert np.allclose(final[3, :3], np.array([0.5, -0.25, 1.0]), atol=1e-6)


def test_spawn_cube_creates_cube_with_size():
    stage = _empty_stage()
    obj = spawn_test_object(stage, "/World", "cube", 0.05, 2.0, 2.0, 2.0, 0.0, np.eye(4))
    cube = UsdGeom.Cube(stage.GetPrimAtPath(obj.prim_path))
    assert cube.GetSizeAttr().Get() == 0.05


def test_each_spawn_uses_a_unique_removable_namespace():
    stage = _empty_stage()
    first = spawn_test_object(stage, "/World", "cube", 0.05, 2.0, 2.0, 2.0, 0.0, np.eye(4))
    second = spawn_test_object(stage, "/World", "cube", 0.05, 2.0, 2.0, 2.0, 0.0, np.eye(4))

    assert first.root_path != second.root_path
    stage.RemovePrim(first.root_path)
    assert not stage.GetPrimAtPath(first.root_path).IsValid()
    assert stage.GetPrimAtPath(second.root_path).IsValid()


def test_spawn_creates_physics_material_with_friction_and_restitution():
    stage = _empty_stage()
    obj = spawn_test_object(stage, "/World", "sphere", 0.05, 2.0, 2.5, 2.0, 0.1, np.eye(4))
    mat = stage.GetPrimAtPath(obj.material_path)
    assert mat.IsValid()
    assert abs(mat.GetAttribute("physics:staticFriction").Get() - 2.5) < 1e-6
    assert abs(mat.GetAttribute("physics:dynamicFriction").Get() - 2.0) < 1e-6
    assert abs(mat.GetAttribute("physics:restitution").Get() - 0.1) < 1e-6


def test_spawn_newton_object_applies_newton_collision_contract():
    stage = _empty_stage()
    obj = spawn_test_object(
        stage,
        "/World",
        "sphere",
        0.05,
        2.0,
        2.5,
        2.0,
        0.1,
        np.eye(4),
        physics_engine="newton",
    )

    prim = stage.GetPrimAtPath(obj.prim_path)
    api_schemas = prim.GetMetadata("apiSchemas")
    authored_schemas = {
        str(schema)
        for schemas in (
            api_schemas.explicitItems,
            api_schemas.prependedItems,
            api_schemas.appendedItems,
            api_schemas.addedItems,
        )
        for schema in schemas
    }
    assert "NewtonCollisionAPI" in authored_schemas
    assert prim.GetAttribute("newton:contactGap").Get() == pytest.approx(0.0)


def test_spawn_unknown_shape_raises():
    stage = _empty_stage()
    with pytest.raises(ValueError):
        spawn_test_object(stage, "/World", "tetrahedron", 0.05, 1.0, 2.0, 2.0, 0.0, np.eye(4))

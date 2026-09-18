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
"""Spawn rigid-body sphere/cube test objects with a high-friction physics
material for FET028 grasp-and-lift tests."""
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade


@dataclass
class SpawnedObject:
    root_path: str
    prim_path: str
    material_path: str
    shape: Literal["sphere", "cube"]


_OBJECTS_ROOT = "/World/_FET028_Objects"


def spawn_test_object(
    stage,
    parent_path: str,
    shape: Literal["sphere", "cube"],
    size_m: float,
    mass_kg: float,
    static_friction: float,
    dynamic_friction: float,
    restitution: float,
    pose_world: np.ndarray,
    physics_engine: str | None = None,
) -> SpawnedObject:
    """Create geometry → CollisionAPI → RigidBodyAPI → MassAPI → bind material.

    Order matters: collision geometry must exist before MassAPI so PhysX has
    a defined body to compute mass/inertia from.
    """
    suffix = uuid4().hex[:8]
    objects_root = "%s/%s_%s" % (parent_path.rstrip("/"), _OBJECTS_ROOT.rsplit("/", 1)[-1], suffix)
    UsdGeom.Xform.Define(stage, objects_root)
    obj_path = "%s/%s" % (objects_root, shape)
    if shape == "sphere":
        gprim = UsdGeom.Sphere.Define(stage, obj_path)
        gprim.CreateRadiusAttr().Set(size_m / 2.0)
        # Vivid orange so the small (cm-scale) test object is clearly
        # visible in side-view captures against the gray gripper and
        # ground plane.
        display_color = Gf.Vec3f(1.0, 0.4, 0.0)
    elif shape == "cube":
        gprim = UsdGeom.Cube.Define(stage, obj_path)
        gprim.CreateSizeAttr().Set(size_m)
        # Distinct color from the sphere so the two phases are easy to
        # tell apart at a glance in the report.
        display_color = Gf.Vec3f(0.1, 0.7, 1.0)
    else:
        raise ValueError("shape must be 'sphere' or 'cube', got: %r" % shape)
    gprim.CreateDisplayColorAttr().Set([display_color])
    prim = gprim.GetPrim()
    UsdGeom.Xformable(prim).MakeMatrixXform().Set(Gf.Matrix4d(*pose_world.flatten().tolist()))
    UsdPhysics.CollisionAPI.Apply(prim)
    if physics_engine == "newton":
        # Synthetic FET028 objects need the same explicit Newton collider
        # contract as Newton-ready assets; generic USD Physics collision alone
        # is not a reliable Newton representation in composed scenes.
        prim.AddAppliedSchema("NewtonCollisionAPI")
        prim.CreateAttribute("newton:contactGap", Sdf.ValueTypeNames.Float).Set(0.0)
    UsdPhysics.RigidBodyAPI.Apply(prim)
    mass_api = UsdPhysics.MassAPI.Apply(prim)
    mass_api.CreateMassAttr().Set(float(mass_kg))

    mat_path = "%s/_material" % objects_root
    mat = UsdShade.Material.Define(stage, mat_path)
    UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    for name, val in (
        ("physics:dynamicFriction", dynamic_friction),
        ("physics:staticFriction", static_friction),
        ("physics:restitution", restitution),
    ):
        attr = mat.GetPrim().GetAttribute(name)
        if not attr or not attr.IsDefined():
            attr = mat.GetPrim().CreateAttribute(name, Sdf.ValueTypeNames.Float)
        attr.Set(float(val))

    # Bind via direct ``material:binding:physics`` relationship (matches what
    # the asset validator queries for; see physics_materials/validation.py).
    binding = UsdShade.MaterialBindingAPI.Apply(prim)
    binding.Bind(
        mat,
        bindingStrength=UsdShade.Tokens.weakerThanDescendants,
        materialPurpose="physics",
    )

    return SpawnedObject(root_path=objects_root, prim_path=obj_path, material_path=mat_path, shape=shape)

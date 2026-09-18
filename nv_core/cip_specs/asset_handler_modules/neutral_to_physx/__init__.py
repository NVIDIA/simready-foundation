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
import os
import sys

from omni.cip.configurable.feature_adapter import feature_adapter
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None
# Add the root directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@feature_adapter(
    name="rigid_body_neutral_to_robot_physx",
    input_feature_id="FET_003_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_004_ROBOT_PHYSX",
    output_feature_version="0.2.0",
)
def rigid_body_neutral_to_robot_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)


@feature_adapter(
    name="rigid_body_neutral_to_robot_physx_2",
    input_feature_id="FET004_BASE_NEUTRAL",
    input_feature_version="0.2.0",
    output_feature_id="FET004_ROBOT_PHYSX",
    output_feature_version="0.3.0",
)
def rigid_body_neutral_to_robot_physx_2(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)


@feature_adapter(
    name="rigid_body_neutral_to_prop_physx",
    input_feature_id="FET_003_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_003_PHYSX",
    output_feature_version="0.1.0",
)
def rigid_body_neutral_to_prop_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _compute_extent(output_stage)


@feature_adapter(
    name="collider_neutral_to_prop_physx",
    input_feature_id="FET_004_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_004_PHYSX",
    output_feature_version="0.1.0",
)
def collider_neutral_to_prop_physx(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # set collider approximation to SDF
    _set_collider_approximation_to_sdf(output_stage)


@feature_adapter(
    name="collider_neutral_to_prop_physx_2",
    input_feature_id="FET004_BASE_NEUTRAL",
    input_feature_version="0.2.0",
    output_feature_id="FET004_ROBOT_PHYSX",
    output_feature_version="0.3.0",
)
def collider_neutral_to_prop_physx_2(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # set collider approximation to SDF
    _set_mesh_collider_sdf_approximation(output_stage)


def _compute_extent(stage: Usd.Stage):
    # compute extent for all meshes
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            boundable = UsdGeom.Boundable(prim)
            extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
            boundable.GetExtentAttr().Set(extent)


def _set_collider_approximation_to_sdf(stage: Usd.Stage):
    # Set the collider approximation to SDF
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return
    for child in Usd.PrimRange(default_prim):
        found_collider = False
        if child.HasAPI(UsdPhysics.MeshCollisionAPI):
            collider = UsdPhysics.MeshCollisionAPI(child)
            approx_attr = collider.GetApproximationAttr()
            if approx_attr:
                approx_attr.Set("sdf")
                found_collider = True
        elif child.HasAPI(UsdPhysics.CollisionAPI):
            collider = UsdPhysics.MeshCollisionAPI(child)
            approx_attr = child.GetAttribute("physics:approximation")
            if not approx_attr:
                child.CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token)
                approx_attr = child.GetAttribute("physics:approximation")
            approx_attr.Set("sdf")
            found_collider = True
        if found_collider:
            if PhysxSchema is None:
                raise RuntimeError("PhysxSchema is not available in this environment")
            child.ApplyAPI(PhysxSchema.PhysxCollisionAPI)
            child.ApplyAPI(PhysxSchema.PhysxSDFMeshCollisionAPI)
            child.ApplyAPI(UsdPhysics.MeshCollisionAPI)

    stage.Save()


def _set_mesh_collider_sdf_approximation(stage: Usd.Stage):
    # Set SDF collision approximation on mesh colliders only.
    #
    # Unlike _set_collider_approximation_to_sdf, this only touches UsdGeom.Mesh
    # (or PhysxMeshMergeCollisionAPI) colliders, preserves an already-authored
    # approximation unless it is "none", and authors a default sdfResolution.
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return
    for child in Usd.PrimRange(default_prim):
        if not child.HasAPI(UsdPhysics.CollisionAPI):
            continue

        is_mesh = child.IsA(UsdGeom.Mesh)
        is_merge_mesh = PhysxSchema is not None and child.HasAPI(PhysxSchema.PhysxMeshMergeCollisionAPI)
        # Leave regular non-mesh colliders (Cube, Sphere, etc.) untouched.
        if not (is_mesh or is_merge_mesh):
            continue

        child.ApplyAPI(UsdPhysics.MeshCollisionAPI)
        collider = UsdPhysics.MeshCollisionAPI(child)
        approx_attr = collider.GetApproximationAttr()

        # Only set "sdf" when nothing meaningful is authored yet.
        # or "none", which would use the expsensive triangle mesh approximation.
        if not approx_attr.HasAuthoredValue() or approx_attr.Get() == "none":
            collider.CreateApproximationAttr("sdf")
            approx_value = "sdf"
        else:
            approx_value = approx_attr.Get()

        if approx_value == "sdf":
            if PhysxSchema is None:
                raise RuntimeError("PhysxSchema is not available in this environment")
            child.ApplyAPI(PhysxSchema.PhysxCollisionAPI)
            sdf_api = PhysxSchema.PhysxSDFMeshCollisionAPI.Apply(child)
            resolution_attr = sdf_api.GetSdfResolutionAttr()
            if not resolution_attr.HasAuthoredValue():
                sdf_api.CreateSdfResolutionAttr(256)

    stage.Save()

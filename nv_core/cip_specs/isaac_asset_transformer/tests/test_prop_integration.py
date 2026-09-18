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
from __future__ import annotations

from pathlib import Path

from conftest import REPOSITORY_ROOT
from pxr import Sdf, Usd, UsdShade
from simready.asset_transformer import transform_package

TOOLBOX = (
    REPOSITORY_ROOT
    / "sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01"
    / "simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd"
)


def _interface_summary(interface_path: Path) -> tuple:
    layer = Sdf.Layer.FindOrOpen(str(interface_path))
    root = layer.GetPrimAtPath("/RootNode")
    variants = tuple(
        (name, tuple(sorted(variant_set.variants.keys()))) for name, variant_set in sorted(root.variantSets.items())
    )
    references = tuple(ref.assetPath for ref in root.referenceList.GetAddedOrExplicitItems())
    return (
        tuple(prim.name for prim in layer.rootPrims),
        variants,
        tuple(sorted(root.variantSelections.items())),
        references,
    )


def test_toolbox_prop_transform_is_clean_and_repeatable(tmp_path: Path) -> None:
    outputs = []
    for name in ("first", "second"):
        package = tmp_path / name
        report = transform_package(
            str(TOOLBOX),
            package,
            profile="simready_physx_to_isaac_prop",
            interface_asset_name="toolbox.usda",
        )
        assert all(result.success for result in report.results)
        outputs.append(package / "toolbox.usda")

    assert _interface_summary(outputs[0]) == _interface_summary(outputs[1])

    layer = Sdf.Layer.FindOrOpen(str(outputs[0]))
    root = layer.GetPrimAtPath("/RootNode")
    assert [prim.name for prim in layer.rootPrims] == ["RootNode"]
    assert set(root.variantSets.keys()) == {"PhysX", "Newton", "MuJoCo"}
    assert dict(root.variantSelections) == {
        "PhysX": "Enabled",
        "Newton": "Disabled",
        "MuJoCo": "Disabled",
    }
    assert all(set(variant_set.variants.keys()) == {"Enabled", "Disabled"} for variant_set in root.variantSets.values())

    package = outputs[0].parent
    base_layer = Sdf.Layer.FindOrOpen(str(package / "payloads/base.usda"))
    base_root = base_layer.GetPrimAtPath("/RootNode")
    asset_identifier = base_root.GetInfo("assetInfo")["identifier"].path
    assert asset_identifier.startswith(("./", "../"))
    assert (package / "payloads" / asset_identifier).resolve() == outputs[0].resolve()

    runtime_instance_layers = {
        "PhysX": "instances_physx.usda",
        "Newton": "instances_newton.usda",
        "MuJoCo": "instances_mujoco.usda",
    }
    for runtime, instances_layer in runtime_instance_layers.items():
        assert (package / f"payloads/{runtime}/enabled.usda").is_file()
        assert (package / f"payloads/{runtime}/disabled.usda").is_file()
        assert (package / f"payloads/{instances_layer}").is_file()
    assert sorted(path.name for path in (package / "payloads/Physics").iterdir()) == ["physics.usda"]
    assert not (package / "payloads/robot.usda").exists()

    stage = Usd.Stage.Open(str(outputs[0]))
    stage.SetEditTarget(stage.GetSessionLayer())
    root_prim = stage.GetDefaultPrim()
    assert stage.GetPrimAtPath("/RootNode/Joints/joint_lid_joint_01")
    assert stage.GetPrimAtPath("/RootNode/Geometry/box_obj_01/grasp_identifier")
    assert not any("IsaacRobotAPI" in prim.GetAppliedSchemas() for prim in stage.Traverse())

    collider_paths = (
        "/RootNode/Geometry/box_obj_01/box_mesh_01/box_mesh_01",
        "/RootNode/Geometry/lock_00_obj_01/lock_00_mesh_01",
    )
    expected_approximations = {
        "PhysX": "sdf",
        "Newton": "none",
        "MuJoCo": "convexHull",
    }
    for selected_runtime, expected_approximation in expected_approximations.items():
        for runtime in expected_approximations:
            root_prim.GetVariantSet(runtime).SetVariantSelection(
                "Enabled" if runtime == selected_runtime else "Disabled"
            )
        for collider_path in collider_paths:
            mesh = stage.GetPrimAtPath(collider_path)
            assert mesh.IsInstanceProxy()
            assert mesh.GetAttribute("physics:approximation").Get() == expected_approximation
            physics_material, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial("physics")
            assert physics_material

    enabled_layer = Sdf.Layer.FindOrOpen(str(package / "payloads/PhysX/enabled.usda"))
    box_wrapper = enabled_layer.GetPrimAtPath("/RootNode/Geometry/box_obj_01/box_mesh_01")
    references = box_wrapper.referenceList.GetAddedOrExplicitItems()
    assert len(references) == 1
    assert references[0].assetPath == "../instances_physx.usda"
    assert not box_wrapper.attributes

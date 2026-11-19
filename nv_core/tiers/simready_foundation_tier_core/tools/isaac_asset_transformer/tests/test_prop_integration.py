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

import os
import stat
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, UsdUtils
from simready.asset_transformer import transform_package

# Pre-composition PhysX prop fixture. This is a pristine copy of the
# obs_electricians_large_tool_box_a01 package as it existed before the
# Robotics-Prop Isaac-composition migration replaced the live sample under
# sample_content/ with the composed form. The transformer test must consume a
# neutral multiphysics prop, so it owns its own fixture rather than depending on
# the mutable (now migrated) sample.
TOOLBOX = (
    Path(__file__).parent / "fixtures/prop_physx_toolbox" / "simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd"
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
        "PhysX": "Disabled",
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
        "PhysX": ("physx", "instances_physx.usda"),
        "Newton": ("newton", "instances_newton.usda"),
        "MuJoCo": ("mujoco", "instances_mujoco.usda"),
    }
    for runtime, (stem, instances_layer) in runtime_instance_layers.items():
        runtime_payload = package / f"runnables/physics/{stem}.usd"
        assert runtime_payload.is_file()
        assert not (package / f"payloads/{runtime}").exists()
        assert (package / f"payloads/{instances_layer}").is_file()
        variant_set = root.variantSets[runtime]
        assert not variant_set.variants["Disabled"].primSpec.hasPayloads
        enabled_payloads = variant_set.variants["Enabled"].primSpec.payloadList.prependedItems
        assert len(enabled_payloads) == 1
        assert enabled_payloads[0].assetPath == f"./runnables/physics/{stem}.usd"
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

    enabled_layer = Sdf.Layer.FindOrOpen(str(package / "runnables/physics/physx.usd"))
    box_wrapper = enabled_layer.GetPrimAtPath("/RootNode/Geometry/box_obj_01/box_mesh_01")
    references = box_wrapper.referenceList.GetAddedOrExplicitItems()
    assert len(references) == 1
    assert references[0].assetPath == "../../payloads/instances_physx.usda"
    assert not box_wrapper.attributes


def test_toolbox_prop_transform_bundles_builtin_mdl_relative_with_import_closure(tmp_path: Path) -> None:
    """A bundled built-in-named MDL (OmniPBR) must be emitted as a ``./``-relative
    ``info:mdl:sourceAsset`` that resolves to an existing file (VM.MDL.001), with
    its sibling MDL import modules co-located next to it so the module compiles
    (VM.BIND.002).

    This is a regression guard: a naive routing either rewrote the reference to a
    bare Kit identifier (fails VM.MDL.001's explicit-relative rule) or bundled
    only the top-level ``OmniPBR.mdl`` under the package root (missing
    ``import OmniPBR_ClearCoat::*`` / ``OmniPBRBase`` siblings, so Kit could not
    load the module). The transformer still prefers ``./`` over ``../`` so the
    module stays next to the materials layer.
    """
    package = tmp_path / "pkg"
    report = transform_package(
        str(TOOLBOX),
        package,
        profile="simready_physx_to_isaac_prop",
        interface_asset_name="toolbox.usda",
    )
    assert all(result.success for result in report.results)

    materials_layer_path = package / "payloads/materials.usda"
    assert materials_layer_path.is_file()
    materials_dir = materials_layer_path.parent
    layer = Sdf.Layer.FindOrOpen(str(materials_layer_path))

    mdl_sources: list[str] = []

    def collect(spec: Sdf.PrimSpec) -> None:
        for child in spec.nameChildren:
            attr = child.attributes.get("info:mdl:sourceAsset")
            if attr is not None and attr.default is not None:
                mdl_sources.append(attr.default.path)
            collect(child)

    materials_scope = layer.GetPrimAtPath("/Materials")
    assert materials_scope is not None
    collect(materials_scope)

    omni_sources = [path for path in mdl_sources if path.endswith("OmniPBR.mdl")]
    assert omni_sources, f"no OmniPBR.mdl sourceAsset authored; found {mdl_sources}"

    for source_path in omni_sources:
        # VM.MDL.001: explicit ./-relative, and resolvable to a real file.
        assert source_path.startswith("./"), f"MDL sourceAsset must be ./-relative, got {source_path!r}"
        resolved = (materials_dir / source_path).resolve()
        assert resolved.is_file(), f"bundled MDL does not resolve to a file: {resolved}"
        # VM.BIND.002: the whole local import closure travels co-located.
        siblings = {p.name for p in resolved.parent.glob("*.mdl")}
        assert {
            "OmniPBR.mdl",
            "OmniPBR_ClearCoat.mdl",
            "OmniPBRBase.mdl",
        } <= siblings, f"MDL import closure not co-located next to {resolved.name}; found {sorted(siblings)}"


def _make_tree_read_only(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IREAD)


def _make_tree_writable(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_retransforming_composed_read_only_prop_keeps_runtime_layers_and_thumbnail(tmp_path: Path) -> None:
    """The shipped sample is already composed: its runnables reference
    ``payloads/instances_<runtime>.usda``. Re-transforming such a package must
    rebuild those runtime instance layers instead of leaving runnables pointing
    at deleted ``payloads/<Runtime>/dependencies`` copies (AA.001), keep the
    thumbnail (SR.002), keep asset paths package-relative, and tolerate a
    read-only source.
    """
    composed = tmp_path / "composed"
    report = transform_package(
        str(TOOLBOX),
        composed,
        profile="simready_physx_to_isaac_prop",
        interface_asset_name="toolbox.usda",
    )
    assert all(result.success for result in report.results)
    assert (composed / ".thumbs/256x256/toolbox.usda.png").is_file()

    _make_tree_read_only(composed)
    try:
        package = tmp_path / "retransformed"
        report = transform_package(
            str(composed / "toolbox.usda"),
            package,
            profile="simready_physx_to_isaac_prop",
            interface_asset_name="toolbox_isaac.usda",
        )
    finally:
        _make_tree_writable(composed)
    assert [result.rule.name for result in report.results if not result.success] == []

    for stem in ("physx", "newton", "mujoco"):
        assert (package / f"payloads/instances_{stem}.usda").is_file()
        runnable = Sdf.Layer.FindOrOpen(str(package / f"runnables/physics/{stem}.usd"))
        assert set(runnable.GetCompositionAssetDependencies()) == {f"../../payloads/instances_{stem}.usda"}
    assert not any(path.name == "dependencies" for path in package.rglob("*"))
    assert (package / ".thumbs/256x256/toolbox_isaac.usda.png").is_file()
    assert all(os.access(path, os.W_OK) for path in package.rglob("*") if path.is_file())

    # Every layer the interface composes (including runnables) stays portable.
    # The upstream manager may leave its intermediate payloads/base.usd behind on
    # Windows; it is not part of the composed asset, so walk real dependencies.
    interface_path = str(package / "toolbox_isaac.usda")
    layers, _, unresolved = UsdUtils.ComputeAllDependencies(interface_path)
    assert unresolved == []
    for layer in layers:
        assert Path(layer.realPath).resolve().is_relative_to(package.resolve()), layer.realPath
        assert "Generated from Composed Stage" not in layer.documentation, layer.realPath
        for dependency in layer.GetCompositionAssetDependencies():
            assert dependency.startswith(("./", "../")), (layer.realPath, dependency)
    base_root = Sdf.Layer.FindOrOpen(str(package / "payloads/base.usda")).GetPrimAtPath("/RootNode")
    assert base_root.GetInfo("assetInfo")["identifier"].path == "../toolbox_isaac.usda"

    stage = Usd.Stage.Open(str(package / "toolbox_isaac.usda"))
    stage.SetEditTarget(stage.GetSessionLayer())
    root_prim = stage.GetDefaultPrim()
    expected_approximations = {"PhysX": "sdf", "Newton": "none", "MuJoCo": "convexHull"}
    for selected_runtime, expected_approximation in expected_approximations.items():
        for runtime in expected_approximations:
            root_prim.GetVariantSet(runtime).SetVariantSelection(
                "Enabled" if runtime == selected_runtime else "Disabled"
            )
        mesh = stage.GetPrimAtPath("/RootNode/Geometry/lock_00_obj_01/lock_00_mesh_01")
        assert mesh.IsInstanceProxy()
        assert mesh.GetAttribute("physics:approximation").Get() == expected_approximation


def test_prop_without_runtime_variants_gets_no_invented_runtime_variant(tmp_path: Path) -> None:
    """A source with no runtime variant sets must not gain a MuJoCo variant.

    The profile's RemoveSchemaRule creates payloads/MuJoCo/enabled.usda even
    when no such overlay was routed. Rewriting that stray layer used to add a
    MuJoCo variant whose payload has no default prim; isaacsim-asset-isolated
    6.2 then refuses to publish the package.
    """
    source = tmp_path / "source" / "box.usda"
    source.parent.mkdir()
    stage = Usd.Stage.CreateNew(str(source))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/Box")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Cube.Define(stage, "/Box/geo")
    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    stage.GetRootLayer().Save()

    package = tmp_path / "package"
    report = transform_package(
        str(source), package, profile="simready_physx_to_isaac_prop", interface_asset_name="box.usda"
    )

    assert [result.rule.name for result in report.results if not result.success] == []
    assert report.composition_errors == []
    assert report.output_stage_path
    interface = Sdf.Layer.FindOrOpen(str(package / "box.usda"))
    assert not interface.GetPrimAtPath("/Box").variantSets
    assert not (package / "payloads/MuJoCo").exists()
    assert not (package / "runnables").exists()

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regressions for composed inputs, read-only sources, and CLI output handling."""

import hashlib
import json
import shutil
import stat
from pathlib import Path

import pytest
from isaacsim.asset.transformer import ExecutionReport, RuleExecutionResult, RuleProfile, RuleSpec
from pxr import Sdf, Usd, UsdGeom, UsdShade, UsdUtils
from simready.asset_transformer import cli, transform_package
from simready.asset_transformer.rules.perf.runtime_instances import RuntimeInstanceRoutingRule

TOOLBOX = (
    Path(__file__).parent / "fixtures/prop_physx_toolbox/simready_usd" / "sm_obs_electricians_large_tool_box_a01_01.usd"
)


def _snapshot(root):
    return {
        str(path.relative_to(root)): (hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(path.stat().st_mode))
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("read_only", [False, True])
def test_composed_prop_preserves_dependencies_thumbnail_and_source(tmp_path, capfd, read_only):
    source = tmp_path / "source"
    first = transform_package(str(TOOLBOX), source, interface_asset_name="toolbox.usda")
    assert all(result.success for result in first.results)
    source_thumbnail = source / ".thumbs/256x256/toolbox.usda.png"
    assert source_thumbnail.read_bytes() == (TOOLBOX.parent / ".thumbs/256x256" / f"{TOOLBOX.name}.png").read_bytes()
    if read_only:
        for path in source.rglob("*"):
            path.chmod(path.stat().st_mode & ~0o222)
        source.chmod(source.stat().st_mode & ~0o222)
    before = _snapshot(source)
    capfd.readouterr()
    try:
        output = tmp_path / "output"
        second = transform_package(str(source / "toolbox.usda"), output, interface_asset_name="renamed.usda")
        assert all(result.success for result in second.results), second.to_json()
        assert "payloads/payloads" not in capfd.readouterr().err
        assert _snapshot(source) == before
        assert (output / ".thumbs/256x256/renamed.usda.png").read_bytes() == source_thumbnail.read_bytes()
        layers, assets, missing = UsdUtils.ComputeAllDependencies(str(output / "renamed.usda"))
        assert missing == []
        assert all(Path(layer.realPath).is_relative_to(output) for layer in layers)
        assert all(Path(str(asset)).is_relative_to(output) for asset in assets)
        for runtime in ("PhysX", "Newton", "MuJoCo"):
            assert (output / f"payloads/instances_{runtime.lower()}.usda").is_file()
    finally:
        # Restore only this test-owned fixture so cleanup also works on Windows.
        source.chmod(source.stat().st_mode | stat.S_IWUSR)
        for path in source.rglob("*"):
            path.chmod(path.stat().st_mode | stat.S_IWUSR)


def test_robot_runtime_metadata_matches_generated_options(tmp_path):
    source = tmp_path / "robot.usda"
    stage = Usd.Stage.CreateNew(str(source))
    root = UsdGeom.Xform.Define(stage, "/robot").GetPrim()
    stage.SetDefaultPrim(root)
    descriptors = {}
    for runtime in ("PhysX", "Newton", "MuJoCo"):
        variants = root.GetVariantSets().AddVariantSet(runtime)
        for option in ("Enabled", "Disabled"):
            variants.AddVariant(option)
        variants.SetVariantSelection("Disabled")
        descriptors[runtime] = {"prim": "/robot", "variantSetName": runtime, "activateOption": "Enabled"}
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": {"Variants": {"Physics": descriptors}}}
    stage.GetRootLayer().Save()
    report = transform_package(str(source), tmp_path / "output", profile="simready_physx_to_isaac_robot")
    assert all(result.success for result in report.results), report.to_json()
    transformed = Usd.Stage.Open(report.output_stage_path)
    descriptors = transformed.GetRootLayer().customLayerData["SimReady_Metadata"]["Variants"]["Physics"]
    for descriptor in descriptors.values():
        prim = transformed.GetPrimAtPath(descriptor["prim"])
        variants = prim.GetVariantSet(descriptor["variantSetName"])
        assert descriptor["activateOption"] in variants.GetVariantNames()
        assert set(variants.GetVariantNames()) == {"Enabled", "Disabled"}
        assert variants.GetVariantSelection() == "Disabled"
        spec = transformed.GetRootLayer().GetPrimAtPath(prim.GetPath())
        enabled = spec.variantSets[descriptor["variantSetName"]].variants["Enabled"]
        expected = f"./runnables/physics/{descriptor['variantSetName'].lower()}.usd"
        assert [payload.assetPath for payload in enabled.primSpec.payloadList.prependedItems] == [expected]
        assert Sdf.Layer.FindOrOpen(str(Path(report.package_root) / expected))


def test_cli_refuses_existing_output_without_traceback_or_changes(tmp_path, caplog):
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("existing package")
    before = _snapshot(output)
    assert cli.main([str(TOOLBOX), str(output)]) == 2
    stderr = caplog.text
    assert "--overwrite" in stderr
    assert "Traceback" not in stderr
    assert _snapshot(output) == before


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure_kind", ["rule", "composition"])
def test_cli_does_not_publish_failed_transform(tmp_path, monkeypatch, existing, failure_kind):
    output = tmp_path / "output"
    if existing:
        output.mkdir()
        (output / "keep.txt").write_text("existing package")
    before = _snapshot(output)

    def failing_transform(input_stage, package_root, **kwargs):
        package_root.mkdir(parents=True)
        (package_root / "partial.usda").write_text("partial output")
        rule = RuleSpec(name="Route Variants", type="failure")
        report = ExecutionReport(
            profile=RuleProfile(profile_name="Failing"), input_stage_path=input_stage, package_root=str(package_root)
        )
        if failure_kind == "rule":
            report.results.append(RuleExecutionResult(rule=rule, success=False, error="cannot write layer"))
        else:
            report.composition_errors.append("Unresolved reference to missing.usda")
        return report

    monkeypatch.setattr(cli, "transform_package", failing_transform)
    args = [str(TOOLBOX), str(output)] + (["--overwrite"] if existing else [])
    assert cli.main(args) == 1
    assert output.exists() is existing
    assert _snapshot(output) == before
    report = json.loads((tmp_path / "output.failed-transform.json").read_text())
    if failure_kind == "rule":
        assert report["results"][0]["error"] == "cannot write layer"
    else:
        assert report["composition_errors"] == ["Unresolved reference to missing.usda"]
    assert not list(tmp_path.glob(".output-*"))


@pytest.mark.parametrize("overwrite", [False, True])
def test_cli_success_report_points_to_published_package(tmp_path, overwrite):
    output = tmp_path / "output"
    if overwrite:
        output.mkdir()
        (output / "old.txt").write_text("old package")
    args = [str(TOOLBOX), str(output), "--interface-name", "renamed.usda"]
    assert cli.main(args + (["--overwrite"] if overwrite else [])) == 0
    assert not (output / "old.txt").exists()
    report = json.loads((output / "transform_report.json").read_text())
    assert report["package_root"] == str(output)
    assert report["output_stage_path"] == str(output / "renamed.usda")
    assert (output / ".thumbs/256x256/renamed.usda.png").is_file()
    layers, _, missing = UsdUtils.ComputeAllDependencies(report["output_stage_path"])
    assert missing == []
    assert all(Path(layer.realPath).is_relative_to(output) for layer in layers)
    assert not list(tmp_path.glob(".output-*"))


def test_cli_restores_existing_package_if_promotion_fails(tmp_path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("existing package")
    before = _snapshot(output)
    original_rename = Path.rename

    def fail_promotion(path, destination):
        if path.name == "package" and path.parent.name.startswith(".output-"):
            raise OSError("Cannot publish package")
        return original_rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_promotion)
    assert cli.main([str(TOOLBOX), str(output), "--overwrite"]) == 1
    assert _snapshot(output) == before
    assert not list(tmp_path.glob(".output-*"))


@pytest.mark.parametrize("read_only", [False, True])
def test_documented_shipped_toolbox_demo(tmp_path, read_only):
    # Exercise the actual README input. Re-transforming the pristine fixture's
    # output does not reproduce its mixture of parent and mesh-level references.
    repository = Path(__file__).resolve().parents[6]
    shipped = repository / "sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd"
    assert shipped.is_dir(), "The documented toolbox sample must be available"
    source = tmp_path / "source"
    shutil.copytree(shipped, source)
    input_stage = source / "sm_obs_electricians_large_tool_box_a01_01.usd"
    output = tmp_path / "output"
    if read_only:
        for path in source.rglob("*"):
            path.chmod(path.stat().st_mode & ~0o222)
        source.chmod(source.stat().st_mode & ~0o222)
    before = _snapshot(source)
    directory_modes = {path: path.stat().st_mode for path in [source, *source.rglob("*")] if path.is_dir()}
    try:
        assert cli.main([str(input_stage), str(output), "--interface-name", "toolbox.usda"]) == 0
        assert _snapshot(source) == before
        assert all(path.stat().st_mode == mode for path, mode in directory_modes.items())
        report = json.loads((output / "transform_report.json").read_text())
        assert report["composition_errors"] == []
        assert all(result["success"] for result in report["results"])
        for thumbnail in (source / ".thumbs/256x256").glob(input_stage.name + "*.png"):
            renamed = "toolbox.usda" + thumbnail.name[len(input_stage.name) :]
            assert (output / ".thumbs/256x256" / renamed).read_bytes() == thumbnail.read_bytes()
        layers, assets, missing = UsdUtils.ComputeAllDependencies(str(output / "toolbox.usda"))
        assert missing == []
        assert all(Path(layer.realPath).is_relative_to(output) for layer in layers)
        assert all(Path(str(asset)).is_relative_to(output) for asset in assets)
        stage = Usd.Stage.Open(str(output / "toolbox.usda"))
        stage.SetEditTarget(stage.GetSessionLayer())
        root = stage.GetDefaultPrim()
        expected = {"PhysX": "sdf", "Newton": "convexHull", "MuJoCo": "convexHull"}
        for runtime, approximation in expected.items():
            for name in expected:
                root.GetVariantSet(name).SetVariantSelection("Enabled" if name == runtime else "Disabled")
            assert not stage.GetCompositionErrors()
            for part in ("handle", "lid", "lock_00", "lock_01"):
                parent = stage.GetPrimAtPath(f"/RootNode/Geometry/{part}_obj_01")
                assert not parent.HasAuthoredReferences(), parent.GetPath()
                assert parent.GetMetadata("references") is None
                assert not parent.IsInstance()
                wrapper = stage.GetPrimAtPath(parent.GetPath().AppendChild(f"{part}_mesh_01"))
                assert wrapper.IsInstance()
                references = wrapper.GetMetadata("references").GetAppliedItems()
                assert [ref.assetPath for ref in references] == [f"../../payloads/instances_{runtime.lower()}.usda"]
            meshes = [
                prim for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()) if prim.IsA(UsdGeom.Mesh)
            ]
            assert len(meshes) == 5
            for mesh in meshes:
                assert mesh.IsInstanceProxy(), mesh.GetPath()
                assert mesh.GetAttribute("physics:approximation").Get() == approximation, mesh.GetPath()
                material, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial("physics")
                assert material, mesh.GetPath()
            payload = output / f"runnables/physics/{runtime.lower()}.usd"
            layer = Sdf.Layer.FindOrOpen(str(payload))
            assert set(layer.GetCompositionAssetDependencies()) == {f"../../payloads/instances_{runtime.lower()}.usda"}
    finally:
        source.chmod(source.stat().st_mode | stat.S_IWUSR)
        for path in source.rglob("*"):
            path.chmod(path.stat().st_mode | stat.S_IWUSR)


@pytest.mark.parametrize("unmapped", [False, True])
def test_parent_runtime_reference_maps_each_mesh_before_removal(tmp_path, unmapped):
    stage = Usd.Stage.CreateInMemory()
    parent = Sdf.CreatePrimInLayer(stage.GetRootLayer(), "/Root/Object")
    parent.referenceList.explicitItems = [Sdf.Reference("./old.usda", "/Prototype")]
    parent.instanceable = True
    Sdf.AttributeSpec(parent, "physics:mass", Sdf.ValueTypeNames.Float).default = 12.0
    Sdf.CreatePrimInLayer(stage.GetRootLayer(), "/Root/Object/Keep")
    external = Sdf.Layer.CreateAnonymous()
    destination = Sdf.Layer.CreateAnonymous()
    mapping = {}
    for name, approximation in [("left", "sdf"), ("right", "convexHull")]:
        spec = Sdf.CreatePrimInLayer(external, "/Prototype/" + name)
        Sdf.AttributeSpec(spec, "physics:approximation", Sdf.ValueTypeNames.Token).default = approximation
        root = Sdf.Path("/Instances/" + name)
        Sdf.CreatePrimInLayer(destination, root.AppendChild(name))
        mapping[Sdf.Path("/Root/Object/" + name)] = root
    if unmapped:
        del mapping[Sdf.Path("/Root/Object/right")]
    before = stage.GetRootLayer().ExportToString(), destination.ExportToString()
    rule = RuntimeInstanceRoutingRule(stage, str(tmp_path), "", {})
    if unmapped:
        with pytest.raises(RuntimeError, match="Cannot route runtime opinion"):
            rule._route_parent_runtime_reference(parent, external, Sdf.Path("/Prototype"), destination, mapping)
        assert (stage.GetRootLayer().ExportToString(), destination.ExportToString()) == before
    else:
        relocations = rule._route_parent_runtime_reference(
            parent, external, Sdf.Path("/Prototype"), destination, mapping
        )
        assert {root for _, root, _ in relocations} == set(mapping)
        assert not parent.referenceList.GetAddedOrExplicitItems()
        assert not parent.HasInfo("references")
        assert not parent.HasInfo("instanceable")
        assert parent.attributes["physics:mass"].default == 12.0
        assert stage.GetRootLayer().GetPrimAtPath("/Root/Object/Keep")
        for name, approximation in [("left", "sdf"), ("right", "convexHull")]:
            spec = destination.GetPrimAtPath(f"/Instances/{name}/{name}")
            assert spec.attributes["physics:approximation"].default == approximation

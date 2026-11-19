# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shipped-content regressions for OMPE-119316, OMPE-119318 and OMPE-119288."""
from pathlib import Path
import json
import re

import pytest

pytest.importorskip("pxr")
from pxr import Sdf, Usd, UsdPhysics

REPO = Path(__file__).resolve().parents[4]
SAMPLES = REPO / "sample_content"
PACKAGES = SAMPLES / "packaging/simple_packages"


@pytest.mark.parametrize("relative,link_count,joint_count", [
    ("ur10/simready_usd/ur10.usd", 7, 7),
    ("Robotiq/2F-85/simready_usd/2F-85.usda", 9, 9),
])
@pytest.mark.parametrize("physx", ["Disabled", "Enabled"])
def test_robot_discovery_covers_real_topology(relative, link_count, joint_count, physx):
    robot_schema = pytest.importorskip("usd.schema.isaac.robot_schema")
    pytest.importorskip("physx_usd_schemas")
    stage = Usd.Stage.Open(str(SAMPLES / "common_assets/robots_general" / relative))
    root = stage.GetDefaultPrim()
    schema_layer = Sdf.Layer.FindOrOpen(str(Path(stage.GetRootLayer().realPath).parent / "payloads/robot.usda"))
    assert schema_layer is not None
    assert all(not prim.variantSets for prim in schema_layer.rootPrims)
    assert "Physics" not in schema_layer.ExportToString()
    stage.SetEditTarget(stage.GetSessionLayer())
    root.GetVariantSet("PhysX").SetVariantSelection(physx)
    assert root.HasAPI(robot_schema.Classes.ROBOT_API.value)
    assert root.GetAttribute("isaac:robotType").Get() in {"Manipulator", "End Effector"}
    for relation, schema, expected, predicate in [
        ("isaac:physics:robotLinks", robot_schema.Classes.LINK_API.value,
         link_count, lambda p: p.HasAPI(UsdPhysics.RigidBodyAPI)),
        ("isaac:physics:robotJoints", robot_schema.Classes.JOINT_API.value,
         joint_count, lambda p: p.IsA(UsdPhysics.Joint)),
    ]:
        relationship = root.GetRelationship(relation)
        targets = relationship.GetTargets()
        assert len(targets) == expected
        assert set(targets) == {p.GetPath() for p in stage.Traverse() if predicate(p)}
        assert all(stage.GetPrimAtPath(p).HasAPI(schema) for p in targets)
        assert all(not spec.targetPathList.isExplicit for spec in relationship.GetPropertyStack())
    joints = root.GetRelationship("isaac:physics:robotJoints").GetTargets()
    anchor = UsdPhysics.FixedJoint(stage.GetPrimAtPath(joints[0]))
    assert anchor, "the first discoverable joint must remain the world anchor"
    assert not anchor.GetBody0Rel().GetTargets() or not anchor.GetBody1Rel().GetTargets()


def test_package_asset_paths_resolve_with_exact_case_on_every_platform():
    roots = sorted(PACKAGES.rglob("*.usd"))
    assert len(roots) == 5
    for path in roots:
        layer = Sdf.Layer.FindOrOpen(str(path))
        assert layer is not None
        for authored in re.findall(r"@([^@]+)@", layer.ExportToString()):
            if Path(authored).suffix.lower() not in {".png", ".jpg", ".exr", ".mdl"}:
                continue
            candidate = Path(authored)
            assert not candidate.is_absolute(), (path, authored)
            current = path.parent
            for component in candidate.parts:
                if component == "..":
                    current = current.parent
                    continue
                assert component in {p.name for p in current.iterdir()}, (path, authored, component)
                current /= component
            assert current.is_file(), (path, authored)


def test_regenerated_package_boms_and_hashes_match_content():
    standard = pytest.importorskip("simready.package.standard")
    definitions = sorted(PACKAGES.glob("*/com.nvidia.simready.packaging.json"))
    assert len(definitions) == 5
    for definition in definitions:
        data = json.loads(definition.read_text(encoding="utf-8"))
        if definition.parent.name == "apple_a01_nobom":
            assert "metadata" not in data and "content_hash" not in data
        else:
            assert not standard.verify_package_dir(definition.parent)
    multi = json.loads((PACKAGES / "apple_a01_usd_bom_multi_hash/com.nvidia.simready.packaging.json").read_text())
    assert set(multi["content_hash"]) == {"sha256", "blake3"}


def test_all_sample_layers_have_no_retired_receipts():
    layers = [p for p in SAMPLES.rglob("*") if p.suffix.lower() in {".usd", ".usda", ".usdc"}]
    assert len(layers) >= 281, "audit includes binary USD and historical folders"
    for path in layers:
        layer = Sdf.Layer.FindOrOpen(str(path))
        assert layer is not None, path
        receipt = layer.customLayerData.get("SimReady_Metadata", {}).get("validation", {})
        assert "FET_" not in str(receipt), path
        assert "Prop-Robotics" not in str(receipt), path
        if "simready_physx_usd" in path.parts and "obs_workbench_tool_a01" in path.parts:
            assert not receipt, path


def test_historical_workbench_sidecar_has_no_retired_profile_claim():
    sidecar = SAMPLES / "common_assets/props_general/obs_workbench_tool_a01/simready_physx_usd/sm_obs_workbench_tool_a01_01.json"
    data = json.loads(sidecar.read_text())
    assert "profile" not in data and "profile_version" not in data
    assert "validation" not in data["SimReady_Metadata"]
    assert data["asset_name"] == "obs_workbench_tool_a01"

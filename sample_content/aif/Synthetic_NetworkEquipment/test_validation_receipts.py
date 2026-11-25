# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Real static receipt and discovery checks on staged copies; no live runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest
from pxr import Sdf, Usd

HERE = Path(__file__).resolve().parent


@pytest.fixture
def staged_validator(tmp_path):
    target = tmp_path / "network-equipment"
    shutil.copytree(HERE, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    asset = target / "asset/Synthetic_NetworkEquipment.usda"
    stage = Usd.Stage.Open(str(asset))
    stage.ClearMetadataByDictKey("customLayerData", "SimReady_Metadata:validation")
    stage.GetRootLayer().Save()
    spec = importlib.util.spec_from_file_location("staged_network_validator", HERE / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE, module.ASSET = target, asset
    return module


def assert_report_hashes_current(sample_dir, reports):
    expected = {
        str(path.relative_to(sample_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((sample_dir / "asset").rglob("*")) if path.is_file()
    }
    for report in reports.values():
        assert report["passed"]
        assert report["asset_file_sha256"] == expected


def test_published_receipts_and_hashes_match_shipped_asset():
    entry = HERE / "asset/Synthetic_NetworkEquipment.usda"
    metadata = Sdf.Layer.OpenAsAnonymous(str(entry)).customLayerData["SimReady_Metadata"]
    targets = metadata["validation"]["profiles"]
    assert set(targets) == {"AIF-Entity@0.3.0", "Networking@0.3.0"}
    assert "runtime_testing" not in metadata
    reports = {}
    for filename in ("validation.json", "validation-networking.json"):
        report = json.loads((HERE / filename).read_text())
        profile = report["profile"]
        key = f"{profile['name']}@{profile['version']}"
        recorded = targets[key]["validated_features"]
        assert report["contracts"] == recorded[max(recorded)]
        assert report["executed_requirements"] == report["selected_requirements"] > 0
        assert not report["issues"]
        reports[key] = report
    assert set(reports) == set(targets)
    assert_report_hashes_current(HERE, reports)


def test_single_profile_validation_preserves_unstamped_interface(staged_validator):
    module = staged_validator
    original = module.ASSET.read_bytes()
    report = module.validate(module.HERE / "validation.json")
    assert report["profile"] == {"name": "AIF-Entity", "version": "0.3.0"}
    assert report["passed"]
    assert module.ASSET.read_bytes() == original


def test_stamp_records_both_static_profiles_then_hashes_final_files(staged_validator):
    module = staged_validator
    reports = module.stamp_profiles()
    assert "float mass =" in module.ASSET.read_text()
    assert_report_hashes_current(module.HERE, reports)
    metadata = Sdf.Layer.OpenAsAnonymous(str(module.ASSET)).customLayerData["SimReady_Metadata"]
    assert set(metadata["validation"]["profiles"]) == {"AIF-Entity@0.3.0", "Networking@0.3.0"}
    assert "runtime_testing" not in metadata
    for name, filename in (("AIF-Entity", "validation.json"), ("Networking", "validation-networking.json")):
        assert json.loads((module.HERE / filename).read_text()) == reports[name]
    # A rerun preserves both independent targets and refreshes final-file hashes.
    repeated = module.stamp_profiles()
    assert_report_hashes_current(module.HERE, repeated)
    metadata = Sdf.Layer.OpenAsAnonymous(str(module.ASSET)).customLayerData["SimReady_Metadata"]
    assert set(metadata["validation"]["profiles"]) == {"AIF-Entity@0.3.0", "Networking@0.3.0"}


def test_failed_preflight_does_not_stamp_interface(staged_validator):
    module = staged_validator
    properties = module.HERE / "asset/layers/Synthetic_NetworkEquipment_Properties.usda"
    layer = Sdf.Layer.FindOrOpen(str(properties))
    layer.GetAttributeAtPath(Sdf.Path("/" + layer.defaultPrim).AppendProperty("aif:spec:cpuAllocation")).default = 0
    layer.Save()
    before = module.ASSET.read_bytes()
    with pytest.raises(SystemExit) as failure:
        module.stamp_profiles()
    assert failure.value.code == 1
    assert module.ASSET.read_bytes() == before
    metadata = Sdf.Layer.OpenAsAnonymous(str(module.ASSET)).customLayerData["SimReady_Metadata"]
    assert "validation" not in metadata


def test_root_metadata_discovers_only_the_equipment_interface(staged_validator):
    pytest.importorskip("simready.evaluate")
    from simready.evaluate.core.asset_discovery import FilesystemWalkDiscovery

    module = staged_validator
    assert FilesystemWalkDiscovery(str(module.HERE)).discover() == [str(module.ASSET)]
    assert FilesystemWalkDiscovery(str(module.HERE / "asset")).discover() == [str(module.ASSET)]

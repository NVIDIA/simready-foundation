# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Dedicated Networking profile eligibility and standalone switch coverage."""
from pathlib import Path
import shutil

import pytest
from pxr import Sdf, Usd
from usd_validation_nvidia import ProfileRegistry

from _harness import assert_rule_fires


@pytest.fixture(scope="module")
def validator():
    import simready.validate as sv

    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield sv
    sv.destroy()


@pytest.fixture
def standalone_switch(tmp_path):
    source = Path(__file__).resolve().parents[4] / "sample_content/aif/Synthetic_NetworkEquipment/asset"
    staged = tmp_path / "Switch"
    shutil.copytree(source, staged)
    return staged / "Synthetic_NetworkEquipment.usda"


def _result(validator, path, profile="Networking", version="0.3.0"):
    result = validator.validate_asset(validator.AssetValidationConfig(
        asset_path=str(path), profile_id=profile, profile_version=version,
    ))
    assert result is not None and result.features_summary
    return result


def test_standalone_switch_passes_networking_profile(validator, standalone_switch):
    result = _result(validator, standalone_switch)
    assert validator.features_summary_passed(result.features_summary), result.features_summary
    assert "FET207_SimulationNetworkTopology.0-3-0" in result.features_summary
    assert not result.issues


def test_relocated_switch_passes_package_candidate(validator, standalone_switch):
    result = _result(validator, standalone_switch, "Package-Candidate", "1.3.0")
    assert validator.features_summary_passed(result.features_summary), result.features_summary
    assert not result.issues


@pytest.mark.parametrize("layer", ["properties", "root", "both"])
def test_other_equipment_class_fails_dedicated_profile(validator, standalone_switch, layer):
    stage = Usd.Stage.Open(str(standalone_switch))
    props = Sdf.Layer.FindOrOpen(str(standalone_switch.parent / "layers/Synthetic_NetworkEquipment_Properties.usda"))
    if layer in ("properties", "both"):
        with Usd.EditContext(stage, props):
            stage.GetDefaultPrim().GetAttribute("aif:core:assetClass").Set("compute-rack")
        props.Save()
    if layer in ("root", "both"):
        stage.GetDefaultPrim().GetAttribute("aif:core:assetClass").Set("compute-rack")
        stage.GetRootLayer().Save()
    result = _result(validator, standalone_switch)
    assert not validator.features_summary_passed(result.features_summary)
    failures = result.features_summary["FET207_SimulationNetworkTopology.0-3-0"].get("failing requirements", [])
    assert "com.nvidia.simready.NET.004" in failures
    assert_rule_fires(standalone_switch, "NET.004")


def test_eligibility_is_not_selected_by_aif_entity(validator):
    for version in ("0.1.0", "0.2.0", "0.3.0"):
        profile = ProfileRegistry().find("AIF-Entity", version)
        assert "com.nvidia.simready.NET.004" not in profile.mandatory_requirements
        assert all(not contract.id.startswith("FET207_") for contract in profile.capabilities)


def test_networking_profile_has_only_exact_aif03_network_contracts(validator):
    profile = ProfileRegistry().find("Networking", "0.3.0")
    assert profile is not None and not profile.optional_capabilities
    ids = {contract.id for contract in profile.capabilities}
    assert "FET207_SimulationNetworkTopology.0-3-0" in ids
    assert {"CAP200_AifMetadata.0-3-0", "CAP201_ConnectionPoints.0-3-0",
            "CAP204_Networking.0-3-0"} <= ids
    assert not any(identity.startswith(("CAP202_", "CAP203_")) for identity in ids)
    assert "com.nvidia.simready.NET.004" in profile.mandatory_requirements
    families = [identity.rsplit(".", 1)[0] for identity in ids]
    assert len(families) == len(set(families))

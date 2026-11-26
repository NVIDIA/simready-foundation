# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Full-profile evidence for the versioned chiller and its physical sample."""
from pathlib import Path
import shutil

import pytest
from pxr import Usd
from usd_validation_nvidia import IssueSeverity, ProfileRegistry

from _harness import assert_rule_does_not_report, assert_rule_fires


SAMPLE = Path(__file__).resolve().parents[4] / "sample_content/aif/Synthetic_LiquidCooledChiller"


@pytest.fixture(scope="module")
def validator():
    import simready.validate as sv

    sv.destroy()
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield sv
    sv.destroy()
    # Later rule-level modules use conftest's shared registry. Restore its
    # registered implementations after clearing this module's profile state.
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])


CHILLER_PROFILE = "Liquid-Cooled-Chiller"
CHILLER_CAPABILITY = "CAP206_LiquidCooledChiller.0-3-0"
CHILLER_REQUIREMENTS = {"com.nvidia.simready." + code for code in ("AM.011", "TC.004", "EL.006")}


def validate_profile(validator, asset, profile):
    result = validator.validate_asset(validator.AssetValidationConfig(
        asset_path=str(asset), profile_id=profile, profile_version="0.3.0",
    ))
    assert result is not None and result.features_summary
    assert not [issue for issue in result.issues if issue.severity is IssueSeverity.ERROR]
    return result


def test_chiller_requirement_ownership(validator):
    registry = ProfileRegistry()
    chiller = registry.find(CHILLER_PROFILE, "0.3.0")
    capabilities = {contract.id: contract for contract in chiller.capabilities}
    assert {r.code for r in capabilities[CHILLER_CAPABILITY].requirements} == CHILLER_REQUIREMENTS
    assert CHILLER_REQUIREMENTS <= chiller.mandatory_requirements
    assert "CAP204_Networking.0-3-0" not in capabilities
    assert not any(".NET." in code for code in chiller.mandatory_requirements)
    general = registry.find("AIF-Entity", "0.3.0")
    assert CHILLER_CAPABILITY not in {contract.id for contract in general.capabilities}
    assert CHILLER_REQUIREMENTS.isdisjoint(general.mandatory_requirements)


@pytest.mark.parametrize("profile", ["AIF-Entity", CHILLER_PROFILE])
def test_complete_chiller_passes_full_profile_after_relocation(tmp_path, validator, profile):
    asset = shutil.copytree(SAMPLE / "asset", tmp_path / "chiller") / "Synthetic_LiquidCooledChiller.usda"
    result = validate_profile(validator, asset, profile)
    assert validator.features_summary_passed(result.features_summary), result.features_summary
    for severity in ("INFO", "WARNING"):
        assert_rule_does_not_report(asset, "CP.012", severity)


@pytest.mark.parametrize("sample, systems", [
    ("Generic_CDU", {"FWS", "TCS"}),
    ("Synthetic_CRAH", {"FWS"}),
])
def test_other_thermal_equipment_uses_its_own_interfaces(tmp_path, validator, sample, systems):
    folder = shutil.copytree(SAMPLE.parent / sample / "asset", tmp_path / sample)
    asset = folder / f"{sample}.usda"
    properties = Usd.Stage.Open(str(folder / "layers" / f"{sample}_Properties.usda"))
    root = properties.GetDefaultPrim()
    assert root.RemoveProperty("aif:core:overallGeometryDimensions")  # Upgrade the staged sample to AIF 0.3.
    assert not root.HasAttribute("aif:spec:performanceModelType")
    properties.GetRootLayer().Save()

    stage = Usd.Stage.Open(str(asset))
    ports = stage.GetDefaultPrim().GetChild("ConnectionPoints").GetChildren()
    thermal_ports = {
        (p.GetAttribute("simready:connectionPoint:system").Get(),
         p.GetAttribute("simready:connectionPoint:direction").Get()): p
        for p in ports if p.GetAttribute("simready:connectionPoint:domain").Get() == "thermal"
    }
    assert set(thermal_ports) == {(system, direction) for system in systems for direction in ("supply", "return")}
    general = validate_profile(validator, asset, "AIF-Entity")
    assert validator.features_summary_passed(general.features_summary), general.features_summary
    specific = validate_profile(validator, asset, CHILLER_PROFILE)
    assert "com.nvidia.simready.AM.011" in specific.features_summary[CHILLER_CAPABILITY]["failing requirements"]

    # Losing either class's return connection must still fail its own thermal rule.
    system = "TCS" if sample == "Generic_CDU" else "FWS"
    thermal_ports[(system, "return")].SetActive(False)
    stage.GetRootLayer().Save()
    assert_rule_fires(asset, "TC.002")


@pytest.mark.parametrize("layer, prim, attribute, invalid, code", [
    ("Properties", "/world", "aif:spec:performanceMapCoolingLookupAuxiliaryHeat_W", [0], "AM.011"),
    ("ConnectionPoints", "/world/ConnectionPoints/EvaporatorSupply",
     "simready:connectionPoint:thermal:designFlowRate", 0.1, "TC.004"),
    ("ConnectionPoints", "/world/ConnectionPoints/ElectricalInlet",
     "simready:connectionPoint:electrical:nominalVoltage", 230, "EL.006"),
])
def test_dedicated_profile_rejects_invalid_chiller(tmp_path, validator, layer, prim, attribute, invalid, code):
    folder = shutil.copytree(SAMPLE / "asset", tmp_path / "chiller")
    stage = Usd.Stage.Open(str(folder / "layers" / f"Synthetic_LiquidCooledChiller_{layer}.usda"))
    assert stage.GetPrimAtPath(prim).GetAttribute(attribute).Set(invalid)
    stage.GetRootLayer().Save()
    result = validate_profile(validator, folder / "Synthetic_LiquidCooledChiller.usda", CHILLER_PROFILE)
    assert not validator.features_summary_passed(result.features_summary)
    assert f"com.nvidia.simready.{code}" in result.features_summary[CHILLER_CAPABILITY]["failing requirements"]


@pytest.mark.parametrize("composed_only", [True, False])
def test_liquid_profile_rejects_air_chiller_class(tmp_path, validator, composed_only):
    folder = shutil.copytree(SAMPLE / "asset", tmp_path / "chiller")
    asset = folder / "Synthetic_LiquidCooledChiller.usda"
    path = asset if composed_only else folder / "layers/Synthetic_LiquidCooledChiller_Properties.usda"
    stage = Usd.Stage.Open(str(path))
    assert stage.GetDefaultPrim().GetAttribute("aif:core:assetClass").Set("AirCooledChiller")
    stage.GetRootLayer().Save()
    result = validate_profile(validator, asset, CHILLER_PROFILE)
    assert not validator.features_summary_passed(result.features_summary)
    assert "com.nvidia.simready.AM.011" in result.features_summary[CHILLER_CAPABILITY]["failing requirements"]


@pytest.mark.parametrize("version", ["0.1.0", "0.2.0"])
def test_chiller_is_not_silently_registered_under_old_profiles(tmp_path, validator, version):
    staged = tmp_path / "chiller"
    shutil.copytree(SAMPLE / "asset", staged)
    result = validator.validate_asset(validator.AssetValidationConfig(
        asset_path=str(staged / "Synthetic_LiquidCooledChiller.usda"),
        profile_id="AIF-Entity", profile_version=version,
    ))
    assert result is not None
    assert not validator.features_summary_passed(result.features_summary)
    assert any(
        issue.severity is IssueSeverity.FAILURE
        and issue.requirement is not None
        and str(issue.requirement.code).endswith(".AM.007")
        for issue in result.issues
    )
    assert not [issue for issue in result.issues if issue.severity is IssueSeverity.ERROR]

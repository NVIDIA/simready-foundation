# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for AIF connection identification and clearance validation."""
import pytest
from pxr import Sdf, Usd, UsdGeom

from _harness import assert_no_failures, assert_rule_fires, assert_rule_reports


def make_asset(tmp_path, asset_class="cdu", version="0.2.0", ports=(), clearance=0.3,
               alias=False, disconnect="flanged"):
    """Compose real Properties and ConnectionPoints layers, with arbitrary port names."""
    properties = Usd.Stage.CreateNew(str(tmp_path / "asset_Properties.usda"))
    root = UsdGeom.Xform.Define(properties, "/Asset").GetPrim()
    properties.SetDefaultPrim(root)
    root.CreateAttribute("aif:core:assetClass", Sdf.ValueTypeNames.String).Set(asset_class)
    if version is not None:
        root.CreateAttribute("aif:core:simreadyVersion", Sdf.ValueTypeNames.String).Set(version)
    properties.GetRootLayer().Save()
    connections = Usd.Stage.CreateNew(str(tmp_path / "asset_ConnectionPoints.usda"))
    UsdGeom.Xform.Define(connections, "/Asset")
    UsdGeom.Scope.Define(connections, "/Asset/ConnectionPoints")
    for name, domain, system, direction in ports:
        prim = UsdGeom.Xform.Define(connections, f"/Asset/ConnectionPoints/{name}").GetPrim()
        UsdGeom.Imageable(prim).CreatePurposeAttr("guide")
        for suffix, value in {
            "type" if alias else "domain": domain,
            "system": system, "direction": direction, "disconnectType": disconnect,
        }.items():
            if value is not None:
                prim.CreateAttribute(f"simready:connectionPoint:{suffix}", Sdf.ValueTypeNames.Token).Set(value)
        prim.CreateAttribute("simready:connectionPoint:serviceClearance", Sdf.ValueTypeNames.Float).Set(clearance)
    connections.GetRootLayer().Save()
    path = tmp_path / "asset.usda"
    stage = Usd.Stage.CreateNew(str(path))
    stage.GetRootLayer().subLayerPaths = ["./asset_Properties.usda", "./asset_ConnectionPoints.usda"]
    stage.SetDefaultPrim(stage.GetPrimAtPath("/Asset"))
    stage.GetRootLayer().Save()
    return path


CDU = [(f"Port{i}", "thermal", system, direction)
       for i, (system, direction) in enumerate([
           ("FWS", "supply"), ("FWS", "return"), ("TCS", "supply"), ("TCS", "return")])]
CRAH = [("PortA", "thermal", "LIQ", "supply"), ("PortB", "thermal", "LIQ", "return")]
ELECTRICAL = [("PortE", "electrical", "power", "input")]
CASES = [("cdu", "TC.002", CDU), ("crah", "TC.002", CRAH)] + [
    (cls, "EL.004", ELECTRICAL) for cls in ("cdu", "crah", "ups")]


@pytest.mark.parametrize("asset_class,code,ports", CASES)
@pytest.mark.parametrize("alias", [False, True])
def test_property_identified_ports(tmp_path, asset_class, code, ports, alias):
    path = make_asset(tmp_path, asset_class, ports=ports, alias=alias)
    assert_no_failures(path, [code, "CP.010", "CP.011"])


@pytest.mark.parametrize("asset_class,code,ports,missing", [
    (cls, code, ports, i) for cls, code, ports in CASES for i in range(len(ports))])
def test_each_required_port_is_required(tmp_path, asset_class, code, ports, missing):
    path = make_asset(tmp_path, asset_class, ports=ports[:missing] + ports[missing + 1:])
    assert_rule_fires(path, code)


@pytest.mark.parametrize("asset_class,code,ports", CASES)
@pytest.mark.parametrize("version", ["0.1.0", None])
def test_legacy_names_still_work(tmp_path, asset_class, code, ports, version):
    named = [(f"acme_{system.lower()}_{direction}_main" if code == "TC.002"
              else "acme_electrical_nominal_voltage_main", None, None, None)
             for _, _, system, direction in ports]
    path = make_asset(tmp_path, asset_class, version=version, ports=named)
    assert_no_failures(path, [code])


@pytest.mark.parametrize("asset_class,code,ports", CASES)
def test_legacy_version_does_not_accept_arbitrary_names(tmp_path, asset_class, code, ports):
    path = make_asset(tmp_path, asset_class, version="0.1.0", ports=ports)
    assert_rule_fires(path, code)


@pytest.mark.parametrize("asset_class,code,ports", CASES)
def test_legacy_names_do_not_hide_wrong_domain(tmp_path, asset_class, code, ports):
    named = [(f"acme_{system.lower()}_{direction}_main" if code == "TC.002"
              else "acme_electrical_nominal_voltage_main", "network", system, direction)
             for _, _, system, direction in ports]
    assert_rule_fires(make_asset(tmp_path, asset_class, ports=named), code)


@pytest.mark.parametrize("field,value", [(2, "other"), (3, "input"), (3, None)])
def test_cdu_requires_matching_system_and_direction(tmp_path, field, value):
    ports = [list(port) for port in CDU]
    ports[0][field] = value
    assert_rule_fires(make_asset(tmp_path, ports=ports), "TC.002")


@pytest.mark.parametrize("system", ["LIQ", "FWS", "equipment_cooling"])
def test_crah_liquid_system_tokens_are_open(tmp_path, system):
    ports = [(name, domain, system, direction) for name, domain, _, direction in CRAH]
    assert_no_failures(make_asset(tmp_path, "crah", ports=ports), ["TC.002"])


@pytest.mark.parametrize("version", ["0.1.0", "0.2.0"])
@pytest.mark.parametrize("asset_class,codes", [("ups", ["TC.002"]), ("compute-rack", ["TC.002", "EL.004"])])
def test_class_exemptions(tmp_path, version, asset_class, codes):
    assert_no_failures(make_asset(tmp_path, asset_class, version), codes)


@pytest.mark.parametrize("clearance", [-0.5, -0.001, 0.0, 0.3])
def test_service_clearance_range(tmp_path, clearance):
    path = make_asset(tmp_path, ports=ELECTRICAL, clearance=clearance)
    if clearance < 0:
        assert_rule_fires(path, "CP.011")
    else:
        assert_no_failures(path, ["CP.011"])


@pytest.mark.parametrize("alias,disconnect,severity", [(True, "flanged", "WARNING"), (False, "custom_connector", "INFO")])
def test_advisories_remain_nonblocking(tmp_path, alias, disconnect, severity):
    path = make_asset(tmp_path, ports=ELECTRICAL, alias=alias, disconnect=disconnect)
    assert_no_failures(path, ["CP.011"])
    assert_rule_reports(path, "CP.011", severity)


@pytest.fixture(scope="module")
def public_validator():
    sv = pytest.importorskip("simready.validate")
    sv.destroy()
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield sv
    sv.destroy()


@pytest.mark.parametrize("asset_class,code,ports", CASES)
@pytest.mark.parametrize("missing", [False, True])
def test_shipped_profile_port_results(tmp_path, public_validator, asset_class, code, ports, missing):
    path = make_asset(tmp_path, asset_class, ports=ports[1:] if missing else ports)
    result = public_validator.validate_asset(public_validator.AssetValidationConfig(
        asset_path=str(path), profile_id="AIF-Entity", profile_version="0.2.0"))
    assert result is not None and result.features_summary
    feature = "FET202_AIF" if code == "TC.002" else "FET203_AIF"
    summary = result.features_summary[feature]
    assert summary["version"] == "0.2.0"
    # These minimal assets intentionally lack unrelated profile requirements.
    failed = summary.get("failing requirements", [])
    assert (f"com.nvidia.simready.{code}" in failed) is missing


@pytest.mark.parametrize("clearance", [-0.5, 0.0])
def test_shipped_profile_clearance_is_blocking(tmp_path, public_validator, clearance):
    path = make_asset(tmp_path, "compute-rack", ports=ELECTRICAL, clearance=clearance)
    result = public_validator.validate_asset(public_validator.AssetValidationConfig(
        asset_path=str(path), profile_id="AIF-Entity", profile_version="0.2.0"))
    assert result is not None and result.features_summary
    failures = [issue for issue in result.issues
                if issue.requirement and issue.requirement.code == "com.nvidia.simready.CP.011"]
    assert bool(failures) is (clearance < 0)
    failed = result.features_summary["FET201_AIF"].get("failing requirements", [])
    assert ("com.nvidia.simready.CP.011" in failed) is (clearance < 0)

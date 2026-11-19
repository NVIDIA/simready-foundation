# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the sample CI gate against both receipt formats and explicit targets."""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

# The lightweight tooling suite runs before USD/validation dependencies are installed.
# Wheel-validation CI supplies them and must execute these tests without a skip.
if os.environ.get("SIMREADY_REQUIRE_BUILT_TIER_WHEEL") == "1":
    from pxr import Usd
    import simready.validate
else:
    Usd = pytest.importorskip("pxr.Usd", reason="sample receipt tests require USD")
    pytest.importorskip("simready.validate", reason="sample receipt tests require simready-validate")

_CHECK = Path(__file__).resolve().parents[3] / "sr_specs/tests/validate_sample_content.py"
_SPEC = importlib.util.spec_from_file_location("sample_validation_ci", _CHECK)
ci = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci)

ASSET = "sample_content/asset.usda"
OLD = ("Robotics-Prop", "3.2.0")
NEW = ("Robotics-Prop", "4.0.0")
PASS = {"FET001_Test.0-1-0": {"passed": True}}
FAIL = {"FET001_Test.0-1-0": {"passed": False}}


def receipt(target):
    return {"profile": target[0], "profile_version": target[1]}


def envelope(*targets):
    return {"profiles": {"@".join(target): receipt(target) for target in targets}}


def write_asset(tmp_path, metadata):
    path = tmp_path / ASSET
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": {"validation": metadata}}
    stage.GetRootLayer().Save()
    return str(path)


@pytest.mark.parametrize("metadata, expected", [
    (receipt(OLD), {OLD}),
    (envelope(OLD, NEW), {OLD, NEW}),
    ({**receipt(OLD), **envelope(OLD, NEW)}, {OLD, NEW}),
    ({}, set()),
])
def test_reads_receipts_from_usd(tmp_path, metadata, expected):
    path = write_asset(tmp_path, metadata)
    targets, errors = ci.read_sample_targets(str(tmp_path), [path], {})
    assert errors == []
    assert targets == {ASSET: expected}


@pytest.mark.parametrize("metadata", [
    None,
    {"profile": "Robotics-Prop"},
    {"profile": "", "profile_version": "3.2.0"},
    {"profile": "Robotics-Prop", "profile_version": 3},
    {"profiles": []},
    {"profiles": {"Robotics-Prop@4.0.0": receipt(OLD)}},
    {"profiles": {"Robotics-Prop@3.2.0": None}},
])
def test_rejects_malformed_or_incomplete_claims(metadata):
    with pytest.raises(ValueError):
        ci._profile_targets(metadata)


def test_each_target_gets_its_own_explicit_validation_request(tmp_path, monkeypatch):
    def validate(configs):
        assert [(c.profile_id, c.profile_version) for c in configs] == [OLD, NEW]
        assert all(c.asset_path == str(tmp_path / ASSET) and not c.write_metadata for c in configs)
        return [SimpleNamespace(features_summary=PASS), SimpleNamespace(features_summary=FAIL)]
    monkeypatch.setattr(ci.sv, "validate_asset_list", validate)
    results, errors = ci.validate_sample_targets(str(tmp_path), {ASSET: {NEW, OLD}})
    assert errors == []
    assert results == {(ASSET, *OLD): PASS, (ASSET, *NEW): FAIL}


@pytest.mark.parametrize("result", [None, SimpleNamespace(features_summary={})])
def test_unavailable_or_empty_result_is_an_error(tmp_path, monkeypatch, result):
    monkeypatch.setattr(ci.sv, "validate_asset_list", lambda configs: [result])
    results, errors = ci.validate_sample_targets(str(tmp_path), {ASSET: {OLD}})
    assert results == {}
    assert len(errors) == 1 and "Validation unavailable or empty" in errors[0]
    assert "missing on" not in errors[0]


def compare(old_targets, new_targets, old_results, new_results, removals=None, manifest=None, deletions=None):
    return ci.compare_sample_targets(
        {ASSET: old_targets}, {ASSET: new_targets}, old_results, new_results,
        {ASSET} if manifest is None else manifest, deletions or {}, removals or {},
    )


def test_multi_profile_success_does_not_hide_another_targets_regression():
    errors = compare(
        {OLD, NEW}, {OLD, NEW}, {(ASSET, *OLD): PASS, (ASSET, *NEW): PASS},
        {(ASSET, *OLD): FAIL, (ASSET, *NEW): PASS},
    )
    assert len(errors) == 1
    assert "Robotics-Prop@3.2.0" in errors[0]


def test_removing_a_claim_requires_its_exact_record():
    assert "without a removal record" in compare({OLD}, set(), {}, {})[0]
    assert compare({OLD}, set(), {}, {}, {(ASSET, *OLD): "Pose-only sample"}) == []
    assert "without a removal record" in compare({OLD}, set(), {}, {}, {(ASSET, *NEW): "Wrong version"})[0]


def test_record_remains_valid_after_merge_but_rejects_reintroduced_claim():
    removal = {(ASSET, *OLD): "Pose-only sample"}
    assert compare(set(), set(), {}, {}, removal) == []
    assert "still claimed" in compare(set(), {OLD}, {}, {}, removal)[0]


def test_profile_version_change_is_not_compared_as_the_same_target():
    errors = compare({OLD}, {NEW}, {(ASSET, *OLD): PASS}, {(ASSET, *NEW): FAIL})
    assert len(errors) == 2
    assert any("removed profile claim (Robotics-Prop@3.2.0)" in e for e in errors)
    assert any("newly claimed profile fails" in e for e in errors)
    assert not any("used to pass" in e for e in errors)


def test_preexisting_failure_is_not_a_regression():
    assert compare({OLD}, {OLD}, {(ASSET, *OLD): FAIL}, {(ASSET, *OLD): FAIL}) == []


def test_unprofiled_assets_still_need_known_deletion_records():
    assert "without a known deletion" in compare(set(), set(), {}, {}, manifest=set())[0]
    assert compare(set(), set(), {}, {}, manifest=set(), deletions={ASSET: Path("deletion.toml")}) == []


def test_profile_removal_cannot_hide_missing_file_or_manifest_entry(tmp_path):
    targets, errors = ci.read_sample_targets(str(tmp_path), [str(tmp_path / ASSET)], {})
    assert targets == {} and "missing on disk" in errors[0]
    errors = compare({OLD}, set(), {}, {}, {(ASSET, *OLD): "Pose-only sample"}, manifest=set())
    assert any("requires a published asset" in error for error in errors)


def test_unreadable_usd_is_not_an_unprofiled_asset(tmp_path):
    path = tmp_path / ASSET
    path.parent.mkdir()
    path.write_text("not USD")
    targets, errors = ci.read_sample_targets(str(tmp_path), [str(path)], {})
    assert targets == {} and "Cannot read profile claims" in errors[0]


@pytest.mark.parametrize("replacement", [
    'profile_version = ""',
    'asset_path = "sample_content/../asset.usda"',
    'reason = ""',
])
def test_profile_removal_records_require_complete_exact_identity(tmp_path, replacement):
    content = "[[removal]]\n" + '\n'.join([
        f'asset_path = "{ASSET}"', 'profile = "Robotics-Prop"',
        'profile_version = "3.2.0"', 'reason = "Pose-only sample"',
    ])
    field = replacement.split(" = ")[0]
    content = '\n'.join(replacement if line.startswith(field + " = ") else line for line in content.splitlines())
    path = tmp_path / "sample_content/known_profile_removals.toml"
    path.parent.mkdir()
    path.write_text(content)
    records, errors = ci.load_known_profile_removals(str(tmp_path))
    assert records == {} and errors


def test_shipped_pose_removal_record_is_valid():
    records, errors = ci.load_known_profile_removals(str(_CHECK.parents[3]))
    assert errors == []
    asset = (
        "sample_content/common_assets/props_general/pose_electricians_large_tool_box_01/"
        "simready_usd/sm_pose_electricians_large_tool_box_01_01.usd"
    )
    assert records[(asset, *OLD)]

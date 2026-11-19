# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validation gate: locating the installed tier's requirement tree and reading its report."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from simready.metadata_conform import validation
from simready.metadata_conform.validation import ValidatorUnavailableError, _rules_dir


@pytest.mark.parametrize("name", ["capabilities", "rules_and_reqs"])
def test_either_requirement_tree_name_is_found(tmp_path, name):
    (tmp_path / name).mkdir()
    assert _rules_dir(tmp_path) == tmp_path / name


def test_the_requirement_tree_wins_over_relocated_cap_contracts(tmp_path):
    (tmp_path / "rules_and_reqs").mkdir()
    (tmp_path / "capabilities").mkdir()
    assert _rules_dir(tmp_path) == tmp_path / "rules_and_reqs"


def test_a_tier_without_a_requirement_tree_is_reported(tmp_path):
    with pytest.raises(ValidatorUnavailableError):
        _rules_dir(tmp_path)


def _validate(monkeypatch, tmp_path, summary, *, version="1.2.0"):
    """Run ``validate_asset`` against a canned validator report."""
    (tmp_path / "rules_and_reqs").mkdir(exist_ok=True)
    monkeypatch.setattr(validation, "_tier_root", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        report = {
            "asset.usda": {
                "profile_id": "Package-Candidate",
                "profile_version": version,
                "features_summary": summary,
            }
        }
        output.write_text(json.dumps(report), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(validation.subprocess, "run", fake_run)
    return validation.validate_asset(tmp_path / "asset.usda", version=version)


@pytest.mark.parametrize(
    ("version", "summary"),
    [
        (
            "1.2.0",
            {
                "CAP031_SelfContainedPackage.0-1-0": {"passed": True},
                "CAP033_SimReadyPackage.0-3-0": {"passed": True},
                "CAP000_Core.0-2-0": {"passed": False},
            },
        ),
        (
            "1.3.0",
            {
                "CAP031_SelfContainedPackage.0-1-0": {"passed": True},
                "CAP033_SimReadyPackage.0-4-0": {"passed": True},
            },
        ),
        ("1.2.0", {"FET_031_STANDARD": {"passed": True}, "FET_033_STANDARD": {"passed": True}}),
    ],
)
def test_passing_metadata_contracts_pass_in_either_layout(monkeypatch, tmp_path, version, summary):
    result = _validate(monkeypatch, tmp_path, summary, version=version)

    assert result.passed is True
    assert result.failing_features == ()


def test_a_failing_metadata_contract_is_reported_by_its_id(monkeypatch, tmp_path):
    summary = {
        "CAP031_SelfContainedPackage.0-1-0": {"passed": True},
        "CAP033_SimReadyPackage.0-3-0": {"passed": False},
    }
    result = _validate(monkeypatch, tmp_path, summary)

    assert result.passed is False
    assert result.failing_features == ("CAP033_SimReadyPackage.0-3-0",)


def test_a_missing_metadata_contract_is_a_validator_error(monkeypatch, tmp_path):
    summary = {"CAP031_SelfContainedPackage.0-1-0": {"passed": True}}
    result = _validate(monkeypatch, tmp_path, summary)

    assert result.passed is False
    assert result.failing_features == ("VALIDATOR_ERROR",)

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Profile validation regression tests for the Generic_CDU sample asset."""
from pathlib import Path
import shutil

import pytest


@pytest.fixture(scope="module")
def validator():
    import simready.validate as sv

    sv.destroy()
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield sv
    sv.destroy()


@pytest.mark.parametrize("profile,version", [
    ("AIF-Entity", "0.1.0"),
    ("AIF-Entity", "0.2.0"),
    ("Package-Candidate", "1.3.0"),
])
def test_generic_cdu_profiles(tmp_path, validator, profile, version):
    source = Path(__file__).resolve().parents[4] / "sample_content/aif/Generic_CDU"
    staged = tmp_path / "Generic_CDU"
    shutil.copytree(source, staged)
    result = validator.validate_asset(validator.AssetValidationConfig(
        asset_path=str(staged / "asset/Generic_CDU.usda"),
        profile_id=profile,
        profile_version=version,
    ))
    assert result is not None and result.features_summary
    assert validator.features_summary_passed(result.features_summary), result.features_summary
    errors = [issue for issue in result.issues if issue.severity.name == "ERROR"]
    assert not errors, errors

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Profile validation regression tests for the Generic_CDU sample asset."""
from pathlib import Path
import shutil

import pytest
from pxr import Usd


@pytest.fixture(scope="module")
def validator():
    import simready.validate as sv

    sv.destroy()
    sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
    yield sv
    sv.destroy()


@pytest.mark.parametrize("profile, version, keep_vector, expected_failure", [
    ("AIF-Entity", "0.1.0", True, None),
    ("AIF-Entity", "0.2.0", True, None),
    ("Package-Candidate", "1.3.0", True, None),
    ("AIF-Entity", "0.1.0", False, "AM.004"),
    ("AIF-Entity", "0.2.0", False, "AM.004"),
    ("AIF-Entity", "0.3.0", True, "AM.009"),
    ("AIF-Entity", "0.3.0", False, None),
])
def test_generic_cdu_profiles(tmp_path, validator, profile, version, keep_vector, expected_failure):
    source = Path(__file__).resolve().parents[4] / "sample_content/aif/Generic_CDU"
    asset = shutil.copytree(source, tmp_path / "Generic_CDU") / "asset"
    if not keep_vector:
        props = Usd.Stage.Open(str(asset / "layers/Generic_CDU_Properties.usda"))
        assert props.GetDefaultPrim().RemoveProperty("aif:core:overallGeometryDimensions")
        props.GetRootLayer().Save()
    result = validator.validate_asset(validator.AssetValidationConfig(
        asset_path=str(asset / "Generic_CDU.usda"), profile_id=profile, profile_version=version,
    ))
    assert result is not None and result.features_summary
    assert validator.features_summary_passed(result.features_summary) == (expected_failure is None), result.features_summary
    errors = [issue for issue in result.issues if issue.severity.name == "ERROR"]
    assert not errors, errors
    failures = {issue.requirement.code for issue in result.issues if issue.severity.name == "FAILURE"}
    assert failures == ({f"com.nvidia.simready.{expected_failure}"} if expected_failure else set())

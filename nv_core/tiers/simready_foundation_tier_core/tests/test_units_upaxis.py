# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""UN.006 requires authored stage metadata, independently of site fallback."""

import pytest
from pxr import Usd, UsdGeom
from simready.foundation.tier_core.rules_and_reqs.core.units.validation import UpAxisZChecker


def issues(stage):
    checker = UpAxisZChecker()
    checker.CheckStage(stage)
    return checker.GetIssues()


@pytest.mark.parametrize("fallback", [UsdGeom.Tokens.y, UsdGeom.Tokens.z])
def test_missing_upaxis_fails_even_with_site_fallback(monkeypatch, fallback):
    stage = Usd.Stage.CreateInMemory()
    monkeypatch.setattr(UsdGeom, "GetStageUpAxis", lambda stage: fallback)
    result = issues(stage)
    assert len(result) == 1
    assert result[0].requirement.code == "com.nvidia.simready.UN.006"
    assert "no upAxis specified" in result[0].message


def test_authored_z_passes():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    assert not issues(stage)


@pytest.mark.parametrize("axis", ["Y", "X", ""])
def test_authored_other_axis_fails(axis):
    stage = Usd.Stage.CreateInMemory()
    stage.SetMetadata("upAxis", axis)
    result = issues(stage)
    assert len(result) == 1
    assert result[0].requirement.code == "com.nvidia.simready.UN.006"


def test_authored_session_z_passes():
    stage = Usd.Stage.CreateInMemory()
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    assert not issues(stage)


def test_clearing_authored_z_fails(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.ClearMetadata("upAxis")
    monkeypatch.setattr(UsdGeom, "GetStageUpAxis", lambda stage: UsdGeom.Tokens.z)
    assert len(issues(stage)) == 1

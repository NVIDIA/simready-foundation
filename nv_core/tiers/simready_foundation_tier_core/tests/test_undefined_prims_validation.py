# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""HI.010 must report undefined prims through the validation framework.

Requires an installed or editable core tier with generated requirements, pytest,
usd-validation-nvidia, and USD. Run against the tier built from the source under test.
"""

import pytest
import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia as validation
from pxr import Usd
from simready.foundation.tier_core.rules_and_reqs.hierarchy.validation import UndefinedPrimsChecker


def _stage(path=None):
    stage = Usd.Stage.CreateNew(str(path)) if path else Usd.Stage.CreateInMemory()
    stage.SetDefaultPrim(stage.DefinePrim("/Asset", "Xform"))
    return stage


def _check(stage):
    checker = UndefinedPrimsChecker()
    assert checker.CheckStage(stage) is None
    issues = list(checker.GetIssues())
    for issue in issues:
        assert issue.requirement == cap.HierarchyRequirements.HI_010
        assert issue.severity == validation.IssueSeverity.FAILURE
    return issues


def _add_arc(prim, arc, identifier):
    if arc == "reference":
        prim.GetReferences().AddReference(identifier)
    else:
        prim.GetPayloads().AddPayload(identifier)


def test_defined_prims_pass():
    stage = _stage()
    stage.DefinePrim("/Asset/Part", "Xform")
    assert _check(stage) == []


@pytest.mark.parametrize("path", ["/Orphan", "/Asset/Orphan"])
def test_undefined_over_reports_requirement_and_location(path):
    stage = _stage()
    stage.OverridePrim(path)

    issues = _check(stage)

    assert len(issues) == 1
    assert f"Prim '{path}'" in issues[0].message
    assert stage.GetRootLayer().identifier in issues[0].message
    assert "undefined 'over'" in issues[0].message


@pytest.mark.parametrize(
    "path",
    [
        "/OmniverseKit_Persp",
        "/OmniverseKit_Front",
        "/OmniverseKit_Top",
        "/OmniverseKit_Right",
        "/OmniKit_Viewport_LightRig",
        "/OmniverseKit_Persp/Child",
        "/Asset/OmniverseKitViewportCameraMesh",
    ],
)
def test_kit_viewport_overs_pass(path) -> None:
    stage = _stage()
    stage.OverridePrim(path)
    assert _check(stage) == []


def test_kit_viewport_exemption_does_not_hide_other_overs() -> None:
    stage = _stage()
    stage.OverridePrim("/OmniverseKit_Persp")
    stage.OverridePrim("/OmniverseKit_Custom")

    issues = _check(stage)

    assert len(issues) == 1
    assert "Prim '/OmniverseKit_Custom'" in issues[0].message


def test_reports_each_undefined_prim():
    stage = _stage()
    paths = ["/Orphan", "/Asset/Orphan"]
    for path in paths:
        stage.OverridePrim(path)

    issues = _check(stage)

    assert len(issues) == len(paths)
    for path in paths:
        assert any(f"Prim '{path}'" in issue.message for issue in issues)


@pytest.mark.parametrize("arc", ["reference", "payload"])
def test_missing_asset_allows_descendant_over(tmp_path, arc):
    stage = _stage(tmp_path / "asset.usda")
    assert not (tmp_path / "missing.usda").exists()
    _add_arc(stage.GetDefaultPrim(), arc, "./missing.usda")
    stage.OverridePrim("/Asset/Orphan")

    assert _check(stage) == []


@pytest.mark.parametrize("arc", ["reference", "payload"])
def test_existing_asset_does_not_allow_undefined_over(tmp_path, arc):
    source = _stage(tmp_path / "source.usda")
    source.GetRootLayer().Save()
    stage = _stage(tmp_path / "asset.usda")
    _add_arc(stage.GetDefaultPrim(), arc, "./source.usda")
    stage.OverridePrim("/Asset/Orphan")

    issues = _check(stage)

    assert len(issues) == 1
    assert "Prim '/Asset/Orphan'" in issues[0].message


@pytest.mark.parametrize("arc", ["reference", "payload"])
def test_over_of_composed_definition_passes(tmp_path, arc):
    source = _stage(tmp_path / "source.usda")
    source.DefinePrim("/Asset/Part", "Xform")
    source.GetRootLayer().Save()
    stage = _stage(tmp_path / "asset.usda")
    _add_arc(stage.GetDefaultPrim(), arc, "./source.usda")
    prim = stage.OverridePrim("/Asset/Part")
    assert prim.IsDefined()

    assert _check(stage) == []


def test_validation_engine_reports_hi010_failure():
    stage = _stage()
    stage.OverridePrim("/Asset/Orphan")
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(UndefinedPrimsChecker)

    issues = list(engine.validate(stage).issues)

    assert len(issues) == 1
    assert issues[0].requirement == cap.HierarchyRequirements.HI_010
    assert issues[0].severity == validation.IssueSeverity.FAILURE
    assert "Prim '/Asset/Orphan'" in issues[0].message

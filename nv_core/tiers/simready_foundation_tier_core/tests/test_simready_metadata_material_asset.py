# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""SR.003 and SR.004 on a material asset: a mass of 0 passes only where the default prim is a Material."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import simready.foundation.tier_core.requirements as cap
from pxr import Gf, Usd
from simready.foundation.tier_core.rules_and_reqs.core.sim_ready.validation import (
    MetadataUnion,
    NestedSimReadyMetadata,
)

_CHECKERS = [
    (MetadataUnion, cap.SimReadyRequirements.SR_004),
    (NestedSimReadyMetadata, cap.SimReadyRequirements.SR_003),
]
_HELPER = (
    Path(__file__).parents[1]
    / "simready/foundation/tier_core/skills/simready-foundation-conform-fet-033-standard"
    / "assets/scripts/extract_simready_metadata.py"
)


def _metadata(**physical):
    metadata = {
        "author": "nvidia",
        "asset_name": "Copper_Brushed",
        "asset_type": "material",
        "asset_license": "CC-BY-4.0",
        "category": "metal",
        "source_file": "Copper_Brushed.mtlx",
        "usd_date_generated": "2026-10-22",
        "qcode": "Q753",
        "rigid_body_count": 0,
        "asset_extents": Gf.Vec3f(0, 0, 0),
        "mass": 0.0,
    }
    metadata.update(physical)
    return metadata


def _stage(tmp_path, prim_type, **physical):
    stage = Usd.Stage.CreateNew(str(tmp_path / "asset.usda"))
    stage.SetDefaultPrim(stage.DefinePrim("/Asset", prim_type))
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": _metadata(**physical)}
    return stage


def _messages(checker_type, requirement, stage):
    checker = checker_type()
    checker.CheckStage(stage)
    issues = list(checker.GetIssues())
    assert all(issue.requirement == requirement for issue in issues)
    return [issue.message for issue in issues]


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_material_asset_with_zero_physical_fields_passes(tmp_path, checker_type, requirement):
    assert _messages(checker_type, requirement, _stage(tmp_path, "Material")) == []


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_material_asset_with_a_negative_mass_fails(tmp_path, checker_type, requirement):
    messages = _messages(checker_type, requirement, _stage(tmp_path, "Material", mass=-1.0))
    assert len(messages) == 1
    assert "'mass' must be a positive number of kilograms" in messages[0]


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_material_asset_with_physical_values_still_passes(tmp_path, checker_type, requirement):
    stage = _stage(tmp_path, "Material", mass=0.5, rigid_body_count=1, asset_extents=Gf.Vec3f(0.1, 0, 0))
    assert _messages(checker_type, requirement, stage) == []


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_other_asset_still_needs_a_positive_mass(tmp_path, checker_type, requirement):
    messages = _messages(checker_type, requirement, _stage(tmp_path, "Xform"))
    assert len(messages) == 1
    assert "'mass' must be a positive number of kilograms" in messages[0]


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_other_asset_with_zero_rigid_bodies_and_extents_passes(tmp_path, checker_type, requirement):
    stage = _stage(tmp_path, "Xform", mass=7.5)
    assert _messages(checker_type, requirement, stage) == []


@pytest.mark.parametrize(("prim_type", "extents", "mass"), [("Material", [0.0, 0.0, 0.0], 0.0), ("Xform", None, None)])
def test_metadata_helper_derives_zero_extents_and_mass_only_for_a_material_asset(tmp_path, prim_type, extents, mass):
    stage = Usd.Stage.CreateNew(str(tmp_path / "asset.usda"))
    stage.SetDefaultPrim(stage.DefinePrim("/Asset", prim_type))
    stage.Save()

    result = subprocess.run(
        [sys.executable, str(_HELPER), str(tmp_path / "asset.usda"), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    derived = json.loads(result.stdout)["derived"]

    assert (derived["asset_extents"], derived["mass"], derived["rigid_body_count"]) == (extents, mass, 0)

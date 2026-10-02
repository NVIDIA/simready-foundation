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
"""A VM.TEX.003 finding has a Suggestion, and applying it repairs the stage.

The repair belongs to the requirement that reports the failure, so any consumer of
``usd-validation-nvidia`` applies it without knowing how it works.

Requires an installed ``simready-foundation-tier-core`` wheel (with generated
requirements) plus ``usd-validation-nvidia`` and ``pxr``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("usd_validation_nvidia")
pytest.importorskip("pxr")
pytest.importorskip("simready.foundation.tier_core.requirements")

from pxr import Sdf, Usd, UsdShade  # noqa: E402

from simready.foundation.tier_core.capabilities.visualization.materials import (  # noqa: E402
    validation as materials,
)

MATERIAL_PATH = "/World/Looks/PaintedMetal"
READER_PATH = f"{MATERIAL_PATH}/DiffuseTexture"


def _stage_with_diffuse_texture(authored_colorspace: str) -> Usd.Stage:
    """One UsdPreviewSurface whose diffuseColor texture declares a color space."""
    stage = Usd.Stage.CreateInMemory()
    material = UsdShade.Material.Define(stage, MATERIAL_PATH)

    surface = UsdShade.Shader.Define(stage, f"{MATERIAL_PATH}/Surface")
    surface.CreateIdAttr("UsdPreviewSurface")
    material.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")

    reader = UsdShade.Shader.Define(stage, READER_PATH)
    reader.CreateIdAttr("UsdUVTexture")
    reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set("./textures/albedo.png")
    reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(authored_colorspace)
    reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

    surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        reader.ConnectableAPI(), "rgb"
    )
    return stage


def _tex003_issues(stage: Usd.Stage) -> list:
    """Every VM.TEX.003 issue the visual-materials checker reports on one stage."""
    import simready.foundation.tier_core.requirements as cap

    checker = materials.VisualMaterialsCapabilityChecker()
    checker.CheckStage(stage)
    for prim in stage.Traverse():
        checker.CheckPrim(prim)
    return [
        issue
        for issue in checker.GetIssues()
        if issue.requirement == cap.MaterialsRequirements.VM_TEX_003
    ]


def test_wrong_colorspace_on_a_color_texture_is_reported_with_a_fix():
    """A data encoding on a texture feeding diffuseColor fails, and the finding fixes it."""
    stage = _stage_with_diffuse_texture("raw")

    issues = _tex003_issues(stage)

    assert issues, "a 'raw' texture feeding diffuseColor must fail VM.TEX.003"
    assert any(issue.suggestion is not None for issue in issues), (
        "the failure must offer a Suggestion so a consumer can apply the repair"
    )


def test_applying_the_suggestion_makes_the_stage_pass():
    """Calling the Suggestion's callable authors the color space the check expects."""
    stage = _stage_with_diffuse_texture("raw")

    issue = next(issue for issue in _tex003_issues(stage) if issue.suggestion is not None)
    reader_prim = stage.GetPrimAtPath(READER_PATH)
    issue.suggestion.callable(stage, reader_prim)

    authored = reader_prim.GetAttribute("inputs:sourceColorSpace").Get()
    assert authored == "sRGB", f"expected the repair to author 'sRGB', got {authored!r}"
    assert not _tex003_issues(stage), "the repaired stage must no longer fail VM.TEX.003"

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Installed-wheel regressions for semantic verdicts in the public API and CLI.

Run with simready-validate and the candidate Core wheel installed. Each consumer
runs in a fresh process so registry state cannot mask discovery failures.
"""

import json
import subprocess
import sys

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdShade

pytest.importorskip("simready.validate")


@pytest.mark.parametrize("label_state", ["missing", "sampled", "static"])
def test_stock_profile_semantic_verdict(tmp_path, label_state):
    asset = tmp_path / f"{label_state}.usda"
    stage = Usd.Stage.CreateNew(str(asset))
    root = UsdGeom.Xform.Define(stage, "/Asset")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Asset/Mesh")
    material = UsdShade.Material.Define(stage, "/Asset/Material")
    shader = UsdShade.Shader.Define(stage, "/Asset/Material/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    if label_state != "missing":
        material.GetPrim().AddAppliedSchema("SemanticsLabelsAPI:material")
        attr = material.GetPrim().CreateAttribute(
            "semantics:labels:material", Sdf.ValueTypeNames.TokenArray
        )
        attr.Set(["metal"])
        if label_state == "sampled":
            attr.Set(["metal"], Usd.TimeCode(1))
            attr.Set(["plastic"], Usd.TimeCode(2))
    stage.GetRootLayer().Save()

    api_report = tmp_path / "api.json"
    code = """
import json, sys
from pathlib import Path
import simready.validate as sv
sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
try:
    result = sv.validate_asset(sv.AssetValidationConfig(
        asset_path=sys.argv[1], profile_id='Robotics-Prop', profile_version='3.2.0'))
    assert result is not None
    assert not any('Failed to initialize rule' in i.message
                   for i in result.issues + result.soft_issues)
    Path(sys.argv[2]).write_text(json.dumps(result.features_summary))
finally:
    sv.destroy()
"""
    api = subprocess.run(
        [sys.executable, "-I", "-c", code, str(asset), str(api_report)],
        capture_output=True, text=True, timeout=60,
    )
    assert api.returncode == 0, api.stdout + api.stderr
    summary = json.loads(api_report.read_text())["FET011_SemanticLabels.RTX.0-1-0"]
    assert summary["passed"] is (label_state == "static")
    assert summary["blocking_failure"] is (label_state != "static")
    if label_state != "static":
        expected = "SL.MAT.001" if label_state == "missing" else "SL.TIME.001"
        assert expected in json.dumps(summary["failing requirements"])

    cli_report = tmp_path / "cli.json"
    cli = subprocess.run(
        [sys.executable, "-I", "-c",
         "from simready.validate._cli import main; raise SystemExit(main())", "--profile",
         "Robotics-Prop", "--version", "3.2.0", "--verbose", "--output",
         str(cli_report), str(asset)],
        capture_output=True, text=True, timeout=60,
    )
    # These minimal fixtures have unrelated profile failures, even when labeled.
    assert cli.returncode == 1, cli.stdout + cli.stderr
    assert "Failed to initialize rule" not in cli.stdout + cli.stderr
    assert cli_report.is_file(), cli.stdout + cli.stderr
    report = json.loads(cli_report.read_text())
    assert len(report) == 1
    entry = next(iter(report.values()))
    assert entry["features_summary"]["FET011_SemanticLabels.RTX.0-1-0"] == summary

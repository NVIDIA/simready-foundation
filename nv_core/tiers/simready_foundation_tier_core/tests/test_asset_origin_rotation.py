# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""VG.025 reports a rotated asset root's angle in degrees, as authored (NVBugs 7033940).

Gf.Rotation.GetAngle() already returns degrees. Converting it again with
math.degrees() reported a 30-degree root as 1718.87 degrees.
"""

import re

import pytest
from pxr import Gf, Usd, UsdGeom
from simready.foundation.tier_core.rules_and_reqs.visualization.geometry.validation import (
    AssetOriginPositioningChecker,
)

VG_025 = "com.nvidia.simready.VG.025"
ANGLE = re.compile(r"non-zero rotation: (-?[0-9.]+) degrees")


def rotated_root(degrees):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Root")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Mesh.Define(stage, "/Root/Mesh")
    root.AddRotateZOp().Set(degrees)
    return stage


def rotation_issues(stage):
    checker = AssetOriginPositioningChecker()
    checker.CheckStage(stage)
    return [i for i in checker.GetIssues() if ANGLE.search(i.message)]


def test_unrotated_root_passes():
    assert not rotation_issues(rotated_root(0.0))


@pytest.mark.parametrize("degrees", [30.0, 90.0])
def test_rotated_root_reports_authored_degrees(degrees):
    result = rotation_issues(rotated_root(degrees))
    assert len(result) == 1
    assert result[0].requirement.code == VG_025
    reported = float(ANGLE.search(result[0].message).group(1))
    assert reported == pytest.approx(degrees, abs=0.01)


def test_rotation_below_tolerance_passes():
    # The verdict compares GetAngle() in degrees against TRANSFORM_TOLERANCE;
    # the fix changes only the reported value, so this boundary must not move.
    stage = rotated_root(5e-5)
    assert Gf.Rotation(Gf.Vec3d(0, 0, 1), 5e-5).GetAngle() < 1e-4
    assert not rotation_issues(stage)

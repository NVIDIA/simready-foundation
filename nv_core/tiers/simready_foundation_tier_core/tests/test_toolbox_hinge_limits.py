# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regression test for OMPE-117889.

The electrician toolbox authored its revolute-joint angular limits as radian
magnitudes in ``UsdPhysicsRevoluteJoint.physics:lowerLimit``, which USD
interprets as *degrees*. The lid therefore clamped to ~2.6 degrees instead of
its intended 150 degrees. This test guards that the shipped limits stay on the
degree scale (full travel) so the unit bug cannot silently return.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pxr")
from pxr import Usd, UsdPhysics  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PHYSICS_LAYER = (
    _REPO_ROOT
    / "sample_content"
    / "common_assets"
    / "props_general"
    / "obs_electricians_large_tool_box_a01"
    / "simready_usd"
    / "payloads"
    / "Physics"
    / "physics.usda"
)

# Intended travel of each hinge, in degrees.
_EXPECTED_LOWER_LIMITS = {
    "joint_lid_joint_01": -150.0,
    "joint_handle_joint_01": -84.0,
    "joint_lock_00_joint_01": -84.0,
    "joint_lock_01_joint_01": -84.0,
}


def _joint_lower_limits() -> dict[str, float]:
    stage = Usd.Stage.Open(str(_PHYSICS_LAYER))
    assert stage is not None, f"could not open {_PHYSICS_LAYER}"
    limits: dict[str, float] = {}
    for prim in stage.TraverseAll():
        if prim.IsA(UsdPhysics.RevoluteJoint):
            attr = prim.GetAttribute("physics:lowerLimit")
            if attr and attr.HasAuthoredValue():
                limits[prim.GetName()] = float(attr.Get())
    return limits


@pytest.mark.skipif(
    not _PHYSICS_LAYER.is_file(),
    reason="toolbox sample asset not present in this checkout",
)
def test_toolbox_hinge_limits_are_degrees() -> None:
    limits = _joint_lower_limits()
    assert set(limits) == set(_EXPECTED_LOWER_LIMITS), limits
    for name, expected in _EXPECTED_LOWER_LIMITS.items():
        assert limits[name] == pytest.approx(expected, abs=0.5), (name, limits[name])


@pytest.mark.skipif(
    not _PHYSICS_LAYER.is_file(),
    reason="toolbox sample asset not present in this checkout",
)
def test_toolbox_hinges_are_not_radian_magnitudes() -> None:
    """A degree limit authored as radians collapses to a tiny opening angle."""
    for name, limit in _joint_lower_limits().items():
        assert abs(limit) > 10.0, (
            f"{name} lowerLimit={limit} looks like a radian magnitude "
            "authored into a degree-valued attribute (OMPE-117889)"
        )

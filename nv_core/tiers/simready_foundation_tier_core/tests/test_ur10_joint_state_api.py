# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regression test for OMPE-119316.

The UR10 sample authored the joint-state *properties*
(``state:angular:physics:position`` / ``velocity``) on each revolute joint but
never applied the ``PhysicsJointStateAPI:angular`` schema that owns them, so
DJ.002 ("Has no Joint State API") failed on all six joints. This test guards
that every revolute joint carries the applied angular JointStateAPI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pxr")
from pxr import Usd, UsdPhysics  # noqa: E402

try:  # match the validator's import fallback
    from pxr import PhysxSchema  # type: ignore
except ImportError:
    try:
        from physx_usd_schemas import PhysxSchema  # type: ignore
    except ImportError:  # pragma: no cover - resolved by the isaac extra
        PhysxSchema = None

if PhysxSchema is None:
    pytest.skip("PhysxSchema not available (install the isaac extra)", allow_module_level=True)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PHYSICS_LAYER = (
    _REPO_ROOT
    / "sample_content"
    / "common_assets"
    / "robots_general"
    / "ur10"
    / "simready_usd"
    / "payloads"
    / "Physics"
    / "physics.usda"
)


@pytest.mark.skipif(
    not _PHYSICS_LAYER.is_file(),
    reason="ur10 sample asset not present in this checkout",
)
def test_ur10_revolute_joints_have_joint_state_api() -> None:
    stage = Usd.Stage.Open(str(_PHYSICS_LAYER))
    assert stage is not None, f"could not open {_PHYSICS_LAYER}"

    joints = [p for p in stage.TraverseAll() if p.IsA(UsdPhysics.RevoluteJoint)]
    assert joints, "expected the ur10 to author revolute joints"

    missing = [
        p.GetName()
        for p in joints
        if not PhysxSchema.JointStateAPI(p, "angular")
    ]
    assert not missing, f"revolute joints missing PhysicsJointStateAPI:angular (DJ.002): {missing}"

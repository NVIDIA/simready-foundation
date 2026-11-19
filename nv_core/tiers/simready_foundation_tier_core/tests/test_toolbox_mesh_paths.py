# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regression test for OMPE-117907.

The electrician toolbox authored ``lid_obj_01`` / ``lock_*_obj_01`` /
``handle_obj_01`` as directly ``instanceable`` Xforms, so the mesh paths that
the revolute joints reference as rigid bodies
(``/RootNode/Geometry/<part>_obj_01/<part>_mesh_01``) resolved only as instance
proxies. ``box_obj_01`` instead nests an instanceable ``box_mesh_01`` child, so
its referenced path is a real prim. Path-based mesh lookups therefore found the
box but not the lid and locks ("mesh not found").

This test guards that every joint body target composes as a real
(non-instance-proxy) prim with resolvable mesh geometry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pxr")
from pxr import Usd, UsdPhysics  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ROOT_LAYER = (
    _REPO_ROOT
    / "sample_content"
    / "common_assets"
    / "props_general"
    / "obs_electricians_large_tool_box_a01"
    / "simready_usd"
    / "sm_obs_electricians_large_tool_box_a01_01.usd"
)


def _joint_body_targets(stage: Usd.Stage) -> list[str]:
    targets: list[str] = []
    for prim in stage.TraverseAll():
        if not prim.IsA(UsdPhysics.RevoluteJoint):
            continue
        for rel_name in ("physics:body0", "physics:body1"):
            rel = prim.GetRelationship(rel_name)
            if rel:
                targets.extend(str(p) for p in rel.GetTargets())
    return targets


@pytest.mark.skipif(
    not _ROOT_LAYER.is_file(),
    reason="toolbox sample asset not present in this checkout",
)
def test_joint_body_meshes_are_real_prims() -> None:
    stage = Usd.Stage.Open(str(_ROOT_LAYER))
    assert stage is not None, f"could not open {_ROOT_LAYER}"

    targets = _joint_body_targets(stage)
    assert targets, "expected the toolbox to author revolute-joint bodies"

    for path in targets:
        prim = stage.GetPrimAtPath(path)
        assert prim and prim.IsValid(), f"joint body target not found: {path}"
        assert not prim.IsInstanceProxy(), (
            f"joint body target {path} resolved as an instance proxy; "
            "path-based mesh lookups fail (OMPE-117907)"
        )
        meshes = [
            d
            for d in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())
            if d.GetTypeName() == "Mesh"
        ]
        points = [len(m.GetAttribute("points").Get() or []) for m in meshes]
        assert any(p > 0 for p in points), f"no mesh geometry under {path}"

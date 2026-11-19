# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AF.001 query against the loaded, composed runtime asset."""

from pxr import Usd
from simready.evaluate import test
from simready.foundation.tier_core.asset_frame import FORWARD_DIRECTION, read_forward_direction
from simready.foundation.tier_core.runtime_tests.fet006_materials._scene import asset_root


@test(
    features=[{"id": "FET008_ObjectForward.0-1-0", "version": "*"}],
    name="object_forward_contract",
    version="1.0.0",
    description="Query explicit facing on the loaded asset root and authored components.",
    expected_video="A still of the asset whose local facing vectors are recorded as metrics.",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={"asset_load_timeout": 30},
    max_duration=120,
)
async def test_object_forward_contract(ctx):
    source = Usd.Stage.Open(str(ctx.asset_path))
    source_root = source.GetDefaultPrim() if source else None
    if not source_root:
        ctx.fail("The source asset has no defaultPrim")
        return
    try:
        expected = {
            str(p.GetPath().MakeRelativePath(source_root.GetPath())): read_forward_direction(p)
            for p in Usd.PrimRange(source_root, Usd.TraverseInstanceProxies())
            if p == source_root or p.HasProperty(FORWARD_DIRECTION)
        }
    except ValueError as error:
        ctx.fail(str(error))
        return
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    root_path = asset_root(ctx)
    root = ctx.scene.stage.GetPrimAtPath(root_path) if root_path else None
    if not root:
        ctx.fail("The runtime asset root is unavailable")
        return
    targets = [
        p for p in Usd.PrimRange(root, Usd.TraverseInstanceProxies()) if p == root or p.HasProperty(FORWARD_DIRECTION)
    ]
    try:
        vectors = {str(p.GetPath()): list(read_forward_direction(p)) for p in targets}
    except ValueError as error:
        ctx.fail(str(error))
        return
    actual = {str(p.GetPath().MakeRelativePath(root.GetPath())): read_forward_direction(p) for p in targets}
    if actual.keys() != expected.keys() or any(
        (actual[path] - value).GetLength() > 1e-4 for path, value in expected.items()
    ):
        ctx.fail("Runtime facing locations or values differ from the source asset")
        return
    ctx.add_metric("object_forward_local_vectors", vectors)
    ctx.scene.auto_frame_camera()
    await ctx.settle(count=2)
    await ctx.capture_frame(label="object_forward_contract", role="summary")

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Execute the DSX Air connectivity adapter through Evaluate.

The adapter owns preflight, request bounds, remote commands and output parsing.
Unexpected setup/API/parse errors remain execution errors. Only a completed
measurement with an explicit false verdict becomes a measured contract failure.
"""
import asyncio
import os

from simready.evaluate import test


@test(
    features=[{"id": "FET207_Networking.DSXAir.0-3-0", "version": "*"}],
    name="device_connectivity",
    version="0.3.0",
    description=(
        "Maps the authored network equipment and selected named port to the "
        "operator-supplied DSX Air fixture, executes the bounded connectivity "
        "adapter and records transmitted/received packet evidence."
    ),
    expected_video=(
        "No video is captured. Evidence is the sanitized DSX Air adapter result "
        "with its explicit passed verdict and transmitted/received packet counts."
    ),
    engine=None,
    config_defaults={"fixture_path": ""},
    max_duration=300,
)
async def device_connectivity(ctx):
    # Absolute import supports Evaluate's source-path discovery context.
    from simready.foundation.tier_aif.dsx_air import run_connectivity

    fixture = ctx.config.get("fixture_path") or os.environ.get("DSX_AIR_CONNECTIVITY_FIXTURE")
    if not isinstance(fixture, str) or not fixture.strip():
        raise RuntimeError("Configure fixture_path or DSX_AIR_CONNECTIVITY_FIXTURE before evaluation")
    ctx.step("Checking the configured DSX Air connectivity fixture")
    evidence = await asyncio.to_thread(run_connectivity, ctx.asset_path, fixture)
    if not isinstance(evidence, dict) or type(evidence.get("passed")) is not bool:
        raise RuntimeError("DSX Air adapter returned no explicit boolean connectivity verdict")
    ctx.add_metric("dsx_air_connectivity", evidence)
    ctx.step("Connectivity measurement completed")
    if not evidence["passed"]:
        ctx.fail("The measured DSX Air connectivity check failed", details=evidence)
        return

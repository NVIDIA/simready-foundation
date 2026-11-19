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

"""FET012 Sensor Visual 3DGS: the Gaussian splat renders (SPL.001-006).

WHAT: Verifies the asset's ParticleField3DGaussianSplat visual actually renders in
      the RTX viewport. The offline validator can tell you the splat data is well
      formed; only a render tells you the renderer draws it.

HOW:  1. Load the asset; confirm at least one ParticleField3DGaussianSplat prim
         exists (a render test on an asset with no splats is meaningless).
      2. Frame the asset in a white room (uniform backdrop). 3DGS is self-emissive
         -- it needs no scene light -- but a flat background keeps the diff clean.
         A dome is added only as that uniform backdrop.
      3. Capture a frame with ONLY the splat prims hidden (everything else -- a base
         mesh, if any -- stays as-is).
      4. Capture a frame with the splats shown.
      5. Compare the two: the pixels that change are exactly the splats' screen
         footprint. Pass when that footprint is a non-trivial fraction of the frame.

WHY:  FET_012 exists so vision sensors can render the asset as a Gaussian-splat
      field. Toggling ONLY the splats (not the whole asset) isolates their
      contribution: an asset that also carries a rendering base mesh cannot pass on
      the mesh's pixels -- the diff is zero unless the splats themselves draw. This
      is the splat analog of FET011's labelled/stripped pair.

NOTES:
  - Uses plain viewport capture (no Replicator orchestrator), so both frames are
    captured in one session.
  - No diagnostic material is applied (as FET001 presence does): splats take no
    material, and a base mesh, when present, is typically a `guide` proxy. Framing
    is done from the composed bounds instead.
  - ParticleField3DGaussianSplat renders only in an RTX-capable Kit (Isaac Sim 6.0 /
    Kit 110.1+). On an older runtime the splats never draw and the diff is ~0, so the
    test fails with the remediation below rather than silently passing.
"""

from simready.evaluate.core.decorator import test

SPLAT_TYPE_NAME = "ParticleField3DGaussianSplat"


def _splat_prims(stage):
    """Every ParticleField3DGaussianSplat prim on the composed stage."""
    return [p for p in stage.Traverse() if p.GetTypeName() == SPLAT_TYPE_NAME]


def _set_splats_visible(stage, splats, visible):
    """Show or hide only the splat prims, authored in the session layer so the
    source asset is never modified. Everything else in the scene is untouched."""
    from pxr import Usd, UsdGeom

    token = UsdGeom.Tokens.inherited if visible else UsdGeom.Tokens.invisible
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for prim in splats:
            UsdGeom.Imageable(prim).GetVisibilityAttr().Set(token)


@test(
    features=[
        {"id": "FET012_GaussianSplat.0-1-0", "version": "*"},
    ],
    name="gaussian_splat_presence",
    description=(
        "Renders the asset's ParticleField3DGaussianSplat field in the RTX viewport "
        "and measures the splats' screen footprint by toggling ONLY the splat prims: "
        "the fraction of pixels that change between splats-hidden and splats-shown. "
        "Passes when that footprint reaches min_splat_coverage, which shows the "
        "renderer actually draws the Gaussian splats (and not some other geometry)."
    ),
    expected_video=(
        "Two still frames: with the splats hidden the asset's Gaussian-splat visual "
        "is absent; with them shown the splat field produces changed pixels on a "
        "flat white background. The min_splat_coverage gate measures this sampled "
        "screen footprint, not photorealism or appearance quality."
    ),
    version="0.2.1",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "settle_frames": 5,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
        # Fraction of the frame the splats must cover (pixels that change when the
        # splats are toggled). Low on purpose: a small prop framed with padding
        # covers only a few percent, and the question is whether the splats draw at
        # all, not whether they are large.
        "min_splat_coverage": 0.01,
    },
    max_duration=600,
)
async def test_gaussian_splat_presence(ctx):
    """Splat-presence check -- the ParticleField3DGaussianSplat must render."""
    from simready.foundation.tier_core.runtime_tests._visual_readback import validate_visual_config

    validate_visual_config(ctx.config, fractions=("min_splat_coverage",))
    cfg = ctx.config

    # --- Load + precheck (runtime SPL.001) ---
    ctx.set_settle_frames(int(cfg["settle_frames"]))
    ctx.scene.load_asset(ctx.asset_path, timeout=int(cfg["asset_load_timeout"]))

    stage = ctx.scene.stage
    splats = _splat_prims(stage)
    if not splats:
        ctx.fail(
            "No ParticleField3DGaussianSplat prim found in the composed stage, so "
            "there is nothing to render for this test.\n"
            "\n"
            "How to fix:\n"
            "- Author the visual representation as a ParticleField3DGaussianSplat "
            "prim (UsdVol, OpenUSD 26.03+).\n"
            "- If the splats live in a payload/reference, confirm it composes by "
            "default (or that the variant that brings it in is selected)."
        )
        return
    ctx.add_metric("gs_splat_prim_count", len(splats))

    # --- Scene: uniform white backdrop, framed with the splats visible so the
    #     bounds include them. The dome is the backdrop only; splats are
    #     self-emissive and do not need it to be lit. ---
    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(1, 1, 1)
    room.hide_ground()
    ctx.scene.lighting.add_dome(intensity=1000.0)
    ctx.scene.auto_frame_camera(padding=float(cfg["camera_padding"]))
    await ctx.settle()

    # --- Capture with ONLY the splats hidden. allow_blank: for a splat-only asset
    #     this frame is the empty backdrop; the blank/washed-frame retry must not
    #     fight it. (For a mesh+splat asset the mesh still renders here.) ---
    ctx.step("Capturing with splats hidden")
    _set_splats_visible(stage, splats, False)
    await ctx.settle()
    frame_off = await ctx.capture_frame(label="gs_splat_off", allow_blank=True)

    # --- Capture with the splats shown ---
    ctx.step("Capturing with splats shown")
    _set_splats_visible(stage, splats, True)
    await ctx.settle()
    frame_on = await ctx.capture_frame(label="gs_splat_on")

    # --- Score: the changed pixels are exactly the splats' footprint. ---
    ctx.step("Measuring splat footprint")
    coverage = ctx.compare_images(frame_off, frame_on, threshold=0.02).different_ratio
    minimum = float(cfg["min_splat_coverage"])
    passed = coverage >= minimum

    ctx.add_metric("gs_splat_coverage", round(coverage, 6))
    ctx.add_metric("gs_present_passed", 1 if passed else 0)

    if not passed:
        ctx.fail(
            "The Gaussian splats did not render: toggling the splat prims changed "
            "only %.2f%% of the frame (need >=%.0f%%), so no splat pixels appeared.\n"
            "\n"
            "How to fix:\n"
            "- Run on Isaac Sim 6.0 or later (Kit 110.1+). Earlier runtimes do not "
            "render ParticleField3DGaussianSplat, so a valid splat still shows blank.\n"
            "- Confirm the RTX render path is active (Real-Time or Path-Traced), not "
            "hdStorm/MinimalRendering.\n"
            "- Confirm the splat prims are not otherwise hidden and carry data "
            "(positions + radiance).\n"
            "- Confirm the asset is in frame; a mis-framed asset also shows no splats."
            % (coverage * 100, minimum * 100)
        )
        return

    ctx.log("3DGS present: splats cover %.2f%% of the frame" % (coverage * 100))

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

"""FET013 Multi-Representation Visual: every representation composes and holds the
visual envelope (AV.001-003, AV.005).

WHAT: An asset that declares a ``Representation`` variation offers mutually
      exclusive whole-asset visual representations (for example a detailed mesh
      and a Gaussian-splat capture of the same object). Each one must compose on
      its own and occupy the same visual envelope, so swapping the representation
      never moves or resizes the object in a scene.

HOW:  1. Open the source asset and read its ``Representation`` variation entries.
      2. For each authored option, recompose the asset with ONLY that option
         selected (on the session layer) and measure the visual envelope.
      3. Pass when every option composes to renderable geometry and its envelope
         matches the authored-default envelope within tolerance.
      4. Load the asset in the viewport and capture a frame per option as the
         rendered proof that each representation draws.

WHY:  FET_013 promises representations are interchangeable. A representation that
      renders empty, or that changes the object's footprint, breaks any consumer
      that framed, placed, or collision-pruned the object by its envelope.
"""

from pxr import Usd
from simready.evaluate import test
from simready.foundation.tier_core import asset_variants as av
from simready.foundation.tier_core.runtime_tests.fet013_representation import (
    _variation as var,
)


@test(
    features=[{"id": "FET013_MultiRepresentationVisual.0-1-0", "version": "*"}],
    name="representation_variation",
    version="1.0.0",
    description=(
        "Recomposes the asset once per declared Representation option and checks that "
        "each one composes to renderable geometry whose visual envelope matches the "
        "authored-default envelope, then renders a frame per option."
    ),
    expected_video=(
        "One still per representation option (for example a detailed mesh and a "
        "Gaussian-splat capture). The object looks different but occupies the same "
        "footprint in every frame."
    ),
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "settle_frames": 3,
        "camera_padding": 1.2,
        # Envelope size axes may differ by at most this many meters between options.
        "envelope_tolerance_m": av.ENVELOPE_TOLERANCE_M,
        # Cap the number of rendered captures so a many-option asset stays bounded.
        "max_captures": 4,
    },
    max_duration=600,
)
async def test_representation_variation(ctx):
    cfg = ctx.config
    tol = float(cfg["envelope_tolerance_m"])

    source = Usd.Stage.Open(str(ctx.asset_path))
    if not source or not source.GetDefaultPrim():
        ctx.fail("The source asset has no defaultPrim, so no representation can be composed.")
        return

    entries = var.category_entries(source, av.CATEGORY_REPRESENTATION)
    if not entries:
        ctx.fail(
            "No Representation variation is declared on the asset, so there is nothing "
            "to switch between.\n"
            "\n"
            "How to fix:\n"
            "- Author at least one Representation variant set and record it under "
            "customLayerData.SimReady_Metadata.Variants.Representation (AV.001).\n"
            "- Give it two or more options (for example Mesh and GaussianSplat)."
        )
        return

    root_layer = source.GetRootLayer()
    baseline = av.envelope_size(av.visual_envelope(source))
    if baseline is None:
        ctx.fail("The authored-default selection composes no visible geometry (AV.005).")
        return

    option_sizes = {}
    failures = []
    for variant_set_name, entry in entries:
        for option in var.entry_options(source, entry, variant_set_name):
            composed = var.compose_with_entry_selection(root_layer, entry, variant_set_name, option)
            size = av.envelope_size(av.visual_envelope(composed))
            key = f"{variant_set_name}={option}"
            if size is None:
                failures.append(f"{key} composes no visible geometry")
                continue
            option_sizes[key] = [round(size[i], 6) for i in range(3)]
            if not av.sizes_match(baseline, size, tol):
                failures.append(f"{key} envelope {var.axis_deltas(baseline, size)} exceeds {tol} m")

    ctx.add_metric("representation_baseline_size", [round(baseline[i], 6) for i in range(3)])
    ctx.add_metric("representation_option_sizes", option_sizes)

    if failures:
        ctx.fail(
            "One or more representations broke the visual-envelope invariant:\n- "
            + "\n- ".join(failures)
            + "\n\nHow to fix:\n"
            "- Ensure every option composes to renderable geometry (AV.003).\n"
            "- Re-author options so the visible bounds match within tolerance (AV.005)."
        )
        return

    ctx.scene.load_asset(ctx.asset_path, timeout=int(cfg["asset_load_timeout"]))
    ctx.set_settle_frames(int(cfg["settle_frames"]))
    stage = ctx.scene.stage
    captured = 0
    budget = int(cfg["max_captures"])
    for variant_set_name, entry in entries:
        for option in var.entry_options(source, entry, variant_set_name):
            if captured >= budget:
                break
            if not var.runtime_select(stage, entry, variant_set_name, option):
                continue
            ctx.scene.auto_frame_camera(padding=float(cfg["camera_padding"]))
            await ctx.settle()
            await ctx.capture_frame(label=f"representation_{variant_set_name}_{option}")
            captured += 1

    ctx.log("All %d representation option(s) composed and held the visual envelope." % len(option_sizes))

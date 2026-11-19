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

"""FET016 Appearance Variant: every appearance option composes, looks different, and
is visual-only (AV.001-005, AV.007).

WHAT: An ``Appearance`` variation swaps the material/look of the asset (for
      example a clean versus a weathered finish) with no change to geometry. It
      is declared ``visual-only``: switching one re-binds materials and must not
      move or resize anything, visible or collision.

HOW:  1. Open the source asset and read its ``Appearance`` entries.
      2. For each option, recompose with only that option selected and confirm
         the visual AND collision envelopes match the authored default (a pure
         re-bind leaves all geometry in place).
      3. Load the asset and capture a frame per option; compare consecutive
         options so the renders are measurably different -- the whole point of an
         appearance variant is that the look actually changes.

WHY:  FET_016 lets a scene restyle an object without re-fitting it. An appearance
      variant that moved geometry would break placement; one that produced an
      identical render would be a no-op mislabelled as a variation.
"""

from pxr import Usd
from simready.evaluate import test
from simready.foundation.tier_core import asset_variants as av
from simready.foundation.tier_core.runtime_tests.fet013_representation import (
    _variation as var,
)


@test(
    features=[{"id": "FET016_AppearanceVariant.0-1-0", "version": "*"}],
    name="appearance_variation",
    version="1.0.0",
    description=(
        "Recomposes the asset once per declared Appearance option and checks that each "
        "composes with unchanged visual and collision envelopes (a pure material "
        "re-bind), then renders a frame per option and confirms consecutive options "
        "render measurably differently."
    ),
    expected_video=(
        "One still per appearance option (for example clean and weathered). The object "
        "keeps the same shape and footprint while its surface look changes."
    ),
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "settle_frames": 3,
        "camera_padding": 1.2,
        "envelope_tolerance_m": av.ENVELOPE_TOLERANCE_M,
        "max_captures": 4,
        # Consecutive appearance options must differ by at least this pixel fraction.
        "min_appearance_delta": 0.005,
    },
    max_duration=600,
)
async def test_appearance_variation(ctx):
    cfg = ctx.config
    tol = float(cfg["envelope_tolerance_m"])

    source = Usd.Stage.Open(str(ctx.asset_path))
    if not source or not source.GetDefaultPrim():
        ctx.fail("The source asset has no defaultPrim, so no appearance variant can be composed.")
        return

    entries = var.category_entries(source, av.CATEGORY_APPEARANCE)
    if not entries:
        ctx.fail(
            "No Appearance variation is declared on the asset.\n"
            "\n"
            "How to fix:\n"
            "- Author an Appearance variant set re-binding materials and record it under "
            "customLayerData.SimReady_Metadata.Variants.Appearance (AV.001).\n"
            "- Mark its impactClass as visual-only (AV.007)."
        )
        return

    root_layer = source.GetRootLayer()
    visual_baseline = av.envelope_size(av.visual_envelope(source))
    collision_baseline = av.envelope_size(av.collision_envelope(source))
    if visual_baseline is None:
        ctx.fail("The authored-default selection composes no visible geometry (AV.005).")
        return

    option_sizes = {}
    failures = []
    for variant_set_name, entry in entries:
        for option in var.entry_options(source, entry, variant_set_name):
            composed = var.compose_with_entry_selection(root_layer, entry, variant_set_name, option)
            visual = av.envelope_size(av.visual_envelope(composed))
            collision = av.envelope_size(av.collision_envelope(composed))
            key = f"{variant_set_name}={option}"
            if visual is None:
                failures.append(f"{key} composes no visible geometry")
                continue
            option_sizes[key] = [round(visual[i], 6) for i in range(3)]
            if not av.sizes_match(visual_baseline, visual, tol):
                failures.append(
                    f"{key} moved the visible geometry {var.axis_deltas(visual_baseline, visual)}; an appearance "
                    "variant must only re-bind materials (AV.005)"
                )
            if not av.sizes_match(collision_baseline, collision, tol):
                failures.append(
                    f"{key} changed the collision envelope {var.axis_deltas(collision_baseline, collision)}; a "
                    "visual-only appearance variant must not (AV.006/AV.007)"
                )

    ctx.add_metric("appearance_visual_baseline_size", [round(visual_baseline[i], 6) for i in range(3)])
    ctx.add_metric("appearance_option_sizes", option_sizes)

    if failures:
        ctx.fail(
            "One or more appearance variants broke the visual-only invariant:\n- "
            + "\n- ".join(failures)
            + "\n\nHow to fix:\n"
            "- Keep geometry out of the Appearance set; author only material bindings.\n"
            "- Confirm the impactClass is visual-only and no mass/collision is touched (AV.007)."
        )
        return

    ctx.scene.load_asset(ctx.asset_path, timeout=int(cfg["asset_load_timeout"]))
    ctx.set_settle_frames(int(cfg["settle_frames"]))
    stage = ctx.scene.stage
    budget = int(cfg["max_captures"])
    min_delta = float(cfg["min_appearance_delta"])
    frames = []
    for variant_set_name, entry in entries:
        for option in var.entry_options(source, entry, variant_set_name):
            if len(frames) >= budget:
                break
            if not var.runtime_select(stage, entry, variant_set_name, option):
                continue
            ctx.scene.auto_frame_camera(padding=float(cfg["camera_padding"]))
            await ctx.settle()
            frame = await ctx.capture_frame(label=f"appearance_{variant_set_name}_{option}")
            frames.append((f"{variant_set_name}={option}", frame))

    deltas = {}
    for (prev_key, prev_frame), (key, frame) in zip(frames, frames[1:]):
        delta = ctx.compare_images(prev_frame, frame, threshold=0.02).different_ratio
        deltas[f"{prev_key} -> {key}"] = round(delta, 6)
    ctx.add_metric("appearance_render_deltas", deltas)

    unchanged = [pair for pair, delta in deltas.items() if delta < min_delta]
    if unchanged:
        ctx.fail(
            "Consecutive appearance options rendered (near-)identically, so the look did "
            "not actually change:\n- " + "\n- ".join(unchanged) + "\n\nHow to fix:\n"
            "- Confirm each option binds a visibly different material.\n"
            "- Confirm the render path shows materials (RTX Real-Time or Path-Traced)."
        )
        return

    ctx.log("All %d appearance option(s) re-bound materials visual-only and rendered distinctly." % len(option_sizes))

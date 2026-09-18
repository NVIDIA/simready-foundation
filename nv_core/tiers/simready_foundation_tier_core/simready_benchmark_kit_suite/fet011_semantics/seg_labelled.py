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
"""FET011 Semantic Labels: the asset segments in the RTX AOV (SL.001).

WHAT: The renderer honours the asset's semantic labels. The offline validator can tell you a
      label is well formed; only a render tells you anything reads it.

HOW:  Frame the asset, attach a semantic-segmentation annotator to the viewport's render
      product, step the orchestrator once, and measure how much of the frame is segmented.

WHY:  Labels are inherited, so a single label on the asset's root should segment every mesh
      beneath it. A populated buffer is evidence that inheritance resolves in the renderer and
      not just in the validator.

Pairs with semantic_labels_seg_stripped, which measures the same asset with its semantics
removed. Together they show the segmentation comes from the labels. They are separate tests
because the orchestrator can only be stepped once per Kit session -- see _seg_common.
"""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.fet011_semantics import _seg_common as common


@test(
    features=[
        {"id": "FET_011_STANDARD", "version": ">=0.2.0"},
        {"id": "FET_011_RTX", "version": ">=0.1.0"},
    ],
    name="semantic_labels_seg_labelled",
    description=(
        "Renders the RTX semantic-segmentation AOV of the asset as authored and measures the "
        "fraction of the frame that resolves to a semantic label. Passes when segmented "
        "coverage reaches on_coverage_min, which shows the renderer reads the asset's "
        "SemanticsLabelsAPI labels."
    ),
    expected_video=(
        "A single still frame of the semantic-segmentation AOV: the asset appears as a solid "
        "block of one colour against a flat background, with no unsegmented holes in it."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(
        common.SHARED_CONFIG,
        # Fraction of the frame that must segment. Low on purpose: a small prop framed with
        # padding covers only a few percent, and the question is whether anything segments at
        # all, not whether the object is large.
        on_coverage_min=0.005,
    ),
    max_duration=600,
)
async def test_semantic_labels_seg_labelled(ctx):
    """Measure segmented coverage with the asset's labels as authored."""
    cfg = ctx.config

    ctx.step("Loading and framing asset")
    stage, target = await common.build_scene(ctx)
    if target is None:
        return

    await ctx.capture_frame(label="semantic_labels_rgb", role="normal")

    ctx.step("Rendering the segmentation AOV")
    segmentation = await common.read_segmentation(ctx, cfg["render_subframes"])
    coverage = common.segmented_coverage(segmentation)
    common.save_image(ctx, segmentation, "semantic_labels_semseg_labelled", role="summary")

    ctx.add_metric("semantic_labels_on_coverage", round(coverage, 6))
    minimum = float(cfg["on_coverage_min"])
    ctx.add_metric("semantic_labels_labelled_passed", 1 if coverage >= minimum else 0)

    if coverage < minimum:
        ctx.fail(
            "The segmentation AOV is nearly blank: %.4f of the frame is segmented, and at least "
            "%.4f is needed.\n"
            "\n"
            "How to fix:\n"
            "- Give every visible mesh a resolvable SemanticsLabelsAPI label, on the prim "
            "itself, on an ancestor, or through its bound material. One label on the "
            "defaultPrim covers the whole asset.\n"
            "- Apply the schema with at least one authored value. An empty label counts as no "
            "label.\n"
            "- Run on Isaac Sim 6.0 or later. Earlier versions do not resolve "
            "SemanticsLabelsAPI in the segmentation pass, so a correctly labelled asset still "
            "renders blank.\n"
            "- Confirm the asset is in frame; a mis-framed asset also renders blank." % (coverage, minimum)
        )
        return

    ctx.log("Segmented coverage %.4f with labels as authored" % coverage)

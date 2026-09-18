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
"""FET011 Semantic Labels: nothing else drives the segmentation (SL.001).

WHAT: The segmentation seen in semantic_labels_seg_labelled comes from the asset's own labels
      and from nothing else.

HOW:  Frame the asset exactly as the labelled test does, remove every semantics schema from the
      label sources SL.001 recognises, and render the AOV. The buffer should be blank.

WHY:  A populated AOV on its own does not prove the asset's labels caused it. Scene content,
      leftover semantics on a shared material, or a stray label elsewhere would produce one
      too. Measuring the same frame with the labels gone is what closes that gap.

The strip happens before the single orchestrator step, so no re-render is needed. That matters:
the orchestrator can only be stepped once per Kit session, which is also why this is a separate
test from the labelled one rather than a second pass inside it. See _seg_common.
"""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.fet011_semantics import _seg_common as common


@test(
    features=[
        {"id": "FET_011_STANDARD", "version": ">=0.2.0"},
        {"id": "FET_011_RTX", "version": ">=0.1.0"},
    ],
    name="semantic_labels_seg_stripped",
    description=(
        "Removes every SemanticsLabelsAPI and deprecated SemanticsAPI schema from the label "
        "sources SL.001 recognises, then renders the RTX semantic-segmentation AOV. Passes when "
        "segmented coverage falls below off_coverage_max, which shows the segmentation in the "
        "companion test came from the asset's labels rather than from anything else in frame."
    ),
    expected_video=(
        "A single still frame of the semantic-segmentation AOV with the asset's semantics "
        "removed: an empty frame of one flat background colour, with the asset invisible to the "
        "segmentation pass even though it is still in view."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(
        common.SHARED_CONFIG,
        # Fraction the stripped render may still segment. Not zero: AOV edge pixels and
        # denoiser fringing leave a few stray samples.
        off_coverage_max=0.002,
    ),
    max_duration=600,
)
async def test_semantic_labels_seg_stripped(ctx):
    """Measure segmented coverage after removing the asset's semantics."""
    cfg = ctx.config

    ctx.step("Loading and framing asset")
    stage, target = await common.build_scene(ctx)
    if target is None:
        return

    ctx.step("Stripping semantics")
    stripped = common.strip_semantics(stage, target)
    ctx.add_metric("semantic_labels_stripped_prims", stripped)
    if not stripped:
        ctx.skip(
            "The asset carries no semantics to strip, so there is nothing for this test to "
            "measure. semantic_labels_seg_labelled reports the same asset as unlabelled."
        )
        return
    ctx.log("Stripped semantics from %d prim(s)" % stripped)

    ctx.step("Rendering the segmentation AOV")
    segmentation = await common.read_segmentation(ctx, cfg["render_subframes"])
    coverage = common.segmented_coverage(segmentation)
    common.save_image(ctx, segmentation, "semantic_labels_semseg_stripped", role="summary")

    ctx.add_metric("semantic_labels_off_coverage", round(coverage, 6))
    allowed = float(cfg["off_coverage_max"])
    ctx.add_metric("semantic_labels_stripped_passed", 1 if coverage <= allowed else 0)

    if coverage > allowed:
        ctx.fail(
            "The segmentation AOV is still populated after every semantics schema was removed "
            "from %d prim(s): %.4f of the frame is segmented, and at most %.4f is allowed. "
            "Something other than the asset's own labels is driving the segmentation.\n"
            "\n"
            "How to fix:\n"
            "- Look for semantics on a material bound to the asset but authored outside its "
            "subtree; those survive a strip that only walks the asset.\n"
            "- Look for labels on scene content other than the asset.\n"
            "- Check for a deprecated SemanticsAPI block left behind alongside the modern "
            "labels, which some older authoring tools still write." % (stripped, coverage, allowed)
        )
        return

    ctx.log("Segmented coverage fell to %.4f after stripping %d prim(s)" % (coverage, stripped))

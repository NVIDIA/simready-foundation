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

WHAT: A sampled presence/absence control for the companion labelled AOV,
      within the sources reached by the current semantics-strip traversal.

HOW:  Frame the asset as the labelled test does, remove recognized schemas from
      visited label sources, and require the configured near-blank AOV threshold.
      Plain PrimRange does not traverse instance proxies; a zero-edits skip does
      not prove the complete composed asset carries no labels.

WHY:  A populated AOV on its own does not prove the asset's labels caused it. Scene content,
      leftover semantics on a shared material, or a stray label elsewhere would produce one
      too. Measuring the same frame with the labels gone is what closes that gap.

The strip happens before this test's single orchestrator step on its fresh stage.
The generic runner may reuse the engine process between tests; these registrations
do not promise a restart. See _seg_common for historical native lifecycle observations.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests._assessment import (
    _has_complete_asset_composition,
    not_applicable,
)
from simready.foundation.tier_core.runtime_tests.fet011_semantics import _seg_common as common


@test(
    features=[
        {"id": "FET011_SemanticLabels.0-2-0", "version": "*"},
        {"id": "FET011_SemanticLabels.RTX.0-1-0", "version": "*"},
    ],
    name="semantic_labels_seg_stripped",
    description=(
        "Removes SemanticsLabelsAPI and deprecated SemanticsAPI schemas from label "
        "sources reached by the current renderable-Gprim traversal, then renders "
        "the RTX semantic-segmentation AOV. Labelled instances inside the loaded asset "
        "are made editable in the session layer; source layers are unchanged. "
        "Unsupported external instance sources are execution errors; "
        "a zero-edits skip is not proof of absent labels. Passes when "
        "segmented coverage is at or below off_coverage_max. Together with the companion "
        "labelled test, this is a sampled label-driven presence/absence proxy, not proof "
        "of complete masks or correct class values."
    ),
    expected_video=(
        "A single still frame of the semantic-segmentation AOV after visited semantics "
        "sources are stripped: a nearly flat background, allowing residual changed pixels up to "
        "off_coverage_max even though the asset remains in view. Inspect that recorded "
        "ratio rather than requiring an exactly empty buffer."
    ),
    version="1.0.2",
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
    from simready.foundation.tier_core.runtime_tests._visual_readback import validate_visual_config

    validate_visual_config(ctx.config, fractions=("off_coverage_max",), positive_counts=("render_subframes",))
    cfg = ctx.config

    ctx.step("Loading and framing asset")
    stage, target = await common.build_scene(ctx)
    if target is None:
        return

    ctx.step("Stripping semantics")
    stripped = common.strip_semantics(stage, target)
    ctx.add_metric("semantic_labels_stripped_prims", stripped)
    if not stripped:
        reason = (
            "No applicable semantics were found in the inspected renderable label sources, "
            "so this stripping control has no behavior to measure. This does not establish "
            "asset-wide absence of semantic metadata."
        )
        if _has_complete_asset_composition(
            stage, target, ctx=ctx, inspection_includes_instance_proxies=True
        ) and common._has_complete_semantics_inspection(stage, target, ctx):
            ctx.add_metric("assessment_applicability", not_applicable("no_applicable_semantics", reason))
        ctx.skip(reason)
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

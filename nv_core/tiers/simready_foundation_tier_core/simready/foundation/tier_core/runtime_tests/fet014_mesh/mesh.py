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

"""FET014 Mesh Variant: every mesh option composes and is visual-only (AV.001-005,
AV.007).

WHAT: A ``MeshVariant`` variation swaps the visible render geometry of the asset
      (for example a crisp high-poly mesh versus a decimated low-poly one) while
      the object's footprint and its simulation-relevant data stay put. Mesh
      variants are declared ``visual-only``: switching one must not disturb
      collision or mass.

HOW:  1. Open the source asset and read its ``MeshVariant`` entries.
      2. For each option, recompose with only that option selected and confirm
         the visual envelope matches the authored default within tolerance.
      3. Confirm the collision envelope is unchanged too, proving the swap really
         was visual-only (AV.007 honesty of the ``visual-only`` impact class).
      4. Load the asset and capture a frame per option as rendered proof.

WHY:  FET_014 lets a pipeline pick a render mesh by budget without re-fitting the
      object: same size, same collision, same mass. A mesh variant that silently
      changed collision would quietly break physics for anyone trusting the label.
"""

from pxr import Usd
from simready.evaluate import test
from simready.foundation.tier_core import asset_variants as av
from simready.foundation.tier_core.runtime_tests.fet013_representation import (
    _variation as var,
)


@test(
    features=[{"id": "FET014_MeshVariant.0-1-0", "version": "*"}],
    name="mesh_variation",
    version="1.0.0",
    description=(
        "Recomposes the asset once per declared MeshVariant option and checks that "
        "each composes to renderable geometry whose visual AND collision envelopes "
        "match the authored default, confirming the swap is visual-only, then renders "
        "a frame per option."
    ),
    expected_video=(
        "One still per mesh option (for example high-poly and low-poly). The surface "
        "detail changes but the object keeps the same footprint in every frame."
    ),
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "settle_frames": 3,
        "camera_padding": 1.2,
        "envelope_tolerance_m": av.ENVELOPE_TOLERANCE_M,
        "max_captures": 4,
    },
    max_duration=600,
)
async def test_mesh_variation(ctx):
    cfg = ctx.config
    tol = float(cfg["envelope_tolerance_m"])

    source = Usd.Stage.Open(str(ctx.asset_path))
    if not source or not source.GetDefaultPrim():
        ctx.fail("The source asset has no defaultPrim, so no mesh variant can be composed.")
        return

    entries = var.category_entries(source, av.CATEGORY_MESH_VARIANT)
    if not entries:
        ctx.fail(
            "No MeshVariant variation is declared on the asset.\n"
            "\n"
            "How to fix:\n"
            "- Author a MeshVariant variant set swapping the render mesh and record it "
            "under customLayerData.SimReady_Metadata.Variants.MeshVariant (AV.001).\n"
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
                failures.append(f"{key} visual envelope {var.axis_deltas(visual_baseline, visual)} exceeds {tol} m")
            if not av.sizes_match(collision_baseline, collision, tol):
                failures.append(
                    f"{key} changed the collision envelope {var.axis_deltas(collision_baseline, collision)}; "
                    "a visual-only mesh variant must not (AV.006/AV.007)"
                )

    ctx.add_metric("mesh_visual_baseline_size", [round(visual_baseline[i], 6) for i in range(3)])
    ctx.add_metric("mesh_option_sizes", option_sizes)

    if failures:
        ctx.fail(
            "One or more mesh variants broke the visual-only invariant:\n- "
            + "\n- ".join(failures)
            + "\n\nHow to fix:\n"
            "- Re-author options so the visible bounds match within tolerance (AV.005).\n"
            "- Keep collision geometry out of the MeshVariant set so it stays visual-only."
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
            await ctx.capture_frame(label=f"mesh_{variant_set_name}_{option}")
            captured += 1

    ctx.log("All %d mesh variant option(s) composed visual-only and held both envelopes." % len(option_sizes))

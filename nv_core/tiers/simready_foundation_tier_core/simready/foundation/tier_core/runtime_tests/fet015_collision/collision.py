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

"""FET015 Collision Variant: every collision option composes, is simulable, and
holds the collision envelope (AV.001-006).

WHAT: A ``Collision`` variation swaps the collision approximation of the asset
      (for example a convex hull versus a tighter convex decomposition) to trade
      simulation fidelity against cost. Collision variants are
      ``simulation-affecting`` -- that is their whole point -- but they must keep
      the collision envelope so the object occupies the same simulated footprint,
      and the visible render geometry must not move.

HOW:  1. Open the source asset and read its ``Collision`` entries.
      2. For each option, recompose with only that option selected and confirm
         the collision envelope matches the authored default within tolerance
         while the visual envelope is unchanged.
      3. Load the asset with physics and settle it, proving each collision option
         simulates without exploding, and capture a frame per option.

WHY:  FET_015 lets a pipeline pick a collider by cost without re-fitting the
      object. A collision variant that resized the collider or shifted the render
      mesh would silently change contacts and placement for every physics
      consumer.
"""

from pxr import Usd
from simready.evaluate import test
from simready.foundation.tier_core import asset_variants as av
from simready.foundation.tier_core.runtime_tests.fet013_representation import (
    _variation as var,
)


@test(
    features=[{"id": "FET015_CollisionVariant.0-1-0", "version": "*"}],
    name="collision_variation",
    version="1.0.0",
    description=(
        "Recomposes the asset once per declared Collision option and checks that each "
        "composes with a collision envelope matching the authored default and an "
        "unchanged visual envelope, then loads the asset with physics, settles it, and "
        "renders a frame per option."
    ),
    expected_video=(
        "One still per collision option after a brief physics settle. The collider "
        "approximation differs but the object rests in the same place with the same "
        "visible footprint."
    ),
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "settle_frames": 3,
        # Settle cycles to advance the simulation before each capture.
        "settle_cycles": 3,
        "camera_padding": 1.2,
        "envelope_tolerance_m": av.ENVELOPE_TOLERANCE_M,
        "max_captures": 4,
    },
    max_duration=600,
)
async def test_collision_variation(ctx):
    cfg = ctx.config
    tol = float(cfg["envelope_tolerance_m"])

    source = Usd.Stage.Open(str(ctx.asset_path))
    if not source or not source.GetDefaultPrim():
        ctx.fail("The source asset has no defaultPrim, so no collision variant can be composed.")
        return

    entries = var.category_entries(source, av.CATEGORY_COLLISION)
    if not entries:
        ctx.fail(
            "No Collision variation is declared on the asset.\n"
            "\n"
            "How to fix:\n"
            "- Author a Collision variant set swapping the collider approximation and "
            "record it under customLayerData.SimReady_Metadata.Variants.Collision (AV.001).\n"
            "- Mark its impactClass as simulation-affecting (AV.007)."
        )
        return

    root_layer = source.GetRootLayer()
    collision_baseline = av.envelope_size(av.collision_envelope(source))
    visual_baseline = av.envelope_size(av.visual_envelope(source))
    if collision_baseline is None:
        ctx.fail(
            "The authored-default selection composes no collision geometry (AV.006), so "
            "the collision envelope cannot be established."
        )
        return

    option_sizes = {}
    failures = []
    for variant_set_name, entry in entries:
        for option in var.entry_options(source, entry, variant_set_name):
            composed = var.compose_with_entry_selection(root_layer, entry, variant_set_name, option)
            collision = av.envelope_size(av.collision_envelope(composed))
            visual = av.envelope_size(av.visual_envelope(composed))
            key = f"{variant_set_name}={option}"
            if collision is None:
                failures.append(f"{key} composes no collision geometry")
                continue
            option_sizes[key] = [round(collision[i], 6) for i in range(3)]
            if not av.sizes_match(collision_baseline, collision, tol):
                failures.append(
                    f"{key} collision envelope {var.axis_deltas(collision_baseline, collision)} exceeds {tol} m"
                )
            if not av.sizes_match(visual_baseline, visual, tol):
                failures.append(
                    f"{key} moved the visible geometry {var.axis_deltas(visual_baseline, visual)}; a collision "
                    "variant must leave the render mesh in place (AV.005)"
                )

    ctx.add_metric("collision_baseline_size", [round(collision_baseline[i], 6) for i in range(3)])
    ctx.add_metric("collision_option_sizes", option_sizes)

    if failures:
        ctx.fail(
            "One or more collision variants broke the collision-envelope invariant:\n- "
            + "\n- ".join(failures)
            + "\n\nHow to fix:\n"
            "- Re-author colliders so the collision bounds match within tolerance (AV.006).\n"
            "- Keep render geometry out of the Collision set so the visible mesh stays put."
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
            await ctx.settle(count=int(cfg["settle_cycles"]))
            await ctx.capture_frame(label=f"collision_{variant_set_name}_{option}")
            captured += 1

    ctx.log("All %d collision option(s) composed, simulated, and held the collision envelope." % len(option_sizes))

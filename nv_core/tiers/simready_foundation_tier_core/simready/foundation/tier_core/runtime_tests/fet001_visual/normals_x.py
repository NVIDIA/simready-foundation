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
"""FET001 Normal direction validation -- X-axis rotation (VG.028).

WHAT: Verifies that mesh normals point outward by detecting dark surfaces
      under uniform dome lighting.

HOW:  1. Load the asset in a WHITE room with dome-only lighting (2000
         intensity), diagnostic material, and double-sided rendering ON.
      2. Settle (let geometry load) BEFORE framing the camera -- the bbox
         computation requires loaded geometry to produce correct results.
      3. Compare a framed diagnostic capture with an asset-hidden control.
         If no asset-attributable orange pixels remain, FAIL immediately.
      4. Rotate the asset 360 degrees around X-axis in 8 steps.
      5. Per frame: mask object pixels (non-black on black background),
         count how many object pixels are dark (luminance < threshold).
      6. If too many frames have excessive dark pixels, normals are inverted.

WHY:  VG.028 requires normals to be valid and point outward. Under uniform
      dome lighting, outward-facing normals receive light from the full
      hemisphere and appear evenly lit. Inverted normals face AWAY from
      the dome hemisphere and receive zero light contribution -> near-black.
      Double-sided rendering ensures all faces are rendered (even those with
      wrong winding), so inverted normals show as dark patches rather than
      invisible holes.

      X-axis rotation exposes top/bottom cap faces.

FALSE POSITIVE AVOIDANCE:
  - Visibility pre-check prevents false passes on empty frames (broken
    load, wrong camera framing).
  - Requires min_problem_frames (default 2) problem frames to fail, not
    just 1. A single dark frame at an extreme rotation angle is likely
    interior geometry (hollow objects like bottles, cups, pipes) where
    inward-facing normals are CORRECT by design.
  - Dark threshold (15% luminance) is low enough to catch genuinely
    inverted normals but high enough to ignore ambient occlusion shadows.
  - Dome-only lighting (no directional) ensures uniform illumination --
    directional light would create shadows that look like dark normals.
  - White room + ctx.compare_object_pixels(): reliably identifies ALL object
    pixels (luma < 0.85 on white background). A black room caused false
    positives because dim-but-valid object pixels blended with the background.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.fet001_visual._asset_visibility import ensure_asset_visible
from simready.foundation.tier_core.runtime_tests._visual_diagnostics import encode_visual_video
from simready.foundation.tier_core.runtime_tests._visual_readback import qualified_object_ratios


@test(
    features=[
        {"id": "FET001_MinimalPlaceableVisual.0-1-0", "version": "*"},
        {"id": "FET001_MinimalPlaceableVisual.1-0-0", "version": "*"},
        {"id": "FET001_MinimalPlaceableVisual.1-0-1", "version": "*"},
    ],
    name="normals_x",
    description=(
        "Rotates the asset around the X axis under uniform dome lighting "
        "(2000 intensity) with double-sided rendering ON and a diagnostic "
        "orange matte material; verifies the visible orange brightness is "
        "uniform across the silhouette. Catches inverted mesh normals — "
        "they show as dark patches on the otherwise uniformly-lit surface."
    ),
    expected_video=(
        "The asset rotating around its X axis (pitch) lit uniformly from "
        "all sides. The orange diagnostic surface should be evenly bright "
        "across every frame. Dark patches that follow the surface as it "
        "rotates indicate inverted normals at those locations."
    ),
    version="2.0.4",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "steps": 8,
        "settle_frames": 5,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
        "dark_threshold": 0.15,
        "max_problem_ratio": 0.50,
        "min_problem_frames": 2,
    },
    enabled=False,
)
async def test_normals_x(ctx):
    """Normal direction validation -- X-axis rotation."""
    from simready.foundation.tier_core.runtime_tests._visual_readback import validate_visual_config

    validate_visual_config(
        ctx.config,
        fractions=("dark_threshold", "max_problem_ratio"),
        positive_counts=("steps", "min_problem_frames"),
        count_limits=(("min_problem_frames", "steps"),),
    )
    steps = int(ctx.config["steps"])
    angle_per_step = 360.0 / float(max(1, steps))

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    # White room: object mask = pixels darker than white background.
    # Black room caused false positives because dim-but-valid object pixels
    # were below the mask threshold, distorting the dark-pixel ratio.
    room.set_color(1, 1, 1)
    room.hide_ground()

    ctx.scene.lighting.add_dome(intensity=2000.0)
    ctx.scene.apply_diagnostic_material(color=(0.9, 0.2, 0.0), roughness=1.0, metallic=0.0)
    ctx.scene.set_double_sided(True)
    if not await ensure_asset_visible(ctx, padding=ctx.config["camera_padding"]):
        ctx.fail(
            "Object not sufficiently visible after multiple attempts. Fewer than "
            "100 asset-attributable diagnostic orange pixels were measured.\n"
            "\n"
            "How to fix:\n"
            "- Check that the asset has renderable Mesh geometry.\n"
            "- Verify the USD file loads correctly (no broken references).\n"
            "- Check asset bbox computation for invisible helper geometry."
        )
        return

    # --- Capture X-axis rotation ---
    ctx.step("Capturing X-axis rotation for normal validation")
    frames = []
    for i in range(steps):
        ctx.scene.rotate_asset("X", i * angle_per_step)
        await ctx.settle()
        ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
        await ctx.settle()
        frames.append(await ctx.capture_frame(label="normals_x"))
    ctx.scene.reset_asset_transform()

    # --- Analysis ---
    ctx.step("Analyzing normal direction (X-axis)")
    dark_threshold = float(ctx.config["dark_threshold"])
    max_problem = float(ctx.config["max_problem_ratio"])
    min_problems = int(ctx.config["min_problem_frames"])

    problem_count = 0
    worst_dark_ratio = 0.0
    worst_idx = 0
    dark_ratios, frame_indices = qualified_object_ratios(
        ctx,
        frames,
        frames,
        prefix="normals_x",
        ratio_name="dark_ratio",
        kind="frames",
        background_color=(1, 1, 1),
        dark_threshold=dark_threshold,
    )
    if len(dark_ratios) < min_problems:
        raise RuntimeError(
            "Required normals_x coverage is incomplete: at least min_problem_frames "
            "sampled frames must each have >=100 object pixels; unmeasured views cannot establish a PASS"
        )

    for i, dark_ratio in zip(frame_indices, dark_ratios, strict=True):
        if dark_ratio > max_problem:
            problem_count += 1
        if dark_ratio > worst_dark_ratio:
            worst_dark_ratio = dark_ratio
            worst_idx = i

    avg_dark = sum(dark_ratios) / len(dark_ratios)
    passed = problem_count < min_problems

    # --- Diagnostics ---
    if not passed:
        encode_visual_video(
            ctx, [frames[worst_idx]], fps=1, delete_frames=False, label="normals_x_worst_frame", role="worst"
        )

    encode_visual_video(ctx, frames, fps=2, label="normals_x_rotation", role="summary")

    # --- Metrics ---
    ctx.add_metric("normals_x_avg_dark", round(avg_dark, 6))
    ctx.add_metric("normals_x_max_dark", round(worst_dark_ratio, 6))
    ctx.add_metric("normals_x_problem_frames", problem_count)
    ctx.add_metric("normals_x_passed", 1 if passed else 0)

    if not passed:
        ctx.fail(
            "Normal direction check FAILED (X-axis): %d frames show >%.0f%% "
            "dark object pixels.\n"
            "Worst: %.0f deg with %.1f%% dark pixels.\n"
            "\n"
            "Under uniform dome lighting, outward-facing normals produce even "
            "illumination. Dark areas indicate inverted normals.\n"
            "\n"
            "How to fix:\n"
            "- Recalculate normals to face outward in your DCC tool.\n"
            "- Flip inverted faces (select dark faces, flip normals).\n"
            "- Ensure normals are not zero-length or NaN (VG.028).\n"
            "- X-axis rotation exposes top/bottom faces."
            % (problem_count, max_problem * 100, worst_idx * angle_per_step, worst_dark_ratio * 100)
        )
        return

    ctx.log("Normal X PASSED: avg dark=%.1f%%, max dark=%.1f%%" % (avg_dark * 100, worst_dark_ratio * 100))

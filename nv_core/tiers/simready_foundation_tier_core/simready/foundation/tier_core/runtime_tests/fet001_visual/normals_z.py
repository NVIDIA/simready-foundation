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
"""FET001 Normal direction validation -- Z-axis rotation (VG.028).

WHAT: Verifies that mesh normals point outward by detecting dark surfaces
      under uniform dome lighting.

HOW:  Same as normals_x but rotates around the Z-axis. Z-axis rotation
      covers side-facing surfaces. See normals_x.py for the full VG.028
      rationale.
      1. Settle (let geometry load) BEFORE framing the camera -- the bbox
         computation requires loaded geometry to produce correct results.
      2. Compare a framed diagnostic capture with an asset-hidden control.
         If no asset-attributable orange pixels remain, FAIL immediately.

WHY:  Z-axis rotation exposes side-facing geometry that X-axis rotation
      keeps edge-on. Together normals_x + normals_z + normals_xz cover all
      face orientations.

FALSE POSITIVE AVOIDANCE:
  - Visibility pre-check prevents false passes on empty frames (broken
    load, wrong camera framing).
  - Same safeguards as normals_x: min_problem_frames threshold, dome-only
    lighting, white room. ctx.compare_object_pixels() handles masking.
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
    name="normals_z",
    description=(
        "Rotates the asset around the Z axis (yaw) under uniform dome "
        "lighting (2000 intensity) with double-sided rendering ON and a "
        "diagnostic orange matte material; verifies brightness is uniform "
        "across the silhouette. Catches inverted normals on faces whose "
        "normals lie in the XY plane."
    ),
    expected_video=(
        "The asset spinning around its vertical Z axis (yaw), lit uniformly. "
        "Orange diagnostic surface is evenly bright at every frame. Dark "
        "patches on side-facing surfaces indicate inverted normals — common "
        "after mirror operations during export."
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
async def test_normals_z(ctx):
    """Normal direction validation -- Z-axis rotation."""
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

    # --- Capture Z-axis rotation ---
    ctx.step("Capturing Z-axis rotation for normal validation")
    frames = []
    for i in range(steps):
        ctx.scene.rotate_asset("Z", i * angle_per_step)
        await ctx.settle()
        ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
        await ctx.settle()
        frames.append(await ctx.capture_frame(label="normals_z"))
    ctx.scene.reset_asset_transform()

    # --- Analysis ---
    ctx.step("Analyzing normal direction (Z-axis)")
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
        prefix="normals_z",
        ratio_name="dark_ratio",
        kind="frames",
        background_color=(1, 1, 1),
        dark_threshold=dark_threshold,
    )
    if len(dark_ratios) < min_problems:
        raise RuntimeError(
            "Required normals_z coverage is incomplete: at least min_problem_frames "
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
            ctx, [frames[worst_idx]], fps=1, delete_frames=False, label="normals_z_worst_frame", role="worst"
        )

    encode_visual_video(ctx, frames, fps=2, label="normals_z_rotation", role="summary")

    # --- Metrics ---
    ctx.add_metric("normals_z_avg_dark", round(avg_dark, 6))
    ctx.add_metric("normals_z_max_dark", round(worst_dark_ratio, 6))
    ctx.add_metric("normals_z_problem_frames", problem_count)
    ctx.add_metric("normals_z_passed", 1 if passed else 0)

    if not passed:
        ctx.fail(
            "Normal direction check FAILED (Z-axis): %d frames show >%.0f%% "
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
            "- Z-axis rotation covers side-facing surfaces."
            % (problem_count, max_problem * 100, worst_idx * angle_per_step, worst_dark_ratio * 100)
        )
        return

    ctx.log("Normal Z PASSED: avg dark=%.1f%%, max dark=%.1f%%" % (avg_dark * 100, worst_dark_ratio * 100))

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
"""FET001 Light Response check (VG.027 -- normals exist).

WHAT: Verifies that the asset's mesh normals exist and produce correct
      shading when a directional light rotates around the object.

HOW:  1. Load the asset in a black room with directional + dome lighting
         and diagnostic material (orange, matte).
      2. Settle (let geometry load) BEFORE framing the camera -- the bbox
         computation requires loaded geometry to produce correct results.
      3. Capture a check frame and verify the diagnostic material (orange)
         is visible. If no orange pixels are detected, FAIL immediately
         (object not on screen).
      4. Rotate the directional light 360 degrees around Z-axis in 30 steps.
      5. For each frame, ctx.compare_object_pixels() masks object pixels
         (luminance > threshold on black background) and measures luminance.
      6. Two-stage check:
         a) Object exists: ctx.compare_object_pixels() blank detection --
            enough non-black pixels across frames.
         b) Light response: ctx.compare_object_pixels() consecutive pair
            comparison -- object pixels show luminance variation as light
            moves.

WHY:  VG.027 requires all non-subdivided meshes to have normals. Without
      normals, the renderer cannot compute correct shading -- the surface
      appears flat/uniform regardless of light direction. This test catches
      missing normals by verifying that shading actually varies with light.

FALSE POSITIVE AVOIDANCE:
  - Visibility pre-check prevents false passes on empty frames (broken
    load, wrong camera framing).
  - Diagnostic material eliminates material-related shading issues (the
    orange matte surface responds predictably to directional light).
  - Black room makes object masking trivial (non-black = object).
  - Dome light (150 intensity) provides baseline illumination so the object
    is never completely dark, even when the directional light is behind it.
  - Per-pair threshold (5% of object pixels changed) is lenient enough to
    handle small objects with few pixels.
  - Blank frame detection uses very low luminance threshold (< 5%) to
    account for the black room absorbing most ambient light.
  - 30 steps provides 29 consecutive pairs for statistical confidence.
  - ctx.compare_object_pixels() with background_color=(0,0,0) masks to
    object-only pixels on the black background. Background noise from RTX
    accumulation is excluded from the variation analysis.
"""
from simready_benchmark.core.decorator import test


@test(
    features=[{"id": "FET001_BASE_NEUTRAL", "version": ">=0.1.0"}],
    name="light_response",
    description=(
        "Renders the asset in a black room with a rotating directional light "
        "and weak dome fill, using a diagnostic orange matte material; "
        "verifies the captured frames show shading variation that follows "
        "the light's position. Validates that mesh normals exist and "
        "correctly modulate Lambert shading — a uniformly-lit surface in "
        "every frame indicates missing or constant normals."
    ),
    expected_video=(
        "The asset stationary at center, with a directional light orbiting "
        "around it. The orange diagnostic surface should brighten on the "
        "side facing the light and darken on the lee side, with the bright "
        "and dark regions tracking the light's position smoothly across "
        "frames. A surface with uniform brightness throughout means the "
        "normals aren't being read by the shader."
    ),
    version="2.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "steps": 30,
        "settle_frames": 5,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
        "max_blank_ratio": 0.50,
        "min_variation_ratio": 0.10,
        "pair_change_threshold": 0.03,
        "pair_change_pixel_ratio": 0.05,
    },
)
async def test_light_response(ctx):
    """Light response check -- normals must produce correct shading."""
    steps = ctx.config["steps"]
    angle_per_step = 360.0 / float(max(1, steps))

    # --- Scene setup (no physics -- visual only) ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(0, 0, 0)
    room.hide_ground()

    dir_light = ctx.scene.lighting.add_directional(direction=(45.0, 0.0, 90.0), intensity=3000.0)
    ctx.scene.lighting.add_dome(intensity=150.0)

    ctx.scene.apply_diagnostic_material(color=(0.9, 0.2, 0.0), roughness=1.0, metallic=0.0)
    if not await ctx.ensure_object_framed(diagnostic_color=(0.9, 0.2, 0.0), padding=ctx.config["camera_padding"]):
        ctx.fail(
            "Object not visible after multiple attempts. The diagnostic "
            "material (orange) was not detected.\n"
            "\n"
            "How to fix:\n"
            "- Check that the asset has renderable Mesh geometry.\n"
            "- Verify the USD file loads correctly (no broken references).\n"
            "- Check asset bbox computation for invisible helper geometry."
        )
        return

    # --- Rotate light and capture ---
    ctx.step("Rotating directional light (Z-axis, %d steps)" % steps)
    frames = []
    for i in range(steps):
        dir_light.set_direction(45.0, 0.0, 90.0 + i * angle_per_step)
        await ctx.settle()
        frames.append(await ctx.capture_frame(label="light_response"))

    # --- Analysis ---
    ctx.step("Analyzing light response")
    max_blank = float(ctx.config["max_blank_ratio"])
    min_variation = float(ctx.config["min_variation_ratio"])
    pair_pixel_ratio = float(ctx.config["pair_change_pixel_ratio"])
    pair_thresh = float(ctx.config["pair_change_threshold"])

    # Stage 1: Object exists -- enough non-black pixels per frame
    blank_count = 0
    for fpath in frames:
        result = ctx.compare_object_pixels(fpath, fpath, background_color=(0, 0, 0))
        if result.object_pixel_count < 100:
            blank_count += 1

    blank_ratio = blank_count / float(max(len(frames), 1))

    # Stage 2: Light response -- consecutive frames show variation
    different_count = 0
    pair_diffs = []
    total_pairs = max(len(frames) - 1, 1)

    for i in range(len(frames) - 1):
        result = ctx.compare_object_pixels(
            frames[i], frames[i + 1], background_color=(0, 0, 0), pixel_threshold=pair_thresh
        )
        pair_diffs.append(result.changed_ratio)
        if result.changed_ratio > pair_pixel_ratio:
            different_count += 1

    variation_ratio = different_count / float(total_pairs)

    # --- Diagnostics ---
    passed = True
    fail_reasons = []

    if blank_ratio > max_blank:
        passed = False
        fail_reasons.append(
            "Rendering appears broken: %.0f%% of frames have too few "
            "object pixels (%d/%d blank, threshold %.0f%%)."
            % (blank_ratio * 100, blank_count, len(frames), max_blank * 100)
        )

    if variation_ratio <= min_variation:
        passed = False
        fail_reasons.append(
            "No light response detected: %.1f%% of consecutive pairs show "
            "variation (need >%.0f%%). Shading does not change as the "
            "directional light rotates." % (variation_ratio * 100, min_variation * 100)
        )

    # --- Failure video: worst pair (least variation) ---
    if not passed and pair_diffs:
        worst_idx = pair_diffs.index(min(pair_diffs))
        if worst_idx < len(frames) - 1:
            ctx.encode_video(
                [frames[worst_idx], frames[worst_idx + 1]],
                fps=1,
                delete_frames=False,
                label="light_response_worst_pair",
                role="worst",
            )

    # --- Always encode rotation video ---
    ctx.encode_video(frames, fps=2, label="light_response_light_rotation", role="summary")

    # --- Metrics ---
    ctx.add_metric("light_response_variation_ratio", round(variation_ratio, 6))
    ctx.add_metric("light_response_blank_ratio", round(blank_ratio, 6))
    ctx.add_metric("light_response_blank_frames", blank_count)
    ctx.add_metric("light_response_total_frames", len(frames))
    ctx.add_metric("light_response_total_pairs", len(pair_diffs))
    ctx.add_metric("light_response_different_pairs", different_count)
    ctx.add_metric("light_response_passed", 1 if passed else 0)
    if pair_diffs:
        ctx.add_metric("light_response_max_pair_change", round(max(pair_diffs), 6))
        ctx.add_metric("light_response_min_pair_change", round(min(pair_diffs), 6))

    # --- Pass/Fail ---
    if not passed:
        fix_hints = []
        if blank_ratio > max_blank:
            fix_hints.append(
                "Ensure the asset has visible geometry with at least one "
                "Mesh prim. Check that meshes are not hidden "
                "(visibility=invisible) and the USD file loads correctly."
            )
        if variation_ratio <= min_variation:
            fix_hints.append(
                "Ensure all meshes have authored normals (VG.027). "
                "Normals define how surfaces respond to directional light. "
                "Missing normals cause flat/uniform shading regardless of "
                "light direction. In your DCC tool, recalculate normals "
                "from the mesh surface."
            )
        ctx.fail(
            "Light response check FAILED.\n" + "\n".join(fail_reasons) + "\n\nHow to fix:\n- " + "\n- ".join(fix_hints)
        )
        return

    ctx.log("Light response PASSED: %.1f%% variation, %.0f%% blank" % (variation_ratio * 100, blank_ratio * 100))

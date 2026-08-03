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
"""FET001 Presence / Visibility check (VG.002 -- valid extent).

WHAT: Verifies the asset produces visible pixels when loaded and rendered.
      This is the most basic visual test -- if nothing renders, all other
      visual tests are meaningless.

HOW:  1. Load the asset in a white room with dome lighting and diagnostic
         material (orange, matte).
      2. Settle (let geometry load) BEFORE framing the camera -- the bbox
         computation requires loaded geometry to produce correct results.
      3. Capture a check frame and verify the diagnostic material (orange)
         is visible. If no orange pixels are detected, FAIL immediately
         (object not on screen).
      4. Capture a background frame with the asset hidden.
      5. Capture a visible frame with the asset shown.
      6. Compare the two frames pixel-by-pixel. If the difference exceeds
         the threshold (default 1%), the asset has visible geometry.

WHY:  VG.002 requires boundable geometry with valid extent. If the asset
      has no renderable meshes, broken references, or all-invisible prims,
      the visible frame will be identical to the background -> test fails.

FALSE POSITIVE AVOIDANCE:
  - Visibility pre-check prevents false passes on empty frames (broken
    load, wrong camera framing).
  - Uses diagnostic material to eliminate material-dependent rendering
    issues (transparent materials, broken textures).
  - White room ensures the background is uniform and predictable.
  - Dome-only lighting (no directional) avoids uneven wall illumination.
  - Very low threshold (1%) accommodates small objects that occupy few pixels.
  - If the asset has only non-mesh geometry (curves, points), it may fail
    this test even though geometry exists. This is intentional: FET001
    requires Mesh representation (VG.MESH.001).
"""
from simready_benchmark.core.decorator import test


@test(
    features=[{"id": "FET001_BASE_NEUTRAL", "version": ">=0.1.0"}],
    name="presence",
    description=(
        "Renders the asset under uniform dome lighting with a diagnostic "
        "orange matte material; verifies that any visible pixels of the "
        "diagnostic color appear in the captured frame. Validates the "
        "asset has at least one renderable surface (no zero-extent geometry, "
        "no broken material binding, no all-instanceable hidden mesh)."
    ),
    expected_video=(
        "A single still frame: the asset rendered as a uniform orange shape "
        "against a white background. The asset should be clearly visible and "
        "fill a recognizable portion of the frame. A blank or near-blank "
        "frame indicates failure (no surfaces rendering)."
    ),
    version="2.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "settle_frames": 5,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
        "min_diff_ratio": 0.01,
    },
)
async def test_presence(ctx):
    """Presence/visibility check -- visible geometry must exist."""
    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(1, 1, 1)
    room.hide_ground()

    # Dome-only lighting -- directional light would illuminate the black walls
    ctx.scene.lighting.add_dome(intensity=1000.0)
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

    # --- Capture hidden (background reference) ---
    # allow_blank=True: with the asset hidden this frame is SUPPOSED to be the
    # empty background; the framework's blank/washed-frame retry must not fight
    # it (an empty frame here is the expected baseline, not a render failure).
    ctx.step("Capturing background reference (asset hidden)")
    ctx.scene.hide_asset()
    await ctx.settle()
    frame_hidden = await ctx.capture_frame(label="presence_hidden", allow_blank=True)

    # --- Capture visible ---
    ctx.scene.show_asset()
    await ctx.settle()
    frame_visible = await ctx.capture_frame(label="presence_visible")

    # --- Compare ---
    ctx.step("Comparing hidden vs visible frames")
    result = ctx.compare_images(frame_hidden, frame_visible, threshold=0.02)
    diff_ratio = result.different_ratio
    min_diff = ctx.config["min_diff_ratio"]

    ctx.add_metric("presence_diff_ratio", round(diff_ratio, 6))
    ctx.add_metric("presence_passed", 1 if diff_ratio >= min_diff else 0)

    if diff_ratio < min_diff:
        ctx.fail(
            "Presence check FAILED: visibility toggle produced only "
            "%.2f%% difference (need >=%.0f%%).\n"
            "\n"
            "How to fix:\n"
            "- Ensure the asset has at least one visible Mesh prim.\n"
            "- Check that meshes are not hidden (visibility=invisible).\n"
            "- Verify the USD file loads correctly (no broken references).\n"
            "- Ensure geometry has valid extent attributes (VG.002)." % (diff_ratio * 100, min_diff * 100)
        )
        return

    ctx.log("Presence PASSED: toggle produced %.2f%% difference" % (diff_ratio * 100))

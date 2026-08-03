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
"""FET001 Backface culling / winding validation -- X-axis rotation (VG.029).

WHAT: Verifies that mesh face winding order is consistent so that backface
      culling does not remove visible surfaces.

HOW:  1. Load the asset in a black room with dome lighting and diagnostic
         material (orange, matte).
      2. Settle (let geometry load) BEFORE framing the camera -- the bbox
         computation requires loaded geometry to produce correct results.
      3. Capture a check frame and verify the diagnostic material (orange)
         is visible. If no orange pixels are detected, FAIL immediately
         (object not on screen).
      4. For each of 8 rotation steps (45 deg) around the X-axis:
         a) Set doubleSided=True and singleSided=False (culling OFF) ->
            capture reference frame.
         b) Set doubleSided=False and singleSided=True (culling ON) ->
            capture test frame. The Omniverse renderer uses singleSided
            as the primary face culling authority.
      5. Compare each pair: if culling ON looks different from culling OFF,
         some faces disappeared -- their winding is incorrect.

WHY:  VG.029 requires correct winding order. When backface culling is
      enabled, faces whose vertices wind clockwise (instead of counter-
      clockwise) are culled and become invisible. This test detects such
      faces by comparing renders with and without culling.

      X-axis rotation specifically exposes top/bottom cap faces that Z-axis
      rotation keeps edge-on. Together culling_x + culling_z + culling_xz
      cover all orientations.

FALSE POSITIVE AVOIDANCE:
  - Visibility pre-check prevents false passes on empty frames (broken
    load, wrong camera framing).
  - Single-loop alternating capture: both frames of each pair are captured
    milliseconds apart at the same rotation angle, same camera, same render
    state. No temporal drift between passes.
  - Per-step camera snap keeps the asset well-framed at every angle.
  - White room + ctx.compare_object_pixels(): only object pixels are compared
    between culling-off and culling-on frames. Background render noise is
    completely ignored, eliminating false positives from RTX accumulation
    differences.
  - Diagnostic material ensures uniform appearance (no texture-dependent
    culling artifacts).
  - Threshold (10% max pair diff) is per-pair, not aggregate. A single
    bad angle fails the test, catching localized winding issues.
  - Camera re-framing per step means the asset fills the frame at all
    angles, maximizing pixel-level sensitivity.
"""
from simready_benchmark.core.decorator import test


@test(
    features=[{"id": "FET001_BASE_NEUTRAL", "version": ">=0.1.0"}],
    name="culling_x",
    description=(
        "Rotates the asset around the X axis under dome lighting with a "
        "diagnostic orange matte material; verifies the orange color is "
        "continuously visible from every angle. Validates that mesh face "
        "winding order is consistent — backface culling should never remove "
        "surfaces that ought to be visible."
    ),
    expected_video=(
        "The asset rotating around its X axis (pitch). At every frame, the "
        "diagnostic orange surface fills the visible silhouette. Black holes "
        "in the silhouette (where faces are missing because they're "
        "back-culled despite facing the camera) indicate inverted winding."
    ),
    version="2.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "steps": 8,
        "settle_frames": 5,
        "different_ratio_threshold": 0.10,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
    },
    enabled=False,
)
async def test_culling_x(ctx):
    """Backface culling / winding validation (X-axis rotation)."""
    steps = ctx.config["steps"]
    threshold = ctx.config["different_ratio_threshold"]
    angle_per_step = 360.0 / float(max(1, steps))

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(1, 1, 1)
    room.hide_ground()
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

    # --- Single-loop alternating capture ---
    ctx.step("Capturing culling pairs (X-axis rotation)")
    frames_off = []
    frames_on = []

    for i in range(steps):
        ctx.scene.rotate_asset("X", i * angle_per_step)
        await ctx.settle()
        ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
        await ctx.settle()

        ctx.scene.set_double_sided(True)
        await ctx.settle()
        frames_off.append(await ctx.capture_frame(label="culling_x_off"))

        ctx.scene.set_double_sided(False)
        await ctx.settle()
        frames_on.append(await ctx.capture_frame(label="culling_x_on"))

    # --- Object-masked comparison ---
    ctx.step("Comparing culling pairs (object-masked)")
    pair_diffs = []
    for i in range(len(frames_off)):
        result = ctx.compare_object_pixels(
            frames_off[i], frames_on[i], background_color=(1, 1, 1), pixel_threshold=0.20
        )
        pair_diffs.append(result.changed_ratio)

    # --- Guard against empty results ---
    if not pair_diffs:
        ctx.fail(
            "No frames captured -- check steps config (got %d).\n"
            "\n"
            "How to fix:\n"
            "- Increase `steps` in the test config so the camera sweep collects at least "
            "two frames per pair.\n"
            "- Verify the viewport is rendering: in Kit, the `omni.kit.viewport.window` "
            "extension must be loaded and the asset must intersect the camera frustum.\n"
            "- Check `capture_fps` and `physics_fps` in config -- a capture interval larger "
            "than `steps * (physics_fps / capture_fps)` produces zero capture frames.\n"
            "- If running a custom plan/profile, confirm the asset bounds resolve correctly "
            "(`ctx.get_asset_bounds()` must return non-zero extents)." % steps
        )
        return

    max_diff = max(pair_diffs)
    mean_diff = sum(pair_diffs) / len(pair_diffs)
    worst_idx = pair_diffs.index(max_diff)
    passed = max_diff <= threshold

    if not passed:
        ctx.encode_video(
            [frames_off[worst_idx], frames_on[worst_idx]],
            fps=1,
            delete_frames=False,
            label="culling_x_worst_pair",
            role="worst",
        )

    # --- Videos (delete_frames=True frees disk after encoding) ---
    ctx.encode_video(frames_off, fps=2, label="culling_x_culling_off", role="summary")
    ctx.encode_video(frames_on, fps=2, label="culling_x_culling_on", role="summary")

    # --- Metrics ---
    ctx.add_metric("culling_x_max_diff", round(max_diff, 6))
    ctx.add_metric("culling_x_mean_diff", round(mean_diff, 6))
    ctx.add_metric("culling_x_worst_angle", worst_idx * angle_per_step)
    ctx.add_metric("culling_x_passed", 1 if passed else 0)

    # --- Pass/Fail ---
    if not passed:
        ctx.fail(
            "X-axis culling check failed at angle %.0f deg: "
            "%.1f%% object pixel diff (threshold %.0f%%).\n"
            "Fix: Check mesh face winding for top/bottom faces. "
            "In your DCC tool, ensure consistent counter-clockwise "
            "winding and recalculate normals outward." % (worst_idx * angle_per_step, max_diff * 100, threshold * 100),
        )
        return

    ctx.log("X-axis culling PASSED (max diff: %.1f%%)" % (max_diff * 100))

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

"""FET001 Pivot / origin validation (VG.025 -- asset origin positioning).

WHAT: Scores authored origin height and XY centering plus sampled tilt-overlap
      and spin-orbit proxies. The signed height test is one-sided; a passing
      weighted score does not require every criterion or physical floor contact.

HOW:  1. Load the asset and query its bounding box and world position.
      2. Settle (let geometry load) BEFORE framing the camera -- the bbox
         computation requires loaded geometry to produce correct results.
      3. Capture a check frame and verify the diagnostic material (orange)
         is visible. If no orange pixels are detected, SKIP the advisory
         pivot check (object not on screen); presence is checked separately.
      4. Check pivot height: should be at or near the bbox bottom (Z min).
      5. Check pivot XY: should be centered within the bbox footprint.
      6. X-axis tilt test: rotate -45 to +45 degrees, check if the bbox
         goes below Z=0 (ground penetration = pivot not at base).
      7. Z-axis spin test: rotate 360 degrees, track bbox center movement
         (orbital motion = pivot not centered in XY).
      8. Score: base=0.70 (pivot at base) + 0.10 (XY centered) + 0.10
         (no penetration) + 0.10 (no orbital). Pass threshold: 0.70.

WHY:  VG.025 requires assets to be positioned at origin for predictable
      placement in scenes. For ground-standing props, the pivot must be at
      the center of the base so the object sits on the ground plane when
      placed at (0,0,0).

FALSE POSITIVE AVOIDANCE:
  - Visibility pre-check prevents false passes on empty frames (broken
    load, wrong camera framing).
  - IMPORTANT: VG.025 defines THREE valid pivot positions depending on
    object type:
      1. Ground objects (props): pivot at center of base -> tested here
      2. Rotating/hinged objects (doors, joints): pivot at rotation center
      3. Attached objects (cameras, wheels): pivot at attachment point
    This test is for FET001_BASE_NEUTRAL (category 1 only). Objects in
    categories 2 and 3 are CORRECT per VG.025 with non-base pivots; this
    check is ADVISORY: a sub-threshold result is reported as SKIPPED (not a
    failure), keeping the tilt/spin videos and an explanatory message, so
    those objects are not failed here. They are validated under FET021/FET022.
    The pivot result is non-failing pending spec clarification on whether
    VG.025 is a mandatory or optional requirement.
  - Height tolerance (10% of bbox height) accommodates slight offsets from
    DCC tool precision or floating-point rounding.
  - Penetration tolerance (5% of bbox height) allows minor clipping from
    rounded bases or complex geometry.
  - Matte ground plane provides visual reference without reflections.
  - Diagnostic material ensures the object is clearly visible in videos.
"""

import math

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.fet001_visual._asset_visibility import ensure_asset_visible
from simready.foundation.tier_core.runtime_tests._assessment import completed_advisory
from simready.foundation.tier_core.runtime_tests._visual_diagnostics import encode_visual_video
from simready.foundation.tier_core.runtime_tests._visual_readback import validate_visual_config


def _complete_pivot_bounds(bounds):
    """Qualify advisory evidence without changing the existing score or reads."""
    return (
        len(bounds.min) == len(bounds.max) == 3
        and all(math.isfinite(value) for value in (*bounds.min, *bounds.max))
        and all(low <= high for low, high in zip(bounds.min, bounds.max, strict=True))
        and bounds.max[2] > bounds.min[2]
    )


@test(
    features=[
        {"id": "FET001_MinimalPlaceableVisual.0-1-0", "version": "*"},
        {"id": "FET001_MinimalPlaceableVisual.1-0-0", "version": "*"},
        {"id": "FET001_MinimalPlaceableVisual.1-0-1", "version": "*"},
    ],
    name="pivot",
    description=(
        "Computes the asset's world-aligned bounding box and verifies the "
        "asset's origin, then scores a Z-height comparison, XY centering, "
        "X-tilt overlap and Z-spin orbit proxies. A score below "
        "pass_score_threshold is advisory SKIP, not FAIL. A passing score "
        "does not establish physical ground contact or every pivot criterion."
    ),
    expected_video=(
        "Two sampled videos show X-axis tilt and Z-axis spin of the "
        "diagnostically shaded asset with the floor as a visual reference. "
        "Inspect overlap and orbit alongside the score; these are authored "
        "geometry probes, not simulated contact or stability measurements."
    ),
    version="2.0.4",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "steps": 30,
        "settle_frames": 5,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
        "pivot_height_tolerance": 0.10,
        "penetration_tolerance": 0.05,
        "orbital_tolerance": 0.10,
        "pass_score_threshold": 0.70,
        "video_capture_interval": 3,
    },
)
async def test_pivot(ctx):
    """Compute an advisory authored-pivot score and sampled geometry proxies."""
    validate_visual_config(
        ctx.config,
        fractions=("pass_score_threshold",),
        nonnegative=("pivot_height_tolerance", "penetration_tolerance", "orbital_tolerance"),
        positive_counts=("steps", "video_capture_interval"),
    )
    steps = int(ctx.config["steps"])
    pivot_height_tol = ctx.config["pivot_height_tolerance"]
    penetration_tol = ctx.config["penetration_tolerance"]
    orbital_tol = ctx.config["orbital_tolerance"]
    pass_threshold = ctx.config["pass_score_threshold"]
    capture_interval = ctx.config["video_capture_interval"]

    # --- Scene setup ---
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    # Pivot test uses visible ground as reference plane.
    # Matte light gray ground so it's clearly visible but not reflective.
    room.show_ground(color=(0.8, 0.8, 0.8))

    ctx.scene.lighting.add_directional(direction=(45.0, 0.0, 90.0), intensity=3000.0)
    ctx.scene.lighting.add_dome(intensity=150.0)
    ctx.scene.apply_diagnostic_material(color=(0.9, 0.2, 0.0), roughness=1.0, metallic=0.0)
    if not await ensure_asset_visible(ctx, padding=ctx.config["camera_padding"]):
        ctx.skip(
            "Pivot check could not run: fewer than 100 asset-attributable "
            "diagnostic pixels were detected after multiple attempts, so "
            "the pivot/origin cannot be evaluated. This is reported as a skip "
            "(not a failure); object visibility itself is covered by the "
            "presence check.\n"
            "\n"
            "How to fix:\n"
            "- Check that the asset has renderable Mesh geometry.\n"
            "- Verify the USD file loads correctly (no broken references).\n"
            "- Check asset bbox computation for invisible helper geometry."
        )
        return

    # --- Pivot analysis ---
    ctx.step("Analyzing pivot location")
    # Pivot/origin is a static USD-authoring check: read the artist-authored
    # geometry, not a live simulated pose. Under Newton the live Fabric pose of
    # a rigid body is anchored at its center of mass, which would misreport the
    # authored origin as "not at base". authored=True forces the USD read on
    # every engine so the pivot score is engine-independent.
    bounds = ctx.get_asset_bounds(authored=True)
    position = ctx.get_asset_position(authored=True)
    measurements_complete = (
        _complete_pivot_bounds(bounds) and len(position) == 3 and all(math.isfinite(value) for value in position)
    )

    bbox_height = bounds.max[2] - bounds.min[2]
    pivot_height_from_base = position[2] - bounds.min[2]
    pivot_relative_height = pivot_height_from_base / bbox_height if bbox_height > 0 else 0.0
    pivot_at_base = pivot_relative_height <= pivot_height_tol

    # XY centering check
    bbox_cx = (bounds.min[0] + bounds.max[0]) / 2.0
    bbox_cy = (bounds.min[1] + bounds.max[1]) / 2.0
    xy_offset = ((position[0] - bbox_cx) ** 2 + (position[1] - bbox_cy) ** 2) ** 0.5
    object_xy_size = max(bounds.max[0] - bounds.min[0], bounds.max[1] - bounds.min[1], 0.001)
    pivot_centered_xy = xy_offset < (0.10 * object_xy_size)

    # --- X-axis tilt: ground penetration check ---
    ctx.step("Testing X-axis rotation for ground penetration")
    angle_per_step = 90.0 / float(max(1, steps))
    z_mins = []
    frames_x = []
    for i in range(steps):
        angle_deg = -45.0 + (i * angle_per_step)
        ctx.scene.rotate_asset("X", angle_deg)
        await ctx.settle()
        cur_bounds = ctx.get_asset_bounds(authored=True)
        measurements_complete = _complete_pivot_bounds(cur_bounds) and measurements_complete
        z_mins.append(cur_bounds.min[2])
        if i % capture_interval == 0:
            ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
            await ctx.settle()
            frames_x.append(await ctx.capture_frame(label="pivot_tilt"))
    ctx.scene.reset_asset_transform()

    min_z = min(z_mins)
    penetration_threshold = -penetration_tol * bbox_height
    ground_penetration = min_z < penetration_threshold

    # --- Z-axis spin: orbital motion check ---
    ctx.step("Testing Z-axis rotation for orbital motion")
    z_angle_per_step = 360.0 / float(max(1, steps))
    centers_x = []
    centers_y = []
    frames_z = []
    for i in range(steps):
        ctx.scene.rotate_asset("Z", i * z_angle_per_step)
        await ctx.settle()
        cur_bounds = ctx.get_asset_bounds(authored=True)
        measurements_complete = _complete_pivot_bounds(cur_bounds) and measurements_complete
        centers_x.append((cur_bounds.min[0] + cur_bounds.max[0]) / 2.0)
        centers_y.append((cur_bounds.min[1] + cur_bounds.max[1]) / 2.0)
        if i % capture_interval == 0:
            ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
            await ctx.settle()
            frames_z.append(await ctx.capture_frame(label="pivot_spin"))
    ctx.scene.reset_asset_transform()

    x_range = max(centers_x) - min(centers_x)
    y_range = max(centers_y) - min(centers_y)
    orbit_radius = max(x_range, y_range) / 2.0
    orbital_motion = orbit_radius > (orbital_tol * object_xy_size) if object_xy_size > 0 else False

    # --- Videos ---
    if frames_x:
        encode_visual_video(ctx, frames_x, fps=2, label="pivot_tilt_x", role="summary")
    if frames_z:
        encode_visual_video(ctx, frames_z, fps=2, label="pivot_spin_z", role="summary")

    # --- Score ---
    # Base=0.70 (pivot at base), XY=0.10, no-penetration=0.10, no-orbital=0.10
    pivot_score = 0.0
    if pivot_at_base:
        pivot_score = 0.70
    if pivot_centered_xy:
        pivot_score += 0.10
    if not ground_penetration:
        pivot_score += 0.10
    if not orbital_motion:
        pivot_score += 0.10

    passed = pivot_score >= pass_threshold

    # --- Metrics ---
    ctx.add_metric("pivot_score", round(pivot_score, 4))
    ctx.add_metric("pivot_pivot_height_pct", round(pivot_relative_height * 100, 1))
    ctx.add_metric("pivot_pivot_at_base", 1 if pivot_at_base else 0)
    ctx.add_metric("pivot_pivot_centered_xy", 1 if pivot_centered_xy else 0)
    ctx.add_metric("pivot_ground_penetration", 1 if ground_penetration else 0)
    ctx.add_metric("pivot_orbital_motion", 1 if orbital_motion else 0)
    ctx.add_metric("pivot_passed", 1 if passed else 0)

    # --- Pass/Fail ---
    if not passed:
        issues = []
        if not pivot_at_base:
            issues.append(
                "Pivot is %.1f%% from base (should be <%.0f%%)." % (pivot_relative_height * 100, pivot_height_tol * 100)
            )
        if not pivot_centered_xy:
            issues.append("Pivot not centered in XY (offset=%.3f, size=%.3f)." % (xy_offset, object_xy_size))
        if ground_penetration:
            issues.append("X-axis tilt causes ground penetration (min_z=%.3f)." % min_z)
        if orbital_motion:
            issues.append("Z-rotation shows orbital motion (radius=%.3f)." % orbit_radius)
        ctx.skip(
            "Pivot/origin check did not meet the recommended score "
            "(score=%.2f, recommended >=%.2f). Reported as SKIPPED, not a "
            "failure: the correct pivot location depends on the object type, so "
            "a sub-threshold result is advisory and does not fail FET001. The "
            "tilt and spin videos are kept below so the pivot can be judged "
            "visually.\n"
            "%s\n"
            "\n"
            "How to fix:\n"
            "- Move the asset pivot to the bottom-center of the bounding box.\n"
            "- The pivot should be at Z=0 (ground level) and centered in XY.\n"
            "- In your DCC tool, set the pivot/origin to the base of the object.\n"
            "- Check the X-tilt and Z-spin videos for visual reference.\n"
            "\n"
            "When this can be ignored: this check validates ground-placeable\n"
            "props. If your object is a rotating/hinged type (e.g., door, robot\n"
            "joint), the pivot should be at the rotation center -- not the base;\n"
            "those are validated under FET021/FET022. Attached objects (cameras,\n"
            "wheels) should have their pivot at the attachment point.\n"
            "\n"
            "INTERIM: pivot/origin (VG.025) is treated as advisory and does not\n"
            "fail the feature, pending spec clarification on whether VG.025 is a\n"
            "mandatory or optional requirement (refer to "
            "docs/spec-clarifications-needed.md)." % (pivot_score, pass_threshold, "\n".join(issues))
        )
        # The legacy SKIP remains the verdict. Only the completed measured
        # advisory branch may distinguish itself from unavailable assessment.
        # Validate derived values too: finite coordinates can still overflow.
        if (
            measurements_complete
            and not ctx.failed
            and all(
                math.isfinite(value)
                for value in (
                    bbox_height,
                    pivot_relative_height,
                    xy_offset,
                    object_xy_size,
                    min_z,
                    penetration_threshold,
                    orbit_radius,
                    pivot_score,
                )
            )
        ):
            ctx.add_metric(
                "assessment_advisory",
                completed_advisory(
                    "pivot_score_below_recommendation",
                    "Completed pivot measurements are below the recommended score; origin placement depends on object type.",
                ),
            )
        return

    ctx.log("Pivot validation PASSED (score=%.2f)" % pivot_score)

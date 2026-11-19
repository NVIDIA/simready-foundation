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
"""FET_035 Render product output check (RP.003).

WHAT: Replicator runtime check for authored RenderProduct prims.

For each authored UsdRender.Product prim (excluding OmniverseKit-internal
prims), reads its authored camera path, resolution, and sourceName list, then:
  - Copy-constructs a Replicator-managed render product from the same camera
    and resolution (cold-authored RP prims are not registered with Hydra;
    Replicator creates its own equivalent RP).
  - Attaches a writer collecting the annotator matching each sourceName.
  - Steps Replicator, up to max_capture_steps frames, until the writer has
    received output from every annotator, and verifies the returned arrays
    are non-empty. Geometry annotators (DepthLinearized, normals) also
    require at least some non-zero values; a reference cube is placed 2 m in
    front of each camera to guarantee geometry hits.
  - Destroys the render product after it is checked, so products do not
    accumulate and slow down the ones that follow.

OmniLidar-targeted RenderProducts are skipped (multiple RTX LiDAR sensors
in one pass cause a CUDA conflict). LiDAR point cloud output is validated
separately by the lidar_point_cloud test.

SCOPE: This test exercises Replicator-managed equivalents of the authored
       RenderProduct configuration. It does not verify direct Hydra activation
       or end-to-end output through the authored RenderProduct prims.

PASS/FAIL:
  - PASS: exercised annotators return non-empty data with at least one finite
          sample for numeric AOVs (and non-zero output for geometry).
  - FAIL: measured geometry output is all-zero, or a referenced camera cannot
          be found in the composed stage.
  - ERROR: required setup, stepping, or readback fails, or output is absent,
           empty, scalar, object, or string data, or a numeric AOV has no finite
           samples. Mixed finite/nonfinite arrays retain the content checks.
  - SKIP: no authored RenderProduct prims found (excluding internal ones).
"""

import os
import sys

import numpy as np
from simready.evaluate.core.decorator import test
from simready.foundation.sensors.runtime_tests.fet035_render_products.render_product_utils import (
    attach_frame_writer,
    availability_error,
    availability_problem,
    composed_path,
    release_render_product,
    step_until_ready,
    waiting_for_data,
)

_DEFAULT_RESOLUTION = (512, 512)
_COLOR_ANNOTATORS = frozenset(
    ("LdrColor", "HdrColor", "SemanticSegmentation", "SemanticBoundingBox2DLoose", "SemanticBoundingBox2DTight")
)


def _save_annotator_image(arr, rp_name, src_name, output_dir):
    """Save annotator array as PNG to output_dir. Silently skips on any error."""
    try:
        from PIL import Image

        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "%s_%s.png" % (rp_name, src_name))
        if arr.ndim == 1:
            return
        if arr.ndim == 3 and arr.shape[2] in (3, 4):
            rgb = arr[:, :, :3].astype(float)
            mn, mx = rgb.min(), rgb.max()
            if mn < 0:
                rgb = (rgb + 1.0) / 2.0 * 255  # normals: remap [-1,1] to [0,255]
            elif mx <= 1.0:
                rgb = rgb * 255
            Image.fromarray(rgb.clip(0, 255).astype(np.uint8), "RGB").save(path)
            if arr.shape[2] == 4 and src_name in _COLOR_ANNOTATORS:
                alpha_path = path.replace(".png", "_alpha.png")
                Image.fromarray(arr[:, :, 3].clip(0, 255).astype(np.uint8), "L").save(alpha_path)
        elif arr.ndim == 2:
            farr = arr.astype(float)
            finite = np.isfinite(farr)
            vis = np.zeros(farr.shape, dtype=float)
            if finite.any():
                mn, mx = farr[finite].min(), farr[finite].max()
                if mx > mn:
                    vis[finite] = (farr[finite] - mn) / (mx - mn)
            Image.fromarray((vis * 255).astype(np.uint8), "L").save(path)
    except Exception:
        pass


def _is_kit_internal(prim_path):
    return "OmniverseKit" in str(prim_path)


def _read_rp_properties(stage, rp_prim):
    """Return (cam_path, resolution, [source_names]) from an authored RP."""
    cam_rel = rp_prim.GetRelationship("camera")
    vars_rel = rp_prim.GetRelationship("orderedVars")

    cam_path = str(cam_rel.GetTargets()[0]) if cam_rel.IsValid() and cam_rel.GetTargets() else None

    res_attr = rp_prim.GetAttribute("resolution")
    resolution = (
        tuple(int(v) for v in res_attr.Get())
        if res_attr.IsValid() and res_attr.Get() is not None
        else _DEFAULT_RESOLUTION
    )

    source_names = []
    if vars_rel.IsValid():
        for var_path in vars_rel.GetTargets():
            var_prim = stage.GetPrimAtPath(var_path)
            if not var_prim.IsValid():
                continue
            src_attr = var_prim.GetAttribute("sourceName")
            if src_attr.IsValid():
                name = src_attr.Get()
                if name:
                    source_names.append(name)

    return cam_path, resolution, source_names


def _place_cube_in_front_of_camera(stage, cam_prim_path, index):
    """Place a 0.4 m cube 2 m along the camera's world forward vector.

    Returns the cube's prim path.
    """
    from pxr import Gf, Usd, UsdGeom

    cam_prim = stage.GetPrimAtPath(cam_prim_path)
    if not cam_prim.IsValid():
        raise RuntimeError(f"Reference geometry camera is unavailable: {cam_prim_path}")
    xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    world_xf = xf_cache.GetLocalToWorldTransform(cam_prim)
    fwd = world_xf.TransformDir(Gf.Vec3d(0, 0, -1)).GetNormalized()
    pos = Gf.Vec3d(world_xf.ExtractTranslation()) + fwd * 2.0
    cube = UsdGeom.Cube.Define(stage, "/World/DepthCube_%d" % index)
    cube.GetSizeAttr().Set(0.4)
    UsdGeom.XformCommonAPI(cube.GetPrim()).SetTranslate((pos[0], pos[1], pos[2]))
    return cube.GetPath().pathString


def _place_light_along_camera(stage, cam_prim_path, index):
    """Add a distant light that shines along the camera's viewing direction.

    A Camera looks along its local -Z axis and a DistantLight shines along its
    own -Z axis, so giving the light the camera's world rotation lights the face
    of the reference cube that the camera sees. A light with the default
    (downward) orientation leaves that face unlit and the color images black.

    Returns the light's prim path.
    """
    from pxr import Gf, Usd, UsdGeom, UsdLux

    cam_prim = stage.GetPrimAtPath(cam_prim_path)
    if not cam_prim.IsValid():
        raise RuntimeError(f"Reference light camera is unavailable: {cam_prim_path}")
    xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    rot = xf_cache.GetLocalToWorldTransform(cam_prim).ExtractRotationQuat()
    light = UsdLux.DistantLight.Define(stage, "/World/CubeLight_%d" % index)
    light.CreateIntensityAttr(3000.0)
    UsdGeom.Xformable(light.GetPrim()).AddOrientOp().Set(Gf.Quatf(float(rot.GetReal()), Gf.Vec3f(rot.GetImaginary())))
    return light.GetPath().pathString


def _remove_prims(stage, prim_paths):
    """Remove the prims placed for one camera so they cannot affect the next one.

    A cube placed for one camera casts shadows on the next camera's cube and can
    show up in its depth image, and a leftover light lights the next camera's scene.
    """
    for path in prim_paths:
        try:
            stage.RemovePrim(path)
        except Exception:
            pass


def _is_ready(src_name, arr):
    """True when annotator output needs no more frames to be judged."""
    if waiting_for_data(arr):
        return False
    return not _all_zero_geometry(src_name, arr)


def _all_zero_geometry(src_name, arr):
    """True for a geometry annotator whose usable output has no non-zero value."""
    return availability_problem(arr) is None and src_name not in _COLOR_ANNOTATORS and not np.any(arr != 0)


@test(
    features=[
        {"id": "FET035_RenderProducts.RTX.0-1-0", "version": "*"},
    ],
    name="render_product_output",
    description=(
        "Copy-constructs a Replicator render product from the authored camera and "
        "resolution of each authored RenderProduct prim, attaches annotators matching "
        "each sourceName, and verifies that each annotator returns non-empty output "
        "within max_capture_steps Replicator frames (RP.003). Each render product is "
        "destroyed after it is checked."
    ),
    expected_video=(
        "One PNG per annotator per Camera RenderProduct, written to the run output "
        "directory. A distant light shining along each camera's viewing direction is "
        "added at runtime so color annotators (LdrColor, HdrColor) render the "
        "reference cube as a lit grey shape rather than solid black. An _alpha.png "
        "companion is saved for color annotators with an alpha channel. Depth and normals images show the reference cube placed 2 m "
        "in front of the camera as normalized grayscale."
    ),
    version="0.1.1",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "warmup_frames": 30,
        # A new render product may not deliver on its first frame; step up to
        # this many frames before reporting its output as unavailable.
        "max_capture_steps": 10,
    },
)
async def test_render_product_output(ctx):
    """Replicator AOV output check — RP.003."""
    import omni.replicator.core as rep

    try:
        await _check_render_product_output(ctx)
    finally:
        primary_error = sys.exc_info()[1]
        try:
            rep.orchestrator.stop()
        except BaseException:
            if primary_error is None:
                raise


async def _check_render_product_output(ctx):
    import omni.replicator.core as rep
    import omni.usd
    from pxr import Usd, UsdGeom, UsdRender

    asset_handle = ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    composed_root = asset_handle.prim_path
    await ctx.settle()

    # RenderProduct prims live in the /Render scope at the root of the USD
    # file, which is outside the asset's defaultPrim. The framework's
    # load_asset() references only the defaultPrim subtree, so /Render is
    # invisible to the composed stage. Open the raw asset file directly to
    # traverse all prims, including the /Render scope.
    asset_stage = Usd.Stage.Open(ctx.asset_path)
    default_prim = asset_stage.GetDefaultPrim()
    default_prim_path = default_prim.GetPath() if default_prim else None
    composed_stage = omni.usd.get_context().get_stage()

    authored_rps = [p for p in asset_stage.Traverse() if p.IsA(UsdRender.Product) and not _is_kit_internal(p.GetPath())]

    if not authored_rps:
        ctx.skip("No authored RenderProduct prims found in asset (excluding OmniverseKit internal prims).")
        return

    ctx.log("Found %d authored RenderProduct prim(s)." % len(authored_rps))
    ctx.add_metric("render_product_count", len(authored_rps))

    # --- Replicator runtime check (RP.003) ---
    ctx.step("Replicator check: annotator attachment and data output")

    # The Replicator runs in the composed stage where cameras were loaded.
    # Camera paths from the raw asset (e.g. /Root/RGB_Camera) are remapped
    # to their composed equivalents by full path, since the framework places
    # the defaultPrim subtree at a different path prefix. Matching on prim name
    # alone is ambiguous when several cameras share a name.

    for _ in range(ctx.config["warmup_frames"]):
        await rep.orchestrator.preview_async()

    annotator_failures = []
    data_failures = []
    max_frames_to_data = 0
    max_capture_steps = max(1, int(ctx.config["max_capture_steps"]))

    for i, rp in enumerate(authored_rps):
        rp_name = rp.GetPath().name
        raw_cam_path, resolution, source_names = _read_rp_properties(asset_stage, rp)

        if raw_cam_path is None or not source_names:
            continue

        # Remap the raw camera path to the composed stage path.
        cam_path = composed_path(raw_cam_path, default_prim_path, composed_root)
        cam_prim = composed_stage.GetPrimAtPath(cam_path) if cam_path else None
        if cam_prim is None or not cam_prim.IsValid():
            annotator_failures.append("%s: camera '%s' not found in composed stage" % (rp_name, raw_cam_path))
            continue

        # Skip OmniLidar prims — they are not Camera prims. Multiple RTX LiDAR
        # sensors in one Replicator pass also cause a CUDA conflict. Point
        # cloud output is covered by the lidar_point_cloud test.
        if cam_prim.GetTypeName() == "OmniLidar":
            ctx.log("  SKIP %s: OmniLidar — deferred to lidar_point_cloud test." % rp_name)
            continue

        if not cam_prim.IsA(UsdGeom.Camera):
            annotator_failures.append(
                "%s: camera '%s' is a %s, not a Camera" % (rp_name, raw_cam_path, cam_prim.GetTypeName())
            )
            continue

        ctx.log("  %s: camera %s" % (rp_name, cam_path))

        # Place a reference cube in front of the camera so geometry annotators
        # (DepthLinearized, normals) have non-background geometry to sample, and
        # a light that shines on the face the camera sees so color annotators
        # (LdrColor, HdrColor) do not render it black. The minimal test fixtures
        # carry no lights. Both are removed once this camera has been checked.
        scene_prims = [
            _place_cube_in_front_of_camera(composed_stage, cam_path, i),
            _place_light_along_camera(composed_stage, cam_path, i),
        ]
        rep_rp = None
        writer = None
        try:
            # Copy-construct a Replicator RP from the authored camera and resolution.
            try:
                rep_rp = rep.create.render_product(cam_path, resolution)
                rep_rp_path = rep_rp.path if hasattr(rep_rp, "path") else str(rep_rp)
            except Exception as exc:
                raise RuntimeError(f"{rp_name}: Replicator render product creation failed") from exc

            # Attach a writer collecting the annotator matching each authored sourceName.
            annotator_names = list(dict.fromkeys(source_names))
            writer = attach_frame_writer(rep, rep_rp_path, annotator_names, rp_name)

            # A new render product may not deliver on its first frame, so step
            # until every annotator has output, up to max_capture_steps.
            arrays, frames_used = await step_until_ready(
                rep, writer, annotator_names, max_capture_steps, rp_name, _is_ready
            )
            max_frames_to_data = max(max_frames_to_data, frames_used)
            if frames_used > 1:
                ctx.log("  %s: needed %d frames before output was ready" % (rp_name, frames_used))

            # Validate annotator output.
            for src_name, arr in arrays.items():
                problem = availability_problem(arr)
                if problem is not None:
                    raise RuntimeError(f"{rp_name} '{src_name}': annotator readback failed") from availability_error(
                        "annotator", problem, frames_used
                    )
                if _all_zero_geometry(src_name, arr):
                    data_failures.append(
                        "%s '%s': all-zero array — no geometry visible to annotator (after %d frame%s)"
                        % (rp_name, src_name, frames_used, "" if frames_used == 1 else "s")
                    )
                else:
                    ctx.log("  PASS %s '%s': shape=%s dtype=%s" % (rp_name, src_name, arr.shape, arr.dtype))
                    out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
                    _save_annotator_image(arr, rp_name, src_name, out_dir)
        finally:
            if rep_rp is not None:
                release_render_product(ctx, rp_name, rep_rp, writer)
            _remove_prims(composed_stage, scene_prims)

    ctx.add_metric("annotator_failures", len(annotator_failures))
    ctx.add_metric("data_failures", len(data_failures))
    ctx.add_metric("max_frames_to_data", max_frames_to_data)

    all_failures = annotator_failures + data_failures
    if all_failures:
        ctx.fail(
            "Replicator runtime check failed (%d issue(s)):\n" % len(all_failures)
            + "\n".join("  " + f for f in all_failures)
        )
        return

    ctx.log("Replicator runtime check PASSED: all annotators returned non-empty data.")

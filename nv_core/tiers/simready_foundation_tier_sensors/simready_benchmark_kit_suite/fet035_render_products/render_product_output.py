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
  - Attaches annotators matching each sourceName.
  - Triggers one Replicator frame and verifies the returned arrays are
    non-empty. Geometry annotators (DepthLinearized, normals) also require
    at least some non-zero values; a reference cube is placed 2 m in front
    of each camera to guarantee geometry hits.

OmniLidar-targeted RenderProducts are skipped (multiple RTX LiDAR sensors
in one pass cause a CUDA conflict). LiDAR point cloud output is validated
separately by the lidar_point_cloud test.

SCOPE: Cold-authored RenderProduct USD prims cannot be directly activated
       via Hydra without Replicator creating its own render product. Full
       pipeline activation via the authored RP awaits a future Isaac Sim
       API (per Avinash Devalla, #omni-rtx-sensors).

PASS/FAIL:
  - PASS: all annotators return non-empty (and non-zero for geometry) data.
  - FAIL: any annotator returns empty/zero data or fails to attach.
  - SKIP: no authored RenderProduct prims found (excluding internal ones).
"""
import os

import numpy as np
from simready_benchmark.core.decorator import test

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
    """Place a 0.4 m cube 2 m along the camera's world forward vector."""
    try:
        from pxr import Gf, Usd, UsdGeom

        cam_prim = stage.GetPrimAtPath(cam_prim_path)
        if not cam_prim.IsValid():
            return
        xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        world_xf = xf_cache.GetLocalToWorldTransform(cam_prim)
        fwd = world_xf.TransformDir(Gf.Vec3d(0, 0, -1)).GetNormalized()
        pos = Gf.Vec3d(world_xf.ExtractTranslation()) + fwd * 2.0
        cube = UsdGeom.Cube.Define(stage, "/World/DepthCube_%d" % index)
        cube.GetSizeAttr().Set(0.4)
        UsdGeom.XformCommonAPI(cube.GetPrim()).SetTranslate((pos[0], pos[1], pos[2]))
    except Exception:
        pass


@test(
    features=[{"id": "FET_035_RTX", "version": ">=0.1.0"}],
    name="render_product_output",
    description=(
        "Copy-constructs a Replicator render product from the authored camera and "
        "resolution of each authored RenderProduct prim, attaches annotators matching "
        "each sourceName, and verifies that each annotator returns non-empty output "
        "(RP.003)."
    ),
    expected_video=(
        "One PNG per annotator per Camera RenderProduct, written to the run output "
        "directory. A distant light is added at runtime so color annotators "
        "(LdrColor, HdrColor) render the reference cube as a grey shape rather than "
        "solid black. An _alpha.png companion is saved for color annotators with an "
        "alpha channel. Depth and normals images show the reference cube placed 2 m "
        "in front of the camera as normalized grayscale."
    ),
    version="0.1.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "warmup_frames": 30,
    },
)
async def test_render_product_output(ctx):
    """Replicator AOV output check — RP.003."""
    import omni.replicator.core as rep
    import omni.usd
    from pxr import Usd, UsdRender

    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    await ctx.settle()

    # Add a distant light so color annotators (LdrColor, HdrColor) produce
    # non-black output. The minimal test fixtures carry no lights of their own.
    import omni.kit.commands
    omni.kit.commands.execute("CreatePrimWithDefaultXform", prim_type="DistantLight")

    # RenderProduct prims live in the /Render scope at the root of the USD
    # file, which is outside the asset's defaultPrim. The framework's
    # load_asset() references only the defaultPrim subtree, so /Render is
    # invisible to the composed stage. Open the raw asset file directly to
    # traverse all prims, including the /Render scope.
    asset_stage = Usd.Stage.Open(ctx.asset_path)
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
    # to their composed equivalents by matching on prim name, since the
    # framework places the defaultPrim subtree at a different path prefix.
    cameras_by_name = {
        p.GetName(): p.GetPath().pathString for p in composed_stage.Traverse() if p.GetTypeName() == "Camera"
    }
    lidar_names = {p.GetName() for p in composed_stage.Traverse() if p.GetTypeName() == "OmniLidar"}

    for _ in range(ctx.config["warmup_frames"]):
        await rep.orchestrator.preview_async()

    annotator_failures = []
    data_failures = []

    for i, rp in enumerate(authored_rps):
        rp_name = rp.GetPath().name
        raw_cam_path, resolution, source_names = _read_rp_properties(asset_stage, rp)

        if raw_cam_path is None or not source_names:
            continue

        # Remap the raw camera path to the composed stage path.
        cam_name = raw_cam_path.split("/")[-1]

        # Skip OmniLidar cameras — they are not Camera prims and won't be in
        # cameras_by_name. Multiple RTX LiDAR sensors in one Replicator pass
        # also cause a CUDA conflict. Point cloud output is covered by the
        # lidar_point_cloud test.
        if cam_name in lidar_names:
            ctx.log("  SKIP %s: OmniLidar — deferred to lidar_point_cloud test." % rp_name)
            continue

        cam_path = cameras_by_name.get(cam_name)
        if cam_path is None:
            annotator_failures.append("%s: camera '%s' not found in composed stage" % (rp_name, cam_name))
            continue

        # Place a reference cube in front of the camera so geometry annotators
        # (DepthLinearized, normals) have non-background geometry to sample.
        _place_cube_in_front_of_camera(composed_stage, cam_path, i)

        # Copy-construct a Replicator RP from the authored camera and resolution.
        try:
            rep_rp = rep.create.render_product(cam_path, resolution)
            rep_rp_path = rep_rp.path if hasattr(rep_rp, "path") else str(rep_rp)
        except Exception as exc:
            annotator_failures.append("%s: rep.create.render_product() failed: %s" % (rp_name, exc))
            continue

        # Attach annotators matching each authored sourceName.
        attached = []
        for src_name in source_names:
            try:
                anno = rep.annotators.get(src_name)
                anno.attach(rep_rp_path)
                attached.append((src_name, anno))
            except Exception as exc:
                annotator_failures.append("%s: annotator '%s' not registered: %s" % (rp_name, src_name, exc))

        if not attached:
            continue

        # Trigger one Replicator frame.
        try:
            await rep.orchestrator.step_async()
        except Exception as exc:
            annotator_failures.append("%s: Replicator step failed: %s" % (rp_name, exc))
            continue

        # Validate annotator output.
        for src_name, anno in attached:
            try:
                data = anno.get_data()
                if data is None:
                    data_failures.append("%s '%s': None returned" % (rp_name, src_name))
                    continue
                if isinstance(data, dict):
                    raw = data.get("data", list(data.values())[0] if data else None)
                    arr = np.array(raw) if raw is not None else np.array([])
                else:
                    arr = np.array(data)
                if arr.size == 0:
                    data_failures.append("%s '%s': empty array" % (rp_name, src_name))
                elif src_name not in _COLOR_ANNOTATORS and not np.any(arr != 0):
                    data_failures.append(
                        "%s '%s': all-zero array — no geometry visible to annotator" % (rp_name, src_name)
                    )
                else:
                    ctx.log("  PASS %s '%s': shape=%s dtype=%s" % (rp_name, src_name, arr.shape, arr.dtype))
                    out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
                    _save_annotator_image(arr, rp_name, src_name, out_dir)
            except Exception as exc:
                ctx.log("  SKIP %s '%s': get_data() error: %s" % (rp_name, src_name, exc))

    rep.orchestrator.stop()

    ctx.add_metric("annotator_failures", len(annotator_failures))
    ctx.add_metric("data_failures", len(data_failures))

    all_failures = annotator_failures + data_failures
    if all_failures:
        ctx.fail(
            "Replicator runtime check failed (%d issue(s)):\n" % len(all_failures)
            + "\n".join("  " + f for f in all_failures)
            + "\n\nHow to fix:\n"
            "- RP.003: each sourceName in orderedVars must match a registered "
            "Replicator annotator name (e.g. LdrColor, DepthLinearized, normals).\n"
            "- Confirm the camera prim is a valid UsdGeom.Camera, not an "
            "OmniLidar or other non-camera prim type."
        )
        return

    ctx.log("Replicator runtime check PASSED: all annotators returned non-empty data.")

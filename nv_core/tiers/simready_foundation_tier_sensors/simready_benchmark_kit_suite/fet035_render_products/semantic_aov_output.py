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
"""FET_035 Semantic AOV runtime output check.

WHAT: Replicator runtime check for semantic AOV RenderVars.

For each RenderProduct containing a semantic RenderVar (sourceName starting
with "semantic"), a Replicator render product is copy-constructed from the
authored camera path and resolution, semantic annotators are attached
matching each sourceName, one frame is triggered, and the returned arrays
are verified to be non-empty.

WHY: Confirms the annotator pipeline is functional at runtime. Static
     validation (RP.004) already enforces BLOSC compression at authoring
     time; this test verifies the annotators actually produce output.

SCOPE: The srtx:compression:type attribute controls compression when output
       is written to disk by a Replicator writer. Reading via
       annotator.get_data() returns an in-memory array to which compression
       has not been applied. Full end-to-end verification of BLOSC on output
       EXR files (via header inspection) requires a Replicator file-writing
       pass and is deferred.
"""
import os

import numpy as np
from simready_benchmark.core.decorator import test

_SEMANTIC_PALETTE = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
]


def _save_annotator_image(arr, rp_name, src_name, output_dir):
    """Save semantic annotator array as PNG to output_dir. Silently skips on any error."""
    try:
        from PIL import Image

        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "%s_%s.png" % (rp_name, src_name))
        if arr.ndim == 2 and arr.dtype == np.uint32:
            h, w = arr.shape
            rgb = np.zeros((h, w, 3), dtype=np.uint8)
            unique_ids = np.unique(arr)
            for idx, uid in enumerate(unique_ids):
                if uid == 0:
                    continue
                color = _SEMANTIC_PALETTE[idx % len(_SEMANTIC_PALETTE)]
                mask = arr == uid
                rgb[mask] = color
            Image.fromarray(rgb, "RGB").save(path)
        elif arr.ndim == 3 and arr.shape[2] in (3, 4):
            rgb = arr[:, :, :3].astype(float)
            mn, mx = rgb.min(), rgb.max()
            if mx <= 1.0:
                rgb = rgb * 255
            Image.fromarray(rgb.clip(0, 255).astype(np.uint8), "RGB").save(path)
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


def _is_kit_internal(prim_path: str) -> bool:
    return "OmniverseKit" in str(prim_path)


def _get_render_products_with_semantic_vars(stage):
    """Return list of (rp_prim, cam_path, resolution, [semantic_source_names])."""
    from pxr import UsdRender

    results = []
    for rp in stage.Traverse():
        if not rp.IsA(UsdRender.Product):
            continue
        if _is_kit_internal(rp.GetPath()):
            continue
        cam_rel = rp.GetRelationship("camera")
        vars_rel = rp.GetRelationship("orderedVars")
        if not cam_rel.IsValid() or not cam_rel.GetTargets():
            continue
        cam_path = str(cam_rel.GetTargets()[0])
        res_attr = rp.GetAttribute("resolution")
        resolution = (
            tuple(int(v) for v in res_attr.Get()) if res_attr.IsValid() and res_attr.Get() is not None else (512, 512)
        )
        semantic_names = []
        if vars_rel.IsValid():
            for var_path in vars_rel.GetTargets():
                var_prim = stage.GetPrimAtPath(var_path)
                if not var_prim.IsValid():
                    continue
                src_attr = var_prim.GetAttribute("sourceName")
                if src_attr.IsValid():
                    name = src_attr.Get() or ""
                    if name.lower().startswith("semantic"):
                        semantic_names.append(name)
        if semantic_names:
            results.append((rp, cam_path, resolution, semantic_names))
    return results


@test(
    features=[{"id": "FET_035_RTX", "version": ">=0.1.0"}],
    name="semantic_aov_output",
    description=(
        "Verifies that Replicator annotators for semantic RenderVars "
        "(sourceName starting with 'semantic') are registered and produce "
        "non-empty output when the render pipeline runs."
    ),
    expected_video=(
        "One PNG per semantic annotator per RenderProduct, written to the run "
        "output directory. SemanticSegmentation output is colorized by class ID "
        "(each unique ID mapped to a distinct color; background class 0 is black). "
        "Values may be all-zero when no prims carry SemanticAPI labels — this is "
        "expected for minimal fixtures."
    ),
    version="0.1.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
    },
)
async def test_semantic_aov_output(ctx):
    """Semantic AOV Replicator output check."""
    import omni.usd
    import omni.replicator.core as rep

    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    await ctx.settle()

    # load_asset() references only the defaultPrim subtree, so /Render prims
    # are invisible in the composed stage. Open the raw file directly to
    # traverse all prims including /Render.
    from pxr import Usd, UsdGeom

    raw_stage = Usd.Stage.Open(ctx.asset_path)
    composed_stage = omni.usd.get_context().get_stage()

    # Index all Camera prims in the composed stage by name for path remapping.
    # The framework loads the defaultPrim subtree at a different path prefix
    # than the raw asset, so camera paths must be matched by prim name.
    cameras_by_name = {
        p.GetName(): str(p.GetPath())
        for p in composed_stage.Traverse()
        if p.IsA(UsdGeom.Camera)
    }

    rps_with_semantic = _get_render_products_with_semantic_vars(raw_stage)
    if not rps_with_semantic:
        ctx.skip("No RenderProducts with semantic RenderVars found in asset.")
        return

    ctx.add_metric("semantic_rp_count", len(rps_with_semantic))

    # --- Replicator runtime check ---
    ctx.step("Replicator check: attach semantic annotators and verify output")

    annotator_failures = []
    data_failures = []

    for rp_prim, raw_cam_path, resolution, semantic_names in rps_with_semantic:
        cam_name = raw_cam_path.split("/")[-1]
        cam_path = cameras_by_name.get(cam_name)
        if cam_path is None:
            annotator_failures.append(
                f"{rp_prim.GetPath().name}: camera '{cam_name}' not found in composed stage"
            )
            continue

        # Copy-construct a Replicator RP mirroring the authored camera and
        # resolution. This confirms the authored camera path is valid and
        # renderable, and that each semantic sourceName maps to a registered
        # Replicator annotator (RP.003 cross-check).
        try:
            rep_rp = rep.create.render_product(cam_path, resolution)
            rep_rp_path = rep_rp.path if hasattr(rep_rp, "path") else str(rep_rp)
        except Exception as e:
            annotator_failures.append(f"{rp_prim.GetPath().name}: render product creation failed: {e}")
            continue

        attached = []
        for name in semantic_names:
            try:
                anno = rep.annotators.get(name)
                anno.attach(rep_rp_path)
                attached.append((name, anno))
            except Exception as e:
                annotator_failures.append(f"{rp_prim.GetPath().name}: annotator '{name}' not registered: {e}")

        if not attached:
            continue

        # Trigger one Replicator frame
        try:
            await rep.orchestrator.step_async()
        except Exception as exc:
            annotator_failures.append(f"{rp_prim.GetPath().name}: Replicator step failed: {exc}")
            continue

        for name, anno in attached:
            try:
                data = anno.get_data()
                arr = np.array(data) if not isinstance(data, np.ndarray) else data
                if arr.size == 0:
                    data_failures.append(f"{rp_prim.GetPath().name} '{name}': empty array returned")
                else:
                    ctx.log(f"  PASS {rp_prim.GetPath().name} '{name}': " f"shape={arr.shape} dtype={arr.dtype}")
                    out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
                    _save_annotator_image(arr, rp_prim.GetPath().name, name, out_dir)
            except Exception as e:
                data_failures.append(f"{rp_prim.GetPath().name} '{name}': get_data error: {e}")

    rep.orchestrator.stop()

    ctx.add_metric("annotator_failures", len(annotator_failures))
    ctx.add_metric("data_failures", len(data_failures))

    all_failures = annotator_failures + data_failures
    if all_failures:
        ctx.fail(
            f"Replicator runtime check failed ({len(all_failures)} issue(s)):\n"
            + "\n".join(f"  {f}" for f in all_failures)
        )
        return

    ctx.log("Replicator check PASSED: all semantic annotators returned non-empty data.")

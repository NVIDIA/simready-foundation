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
authored camera path and resolution, a writer collecting the semantic
annotator matching each sourceName is attached, Replicator is stepped (up to
max_capture_steps frames) until the writer has received output from every
annotator, and the returned arrays are verified to be non-empty. The render
product is destroyed after it is checked.

PASS/FAIL:
  - PASS: exercised semantic annotators return non-empty array data, including
          all-zero imagery, with at least one finite sample for numeric AOVs.
  - FAIL: a referenced camera cannot be found in the composed stage.
  - ERROR: required setup, stepping, or readback fails, or output is absent,
           empty, scalar, object, or string data, or a numeric AOV has no finite
           samples. Mixed finite/nonfinite arrays retain the content checks.
  - SKIP: no eligible RenderProducts with semantic RenderVars are found.

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

import json
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

_SEMANTIC_PALETTE = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
]


def _save_annotator_image(arr, rp_name, src_name, output_dir, payload=None):
    """Save diagnostic PNG/label metadata; return a warning when evidence is incomplete."""
    try:
        from PIL import Image

        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "%s_%s.png" % (rp_name, src_name))
        warning = None
        if arr.ndim == 2 and arr.dtype == np.uint32:
            h, w = arr.shape
            rgb = np.zeros((h, w, 3), dtype=np.uint8)
            info = payload.get("info") if isinstance(payload, dict) else None
            labels = info.get("idToLabels") if isinstance(info, dict) else None
            # Render-product writer payloads flatten metadata beside "data";
            # legacy annotator payloads keep it under "info".
            if labels is None and isinstance(payload, dict):
                labels = payload.get("idToLabels")
            labels = {str(key): value for key, value in labels.items()} if isinstance(labels, dict) else {}
            colors, unmapped = {}, []
            class_index = 0
            for uid in np.unique(arr):
                key = str(int(uid))
                label = labels.get(key)
                values = list(label.values()) if isinstance(label, dict) else [label]
                values = [value.strip().casefold() for value in values if isinstance(value, str) and value.strip()]
                color = (0, 0, 0)
                if uid != 0:
                    if not values:
                        unmapped.append(int(uid))
                    elif any(value not in {"background", "unlabelled", "unlabeled"} for value in values):
                        color = _SEMANTIC_PALETTE[class_index % len(_SEMANTIC_PALETTE)]
                        class_index += 1
                colors[key] = list(color)
                rgb[arr == uid] = color
            # Preserve the annotator's labels, including reserved and unseen IDs,
            # alongside the palette actually used for pixels in this frame.
            with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as stream:
                json.dump({"idToLabels": labels, "idToColor": colors, "unmappedIds": unmapped}, stream, indent=2)
            Image.fromarray(rgb, "RGB").save(path)
            if unmapped:
                warning = f"{len(unmapped)} semantic IDs have no label metadata; shown black (see JSON unmappedIds)"
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
        return warning
    except Exception as exc:
        return f"could not save semantic diagnostics: {exc}"


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
    features=[
        {"id": "FET035_RenderProducts.RTX.0-1-0", "version": "*"},
    ],
    name="semantic_aov_output",
    description=(
        "Verifies that Replicator annotators for semantic RenderVars "
        "(sourceName starting with 'semantic') are registered and produce "
        "non-empty output within max_capture_steps Replicator frames. Each render "
        "product is destroyed after it is checked."
    ),
    expected_video=(
        "One PNG per semantic annotator per RenderProduct, written to the run "
        "output directory. SemanticSegmentation output is colorized by class ID "
        "using idToLabels; background and unlabelled pixels are black. A JSON "
        "sidecar records idToLabels, idToColor, and unmappedIds. Unmapped IDs "
        "remain black and produce a diagnostic warning. "
        "Values may be all-zero when no prims carry SemanticAPI labels — this is "
        "expected for minimal fixtures."
    ),
    version="0.1.2",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        # A new render product may not deliver on its first frame; step up to
        # this many frames before reporting its output as unavailable.
        "max_capture_steps": 10,
    },
)
async def test_semantic_aov_output(ctx):
    """Semantic AOV Replicator output check."""
    import omni.replicator.core as rep

    try:
        await _check_semantic_aov_output(ctx)
    finally:
        primary_error = sys.exc_info()[1]
        try:
            rep.orchestrator.stop()
        except BaseException:
            if primary_error is None:
                raise


async def _check_semantic_aov_output(ctx):
    import omni.replicator.core as rep
    import omni.usd

    asset_handle = ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    composed_root = asset_handle.prim_path
    await ctx.settle()

    # load_asset() references only the defaultPrim subtree, so /Render prims
    # are invisible in the composed stage. Open the raw file directly to
    # traverse all prims including /Render.
    from pxr import Usd, UsdGeom

    raw_stage = Usd.Stage.Open(ctx.asset_path)
    default_prim = raw_stage.GetDefaultPrim()
    default_prim_path = default_prim.GetPath() if default_prim else None
    composed_stage = omni.usd.get_context().get_stage()

    rps_with_semantic = _get_render_products_with_semantic_vars(raw_stage)
    if not rps_with_semantic:
        ctx.skip("No RenderProducts with semantic RenderVars found in asset.")
        return

    ctx.add_metric("semantic_rp_count", len(rps_with_semantic))

    # --- Replicator runtime check ---
    ctx.step("Replicator check: attach semantic annotators and verify output")

    annotator_failures = []
    data_failures = []
    max_frames_to_data = 0
    max_capture_steps = max(1, int(ctx.config["max_capture_steps"]))

    for rp_prim, raw_cam_path, resolution, semantic_names in rps_with_semantic:
        rp_name = rp_prim.GetPath().name

        # The framework loads the defaultPrim subtree at a different path prefix
        # than the raw asset, so remap the camera path by its path relative to the
        # defaultPrim. Matching on prim name alone is ambiguous when several
        # cameras share a name.
        cam_path = composed_path(raw_cam_path, default_prim_path, composed_root)
        cam_prim = composed_stage.GetPrimAtPath(cam_path) if cam_path else None
        if cam_prim is None or not cam_prim.IsValid() or not cam_prim.IsA(UsdGeom.Camera):
            annotator_failures.append(f"{rp_name}: camera '{raw_cam_path}' not found in composed stage")
            continue

        # Copy-construct a Replicator RP mirroring the authored camera and
        # resolution. This confirms the authored camera path is valid and
        # renderable, and that each semantic sourceName maps to a registered
        # Replicator annotator (RP.003 cross-check).
        rep_rp = None
        writer = None
        try:
            try:
                rep_rp = rep.create.render_product(cam_path, resolution)
                rep_rp_path = rep_rp.path if hasattr(rep_rp, "path") else str(rep_rp)
            except Exception as exc:
                raise RuntimeError(f"{rp_name}: render product creation failed") from exc

            # The raw SemanticSegmentation AOV exposes IDs without label metadata.
            # Replicator's public annotator pairs the pixels with idToLabels.
            source_to_annotator = {
                name: "semantic_segmentation" if name == "SemanticSegmentation" else name
                for name in semantic_names
            }
            annotator_names = list(dict.fromkeys(source_to_annotator.values()))
            writer = attach_frame_writer(rep, rep_rp_path, annotator_names, rp_name)

            # A new render product may not deliver on its first frame, so step
            # until every annotator has output, up to max_capture_steps. All-zero
            # output is valid for semantic data, so only absent output is waited for.
            arrays, frames_used = await step_until_ready(
                rep, writer, annotator_names, max_capture_steps, rp_name, lambda name, arr: not waiting_for_data(arr)
            )
            max_frames_to_data = max(max_frames_to_data, frames_used)
            if frames_used > 1:
                ctx.log(f"  {rp_name}: needed {frames_used} frames before output was ready")

            for name, annotator_name in source_to_annotator.items():
                arr = arrays[annotator_name]
                problem = availability_problem(arr)
                if problem is not None:
                    raise RuntimeError(f"{rp_name} '{name}': semantic readback failed") from availability_error(
                        "semantic", problem, frames_used
                    )
                ctx.log(f"  PASS {rp_name} '{name}': shape={arr.shape} dtype={arr.dtype}")
                out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
                warning = _save_annotator_image(arr, rp_name, name, out_dir, payload=writer.latest.get(annotator_name))
                if warning:
                    ctx.log(f"  WARN {rp_name} '{name}': {warning}")
        finally:
            if rep_rp is not None:
                release_render_product(ctx, rp_name, rep_rp, writer)

    ctx.add_metric("annotator_failures", len(annotator_failures))
    ctx.add_metric("data_failures", len(data_failures))
    ctx.add_metric("max_frames_to_data", max_frames_to_data)

    all_failures = annotator_failures + data_failures
    if all_failures:
        ctx.fail(
            f"Replicator runtime check failed ({len(all_failures)} issue(s)):\n"
            + "\n".join(f"  {f}" for f in all_failures)
        )
        return

    ctx.log("Replicator check PASSED: all semantic annotators returned non-empty data.")

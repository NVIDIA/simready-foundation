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
"""Shared machinery for the FET011 segmentation-AOV tests.

Named with a leading underscore so test discovery skips it: only modules that declare an
``@test`` belong in the walk.

Everything Kit-specific is imported inside a function. Discovery catches ImportError and drops
the importing module without a word, so a module-level ``import omni.replicator.core`` here
would silently remove both tests from ``--list-tests`` on any machine without Kit.

Three constraints this framework imposes on Replicator, each found by crashing into it:

1. ``rep.orchestrator.step()`` is legal only in a standalone SimulationApp workflow. Inside a
   live Kit app it raises and the test fails. Use ``step_async``.
2. ``rep.create.render_product()`` alongside the framework's viewport product kills the process
   outright, with no Python traceback. Attach annotators to the viewport's existing product.
3. **The orchestrator can be stepped once per session.** A second ``step_async`` crashes the
   process whatever comes between the two, settle or no settle, stage edits or none. This is
   why the labelled and stripped measurements live in separate tests rather than one
   before/after test: each gets a fresh session, and each steps exactly once.

Only the orchestrator fills the annotator. Advancing frames with ``ctx.settle()`` leaves it at
shape ``(0,)`` before the first step, and returns a stale buffer after it.
"""
from __future__ import annotations

SEMANTIC_SCHEMA_PREFIXES = ("SemanticsLabelsAPI:", "SemanticsAPI:")


def label_source_prims(prim):
    """Every prim SL.001 can resolve a label from, for one renderable gprim.

    The prim and its ancestors, its computed bound material and that material's ancestors, and
    its GeomSubset children. Mirrors the offline validator, so a strip removes exactly the
    sources SL.001 counts -- including a bound material living outside the asset subtree.
    """
    from pxr import UsdGeom, UsdShade

    sources = []
    cur = prim
    while cur and not cur.IsPseudoRoot():
        sources.append(cur)
        cur = cur.GetParent()
    material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)
    if material:
        cur = material.GetPrim()
        while cur and not cur.IsPseudoRoot():
            sources.append(cur)
            cur = cur.GetParent()
    for child in prim.GetChildren():
        if child.IsA(UsdGeom.Subset):
            sources.append(child)
    return sources


def strip_semantics(stage, under):
    """Remove every semantics schema from the label sources under ``under``, in the session
    layer. Returns the number of prims edited.

    Reads ``prim.GetAppliedSchemas()`` rather than the added or explicit list items. The
    standard USD apply path prepends, and prepended entries are absent from
    ``GetAddedOrExplicitItems()``, so reading those alone makes the strip a silent no-op on most
    real assets and the test reports a false failure.
    """
    from pxr import Sdf, Usd, UsdGeom

    targets = {}
    for prim in Usd.PrimRange(under):
        gprim = UsdGeom.Gprim(prim)
        if not gprim:
            continue
        if gprim.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
            continue
        for source in label_source_prims(prim):
            targets[source.GetPath()] = source

    edited = 0
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for prim in targets.values():
            if not prim.GetMetadata("apiSchemas"):
                continue
            applied = list(prim.GetAppliedSchemas())
            kept = [s for s in applied if not s.startswith(SEMANTIC_SCHEMA_PREFIXES)]
            if len(kept) != len(applied):
                listop = Sdf.TokenListOp()
                listop.explicitItems = kept
                prim.SetMetadata("apiSchemas", listop)
                edited += 1
    return edited


def as_rgb8(array):
    """Coerce annotator output to an HxWx3 uint8 image."""
    import numpy as np

    a = np.asarray(array)
    if a.ndim == 3 and a.shape[-1] >= 3:
        a = a[..., :3]
    elif a.ndim == 2:
        a = np.stack([a] * 3, -1)
    if a.dtype != np.uint8:
        a = (255 * (a.astype("float64") / (float(a.max()) or 1))).astype("uint8")
    return a


def annotator_array(annotator):
    """Unwrap annotator output, which may be an array or a dict carrying one."""
    import numpy as np

    data = annotator.get_data()
    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif data:
            data = next(iter(data.values()))
        else:
            raise ValueError("semantic_segmentation annotator returned an empty dict")
    return np.asarray(data)


def segmented_coverage(segmentation):
    """Fraction of pixels outside the single most common colour.

    Measured this way rather than against a known background colour because the AOV's colour
    assignment is not stable between runs, so nothing may depend on which colour appears.
    """
    import numpy as np

    flat = as_rgb8(segmentation).reshape(-1, 3)
    _, counts = np.unique(flat, axis=0, return_counts=True)
    return float(flat.shape[0] - counts.max()) / flat.shape[0]


async def build_scene(ctx):
    """Load the asset and frame it, returning the asset prim.

    Uses the framework's own scene helpers. Authoring a camera and light directly, as the
    standalone version of this benchmark did, leaves the framework's viewport pointing
    somewhere else.
    """
    cfg = ctx.config
    ctx.scene.load_asset(ctx.asset_path, timeout=int(cfg["asset_load_timeout"]))

    stage = ctx.scene.stage
    target = stage.GetPrimAtPath(ctx.scene.asset.prim_path)
    if not target or not target.IsValid():
        ctx.fail(
            "Asset prim %s did not load.\n\nHow to fix:\n"
            "- Confirm the USD file opens and its references resolve.\n"
            "- Check the asset declares a defaultPrim." % ctx.scene.asset.prim_path
        )
        return None, None

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(1, 1, 1)
    room.hide_ground()
    ctx.scene.lighting.add_dome(intensity=1000.0)
    ctx.scene.auto_frame_camera(padding=float(cfg["camera_padding"]))
    await ctx.settle(frames=int(cfg["settle_frames"]))
    return stage, target


async def read_segmentation(ctx, subframes):
    """Attach the segmentation annotator, step the orchestrator once, and read the buffer.

    One step, and only one: see the module docstring. The annotator is detached before
    returning so nothing is left attached to the framework's render product.
    """
    import omni.kit.viewport.utility as vp_util
    import omni.replicator.core as rep

    render_product_path = vp_util.get_active_viewport().render_product_path
    annotator = rep.AnnotatorRegistry.get_annotator("semantic_segmentation", init_params={"colorize": True})
    annotator.attach(render_product_path)
    try:
        await rep.orchestrator.step_async(rt_subframes=int(subframes))
        return annotator_array(annotator)
    finally:
        try:
            annotator.detach()
        except Exception:  # noqa: BLE001
            pass


def save_image(ctx, array, name, role="normal"):
    """Write an image into the test's capture directory and register it on the result."""
    import os

    from PIL import Image

    captures = os.path.join(ctx.output_dir, "captures")
    os.makedirs(captures, exist_ok=True)
    path = os.path.join(captures, "%s.png" % name)
    Image.fromarray(as_rgb8(array)).save(path)
    ctx.attach_media(path, role=role)
    return path


SHARED_CONFIG = {
    "camera_padding": 1.2,
    "settle_frames": 5,
    "asset_load_timeout": 30,
    # Path-traced subframes for the single orchestrator step.
    "render_subframes": 4,
}

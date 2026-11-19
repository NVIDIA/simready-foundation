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

Named with a leading underscore so test discovery skips this pure helper.
Non-underscore helpers are scanned too and need the same qualified import context.

Everything Kit-specific is imported inside a function so host discovery can
register these tests without importing Replicator. Current discovery warns
about unavailable Kit-only dependencies and raises for required helper-import
failures; missing imports are not silently ignored or evidence of applicability.

Historical native observations that motivated this implementation, not universal
constraints qualified on every current Kit/Replicator runtime:

1. ``rep.orchestrator.step()`` is legal only in a standalone SimulationApp workflow. Inside a
   live Kit app it raises and the test fails. Use ``step_async``.
2. ``rep.create.render_product()`` alongside the framework's viewport product kills the process
   outright, with no Python traceback. Attach annotators to the viewport's existing product.
3. A second ``step_async`` crashed the historical engine process even after settling
   or stage edits. The current procedures each step once on their own fresh stage;
   generic batch/per-asset policies may still reuse the process. Their registrations
   do not guarantee separate engine sessions. A reused-session orchestrator failure
   requires current native qualification and is not itself an asset verdict.

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


def _has_complete_semantics_inspection(stage, under, ctx):
    """Qualify actual label and binding dependencies, without expanding stripping."""
    from pxr import Usd, UsdGeom, UsdShade
    from simready.foundation.tier_core.runtime_tests._assessment import (
        _has_complete_prim_ancestry,
        _has_complete_relationship_sources,
        _log_applicability_gap,
    )

    def ancestry(prim):
        return _has_complete_prim_ancestry(stage, prim, ctx=ctx)

    def binding_rels(prim):
        api = UsdShade.MaterialBindingAPI(prim)
        for purpose in (UsdShade.Tokens.allPurpose, UsdShade.Tokens.full):
            direct = api.GetDirectBindingRel(materialPurpose=purpose)
            if direct and direct.HasAuthoredTargets():
                yield direct, False
            for rel in api.GetCollectionBindingRels(materialPurpose=purpose):
                if rel.HasAuthoredTargets():
                    yield rel, True

    def resolved_targets(rel):
        if not _has_complete_relationship_sources(stage, rel, ctx=ctx):
            raise ValueError("unqualified relationship source dependencies")
        return list(rel.GetForwardedTargets())

    def collection_complete(collection, visiting=None):
        if not collection or not ancestry(collection.GetPrim()):
            return False
        path = collection.GetCollectionPath()
        visiting = set() if visiting is None else set(visiting)
        if path in visiting or not collection.Validate()[0] or collection.IsInExpressionMode():
            return False
        visiting.add(path)
        for rel in (collection.GetIncludesRel(), collection.GetExcludesRel()):
            if not rel:
                continue
            for target in resolved_targets(rel):
                if Usd.CollectionAPI.IsCollectionAPIPath(target):
                    if not collection_complete(Usd.CollectionAPI.GetCollection(stage, target), visiting):
                        return False
                elif not target.IsPrimPath() or not ancestry(stage.GetPrimAtPath(target)):
                    return False
        return True

    def binding_complete(rel, is_collection):
        targets = resolved_targets(rel)
        if not targets:  # Explicit unbind has no hidden material source.
            return True
        if is_collection:
            if len(targets) != 2:
                return False
            binding = UsdShade.MaterialBindingAPI.CollectionBinding(rel)
            if not collection_complete(binding.GetCollection()):
                return False
        else:
            if len(targets) != 1:
                return False
            binding = UsdShade.MaterialBindingAPI.DirectBinding(rel)
        material = binding.GetMaterial()
        return bool(material) and ancestry(material.GetPrim())

    try:
        for prim in Usd.PrimRange(under, Usd.TraverseInstanceProxies()):
            gprim = UsdGeom.Gprim(prim)
            if not gprim or gprim.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
                continue
            for source in label_source_prims(prim):
                if not ancestry(source):
                    return False
            owner = prim
            while owner and not owner.IsPseudoRoot():
                for rel, is_collection in binding_rels(owner):
                    if not binding_complete(rel, is_collection):
                        return _log_applicability_gap(
                            ctx, "required material or collection binding dependencies are incomplete"
                        )
                owner = owner.GetParent()
            for child in prim.GetChildren():
                if not child.IsA(UsdGeom.Subset):
                    continue
                subset_material, subset_binding = UsdShade.MaterialBindingAPI(child).ComputeBoundMaterial(
                    materialPurpose=UsdShade.Tokens.full
                )
                if subset_material or subset_binding or any(binding_rels(child)):
                    # The historical stripper visits the Subset itself, not its
                    # bound material. Do not silently extend stripping behavior.
                    return _log_applicability_gap(ctx, "Subset material-source inspection is not established")
        return True
    except Exception:
        return _log_applicability_gap(ctx, "required semantic source or binding dependencies could not be queried")


def strip_semantics(stage, under):
    """Remove recognized semantics schemas from visited sources in the session layer.

    Traverse default/render Gprims including instance proxies. Inspect their
    ancestors, full-purpose bound materials and GeomSubset sources. A labelled
    instance source is made editable by de-instancing its enclosing instance
    inside the loaded asset in the session layer; source layers stay unchanged.
    An external proxy source that cannot be edited within this boundary is a
    setup error, not a proven absence of labels. Return the edited-prim count.

    Reads ``prim.GetAppliedSchemas()`` rather than the added or explicit list items. The
    standard USD apply path prepends, and prepended entries are absent from
    ``GetAddedOrExplicitItems()``, so reading those alone makes the strip a silent no-op on most
    real assets and the test reports a false failure. Returns edited-prim count.
    """
    from pxr import Sdf, Usd, UsdGeom

    def collect_targets():
        targets = {}
        for prim in Usd.PrimRange(under, Usd.TraverseInstanceProxies()):
            gprim = UsdGeom.Gprim(prim)
            if not gprim or gprim.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
                continue
            for source in label_source_prims(prim):
                targets[source.GetPath()] = source
        return targets

    edited = 0
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        deinstanced = set()
        while True:
            targets = collect_targets()
            owners = {}
            for prim in targets.values():
                if not prim.IsInstanceProxy() or not any(
                    schema.startswith(SEMANTIC_SCHEMA_PREFIXES) for schema in prim.GetAppliedSchemas()
                ):
                    continue
                owner = None
                ancestor = prim.GetParent()
                while ancestor and not ancestor.IsPseudoRoot():
                    if ancestor.IsInstance() and not ancestor.IsInstanceProxy():
                        owner = ancestor
                    ancestor = ancestor.GetParent()
                if owner is None or not owner.GetPath().HasPrefix(under.GetPath()):
                    raise RuntimeError("FET011 cannot edit semantic instance-proxy sources outside the loaded asset")
                owners[str(owner.GetPath())] = owner
            if not owners:
                break
            for path, owner in owners.items():
                if path in deinstanced or not owner.SetInstanceable(False):
                    raise RuntimeError(f"FET011 could not make semantic source editable in the session layer: {path}")
                deinstanced.add(path)
                if stage.GetPrimAtPath(path).IsInstance():
                    raise RuntimeError(f"FET011 semantic source remains instanceable after session override: {path}")
            # Recollect after composition changes; never author through stale proxy handles.
        for prim in targets.values():
            if not prim.GetMetadata("apiSchemas"):
                continue
            applied = list(prim.GetAppliedSchemas())
            kept = [s for s in applied if not s.startswith(SEMANTIC_SCHEMA_PREFIXES)]
            if len(kept) != len(applied):
                listop = Sdf.TokenListOp()
                listop.explicitItems = kept
                if not prim.SetMetadata("apiSchemas", listop):
                    raise RuntimeError(f"FET011 could not strip semantic source: {prim.GetPath()}")
                edited += 1
    return edited


def _required_aov(array):
    """Keep required AOV identities in their original real numeric dtype."""
    import numpy as np

    try:
        a = np.asarray(array)
        if (
            a.dtype.kind not in "iuf"
            or a.size == 0
            or not np.isfinite(a).all()
            or (a < 0).any()
            or not (a.ndim == 2 or (a.ndim == 3 and a.shape[-1] >= 3))
            or any(size <= 0 for size in a.shape)
        ):
            raise ValueError("requires a finite nonempty real numeric 2D or RGB image")
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError("Required semantic-segmentation AOV is unavailable or invalid") from error
    return a


def as_rgb8(array):
    """Convert validated evidence for presentation only, never identity counts."""
    import numpy as np

    a = _required_aov(array)
    if a.ndim == 3 and a.shape[-1] >= 3:
        a = a[..., :3]
    elif a.ndim == 2:
        a = np.stack([a] * 3, -1)
    if a.dtype != np.uint8:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
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

    observed = _required_aov(segmentation)
    # Quantizing to a display image can collapse distinct label IDs/colors,
    # making populated evidence look blank. RGB alpha remains excluded as in
    # the existing uint8 predicate; two-dimensional IDs stay exact.
    flat = observed.reshape(-1) if observed.ndim == 2 else observed[..., :3].reshape(-1, 3)
    _, counts = np.unique(flat, axis=None if observed.ndim == 2 else 0, return_counts=True)
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
    asset_path = getattr(getattr(ctx.scene, "asset", None), "prim_path", None)
    if not asset_path:
        raise RuntimeError("Required semantic scene asset path is unavailable after load_asset")
    target = stage.GetPrimAtPath(asset_path)
    if not target or not target.IsValid():
        raise RuntimeError("Required semantic scene asset prim did not load: %s" % asset_path)

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(1, 1, 1)
    room.hide_ground()
    ctx.scene.lighting.add_dome(intensity=1000.0)
    ctx.scene.auto_frame_camera(padding=float(cfg["camera_padding"]))
    await ctx.settle(frames=int(cfg["settle_frames"]))
    return stage, target


def _record_required_annotator_cleanup_failure(ctx, primary):
    """Retire an unsafe native attachment without replacing its first cause."""
    try:
        session = getattr(ctx, "_engine_session", None)
        callback = getattr(session, "record_required_cleanup_failure", None)
        if callable(callback):
            callback("Required semantic-segmentation annotator cleanup failed.")
    except BaseException as diagnostic_error:
        from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
            note_secondary_error,
        )

        note_secondary_error(
            primary,
            lambda diagnostic_error=diagnostic_error: (
                "Semantic cleanup health reporting also failed (%s)." % type(diagnostic_error).__name__
            ),
        )


async def read_segmentation(ctx, subframes):
    """Attach the segmentation annotator, step the orchestrator once, and read the buffer.

    One step per procedure: see the module docstring. Detach is attempted after
    every attach attempt, including partial setup, read errors and cancellation.
    Detach-only failures are execution errors; an earlier cause remains primary
    even if optional SDK exception notes cannot be formatted or delivered.
    """
    import omni.kit.viewport.utility as vp_util
    import omni.replicator.core as rep

    render_product_path = vp_util.get_active_viewport().render_product_path
    annotator = rep.AnnotatorRegistry.get_annotator("semantic_segmentation", init_params={"colorize": True})
    primary = None
    try:
        # An attach attempt can partially acquire native resources before
        # raising. Detach is required even when setup or observation fails.
        annotator.attach(render_product_path)
        await rep.orchestrator.step_async(rt_subframes=int(subframes))
        return annotator_array(annotator)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            annotator.detach()
        except BaseException as error:
            _record_required_annotator_cleanup_failure(ctx, primary if primary is not None else error)
            if primary is not None:
                from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
                    note_secondary_error,
                )

                note_secondary_error(
                    primary, lambda error=error: f"Required semantic annotator cleanup also failed: {error}"
                )
            elif isinstance(error, Exception):
                raise RuntimeError("Required semantic annotator cleanup failed") from error
            else:
                raise


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

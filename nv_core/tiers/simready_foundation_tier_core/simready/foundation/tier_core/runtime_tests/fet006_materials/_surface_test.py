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

"""The body every surface-render test in this family is built from.

``run_coverage_test`` measures bound-material pixel coverage with one requested
render context. It does not compare separately pinned contexts; an MDL/MaterialX
pin can still render a universal fallback and a bound shader that fails to
evaluate can still count as covered.

Three probe renders share the requested render context and scene framing:

``strongerThanDescendants``  the magenta control wins everywhere, so every pixel
                             the asset draws comes back flat magenta. The
                             silhouette, and the denominator.
``weakerThanDescendants``    asset bindings win over inherited magenta and
                             cyan controls in two separate stages. Only pixels
                             following both colors, inside the silhouette,
                             form the uncovered-color proxy.

Coverage is ``1 - uncovered / silhouette``. Controls bind to a test-owned
ancestor, preserving authored bindings on the asset root and descendants.

An unchanged authored magenta or cyan surface does not follow both controls.
This is still color classification, not binding identity or shader-evaluation
proof; inspect original appearance and resolved bindings before source repair.

Each pass builds its own stage. Binding both strengths in turn on one live stage
does not resolve the way USD says it should: see ``_render_pass``.

A MATERIAL PUBLISHED ON ITS OWN
-------------------------------
An asset with no renderable geometry has nothing of its own to cover. The scene
binds each of its materials to a test sphere (``_scene.add_test_spheres``) and
the test renders those with the requested context. Only the strong pass runs:
it supplies the reported frame of each material and confirms the spheres were
framed. Coverage is not measured, because the test authored every sphere's
binding and no pixel can show the weak control. ``openpbr_renders`` still reads
the MaterialX log, the one check here that can fail a material on its content.

WHY NOT A FALLBACK COLOUR
-------------------------
Earlier shapes asked whether the asset came back on a colour the *renderer*
chose. Measuring the red-dominant share of the silhouette fails a red asset --
the reference joystick reads 25.2% while rendering correctly. Binding a control
with no surface outputs and comparing against the neutral grey Kit paints has
the same defect one colour over, and grey is commoner in real content than red.

The control's magenta is authored, and it has a surface on all three
contexts, so it resolves under whichever list is pinned. Nothing in the gate is a
colour the renderer picked, which is also what makes the shape portable to a
runtime that is not Kit.

WHAT IS NOT MEASURED HERE, AND WHERE IT LIVES
---------------------------------------------
**Presence** belongs to static validation. ``VM.PS.002`` (from
``FET006_Materials`` 0-2-0), ``VM.MDL.003`` (from ``FET006_Materials.MDL``
0-2-0) and ``VM.PBR.001`` require the material a renderable Gprim renders with
to connect the surface, and ``VM.PBR.003`` requires its ``info:id`` to name a
declared node. A benchmark that re-asked would duplicate them. Normal planning consumes prior validation
evidence; this test does not rerun validation. Forced-feature diagnostics can
run with absent or failed validation, so these requirements need separate proof.

**Whether a bound material evaluated** is not visible to this measurement: a
shader that fails to resolve still wins over the weak control and counts as
covered. Launching Kit with
``--/persistent/app/material/materialx/validate=true`` logs
``[Error] [rtx.materialx.plugin] Unable to create document for material:
'<path>'`` with the prim and the reason. Measured: without it, a material naming
a nodedef that does not exist renders flat red and Kit logs no error at all,
across 273 warnings. It is a ``/persistent`` setting read at startup, so no test
can switch it on -- it belongs to how the runner launches Kit, and it is
MaterialX-only.

WHAT THIS REPLACED
------------------
The OpenPBR and MDL tests rendered twice -- once pinned to their own context,
once to the universal one -- and required the frames to differ. The universal
context is ``FET_006_STANDARD``'s UsdPreviewSurface, so the verdict depended on
a different feature: an asset with both, authored so the preview is a
faithful stand-in for the final surface, converged and failed, while an asset
with no preview surface fell through to the default material, differed, and
passed. It also rewarded divergence between the two surfaces, which is the
opposite of what a preview surface is for.
"""

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade
from simready.foundation.tier_core.runtime_tests._assessment import (
    _has_complete_asset_composition,
    _has_complete_relationship_sources,
    not_applicable,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
    record_required_cleanup_failure,
)
from simready.foundation.tier_core.runtime_tests.fet006_materials import (
    _context,
    _logs,
    _pixels,
    _scene,
    surfaces,
)

# Outside the asset, so nothing scoped to the asset root inventories it.
PROBE_SCOPE = "/SimReadySurfaceProbe"

# Magenta: two channels at full and one at zero. A secondary survives a
# specular sheen better than a primary under a dominance test, because the
# sheen is white and has two channels to erode rather than one.
PROBE_COLOR = (1.0, 0.0, 1.0)
MAGENTA_CHANNELS = (0, 2)
SECOND_PROBE_COLOR = (0.0, 1.0, 1.0)
SECOND_PROBE_CHANNELS = (1, 2)

# What a coverage failure asks the author to fix. A pixel counts as uncovered only where
# the geometry resolves no material of the asset's, so the fix is a binding, whatever the
# render context. The run appends a bullet that restates VM.MAT.001, so these lead with
# what that requirement misses.
BINDING_FIX_HINT = (
    "- Where a Gprim has materialBind GeomSubset children, faces outside every subset "
    "render with the material the Gprim itself resolves, and VM.MAT.001 checks only the "
    "subsets. Bind the Gprim itself, or make the materialBind subsets a partition of its "
    "faces.\n"
    "- A binding authored only for the preview purpose does not reach a final render; "
    "bind through material:binding or material:binding:full."
)


def build_probe(stage, color=PROBE_COLOR):
    """A flat control-color material with a surface on all three contexts.

    All three, because each pass pins a different list and the silhouette has
    to be cut the same way under every one of them. With a surface on every
    context the probe resolves the pinned context directly, and does not depend
    on the universal fallback ``_context`` measured.
    """
    UsdGeom.Scope.Define(stage, PROBE_SCOPE)
    material = UsdShade.Material.Define(stage, PROBE_SCOPE + "/Flat")

    preview = UsdShade.Shader.Define(stage, PROBE_SCOPE + "/Flat/Preview")
    preview.CreateIdAttr("UsdPreviewSurface")
    preview.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    preview.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    preview.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(preview.ConnectableAPI(), "surface")

    mdl = UsdShade.Shader.Define(stage, PROBE_SCOPE + "/Flat/Mdl")
    mdl.CreateIdAttr("mdl:OmniPBR")
    mdl.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
    mdl.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    mdl.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    mdl.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(1.0)
    mdl.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(0.0)
    mdl.CreateInput("specular_level", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput("mdl").ConnectToSource(mdl.ConnectableAPI(), "out")

    mtlx = UsdShade.Shader.Define(stage, PROBE_SCOPE + "/Flat/Mtlx")
    mtlx.CreateIdAttr("ND_open_pbr_surface_surfaceshader")
    mtlx.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    mtlx.CreateInput("base_weight", Sdf.ValueTypeNames.Float).Set(1.0)
    mtlx.CreateInput("base_metalness", Sdf.ValueTypeNames.Float).Set(0.0)
    mtlx.CreateInput("specular_weight", Sdf.ValueTypeNames.Float).Set(0.0)
    mtlx.CreateInput("base_diffuse_roughness", Sdf.ValueTypeNames.Float).Set(0.0)
    mtlx.CreateOutput("out", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput("mtlx").ConnectToSource(mtlx.ConnectableAPI(), "out")
    return material


def paint(stage, root_path, strength=UsdShade.Tokens.strongerThanDescendants, color=PROBE_COLOR):
    """Bind a control to the caller's test-owned ancestor; return whether it took.

    ``strongerThanDescendants`` paints everything the asset draws, which is the
    silhouette. ``weakerThanDescendants`` lets any binding the asset authors win,
    so exposed control can show where an asset binding does not win. The
    two weak-color frames distinguish unchanged source colors from exposed
    control. The caller must not supply an authored asset-root binding site.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return False
    material = build_probe(stage, color)
    api = UsdShade.MaterialBindingAPI.Apply(root)
    # A purpose-specific source binding wins over an all-purpose binding even
    # when that binding is strong. Paint every standard purpose for the strong
    # silhouette; weak controls stay all-purpose so source-purpose resolution
    # is preserved rather than hidden by a purpose-specific ancestor control.
    purposes = (UsdShade.Tokens.allPurpose,)
    if strength == UsdShade.Tokens.strongerThanDescendants:
        purposes += (UsdShade.Tokens.full, UsdShade.Tokens.preview)
    for purpose in purposes:
        try:
            bound = api.Bind(material, bindingStrength=strength, materialPurpose=purpose)
        except Exception as error:
            raise RuntimeError(
                f"Required surface probe binding failed for material purpose {purpose or 'allPurpose'}"
            ) from error
        if not bound:
            raise RuntimeError(
                f"Required surface probe binding was rejected for material purpose {purpose or 'allPurpose'}"
            )
    return True


def deinstance(stage, root_path):
    """Clear ``instanceable`` from the asset root down. Returns how many were cleared.

    A material bound on a ``GeomSubset`` inside an instance is not overridden by an
    ancestor binding marked ``strongerThanDescendants``. USD resolves the ancestor's
    material for the subset and the renderer draws the subset's own, so the probe
    paints nothing at all, or only the meshes that carry no subsets: the silhouette
    comes back empty or partial and coverage is measured against the wrong
    denominator.

    Binding the probe per prim instead does not help. An instance proxy cannot be
    authored on, and inside an instance every Gprim and subset is one. The
    measurement stage is built per pass and thrown away, so it is de-instanced.

    Clearing an outer prim exposes inner instanceable prims that sat inside its
    prototype and invalidates descendant handles. Re-query one path at a time,
    author only in the disposable stage's session layer, and require composed
    progress so an ineffective write cannot trap the worker in this loop.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return 0
    predicate = Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    cleared = 0
    visited = set()
    while True:
        root = stage.GetPrimAtPath(root_path)
        if not root or not root.IsValid():
            raise RuntimeError(f"Required surface de-instancing lost its asset root: {root_path}")
        target = None
        for prim in Usd.PrimRange(root, predicate):
            if prim.IsInstance():
                target = prim.GetPath()
                break
        if target is None:
            return cleared
        if target in visited:
            raise RuntimeError(f"Required surface de-instancing made no composed progress at {target}")
        visited.add(target)
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            if not stage.GetPrimAtPath(target).SetInstanceable(False):
                raise RuntimeError(f"Required surface de-instancing write was rejected at {target}")
        observed = stage.GetPrimAtPath(target)
        if not observed or not observed.IsValid() or observed.IsInstance():
            raise RuntimeError(f"Required surface de-instancing made no composed progress at {target}")
        cleared += 1


def instances_under(stage, root_path):
    """How many prims under the root are still instances. Zero is the precondition.

    Read after ``deinstance``. ``ComputeBoundMaterial`` cannot stand in for this:
    it returns the probe for a subset inside an instance, correctly, while the
    renderer draws the subset's own material. USD agreeing is what let the fault
    go unnoticed, so the precondition is checked on the instancing directly.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return 0
    predicate = Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    return sum(1 for prim in Usd.PrimRange(root, predicate) if prim.IsInstance())


def stronger_bindings_under(stage, root_path):
    """Inventory stronger descendant bindings for diagnostics, not a verdict.

    A strong ancestor can override these legal bindings. Their presence alone
    does not demonstrate that the test-owned control loses; read its effective
    binding after authoring instead. USD resolution is not a renderer readback.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return []
    found = []
    for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        if prim == root:
            continue
        binding = UsdShade.MaterialBindingAPI(prim)
        relationship = binding.GetDirectBindingRel()
        if not relationship or not relationship.GetTargets():
            continue
        strength = UsdShade.MaterialBindingAPI.GetMaterialBindingStrength(relationship)
        if strength == UsdShade.Tokens.strongerThanDescendants:
            found.append(str(prim.GetPath()))
    return found


def _require_strong_probe(stage, root_path):
    """Qualify the strong control's composed binding, not authored flags alone."""
    root = stage.GetPrimAtPath(root_path)
    expected = Sdf.Path(PROBE_SCOPE + "/Flat")
    for prim in Usd.PrimRange(root):
        if not (prim.IsA(UsdGeom.Gprim) or prim.IsA(UsdGeom.Subset)):
            continue
        for purpose in (UsdShade.Tokens.allPurpose, UsdShade.Tokens.full, UsdShade.Tokens.preview):
            material, _relationship = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=purpose)
            if not material or material.GetPath() != expected:
                raise RuntimeError(
                    f"Required strong surface probe does not resolve at {prim.GetPath()} "
                    f"for material purpose {purpose or 'allPurpose'}; silhouette measurement is unqualified"
                )


def clear(stage, root_path):
    """Clear only the caller's test-owned ancestor binding."""
    root = stage.GetPrimAtPath(root_path)
    if root and root.IsValid():
        api = UsdShade.MaterialBindingAPI(root)
        first_error = None
        for purpose in (UsdShade.Tokens.allPurpose, UsdShade.Tokens.full, UsdShade.Tokens.preview):
            try:
                if not api.UnbindDirectBinding(materialPurpose=purpose):
                    raise RuntimeError(
                        f"Required surface probe cleanup was rejected for material purpose {purpose or 'allPurpose'}"
                    )
            except BaseException as error:
                if first_error is None:
                    first_error = error
                else:
                    note_secondary_error(
                        first_error, lambda error=error: f"Another surface binding cleanup failed: {error}"
                    )
        if first_error is not None:
            raise first_error


def readable(order):
    """An order list as a readable string, with the universal context named."""
    if order is None:
        return "unreadable"
    return ", ".join(o or "universal" for o in order)


def pin_took(effective, wanted):
    """Whether Kit now holds the list the test asked for.

    Read back from carb rather than assumed from the write, so a setting that
    did not take is reported as a failure to pin instead of being measured as a
    surface result. The whole list is compared, not just its head: the fallback
    entries are as load-bearing as the first one.
    """
    return effective is not None and list(effective) == list(wanted)


def _required_probe_mask(mask, label):
    """Validate observed mask structure; an empty boolean mask remains valid."""
    if mask is None:
        raise RuntimeError(
            f"Required {label} probe mask is unavailable; surface coverage was not measured. "
            "Check readable captures and Pillow/numpy availability inside the selected runtime."
        )
    try:
        shape = tuple(mask.shape)
        boolean = mask.dtype.kind == "b"
    except Exception as error:
        raise RuntimeError(f"Required {label} probe mask has no valid image structure") from error
    if len(shape) != 2 or any(dimension <= 0 for dimension in shape) or not boolean:
        raise RuntimeError(f"Required {label} probe mask must be a nonempty-shape 2D boolean image")
    return mask


def _validated_measurement_config(config):
    """Require usable acceptance and mask parameters before touching the scene."""
    import math
    from numbers import Real

    values = {}
    for key in ("min_material_coverage", "min_silhouette_pixels", "mask_dominance_ratio", "mask_dominance_floor"):
        value = config.get(key, _scene.SCENE_DEFAULTS[key])
        try:
            valid_real = not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise RuntimeError(
                f"Invalid surface measurement configuration: {key} must be a finite real number"
            ) from error
        if not valid_real:
            raise RuntimeError(f"Invalid surface measurement configuration: {key} must be a finite real number")
        if key in ("min_material_coverage", "mask_dominance_floor") and not 0.0 <= value <= 1.0:
            raise RuntimeError(f"Invalid surface measurement configuration: {key} must be in [0, 1]")
        if key == "mask_dominance_ratio" and value <= 0.0:
            raise RuntimeError(f"Invalid surface measurement configuration: {key} must be positive")
        if key == "min_silhouette_pixels":
            if value <= 0 or value != math.trunc(value):
                raise RuntimeError(f"Invalid surface measurement configuration: {key} must be a positive integer")
            values[key] = int(value)
        else:
            values[key] = float(value)
    return values


def _absent_context(
    ctx, context, owning_feature, present, on_spheres=False, *, stage, asset_root, sphere_count=0, resolved_scope=None
):
    """Skip a run where no material a final render resolves declares a surface for ``context``.

    On a material asset (``on_spheres``) those materials are every material the
    asset publishes, each bound to its test sphere.

    With no surface on the pinned context, Kit falls back to each material's universal
    surface (``_context`` records the measurement), so the run would measure the
    UsdPreviewSurface again and report it as coverage for ``context``. An asset with no
    surface for ``context`` has declined an optional feature, and a skipped test does not
    fail the feature. ``surfaces.declared_contexts`` makes the decision, at the ``full``
    purpose the static gates use.

    The decision is made here, not through ``ctx.precheck_failure``, which fails the run when
    the asset's validation claims a feature the test registers under. ``openpbr_renders``
    and ``mdl_renders`` also register under ``FET009_MaterialCoverage``, which an asset
    claims while declining OpenPBR or MDL, so a claim-based branch would fail exactly the
    assets this skip exists for. Whether a surface the asset is meant to have is missing is a static
    question, and ``VM.PBR.001`` and ``VM.MDL.003`` answer it in validation. A forced-feature
    run can reach this test without that validation, so the skip establishes only that the
    asset has no surface on ``context``.
    """
    asset_prim = stage.GetPrimAtPath(asset_root) if stage is not None else None
    if not _has_complete_asset_composition(stage, asset_prim, inspection_includes_instance_proxies=True):
        ctx.skip("Cannot establish absence of the requested material surface: asset composition is incomplete")
        return

    resolved_scope = resolved_scope or asset_root
    resolved_root = stage.GetPrimAtPath(resolved_scope)
    if not resolved_root or not resolved_root.IsValid():
        ctx.skip("Cannot establish absence of the requested material surface: resolved material scope is unavailable")
        return
    roots = [asset_prim] if resolved_root == asset_prim else [asset_prim, resolved_root]
    for scope_root in roots:
        for prim in Usd.PrimRange(scope_root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            for relationship in prim.GetRelationships():
                if relationship.GetName().startswith("material:binding") and not _has_complete_relationship_sources(
                    stage, relationship, ctx=ctx
                ):
                    ctx.skip(
                        "Cannot establish absence of the requested material surface: "
                        "a material binding source is incomplete"
                    )
                    return
    for material_prim in surfaces.full_bound_materials(stage, resolved_scope):
        material = UsdShade.Material(material_prim)
        output = material.GetSurfaceOutput(context) if context else material.GetSurfaceOutput()
        if output and output.GetAttr().GetConnections() and not output.HasConnectedSource():
            ctx.skip(
                "Cannot establish absence of the requested material surface: "
                "an authored surface source is unavailable"
            )
            return
    if next(surfaces.renderable_geometry(stage, asset_root), None) is None:
        if sphere_count != len(surfaces.published_materials(stage, asset_root)):
            ctx.skip("Cannot establish absence of the requested material surface: test sphere inventory is incomplete")
            return

    present_contexts = ", ".join(present) or "no context at all"
    static_requirement = "VM.PBR.001" if context == surfaces.MTLX else "VM.MDL.003"
    materials = (
        "None of the materials the asset publishes"
        if on_spheres
        else "No material that renderable geometry resolves at the full purpose"
    )
    message = (
        f"{materials} declares a surface for the "
        f"{surfaces.label_for(context)} render context, so Kit would render each material's universal "
        "surface in its place and this "
        f"test would measure that again. The asset has a surface on: {present_contexts}. "
        f"{owning_feature} is optional in the profiles that select it; {static_requirement} reports a "
        "surface the asset is meant to have and lacks."
    )
    ctx.add_metric("assessment_applicability", not_applicable("no_resolved_surface_for_context", message))
    ctx.skip(message)


async def run_coverage_test(ctx, context, requirement, fix_hint, read_materialx_log=False, owning_feature=None):
    """Measure bound-material pixel coverage with ``context`` requested.

    Three control renders use the same requested context and scene framing.

    ``strongerThanDescendants``  the control wins everywhere, so every pixel the
                                 asset draws comes back flat magenta. That is the
                                 silhouette, and the denominator.
    ``weakerThanDescendants``    asset bindings can win over inherited controls.
                                 A pixel must follow both magenta and cyan weak
                                 probes to count in the uncovered-color proxy.

    Coverage is ``1 - uncovered / silhouette``. Controls live on the test-owned
    enclosing wrapper, not on the source asset root, so source material opinions
    survive. Each pass builds its own stage because rebinding a live stage can
    leave stale native material assignments; ``_render_pass`` has the details.

    WHY MAGENTA AND NOT A FALLBACK COLOUR
    -------------------------------------
    An earlier shape asked whether the asset came back on Kit's default material,
    by measuring how much of the silhouette was red-dominant. That fails a red
    asset: the reference joystick reads 25.2% red-dominant while rendering
    correctly. Binding a control material with no surface outputs and comparing
    against the neutral grey Kit paints instead has the same defect one colour
    over, and grey is commoner in real content than red.

    The probe's magenta is authored rather than inferred, and it has a
    surface on all three contexts, so it resolves under whichever list is pinned.
    Nothing here compares against a colour the renderer chose.

    WHAT THIS DOES NOT MEASURE
    --------------------------
    Whether a material that *is* bound evaluated correctly. A shader that fails
    to resolve still wins over the weak control, so it counts as covered. That
    failure is caught by launching Kit with
    ``--/persistent/app/material/materialx/validate=true``, which logs
    ``[Error] [rtx.materialx.plugin] Unable to create document for material:
    '<path>'`` naming the prim and the reason. It is a ``/persistent`` setting
    read at startup, so a test cannot switch it on -- it belongs to how the
    runner launches Kit.

    Presence is not re-checked here. Static validation owns it: ``VM.PS.002``,
    ``VM.MDL.003`` and ``VM.PBR.001`` (the first two in the 0-2-0 and later FET006
    versions) require the material a renderable Gprim renders with to connect the
    surface, and ``VM.PBR.003`` requires its ``info:id`` to name a declared node.
    Normal planning consumes prior validation evidence; this test does not rerun
    validation. Forced-feature diagnostics can bypass absent or failed evidence, so
    coverage alone is not proof of those requirements.

    WHEN THE ASSET DECLARES NO SURFACE FOR THE CONTEXT
    --------------------------------------------------
    Passing ``owning_feature`` makes that case skip instead of measuring the
    universal surface Kit falls back to; ``_absent_context`` has the reasoning.
    The decision reads ``surfaces.declared_contexts``: the materials renderable
    geometry resolves at the ``full`` purpose, kept by path. It is recorded as the
    ``<context>_surface_contexts_declared`` metric. Left at None, the run measures
    whatever renders and records neither. ``openpbr_renders`` and ``mdl_renders``
    pass it. ``preview_surface_renders`` leaves it unset: the universal context has
    no fallback to measure twice, and ``FET009_MaterialCoverage`` depends on
    ``FET006_Materials`` 0-3-0, whose ``VM.PS.002`` requires the
    UsdPreviewSurface.

    WHEN THE ASSET HAS NO GEOMETRY
    ------------------------------
    Each of its materials is rendered on a test sphere and only the strong pass
    runs; the module docstring has the reasoning. The inventory and the skip
    decision read the spheres' bindings, which resolve every material the asset
    publishes. ``<context>_surface_test_spheres`` records how many spheres there
    were, and is zero for an asset with geometry of its own.
    """
    measurement_config = _validated_measurement_config(ctx.config)
    order = [context]
    name = surfaces.label_for(context)
    short = context or "universal"
    floor = measurement_config["min_material_coverage"]

    previous = _context.read_order()
    primary_error = None
    try:
        ctx.step("Rendering with the render-context list pinned to [%s]" % readable(order))
        rendered = await _render_pass(ctx, order, "%s_surface_pinned" % short, UsdShade.Tokens.strongerThanDescendants)
        if rendered.get("error"):
            _fail_pass(ctx, rendered, order, name, requirement)
            return

        stage, root = rendered["stage"], rendered["root"]
        # On a material asset the spheres are the renderable geometry, and their scope stands in
        # for the asset root wherever the question is which materials the frame resolves.
        spheres = rendered.get("spheres", 0)
        scope = rendered.get("scope", root)
        inventory = _scene.report_surface_inventory(ctx, stage, scope, "%s_surface" % short)
        present = sorted({c or "universal" for cs in inventory.values() for c in cs})
        ctx.add_metric("%s_surface_asset_root" % short, root)
        ctx.add_metric(f"{short}_surface_test_spheres", spheres)
        ctx.add_metric("%s_surface_contexts_present" % short, ", ".join(present) or "none")
        ctx.add_metric("%s_surface_render_context_order" % short, readable(rendered["effective"]))

        if owning_feature:
            declared = sorted(c or "universal" for c in surfaces.declared_contexts(stage, scope))
            ctx.add_metric(f"{short}_surface_contexts_declared", ", ".join(declared) or "none")
            if (context or "universal") not in declared:
                _absent_context(
                    ctx,
                    context,
                    owning_feature,
                    declared,
                    on_spheres=bool(spheres),
                    stage=stage,
                    asset_root=root,
                    sphere_count=spheres,
                    resolved_scope=scope,
                )
                return

        ctx.add_metric("%s_surface_deinstanced_prims" % short, rendered.get("deinstanced", 0))
        instances_left = rendered.get("instances_left", 0)
        ctx.add_metric("%s_surface_instances_remaining" % short, instances_left)
        stronger = rendered.get("stronger") or []
        ctx.add_metric("%s_surface_stronger_bindings" % short, len(stronger))

        silhouette_mask = _required_probe_mask(rendered["mask"], "strong silhouette")
        silhouette = _pixels.mask_size(silhouette_mask)
        ctx.add_metric("%s_surface_silhouette_pixels" % short, silhouette)
        minimum = measurement_config["min_silhouette_pixels"]
        if silhouette < minimum:
            raise RuntimeError(
                "The %s %d pixel(s) of flat magenta when the control "
                "material is bound over it, below the %d needed to measure "
                "anything.\n"
                "\n"
                "Measurement setup guidance (not an asset-cause assessment):\n"
                "- Check the camera framed the object. The run auto-frames on "
                "the asset bounds and an empty bound produces this.\n"
                "- Check the asset has renderable geometry of default or render "
                "purpose that is not authored invisible. An asset with no "
                "geometry needs a Material for the test to render on a test "
                "sphere." % ("test spheres cover" if spheres else "asset covers", silhouette, minimum)
            )

        if spheres:
            if read_materialx_log and not _report_materialx(ctx, root, short, name):
                return
            ctx.log(
                f"The asset has no renderable geometry, so its {spheres} material(s) were "
                "rendered on test spheres with the render-context list pinned to "
                f"[{readable(rendered['effective'])}]. The reported frame shows each material "
                "as Kit rendered it. Coverage is not measured: the test bound every sphere "
                "itself, so no pixel can show the control. The asset has a surface on: "
                f"{', '.join(present) or 'no surface at all'}."
            )
            return

        ctx.step("Rendering weak magenta and cyan controls without replacing source asset bindings")
        weak = await _render_pass(
            ctx, order, "%s_surface" % short, UsdShade.Tokens.weakerThanDescendants, capture_reported=False
        )
        if weak.get("error"):
            _fail_pass(ctx, weak, order, name, requirement)
            return
        weak_mask = _required_probe_mask(weak["mask"], "weak magenta")
        # An authored magenta material matches the first probe in both frames.
        # Only pixels that follow both distinct weak probe colors are classified as exposed control.
        second_weak = await _render_pass(
            ctx,
            order,
            f"{short}_surface_cyan",
            UsdShade.Tokens.weakerThanDescendants,
            capture_reported=False,
            probe_color=SECOND_PROBE_COLOR,
            probe_channels=SECOND_PROBE_CHANNELS,
        )
        if second_weak.get("error"):
            _fail_pass(ctx, second_weak, order, name, requirement)
            return
        second_mask = _required_probe_mask(second_weak["mask"], "weak cyan")
        if weak_mask.shape != silhouette_mask.shape or second_mask.shape != silhouette_mask.shape:
            raise RuntimeError("Required surface probe masks have incompatible image shapes; coverage was not measured")
        exposed_control = _pixels.mask_intersection(_pixels.mask_intersection(silhouette_mask, weak_mask), second_mask)
        uncovered = _pixels.mask_size(exposed_control)
        if uncovered < 0:
            raise RuntimeError(
                f"Required surface probe masks could not be combined; coverage of the {name} surface is unknown"
            )

        # Intersection restricts exposed control to the strong silhouette.
        # Framing and shading still occur on separate stages; this is sampled
        # visible pixel coverage, not an exact inventory of material bindings.
        coverage = max(0.0, 1.0 - (uncovered / float(silhouette)))
        ctx.add_metric("%s_surface_uncovered_pixels" % short, uncovered)
        ctx.add_metric("%s_surface_coverage" % short, round(coverage, 5))

        if coverage < floor:
            ctx.fail(
                "With the render-context list pinned to [%s], %.1f%% of the "
                "asset's %d pixel silhouette does not follow both weak controls, "
                "below the %.0f%% required. The remaining %d pixel(s) came back "
                "as the control material, which is what a pixel the asset binds "
                "nothing to looks like.\n"
                "\n"
                "Three separately built stages share the scene and requested "
                "context. The controls bind above the asset, preserving its "
                "root and descendant bindings. This is a color proxy, not "
                "proof that every bound shader evaluated. The asset has a "
                "surface on: %s.\n"
                "\n"
                "This is %s.\n"
                "\n"
                "How to fix:\n"
                "%s\n"
                "- Check every renderable Gprim resolves a material, rather than "
                "the material being left in /Looks or bound only to invisible, "
                "guide or proxy geometry (VM.MAT.001)."
                % (
                    readable(order),
                    coverage * 100,
                    silhouette,
                    floor * 100,
                    uncovered,
                    ", ".join(present) or "no surface at all",
                    requirement,
                    fix_hint,
                )
            )
            return

        if read_materialx_log and not _report_materialx(ctx, root, short, name):
            return

        ctx.log(
            "With the render-context list pinned to [%s], %.1f%% of the asset's "
            "%d pixel silhouette does not follow both weak controls, and "
            "%d pixel(s) follow magenta and cyan within the strong silhouette. "
            "Three stages share the scene and requested context; inherited "
            "controls preserve source root and descendant bindings. This "
            "measurement is a color proxy. The asset has a surface on: %s.\n"
            "\n"
            "Coverage on its own does not establish that those materials "
            "evaluated. A shader that fails to resolve still wins over the weak "
            "control and counts as covered, which is what the MaterialX "
            "validation log reports separately."
            % (
                readable(rendered["effective"]),
                coverage * 100,
                silhouette,
                uncovered,
                ", ".join(present) or "no surface at all",
            )
        )
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            _context.restore(ctx, previous)
        except BaseException as restore_error:
            record_required_cleanup_failure(
                ctx, "Required surface render-context restoration failed.", primary_error or restore_error
            )
            if primary_error is not None:
                note_secondary_error(
                    primary_error,
                    lambda restore_error=restore_error: (
                        f"Surface render-context restoration also failed: {restore_error}"
                    ),
                )
            else:
                if not isinstance(restore_error, Exception):
                    raise
                raise RuntimeError("Required surface render-context restoration failed") from restore_error


async def _render_pass(
    ctx, order, label, strength, capture_reported=True, *, probe_color=PROBE_COLOR, probe_channels=MAGENTA_CHANNELS
):
    """Pin a render context, build a scene, and mask a test-owned color control.

    Returns a dict with ``frame``, ``mask``, ``effective``, ``stage``, ``root``,
    ``spheres`` (how many test spheres the scene built, zero for an asset with
    geometry) and ``scope`` (the spheres' scope, or the asset root), or one with
    ``error`` set when the pin or fixture root did not resolve. Required binding,
    image-mask or cleanup failures raise; none of those unobserved prerequisites
    establishes an asset coverage failure.

    Each pass builds its own stage. The scene has to be built after the pin
    because Kit reads the render-context list when a stage is attached, and the
    two strengths have to be measured on separate stages because rebinding on a
    live one does not resolve the way USD says it should. Measured on
    ``apple_a01``, whose single renderable Gprim resolves its own material under
    every purpose with the control bound weaker: on one stage the apple came
    back a blend of its own red and the control's magenta -- mean
    (0.866, 0.296, 0.426) against (0.852, 0.349, 0.349) with no control bound at
    all -- and 40% of the silhouette crossed the magenta threshold. Raising the
    settle from 8 frames to 40 moved it by 1%, so it is not accumulation. It
    appears under a pinned ``["mdl"]`` and not under the universal context,
    which points at the MDL material assignment surviving the rebind.
    """
    effective = await _context.pin(ctx, order)
    if not pin_took(effective, order):
        return {"error": "pin", "effective": effective}

    spheres = await _scene.build_scene(ctx) or 0
    stage = ctx.scene.stage
    root = _scene.asset_root(ctx)
    if not root:
        return {"error": "root", "effective": effective}

    binding_root = _scene.PROBE_ASSET_PARENT
    loaded = stage.GetPrimAtPath(root)
    wrapper = stage.GetPrimAtPath(binding_root)
    # The wrapper holds the asset and, for a material asset, the test spheres beside it.
    owned = [loaded] + ([stage.GetPrimAtPath(_scene.TEST_SPHERES)] if spheres else [])
    if not loaded or not wrapper or loaded.GetParent() != wrapper or list(wrapper.GetChildren()) != owned:
        return {"error": "root", "effective": effective}
    scope = _scene.TEST_SPHERES if spheres else root

    # The probe is bound above the asset root, so it only reaches the geometry once
    # nothing below is still an instance. See deinstance().
    deinstanced = deinstance(stage, root)
    instances_left = instances_under(stage, root)
    if instances_left:
        raise RuntimeError(
            f"Required surface measurement still has {instances_left} instance(s) under {root}; "
            "the disposable stage setup is unqualified, not an asset coverage failure"
        )
    stronger = stronger_bindings_under(stage, root)

    # The appearance frame precedes the control binding. Additional captured
    # probe frames show the control and must not be mistaken for source shading.
    frame = await _settled_frame(ctx, label) if capture_reported else None

    suffix = "silhouette" if strength == UsdShade.Tokens.strongerThanDescendants else "uncovered"
    mask = None
    primary_error = None
    try:
        if not paint(stage, binding_root, strength, color=probe_color):
            raise RuntimeError("Required surface probe binding was not established; coverage was not measured")
        await ctx.settle(count=2)
        if strength == UsdShade.Tokens.strongerThanDescendants:
            _require_strong_probe(stage, scope)
        control_frame = await ctx.capture_frame(label="%s_%s" % (label, suffix), allow_blank=True)
        mask = _pixels.dominant_mask(
            control_frame,
            probe_channels,
            float(ctx.config["mask_dominance_ratio"]),
            float(ctx.config["mask_dominance_floor"]),
        )
        _required_probe_mask(mask, suffix)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            clear(stage, binding_root)
        except BaseException as cleanup_error:
            record_required_cleanup_failure(
                ctx, "Required surface probe cleanup failed.", primary_error or cleanup_error
            )
            if primary_error is not None:
                note_secondary_error(
                    primary_error,
                    lambda cleanup_error=cleanup_error: f"Surface probe cleanup also failed: {cleanup_error}",
                )
            else:
                if not isinstance(cleanup_error, Exception):
                    raise
                raise RuntimeError("Required surface probe cleanup failed") from cleanup_error
    return {
        "frame": frame,
        "mask": mask,
        "effective": effective,
        "stage": stage,
        "root": root,
        "scope": scope,
        "spheres": spheres,
        "deinstanced": deinstanced,
        "instances_left": instances_left,
        "stronger": stronger,
    }


def _report_materialx(ctx, root, short, name):
    """Inspect captured scoped document-build errors; False when any were found.

    Absence of captured errors is not proof that every material evaluated.
    Coverage cannot identify that either: a shader that fails to resolve still
    wins over the weak control and can count as covered. The startup MaterialX
    validation setting enables these logs but does not make them a complete
    material-evaluation inventory.
    """
    enabled = _logs.validation_enabled()
    if not enabled:
        ctx.add_metric("%s_surface_materialx_validation" % short, "unreadable" if enabled is None else "off")
        ctx.log(
            "Whether the %s materials evaluated was not checked. Kit was "
            "launched without --/persistent/app/material/materialx/validate=true, "
            "so a material whose document it could not build is not named in the "
            "log and reads here the same as one that rendered. The setting is "
            "read at startup, so it belongs to how the runner launches Kit." % name
        )
        return True

    unresolved = _logs.unresolved_materials(root)
    ctx.add_metric("%s_surface_materialx_validation" % short, "on")
    ctx.add_metric("%s_surface_materialx_unresolved" % short, len(unresolved))
    if not unresolved:
        ctx.log(
            f"No scoped MaterialX document-build errors were captured under {root}; "
            "absence of captured errors is not proof that all materials evaluated."
        )
        return True

    ctx.fail(
        "Kit could not build a MaterialX document for %d material(s) under %s, "
        "so the %s network did not evaluate even where the geometry is shaded:\n"
        "%s\n"
        "\n"
        "Coverage does not see this. A shader that fails to resolve still wins "
        "over the weakly bound control, so those pixels count as covered and the "
        "object draws solid in the renderer's own colour.\n"
        "\n"
        "How to fix:\n"
        "- Check the shader's info:id names a node the target environment "
        "declares (VM.PBR.003).\n"
        "- Check every texture the network references resolves on disk.\n"
        "- The Kit log entry for each prim gives the reason its document could "
        "not be built." % (len(unresolved), root, name, "\n".join("  " + p for p in unresolved))
    )
    return False


async def _settled_frame(ctx, label):
    """The reported frame, re-captured until two in a row agree.

    Materials are not resident the moment a stage is attached and nothing in the
    test API reports when they are, so the first capture of a run can be of an
    object whose textures have not arrived. Measured on Isaac Sim 5.0, the first
    asset of a run captured its MDL pass at a mean of (0.344, 0.344, 0.344) and
    the same frame later in the same session at (0.159, 0.156, 0.159).

    Only the reported frame needs this. Coverage uses three control passes;
    each flat control material is resident immediately.
    """
    tolerance = float(ctx.config["frame_settle_tolerance"])
    attempts = int(ctx.config["frame_settle_attempts"])

    frame = await ctx.capture_frame(label=label, role="summary")
    previous = _pixels.frame_summary(frame)
    for attempt in range(attempts - 1):
        await ctx.settle()
        candidate = await ctx.capture_frame(label=label, role="summary")
        current = _pixels.frame_summary(candidate)
        frame = candidate
        if previous is None or current is None:
            break
        moved = max(abs(a - b) for a, b in zip(previous, current, strict=False))
        if moved <= tolerance:
            break
        ctx.log(
            "The frame was still changing after capture %d, by %.4f on the "
            "widest channel -- the asset's materials were not resident yet. "
            "Re-captured." % (attempt + 1, moved)
        )
        previous = current
    return frame


def _fail_pass(ctx, result, wanted, name, requirement):
    """Raise an execution error for unestablished render prerequisites."""
    if result["error"] == "pin":
        raise RuntimeError(
            "Kit's render-context list could not be set to [%s] for the %s "
            "surface. It reads [%s], so Kit would resolve some other surface "
            "and this run would measure the wrong one.\n"
            "\n"
            "How to fix:\n"
            "- Check %s is writable in this Kit build.\n"
            "- Kit persists this key to user.config.json on shutdown, and the "
            "framework's reset_render_settings does not unset a key a test "
            "added, so a value pinned by an earlier run can survive into this "
            "one."
            % (
                readable(wanted),
                name,
                readable(result["effective"]),
                _context.RENDER_CONTEXTS_SETTING,
            )
        )
    raise RuntimeError(
        "The asset's stage path could not be determined, so there is no root "
        "prim to bind the silhouette probe on and %s cannot be measured. The "
        "binding would either miss the asset or take the room with it.\n"
        "\n"
        "How to fix:\n"
        "- The path comes from the asset handle's prim_path, falling back to "
        "the scene handle's _asset_root_path. A framework rename of either "
        "lands here." % requirement
    )

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

``run_coverage_test`` measures how much of an asset is shaded by materials it
authored for one render context, and reads nothing outside that feature.

Two renders, identical but for the strength of one binding, both with the
render-context list pinned to the context under test:

``strongerThanDescendants``  the magenta control wins everywhere, so every pixel
                             the asset draws comes back flat magenta. The
                             silhouette, and the denominator.
``weakerThanDescendants``    any binding the asset authored wins, so magenta is
                             left only where the asset binds nothing.

Coverage is ``1 - uncovered / silhouette``, counted the same way in both frames.

Each pass builds its own stage. Binding both strengths in turn on one live stage
does not resolve the way USD says it should: see ``_render_pass``.

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
**Presence** belongs to the validator, which runs first. ``com.nvidia.usd.VM.PS.001``,
``VM.MDL.001`` and ``VM.PBR.001`` require the surface to exist and resolve, and
``VM.PBR.003`` requires its ``info:id`` to name a declared node. A benchmark
that re-asked would duplicate it.

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

from pxr import Gf, Sdf, UsdGeom, UsdShade

from simready_benchmark_kit_suite.fet006_materials import (
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

def build_probe(stage):
    """A flat magenta material with a surface on all three contexts.

    All three, because each pass pins a different list and the silhouette has
    to be cut the same way under every one of them. A probe with only a
    UsdPreviewSurface would resolve under ``[""]`` and fall to Kit's default
    material under ``["mtlx"]``, which is red rather than magenta.
    """
    UsdGeom.Scope.Define(stage, PROBE_SCOPE)
    material = UsdShade.Material.Define(stage, PROBE_SCOPE + "/Flat")

    preview = UsdShade.Shader.Define(stage, PROBE_SCOPE + "/Flat/Preview")
    preview.CreateIdAttr("UsdPreviewSurface")
    preview.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*PROBE_COLOR))
    preview.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    preview.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(preview.ConnectableAPI(), "surface")

    mdl = UsdShade.Shader.Define(stage, PROBE_SCOPE + "/Flat/Mdl")
    mdl.CreateIdAttr("mdl:OmniPBR")
    mdl.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
    mdl.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    mdl.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(*PROBE_COLOR)
    )
    mdl.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(1.0)
    mdl.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(0.0)
    mdl.CreateInput("specular_level", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput("mdl").ConnectToSource(mdl.ConnectableAPI(), "out")

    mtlx = UsdShade.Shader.Define(stage, PROBE_SCOPE + "/Flat/Mtlx")
    mtlx.CreateIdAttr("ND_open_pbr_surface_surfaceshader")
    mtlx.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*PROBE_COLOR))
    mtlx.CreateInput("base_weight", Sdf.ValueTypeNames.Float).Set(1.0)
    mtlx.CreateInput("base_metalness", Sdf.ValueTypeNames.Float).Set(0.0)
    mtlx.CreateInput("specular_weight", Sdf.ValueTypeNames.Float).Set(0.0)
    mtlx.CreateInput("base_diffuse_roughness", Sdf.ValueTypeNames.Float).Set(0.0)
    mtlx.CreateOutput("out", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput("mtlx").ConnectToSource(mtlx.ConnectableAPI(), "out")
    return material


def paint(stage, root_path, strength=UsdShade.Tokens.strongerThanDescendants):
    """Bind the probe over the whole asset. Returns whether it took.

    ``strongerThanDescendants`` paints everything the asset draws, which is the
    silhouette. ``weakerThanDescendants`` lets any binding the asset authors win,
    so the probe is left showing only where the asset binds nothing -- which is
    the same measurement with the strength flipped, and the only difference
    between the two passes.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return False
    return bool(
        UsdShade.MaterialBindingAPI.Apply(root).Bind(
            build_probe(stage), bindingStrength=strength
        )
    )


def clear(stage, root_path):
    """Take the probe binding back off the asset root."""
    root = stage.GetPrimAtPath(root_path)
    if root and root.IsValid():
        UsdShade.MaterialBindingAPI(root).UnbindDirectBinding()


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


async def run_coverage_test(ctx, context, requirement, fix_hint,
                            read_materialx_log=False):
    """How much of the asset is shaded by materials it authored for ``context``.

    Two renders, identical but for the binding strength of one control material,
    with the render-context list pinned to ``context`` for both.

    ``strongerThanDescendants``  the control wins everywhere, so every pixel the
                                 asset draws comes back flat magenta. That is the
                                 silhouette, and the denominator.
    ``weakerThanDescendants``    any binding the asset authored wins, so magenta
                                 is left only where the asset binds nothing. That
                                 is the numerator of what is *not* covered.

    Coverage is ``1 - uncovered / silhouette``. Both numbers are counted the same
    way, on the same geometry, lighting and camera framing, and the only thing
    that changed between them is the strength of one binding. Each pass builds
    its own stage, because rebinding on a live one does not resolve the way USD
    says it should -- ``_render_pass`` has the measurement.

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

    Presence is not re-checked here. The validator owns it and runs first:
    ``com.nvidia.usd.VM.PS.001``, ``VM.MDL.001`` and ``VM.PBR.001`` require the surface to
    exist and resolve, and ``VM.PBR.003`` requires its ``info:id`` to name a
    declared node.
    """
    order = [context]
    name = surfaces.label_for(context)
    short = context or "universal"
    floor = float(ctx.config["min_material_coverage"])

    previous = _context.read_order()
    try:
        ctx.step("Rendering with the render-context list pinned to [%s]" % readable(order))
        rendered = await _render_pass(
            ctx, order, "%s_surface_pinned" % short,
            UsdShade.Tokens.strongerThanDescendants)
        if rendered.get("error"):
            _fail_pass(ctx, rendered, order, name, requirement)
            return

        stage, root = rendered["stage"], rendered["root"]
        inventory = _scene.report_surface_inventory(ctx, stage, root, "%s_surface" % short)
        present = sorted({c or "universal" for cs in inventory.values() for c in cs})
        ctx.add_metric("%s_surface_asset_root" % short, root)
        ctx.add_metric("%s_surface_contexts_present" % short, ", ".join(present) or "none")
        ctx.add_metric("%s_surface_render_context_order" % short, readable(rendered["effective"]))

        silhouette = _pixels.mask_size(rendered["mask"])
        ctx.add_metric("%s_surface_silhouette_pixels" % short, silhouette)
        minimum = int(ctx.config["min_silhouette_pixels"])
        if silhouette < 0:
            ctx.fail(
                "The rendered frame could not be measured, so this run proves "
                "nothing about the %s surface. Pillow and numpy have to be "
                "importable inside Kit for these tests to report a result." % name
            )
            return
        if silhouette < minimum:
            ctx.fail(
                "The asset covers %d pixel(s) of flat magenta when the control "
                "material is bound over it, below the %d needed to measure "
                "anything.\n"
                "\n"
                "How to fix:\n"
                "- Check the camera framed the object. The run auto-frames on "
                "the asset bounds and an empty bound produces this.\n"
                "- Check the asset has renderable geometry of default or render "
                "purpose that is not authored invisible." % (silhouette, minimum)
            )
            return

        ctx.step("Rendering again with the control bound weakerThanDescendants")
        weak = await _render_pass(
            ctx, order, "%s_surface" % short,
            UsdShade.Tokens.weakerThanDescendants, capture_reported=False)
        if weak.get("error"):
            _fail_pass(ctx, weak, order, name, requirement)
            return
        uncovered = _pixels.mask_size(weak["mask"])
        if uncovered < 0:
            ctx.fail(
                "The second frame could not be measured, so coverage of the %s "
                "surface is unknown." % name
            )
            return

        # Clamped at zero: the two passes frame on separate stages, so an asset
        # that binds nothing anywhere can report marginally more uncovered
        # pixels than the silhouette it is divided by. Measured at 71 to 113
        # pixels of 406,000 on TEST/minimal.usd, under 0.03%, which is the whole
        # of the error.
        coverage = max(0.0, 1.0 - (uncovered / float(silhouette)))
        ctx.add_metric("%s_surface_uncovered_pixels" % short, uncovered)
        ctx.add_metric("%s_surface_coverage" % short, round(coverage, 5))

        if coverage < floor:
            ctx.fail(
                "With the render-context list pinned to [%s], %.1f%% of the "
                "asset's %d pixel silhouette is shaded by materials it authored, "
                "below the %.0f%% required. The remaining %d pixel(s) came back "
                "as the control material, which is what a pixel the asset binds "
                "nothing to looks like.\n"
                "\n"
                "Both frames are the same scene under the same pin, with one "
                "binding's strength flipped, so the difference between them is "
                "the asset's own bindings and nothing else. The asset has a "
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
                    readable(order), coverage * 100, silhouette, floor * 100,
                    uncovered, ", ".join(present) or "no surface at all",
                    requirement, fix_hint,
                )
            )
            return

        if read_materialx_log and not _report_materialx(ctx, root, short, name):
            return

        ctx.log(
            "With the render-context list pinned to [%s], %.1f%% of the asset's "
            "%d pixel silhouette is shaded by materials the asset authored, and "
            "%d pixel(s) came back as the control. The two frames are the same "
            "scene under the same pin, differing only in the strength of one "
            "binding, so that share is the asset's own bindings and nothing "
            "else. The asset has a surface on: %s.\n"
            "\n"
            "Coverage on its own does not establish that those materials "
            "evaluated. A shader that fails to resolve still wins over the weak "
            "control and counts as covered, which is what the MaterialX "
            "validation log reports separately."
            % (
                readable(rendered["effective"]), coverage * 100, silhouette,
                uncovered, ", ".join(present) or "no surface at all",
            )
        )
    finally:
        _context.restore(ctx, previous)


async def _render_pass(ctx, order, label, strength, capture_reported=True):
    """Pin one render-context list, build a scene, bind the control, mask magenta.

    Returns a dict with ``frame``, ``mask``, ``effective``, ``stage`` and
    ``root``, or one with ``error`` set when the pin or the scene did not come
    up.

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

    await _scene.build_scene(ctx)
    stage = ctx.scene.stage
    root = _scene.asset_root(ctx)
    if not root:
        return {"error": "root", "effective": effective}

    # The reported frame is captured before the control goes on, so no frame
    # this test reports shows anything but the asset's own materials.
    frame = await _settled_frame(ctx, label) if capture_reported else None

    suffix = ("silhouette" if strength == UsdShade.Tokens.strongerThanDescendants
              else "uncovered")
    mask = None
    if paint(stage, root, strength):
        await ctx.settle(count=2)
        control_frame = await ctx.capture_frame(
            label="%s_%s" % (label, suffix), allow_blank=True
        )
        mask = _pixels.dominant_mask(
            control_frame,
            MAGENTA_CHANNELS,
            float(ctx.config["mask_dominance_ratio"]),
            float(ctx.config["mask_dominance_floor"]),
        )
    clear(stage, root)
    return {
        "frame": frame,
        "mask": mask,
        "effective": effective,
        "stage": stage,
        "root": root,
    }


def _report_materialx(ctx, root, short, name):
    """Whether the asset's MaterialX documents built. False when one did not.

    Coverage cannot see this. A shader that fails to resolve still wins over the
    weakly bound control and counts as covered, so the object draws solid in the
    renderer's own colour and the number is unchanged. ``_logs`` has why the Kit
    log is the only place it shows, and why the setting has to be on for the log
    to hold anything.
    """
    enabled = _logs.validation_enabled()
    if not enabled:
        ctx.add_metric("%s_surface_materialx_validation" % short,
                       "unreadable" if enabled is None else "off")
        ctx.log(
            "Whether the %s materials evaluated was not checked. Kit was "
            "launched without --/persistent/app/material/materialx/validate=true, "
            "so a material whose document it could not build is not named in the "
            "log and reads here the same as one that rendered. The setting is "
            "read at startup, so it belongs to how the runner launches Kit."
            % name
        )
        return True

    unresolved = _logs.unresolved_materials(root)
    ctx.add_metric("%s_surface_materialx_validation" % short, "on")
    ctx.add_metric("%s_surface_materialx_unresolved" % short, len(unresolved))
    if not unresolved:
        ctx.log("Kit built a MaterialX document for every material under %s." % root)
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
        "not be built."
        % (len(unresolved), root, name, "\n".join("  " + p for p in unresolved))
    )
    return False


async def _settled_frame(ctx, label):
    """The reported frame, re-captured until two in a row agree.

    Materials are not resident the moment a stage is attached and nothing in the
    test API reports when they are, so the first capture of a run can be of an
    object whose textures have not arrived. Measured on Isaac Sim 5.0, the first
    asset of a run captured its MDL pass at a mean of (0.344, 0.344, 0.344) and
    the same frame later in the same session at (0.159, 0.156, 0.159).

    Only the reported frame needs this. Coverage is measured from the two control
    passes, and the control is a flat colour that is resident immediately.
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
        moved = max(abs(a - b) for a, b in zip(previous, current))
        if moved <= tolerance:
            break
        ctx.log("The frame was still changing after capture %d, by %.4f on the "
                "widest channel -- the asset's materials were not resident yet. "
                "Re-captured." % (attempt + 1, moved))
        previous = current
    return frame


def _fail_pass(ctx, result, wanted, name, requirement):
    """Report a pass that never got as far as a frame."""
    if result["error"] == "pin":
        ctx.fail(
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
                readable(wanted), name, readable(result["effective"]),
                _context.RENDER_CONTEXTS_SETTING,
            )
        )
        return
    ctx.fail(
        "The asset's stage path could not be determined, so there is no root "
        "prim to bind the silhouette probe on and %s cannot be measured. The "
        "binding would either miss the asset or take the room with it.\n"
        "\n"
        "How to fix:\n"
        "- The path comes from the asset handle's prim_path, falling back to "
        "the scene handle's _asset_root_path. A framework rename of either "
        "lands here." % requirement
    )

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
"""FET006 Display Colour Response (DISP.001 and DISP.003, measured in pixels).

WHAT: Binds the material DISP.001 nominates over the whole asset, renders it with
      the primvar reader swapped in and out, and reads the answer off the
      differences between the frames. Nothing on the asset is edited.

HOW:  One material is bound on the asset's ROOT prim with
      ``bindMaterialAs = "strongerThanDescendants"``, which beats every binding
      the asset authors below it -- including bindings inside prototypes
      reached through instance proxies. Swapping that one binding swaps the
      shading of the whole asset.

      Three materials go through it, all the same OpenPBR surface, plus a
      duplicate of the first that serves as the noise control:

      ``Read``     ``displayColor`` -> ``base_color``, fallback magenta.
      ``Removed``  no reader at all; ``base_color`` is flat magenta.
      ``Opacity``  as ``Read``, with the ``displayOpacity`` fallback at 0.0.

      Read against Removed answers one question: does ``primvars:displayColor``
      do anything at all in this engine. The two materials paint the same
      magenta, one as a reader's fallback and one as a constant, so geometry
      that resolves a display colour differs between the frames and geometry
      that resolves none does not. Any difference above the swap noise is the
      primvar reaching the shader and driving pixels. Read against Opacity asks
      the same of ``displayOpacity``, which is DISP.003.

WHAT THIS IS NOT: a coverage measurement. The question is presence, not
      extent, and the floor is set where nothing separates from something
      rather than anywhere near full coverage. That is deliberate, because the
      metric is denominated in pixels and DISP.001 is denominated in Gprims, and
      the two come apart badly. Measured on the reference toaster: a display
      colour on the body alone leaves four of five Gprims resolving nothing and
      reads 97.5% of the silhouette; a display colour on the four small parts
      leaves one of five resolving nothing and reads 2.7%. The same requirement
      is broken in both. No floor on this ratio orders them correctly, and
      DISP.001 orders both correctly per Gprim, so coverage stays with the
      validator, which runs ahead of the benchmarks.

      A green result here therefore means the feature is live, not that the
      asset is conformant. An asset carrying a display colour on one prim in
      fifty passes this and fails DISP.001.

WHAT CHANGED IN 0.4.0: coverage used to be a fourth frame, ``Altered``, which
      was ``Read`` with the reader's fallback moved from magenta to green, and
      was gated the other way up: geometry that resolved nothing changed colour
      between the two frames, so a *high* difference was the failure. That
      measured the same geometry as Read against Removed from the opposite
      side, and Read against Removed also proves the primvar drove the pixels,
      which Read against Altered does not. The green reader and its gate are
      gone.

      It was also an attempt to measure coverage in pixels, which is the wrong
      instrument for a per-Gprim requirement however it is gated. That claim
      has gone back to the validator rather than being re-tuned here.

      One case went with them. Geometry whose authored display colour is itself
      the probe's magenta renders identically under Read and Removed and is now
      counted as unresponsive; under Read against Altered it renders magenta in
      both and was correctly counted as covered. The result is a false failure
      rather than a false pass, and the failure message names the constant.

WHY:  DISP.001 to DISP.003 are statically checkable and the validator checks them.
      What no file inspection establishes is that the values reach a renderer:
      that the primvar the file declares is the primvar the shader reads. This
      test puts the nominated material in front of the asset and measures it.

      The material matters. Kit's own fallback for unbound geometry
      (``kit/mdl/rtx/Default.mdl``) reads ``displayColor`` into a diffuse tint
      and declares no opacity term, so a benchmark built on it measures Kit's
      internals and cannot reach DISP.003 at all. DISP.001's Guidance nominates an
      OpenPBR surface driven by MaterialX primvar readers instead, with a
      worked example. That is what this test binds, so what it measures is what
      the specification asks authors to produce.

WHAT CHANGED AND WHY: the previous version stripped every material binding on
  the asset to fall through to Kit's default material, made every instance
  under the asset non-instanceable so it could author on the geometry, hid
  Gprims one at a time to measure them alone, drove ``primvars:displayColor``
  through red, green and blue, and put it all back. Every one of those steps
  mutated the asset, and two of them broke on real content: nested instancing
  made ``SetInstanceable(False)`` raise part-way through a run on ur10 and 
  Robotiq 2F-85, and the per-Gprim isolation left visibility
  opinions to be unwound.

  It also asserted a per-Gprim rendered-luminance ordering. DISP.002's Guidance
  rules that out in as many words -- "No plausibility band is set, and none is
  planned" -- on the grounds that Rec.709 weights blue at 0.0722, so a
  saturated navy computes a lower luminance than charcoal. That assertion is
  gone and nothing has replaced it. This test does not judge the values.

  And it gated on DISP.001 coverage before rendering, by inspecting the file.
  That is the validator's job and the validator runs ahead of the benchmarks.
  The gate is gone; coverage is now a render measurement, which is the only
  kind of statement a benchmark is in a position to add.

WHAT THIS ASSERTS, AND WHAT IT DELIBERATELY DOES NOT:
  - It asserts that a measurable part of the asset's silhouette renders
    differently from the same surface driven by the reader's own fallback
    colour as a constant. That is display colour reaching the renderer, and it
    is at the same time the primvar rather than something else driving the
    pixels.
  - It does not assert how much of the asset carries a display colour. That is
    DISP.001's coverage claim and it belongs to the validator, which counts
    Gprims rather than pixels and names the ones that resolve nothing.
  - It asserts that the opacity reader's fallback is what keeps geometry
    omitting ``displayOpacity`` opaque, or, on an asset that authors opacity
    everywhere, that the fallback is never reached. That is DISP.003.
  - It asserts nothing about which display colour is brighter than which, no
    plausibility band, and no match between a pixel and an authored value. RTX
    tone-maps and the scene is dome-lit, so no absolute match is available; the
    first two are ruled out by DISP.002.
  - It does not require the asset to carry more than one display colour. DISP.001
    explicitly allows one constant value on an enclosing Xform or Scope, and an
    asset shaped that way passes here without a variation to measure.

FALSE POSITIVE AVOIDANCE:
  - Every ratio is denominated in the asset's own silhouette, cut out of the
    Removed frame by magenta dominance. A whole-frame difference would also
    count the shadow the asset casts and the light it bounces onto the room,
    neither of which is the asset.
  - The control frame is the Read frame taken again through a second material
    that duplicates the first. It has to be a swap, not a repeated capture: a
    material swap costs the path tracer its accumulated history, so it
    re-shades from scratch onto a different noise realisation. Measured on the
    two-box fixtures, a repeated capture with no swap between differed over
    0.0% of the silhouette and two swaps that should have looked identical
    differed over 4.0%, so a repeated capture was understating the floor by the
    entire floor. The control is also what the DISP.003 no-change case is
    measured against, so that ceiling can never sit below the noise it has to
    see through.
  - Each swap is settled long enough for the accumulated image to converge, not
    just long enough for the edit to reach Hydra. Those are different durations
    and the gap is large.
  - The fallback colour is magenta rather than a plausible grey. DISP.001's
    Guidance suggests a grey, which is right for an asset shipping the material
    and wrong for a probe: a plausible grey is indistinguishable from a display
    colour that resolved.
  - The file is read as well, for ``displayColor`` and ``displayOpacity``
    coverage, and the two answers are reported side by side. Neither gates the
    run. Their disagreement is the diagnostic: a file that resolves everywhere
    and a render that does not means either that the primvar is not reaching
    the shader, which is a different defect from the asset not carrying one, or
    that it is reaching it and the value is the probe's own magenta.
  - ``mtlx`` has to be in Kit's render-context list or the nominated material
    resolves to nothing and the geometry falls back to a default that is not
    under test. The list is read and reported, and its absence fails the run
    rather than being measured.

WHAT THIS FOUND: an inherited display colour inside an instance prototype does
  not reach the geometry in Kit. DISP.001 allows authoring one value on an
  enclosing Xform or Scope, USD resolves it on the instance proxies
  (``FindPrimvarWithInheritance`` returns it), and the render comes back on the
  reader's fallback anyway. Measured across four fixtures: the value reaches
  the geometry when it sits on the geometry itself or on the prototype's own
  root prim, and does not when it sits on an intermediate prim inside the
  prototype. Uninstanced assets are unaffected. This is the kind of thing a
  render benchmark exists to find -- the asset is conformant, the validator
  passes it, and a consumer sees no colour.

NOT COVERED: whether the shipped colours are the right ones. Nothing visible in
  a render establishes that a display colour is a faithful stand-in for the
  material it was derived from, and DISP.002 sets no band against which such a
  claim could be checked.

  Nothing is written to disk. The stage is the one the framework composed for
  this run and the asset's own layers are never opened for editing.
"""

from simready_benchmark.core.decorator import test

from simready_benchmark_kit_suite.fet010_standard import _probe
from simready_benchmark_kit_suite.fet006_materials import _context, _pixels, _scene, surfaces
from pxr import UsdGeom

BLACK = (0, 0, 0)

# The two channels the Removed frame's flat magenta puts at full, and the one
# it leaves at zero. This is what the silhouette is cut by.
MAGENTA_CHANNELS = (0, 2)


def display_color_coverage(gprims):
    """Which Gprims resolve a ``primvars:displayColor``, from the file.

    ``FindPrimvarWithInheritance`` rather than ``GetDisplayColorPrimvar``,
    because DISP.001 explicitly allows authoring once on an ancestor and letting
    ``UsdGeomPrimvarsAPI`` inheritance carry the value down. A Gprim that
    inherits its colour conforms.

    This is a prediction, not a gate. The render decides; this is what makes
    the render's answer diagnosable.
    """
    missing = []
    for prim in gprims:
        primvar = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance("displayColor")
        values = primvar.Get() if primvar else None
        if values is None or len(values) == 0:
            missing.append(prim.GetPath().pathString)
    return missing


def listed(paths, limit=10):
    """A path list for a failure message, truncated with a count."""
    shown = "\n  ".join(paths[:limit])
    if len(paths) > limit:
        return "%s\n  ... and %d more" % (shown, len(paths) - limit)
    return shown


@test(
    features=[{"id": "FET_010_STANDARD", "version": ">=0.1.0"}],
    name="display_color_response",
    description=(
        "Binds the OpenPBR primvar-reader material DISP.001 nominates over the "
        "whole asset and renders it with the reader swapped in and out. A "
        "measurable part of the silhouette must render differently from the "
        "same surface driven by the reader's own fallback colour as a "
        "constant, which is displayColor reaching the shader and driving "
        "pixels. It measures presence rather than coverage: DISP.001 owns how "
        "much of the asset carries one, per Gprim, in the validator. Nothing "
        "on the asset is edited."
    ),
    expected_video=(
        "The asset shaded by its own primvars:displayColor, then the same "
        "surface with the reader replaced by a flat magenta constant, then the "
        "display-opacity probe. The first two frames should look nothing "
        "alike; anything magenta in the first is geometry that resolved no "
        "display colour and took the reader's fallback, and it does not change "
        "in the second. In the third, geometry that omits "
        "primvars:displayOpacity disappears."
    ),
    version="0.4.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "settle_frames": 30,
        # Settle passes after a material swap, on top of settle_frames. The
        # viewport runs RTX RealTimePathTracing, which accumulates across
        # frames, so a new material does not replace the old image -- it blends
        # over the temporal history. Settle frames cost about 8ms each, so
        # 30 x 4 is around a second per capture.
        "swap_settle_count": 4,
        "camera_padding": 1.2,
        "asset_load_timeout": 30,
        # Largest single-channel move that counts a pixel as changed. Higher
        # than the 0.04 the material tests use, and deliberately so: every
        # signal this test looks for is a swap between saturated colours --
        # magenta against the asset's own colour, opaque against invisible --
        # both of which move a channel by far more
        # than this, while a material swap costs the path tracer its
        # accumulated history and lands on a different noise realisation. On
        # the two-box fixtures that noise measured 4.0% of the silhouette at
        # 0.04 and 0.05% at 0.08, with every real signal still at 100%.
        "pixel_change_threshold": 0.08,
        # How the asset's silhouette is cut out of the Removed frame, where it
        # is flat magenta. The floor rejects the dim magenta bounce the object
        # throws across the room; the object itself is saturated and bright.
        "mask_dominance_ratio": 1.5,
        "mask_dominance_floor": 0.20,
        # Silhouette pixels the asset needs before anything is measured. Below
        # this every ratio is denominated in noise.
        "min_silhouette_pixels": 5000,
        # Read against a second material that duplicates it. Both frames sit
        # on the far side of a material swap and should be indistinguishable,
        # so anything above this is an unsettled render rather than a result.
        # It is also the ceiling the DISP.003 no-change case is measured against,
        # which is the same shape of question: two frames that should agree.
        "max_control_ratio": 0.02,
        # Read against Removed. The two materials paint the same magenta, one
        # through the reader's fallback and one as a constant, so the silhouette
        # moves where a display colour of the asset's own reached the shader and
        # stays still where nothing did.
        #
        # THIS IS A PRESENCE FLOOR, NOT A COVERAGE FLOOR. It asks whether
        # displayColor does anything at all in the engine. It does not ask how
        # much of the asset carries one, and it must not be read as though it
        # did, because the number it produces is denominated in pixels and the
        # requirement is denominated in Gprims. Measured on the reference
        # toaster: a display colour on the body alone leaves four of five
        # Gprims resolving nothing and reads 0.975, and a display colour on the
        # four small parts leaves one of five resolving nothing and reads 0.027.
        # The same requirement is broken in both and the metric is two orders of
        # magnitude apart, because the body is most of the silhouette. No floor
        # on this ratio can separate them, and DISP.001 separates both correctly,
        # per Gprim and by name, in the validator that runs ahead of this.
        #
        # So the floor is set where the two populations actually part: nothing
        # happening at all against something happening. Measured on Isaac Sim
        # 6.0, the control -- two renders that should be identical -- ran
        # 0.0 to 0.00055, and an asset with no display colour anywhere read
        # 0.00076. The quietest run where a display colour did reach the shader
        # is the toaster carrying one on its four small parts, at 0.027, and
        # that number is small because those parts are small rather than
        # because the feature is faint.
        #
        # 0.005 is the geometric middle of 0.00076 and 0.027 -- six times the
        # loudest inert run, five times under the quietest live one, and an
        # order of magnitude above the worst control measured. It is not tuned
        # to either side.
        "min_response_ratio": 0.005,
        # Read against the opacity probe, on an asset where no Gprim resolves
        # displayOpacity. Every one of them is then holding its opacity from the
        # reader's fallback, so dropping that fallback to zero takes geometry
        # away. A presence floor for the same reason: how much of the silhouette
        # goes with it is a property of the asset's shape and of the room, not
        # of DISP.003.
        #
        # The workbench tool is why. It renders at a mean of (0.059, 0.053,
        # 0.050) against this test's black room, so an invisible object and a
        # very dark one differ by less than the 0.08 pixel threshold over more
        # than half the silhouette. It measured 0.412 with the opacity reader
        # working correctly, and a 0.90 floor failed a conformant shipping
        # sample on nothing but how dark it is.
        #
        # The same number as the response floor, because it is the same
        # question against the same swap noise. Nothing measured falls between
        # that noise and the 0.412 the workbench tool set, so this side has far
        # more clearance than the response floor does; it is held level with it
        # rather than tuned separately.
        "min_opacity_response_ratio": 0.005,
    },
)
async def test_display_color_response(ctx):
    """The asset's own displayColor must drive the material DISP.001 nominates."""
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    stage = ctx.scene.stage
    root = _scene.asset_root(ctx)
    ctx.add_metric("display_color_asset_root", root or "<whole stage>")
    if not root:
        ctx.fail(
            "The asset's stage path could not be determined, so there is no "
            "root prim to bind the probe material on and the binding would "
            "either miss the asset or take the room with it.\n"
            "\n"
            "How to fix:\n"
            "- The path comes from the asset handle's prim_path, falling back "
            "to the scene handle's _asset_root_path. A framework rename of "
            "either lands here."
        )
        return

    # The nominated material carries an mtlx surface and nothing else. Kit
    # walks its render-context list and takes the first output a material has,
    # so with mtlx missing from that list the probe resolves to nothing and the
    # geometry falls back to a default material that is not what is under test.
    # Nothing is pinned here: the shipped order already contains mtlx, and
    # reordering it would need a new stage.
    order = _context.read_order()
    ctx.add_metric(
        "display_color_render_context_order",
        ", ".join(c or "universal" for c in order) if order else "unreadable",
    )
    if order is not None and "mtlx" not in order:
        ctx.fail(
            "Kit's render-context list reads [%s] and does not contain mtlx, "
            "so the OpenPBR probe material DISP.001 nominates resolves to no "
            "surface at all and the geometry would render on a fallback "
            "material this test says nothing about.\n"
            "\n"
            "How to fix:\n"
            "- Restore %s to its shipped value [mdl, mtlx, \"\"]. Kit persists "
            "that key to user.config.json on shutdown, so a value narrowed by "
            "an earlier run survives into this one."
            % (", ".join(c or "universal" for c in order), _context.RENDER_CONTEXTS_SETTING)
        )
        return

    gprims = list(surfaces.renderable_geometry(stage, root))
    ctx.add_metric("display_color_renderable_gprims", len(gprims))
    if not gprims:
        ctx.skip("The asset has no renderable geometry, so there is nothing to colour.")
        return

    # Read the file as well as the render, and report both. Neither gates.
    # Their disagreement is the diagnostic: a file that resolves everywhere and
    # a render that does not is a different defect from an asset that carries
    # no display colour.
    missing_color = display_color_coverage(gprims)
    without_opacity = [
        p.GetPath().pathString for p in gprims if not _probe.resolves_display_opacity(p)
    ]
    ctx.add_metric("display_color_gprims_without_displaycolor", len(missing_color))
    ctx.add_metric("display_color_gprims_without_displayopacity", len(without_opacity))

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(*BLACK)
    room.hide_ground()
    ctx.scene.lighting.add_dome(intensity=1000.0)

    ctx.step("Binding the display-colour probe material on the asset root")
    materials = _probe.build(stage)
    _probe.bind(stage, root, materials[_probe.READ])

    # Resolve the swap the way the renderer will, before reading any pixel. A
    # Gprim the probe did not reach is one no frame below can say anything
    # about, and naming it here beats reporting it later as an unexplained
    # absence of response.
    unreached = [
        p.GetPath().pathString for p in gprims if _probe.bound_probe(p) != _probe.READ
    ]
    ctx.add_metric("display_color_probe_bound_gprims", len(gprims) - len(unreached))
    if unreached:
        ctx.fail(
            "%d of %d renderable Gprim(s) do not resolve the probe material "
            "after it was bound on %s with bindMaterialAs = "
            "\"strongerThanDescendants\":\n"
            "  %s\n"
            "\n"
            "A strongerThanDescendants binding on the asset root is supposed "
            "to beat every binding below it. Something above the asset root is "
            "binding over it.\n"
            "\n"
            "How to fix:\n"
            "- Run this test on the asset in isolation, rather than inside a "
            "scene that binds a material over it."
            % (len(unreached), len(gprims), root, listed(unreached))
        )
        return

    await ctx.settle(count=2)
    ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])

    settle_passes = int(ctx.config["swap_settle_count"])
    threshold = float(ctx.config["pixel_change_threshold"])

    async def swap(name, label, role="normal"):
        """Bind one probe material, let the image converge, capture it."""
        _probe.bind(stage, root, materials[name])
        await ctx.settle(count=settle_passes)
        # allow_blank throughout: an asset rendering its own dark display
        # colours against a black room is exactly what the blank-frame detector
        # is built to catch, and here it is the expected picture rather than a
        # failed render. The opacity probe frame is legitimately empty on an
        # asset that omits displayOpacity everywhere.
        return await ctx.capture_frame(
            label="display_color_%s" % label, role=role, allow_blank=True
        )

    ctx.step("Rendering the asset through the probe material")
    ctx.scene.hide_asset()
    await ctx.settle(count=settle_passes)
    background = await ctx.capture_frame(label="display_color_background", allow_blank=True)
    ctx.scene.show_asset()

    read = await swap(_probe.READ, "read", role="summary")
    # Through a second material that duplicates the first, so the control is
    # the same kind of comparison as the measurements: two frames either side
    # of a swap, which should be indistinguishable and are not bit-identical.
    read_control = await swap(_probe.READ_CONTROL, "read_control")

    ctx.step("Replacing the reader with a constant")
    removed = await swap(_probe.REMOVED, "removed")

    ctx.step("Dropping the display-opacity fallback to zero")
    opacity = await swap(_probe.OPACITY, "opacity")

    _probe.unbind(stage, root)

    ctx.encode_video(
        [read, removed, opacity],
        fps=1,
        delete_frames=False,
        label="display_color_response",
        role="summary",
    )

    # ------------------------------------------------------------------
    # The silhouette. Everything below is denominated in it.
    # ------------------------------------------------------------------
    ctx.step("Measuring the frames")
    mask = _pixels.dominant_mask(
        removed,
        MAGENTA_CHANNELS,
        float(ctx.config["mask_dominance_ratio"]),
        float(ctx.config["mask_dominance_floor"]),
    )
    silhouette = _pixels.mask_size(mask)
    footprint = _pixels.changed_pixels(background, removed, threshold)
    ctx.add_metric("display_color_silhouette_pixels", silhouette)
    ctx.add_metric("display_color_whole_frame_delta_pixels", footprint)
    ctx.add_metric("display_color_read_mean_rgb", _pixels.frame_summary(read))

    if silhouette < 0:
        ctx.fail(
            "The rendered frames could not be measured, so this run proves "
            "nothing. Pillow and numpy have to be importable inside Kit for "
            "these tests to report a result."
        )
        return

    minimum = int(ctx.config["min_silhouette_pixels"])
    if silhouette < minimum:
        ctx.fail(
            "The asset covers %d pixel(s) of flat magenta when the probe "
            "material drives it with a constant, below the %d needed to "
            "measure anything. The whole frame moved %d pixel(s) against an "
            "empty room, so the object is either not there or not magenta.\n"
            "\n"
            "How to fix:\n"
            "- Check the camera framed the object; the run auto-frames on the "
            "asset bounds and an empty bound produces this.\n"
            "- Check primvars:displayOpacity. Geometry resolving an opacity of "
            "zero renders invisible under the nominated material whatever its "
            "display colour says, which DISP.003 calls out as a common artifact "
            "of an unconfigured export.\n"
            "- Check the probe material resolved. With mtlx first in Kit's "
            "render-context list the OpenPBR surface is what Kit evaluates; "
            "the list this run saw is reported above."
            % (silhouette, minimum, footprint)
        )
        return

    def ratio_in_mask(frame_a, frame_b):
        """Changed pixels between two frames, as a fraction of the silhouette."""
        changed = _pixels.changed_pixels_in(frame_a, frame_b, mask, threshold)
        if changed < 0:
            return None
        return changed / float(silhouette)

    noise = ratio_in_mask(read, read_control)
    response = ratio_in_mask(read, removed)
    opacity_response = ratio_in_mask(read, opacity)
    if None in (noise, response, opacity_response):
        ctx.fail(
            "One of the four frames could not be compared against the others, "
            "so no ratio below is a measurement. Pillow and numpy have to be "
            "importable inside Kit, and all four captures have to have the "
            "same shape."
        )
        return

    ctx.add_metric("display_color_control_ratio", round(noise, 6))
    ctx.add_metric("display_color_response_ratio", round(response, 6))
    ctx.add_metric("display_color_opacity_ratio", round(opacity_response, 6))

    reasons = []

    if noise > float(ctx.config["max_control_ratio"]):
        ctx.fail(
            "Two renders of the same material differ over %.2f%% of the "
            "asset's %d silhouette pixels, above the %.0f%% the control "
            "allows. The render is not settled, so none of the comparisons "
            "below is a measurement.\n"
            "\n"
            "How to fix:\n"
            "- Raise settle_frames or swap_settle_count."
            % (noise * 100, silhouette, float(ctx.config["max_control_ratio"]) * 100)
        )
        return

    # ------------------------------------------------------------------
    # Does displayColor do anything at all in this engine? Read and Removed are
    # the same surface painted the same magenta, once through the reader's
    # fallback and once as a constant, so the silhouette moves where a display
    # colour of the asset's own reached the shader and drove pixels.
    #
    # HOW MUCH of it moved is not asked. That number is denominated in pixels
    # and DISP.001 is denominated in Gprims, and the two come apart by orders of
    # magnitude on the same defect depending on how large the offending
    # geometry is. Coverage is the validator's, per Gprim and by name.
    # ------------------------------------------------------------------
    if response < float(ctx.config["min_response_ratio"]):
        agreement = (
            "The file agrees: %d of %d renderable Gprim(s) resolve no "
            "primvars:displayColor, on the prim or on any ancestor.\n"
            "  %s\n"
            "\n"
            "This is DISP.001, and the validator names every one of them."
            % (len(missing_color), len(gprims), listed(missing_color))
            if missing_color
            else
            "The file disagrees: every one of the %d renderable Gprim(s) "
            "resolves a primvars:displayColor. So either the values are "
            "authored and are not reaching the shader, which is a different "
            "defect from an asset that carries no display colour, or they are "
            "reaching it and are the probe's own constant %s, which is a "
            "finding about the values.\n"
            "\n"
            "The known cause of the first, measured on this suite's fixtures, "
            "is an inherited display colour inside an instance prototype. "
            "DISP.001 allows authoring one value on an enclosing Xform or Scope "
            "and letting UsdGeomPrimvarsAPI inheritance carry it down, and USD "
            "resolves that on an instance proxy -- but Kit does not carry it "
            "into the geometry unless the value sits on the prototype's own "
            "root prim. %d of the %d Gprim(s) here are instance proxies.\n"
            "\n"
            "Failing that, the value is authored somewhere the renderer will "
            "not read: an interpolation or element count that disagrees with "
            "the topology, an indexed primvar with a bad index, or a name the "
            "geompropvalue reader does not resolve to.\n"
            "\n"
            "The display_color_read frame tells the two apart. Geometry that "
            "took the reader's fallback is magenta in it; geometry rendering "
            "an authored colour that happens to be magenta is magenta too, but "
            "so is the rest of the asset."
            % (
                len(gprims),
                str(_probe.FALLBACK_COLOR),
                sum(1 for p in gprims if p.IsInstanceProxy()),
                len(gprims),
            )
        )
        reasons.append(
            "Replacing the primvar reader with a flat %s constant changed "
            "%.3f%% of the asset's %d silhouette pixels, below the %.0f%% this "
            "test needs to say the primvar did anything at all. Two renders of "
            "the same material differed over %.3f%% of it, so this is the "
            "noise floor rather than a signal: primvars:displayColor is not "
            "reaching the shader on any part of this asset a camera can see.\n"
            "\n"
            "%s\n"
            "\n"
            "How to fix:\n"
            "- Author primvars:displayColor on the geometry, or once on a "
            "common ancestor with constant interpolation. Only constant "
            "primvars are inheritable, so an ancestor value at any other "
            "interpolation will not reach the Gprim.\n"
            "- On instanced geometry, author it on the geometry itself or on "
            "the prototype's root prim. An intermediate Xform or Scope inside "
            "the prototype is where Kit stops carrying it, and no file check "
            "sees that.\n"
            "- Check swap_settle_count is high enough. Under-settled, each "
            "frame still shows most of the previous one and every difference "
            "reads small."
            % (
                str(_probe.FALLBACK_COLOR),
                response * 100,
                silhouette,
                float(ctx.config["min_response_ratio"]) * 100,
                noise * 100,
                agreement,
            )
        )

    # ------------------------------------------------------------------
    # DISP.003. The opacity probe is the read material with the reader's
    # fallback dropped from 1.0 to 0.0, so geometry holding its opacity from
    # that fallback disappears and geometry resolving its own does not.
    # ------------------------------------------------------------------
    all_omit = len(without_opacity) == len(gprims)
    none_omit = not without_opacity
    # Two frames that should agree, measured against the ceiling the control
    # uses, which is the other pair in this test that should agree. Reusing it
    # rather than carrying a constant of its own means this can never be
    # tighter than the swap noise the same run has already demonstrated.
    unchanged_limit = float(ctx.config["max_control_ratio"])
    if none_omit:
        if opacity_response > unchanged_limit:
            reasons.append(
                "Every one of the %d renderable Gprim(s) resolves a "
                "primvars:displayOpacity, so dropping the reader's fallback "
                "from 1.0 to 0.0 should have changed nothing. It changed %.1f%% "
                "of the %d silhouette pixels, above the %.0f%% allowed, so some "
                "geometry is taking the fallback rather than the value it "
                "authors.\n"
                "\n"
                "This is DISP.003 not reaching the shader. The value is there and "
                "the renderer is not reading it, which points at the primvar's "
                "type, interpolation or element count rather than at its "
                "presence."
                % (len(gprims), opacity_response * 100, silhouette, unchanged_limit * 100)
            )
    elif all_omit:
        floor = float(ctx.config["min_opacity_response_ratio"])
        if opacity_response < floor:
            reasons.append(
                "No renderable Gprim resolves a primvars:displayOpacity, so "
                "every one of them is holding its opacity from the reader's "
                "fallback and dropping that fallback to 0.0 should have taken "
                "geometry away. It changed %.3f%% of the %d silhouette pixels, "
                "below the %.0f%% this test needs to say the opacity reader did "
                "anything at all, against %.3f%% for two renders that should "
                "have been identical.\n"
                "\n"
                "The opacity half of the material DISP.001 nominates is not "
                "reaching geometry_opacity in this build, so nothing in this "
                "run is evidence about DISP.003.\n"
                "\n"
                "How much of the silhouette goes with it is not asserted, and "
                "should not be: a dark asset against this test's black room "
                "barely differs from an invisible one, so the fraction is a "
                "property of the asset's colours rather than of DISP.003.\n"
                "\n"
                "How to fix:\n"
                "- Check ND_geompropvalue_float and the OpenPBR surface's "
                "geometry_opacity input both resolve in this Kit build."
                % (opacity_response * 100, silhouette, floor * 100, noise * 100)
            )
    else:
        ctx.warn(
            "%d of %d renderable Gprim(s) resolve no primvars:displayOpacity, "
            "which DISP.003 permits. Dropping the reader's fallback to 0.0 moved "
            "%.1f%% of the silhouette. No floor is asserted on a mixed asset: "
            "the geometry that would disappear may be occluded by the geometry "
            "that would not, so a small number here is not a finding. The "
            "measurement is reported and the frame is in the video."
            % (len(without_opacity), len(gprims), opacity_response * 100)
        )

    if reasons:
        ctx.fail("\n\n".join(reasons))
        return

    if none_omit:
        opacity_note = (
            "Every Gprim resolves a display opacity of its own, and dropping "
            "the reader's fallback to zero moved %.2f%% of the silhouette, so "
            "none of them is relying on the fallback (DISP.003)."
            % (opacity_response * 100)
        )
    elif all_omit:
        opacity_note = (
            "No Gprim resolves a display opacity, and dropping the reader's "
            "fallback from 1.0 to zero removed %.1f%% of the silhouette, so "
            "the fallback is what is holding the asset opaque -- which is what "
            "DISP.001's Guidance asks that default to do and what DISP.003 permits "
            "the geometry to rely on. The size of that number is not asserted: "
            "a dark asset against a black room barely differs from an invisible "
            "one." % (opacity_response * 100)
        )
    else:
        opacity_note = (
            "%d of %d Gprim(s) resolve no display opacity and rely on the "
            "reader's fallback; dropping it to zero moved %.1f%% of the "
            "silhouette (DISP.003)."
            % (len(without_opacity), len(gprims), opacity_response * 100)
        )

    ctx.log(
        "All %d renderable Gprim(s) resolved the probe material through one "
        "strongerThanDescendants binding on %s, and nothing on the asset was "
        "edited. Over the asset's %d silhouette pixels, replacing the primvar "
        "reader with a flat %s constant moved %.1f%%, against %.3f%% for a swap "
        "to a duplicate of the same material. Those two materials paint the "
        "same colour, once as the reader's fallback and once as a constant, so "
        "the pixels that moved are pixels a display colour of the asset's own "
        "reached the shader and drove. primvars:displayColor is live in this "
        "engine.\n"
        "\n"
        "This does not say every Gprim carries one. The measurement is "
        "denominated in pixels and DISP.001 is denominated in Gprims, so an asset "
        "with a display colour on one large prim and none on twenty small ones "
        "reads the same here as one that is fully covered. DISP.001 is the "
        "coverage check, it is per Gprim, and the validator runs ahead of this. "
        "This run adds what the validator cannot see: that the values reach a "
        "renderer at all. On the file side of this run, %d of %d renderable "
        "Gprim(s) resolve no primvars:displayColor.\n"
        "\n"
        "%s"
        % (
            len(gprims),
            root,
            silhouette,
            str(_probe.FALLBACK_COLOR),
            response * 100,
            noise * 100,
            len(missing_color),
            len(gprims),
            opacity_note,
        )
    )

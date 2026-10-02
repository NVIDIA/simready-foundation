# FET010 Display Color

How much of an asset's own display color reaches a renderer, through the material the
specification nominates for it.

## Overview

Display color is a primvar rather than a material, so the asset carries no surface for it and there is no render context to resolve through. It sits alongside the material features rather than inside them, which is why it has its own family.

The capability rests on a premise no file inspection can establish: that display color is a usable appearance layer for consumers that do not evaluate materials. Static validation confirms the primvar is authored and well formed. The test in this family renders the asset through that layer and measures what comes out.

What it renders through is the material DISP.001's Guidance nominates: an OpenPBR surface driven by MaterialX primvar readers, `ND_geompropvalue_color3` on `displayColor` into `base_color` and `ND_geompropvalue_float` on `displayOpacity` into `geometry_opacity`. The test binds that material over the whole asset with one `strongerThanDescendants` binding on the asset's root prim, then swaps the reader in and out behind it and reads the answer off the differences between the frames. Nothing on the asset is edited.

Using the nominated material rather than a renderer's own fallback is what makes the result about the specification. It is also what reaches display opacity: Kit's fallback for unbound geometry, `kit/mdl/rtx/Default.mdl`, declares a surface and no opacity term, so a benchmark built on it cannot show a response to `displayOpacity` at all.

## What a Passing Family Means

**A pass means the feature is live. It does not mean the asset is conformant.**

A reviewer, PM, or OEM can trust that display colors this asset ships reach a renderer through the material the specification nominates for them, so a consumer that ignores materials gets the asset's own colors rather than a uniform default. That is what a render can establish and a file check cannot.

It is not a coverage result. This benchmark does not say every renderable Gprim carries a display color, and an asset with one on a single prim in fifty passes it. Coverage is DISP.001's, the validator measures it per Gprim and names the prims that resolve nothing, and the validator runs ahead of the benchmarks. The two are complementary and neither substitutes for the other: the validator reads what the file declares, this reads what the renderer does with it.

The reason for the split is that the benchmark's measurement is denominated in pixels while the requirement is denominated in Gprims, and on the same defect those two disagree by orders of magnitude depending on how large the offending geometry happens to be. The [test page](fet010/display-color-response.md#why-coverage-is-not-measured-here) has the fixtures that show it.

What a pass does not do is judge whether the shipped colors are the right ones, or order them. Nothing visible in a render establishes that a display color is a faithful stand-in for the material it was derived from, and DISP.002 sets no plausibility band against which such a claim could be checked. It says none is planned, because Rec.709 weights blue at 0.0722 and a saturated navy computes a lower luminance than charcoal.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [display_color_response](fet010/display-color-response.md)
  - `primvars:displayColor` and `primvars:displayOpacity` reach the renderer through the material DISP.001 nominates for them.
  - FET_010_STANDARD
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET010 Display Color](../../../features/FET_010_STANDARD.md). Authoring and value rules live
in the [Display Color capability](../../../capabilities/visualization/display_color/capability-display_color.md).

```{toctree}
:maxdepth: 1
:hidden:

display_color_response <fet010/display-color-response>
```

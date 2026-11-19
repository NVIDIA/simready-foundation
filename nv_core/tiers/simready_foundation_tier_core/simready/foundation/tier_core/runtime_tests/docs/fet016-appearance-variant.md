# FET016 Appearance Variant

## Overview

`FET016_AppearanceVariant.0-1-0` has one version 1.0.0 runtime test. It
checks that every declared `Appearance` option composes, renders differently,
and is visual-only: a pure material re-bind that moves no geometry.

## What a Passing Family Means

The asset offers interchangeable looks (for example clean and weathered) that a
scene can swap without re-fitting the object. Each option renders a visibly
different surface while the shape and footprint are unchanged.

## Tests

:::{list-table}
:header-rows: 1
:widths: 30 45 25

* - Test
  - What It Checks
  - Validates
* - [appearance_variation](fet016/appearance-variation.md)
  - Recomposes each Appearance option, confirms visual and collision envelopes are unchanged, then renders a frame per option and checks consecutive options differ.
  - FET016 Appearance Variant
:::

## Relationship to the Feature

The test provides evidence for
[Appearance Variant](../../features/FET016_AppearanceVariant.md). It
exercises AV.001-AV.005 and AV.007, validated by the `AssetVariants` checkers,
and depends on the material contract carried by `FET006`.

```{toctree}
:maxdepth: 1
:hidden:

appearance_variation <fet016/appearance-variation>
```

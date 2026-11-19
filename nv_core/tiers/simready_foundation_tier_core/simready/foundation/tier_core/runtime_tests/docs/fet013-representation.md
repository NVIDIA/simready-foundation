# FET013 Multi-Representation Visual

## Overview

`FET013_MultiRepresentationVisual.0-1-0` has one version 1.0.0 runtime
test. It checks that every declared `Representation` option composes to
renderable geometry and occupies the same visual envelope, so a consumer can
swap the representation without the object moving or resizing.

## What a Passing Family Means

Each representation of the asset (for example a detailed mesh and a Gaussian
splat capture of the same object) composes on its own, renders, and keeps the
same footprint as the authored default. The representations are genuinely
interchangeable.

## Tests

:::{list-table}
:header-rows: 1
:widths: 30 45 25

* - Test
  - What It Checks
  - Validates
* - [representation_variation](fet013/representation-variation.md)
  - Recomposes each Representation option, compares its visual envelope with the authored default, and renders a frame per option.
  - FET013 Multi-Representation Visual
:::

## Relationship to the Feature

The test provides evidence for
[Multi-Representation Visual](../../features/FET013_MultiRepresentationVisual.md).
It exercises AV.001-AV.003 (discovery, location, composability) and AV.005
(visual envelope invariant), validated by the `AssetVariants` checkers. The test
is independent of the physics solver.

```{toctree}
:maxdepth: 1
:hidden:

representation_variation <fet013/representation-variation>
```

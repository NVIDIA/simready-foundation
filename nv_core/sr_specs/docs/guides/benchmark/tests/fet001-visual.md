# FET001 Visual

The minimal placeable visual feature: the asset renders, faces the right way, and sits correctly for placement.

## Overview

This family confirms an asset is visually usable in a scene. The tests verify that the asset produces visible pixels, that its surface normals face outward, that back faces are culled correctly, that the surface responds to lighting, and that the pivot supports ground placement.

## What a Passing Family Means

A reviewer, PM, or OEM can trust the asset renders as a solid, correctly shaded object. Surface normals face outward, face winding is correct, and the mesh responds to directional lighting. The pivot check is advisory: a sub-threshold result is reported as SKIPPED rather than failed, so a passing family does not guarantee ground placement for non-prop object types.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [presence](fet001/presence.md)
  - Renders the asset and confirms visible pixels exist.
  - FET001_BASE_NEUTRAL
* - [normals_xz](fet001/normals-xz.md)
  - Checks surface normals face outward across a combined X and Z rotation sweep.
  - FET001_BASE_NEUTRAL
* - [culling_xz](fet001/culling-xz.md)
  - Checks face winding order is correct across a combined X and Z rotation sweep.
  - FET001_BASE_NEUTRAL
* - [light_response](fet001/light-response.md)
  - Confirms the asset shading changes as a directional light moves around it.
  - FET001_BASE_NEUTRAL
* - [pivot](fet001/pivot.md)
  - Checks the pivot sits at the bottom-center of the asset for ground placement.
  - FET001_BASE_NEUTRAL
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET001 Minimal Placeable Visual](../../../features/FET_001-minimal.md).

```{toctree}
:maxdepth: 1
:hidden:

presence <fet001/presence>
normals_xz <fet001/normals-xz>
culling_xz <fet001/culling-xz>
light_response <fet001/light-response>
pivot <fet001/pivot>
```

# FET001 Visual

The minimal placeable visual feature: sampled rendering probes and an advisory authored-pivot score.

`FET001` is the evaluation family label. The enabled registrations advertise
`FET001_MinimalPlaceableVisual.0-1-0`, `.1-0-0` and `.1-0-1`
(with the same full prefix). `FET_001_STANDARD` is a legacy family alias,
not the current manifest ID. A bare `FET001` manifest is not required.

## Overview

This family measures visible rendering, dark-pixel counts, paired culling
differences and image response to a moving light. Those sampled image proxies
help investigate normals, winding and scene setup without certifying every
surface. The authored-pivot test reports a weighted advisory score; it does
not simulate physical placement or establish every pivot criterion.

## What a Passing Family Means

All five probes reject malformed/nonfinite acceptance configuration before
scene mutation. Steps and capture intervals must permit actual observations;
light response needs at least two frames, and the normals problem-frame count
must be reachable within the configured sweep. Valid thresholds and defaults
keep their existing domains, including documented zero fractions/tolerances.
Required capture or image-analysis failures remain execution errors, not
zero-valued measurements or asset-response verdicts.

The initial visibility precheck compares a framed diagnostic capture with an
asset-hidden control under the same lighting. It requires at least 100
diagnostic-colored pixels attributable to the asset, so orange scene content
alone cannot establish visibility. Valid decoded images with too few changed
pixels follow the documented FAIL/advisory-SKIP policy; missing/corrupt images
or unavailable analysis dependencies leave execution incomplete.

Normals/culling object ratios require the existing 100-pixel reference mask.
Normals excludes undersized views from its average and problem count, records
their indices, and needs at least `min_problem_frames` qualified frames.
Culling requires every OFF reference to qualify before it can PASS; an empty
ON image after a qualified OFF image remains a measured difference. Missing
coverage gives an execution error unless an observed valid culling pair
already fails the threshold, in which case that FAIL is retained with gap
metrics. Edge-on or missing views do not by themselves prove an asset defect.

Video encoding is optional presentation when the owned encoder returns `None`
for a recoverable failure. RunContext retains a warning where available without
replacing measured PASS/FAIL/advisory SKIP. Unknown engine/session exceptions,
unsafe media paths, cancellation and required-cleanup signals still propagate
as execution errors; these are not ordinary missing-video outcomes.

The asset produces visible pixels and its sampled rendering satisfies the
configured darkness, culling-difference and lighting-response thresholds.
These image proxies do not certify every normal or face, all viewing angles,
material correctness or complete reference resolution. The pivot check is
advisory: a sub-threshold result is SKIPPED, not FAIL, and even a passing pivot
score is not a physical ground-contact guarantee.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [presence](fet001/presence.md)
  - Renders the asset and confirms visible pixels exist.
  - FET001_MinimalPlaceableVisual
* - [normals_xz](fet001/normals-xz.md)
  - Counts excessive dark-pixel frames in a sampled combined X and Z sweep.
  - FET001_MinimalPlaceableVisual
* - [culling_xz](fet001/culling-xz.md)
  - Limits object-masked differences between sampled culling-off/on pairs.
  - FET001_MinimalPlaceableVisual
* - [light_response](fet001/light-response.md)
  - Checks sampled image variation and blank-frame ratios as a directional light moves.
  - FET001_MinimalPlaceableVisual
* - [pivot](fet001/pivot.md)
  - Scores authored origin height, XY centering, tilt-overlap and orbit proxies; sub-threshold results are SKIP.
  - FET001_MinimalPlaceableVisual
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[`FET001_MinimalPlaceableVisual` - Minimal Placeable Visual](../../features/FET001_MinimalPlaceableVisual.md).

```{toctree}
:maxdepth: 1
:hidden:

presence <fet001/presence>
normals_xz <fet001/normals-xz>
culling_xz <fet001/culling-xz>
light_response <fet001/light-response>
pivot <fet001/pivot>
```

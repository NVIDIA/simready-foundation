# pivot  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | pivot                          |
| Feature(s)   | `FET001_MinimalPlaceableVisual.0-1-0`, `FET001_MinimalPlaceableVisual.1-0-0`, `FET001_MinimalPlaceableVisual.1-0-1`            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.4                          |

## Summary

Scores the authored asset origin against its Z-aligned bounding box and samples
tilt-overlap and spin-orbit proxies. A sub-threshold score is an advisory skip,
not a physical-contact failure.

## What Pass Guarantees

Before scene mutation, `steps` and `video_capture_interval` must be positive
whole counts, settling nonnegative, and camera padding/load timeout finite
and positive. The three configurable geometry-relative tolerances must be
finite and nonnegative (zero and ratios greater than one remain allowed).
The normalized score threshold must be a finite fraction in `[0, 1]`.
Invalid controls are configuration errors; an empty sweep cannot fabricate
zero overlap/orbit measurements or an advisory PASS.

A pass means the weighted score reaches `pass_score_threshold` (default 0.70).
At that default the 0.70 height contribution is necessary and sufficient;
the three other contributions total only 0.30. If the threshold is overridden,
that relationship changes. The height check is one-sided:
`(origin_z - bbox_min_z) / bbox_height <= pivot_height_tolerance`; it is not an
absolute-distance band and can accept an origin below the box. A pass does not
guarantee flush placement, XY centering, no overlap, or physical floor contact.

## What It Checks

The test evaluates four aspects of the pivot location and scores them:

| Aspect | Weight | Condition |
|---|---|---|
| Pivot at base | 0.70 | Signed origin height above bbox minimum, divided by bbox height, is at or below `pivot_height_tolerance` (default 10%); this is not an absolute-distance check. |
| Pivot centered in XY | 0.10 | The asset origin is within 10 percent of the largest horizontal dimension from the bounding box center in the XY plane. |
| No bbox overlap on X tilt | 0.10 | The sampled authored world-aligned bbox minimum Z stays at or above negative `penetration_tolerance` times bbox height (default 5%); this is not a mesh/contact measurement. |
| No orbital motion on Z spin | 0.10 | Rotating the asset a full 360 degrees around the Z axis does not produce a bounding-box center trajectory whose radius exceeds 10 percent of the largest horizontal dimension. |

The combined score must reach `pass_score_threshold` (default 0.70) to pass.
Table tolerances are defaults. XY centering uses a fixed 10% comparison;
height, tilt-overlap, orbital and score tolerances have configurable defaults.

## How It Works

The asset is loaded with a visible matte ground plane (color 0.8, 0.8, 0.8) so the floor is clearly visible in the tilt and spin videos. A directional light (intensity 3000) and a weak dome fill (intensity 150) provide illumination. An orange matte diagnostic material is applied for visibility.

After loading, the asset bounding box and world position are queried directly. The height score and XY centering score are computed from these values before any rotation.

The tilt sweep runs 30 steps from -45 to +45 degrees around the X axis, recording the minimum Z coordinate of the bounding box at each step. Ground penetration is flagged when the minimum Z goes below negative 5 percent of the bounding box height.

The spin sweep runs 30 steps across a full 360-degree rotation around the Z axis, recording the bounding box center in XY at each step. The orbit radius is the largest range in X or Y divided by two. Orbital motion is flagged when the orbit radius exceeds 10 percent of the largest horizontal dimension.

Frames are captured every three steps during both sweeps and encoded as tilt
and spin videos when encoding succeeds. A recoverable producer failure returning
no video is optional and does not change the measured score or advisory
PASS/SKIP; warning/timing transport failures are also best-effort. Unknown encoder
exceptions, unsafe evidence paths, cancellation and unsafe engine/cleanup signals
remain execution errors. Required captures and geometry reads still propagate
their errors.

A visibility pre-check compares the framed view with an asset-hidden control under the same lighting. If fewer than 100 diagnostic-colored pixels are attributable to the asset, the test is reported as SKIPPED (not failed), before bounds are read.

A completed sub-threshold assessment in test version 2.0.3 also publishes the metric
`assessment_advisory.value` with `status: completed`, reason code
`pivot_score_below_recommendation`, and a bounded explanation. This evidence
requires finite, nonempty authored bounds with positive height, a finite origin,
both complete sweeps and successful transform resets. The result remains SKIP
with `pivot_passed: 0`; consumers can display completed advice as nonblocking
without claiming PASS or non-applicability. Early visibility skips, incomplete
or invalid reads, required execution errors and interrupted runs do not publish
this marker. Final execution health and cleanup failures take priority over it.

The marker describes this runtime assessment only. The selected FET001 source
contract still includes `VG.025`; its origin-positioning requirement and static
validation obligations apply independently.

## Failure Cases

A sub-threshold score is SKIP, not FAIL. With the default score threshold,
only the height contribution is necessary to reach PASS:

| Symptom | Likely cause |
|---|---|
| Pivot height score not earned (gating condition) | Asset origin is not at or near the bottom of the bounding box; the pivot is at the object midpoint or at the top |

At the default score threshold, the following conditions reduce the score but
do not independently change pass/skip. Overrides can make them significant:

| Symptom | Advisory diagnostic |
|---|---|
| Pivot horizontal centering fails | Asset origin is offset from the horizontal center; the object drifts when rotated at the world origin |
| Ground penetration detected on tilt | Pivot is above the base; tilting the asset causes the bottom to dip below the ground plane |
| Orbital motion detected on spin | Pivot is not at the horizontal center; rotating the asset around its vertical axis causes it to orbit rather than spin in place |

## How to Fix

Move the asset pivot to the bottom-center of the bounding box. The pivot should be at the ground level (the lowest point of the mesh) and centered horizontally. In most DCC tools this is done by setting the pivot or origin to the base of the object and then freezing or applying the transform.

Refer to the tilt and spin videos when inspecting the origin and geometry.
Overlap or orbit can motivate that inspection, but these bounding-box
observations do not establish a unique cause.

## Expected Result

![pivot expected result](../_images/pivot.png)

[Result video](../../../../../../../../sr_specs/docs/_static/videos/pivot.mp4)

Sampled X-tilt and Z-spin videos show the diagnostic asset and floor reference.
They are authored-geometry probes, not a physical settling/contact simulation.
With 30 default steps, the tilt samples run from -45 to +42 degrees and the
spin samples from 0 to 348 degrees; the endpoints are not both captured.

## Notes and Caveats

A sub-threshold pivot score is reported as SKIPPED, not as a failure. The tilt and spin videos are preserved with an explanatory message so the result can be judged visually. This advisory behavior exists because the correct pivot location depends on the object type. Rotating or hinged objects such as doors or robot joints have their pivot at the rotation center, not at the base. Attached objects such as cameras or wheels have their pivot at the attachment point. Those object types are not ground-placeable props and are not expected to pass this check.

The height tolerance of 10 percent of the bounding box height accommodates minor offsets from DCC tool precision or floating-point rounding. The penetration tolerance of 5 percent allows slight clipping from rounded bases or complex geometry at the bottom of the mesh.

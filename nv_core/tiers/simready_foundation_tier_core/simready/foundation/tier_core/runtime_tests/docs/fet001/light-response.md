# light_response  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | light_response                 |
| Feature(s)   | `FET001_MinimalPlaceableVisual.0-1-0`, `FET001_MinimalPlaceableVisual.1-0-0`, `FET001_MinimalPlaceableVisual.1-0-1`            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.4                          |

## Summary

Samples a directional light orbit around the asset and checks consecutive-image
variation and the fraction of blank frames against configured thresholds.

## What Pass Guarantees

Before scene setup, pixel/frame fractions must be finite real numbers in
`[0, 1]`, step count a whole number of at least two, settling count a nonnegative
whole number, and camera padding/load timeout finite and positive. Booleans,
numeric strings, NaN and infinity are invalid configuration, not measured
asset response. Valid zero fractions and existing defaults remain allowed.
Required image-analysis failures leave execution incomplete; they do not
supply a zero change or blank-frame measurement. Native renderer qualification
is separate from host regression coverage.
At least two captured frames are required to observe a real consecutive
comparison pair; a one-frame override is a configuration error, not an asset
with zero response. Required object counts must be finite nonnegative whole
numbers and measured pair ratios finite fractions. The existing explicit
blank-frame gate still permits its configured fraction of valid empty masks.

A passing result means the sampled frames meet `max_blank_ratio` and their
consecutive-pair variation exceeds `min_variation_ratio`. It demonstrates an
image response in this diagnostic scene, not authored-normal existence,
every normal's correctness, or naturally shaded appearance in every scene.

## What It Checks

The test checks that the shading on the asset varies as a directional light orbits around it. When normals are present and correct, the bright region tracks the light: the face toward the light brightens and the face away from it darkens. When normals are missing or constant, the surface appears the same in every frame because the renderer has no per-vertex direction information to compute Lambert shading from.

The test first frames the asset, captures the current view and an asset-hidden control under the same lighting, and requires at least 100 diagnostic-colored pixels attributable to the asset. It then checks the blank-frame fraction and measures consecutive frame-pair variation as the light advances.

## How It Works

The asset is loaded in a black room (walls color 0, 0, 0) with a directional light (intensity 3000) and a weak dome fill (intensity 150). The black room supports the sweep's non-black pixel mask, while the paired asset-hidden pre-check establishes that the asset itself renders. The dome fill keeps the unlit side from becoming completely black.

An orange matte diagnostic material is applied to eliminate shading contributions from the asset's own materials or texture maps.

The directional light is rotated 360 degrees around the Z axis in 30 steps (`steps = 30`). One frame is captured per step, producing 29 consecutive pairs. For each pair, the fraction of object pixels that changed luminance beyond `pair_change_threshold = 0.03` is measured. A pair counts as "different" when more than 5 percent of object pixels changed (`pair_change_pixel_ratio = 0.05`).

The test passes when more than 10 percent of the 29 pairs are classified as different (`min_variation_ratio = 0.10`). Frames with fewer than 100 object pixels are counted as blank; the test also fails when more than 50 percent of frames are blank (`max_blank_ratio = 0.50`).

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Ten percent or fewer of consecutive frame pairs show luminance variation | Mesh normals are missing; normals are constant (all the same value); the diagnostic material is not modulating shading |
| More than 50 percent of frames have too few object pixels | Asset not rendering; geometry broken or hidden; black room is masking the object |
| Fewer than 100 asset-attributable diagnostic pixels in pre-check | Asset hidden, not loaded, or camera framed incorrectly |

## How to Fix

If the variation ratio is below threshold, inspect lighting, camera framing,
diagnostic material and geometry before assigning a cause. Check authored
normals for confirmed defects and correct those in the DCC tool. A low image
response alone does not prove missing or invalid normals. Re-export and rerun
after any confirmed correction.

If too many frames are blank, verify that the asset has visible Mesh geometry, that no meshes are marked `visibility = invisible`, and that the USD file loads without broken references.

## Expected Result

![light_response expected result](../_images/light-response.png)

[Result video](../../../../../../../../sr_specs/docs/_static/videos/light-response.mp4)

The asset remains stationary while a directional light orbits it. Inspect the
diagnostic surface's shading variation alongside the measured pair-change and
blank-frame ratios. Uniform brightness motivates inspecting the light/material
setup and normals; it does not establish a unique defect.

## Notes and Caveats

The sweep's non-black pixel mask is a sampled response proxy. Room lighting can also produce non-black pixels, so the paired asset-hidden pre-check is required before this analysis.

The dome fill (intensity 150) provides baseline illumination so the unlit side of the asset retains some brightness. Without the dome fill, the unlit side would be too dark for the per-pair comparison to detect small luminance changes.

The 30-step sweep provides 29 consecutive pairs, giving the statistical test enough data points to tolerate a few low-variation transitions near the light's dead-ahead and dead-behind positions, where the per-step change is smallest.

Video encoding is optional presentation when the owned encoder returns `None`
for a recoverable failure, with warnings where available. Unknown engine/session
exceptions and unsafe media paths still propagate, as do required capture/analysis
errors, cancellation and required-cleanup signals.

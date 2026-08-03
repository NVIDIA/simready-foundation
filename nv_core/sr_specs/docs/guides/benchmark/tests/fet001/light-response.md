# light_response  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | light_response                 |
| Feature(s)   | FET001_BASE_NEUTRAL            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.0                          |

## Summary

Rotates a directional light 360 degrees around the asset and verifies that the shading changes between consecutive frames, confirming that mesh normals exist and produce correct Lambert shading.

## What Pass Guarantees

A passing result confirms that the asset's mesh surfaces have authored normals that the renderer reads correctly. Reviewers, PMs, and OEMs can trust the asset will shade naturally in a lit scene, brightening on the side facing a light source and darkening on the opposite side, rather than appearing flat or uniformly lit regardless of the light direction.

## What It Checks

The test checks that the shading on the asset varies as a directional light orbits around it. When normals are present and correct, the bright region tracks the light: the face toward the light brightens and the face away from it darkens. When normals are missing or constant, the surface appears the same in every frame because the renderer has no per-vertex direction information to compute Lambert shading from.

The test runs two checks in sequence. First, it verifies that enough non-black pixels appear across the captured frames, confirming the object is visible. Second, it measures the fraction of consecutive frame pairs where the object pixel luminance changes measurably as the light advances one step.

## How It Works

The asset is loaded in a black room (walls color 0, 0, 0) with a directional light (intensity 3000) and a weak dome fill (intensity 150). The black room makes object masking straightforward because any non-black pixel belongs to the object. The dome fill ensures the unlit side of the asset is never completely black, which would make the per-pair comparison harder to read.

An orange matte diagnostic material is applied to eliminate shading contributions from the asset's own materials or texture maps.

The directional light is rotated 360 degrees around the Z axis in 30 steps (`steps = 30`). One frame is captured per step, producing 29 consecutive pairs. For each pair, the fraction of object pixels that changed luminance beyond `pair_change_threshold = 0.03` is measured. A pair counts as "different" when more than 5 percent of object pixels changed (`pair_change_pixel_ratio = 0.05`).

The test passes when more than 10 percent of the 29 pairs are classified as different (`min_variation_ratio = 0.10`). Frames with fewer than 100 object pixels are counted as blank; the test also fails when more than 50 percent of frames are blank (`max_blank_ratio = 0.50`).

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Ten percent or fewer of consecutive frame pairs show luminance variation | Mesh normals are missing; normals are constant (all the same value); the diagnostic material is not modulating shading |
| More than 50 percent of frames have too few object pixels | Asset not rendering; geometry broken or hidden; black room is masking the object |
| Diagnostic color not detected in pre-check | Asset not loaded or camera framed incorrectly |

## How to Fix

If the variation ratio is below threshold, the mesh surfaces do not have authored normals or the normals are not being read by the shader. In your DCC tool, recalculate normals from the mesh surface for all meshes. Ensure normals are exported with the mesh and that no export setting strips them. Re-export the asset and re-run the test.

If too many frames are blank, verify that the asset has visible Mesh geometry, that no meshes are marked `visibility = invisible`, and that the USD file loads without broken references.

## Expected Result

![light_response expected result](../_images/light-response.png)

[Result video](../../../../_static/videos/light-response.mp4)

The asset stationary at center, with a directional light orbiting around it. The orange diagnostic surface brightens on the side facing the light and darkens on the lee side, with the bright and dark regions tracking the light position smoothly across frames. A surface with uniform brightness throughout means the normals are not being read by the shader.

## Notes and Caveats

The black room makes object pixel masking trivial: non-black pixels are object pixels. Background noise from RTX accumulation is excluded from the variation analysis.

The dome fill (intensity 150) provides baseline illumination so the unlit side of the asset retains some brightness. Without the dome fill, the unlit side would be too dark for the per-pair comparison to detect small luminance changes.

The 30-step sweep provides 29 consecutive pairs, giving the statistical test enough data points to tolerate a few low-variation transitions near the light's dead-ahead and dead-behind positions, where the per-step change is smallest.

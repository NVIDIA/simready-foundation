# presence  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | presence                       |
| Feature(s)   | `FET001_MinimalPlaceableVisual.0-1-0`, `FET001_MinimalPlaceableVisual.1-0-0`, `FET001_MinimalPlaceableVisual.1-0-1`            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.1                          |

## Summary

Renders the asset under uniform dome lighting with a diagnostic orange matte material and verifies that visible pixels of the diagnostic color appear in the captured frame.

## What Pass Guarantees

Before scene mutation, `min_diff_ratio` must be a finite real fraction in
`[0, 1]`, settling a nonnegative whole count, and camera padding/load timeout
finite and positive. Booleans, numeric strings and nonfinite values are
configuration errors. Zero is still a valid configured difference threshold.
The measured difference must itself be a finite fraction; unavailable/invalid
analysis is a runtime error, never an implicit PASS.

A passing result confirms that the diagnostic-color visibility pre-check succeeds
and the hidden-versus-visible frame difference reaches `min_diff_ratio` in this
view. It does not certify every reference, geometry extent, original material
binding, or hidden component. Original materials are replaced for this probe.

## What It Checks

The test verifies that the asset produces visible geometry in the rendered frame. It first checks that the diagnostic orange material is visible in the scene, confirming that the camera is correctly framed on the asset. It then captures two frames: one with the asset hidden and one with the asset shown. The pixel-by-pixel difference between the two frames must exceed a minimum threshold (default 1 percent) for the test to pass.

This image procedure has no Mesh-type gate. Rendered non-mesh geometry can meet
the pixel criterion; any separate static Mesh requirement belongs to validation.

## How It Works

The asset is loaded in a white room with dome-only lighting (intensity 1000). No directional light is used because a directional light would illuminate the walls unevenly. An orange matte diagnostic material (roughness 1.0, metallic 0.0) is applied to all surfaces so that material-dependent rendering issues such as transparent or broken textures do not affect the result.

The camera is framed with a padding factor of 1.2. Before framing, the asset is allowed to settle for five frames so that bounding box computation operates on fully loaded geometry. If the orange diagnostic color is not detected in the pre-check frame, the test fails immediately, indicating the asset is not on screen.

After the pre-check passes, the test hides the asset, captures a background reference frame, shows the asset again, and captures a visible frame. The two frames are compared pixel-by-pixel. The default minimum difference ratio is 1 percent (`min_diff_ratio`). A ratio below this threshold means the asset produced no measurable change in the frame and the test fails.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Diagnostic color not detected in pre-check | Asset not loaded, bounding box invalid, or camera framed on invisible helper geometry rather than the mesh |
| Visible and hidden frames differ by less than 1 percent | No renderable Mesh geometry; all meshes hidden; broken USD references; zero-extent geometry |

## How to Fix

If the diagnostic color pre-check fails, confirm that the asset file loads without errors and that the USD hierarchy contains at least one visible Mesh prim. Check that the bounding box is not dominated by invisible helper prims that push the mesh off screen.

If the frame comparison fails, confirm that at least one Mesh prim has valid geometry and is not marked `visibility = invisible`. Verify the USD file loads without broken references. Ensure the geometry has valid extent attributes so the renderer can produce pixels.

## Expected Result

![presence expected result](../_images/presence.png)

A single still frame showing the asset rendered as a uniform orange shape against a white background. The asset should be clearly visible and fill a recognizable portion of the frame. A blank or near-blank frame indicates failure.

## Notes and Caveats

The white room and dome-only lighting ensure a uniform, predictable background. The orange diagnostic material eliminates any influence from the asset's own materials, including transparent shaders or broken texture bindings.

The very low 1 percent threshold accommodates small objects that occupy few pixels in the frame. Larger objects must meet the same threshold but will typically produce a much larger difference.

Non-mesh geometry is not explicitly rejected by this procedure. A runtime pixel
pass does not establish that the asset satisfies a feature's static Mesh rule.

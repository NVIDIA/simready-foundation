# presence  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | presence                       |
| Feature(s)   | FET001_BASE_NEUTRAL            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.0                          |

## Summary

Renders the asset under uniform dome lighting with a diagnostic orange matte material and verifies that visible pixels of the diagnostic color appear in the captured frame.

## What Pass Guarantees

A passing result confirms that the asset has at least one renderable mesh surface that produces pixels when loaded into the engine. Reviewers, PMs, and OEMs can trust that the asset is not an invisible placeholder, does not consist solely of broken or missing references, and does not rely on hidden or zero-extent geometry to satisfy the file structure.

## What It Checks

The test verifies that the asset produces visible geometry in the rendered frame. It first checks that the diagnostic orange material is visible in the scene, confirming the camera is correctly framed on the asset. It then captures two frames: one with the asset hidden and one with the asset shown. The pixel-by-pixel difference between the two frames must exceed a minimum threshold (default 1 percent) for the test to pass.

Assets that consist only of non-mesh geometry such as curves or points can fail this test by design. The test requires at least one Mesh prim with valid geometry.

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

If the diagnostic color pre-check fails, confirm the asset file loads without errors and that the USD hierarchy contains at least one visible Mesh prim. Check that the bounding box is not dominated by invisible helper prims that push the mesh off screen.

If the frame comparison fails, confirm that at least one Mesh prim has valid geometry and is not marked `visibility = invisible`. Verify the USD file loads without broken references. Ensure the geometry has valid extent attributes so the renderer can produce pixels.

## Expected Result

![presence expected result](../_images/presence.png)

A single still frame showing the asset rendered as a uniform orange shape against a white background. The asset should be clearly visible and fill a recognizable portion of the frame. A blank or near-blank frame indicates failure.

## Notes and Caveats

The white room and dome-only lighting ensure a uniform, predictable background. The orange diagnostic material eliminates any influence from the asset's own materials, including transparent shaders or broken texture bindings.

The very low 1 percent threshold accommodates small objects that occupy few pixels in the frame. Larger objects must meet the same threshold but will typically produce a much larger difference.

Assets that have only non-mesh geometry (curves, points) can fail this test even when geometry is present. This is expected behavior: the feature requires Mesh representation.

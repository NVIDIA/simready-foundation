# normals_xz  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | normals_xz                     |
| Feature(s)   | FET001_BASE_NEUTRAL            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.0                          |

## Summary

Rotates the asset through a combined X and Z axis sweep under uniform dome lighting and verifies that the diagnostic surface remains evenly bright, confirming surface normals face outward.

## What Pass Guarantees

A passing result confirms that the mesh normals point outward at the face orientations sampled across a combined pitch-and-yaw rotation sweep, including diagonal faces such as bevels, chamfers, and angled panels. Reviewers, PMs, and OEMs can trust the asset will not display dark patches on oblique surfaces when placed in a lit scene.

## What It Checks

The test checks that no significant portion of the visible surface appears abnormally dark during a combined X-and-Z rotation sweep. Under uniform dome lighting, a surface with outward-facing normals appears evenly lit from all angles. A surface with inverted normals faces inward and receives no illumination from the dome, producing dark patches in the rendered frame.

The combined rotation (X at 70 percent amplitude, Z at 100 percent) sweeps the asset through diagonal angles where beveled, chamfered, or angled faces become visible. A rotation around a single axis would keep many of these faces edge-on and miss the defect.

## How It Works

The asset is loaded in a white room with dome-only lighting (intensity 2000) and an orange matte diagnostic material. Double-sided rendering is enabled during capture so that face culling does not interfere with the dark-pixel analysis.

Eight rotation steps are captured (`steps = 8`). At each step the asset is rotated with X at 70 percent of the step angle and Z at 100 percent (`rotate_asset_multi`). The camera is re-framed after each rotation. For each frame, object pixels are masked against the white background and the fraction of dark pixels (luminance below `dark_threshold = 0.15`) is measured.

A frame is counted as a problem frame when more than 50 percent of its object pixels are dark (`max_problem_ratio = 0.50`). The test fails when the number of problem frames reaches or exceeds two (`min_problem_frames = 2`). This threshold prevents a single interior-exposed angle from failing the test.

A visibility pre-check runs before the sweep. If the orange diagnostic color is not detected, the test fails immediately.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Two or more rotation frames show more than 50 percent dark object pixels | Surface normals on one or more faces are inverted; affected faces receive no dome illumination |
| Diagnostic color not detected in pre-check | Asset not loaded or camera framed incorrectly |

## How to Fix

If the rotation sweep shows dark frames, the affected faces have inverted normals. In your DCC tool, select the dark faces and flip their normals so they face outward. Then recalculate normals to ensure they are not zero-length or not-a-number values. Re-export the asset and re-run the test.

The combined X-and-Z sweep is specifically designed to expose diagonal faces that a single-axis rotation keeps edge-on. If only a small number of diagonal faces are affected, they might only appear dark during the XZ sweep and not during purely horizontal or vertical rotation.

## Expected Result

![normals_xz expected result](../_images/normals-xz.png)

[Result video](../../../../_static/videos/normals-xz.mp4)

The asset rotating around a tilted axis combining pitch and yaw, lit uniformly. The orange diagnostic surface is evenly bright at every frame. Dark patches at oblique angles indicate inverted normals on faces that face neither a pure horizontal nor a pure vertical direction.

## Notes and Caveats

Dome-only lighting is used so that every face with outward-pointing normals receives equal illumination regardless of its orientation. A directional light would produce natural shading variation that would be indistinguishable from inverted-normal darkening.

The `min_problem_frames = 2` threshold prevents a false failure when a hollow object's interior is briefly exposed at one rotation angle. A single interior-exposed frame is not treated as a defect.

Object pixels with fewer than 100 total pixels in a frame are excluded from the problem-frame count to avoid false positives from edge-on or heavily foreshortened poses.

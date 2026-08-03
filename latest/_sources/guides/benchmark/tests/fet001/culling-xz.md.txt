# culling_xz  (FET001 Visual)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | culling_xz                     |
| Feature(s)   | FET001_BASE_NEUTRAL            |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 2.0.0                          |

## Summary

Rotates the asset through a combined X and Z axis sweep, captures paired frames with back-face culling off and on, and verifies the two frames match, confirming face winding order is correct.

## What Pass Guarantees

A passing result confirms that the mesh face winding is consistent and correct at the face orientations sampled across a combined pitch-and-yaw rotation sweep. Reviewers, PMs, and OEMs can trust the asset will not display holes in its silhouette or faces that appear to show through the mesh when the renderer applies back-face culling.

## What It Checks

The test checks that back-face culling does not change the visible appearance of the asset. With correct counter-clockwise winding, all outward-facing polygons remain visible whether culling is off or on. With incorrect winding on any face, enabling culling causes that face to disappear or reveals the inside of the mesh, producing a measurable difference in the frame.

The combined rotation (X at 70 percent amplitude, Z at 100 percent) sweeps the asset through diagonal angles where chamfered, beveled, or angled faces become front-facing. A single-axis rotation keeps many of these faces edge-on and would miss winding defects that only appear at oblique view angles.

## How It Works

The asset is loaded in a white room with dome lighting (intensity 1000) and an orange matte diagnostic material. Eight rotation steps are captured (`steps = 8`). At each step the asset is rotated, the camera is re-framed, and two frames are captured in sequence:

1. Culling off: `doubleSided = True`. Both faces of every polygon are rendered.
2. Culling on: `doubleSided = False` (the Omniverse renderer uses `singleSided` as the primary face culling authority). Only outward-facing polygons are rendered.

The two frames are compared using an object-masked per-pixel difference on the white background (`pixel_threshold = 0.20`). The maximum difference ratio across all step pairs is compared against `different_ratio_threshold = 0.10` (10 percent of object pixels). The test passes when no step pair exceeds this threshold.

A visibility pre-check runs before the sweep. If the orange diagnostic color is not detected, the test fails immediately.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Any rotation step shows more than 10 percent object pixel difference between culling-off and culling-on frames | One or more faces have incorrect (clockwise) winding order; enabling culling removes those faces |
| No frames captured | Configuration error; `steps` is zero or the viewport is not rendering |
| Diagnostic color not detected in pre-check | Asset not loaded or camera framed incorrectly |

## How to Fix

If paired frames differ at any rotation angle, the affected faces have incorrect winding order. In your DCC tool, select the faces that disappear when culling is enabled, flip their winding to counter-clockwise, and recalculate normals outward. Re-export the asset and re-run the test.

The combined X-and-Z sweep is specifically designed to expose diagonal faces that a single-axis rotation keeps edge-on. Winding defects on chamfered or angled surfaces might only appear during the combined rotation.

If no frames are captured, verify that `steps` is greater than zero in the test configuration, that the viewport extension is loaded, and that the asset bounds resolve to non-zero extents.

## Expected Result

![culling_xz expected result](../_images/culling-xz.png)

[Result video](../../../../_static/videos/culling-xz.mp4)

The asset rotating around a tilted axis combining pitch and yaw. The orange diagnostic surface fills the silhouette at every frame. Holes in the silhouette or faces that appear to show through the mesh when culling is enabled indicate incorrect winding only visible at oblique angles.

## Notes and Caveats

The Omniverse renderer uses `singleSided` as the primary face culling authority. The test sets `doubleSided = False` (culling on) rather than relying on any other material flag to ensure the comparison reflects the renderer's actual culling behavior.

Object-masked comparison on a white background excludes background noise from the per-pixel difference calculation, ensuring only changes within the object silhouette contribute to the result.

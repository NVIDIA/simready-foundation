# render_product_output  (FET035 Render Products)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | render_product_output          |
| Feature(s)   | FET035_RenderProducts.RTX  |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.1                          |

## Running with simready-evaluate

This test ships in `simready-foundation-tier-sensors`, under the Python package
`simready.foundation.sensors.runtime_tests`.
Run it against an asset:

```bash
simready-evaluate --assets path/to/asset.usd --features FET035
```

The test skips automatically if no authored `RenderProduct` prim is found (excluding OmniverseKit internal prims).

## Summary

Reads the camera path, resolution, and AOV source names from each authored
`RenderProduct` prim, then creates a matching Replicator render product and
reads back AOV data to confirm each declared annotator produces non-empty
output. Output images are saved per annotator for visual inspection.

## What Pass Guarantees

For the camera render products actually exercised, matching Replicator
annotators returned real, non-empty array data; geometry annotators also
returned at least one nonzero value. Static validation separately checks
authored wiring. Products with absent camera/source names and OmniLidar products
are excluded from this measurement, so PASS alone does not prove full authored
product coverage or end-to-end SDG readiness.

## What It Checks

For each authored `RenderProduct` prim, the test reads the `camera` relationship,
`resolution`, and `sourceName` values from `orderedVars`. If the camera or source
names are absent the prim is silently skipped. For `RenderProduct` prims whose
camera is a USD `Camera` prim, a Replicator render product is created with the same
camera and resolution, a writer is attached that collects the annotator matching each
`sourceName`, Replicator is stepped until the writer has received output from every
annotator (at most `max_capture_steps` frames), and data is verified:

- **Color annotators** (`LdrColor`, `HdrColor`, semantic annotators): pass on
  non-empty array alone. The color image shows the reference cube lit by the
  test's own light; it is not checked for brightness.
- **Geometry annotators** (`DepthLinearized`, `normals`, etc.): additionally
  require at least one non-zero value, confirming geometry is visible from
  the camera.

A reference cube is placed 2 m in front of each camera along its world-space
forward direction so geometry annotators have meaningful hits, together with a
distant light shining along the camera's viewing direction so the cube's visible
face is lit in color images.

`OmniLidar` prims are skipped — multiple RTX LiDAR sensors in the same
Replicator pass cause a CUDA conflict. Their point cloud output is covered by
the `lidar_point_cloud` test.

Configuration and fallback:

- `warmup_frames`: 30 (physics + timeline frames before triggering the Replicator step)
- `max_capture_steps`: 10 (Replicator frames to wait for a new render product to deliver output)
- Fixed resolution fallback: (512, 512) if the authored RP has no `resolution` attribute

## How It Works

**Stage traversal:** `RenderProduct` prims are typically authored in a `/Render` scope that is a sibling of the asset's `defaultPrim`. The framework's `load_asset()` references only the `defaultPrim` subtree, making `/Render` invisible to the composed stage. The test opens the raw asset file via `Usd.Stage.Open(ctx.asset_path)` to traverse all prims including `/Render`.

**Property reading:** for each authored `RenderProduct` (excluding OmniverseKit internal prims), the test reads the `camera` relationship, `resolution`, and `sourceName` values from `orderedVars` directly from the raw asset stage. RenderProducts with a missing camera or no source names are silently skipped.

**Camera path remapping:** camera prim paths from the raw asset (e.g. `/Root/RGB_Camera`) are remapped to their equivalents in the composed stage (where cameras were loaded under the framework's path prefix). Remapping preserves the camera's path relative to the asset's `defaultPrim`, so cameras that share a name under different parents (for example `front/left/camera` and `back/left/camera`) stay distinct. A camera outside the `defaultPrim` subtree is reported as not found.

**Replicator AOV check:** for each `Camera`-typed render product:
1. A 0.4 m reference cube is placed 2 m along the camera's world-space forward direction so depth and normals annotators have geometry to sample, and a distant light with the camera's world rotation is added so color annotators see the cube's face lit (a Camera and a DistantLight both point along local -Z; a light left at the default downward orientation leaves that face dark).
2. `rep.create.render_product(cam_path, resolution)` creates a Replicator-managed render product mirroring the authored camera and resolution.
3. `rep.annotators.get(source_name)` is called for each authored `sourceName`, then a custom `rep.Writer` that collects those annotators is attached to the render product. API exceptions propagate with their causes as execution errors; an exception alone does not establish that a name is unregistered.
4. `rep.orchestrator.step_async()` is called until the writer has received output from every annotator, up to `max_capture_steps` frames. The writer's `write()` runs once for each frame the render product really produces, so a step that produced no frame, or output that is `None`, empty, has no finite samples, or (for geometry annotators) is all-zero, is followed by another step rather than judged immediately. A render product created during the test may not deliver on its first frame.
5. Annotator data is validated: color annotators pass on non-empty array; geometry annotators additionally require at least one non-zero value.
6. The writer is detached and the render product is destroyed, and the reference cube and light are removed, before the next camera is checked. Replicator render products keep rendering until destroyed, so without this a stage with many cameras slows every later product down, and a leftover cube shadows and appears in other cameras' images.

`OmniLidar` prims are identified by their type in the composed stage and skipped for the Replicator check (CUDA conflict). Their point cloud output is covered by the `lidar_point_cloud` test.

Output images are saved to the run output directory (one PNG per annotator per Camera RenderProduct). The `LdrColor` image shows a lit grey cube; the companion `_alpha.png` file confirms geometry hits. Depth and normals images are saved as normalized grayscale.

Required reference-geometry setup, render-product creation, attachment, stepping,
and readback errors prevent a measured verdict. `None`, empty arrays, and
malformed object/scalar data are unavailable output and produce execution errors;
`None`, empty and all-NaN/Inf output is reported only after `max_capture_steps`
frames, and the error states how many frames were stepped. A failing step is not
retried.
For dictionary responses, the array is read from `data`, not from metadata.
Numeric AOV arrays with no finite samples (all NaN/Inf) are likewise unavailable
measurement and produce execution errors. If at least one finite sample exists,
the current color/geometry content checks apply to the original array. This is
an availability check, not an all-pixel finiteness or image-quality criterion.
Replicator stop is attempted on every exit, including early exceptions; a stop
error cannot replace an earlier acquisition cause. PNG publication is optional
and does not change the measured verdict.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Render-product creation, annotator setup, stepping, or readback API exception | Execution error; inspect the retained cause and runtime diagnostics before attributing it to authored data. |
| Geometry annotator all-zero | No geometry is visible from the camera, still all-zero after `max_capture_steps` frames — check camera transform and cube placement. |
| Camera not found in composed stage | The authored camera path is outside the asset's `defaultPrim` subtree or does not exist. |
| Annotator returned None, empty, or malformed data | Execution error: required measurement was unavailable, after up to `max_capture_steps` frames. This alone does not identify an asset defect. |
| Numeric array contains no finite samples | Execution error: measurement is unavailable. Mixed finite/nonfinite arrays keep the existing content checks; zero semantic output remains allowed and all-zero geometry remains a measured failure. |
| Test skipped | No authored `RenderProduct` prim was found. OmniLidar products and products missing camera/sourceNames are excluded inside the loop without a separate skip verdict. |
| Static validation failed | The asset did not pass RP.001–RP.003. Fix the static issues first. |

## How to Fix

If runtime diagnostics establish an unregistered annotator, verify that the `sourceName` attribute on
the `RenderVar` prim matches a name in the Replicator annotator registry.
Common valid names include `LdrColor`, `HdrColor`, `DepthLinearized`,
`normals`, `SemanticSegmentation`, and `GenericModelOutput`.

If geometry annotators are all-zero, confirm that the camera prim's world
transform is correctly authored so the reference cube falls within the
camera's field of view.

## Expected Result

The evaluation test writes one PNG per annotator per Camera RenderProduct to the
run output directory. File names follow the pattern `{rp_name}_{src_name}.png`
(e.g. `RGB_CameraRp_normals.png`). Color annotators (LdrColor, HdrColor) that
have an alpha channel also produce a companion `_alpha.png` file.

![render-product-output expected result](../_images/render-product-output.png)

The `normals` annotator output for the `RGB_CameraRp` render product from the
PASS fixture (`RenderProductsCheckerPass.usda`). The reference cube placed 2 m
in front of the camera appears as a coloured patch — each colour encodes the
surface normal direction. The surrounding grey background corresponds to the
far-clip plane (no geometry hit). A non-grey patch confirms that the camera,
render product wiring, and `normals` annotator are all functioning correctly.

The `LdrColor` image shows the reference cube as a lit grey shape, and the
`_alpha.png` companion image shows white pixels where the cube geometry was hit. The `DepthLinearized` image shows a dark square (near
cube) on a white background (far clip plane).

## Notes and Caveats

**Scope limitation — Replicator creates its own render product:**
`rep.create.render_product()` creates a Replicator-managed render product
rather than activating the authored `RenderProduct` prim in the stage. The
test mirrors the authored configuration (camera path, resolution, sourceName
values) but does not route output through the authored
`RenderProduct → orderedVars → RenderVar` chain. Direct Hydra activation of
the authored prims is outside this test's coverage.

**Full pipeline verification — future work:**
End-to-end verification that the authored `RenderProduct → RenderVar` chain
actually writes the declared AOVs to disk would need to exercise the existing
authored paths rather than create new render products. The current test does
not provide that end-to-end evidence.

**Color annotator image appearance:**
The `LdrColor` image shows the cube lit by a distant light that the test adds
along each camera's viewing direction; a light at the default orientation would
leave the visible face dark. The `_alpha.png` companion image confirms
geometry is present (white pixels where the cube is hit). The depth and
normals images are more informative for visual inspection.

**OmniLidar RenderProducts:**
`OmniLidar` prims are skipped for the Replicator check because running two
RTX LiDAR sensors with the `GenericModelOutput` annotator in the same
Replicator pass causes a CUDA memory conflict and crashes Isaac Sim. Point
cloud output is verified by the `lidar_point_cloud` test.

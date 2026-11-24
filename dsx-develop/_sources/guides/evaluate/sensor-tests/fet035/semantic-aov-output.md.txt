# semantic_aov_output  (FET035 Render Products)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | semantic_aov_output            |
| Feature(s)   | FET035_RenderProducts.RTX  |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.2                          |

## Running with simready-evaluate

This test ships in `simready-foundation-tier-sensors`, under the Python package
`simready.foundation.sensors.runtime_tests`.
Run it against an asset:

```bash
simready-evaluate --assets path/to/asset.usd --features FET035
```

The test skips automatically if no `RenderProduct` with semantic RenderVars is found.

## Summary

Replicator runtime check for semantic AOV RenderVars: confirms that each
semantic annotator declared in `orderedVars` is registered in Replicator and
produces non-empty output when the render pipeline runs. BLOSC compression
(RP.004) is enforced by static validation, not by this evaluation test.

## What Pass Guarantees

For the semantic render products exercised, the corresponding Replicator
annotators returned real, non-empty arrays. This confirms in-memory output for
this run. Static validation separately checks authored BLOSC configuration
(RP.004); this procedure does not verify compression of a written file.
Label coverage is reviewed through the diagnostic image and label mapping;
unlabelled geometry does not change the non-empty-output acceptance criterion.

## What It Checks

For each `RenderProduct` whose `orderedVars` includes a semantic `RenderVar`:

- A matching Replicator render product is created using the authored camera
  path and resolution (`rep.create.render_product()`).
- `SemanticSegmentation` selects Replicator's `semantic_segmentation` annotator,
  which returns pixels with their label mapping. Other semantic `sourceName`
  values are passed directly to `rep.annotators.get()`. A custom
  `rep.Writer` collecting those annotators is attached to the render product.
  API exceptions retain their causes as execution errors; the exception alone
  does not prove an authored name is invalid.
- Replicator is stepped until the writer has received output from every
  annotator (at most `max_capture_steps` frames) and each annotator's output is
  verified to be a non-empty array.
- The render product is destroyed once it has been checked.

Data values may be all-zero when no prims carry `SemanticAPI` labels (expected
for minimal test fixtures) — the check requires non-empty arrays, not
non-zero values.

Selection and configuration:

- `asset_load_timeout`: 30 seconds
- `max_capture_steps`: 10 (Replicator frames to wait for a new render product to deliver output)
- Fixed selection: case-insensitive `"semantic"` source-name prefix
- Up to `max_capture_steps` Replicator steps per selected render product; no separate warmup loop

## How It Works

1. The raw asset stage is opened so authored `RenderProduct` prims outside the
   referenced default-prim subtree are visible. Their `orderedVars` targets
   are inspected for semantic `sourceName` values. Products without a camera
   target or semantic names are excluded.
2. Each selected raw camera path is remapped to the composed stage by its path
   relative to the asset's `defaultPrim`, so cameras that share a name under
   different parents stay distinct. A Replicator render product is created
   with that camera and the authored resolution (fallback 512 × 512).
3. A writer collecting the semantic annotators is attached, then Replicator is
   stepped until the writer has received output from every annotator, at most
   `max_capture_steps` frames: a new render product may not deliver on its first
   frame, and the writer's `write()` runs once for each frame really produced.
   Dictionary responses
   use the `data` member for availability checks and retain `idToLabels`
   (or `info.idToLabels` in legacy payloads)
   from the captured frame for diagnostic colorization. `None`, empty arrays,
   and malformed object/scalar data produce execution errors. Valid all-zero
   arrays remain accepted. Numeric arrays must contain at least one finite
   sample; all-NaN/Inf arrays are unavailable measurement and produce execution
   errors, reported only after `max_capture_steps` frames; the error states how
   many were stepped. Mixed finite/nonfinite arrays retain the non-empty content
   criterion; the procedure imposes no all-pixel finiteness or image-quality
   threshold. A failing step is not retried.
4. Replicator stop is attempted on every exit, including setup/readback errors.
   A cleanup exception does not replace the original acquisition cause.
   Saving the optional diagnostic PNG and JSON cannot change measurement
   acceptance. Diagnostic write failures are logged as warnings.
   Each render product's annotators are detached and the product is destroyed
   once it has been checked: Replicator render products keep rendering until
   destroyed, so on a stage with many cameras they would otherwise slow every
   later product down.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Creation, annotator setup, stepping, or readback exception | Execution error; inspect the original cause and runtime diagnostics before diagnosing authored data. |
| Annotator returned None, empty, or malformed data | Execution error: required output is unavailable (after up to `max_capture_steps` frames), not evidence of an authored violation. |
| Camera not found in composed stage | The authored camera path is outside the asset's `defaultPrim` subtree, does not exist, or is not a Camera. |
| Numeric array contains no finite samples | Execution error: measurement is unavailable. A valid all-zero semantic array still passes, and mixed finite/nonfinite arrays keep the existing content criterion. |
| Test skipped | No eligible RenderProduct with a camera target and semantic RenderVars was found in the raw asset. |
| Static validation failed | Asset did not pass RP.004 (`srtx:compression:type` missing or not `"blosc"`). Fix the static issue first. |

## How to Fix

For a separately established RP.004 static violation, set
`srtx:compression:type = "blosc"` on every semantic `RenderVar` prim:

```usd
def RenderVar "SemanticSegmentation"
{
    uniform string sourceName = "SemanticSegmentation"
    uniform string srtx:compression:type = "blosc" (
        allowedTokens = ["hevc", "h264", "av1", "blosc"]
    )
}
```

## Expected Result

The evaluation test writes one PNG per semantic annotator per Camera RenderProduct
to the run output directory. File names follow the pattern
`{rp_name}_{src_name}.png` (e.g. `CameraRp_SemanticSegmentation.png`).

For two-dimensional `uint32` segmentation output, `info.idToLabels` determines
which IDs have semantic labels. ID 0 and IDs labelled `BACKGROUND`, `UNLABELLED`,
or `UNLABELED` (case-insensitive) are black. Labelled IDs receive colors from
the diagnostic palette. IDs with absent or empty label metadata also remain
black and produce a warning; their identity is recorded as unresolved.

A same-stem JSON sidecar records:

- `idToLabels`: the captured annotator mapping, including background and unlabelled entries.
- `idToColor`: the RGB color assigned to each ID observed in the image.
- `unmappedIds`: nonzero IDs observed without usable label metadata.

Use this mapping to distinguish unlabelled pixels from unresolved IDs and to
identify classes when the finite palette repeats. Colors are diagnostic and
can change between captures as the observed classes change.
Other semantic annotators are saved as normalized grayscale.

![semantic-aov-output expected result](../_images/semantic-aov-output.png)

Semantic segmentation output for the `CameraRp` render product from the PASS
fixture (`SemanticAovCompressionCheckerPass.usda`). Three labeled prims are
visible — box, ball, pillar — each rendered as a solid
color. Black regions represent background, unlabelled pixels, or unresolved IDs
as recorded in the JSON sidecar. Colored regions for labelled classes confirm
that the in-memory semantic annotator pipeline produced distinct label values
in that run. The image does not verify written BLOSC compression.

## Notes and Caveats

**Relationship to static validation:**
RP.004 (`srtx:compression:type = "blosc"`) is enforced by the static validator,
not by this evaluation test. The evaluation adds genuine runtime value: it confirms
the semantic annotator names in `sourceName` are registered in Replicator and
the pipeline produces output — neither of which the static validator can verify.

**Data values and semantic labels:**
Semantic annotator output may be all-zero when no prims in the stage carry
`SemanticAPI` labels. This is expected for the minimal test fixtures and does
not indicate a failure — the check requires non-empty arrays, not non-zero
values.

**Compression format verification:**
The `srtx:compression:type` attribute controls how semantic AOV output is
compressed when written to disk by a Replicator writer. The writer this test
attaches only collects in-memory numpy arrays, to which compression has not been
applied. Full end-to-end verification of the BLOSC compression on
output files requires a Replicator file-writing pass and EXR header inspection,
which is deferred (the `OpenEXR` library is also not bundled in Isaac Sim's
Python environment).

**BLOSC compression rationale:**
BLOSC is lossless and preserves integer label values exactly. Lossy codecs
(`"hevc"`, `"h264"`) corrupt integer segmentation labels, making them
unusable for training. This is why RP.004 enforces BLOSC for semantic AOVs.

Non-semantic AOVs (`"LdrColor"`, `"DepthLinearized"`, etc.) are not checked
by this test — their compression format is unrestricted.

# Segmentation AOV (FET011 Semantic Labels)

Two tests, run as a pair.

| Property     | Value                                                        |
|--------------|--------------------------------------------------------------|
| Test names   | `semantic_labels_seg_labelled`, `semantic_labels_seg_stripped` |
| Feature(s)   | `FET_011_STANDARD` (>=0.2.0), `FET_011_RTX` (>=0.1.0)        |
| Engine       | Kit / Isaac Sim (>=6.0)                                      |
| Test version | 1.0.0                                                        |

## Summary

`semantic_labels_seg_labelled` renders the RTX semantic-segmentation AOV of the asset as authored
and measures the fraction of the frame that resolves to a semantic label.

`semantic_labels_seg_stripped` frames the same asset identically, removes every
`SemanticsLabelsAPI` and deprecated `SemanticsAPI` schema from the label sources `SL.001`
recognises, and renders again. The buffer should come back blank.

## What Pass Guarantees

Together they show the asset's labels are honored by the RTX segmentation pipeline, and that the
segmentation comes from those labels rather than from scene setup or incidental geometry. The
stripped test is what makes the first meaningful: a populated buffer alone could be produced by
anything in frame.

Label *format* correctness is not re-checked here — the offline validator is authoritative for
that. This pair checks that the labels *render*.

## What It Checks

Both tests load the asset, add a neutral room, add a dome light, auto-frame the camera with
`camera_padding` 1.2, and settle for `settle_frames` 5 frames. Each then attaches a colorized
`semantic_segmentation` annotator to the viewport's existing render product and steps the
orchestrator once with `render_subframes` 4.

- **`semantic_labels_seg_labelled`** — segmented coverage must reach `on_coverage_min`, default
  `0.005`. The threshold is low on purpose: a small prop framed with padding covers only a few
  percent, and the question is whether anything segments at all, not how large the object is.
- **`semantic_labels_seg_stripped`** — after the strip, segmented coverage must fall to
  `off_coverage_max` or below, default `0.002`. Not zero: AOV edge pixels and denoiser fringing
  leave a few stray samples.

Coverage is measured as the fraction of pixels outside the single most common colour, rather than
against a known background colour, because the AOV's colour assignment is not stable between runs.

The strip walks the sources `SL.001` resolves a label from — the prim, its ancestors, its computed
bound material and that material's ancestors, and its `GeomSubset` children — so it removes exactly
what the requirement counts, including a bound material living outside the asset subtree. It is
applied in the session layer before the single orchestrator step, so no re-render is needed.

## Execution Model

The two tests run in **separate engine sessions**. Replicator's orchestrator can be stepped only
once per session; a second step ends the process regardless of what happens in between. Each test
therefore gets a fresh session and steps exactly once, which is why the labelled and stripped
measurements are two tests rather than one before/after test.

## Metrics

| Metric | Test | Meaning |
|---|---|---|
| `semantic_labels_on_coverage` | labelled | fraction of the frame that segmented, as authored |
| `semantic_labels_labelled_passed` | labelled | 1 when coverage reached `on_coverage_min` |
| `semantic_labels_off_coverage` | stripped | fraction that still segmented after the strip |
| `semantic_labels_stripped_prims` | stripped | number of prims the strip edited |
| `semantic_labels_stripped_passed` | stripped | 1 when coverage fell to `off_coverage_max` or below |

`semantic_labels_seg_stripped` skips, rather than fails, when the asset carries no semantics to
strip; in that case the labelled test reports the same asset as unlabelled.

## Evidence

Each test attaches its segmentation frame: `semantic_labels_semseg_labelled` and
`semantic_labels_semseg_stripped`. The labelled test also captures an RGB frame,
`semantic_labels_rgb`.

## Common Failure Modes

- **Labelled coverage near zero.** No resolvable label on the visible meshes, a schema applied
  with no authored value, or an Isaac Sim older than 6.0, which does not resolve
  `SemanticsLabelsAPI` in the segmentation pass. Check the asset is in frame.
- **Stripped coverage still high.** Something other than the asset's own labels is driving the
  segmentation: semantics on a material bound to the asset but authored outside its subtree,
  labels on other scene content, or a deprecated `SemanticsAPI` block left alongside the modern
  labels.

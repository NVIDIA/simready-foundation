# Segmentation AOV (FET011 Semantic Labels)

Two tests, run as a pair.

| Property     | Value                                                        |
|--------------|--------------------------------------------------------------|
| Test names   | `semantic_labels_seg_labelled`, `semantic_labels_seg_stripped` |
| Feature(s)   | `FET011_SemanticLabels.0-2-0`, `FET011_SemanticLabels.RTX.0-1-0`        |
| Engine metadata | Kit-tagged runtime, version `>=2024.2.0`                  |
| Effective support | Isaac Sim 6.0+ for `SemanticsLabelsAPI` segmentation   |
| Test version | `semantic_labels_seg_labelled` 1.0.1; `semantic_labels_seg_stripped` 1.0.2 |

## Summary

`semantic_labels_seg_labelled` renders the RTX semantic-segmentation AOV of the asset as authored
and measures the fraction of the frame that resolves to a semantic label.

`semantic_labels_seg_stripped` frames the same asset identically, removes
`SemanticsLabelsAPI` and deprecated `SemanticsAPI` schemas from visited label
sources, and renders again. It includes instance proxies and makes their
owning asset instances editable only in the disposable session layer. The
buffer must meet the configured near-blank threshold.

## What Pass Guarantees

Acceptance coverage fractions must be finite real numbers in `[0, 1]`;
camera padding/load timeout finite and positive, settling count nonnegative
and render-subframe count positive whole numbers. Invalid booleans, strings,
NaN/infinity or domains stop before scene mutation as configuration errors.
The AOV must contain nonempty finite nonnegative real numeric data, as a
two-dimensional label buffer or a three-dimensional color buffer with at
least three channels. Boolean, string, object, complex, empty, negative,
nonfinite or unsupported-shaped data is a required observation error. It
cannot become a black/near-blank buffer or a zero-coverage PASS. Defaults
and valid zero fractions are unchanged; native renderer qualification remains
separate from host regression coverage.

Together they show the asset's labels are honored by the RTX segmentation pipeline, and that the
segmentation comes from those labels rather than from scene setup or incidental geometry. The
stripped test is what makes the first meaningful: a populated buffer alone could be produced by
anything in frame.

Label *format* correctness is not re-checked here — the offline validator is authoritative for
that. This pair checks label-driven pixel presence/absence at the configured
thresholds; it does not compare class values, require complete masks, or prove
that every labelled component segments correctly.
A configured zero `on_coverage_min` can accept a blank labelled buffer;
that supported override is not evidence of label presence. The default
positive floor is unchanged.

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

Coverage is measured as the fraction of pixels outside the single most common
raw label ID or RGB tuple, rather than against a known background colour,
because the AOV's colour assignment is not stable between runs. Counting
preserves the validated buffer's numeric dtype and distinct identities;
two-dimensional IDs and the first three channels of colour buffers are used,
with alpha ignored. Conversion to an 8-bit RGB preview is presentation only
and cannot collapse close high-precision values into a near-blank PASS. This
still counts pixel identities, not semantic class correctness or mask quality.

For each default/render-purpose Gprim reached with `Usd.TraverseInstanceProxies()`, the
strip visits the prim, ancestors, its computed full-purpose bound material and
that material's ancestors, and its `GeomSubset` children. This can reach a
material outside the asset subtree. When a recognized label source is an
instance proxy, the owning instance must lie inside the loaded asset boundary;
it is de-instanced in the session layer and sources are recollected after
composition changes. An external instance-proxy source, rejected required edit
or still-instanced source is a setup/runtime error, not a false zero-edits skip.
Removal is applied in the session layer before the orchestrator step without
modifying source layers, instance prototypes or submitted asset files.

Positive absence proof also qualifies the authored direct/collection bindings,
collection sources, resolved materials and visited ancestors, including sources
outside the asset. Missing, masked, unloaded, undefined, abstract or unresolved
dependencies cannot prove absence merely because computed material resolution
returned nothing. The strip visits GeomSubset prims but does not follow each
subset's bound material. A subset-bound material not otherwise inspected,
including one reached through an inherited or collection binding, remains an
unqualified source: the marker is withheld, without extending stripping or
changing the render criterion. Expression-based collections and failed binding
queries likewise cannot supply positive absence proof.

## Execution Model

The registrations advertise a Kit engine version of `>=2024.2.0`; they do not
exclude earlier Isaac Sim versions solely through a `>=6.0` eligibility gate.
Modern `SemanticsLabelsAPI` segmentation requires the effective support observed
on Isaac Sim 6.0+. An older selected runtime can therefore produce a blank
labelled AOV and the existing failure guidance, even when labels are correctly
authored. Inspect the selected runtime separately from the registration metadata.

The shared executor creates a fresh stage for each test, and each procedure
steps Replicator once for its own labelled or stripped measurement. Generic
batch/per-asset session policies can reuse the engine process; these
registrations do not guarantee separate processes for the two procedures.
Host regressions qualify the data/measurement path, not native Replicator
lifecycle behavior across reused sessions. Investigate any runtime-specific
orchestrator failure as an execution issue before assigning an asset verdict.
Annotator attachment is protected by required cleanup, including a partially
failed attach. A detach failure with no earlier cause is an execution error,
not a completed presence/absence verdict. Earlier attach/read errors or
cancellation remain primary; secondary note lookup, formatting or delivery
must not replace them, including for SDK exceptions without `add_note`.
A failed required detach also records required cleanup failure with the
compatible Kit adapter and retires that worker rather than reusing an
unqualified annotator attachment. Retirement-reporting failures cannot
replace the original cleanup/read/attach cause or cancellation.

## Metrics

| Metric | Test | Meaning |
|---|---|---|
| `semantic_labels_on_coverage` | labelled | fraction of the frame that segmented, as authored |
| `semantic_labels_labelled_passed` | labelled | 1 when coverage reached `on_coverage_min` |
| `semantic_labels_off_coverage` | stripped | fraction that still segmented after the strip |
| `semantic_labels_stripped_prims` | stripped | number of prims the strip edited |
| `semantic_labels_stripped_passed` | stripped | 1 when coverage fell to `off_coverage_max` or below |

`semantic_labels_seg_stripped` retains its skip when it edits no semantics
sources. It records `no_applicable_semantics` only after positive complete
inspection proof for this stripping control and its actual dependencies. An
unqualified owned inventory, binding, collection, material or ancestry source
leaves that skip unmarked and reported as Could not assess, not evaluated asset
FAIL or PASS. Zero edits means no recognized schema was removed from the visited
sources; it does not certify absence of every possible semantic source.
Supported instanceable sources participate in the traversal. Inspect the
labelled measurement, composed sources and required-edit errors separately.

## Evidence

Each test attaches its segmentation frame: `semantic_labels_semseg_labelled` and
`semantic_labels_semseg_stripped`. The labelled test also captures an RGB frame,
`semantic_labels_rgb`.

## Common Failure Modes

- **Stripped test skipped with zero edits.** Read the applicability metric.
  A healthy marked skip identifies positively qualified Not applicable behavior;
  an unmarked skip is Could not assess because complete inspected-source proof
  is unavailable. Neither is measured segmentation PASS or asset FAIL.
- **Labelled coverage near zero.** No resolvable label on the visible meshes, a schema applied
  with no authored value, or an Isaac Sim older than 6.0, which does not resolve
  `SemanticsLabelsAPI` in the segmentation pass. Check the asset is in frame.
- **Stripped coverage still high.** Something other than the asset's own labels is driving the
  segmentation: semantics on a material bound to the asset but authored outside its subtree,
  labels on other scene content, or a deprecated `SemanticsAPI` block left alongside the modern
  labels.

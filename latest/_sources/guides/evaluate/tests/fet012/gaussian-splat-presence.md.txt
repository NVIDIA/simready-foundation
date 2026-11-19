# Gaussian Splat Presence (FET012 Gaussian Splat)

| Property     | Value                                          |
|--------------|------------------------------------------------|
| Test name    | gaussian_splat_presence                        |
| Feature(s)   | `FET012_GaussianSplat.0-1-0`                    |
| Engine       | Kit / Isaac Sim (>=6.0 in practice — see below) |
| Test version | 0.2.1                                          |

## Summary

Renders the asset in the RTX viewport and measures the screen footprint of its
`ParticleField3DGaussianSplat` visual by toggling **only** the splat prims: it captures one frame
with the splats hidden and one with them shown, and takes the fraction of pixels that change
between them.

## What Pass Guarantees

`min_splat_coverage` must be a finite real number in `[0, 1]`;
camera padding/load timeout finite and positive and settling count a
nonnegative whole number. Invalid booleans, numeric strings, NaN/infinity
or domains stop before scene mutation as configuration errors. Defaults and
valid zero fractions are preserved. Required image-analysis errors leave
execution incomplete rather than producing a fabricated zero measurement.
Host regressions do not establish native renderer support.

The asset's Gaussian-splat visual is drawn by the RTX renderer, and the pixels measured come from
the splats themselves — not from a base mesh or scene content that happens to be in frame. A
pass applies to this sampled viewport and configured footprint threshold;
it is not a guarantee for every sensor/view or of photoreal appearance.

Splat *data* correctness is not re-checked here — the offline validator (`SPL.001`–`SPL.006`) is
authoritative for that. This test checks that the splats *render*.

## What It Checks

The test loads the asset, confirms at least one `ParticleField3DGaussianSplat` prim exists (a
render test on a splat-less asset is meaningless and fails fast), adds a neutral white room,
adds a dome light as a uniform backdrop, auto-frames the camera with `camera_padding` 1.2, and
settles for `settle_frames` 5 frames.

It then captures two frames of the same framing:

- **splats hidden** — every `ParticleField3DGaussianSplat` prim's visibility is set to
  `invisible` in the session layer. Anything else in the scene (a base mesh, if the asset has
  one) is left untouched.
- **splats shown** — the same prims are set back to `inherited`.

The changed fraction between the two frames is the splats' footprint. It must reach
`min_splat_coverage`, default `0.01`. The threshold is low on purpose: a small prop framed with
padding covers only a few percent, and the question is whether the splats draw at all, not how
large they are.

Toggling only the splats is deliberate. FET_012 allows an asset to carry a base mesh alongside
the 3DGS visual; hiding the whole asset could not attribute the changed pixels to the splats.
Hiding just the splats leaves any base geometry in both frames, so the difference is the splats
alone.

3DGS is self-emissive: the dome light is only a uniform backdrop for a clean difference, not a
lighting requirement.

## Execution Model

A single engine session. Both frames use plain viewport capture (no Replicator orchestrator), so
there is no once-per-session step limit — the hidden and shown captures happen back to back in
one session.

## Metrics

| Metric | Meaning |
|---|---|
| `gs_splat_prim_count` | number of `ParticleField3DGaussianSplat` prims found on the composed stage |
| `gs_splat_coverage` | fraction of the frame that changed when the splats were toggled (their footprint) |
| `gs_present_passed` | 1 when `gs_splat_coverage` reached `min_splat_coverage` |

## Evidence

The test attaches both frames: `gs_splat_off` (splats hidden) and `gs_splat_on` (splats shown).

## Common Failure Modes

- **Coverage near zero.** The splats did not render. The most common cause is running on a Kit
  older than 110.1 / Isaac Sim older than 6.0, which does not draw
  `ParticleField3DGaussianSplat` — a valid splat then shows blank. Confirm the RTX render path is
  active (Real-Time or Path-Traced), not hdStorm or MinimalRendering; confirm the splat prims are
  not otherwise hidden and carry `positions` and radiance data; and confirm the asset is in
  frame, since a mis-framed asset also shows no splats.

## Runtime Requirement

`ParticleField3DGaussianSplat` renders only on an RTX-capable Kit (Isaac Sim 6.0 / Kit 110.1+).
The test does not pin the engine version — engine version detection is not reliable across
configurations — so on an older runtime the splats simply do not draw and the test fails with the
guidance above rather than being skipped.

# Representation Variation (FET013 Multi-Representation Visual)

| Property     | Value                                             |
|--------------|---------------------------------------------------|
| Test name    | representation_variation                          |
| Feature(s)   | `FET013_MultiRepresentationVisual.0-1-0`  |
| Engine       | Kit / Isaac Sim                                   |
| Test version | 1.0.0                                             |

## Summary

For every `Representation` option declared under
`customLayerData.SimReady_Metadata.Variants.Representation`, the test recomposes
the asset with only that option selected (on the session layer, so the source is
untouched) and measures the visual envelope. It passes when every option
composes to renderable geometry whose envelope matches the authored-default
envelope within tolerance, then renders a frame per option.

## What Pass Guarantees

The asset's representations are interchangeable: each one draws, and none of
them move or resize the object. A consumer that framed, placed, or
collision-pruned the object by its envelope can switch representation freely.

## What It Checks

Each `Representation` option must compose to renderable geometry, and every
option's visual envelope must match the authored-default envelope within
`envelope_tolerance_m`. The source layer is never mutated; selections are made
on the session layer only.

## How It Works

1. Open the source asset and read its `Representation` entries (AV.001).
2. Establish the authored-default visual envelope (default + render purposes).
3. For each option, recompose with that selection and compare its visual
   envelope with the default within `envelope_tolerance_m` (AV.005).
4. Load the asset in the viewport and capture up to `max_captures` frames, one
   per option, as rendered proof.

## Common Failure Modes

- **An option composes no visible geometry.** The payload for that option is
  missing or does not compose by default; confirm the option brings in
  renderable geometry (AV.003).
- **An option changes the envelope.** Re-author the option so the visible bounds
  match the default within tolerance (AV.005).
- **No `Representation` variation is declared.** Author a `Representation`
  variant set and record it in the discovery metadata (AV.001).

## Evidence

One rendered frame per `Representation` option, captured from the auto-framed
viewport, so each representation's draw can be compared side by side.

## Metrics

- `representation_baseline_size` - authored-default envelope size (meters, XYZ).
- `representation_option_sizes` - per-option envelope size.

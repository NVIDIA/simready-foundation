# Appearance Variation (FET016 Appearance Variant)

| Property     | Value                                    |
|--------------|------------------------------------------|
| Test name    | appearance_variation                     |
| Feature(s)   | `FET016_AppearanceVariant.0-1-0` |
| Engine       | Kit / Isaac Sim                          |
| Test version | 1.0.0                                    |

## Summary

For every `Appearance` option declared under
`customLayerData.SimReady_Metadata.Variants.Appearance`, the test recomposes the
asset with only that option selected and confirms both the visual and collision
envelopes match the authored default (a pure material re-bind leaves all
geometry in place). It then loads the asset, captures a frame per option, and
compares consecutive options so the renders are measurably different.

## What Pass Guarantees

The appearance options are interchangeable looks: each re-binds materials
without moving or resizing anything, and each actually changes what the viewer
sees. An option that produced an identical render would be a mislabelled no-op.

## What It Checks

Each `Appearance` option must leave both the visual and collision envelopes at
the authored default (AV.005, AV.006, AV.007 visual-only honesty), and
consecutive options must render differently by at least `min_appearance_delta`,
so a declared appearance change is a real one.

## How It Works

1. Open the source asset and read its `Appearance` entries (AV.001).
2. Establish the authored-default visual and collision envelopes.
3. For each option, recompose and confirm both envelopes are unchanged (AV.005
   visual, AV.006 collision; AV.007 visual-only honesty).
4. Load the asset, capture up to `max_captures` frames, and confirm consecutive
   options differ by at least `min_appearance_delta`.

## Common Failure Modes

- **An option moves geometry.** Keep geometry out of the `Appearance` set;
  author only material bindings (AV.005/AV.006).
- **Consecutive options render identically.** Confirm each option binds a
  visibly different material and the render path shows materials.
- **No `Appearance` variation is declared.** Author an `Appearance` set and
  record it in the discovery metadata (AV.001).

## Evidence

One rendered frame per `Appearance` option, captured from the auto-framed
viewport, plus the pixel-change fraction between consecutive options.

## Metrics

- `appearance_visual_baseline_size` - authored-default visual envelope size.
- `appearance_option_sizes` - per-option visual envelope size.
- `appearance_render_deltas` - pixel-change fraction between consecutive options.

# Mesh Variation (FET014 Mesh Variant)

| Property     | Value                                  |
|--------------|----------------------------------------|
| Test name    | mesh_variation                         |
| Feature(s)   | `FET014_MeshVariant.0-1-0`     |
| Engine       | Kit / Isaac Sim                        |
| Test version | 1.0.0                                  |

## Summary

For every `MeshVariant` option declared under
`customLayerData.SimReady_Metadata.Variants.MeshVariant`, the test recomposes
the asset with only that option selected and measures both the visual envelope
and the collision envelope. It passes when every option composes to renderable
geometry whose visual envelope matches the authored default AND whose collision
envelope is unchanged, confirming the swap really was visual-only, then renders
a frame per option.

## What Pass Guarantees

The mesh options are interchangeable render geometry: swapping one keeps the
object the same size and leaves collision and mass alone. A physics consumer can
trust that picking a render mesh by budget will not change simulation.

## What It Checks

Each `MeshVariant` option must compose to renderable geometry whose visual
envelope matches the authored default within `envelope_tolerance_m`, while the
collision envelope stays unchanged, proving the swap is visual-only (AV.007).

## How It Works

1. Open the source asset and read its `MeshVariant` entries (AV.001).
2. Establish the authored-default visual and collision envelopes.
3. For each option, recompose and compare both envelopes within
   `envelope_tolerance_m` (AV.005 visual, AV.006 collision; AV.007 honesty).
4. Load the asset and capture up to `max_captures` frames, one per option.

## Common Failure Modes

- **An option changes the collision envelope.** A visual-only mesh variant must
  not carry collision geometry; keep colliders out of the `MeshVariant` set
  (AV.006/AV.007).
- **An option changes the visual envelope.** Re-author the option so the visible
  bounds match the default within tolerance (AV.005).
- **No `MeshVariant` variation is declared.** Author a `MeshVariant` set and
  record it in the discovery metadata (AV.001).

## Evidence

One rendered frame per `MeshVariant` option, captured from the auto-framed
viewport, so each render mesh can be compared side by side.

## Metrics

- `mesh_visual_baseline_size` - authored-default visual envelope size.
- `mesh_option_sizes` - per-option visual envelope size.

# Collision Variation (FET015 Collision Variant)

| Property     | Value                                   |
|--------------|-----------------------------------------|
| Test name    | collision_variation                     |
| Feature(s)   | `FET015_CollisionVariant.0-1-0` |
| Engine       | Kit / Isaac Sim                         |
| Test version | 1.0.0                                   |

## Summary

For every `Collision` option declared under
`customLayerData.SimReady_Metadata.Variants.Collision`, the test recomposes the
asset with only that option selected and measures the collision envelope (proxy
/ guide purposes) and the visual envelope. It passes when every option composes
with a collision envelope matching the authored default AND an unchanged visual
envelope, then loads the asset with physics, settles it, and renders a frame per
option.

## What Pass Guarantees

The collider options are interchangeable: each simulates, occupies the same
simulated footprint, and leaves the render mesh in place. A pipeline can pick a
collider by cost without changing contacts or placement.

## What It Checks

Each `Collision` option must compose with a collision envelope matching the
authored default within `envelope_tolerance_m` (AV.006) while the visual
envelope stays unchanged (AV.005), confirming the swap touches only colliders.

## How It Works

1. Open the source asset and read its `Collision` entries (AV.001).
2. Establish the authored-default collision and visual envelopes.
3. For each option, recompose and compare the collision envelope (AV.006) and
   confirm the visual envelope is unchanged (AV.005).
4. Load the asset with physics, advance the simulation, and capture up to
   `max_captures` frames, one per option.

## Common Failure Modes

- **An option resizes the collider.** Re-author colliders so the collision
  bounds match the default within tolerance (AV.006).
- **An option moves the render mesh.** Keep render geometry out of the
  `Collision` set so the visible mesh stays put (AV.005).
- **No `Collision` variation is declared.** Author a `Collision` set and record
  it in the discovery metadata (AV.001).

## Evidence

One still per `Collision` option captured after a brief physics settle, so each
collider's simulated footprint can be compared.

## Metrics

- `collision_baseline_size` - authored-default collision envelope size.
- `collision_option_sizes` - per-option collision envelope size.

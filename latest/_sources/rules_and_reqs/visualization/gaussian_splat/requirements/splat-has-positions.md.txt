# splat-has-positions

| Code     | SPL.002 |
|----------|---------|
| Validator| `GaussianSplatCapabilityChecker` (validation.py) |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Each `ParticleField3DGaussianSplat` prim must author `positions`.

## Description

`positions` gives the center of each Gaussian in the prim's local space, one
entry per Gaussian. It is the anchor array that every other per-Gaussian array
(`scales`, `orientations`, `opacities`, radiance coefficients) is indexed
against, so it must be authored and non-empty.

## Why is it required?

- Without positions there is no geometry to place or render.
- `positions` defines the Gaussian count that `SPL.003`–`SPL.006` are validated
  against.

## Examples

```usd
# Invalid: no positions authored
def ParticleField3DGaussianSplat "capture"
{
    float[] opacities = [...]
}

# Valid
def ParticleField3DGaussianSplat "capture"
{
    point3f[] positions = [(0, 0, 0), (0.01, 0, 0), ...]
}
```

## How to comply

Author the `positions` attribute with one `point3f` per Gaussian. The reference
converter `py3dgsPlyToUsd.py` populates this from the PLY `x`/`y`/`z` columns.

## For More Information

- [3D Gaussian Splat Capability](../capability-gaussian_splat.md)
- [splat-prim-type](splat-prim-type.md)

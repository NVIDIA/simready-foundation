# splat-has-scales

| Code     | SPL.003 |
|----------|---------|
| Validator| `GaussianSplatCapabilityChecker` (validation.py) |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Each `ParticleField3DGaussianSplat` prim must author `scales`, one per Gaussian.

## Description

`scales` gives the per-axis extent of each Gaussian (its ellipsoid radii) in
local space, one `float3` per Gaussian. Scales must be authored with the same
length as `positions`. The OpenUSD schema stores linear scales; the Inria PLY
format stores log-space scales, so a converter must apply `exp()` before
authoring.

## Why is it required?

- Scales determine the size and anisotropy of each Gaussian and are required to
  render the splat correctly.
- A missing or mismatched-length `scales` array produces incorrect or
  undefined rendering.

## Examples

```usd
# Valid
def ParticleField3DGaussianSplat "capture"
{
    point3f[] positions = [...]        # N entries
    float3[] scales = [...]            # N entries, linear space
}
```

## How to comply

Author `scales` with one `float3` per Gaussian, in linear space and matching
the length of `positions`. The reference converter `py3dgsPlyToUsd.py` applies
`exp()` to the PLY `scale_*` columns automatically.

## For More Information

- [3D Gaussian Splat Capability](../capability-gaussian_splat.md)
- [splat-has-positions](splat-has-positions.md)

# splat-has-opacities

| Code     | SPL.005 |
|----------|---------|
| Validator| `GaussianSplatCapabilityChecker` (validation.py) |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Each `ParticleField3DGaussianSplat` prim must author `opacities`, one per
Gaussian.

## Description

`opacities` gives the alpha of each Gaussian, one `float` per Gaussian, matching
the length of `positions`. Values are in linear `[0, 1]` space. The Inria PLY
format stores opacity as a logit, so a converter must apply the `sigmoid()`
function before authoring.

## Why is it required?

- Opacity controls each Gaussian's contribution during alpha compositing;
  without it the splat cannot be blended correctly.
- A mismatched-length `opacities` array breaks per-Gaussian indexing.

## Examples

```usd
# Valid
def ParticleField3DGaussianSplat "capture"
{
    point3f[] positions = [...]        # N entries
    float[] opacities = [...]          # N entries, linear [0, 1]
}
```

## How to comply

Author `opacities` with one `float` per Gaussian in linear `[0, 1]` space,
matching the length of `positions`. The reference converter `py3dgsPlyToUsd.py`
applies `sigmoid()` to the PLY `opacity` column automatically.

## For More Information

- [3D Gaussian Splat Capability](../capability-gaussian_splat.md)
- [splat-has-orientations](splat-has-orientations.md)

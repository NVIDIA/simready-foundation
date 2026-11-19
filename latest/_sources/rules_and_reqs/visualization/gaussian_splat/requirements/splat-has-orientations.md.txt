# splat-has-orientations

| Code     | SPL.004 |
|----------|---------|
| Validator| `GaussianSplatCapabilityChecker` (validation.py) |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Each `ParticleField3DGaussianSplat` prim must author `orientations`, one per
Gaussian.

## Description

`orientations` gives the rotation of each Gaussian's ellipsoid as a quaternion,
one `quatf` per Gaussian, matching the length of `positions`. Together with
`scales` it defines each Gaussian's oriented covariance. Quaternions should be
normalized.

## Why is it required?

- Orientation defines the direction of each Gaussian's anisotropy; without it
  the covariance is undefined and the splat renders incorrectly.
- A mismatched-length `orientations` array breaks per-Gaussian indexing.

## Examples

```usd
# Valid
def ParticleField3DGaussianSplat "capture"
{
    point3f[] positions = [...]        # N entries
    quatf[] orientations = [...]       # N normalized quaternions
}
```

## How to comply

Author `orientations` with one normalized `quatf` per Gaussian, matching the
length of `positions`. The reference converter `py3dgsPlyToUsd.py` normalizes
the PLY `rot_*` columns and authors them in the schema's quaternion layout.

## For More Information

- [3D Gaussian Splat Capability](../capability-gaussian_splat.md)
- [splat-has-scales](splat-has-scales.md)

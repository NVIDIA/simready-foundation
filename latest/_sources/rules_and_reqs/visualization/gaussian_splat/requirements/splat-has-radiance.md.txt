# splat-has-radiance

| Code     | SPL.006 |
|----------|---------|
| Validator| `GaussianSplatCapabilityChecker` (validation.py) |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Each `ParticleField3DGaussianSplat` prim must author view-dependent radiance:
`radiance:sphericalHarmonicsDegree` and
`radiance:sphericalHarmonicsCoefficients`, with a coefficient count consistent
with the degree and Gaussian count.

## Description

3DGS stores each Gaussian's view-dependent color as spherical-harmonic (SH)
coefficients. A compliant prim authors both:

- `radiance:sphericalHarmonicsDegree` — the SH degree `d` (0–3).
- `radiance:sphericalHarmonicsCoefficients` — the interleaved SH coefficients.

The coefficient array length must equal `len(positions) * (d + 1)^2`
(one `float3` block of `(d + 1)^2` coefficients per Gaussian). A mismatch means
the radiance data is inconsistent with the declared degree or Gaussian count.

## Why is it required?

- Radiance is what gives each Gaussian its color; without it the splat has no
  appearance.
- Enforcing the `(d + 1)^2` relationship catches truncated, mis-interleaved, or
  degree-mismatched coefficient arrays that render incorrectly.

## Examples

```usd
# Valid, degree 3 -> 16 coefficient vec3 blocks per Gaussian
def ParticleField3DGaussianSplat "capture"
{
    point3f[] positions = [...]                                  # N entries
    int radiance:sphericalHarmonicsDegree = 3
    float3[] radiance:sphericalHarmonicsCoefficients = [...]     # N * 16 entries
}
```

## How to comply

1. Author `radiance:sphericalHarmonicsDegree` with the SH degree used (0–3).
2. Author `radiance:sphericalHarmonicsCoefficients` with
   `len(positions) * (degree + 1)^2` entries in the schema's interleaved layout.
3. The reference converter `py3dgsPlyToUsd.py` handles the DC (`f_dc_*`) and
   higher-order (`f_rest_*`) coefficient interleaving and degree derivation
   automatically; pass `--generateSh` when only `red`/`green`/`blue` columns
   are present.

## For More Information

- [3D Gaussian Splat Capability](../capability-gaussian_splat.md)
- [splat-has-opacities](splat-has-opacities.md)

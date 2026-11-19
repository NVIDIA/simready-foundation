# splat-prim-type

| Code     | SPL.001 |
|----------|---------|
| Validator| `GaussianSplatCapabilityChecker` (validation.py) |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

The asset's visual representation must be a `ParticleField3DGaussianSplat` prim.

## Description

A 3D Gaussian Splat visual representation is authored with the OpenUSD
`ParticleField3DGaussianSplat` schema (`UsdVol`, OpenUSD `26.03`+). The asset
must contain at least one prim whose type is `ParticleField3DGaussianSplat`
carrying the per-Gaussian splat data. Legacy encodings that store splat data on
a `UsdGeomPoints` prim with PLY-named primvars (`primvars:f_dc_*`,
`primvars:f_rest_*`, `primvars:opacity`, `primvars:scale_*`, `primvars:rot_*`)
do not satisfy this requirement and must be converted.

## Why is it required?

- Establishes a single, schema-typed representation that vision-sensor
  renderers can discover and render without heuristics.
- Enables the per-Gaussian data requirements (`SPL.002`–`SPL.006`) to be
  validated against a known schema.
- Avoids ambiguous legacy point-cloud encodings that tools cannot reliably
  interpret as splats.

## Examples

```usd
# Invalid: legacy 3DGS stored as UsdGeomPoints with PLY-named primvars
def Points "capture"
{
    float[] primvars:f_dc_0 = [...]
    float[] primvars:opacity = [...]
}

# Valid: ParticleField3DGaussianSplat prim
def ParticleField3DGaussianSplat "capture"
{
    point3f[] positions = [...]
}
```

## How to comply

1. Author the visual representation as a `ParticleField3DGaussianSplat` prim.
2. If starting from an Inria-format `.ply`, use the OpenUSD reference converter
   `extras/imaging/examples/hdParticleField/py3dgsPlyToUsd.py`.
3. If starting from a legacy 3DGS USD, export it back to an Inria-format `.ply`
   and re-run the reference converter.

## For More Information

- [3D Gaussian Splat Capability](../capability-gaussian_splat.md)
- [splat-has-positions](splat-has-positions.md)
- [splat-has-radiance](splat-has-radiance.md)

# Gaussian Splat

## Overview

This capability provides requirements for authoring an asset's visual
representation as a **3D Gaussian Splat (3DGS)** using the OpenUSD
`ParticleField3DGaussianSplat` schema (`UsdVol`). A 3DGS asset stores its
appearance as a field of oriented, scaled, semi-transparent Gaussians with
view-dependent radiance, rather than as surface meshes and materials.

3DGS is intended for consumption by RGB cameras and other vision sensors that
produce photorealistic output. It provides high visual fidelity for outdoor,
organic, or otherwise hard-to-model captured environments where conventional
surface meshes and materials are impractical.

## Summary

- **The asset's visual representation is a `ParticleField3DGaussianSplat` prim.**
- **Each splat prim authors the per-Gaussian data required to render it:
  positions, scales, orientations, opacities, and view-dependent radiance.**
- **The radiance spherical-harmonic coefficients are consistent with the
  authored degree and Gaussian count.**

## Schema / OpenUSD Specification

3D Gaussian Splats are defined with the
[`ParticleField3DGaussianSplat` schema](https://openusd.org/dev/user_guides/schemas/usdVol/ParticleField3DGaussianSplat.html),
available in OpenUSD `26.03` and later. The schema carries built-in applied API
schemas for the per-Gaussian data, so a compliant prim requires no additional
custom attributes.

## USDA Sample

```usd
def ParticleField3DGaussianSplat "asset_capture"
{
    point3f[] positions = [...]
    float3[] scales = [...]
    quatf[] orientations = [...]
    float[] opacities = [...]
    int radiance:sphericalHarmonicsDegree = 3
    float3[] radiance:sphericalHarmonicsCoefficients = [...]
}
```

## Authoring / Conversion

OpenUSD ships a reference converter that produces a compliant prim from an
Inria-format 3DGS `.ply`:

```
<OpenUSD>/extras/imaging/examples/hdParticleField/py3dgsPlyToUsd.py
```

The converter applies the standard 3DGS data transformations (`exp()` on
scales, `sigmoid()` on opacities, quaternion normalization, and spherical-
harmonic interleaving) and applies the schema's built-in API schemas, so its
output satisfies this capability's requirements without further authoring.

## Related Capabilities

- [Geometry](../geometry/capability-geometry.md) — surface-mesh visual
  representation (the conventional alternative to 3DGS).
- [Materials](../materials/capability-materials.md) — surface material binding,
  not used by a 3DGS visual representation.

### Requirements

```{requirements-table}
```

```{toctree}
:maxdepth: 1
:hidden:

Requirements <requirements>
```

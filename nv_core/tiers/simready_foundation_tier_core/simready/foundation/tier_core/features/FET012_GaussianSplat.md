# Feature: `FET012_GaussianSplat`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET012_GaussianSplat` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

This feature defines the Standard OpenUSD contract for an asset whose visual
representation is a **3D Gaussian Splat (3DGS)**, authored with the
`ParticleField3DGaussianSplat` schema (`UsdVol`, OpenUSD `26.03`+). An asset
that satisfies this feature can be rendered by RGB cameras and other vision
sensors as a photorealistic Gaussian-splat field instead of surface meshes and
materials.

The feature applies to captured or reconstructed content — outdoor, organic, or
otherwise hard-to-model environments and objects — where a conventional mesh and
material representation is impractical. Static validation verifies that the
asset contains a `ParticleField3DGaussianSplat` prim and that each splat prim
authors the per-Gaussian data required to render it: positions, scales,
orientations, opacities, and view-dependent spherical-harmonic radiance whose
coefficient count is consistent with the declared degree and Gaussian count.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly. It
is self-contained: it carries the non-mesh half of the minimal placeable
contract (anchored paths, up-axis/units, hierarchy) alongside the Gaussian-splat
data contract, so a pure 3DGS asset with no mesh can conform without depending on
`FET001_MinimalPlaceableVisual` (whose mesh requirement a splat-only asset cannot satisfy).

## Use Cases

Products or workflows that consume this feature:

- NuRec / neural-reconstruction 3DGS asset delivery
- RGB camera and vision-sensor simulation
- Synthetic data generation over captured environments

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [NuRec](../profiles/nurec.md): required in `1.0.0`

#### Feature Dependencies

None. This feature is self-contained (see [Dependency Graph](#dependency-graph)).

#### Requirement List

Minimal placeable contract (non-mesh half), inlined so a splat-only asset is a
valid placeable asset without the `FET001_MinimalPlaceableVisual` mesh requirement:

* Capability: [Atomic Asset](../rules_and_reqs/core/atomic_asset/capability-atomic_asset.md)
    * Requirements: `AA.001` (anchored reference/payload paths), `AA.002` (supported reference file types)
* Capability: [Units](../rules_and_reqs/core/units/capability-units.md)
    * Requirements: `UN.006` (`upAxis = "Z"`), `UN.007` (`metersPerUnit = 1.0`)
* Capability: [Hierarchy](../rules_and_reqs/hierarchy/capability-hierarchy.md)
    * Requirements: `HI.001` (single stage root), `HI.003` (root is `UsdGeomXformable`), `HI.004` (valid `defaultPrim`)

Gaussian Splat data contract:

* Capability: [3D Gaussian Splat](../rules_and_reqs/visualization/gaussian_splat/capability-gaussian_splat.md)
    * Requirements:
        * [splat-prim-type](../rules_and_reqs/visualization/gaussian_splat/requirements/splat-prim-type.md)
            * `SPL.001` | Version `0.1.0`
        * [splat-has-positions](../rules_and_reqs/visualization/gaussian_splat/requirements/splat-has-positions.md)
            * `SPL.002` | Version `0.1.0`
        * [splat-has-scales](../rules_and_reqs/visualization/gaussian_splat/requirements/splat-has-scales.md)
            * `SPL.003` | Version `0.1.0`
        * [splat-has-orientations](../rules_and_reqs/visualization/gaussian_splat/requirements/splat-has-orientations.md)
            * `SPL.004` | Version `0.1.0`
        * [splat-has-opacities](../rules_and_reqs/visualization/gaussian_splat/requirements/splat-has-opacities.md)
            * `SPL.005` | Version `0.1.0`
        * [splat-has-radiance](../rules_and_reqs/visualization/gaussian_splat/requirements/splat-has-radiance.md)
            * `SPL.006` | Version `0.1.0`

</details>

## Pipelines

Source file type:

- `.ply` (Inria 3DGS format)
  - Via the OpenUSD reference converter
    `extras/imaging/examples/hdParticleField/py3dgsPlyToUsd.py`.
- `.spz`
  - Via the OpenUSD reference converter
    `extras/imaging/examples/hdParticleField/py3dgsSpzToUsd.py`.
- Legacy 3DGS `.usd` (`UsdGeomPoints` with PLY-named primvars)
  - Export back to an Inria-format `.ply`, then run `py3dgsPlyToUsd.py`.

Validation or runtime pipeline:

- SimReady validation - verifies the static `SPL.001`-`SPL.006` 3D Gaussian
  Splat contract.

## Samples

- [`traffic_cone_chn_red`](../../../../../../../sample_content/common_assets/props_general/traffic_cone_chn_red/simready_usd/sm_traffic_cone_chn_red_01.usd) — the **NuRec** sample: a pure Gaussian-splat prop (a single `ParticleField3DGaussianSplat`, no mesh). This is what FET_012 and the NuRec profile validate.

The pure-splat (NuRec) case is the validated consumer of FET_012. An asset that
also carries a base mesh may compose its splats however it likes — gated behind a
`Visual_3DGS` variant or composed unconditionally — which is an authoring choice
and is **not** prescribed by the spec. That mesh + variant composition is shown
below as an illustration.

### USD Composition

For an asset that also carries a base mesh (the illustrative case; the NuRec
sample is pure splat with no mesh), the 3DGS visual may be composed as an
optional `Visual_3DGS` variant that, when enabled, provides
`ParticleField3DGaussianSplat` prims (one per geometry piece) satisfying the
[3D Gaussian Splat](../rules_and_reqs/visualization/gaussian_splat/capability-gaussian_splat.md)
capability. Only the USD composition below is part of this feature — the
on-disk file and payload layout is an authoring choice and is **not** prescribed
by the spec.

```usd
def Xform "RootNode" (
    variants = {
        string Visual_3DGS = "Disabled"
    }
    prepend variantSets = ["Visual_3DGS"]
)
{
    # ... base mesh geometry under Geometry/ ...

    variantSet "Visual_3DGS" = {
        "Disabled" {
        }
        "Enabled" {
            over "Geometry"
            {
                over "box_obj_01"
                {
                    # 3DGS visual representation for this geometry piece,
                    # satisfying the 3D Gaussian Splat capability (SPL.001-006).
                    # Brought in via a payload or reference to a compliant
                    # ParticleField3DGaussianSplat source (layout not prescribed).
                    def ParticleField3DGaussianSplat "box_mesh_01_3dgs" (
                        prepend payload = @<compliant-3dgs-source>@</box_mesh_01>
                    )
                    {
                    }
                }
                # ... one ParticleField3DGaussianSplat prim per geometry piece ...
            }
        }
    }
}
```

## Evaluates

- Suite: [FET012 Gaussian Splat](../runtime_tests/docs/fet012-gaussian-splat.md)
  - Tests:
    - [gaussian_splat_presence](../runtime_tests/docs/fet012/gaussian-splat-presence.md)

## Adapters

None.

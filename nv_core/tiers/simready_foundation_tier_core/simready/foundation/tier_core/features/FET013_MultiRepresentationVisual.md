# Feature: `FET013_MultiRepresentationVisual`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET013_MultiRepresentationVisual` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

The Multi-Representation Visual feature defines the OpenUSD contract for an asset
that offers two or more interchangeable visual representations of the same
geometry, selectable without changing how the asset places or simulates. Its
variation category is `Representation` and its impact class is `visual-only`.

`Representation` switches the encoding of a scope between a `UsdGeomMesh` and a
`ParticleField3DGaussianSplat`, with an open-ended option vocabulary: NeRF, voxel,
point cloud, and imposter encodings can be added as options in a later version
without a new feature, each bringing its own content requirements. The feature
itself mandates no representation technology -- it carries only the variation
contract (`AV.001`-`AV.010`). Each representation is validated by the feature it
claims: a `Mesh` option satisfies the mesh geometry requirements carried by the
`FET001_MinimalPlaceableVisual` dependency, and a `GaussianSplat` option is
expected to additionally satisfy `FET012_GaussianSplat` (`SPL.001`-`SPL.006`).
This keeps a mesh-only multi-representation asset from being forced to carry splat
data.

Variant sets live on the default prim: a master `Representation` set plus a
per-part `Representation_<part>` set for each multi-representation scope, with each
option composed from an isolated payload (`AV.004`). Every option holds the visual
envelope invariant (`AV.005`), and physics, collision, semantics, grasp, and
provenance are authored on the neutral prim outside every variant so the
`visual-only` impact class is honest (`AV.007`). A scope with a single
representation carries no set (`AV.008`).

## Dependency Graph

```{mermaid}
flowchart LR
    FET013S1["FET013_MultiRepresentationVisual\n0-1-0"]
    FET001S1["FET001_MinimalPlaceableVisual\n1-0-1"]

    FET013S1 --> FET001S1

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET013S1 current
    class FET001S1 other
```

## Use Cases

- Assets delivered with both a mesh and a Gaussian-splat visual of the same object.
- Swapping a high-cost encoding for a cheaper one without re-authoring placement or physics.
- Adding new representation encodings (NeRF, point cloud, imposter) as options under a stable contract.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Minimal Placeable Visual](FET001_MinimalPlaceableVisual.md#version-1-0-1) (`FET001_MinimalPlaceableVisual.1-0-1`) |

#### Requirement List

* Capability: [Core/Asset Variants](../rules_and_reqs/core/asset_variants/capability-asset_variants.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `AV.001` | [AV.001](../rules_and_reqs/core/asset_variants/requirements/variation-discovery-metadata.md) |
| `AV.002` | [AV.002](../rules_and_reqs/core/asset_variants/requirements/variant-set-location.md) |
| `AV.003` | [AV.003](../rules_and_reqs/core/asset_variants/requirements/option-composability.md) |
| `AV.004` | [AV.004](../rules_and_reqs/core/asset_variants/requirements/section-purity-isolation.md) |
| `AV.005` | [AV.005](../rules_and_reqs/core/asset_variants/requirements/visual-envelope-invariant.md) |
| `AV.006` | [AV.006](../rules_and_reqs/core/asset_variants/requirements/collision-envelope-invariant.md) |
| `AV.007` | [AV.007](../rules_and_reqs/core/asset_variants/requirements/impact-class-honesty.md) |
| `AV.008` | [AV.008](../rules_and_reqs/core/asset_variants/requirements/conditional-presence.md) |
| `AV.009` | [AV.009](../rules_and_reqs/core/asset_variants/requirements/authored-physical-properties.md) |
| `AV.010` | [AV.010](../rules_and_reqs/core/asset_variants/requirements/variation-stability.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc` carrying authored representation variant sets.

Validation or runtime pipeline:

- SimReady validation verifies the selected `FET013_MultiRepresentationVisual.0-1-0` manifest.

## Samples

- [sample_content/common_assets/props_general/obs_electricians_large_tool_box_a02/simready_usd/sm_obs_electricians_large_tool_box_a02.usda](../../../../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a02/simready_usd/sm_obs_electricians_large_tool_box_a02.usda) - toolbox with a master `Representation` set (all-mesh `Original` / all-splat `Splat`) driving per-part `Representation_base` and `Representation_lid` sets: the master switches both parts at once, and a per-part selection overrides a single part (e.g. splat base with mesh lid), while the collider and mass stay invariant.

## Runtime Tests

- [FET013 Multi-Representation Visual](../runtime_tests/docs/fet013-representation.md)
  - [representation_variation](../runtime_tests/docs/fet013/representation-variation.md) - selects each master and per-part option, confirms the active representation is valid and the inactive one is not leaked, and checks that the visual envelope and simulation data are unchanged.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| Non-conformant asset | `FET013_MultiRepresentationVisual.0-1-0` | `simready-foundation-conform-fet-013-standard` | Available | Authors the discovery metadata, master/per-part variant sets, and isolated payload options on a staged copy. It never fabricates geometry; a representation option that needs content the asset lacks is reported as a blocker. |

# Feature: `FET016_AppearanceVariant`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET016_AppearanceVariant` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

The Appearance Variant feature defines the OpenUSD contract for an asset that
offers two or more surface appearances with identical geometry, physical material,
and mass. Its variation category is `Appearance` and its impact class is
`visual-only`.

`Appearance` switches surface look -- color, finish, weathering, or texture -- with
a documented sub-vocabulary of `Colorway`, `Finish`, `Condition`, and `Texture`.
Each option binds a valid visual material satisfying the UsdPreviewSurface
requirements carried by the `FET006_Materials` dependency. It is one feature
with a sub-vocabulary rather than four, because all appearance kinds share the same
mechanism (a material-binding variant) and the same invariants.

Only the visual material binding changes. The bound UsdPhysics physical material
and the authored mass are invariant -- no change of physical material type (no wood,
metal, or plastic swap) -- and geometry and both envelopes are unchanged, keeping
the `visual-only` impact class honest (`AV.007`).

## Dependency Graph

```{mermaid}
flowchart LR
    FET016S1["FET016_AppearanceVariant\n0-1-0"]
    FET001S1["FET001_MinimalPlaceableVisual\n1-0-1"]
    FET006S1["FET006_Materials\n0-2-0"]

    FET016S1 --> FET001S1
    FET016S1 --> FET006S1

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET016S1 current
    class FET001S1,FET006S1 other
```

## Use Cases

- A product shipped in several colorways or finishes from one asset.
- Clean, worn, and damaged condition variants of the same object.
- Swapping texture sets without changing geometry, physical material, or mass.

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
| Dependency | [Materials](FET006_Materials.md#version-0-2-0) (`FET006_Materials.0-2-0`) |

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

- `.usd`, `.usda`, `.usdc` carrying authored appearance variant sets with bound visual materials.

Validation or runtime pipeline:

- SimReady validation verifies the selected `FET016_AppearanceVariant.0-1-0` manifest.

## Samples

- None.

## Runtime Tests

- [FET016 Appearance Variant](../runtime_tests/docs/fet016-appearance-variant.md)
  - [appearance_variation](../runtime_tests/docs/fet016/appearance-variation.md) - selects each appearance option, confirms each binds a valid visual material, and checks that the bound physical material, mass, geometry, and both envelopes are unchanged across options.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| Non-conformant asset | `FET016_AppearanceVariant.0-1-0` | `simready-foundation-conform-fet-016-standard` | Available | Authors the discovery metadata and material-binding variant sets on a staged copy, keeping geometry, the physical material, and the authored mass outside the variant sections. It never changes the physical material type or fabricates a material; a missing visual material is reported as a blocker. |

# Feature: `FET015_CollisionVariant`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET015_CollisionVariant` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

The Collision Variant feature defines the OpenUSD contract for an asset that offers
two or more collider fidelities at the same footprint, with bulk dynamics
unchanged. Its variation category is `Collision` and its impact class is
`simulation-affecting`.

`Collision` switches collider fidelity (for example convex hull, triangle mesh, or
primitive decomposition) at the same footprint. Each option is a valid collider
satisfying the collider presence/approximation requirements carried by the
`FET003_RigidBody` rigid-body dependency. The visual representation is
unchanged across options.

`FET015_CollisionVariant` is the only `simulation-affecting` member of the
variation family. Its declared domain is collision-contact behavior only: the
collision envelope size is invariant (`AV.006`). Mass, center of mass, and inertia
MUST be explicitly authored on the rigid body via `UsdPhysics.MassAPI` and are
validated (`AV.009`) -- never derived from the collider. Because they are authored
on the invariant body outside the variant sections, they stay identical across all
collider options, so a fidelity swap never changes bulk dynamics.

## Dependency Graph

```{mermaid}
flowchart LR
    FET015S1["FET015_CollisionVariant\n0-1-0"]
    FET001S1["FET001_MinimalPlaceableVisual\n1-0-1"]
    FET003S1["FET003_RigidBody\n0-2-0"]

    FET015S1 --> FET001S1
    FET015S1 --> FET003S1

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET015S1 current
    class FET001S1,FET003S1 other
```

## Use Cases

- A rigid body shipped with both a cheap convex collider and a high-fidelity mesh collider.
- Trading collision accuracy for solver cost without changing resting pose or bulk dynamics.
- Supplying a primitive-decomposition collider for fast contact alongside a detailed one.

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
| Dependency | [Rigid Body Physics](FET003_RigidBody.md#version-0-2-0) (`FET003_RigidBody.0-2-0`) |

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

- `.usd`, `.usda`, `.usdc` carrying authored collision variant sets with an authored rigid body.

Validation or runtime pipeline:

- SimReady validation verifies the selected `FET015_CollisionVariant.0-1-0` manifest.

## Samples

- None.

## Runtime Tests

- [FET015 Collision Variant](../runtime_tests/docs/fet015-collision-variant.md)
  - [collision_variation](../runtime_tests/docs/fet015/collision-variation.md) - selects each collider option, confirms each composes a valid collider, checks the collision envelope and authored mass/center-of-mass/inertia are identical across options, and optionally drops the asset onto a plane to confirm the resting pose agrees.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| Non-conformant asset | `FET015_CollisionVariant.0-1-0` | `simready-foundation-conform-fet-015-standard` | Available | Authors the discovery metadata and collider variant sets on a staged copy, keeping the authored mass/center-of-mass/inertia on the invariant rigid body. It never derives mass from the collider or fabricates a collider; a missing authored value is reported as a blocker. |

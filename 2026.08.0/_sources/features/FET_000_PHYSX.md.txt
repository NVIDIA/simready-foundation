# Feature: `FET_000_PHYSX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_000_PHYSX` |
| Runtime                 | `PHYSX` |
| Proprietary Techs       | `PhysX` |
| Latest Version          | `0.1.0` |

## Description

The Core (PhysX) feature adds the PhysX physics runtime variant to a SimReady
asset on top of the neutral Core contract. A satisfying asset exposes a `PhysX`
variant set on its root that, when enabled, composes a PhysX runtime payload from
`runnables/physics/physx.usd`, while the neutral asset stays unchanged when the
variant is disabled.

This feature only deals with the PhysX runtime variant. Newton and MuJoCo
variants are provided by `FET_000_NEWTON` and `FET_000_MUJOCO`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000PHYSX["FET_000_PHYSX\n0.1.0"]
    FET000STD["FET_000_STANDARD\n0.1.0"]

    FET000PHYSX --> FET000STD

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000PHYSX current
    class FET000STD other
```

## Use Cases

- Assets that must run under the PhysX solver while remaining valid as a neutral
  SimReady asset.
- Pipelines that switch an asset into PhysX by selecting a single variant.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](FET_000_STANDARD.md) (`FET_000_STANDARD@0.1.0`) |

#### Requirement List

* Capability: [Core/Runtime Variants](../capabilities/core/runtime_variants/capability-runtime_variants.md)
    * Requirements:
        * [PhysX-Variant-Set](../capabilities/core/runtime_variants/requirements/physx-variant-set.md)
            * RV.001 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [PhysX-Runtime-Payload](../capabilities/core/runtime_variants/requirements/physx-runtime-payload.md)
            * RV.002 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [PhysX-Variant-Metadata](../capabilities/core/runtime_variants/requirements/physx-variant-metadata.md)
            * RV.003 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [Runtime-Variant-Section-Purity](../capabilities/core/runtime_variants/requirements/runtime-variant-section-purity.md)
            * RV.010 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [Runtime-Physics-Isolation](../capabilities/core/runtime_variants/requirements/runtime-physics-isolation.md)
            * RV.011 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)

Inherited from `FET_000_STANDARD@0.1.0`: NP.002, NP.003, NP.004, NP.005, NP.006,
NP.007, NP.008, SR.001, HI.010.

</details>

## Pipelines

Validation or runtime pipeline:

- SimReady validation - verifies the PhysX runtime variant requirement IDs listed
  in the feature manifest.

## Samples

- `sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd` - `PhysX` variant set with a `runnables/physics/physx.usd` payload.

## Benchmarks

- None.

## Adapters

None.

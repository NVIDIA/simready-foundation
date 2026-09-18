# Feature: `FET_000_MUJOCO`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_000_MUJOCO` |
| Runtime                 | `MUJOCO` |
| Proprietary Techs       | `MuJoCo` |
| Latest Version          | `0.1.0` |

## Description

The Core (MuJoCo) feature adds the MuJoCo physics runtime variant to a SimReady
asset on top of the neutral Core contract. A satisfying asset exposes a `MuJoCo`
variant set on its root that, when enabled, composes a MuJoCo runtime payload
from `runnables/physics/mujoco.usd`, while the neutral asset stays unchanged when
the variant is disabled.

This feature only deals with the MuJoCo runtime variant. PhysX and Newton
variants are provided by `FET_000_PHYSX` and `FET_000_NEWTON`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000MUJOCO["FET_000_MUJOCO\n0.1.0"]
    FET000STD["FET_000_STANDARD\n0.1.0"]

    FET000MUJOCO --> FET000STD

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000MUJOCO current
    class FET000STD other
```

## Use Cases

- Assets that must run under the MuJoCo solver while remaining valid as a neutral
  SimReady asset.
- Pipelines that switch an asset into MuJoCo by selecting a single variant.

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
        * [MuJoCo-Variant-Set](../capabilities/core/runtime_variants/requirements/mujoco-variant-set.md)
            * RV.007 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [MuJoCo-Runtime-Payload](../capabilities/core/runtime_variants/requirements/mujoco-runtime-payload.md)
            * RV.008 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [MuJoCo-Variant-Metadata](../capabilities/core/runtime_variants/requirements/mujoco-variant-metadata.md)
            * RV.009 | Version 0.1.0
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

- SimReady validation - verifies the MuJoCo runtime variant requirement IDs listed
  in the feature manifest.

## Samples

- None. (The `obs_orange_a02` prop demonstrates `PhysX` and `Newton`; a `MuJoCo`
  variant would add `runnables/physics/mujoco.usd`.)

## Benchmarks

- None.

## Adapters

None.

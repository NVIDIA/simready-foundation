# Feature: `FET_000_NEWTON`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_000_NEWTON` |
| Runtime                 | `NEWTON` |
| Proprietary Techs       | `Newton` |
| Latest Version          | `0.1.0` |

## Description

The Core (Newton) feature adds the Newton physics runtime variant to a SimReady
asset on top of the neutral Core contract. A satisfying asset exposes a `Newton`
variant set on its root that, when enabled, composes a Newton runtime payload
from `runnables/physics/newton.usd`, while the neutral asset stays unchanged when
the variant is disabled.

This feature only deals with the Newton runtime variant. PhysX and MuJoCo
variants are provided by `FET_000_PHYSX` and `FET_000_MUJOCO`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000NEWTON["FET_000_NEWTON\n0.1.0"]
    FET000STD["FET_000_STANDARD\n0.1.0"]

    FET000NEWTON --> FET000STD

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000NEWTON current
    class FET000STD other
```

## Use Cases

- Assets that must run under the Newton solver while remaining valid as a neutral
  SimReady asset.
- Pipelines that switch an asset into Newton by selecting a single variant.

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
        * [Newton-Variant-Set](../capabilities/core/runtime_variants/requirements/newton-variant-set.md)
            * RV.004 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [Newton-Runtime-Payload](../capabilities/core/runtime_variants/requirements/newton-runtime-payload.md)
            * RV.005 | Version 0.1.0
            * [Rule | Implementation](../capabilities/core/runtime_variants/validation.py)
        * [Newton-Variant-Metadata](../capabilities/core/runtime_variants/requirements/newton-variant-metadata.md)
            * RV.006 | Version 0.1.0
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

- SimReady validation - verifies the Newton runtime variant requirement IDs listed
  in the feature manifest.

## Samples

- `sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd` - `Newton` variant set with a `runnables/physics/newton.usd` payload.

## Benchmarks

- None.

## Adapters

None.

# Feature: `FET_024_NEWTON`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_024_NEWTON` |
| Runtime | `NEWTON` |
| Proprietary Techs | `Newton` |
| Latest Version | `0.1.0` |

## Description

Defines the Newton base-articulation contract. It depends on Standard articulation root
authoring and adds Newton articulation-root configuration via `newton:selfCollisionEnabled`.
The canonical form is `NewtonArticulationRootAPI` applied to the single articulation root
(it extends `PhysicsArticulationRootAPI` and defines `newton:selfCollisionEnabled` plus the
optional `newton:jointsAddMobility`); the bare `newton:selfCollisionEnabled` attribute on a
`PhysicsArticulationRootAPI` root is also accepted.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_024_NEWTON_0_1_0["FET_024_NEWTON\n0.1.0"]
    FET_024_STANDARD_0_1_0["FET_024_STANDARD\n0.1.0"]
    FET_024_NEWTON_0_1_0 --> FET_024_STANDARD_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies NEWTON.BA.001.
- Newton runtime validation is planned when a Newton robot profile consumes this feature.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_024_STANDARD@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Base Articulation](../capabilities/physics_bodies/base_articulation/capability-base-articulation.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `NEWTON.BA.001` | [NEWTON.BA.001](../capabilities/physics_bodies/base_articulation/requirements/newton-articulation-root-config.md) | [Implementation](../capabilities/physics_bodies/base_articulation/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies NEWTON.BA.001.
- Newton runtime validation is planned when a Newton robot profile consumes this feature.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.

# Feature: `FET_024_MUJOCO`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_024_MUJOCO` |
| Runtime | `MUJOCO` |
| Proprietary Techs | `MuJoCo` |
| Latest Version | `0.1.0` |

## Description

Defines the MuJoCo base-articulation contract. MuJoCo USD uses standard `UsdPhysics.ArticulationRootAPI`; the current official schema does not define a separate `MjcArticulationRootAPI` or `MjcArticulationRoot` type. Version 0.1.0 therefore depends on the Standard articulation feature and adds a MuJoCo compatibility check that rejects invented MuJoCo articulation-root schemas.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_024_STANDARD_0_1_0["FET_024_STANDARD\n0.1.0"]
    FET_024_MUJOCO_0_1_0["FET_024_MUJOCO\n0.1.0"]
    FET_024_MUJOCO_0_1_0 --> FET_024_STANDARD_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

- SimReady validation verifies MuJoCo-compatible articulation root authoring.
- MuJoCo robot runtime validation can consume a single standard articulation root while MuJoCo-specific data lives on supported scene, joint, actuator, collider, and site schemas.

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
| `MUJOCO.BA.001` | [MUJOCO.BA.001](../capabilities/physics_bodies/base_articulation/requirements/mujoco-standard-articulation-root.md) | [Implementation](../capabilities/physics_bodies/base_articulation/validation.py) |

</details>

## Pipelines

Source file type:

- `.mjcf`, `.xml`, `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- SimReady validation verifies `FET_024_MUJOCO@0.1.0`.
- MuJoCo runtime validation should verify that the single articulation root imports as the intended robot articulation.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.

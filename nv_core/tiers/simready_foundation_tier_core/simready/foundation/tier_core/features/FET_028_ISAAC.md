# Feature: `FET_028_ISAAC`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_028_ISAAC` |
| Runtime | `ISAAC` |
| Proprietary Techs | `Isaac Sim` |
| Latest Version | `0.1.0` |

## Description

Defines the Isaac gripper-site contract. It depends on the Standard gripper-site feature and the selected Isaac driven-joint version, then adds the Isaac gripper-site API requirement.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_022_ISAAC_0_1_0["FET_022_ISAAC\n0.1.0"]
    FET_028_ISAAC_0_1_0["FET_028_ISAAC\n0.1.0"]
    FET_028_STANDARD_0_1_0["FET_028_STANDARD\n0.1.0"]
    FET_028_ISAAC_0_1_0 --> FET_028_STANDARD_0_1_0
    FET_028_ISAAC_0_1_0 --> FET_022_ISAAC_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies the selected FET_028_ISAAC manifest.
- FET028 close-and-lift benchmark exercises Isaac gripper discovery and actuation.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Robot Gripper Isaac v0.1.0
- Robot Gripper Isaac v0.2.0
- Robot Gripper v2.0.0 optional

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_028_STANDARD@0.1.0` |
| Dependency | `FET_022_ISAAC@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Grippers](../capabilities/physics_bodies/physics_grippers/capability-physics_grippers.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `GR.ISA.001` | [GR.ISA.001](../capabilities/physics_bodies/physics_grippers/requirements/gripper-site-api.md) | [Implementation](../capabilities/physics_bodies/physics_grippers/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies the selected FET_028_ISAAC manifest.
- FET028 close-and-lift benchmark exercises Isaac gripper discovery and actuation.

## Samples

- [`Robotiq 2F-85` gripper](../../../../sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/2F-85.usda)

## Benchmarks

- FET028 gripper close-and-lift benchmark suite

## Adapters

None.

# Feature: `FET028_Gripper.Isaac`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET028_Gripper.Isaac` |
| Runtime                 | `Isaac` |
| Proprietary Techs       | `Isaac Sim` |
| Versions                | `0-1-0` |

## Description

Defines the Isaac gripper-site contract. It depends on the Standard gripper-site feature and the selected Isaac driven-joint version, then adds the Isaac gripper-site API requirement.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_022_ISAAC_0_1_0["FET022_DrivenJoints.Isaac\n0-1-0"]
    FET_028_ISAAC_0_1_0["FET028_Gripper.Isaac\n0-1-0"]
    FET_028_STANDARD_0_1_0["FET028_Gripper\n0-1-0"]
    FET_028_ISAAC_0_1_0 --> FET_028_STANDARD_0_1_0
    FET_028_ISAAC_0_1_0 --> FET_022_ISAAC_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies the selected FET028_Gripper.Isaac manifest.
- FET028 close-and-lift evaluation exercises Isaac gripper discovery and actuation.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET028_Gripper.0-1-0` |
| Dependency | `FET022_DrivenJoints.Isaac.0-1-0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Grippers](../rules_and_reqs/physics_bodies/physics_grippers/capability-physics_grippers.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `GR.ISA.001` | [GR.ISA.001](../rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-site-api.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies the selected FET028_Gripper.Isaac manifest.
- FET028 close-and-lift evaluation exercises Isaac gripper discovery and actuation.

## Samples

- [`Robotiq 2F-85` gripper](../../../../../../../sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/2F-85.usda)

## Evaluates

- FET028 gripper close-and-lift evaluation suite

## Adapters

None.

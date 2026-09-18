# Feature: `FET_022_ISAAC`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_022_ISAAC` |
| Runtime | `ISAAC` |
| Proprietary Techs | `Isaac Sim` |
| Latest Version | `0.2.0` |

## Description

Defines the Isaac driven-joint contract by adding robot-schema joint, link, and relationship checks on top of a PhysX driven-joint dependency.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_022_ISAAC_0_1_0["FET_022_ISAAC\n0.1.0"]
    FET_022_ISAAC_0_2_0["FET_022_ISAAC\n0.2.0"]
    FET_022_PHYSX_0_1_0["FET_022_PHYSX\n0.1.0"]
    FET_022_PHYSX_0_2_0["FET_022_PHYSX\n0.2.0"]
    FET_022_ISAAC_0_1_0 --> FET_022_PHYSX_0_1_0
    FET_022_ISAAC_0_2_0 --> FET_022_PHYSX_0_2_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies the selected FET_022_ISAAC manifest.
- SimReady Benchmark FET022 Driven Joints verifies Isaac/PhysX driven-joint behavior.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Robot Body Isaac v1.0.0
- Robot Gripper Isaac v0.1.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_022_PHYSX@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `DJ.008` | [DJ.008](../capabilities/physics_bodies/physics_driven_joints/requirements/robot-schema-joint-exist.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.009` | [DJ.009](../capabilities/physics_bodies/physics_driven_joints/requirements/robot-schema-links-exist.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.010` | [DJ.010](../capabilities/physics_bodies/physics_driven_joints/requirements/check-robot-relationships.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Robot Body Isaac v1.1.0
- Robot Body v2.0.0 optional
- Robot Gripper Isaac v0.2.0
- Robot Gripper v2.0.0 optional

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_022_PHYSX@0.2.0` |

#### Changes From Version 0.1.0

Keeps Version 0.1.0 requirements and updates the dependency to FET_022_PHYSX@2.

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies the selected FET_022_ISAAC manifest.
- SimReady Benchmark FET022 Driven Joints verifies Isaac/PhysX driven-joint behavior.

## Samples

- [`ur10` Isaac robot](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Benchmarks

- [FET022 Driven Joints](../guides/benchmark/tests/fet022-driven-joints.md):
  `drive_gain_validation`, `effort_limit`, `full_range_sweep`,
  `ik_target_reach`, `jacobian_ik`, `mimic_joint`,
  `multi_joint_coordination`, `state_accuracy`, and `velocity_limit`.

## Adapters

None.

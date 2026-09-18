# Feature: `FET_022_PHYSX`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_022_PHYSX` |
| Runtime | `PHYSX` |
| Proprietary Techs | `PhysX` |
| Latest Version | `0.2.0` |

## Description

Defines the PhysX driven-joint contract, adding PhysX-compatible drive, mimic, velocity, and drive-value requirements to robot joint authoring.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_004_PHYSX_0_4_0["FET_004_PHYSX\n0.4.0"]
    FET_004_ROBOT_PHYSX_0_1_0["FET_004_ROBOT_PHYSX\n0.1.0"]
    FET_022_PHYSX_0_1_0["FET_022_PHYSX\n0.1.0"]
    FET_022_PHYSX_0_2_0["FET_022_PHYSX\n0.2.0"]
    FET_022_PHYSX_0_1_0 --> FET_004_ROBOT_PHYSX_0_1_0
    FET_022_PHYSX_0_2_0 --> FET_004_PHYSX_0_4_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies the selected FET_022_PHYSX manifest.
- SimReady Benchmark FET022 Driven Joints verifies PhysX driven-joint behavior.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Robot Body Runnable v1.0.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_004_ROBOT_PHYSX@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `DJ.001` | [DJ.001](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-drive-and-joint-state.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.002` | [DJ.002](../capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-joint-state-api.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.003` | [DJ.003](../capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-correct-transform-and-state.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.004` | [DJ.004](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-has-drive-or-mimic-api.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.005` | [DJ.005](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-max-velocity.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.006` | [DJ.006](../capabilities/physics_bodies/physics_driven_joints/requirements/drive-joint-value-reasonable.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.007` | [DJ.007](../capabilities/physics_bodies/physics_driven_joints/requirements/mimic-api-check.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `DJ.011` | [DJ.011](../capabilities/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Robot Body Runnable v1.1.0
- Robot Body v2.0.0 optional
- Robot Gripper v2.0.0 optional

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_004_PHYSX@0.4.0` |

#### Changes From Version 0.1.0

Keeps Version 0.1.0 requirements and aligns the dependency with FET_004_PHYSX@4.

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies the selected FET_022_PHYSX manifest.
- SimReady Benchmark FET022 Driven Joints verifies PhysX driven-joint behavior.

## Samples

- [`ur10` PhysX robot](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Benchmarks

- [FET022 Driven Joints](../guides/benchmark/tests/fet022-driven-joints.md):
  `drive_gain_validation`, `effort_limit`, `full_range_sweep`,
  `ik_target_reach`, `jacobian_ik`, `mimic_joint`,
  `multi_joint_coordination`, `state_accuracy`, and `velocity_limit`.

## Adapters

None.

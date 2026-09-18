# Feature: `FET_022_MUJOCO`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_022_MUJOCO` |
| Runtime | `MUJOCO` |
| Proprietary Techs | `MuJoCo` |
| Latest Version | `0.1.0` |

## Description

Defines the MuJoCo driven-joint contract using standard USD physics joint topology with MuJoCo joint and actuator schemas. This feature is for robot assets whose MuJoCo runtime layer applies `MjcJointAPI` to articulation joints and authors `MjcActuator` prims that target those joints.

Version 0.1.0 depends on `FET_004_ROBOT_MUJOCO@0.1.0` so MuJoCo driven-joint and actuator validation runs after the MuJoCo robot multibody contract.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_004_ROBOT_MUJOCO_0_1_0["FET_004_ROBOT_MUJOCO\n0.1.0"]
    FET_022_MUJOCO_0_1_0["FET_022_MUJOCO\n0.1.0"]
    FET_022_MUJOCO_0_1_0 --> FET_004_ROBOT_MUJOCO_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies MuJoCo driven-joint requirements.
- MuJoCo runtime import uses `MjcJointAPI` and `MjcActuator` data to drive robot articulations.
- Converter-generated MuJoCo overlay layers can be validated without treating PhysX drive or joint-state schemas as the runtime contract.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_004_ROBOT_MUJOCO@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `DJ.011` | [DJ.011](../capabilities/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `MUJOCO.DJ.001` | [MUJOCO.DJ.001](../capabilities/physics_bodies/physics_driven_joints/requirements/mujoco-joint-api.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `MUJOCO.DJ.002` | [MUJOCO.DJ.002](../capabilities/physics_bodies/physics_driven_joints/requirements/mujoco-actuator-targets.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies MuJoCo driven-joint requirements.
- MuJoCo runtime validation should import the authored USD layer stack and verify that each `MjcActuator` drives its target joint as expected.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.

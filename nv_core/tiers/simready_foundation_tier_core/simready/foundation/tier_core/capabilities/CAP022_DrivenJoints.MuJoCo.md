# Capability: `CAP022_DrivenJoints.MuJoCo`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP022_DrivenJoints.MuJoCo` |
| Runtime                 | `MuJoCo` |
| Proprietary Techs       | `MuJoCo` |
| Versions                | `0-1-0` |

## Description

Defines the MuJoCo driven-joint contract using standard USD physics joint topology with MuJoCo joint and actuator schemas. This capability is for robot assets whose MuJoCo runtime layer applies `MjcJointAPI` to articulation joints and authors `MjcActuator` prims that target those joints.

Version 0-1-0 depends on `CAP004_Multibody.RobotMuJoCo.0-1-0` so MuJoCo driven-joint and actuator validation runs after the MuJoCo robot multibody contract.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_004_ROBOT_MUJOCO_0_1_0["CAP004_Multibody.RobotMuJoCo\n0-1-0"]
    FET_022_MUJOCO_0_1_0["CAP022_DrivenJoints.MuJoCo\n0-1-0"]
    FET_022_MUJOCO_0_1_0 --> FET_004_ROBOT_MUJOCO_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this capability:

- SimReady validation verifies MuJoCo driven-joint requirements.
- MuJoCo runtime import uses `MjcJointAPI` and `MjcActuator` data to drive robot articulations.
- Converter-generated MuJoCo overlay layers can be validated without treating PhysX drive or joint-state schemas as the runtime contract.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.1.0`, `2.2.0`, `3.0.0`

#### Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `CAP004_Multibody.RobotMuJoCo.0-1-0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../rules_and_reqs/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `DJ.011` | [DJ.011](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md) |
| `MUJOCO.DJ.001` | [MUJOCO.DJ.001](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/mujoco-joint-api.md) |
| `MUJOCO.DJ.002` | [MUJOCO.DJ.002](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/mujoco-actuator-targets.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies MuJoCo driven-joint requirements.
- MuJoCo runtime validation should import the authored USD layer stack and verify that each `MjcActuator` drives its target joint as expected.

## Samples

- None.

## Evaluates

- None.

## Adapters

None.

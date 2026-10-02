# Feature: `FET_022_NEWTON`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_022_NEWTON` |
| Runtime | `NEWTON` |
| Proprietary Techs | `Newton` |
| Latest Version | `0.1.0` |

## Description

Defines the Newton driven-joint contract. Actuation may be authored either with standard
`UsdPhysics.DriveAPI` drives or with the published Newton actuator schemas
(`NewtonActuator` + a control-law API), and Newton joint tuning is expressed with
`NewtonJointAPI` (or the equivalent `newton:*` resolver attributes) instead of PhysX joint
APIs. Coupled (mimic) joints are expressed with `NewtonMimicAPI`.

### Newton Authoring Notes

Editorial guidance (does not change the requirement IDs above):

- **Joint tuning** uses `NewtonJointAPI` on the `UsdPhysics.Joint`: `newton:armature`,
  `newton:damping`, `newton:friction` (all non-negative), `newton:velocityLimit`
  (positive or `inf`), and the `newton:limitStiffness` / `newton:limitDamping` limit spring
  (non-negative, or the `-inf` sentinel that defers to the engine default). Values broadcast
  uniformly to every DOF; angular attributes use degrees.
- **Actuators** are `NewtonActuator` prims that target a `PhysicsRevoluteJoint` or
  `PhysicsPrismaticJoint` via `rel newton:targets`. Each actuator applies exactly one control
  law — `NewtonPDControlAPI` (`newton:kp`, `newton:kd`, `newton:constEffort`),
  `NewtonPIDControlAPI` (adds `newton:ki`, `newton:integralMax`), or
  `NewtonNeuralControlAPI` — plus optional clamps (`NewtonMaxEffortClampingAPI` `newton:maxEffort`,
  `NewtonDCMotorClampingAPI`, `NewtonPositionBasedClampingAPI`) and an optional
  `NewtonActuatorDelayAPI` (`newton:delaySteps`). Actuators use radians.
- A joint counts as actuated for `NEWTON.DJ.001` when it has a `PhysicsDriveAPI:<axis>` **or**
  is targeted by a `NewtonActuator`. In the isolated Newton runtime layer, drive each joint by
  exactly one of these to avoid double-driving: the usual pattern removes the neutral
  `PhysicsDriveAPI` in the Newton runnable and drives via `NewtonActuator`. Keep the standard
  `PhysicsDriveAPI` only when the same joint must serve multiple runtimes in one composition.
- **Mimic (coupled) joints** use `NewtonMimicAPI` on the follower `UsdPhysics.Joint`
  (`NEWTON.DJ.003`): author `rel newton:mimicJoint` pointing at one leader joint (not the
  follower itself), with finite `newton:mimicCoef0` / `newton:mimicCoef1` enforcing
  `joint0 = coef0 + coef1 * joint1`. Apply only on single-DOF joints; typical use is a
  parallel-jaw gripper where one finger tracks the other.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_004_ROBOT_NEWTON_0_1_0["FET_004_ROBOT_NEWTON\n0.1.0"]
    FET_022_NEWTON_0_1_0["FET_022_NEWTON\n0.1.0"]
    FET_022_NEWTON_0_1_0 --> FET_004_ROBOT_NEWTON_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies Newton driven-joint requirements.
- SimReady Benchmark runs `state_accuracy` with the Newton engine to command
  driven joints and verify Newton joint-state readback against each target.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_004_ROBOT_NEWTON@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `DJ.011` | [DJ.011](../capabilities/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `NEWTON.DJ.001` | [NEWTON.DJ.001](../capabilities/physics_bodies/physics_driven_joints/requirements/newton-joint-drive-api.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `NEWTON.DJ.002` | [NEWTON.DJ.002](../capabilities/physics_bodies/physics_driven_joints/requirements/newton-joint-attributes.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |
| `NEWTON.DJ.003` | [NEWTON.DJ.003](../capabilities/physics_bodies/physics_driven_joints/requirements/newton-mimic-api.md) | [Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies Newton driven-joint requirements.
- `state_accuracy` runs in the Newton engine and verifies position-command
  tracking plus joint-state reporting for every eligible driven joint.

## Samples

- `sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd`

## Benchmarks

- `state_accuracy` (Kit / Isaac Sim Newton experience)

## Adapters

None.

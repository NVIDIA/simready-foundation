# Feature: `ID:022 - Driven - Joints`
## Description

Driven joints enable physics-driven joint simulation for articulated bodies and robotic mechanisms, with proper drive/state configuration, PhysX drive or mimic APIs, and robot-schema integration for Isaac Sim.

## Dependency Graph

```{mermaid}
flowchart LR
    FET004N["FET004_BASE_NEUTRAL\n0.1.0"]
    FET004RN["FET004_ROBOT_PHYSX\n0.1.0"]
    FET022N["FET022_DRIVEN_JOINTS_NEUTRAL\n0.1.0"]
    FET022P["FET022_DRIVEN_JOINTS_PHYSX\n0.1.0"]
    FET022I["FET022_DRIVEN_JOINTS_ISAAC\n0.1.0"]

    FET022N --> FET004N
    FET022P --> FET004RN
    FET022I --> FET022P

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET022N,FET022P,FET022I current
    class FET004N,FET004RN other
```

## Neutral Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET022_DRIVEN_JOINTS_NEUTRAL`|

#### Used in Profiles

This version is used in the following profiles:

- (None documented.)

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [ID:004 - Simulate Multi-Body Physics - Base - Neutral Format - v0.1.0](../features/FET_004-simulate_multi_body_physics.md#neutral-format) (FET004_BASE_NEUTRAL) |

* Capability: [Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)
    * Requirements:
        * [physics-drive-and-joint-state](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-drive-and-joint-state.md)
            * DJ.001 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [joint-has-joint-state-api](../capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-joint-state-api.md)
            * DJ.002 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [joint-has-correct-transform-and-state](../capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-correct-transform-and-state.md)
            * DJ.003 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [no-articulation-loops](../capabilities/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md)
            * DJ.011 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)

#### Pipelines Supported for this Feature

None.

#### Benchmarks

None.

</details>

## NVIDIA Physx Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET022_DRIVEN_JOINTS_PHYSX`|
| Proprietary Techs       | `Physx`           |

#### Used in Profiles

This version is used in the following profiles:

- (None documented.)

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Robot PhysX Format (FET004_ROBOT_PHYSX) - v0.1.0](../features/FET_004-simulate_multi_body_physics.md#robot-physx-format-fet004_robot_physx) |

* Capability: [Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)
    * Requirements:
        * [physics-drive-and-joint-state](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-drive-and-joint-state.md)
            * DJ.001 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [joint-has-joint-state-api](../capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-joint-state-api.md)
            * DJ.002 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [joint-has-correct-transform-and-state](../capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-correct-transform-and-state.md)
            * DJ.003 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [physics-joint-has-drive-or-mimic-api](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-has-drive-or-mimic-api.md)
            * DJ.004 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [physics-joint-max-velocity](../capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-max-velocity.md)
            * DJ.005 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [drive-joint-value-reasonable](../capabilities/physics_bodies/physics_driven_joints/requirements/drive-joint-value-reasonable.md)
            * DJ.006 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [mimic-api-check](../capabilities/physics_bodies/physics_driven_joints/requirements/mimic-api-check.md)
            * DJ.007 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [no-articulation-loops](../capabilities/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md)
            * DJ.011 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)

#### Pipelines Supported for this Feature

None.

#### Benchmarks

* Suite: [FET022 Driven Joints](../guides/benchmark/tests/fet022-driven-joints.md)
  * Tests:
    * [drive_gain_validation](../guides/benchmark/tests/fet022/drive-gain-validation.md)
    * [effort_limit](../guides/benchmark/tests/fet022/effort-limit.md)
    * [full_range_sweep](../guides/benchmark/tests/fet022/full-range-sweep.md)
    * [ik_target_reach](../guides/benchmark/tests/fet022/ik-target-reach.md)
    * [jacobian_ik](../guides/benchmark/tests/fet022/jacobian-ik.md)
    * [mimic_joint](../guides/benchmark/tests/fet022/mimic-joint.md)
    * [multi_joint_coordination](../guides/benchmark/tests/fet022/multi-joint-coordination.md)
    * [state_accuracy](../guides/benchmark/tests/fet022/state-accuracy.md)
    * [velocity_limit](../guides/benchmark/tests/fet022/velocity-limit.md)

</details>

## Isaac Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET022_DRIVEN_JOINTS_ISAAC`|
| Proprietary Techs       | `Isaac Sim`       |

#### Used in Profiles

This version is used in the following profiles:

- (None documented.)

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [ID:022 - Driven Joints - NVIDIA Physx Format - v0.1.0](#nvidia-physx-format) (FET022_DRIVEN_JOINTS_PHYSX) |

* Capability: [Physics Driven Joints](../capabilities/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)
    * Requirements:
        * [robot-schema-joint-exist](../capabilities/physics_bodies/physics_driven_joints/requirements/robot-schema-joint-exist.md)
            * DJ.008 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [robot-schema-links-exist](../capabilities/physics_bodies/physics_driven_joints/requirements/robot-schema-links-exist.md)
            * DJ.009 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)
        * [check-robot-relationships](../capabilities/physics_bodies/physics_driven_joints/requirements/check-robot-relationships.md)
            * DJ.010 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_driven_joints/validation.py)

#### Pipelines Supported for this Feature

None.

#### Benchmarks

* Suite: [FET022 Driven Joints](../guides/benchmark/tests/fet022-driven-joints.md)
  * Tests:
    * [drive_gain_validation](../guides/benchmark/tests/fet022/drive-gain-validation.md)
    * [effort_limit](../guides/benchmark/tests/fet022/effort-limit.md)
    * [full_range_sweep](../guides/benchmark/tests/fet022/full-range-sweep.md)
    * [ik_target_reach](../guides/benchmark/tests/fet022/ik-target-reach.md)
    * [jacobian_ik](../guides/benchmark/tests/fet022/jacobian-ik.md)
    * [mimic_joint](../guides/benchmark/tests/fet022/mimic-joint.md)
    * [multi_joint_coordination](../guides/benchmark/tests/fet022/multi-joint-coordination.md)
    * [state_accuracy](../guides/benchmark/tests/fet022/state-accuracy.md)
    * [velocity_limit](../guides/benchmark/tests/fet022/velocity-limit.md)

</details>

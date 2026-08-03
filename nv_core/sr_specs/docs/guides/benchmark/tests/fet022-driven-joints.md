# FET022 Driven Joints

Actively driven joints follow their commands within their declared limits.

## Overview

This family commands the asset's driven joints and confirms they reach their
targets, respect their velocity and effort limits, honor mimic relationships,
coordinate across multiple joints, and support inverse-kinematics reach. The
tests cover every aspect of joint authoring that determines whether an
articulated asset is controllable at runtime: drive gains, state accuracy,
limit enforcement, parallel linkage coupling, simultaneous coordination, and
end-effector IK.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset's joint drives, limits, and mimic
relationships are authored correctly so the articulation is controllable. The
same reviewer can rely on the family to confirm that the robot or articulated
tool will follow commanded trajectories in simulation, respect the declared
velocity and effort ceilings, and expose a usable IK interface for manipulation
planning.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [full_range_sweep](fet022/full-range-sweep.md)
  - Commands each joint across its full declared range and confirms it follows.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [velocity_limit](fet022/velocity-limit.md)
  - Confirms a joint does not exceed its declared velocity limit.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [effort_limit](fet022/effort-limit.md)
  - Confirms a joint respects its declared effort limit under external force.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [drive_gain_validation](fet022/drive-gain-validation.md)
  - Confirms the joint drive gains produce stable, low-overshoot tracking.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [state_accuracy](fet022/state-accuracy.md)
  - Confirms reported joint state matches commanded state across a waypoint sequence.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [mimic_joint](fet022/mimic-joint.md)
  - Confirms mimic joints follow their reference joint by the declared gear ratio.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [multi_joint_coordination](fet022/multi-joint-coordination.md)
  - Confirms multiple joints reach their targets simultaneously without interference.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [ik_target_reach](fet022/ik-target-reach.md)
  - Confirms the end effector reaches commanded poses using the Lula IK solver.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
* - [jacobian_ik](fet022/jacobian-ik.md)
  - Confirms Jacobian-based IK converges to FK-sampled targets without a Lula descriptor.
  - FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET022 Driven Joints](../../../features/FET_022-driven_joints.md).

```{toctree}
:maxdepth: 1
:hidden:

drive_gain_validation <fet022/drive-gain-validation>
effort_limit <fet022/effort-limit>
full_range_sweep <fet022/full-range-sweep>
ik_target_reach <fet022/ik-target-reach>
jacobian_ik <fet022/jacobian-ik>
mimic_joint <fet022/mimic-joint>
multi_joint_coordination <fet022/multi-joint-coordination>
state_accuracy <fet022/state-accuracy>
velocity_limit <fet022/velocity-limit>
```

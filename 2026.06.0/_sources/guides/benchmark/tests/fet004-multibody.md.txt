# FET004 Multibody

Multibody physics: jointed assemblies articulate at their joints.

## Overview

This family confirms that an asset built from multiple bodies connected by joints
actually articulates. The tests discover the asset's movable joints and verify
that the bodies those joints connect move relative to one another under simulation.
A robot arm, a gripper, a door panel, or any other jointed assembly must be able
to demonstrate real relative motion across its joints, not simply coexisting as
rigidly fused geometry.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset is a genuinely articulated
assembly rather than a fused or static mesh. At least one of the asset's joints
produces measurable relative motion between its connected bodies, confirming the
joint is not seized, its axis is correctly authored, and the connected bodies are
free to move within the joint's allowed degrees of freedom. An asset that passes
this family is ready for downstream robot simulation that depends on joint
articulation.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [joint_movement](fet004/joint-movement.md)
  - Discovers movable joints and verifies that at least one joint produces
    measurable relative motion between its connected bodies.
  - FET004_BASE_PHYSX, FET004_ROBOT_PHYSX
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET004 Multi-Body Physics](../../../features/FET_004-simulate_multi_body_physics.md).

```{toctree}
:maxdepth: 1
:hidden:

joint_movement <fet004/joint-movement>
```

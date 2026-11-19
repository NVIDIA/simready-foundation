# FET004 Multibody

Multibody physics: jointed assemblies articulate at their joints.

## Overview

This family discovers movable joints in an asset built from connected bodies
and checks for relative body motion under configured simulation probes. The Core
PhysX test requires at least one tested joint to cross its movement threshold;
it does not require every discovered joint to respond or certify the complete
articulation's behavior.

## What a Passing Family Means

At least one tested joint produced relative body motion above the configured
rotation or translation threshold. This does not establish that every joint
works, every axis or limit is correct, or the assembly is ready for every
downstream robot simulation. Review the individual joint metrics and videos.

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
  - FET004_Multibody, FET004_Multibody.PhysX, and
    FET004_Multibody.RobotPhysX (registered versions; RobotPhysX is deprecated compatibility)
:::

## Relationship to the Feature

These Core procedures validate the Standard and PhysX FET004 multibody
features using PhysX, including registered robot-specific PhysX variants.
Newton FET004 and RobotNewton features are exercised by the separate
`joint_movement_newton` procedure owned by the Newton tier.

```{toctree}
:maxdepth: 1
:hidden:

joint_movement <fet004/joint-movement>
```

# FET005 Grasp

Tests in this family verify that a robot gripper can grasp the asset, lift it off the ground, and hold it without the asset slipping or being knocked free.

## Overview

This family places a standardized parallel-jaw gripper at each declared grasp point on the asset, closes the jaws onto the asset under real gravity, and lifts the gripper to confirm the asset follows the motion. The gripper then holds the asset in the air, applies a circular horizontal orbit to stress the grip, and finally opens to release. The test confirms that each declared grasp point produces a physically achievable hold in the PhysX simulation engine.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that at least one declared grasp point on the asset produces a physically achievable hold in the PhysX simulation engine at 9.81 m/s squared gravity. An overall pass does not guarantee that every identifier succeeds; refer to the per-identifier results in the test metrics to confirm which grasp points are usable in a pick-and-place workflow.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [grasp_and_lift](fet005/grasp-and-lift.md)
  - The gripper positions at each grasp identifier, closes onto the asset, lifts it, holds it through a circular horizontal orbit shake, and releases it cleanly.
  - FET005_BASE_NEUTRAL
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET005 Grasp Physics](../../../features/FET_005-simulate_grasp_physics.md).

```{toctree}
:maxdepth: 1
:hidden:

grasp_and_lift <fet005/grasp-and-lift>
```

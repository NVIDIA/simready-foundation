# FET037 Joint Sensors

Joint sensor prims produce valid state data when the asset is simulated in Isaac Sim.

## Overview

This family loads a robot asset that conforms to FET_037_ISAAC into an
Isaac Sim physics scene, steps the simulation, and confirms that each
IsaacJointStateSensor prim reports numerically valid joint position and velocity
output that reflects the live articulation state.

A conforming asset must have already passed static validation (PS.002)
before these runtime tests are meaningful. An asset that fails static validation
will be reported as VALIDATION_FAILED and skipped.

**Note:** These tests require a robot asset that carries at least one
`IsaacJointStateSensor` prim. An asset with no joint sensors will be reported
as not applicable and skipped.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset's joint sensor prims are correctly
attached to an articulated body and configured so that Isaac Sim can initialize
them and produce live joint state data without manual intervention. The asset is
ready for use in control loops that close on joint state feedback.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [joint_sensor_data](fet037/joint-sensor-data.md)
  - Joint sensor prim reports joint position and velocity consistent with the physics simulation state.
  - FET_037_ISAAC
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET_037_ISAAC Joint Sensor](../../../features/FET_037_ISAAC-0.1.0.json).

```{toctree}
:maxdepth: 1
:hidden:

joint_sensor_data <fet037/joint-sensor-data>
```

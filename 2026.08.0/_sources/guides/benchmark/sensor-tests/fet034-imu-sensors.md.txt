# FET034 IMU Sensors

IMU sensor prims produce valid data streams when the asset is simulated in Isaac Sim.

## Overview

This family loads a robot asset that conforms to FET_034_ISAAC into an
Isaac Sim physics scene, steps the simulation, and confirms that each
IsaacImuSensor prim produces non-empty, numerically valid inertial output.

A conforming asset must have already passed static validation (PS.001)
before these runtime tests are meaningful. An asset that fails static validation
will be reported as VALIDATION_FAILED and skipped.

**Note:** These tests require a robot asset that carries at least one
`IsaacImuSensor` prim. An asset with no IMU sensors will be reported as not
applicable and skipped.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset's IMU sensor prims are correctly
placed and configured so that Isaac Sim can initialize them and produce live
inertial data without manual intervention. The asset is ready for use in
perception or navigation pipelines that depend on onboard IMU sensing.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [imu_sensor_data](fet034/imu-sensor-data.md)
  - IMU sensor prim produces non-zero angular velocity and linear acceleration after simulation steps.
  - FET_034_ISAAC
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET_034_ISAAC IMU Sensor](../../../features/FET_034_ISAAC-0.1.0.json).

```{toctree}
:maxdepth: 1
:hidden:

imu_sensor_data <fet034/imu-sensor-data>
```

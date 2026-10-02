# FET036 RTX Sensors

OmniLidar prims produce valid point cloud output when the asset is simulated in Isaac Sim.

## Overview

This family loads a robot asset that conforms to FET_036_RTX into an
Isaac Sim physics scene, steps the RTX render pipeline, and confirms that each
OmniLidar prim produces a non-empty, finite-valued point cloud.

A conforming asset must have already passed static validation (LI.001–LI.004)
before these runtime tests are meaningful. An asset that fails static validation
will be reported as VALIDATION_FAILED and skipped.

**Note:** These tests require a robot asset that carries at least one `OmniLidar`
prim with `OmniSensorGenericLidarCoreAPI` applied. An asset with no LiDAR sensors
will be reported as not applicable and skipped.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset's OmniLidar prims are correctly
typed and configured so that Isaac Sim can initialize the RTX render pipeline and
produce range data without manual intervention. The asset is ready for use in
mapping, obstacle avoidance, or synthetic data generation pipelines that depend
on LiDAR output.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [lidar_point_cloud](fet036/lidar-point-cloud.md)
  - OmniLidar prim produces a non-empty point cloud after one RTX sensor tick.
  - FET_036_RTX
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET_036_RTX RTX Sensors](../../../features/FET_036_RTX-0.1.0.json).

```{toctree}
:maxdepth: 1
:hidden:

lidar_point_cloud <fet036/lidar-point-cloud>
```

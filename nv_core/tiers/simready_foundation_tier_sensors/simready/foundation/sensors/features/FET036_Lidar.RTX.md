# Feature: `FET036_Lidar.RTX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET036_Lidar.RTX` |
| Runtime                 | `RTX` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines the simulation-readiness contract for OmniLidar RTX sensor prims. LiDAR is an RTX rendering sensor that fires rays and produces point cloud data via the GPU render pipeline. It is categorized under `nonvisual_sensors/` because its output is rendered data (GenericModelOutput point cloud), not physics simulation state.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies LiDAR sensor schema and parameter consistency at asset authoring time.
- Isaac Sim runtime evaluation test (`lidar_point_cloud`) verifies the sensor produces accurate range measurements by surrounding it with cubes at known distances and checking that measured returns match expected wall distances.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Sensor-LiDAR](../../../../../../sr_specs/docs/shared/profiles/profiles.md): required in `1.0.0`

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Non-Visual Sensors/LiDAR](../rules_and_reqs/nonvisual_sensors/lidar/capability-lidar.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `LI.001` | [LI.001](../rules_and_reqs/nonvisual_sensors/lidar/requirements/lidar-omni-lidar-schema.md) |
| `LI.002` | [LI.002](../rules_and_reqs/nonvisual_sensors/lidar/requirements/lidar-emitter-state-length.md) |
| `LI.003` | [LI.003](../rules_and_reqs/nonvisual_sensors/lidar/requirements/lidar-scan-rate-minimum.md) |
| `LI.004` | [LI.004](../rules_and_reqs/nonvisual_sensors/lidar/requirements/lidar-solid-state-rays-per-line.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- `simready-validate` verifies FET036_Lidar.RTX requirements at asset authoring time.
- `simready-evaluate --features FET036_Lidar.RTX` runs RTX LiDAR point cloud verification in Isaac Sim (requires GPU driver >= 576.x).

## Samples

- [sample_content/common_assets/sensors/lidar/OmniLidarCheckerPass.usda](../../../../../../../sample_content/common_assets/sensors/lidar/OmniLidarCheckerPass.usda)
- [sample_content/common_assets/sensors/lidar/OmniLidarSolidStateCheckerPass.usda](../../../../../../../sample_content/common_assets/sensors/lidar/OmniLidarSolidStateCheckerPass.usda)
- [sample_content/common_assets/sensors/lidar/OmniLidarSolidStateRTXPass.usda](../../../../../../../sample_content/common_assets/sensors/lidar/OmniLidarSolidStateRTXPass.usda)
- [sample_content/common_assets/sensors_fails/lidar/OmniLidarCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/lidar/OmniLidarCheckerFail.usda)
- [sample_content/common_assets/sensors_fails/lidar/OmniLidarEmitterStateCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/lidar/OmniLidarEmitterStateCheckerFail.usda)
- [sample_content/common_assets/sensors_fails/lidar/OmniLidarRangeCountCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/lidar/OmniLidarRangeCountCheckerFail.usda)
- [sample_content/common_assets/sensors_fails/lidar/OmniLidarScanRateCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/lidar/OmniLidarScanRateCheckerFail.usda)
- [sample_content/common_assets/sensors_fails/lidar/OmniLidarSolidStateCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/lidar/OmniLidarSolidStateCheckerFail.usda)

## Evaluates

- `lidar_point_cloud` — surrounds each OmniLidar sensor with 16 cubes at asymmetric known distances, runs 120 RTX scan frames, and verifies that per-return measured ranges match expected wall distances (fewer than 1% of non-edge returns exceed 2% range error). Skips (not fails) when GPU driver does not support RTX LiDAR CUDA 12.9.

## Adapters

None.

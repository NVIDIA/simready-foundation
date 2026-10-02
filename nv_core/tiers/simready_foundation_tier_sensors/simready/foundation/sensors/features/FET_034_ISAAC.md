# Feature: `FET_034_ISAAC`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_034_ISAAC` |
| Runtime | `ISAAC` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the simulation-readiness contract for IMU sensor prims on robot assets. An IMU sensor prim must be parented under a prim with PhysicsRigidBodyAPI so that the physics engine communicates forces and velocities to the sensor.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies IMU sensor wiring requirements at asset authoring time.
- Isaac Sim runtime benchmark tests (`imu_sensor_data`) verify live IMU sensor data output.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Sensor-IMU v1.0.0 (required)

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Physics Bodies/Physics Sensors](../capabilities/physics_bodies/physics_sensors/capability-physics_sensors.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `PS.001` | [PS.001](../capabilities/physics_bodies/physics_sensors/requirements/imu-sensor-rigid-body.md) | [Implementation](../capabilities/physics_bodies/physics_sensors/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- `simready-validate` verifies FET_034_ISAAC requirements at asset authoring time.
- `simready-benchmark --features FET_034_ISAAC` runs runtime IMU sensor data verification in Isaac Sim.

## Samples

- [sample_content/common_assets/sensors/physics_sensors/IMUSensorCheckerPass.usda](../../../../sample_content/common_assets/sensors/physics_sensors/IMUSensorCheckerPass.usda)
- [sample_content/common_assets/sensors_fails/physics_sensors/IMUSensorCheckerFail.usda](../../../../sample_content/common_assets/sensors_fails/physics_sensors/IMUSensorCheckerFail.usda)

## Benchmarks

- `imu_sensor_data` — verifies IMU sensor produces non-zero angular velocity and linear acceleration during physics simulation.

## Adapters

None.

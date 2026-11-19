# Sensor-IMU Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Sensor-IMU` profile.

`Sensor-IMU` is a sensor profile: it validates the IMU sensors an asset
carries, not the asset itself. Stamp it alongside the asset's primary profile
([`Robot-Body`](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-body.md), [`Robotics-Prop`](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md), or whichever profile matches the host asset — see the [profile index](../../../../../../sr_specs/docs/shared/profiles/profiles.md#profile-comparison)). An asset that
carries several sensor types is stamped with one sensor profile per type.

Validating an asset against this profile requires both the Sensors tier and
the Core tier:

```bash
pip install simready-validate simready-foundation-tier-sensors simready-foundation-tier-core
```

## Profile definition

The `Sensor-IMU` profile contains a single feature (see `profiles.toml`
alongside this document, and the
[feature dependency graph](../../../../../../sr_specs/docs/shared/features/feature-dependency-graph.md)):

```toml
[Sensor-IMU]
"1.0.0" = {features = [
    {selector = "FET034_ImuSensor.Isaac.0-1-0"}, # "IMU Sensor"
]}
```

[`FET034_ImuSensor.Isaac.0-1-0`](../features/FET034_ImuSensor.Isaac.md) defines the simulation-readiness
contract for IMU sensor prims. It has no feature dependencies, so this profile
checks IMU wiring only. Everything else about the asset — units, hierarchy,
physics, materials, packaging — comes from whichever primary profile the asset
is also stamped with.

## What the profile checks

| Requirement | Capability | Summary |
|---|---|---|
| [`PS.001`](../rules_and_reqs/physics_bodies/physics_sensors/requirements/imu-sensor-rigid-body.md) | [Physics Bodies/Physics Sensors](../rules_and_reqs/physics_bodies/physics_sensors/capability-physics_sensors.md) | An `IsaacImuSensor` prim must be a descendant of a prim with `PhysicsRigidBodyAPI` applied. |

The check applies only to the `IsaacImuSensor` prims a stage actually
contains. An asset with no IMU sensor **passes** this profile without
asserting anything. A passing result therefore means "every IMU present is
wired correctly", not "this asset has a working IMU" — confirm the sensor
exists before treating conformance as evidence that it does.

## Required USD authoring

An `IsaacImuSensor` reads forces and velocities from the physics engine. The
engine reports those quantities per rigid body, so the sensor only receives
data when it sits underneath one. A sensor authored outside a rigid body
loads without error and reports nothing at runtime, which is why this is
checked statically.

Place the sensor as a child or deeper descendant of the prim that carries
`PhysicsRigidBodyAPI`. An ancestor relationship is required; a sibling does
not satisfy `PS.001`.

```usd
# Valid: the sensor is under a rigid body
def Xform "Robot"
{
    def Xform "Base" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
        def IsaacImuSensor "IMU" {}
    }
}
```

```usd
# Invalid: no rigid body ancestor, so the sensor receives no physics state
def Xform "Robot"
{
    def IsaacImuSensor "IMU" {}
}
```

Mount the sensor at the pose it occupies on the physical robot. The profile
does not check placement, so an IMU authored at the body origin passes
validation while producing accelerations that do not match the real device.

## Validation

A sensor profile is validated in its own run. "Stamping both profiles" means
validating the asset against each requested target independently:

```bash
simready-validate --profile Robotics-Prop --version 4.0.0 path/to/asset.usd
simready-validate --profile Sensor-IMU --version 1.0.0 path/to/asset.usd
```

Both runs must pass. The sensor profile is not a substitute for the primary
one — on its own it says nothing about units, hierarchy, physics, materials,
or packaging.

Preserve a separate report for each `(profile, version)` target. To retain
profile-keyed USD receipts, use the multi-profile API described in the
[profile validation guide](../../../../../../sr_specs/docs/guides/profiles/profiles.md#chain-stamping).

## Runtime verification

Static validation confirms the sensor is wired to a rigid body. It cannot
confirm the sensor produces data. The Evaluate test `imu_sensor_data` checks
that the sensor reports non-zero angular velocity and linear acceleration
during physics simulation:

```bash
pip install "simready-foundation-tier-sensors[evaluate]"
simready-evaluate --features FET034_ImuSensor.Isaac.0-1-0
```

The `[evaluate]` extra installs the Evaluate engine; a validator-only tier
install does not include it.

## Samples

- Passing: `sample_content/common_assets/sensors/physics_sensors/IMUSensorCheckerPass.usda`
- Failing: `sample_content/common_assets/sensors_fails/physics_sensors/IMUSensorCheckerFail.usda`

## References

- [`FET034_ImuSensor.Isaac.0-1-0` feature](../features/FET034_ImuSensor.Isaac.md)
- [Physics Sensors capability](../rules_and_reqs/physics_bodies/physics_sensors/capability-physics_sensors.md)
- [`PS.001` imu-sensor-rigid-body](../rules_and_reqs/physics_bodies/physics_sensors/requirements/imu-sensor-rigid-body.md)
- `profiles.toml`, the profile definition alongside this document

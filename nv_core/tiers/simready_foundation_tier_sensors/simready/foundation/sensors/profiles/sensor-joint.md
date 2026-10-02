# Sensor-Joint Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Sensor-Joint` profile.

`Sensor-Joint` is a sensor profile: it validates the joint state sensors an
asset carries, not the asset itself. Stamp it alongside the asset's primary
profile ([`Robot-Body`](robot-body.md), [`Robot-Gripper`](robot-gripper.md), or whichever profile matches the host asset — see the [profile index](profiles.md#profile-comparison)). An asset that carries
several sensor types is stamped with one sensor profile per type.

Validating an asset against this profile requires both the Sensors tier and
the Core tier:

```bash
pip install simready-validate simready-foundation-tier-sensors simready-foundation-tier-core
```

## Profile definition

The `Sensor-Joint` profile contains a single feature (see `profiles.toml`
alongside this document, and the
[feature dependency graph](../features/feature-dependency-graph)):

```toml
[Sensor-Joint]
"1.0.0" = {features = [
    {"FET_037_ISAAC" = {version = "0.1.0"}}, # "Joint Sensor"
]}
```

[`FET_037_ISAAC`](../features/FET_037_ISAAC.md) defines the simulation-readiness
contract for joint sensor prims. It has no feature dependencies, so this
profile checks joint sensor wiring only. The articulation itself — joint
topology, drives, articulation roots — is the responsibility of the asset's
primary profile.

## What the profile checks

| Requirement | Capability | Summary |
|---|---|---|
| [`PS.002`](../capabilities/physics_bodies/physics_sensors/requirements/joint-sensor-articulation-root.md) | [Physics Bodies/Physics Sensors](../capabilities/physics_bodies/physics_sensors/capability-physics_sensors.md) | An `IsaacJointStateSensor` prim must also have `PhysicsArticulationRootAPI` applied. |

The check applies only to the `IsaacJointStateSensor` prims a stage actually
contains. An asset with no joint sensor **passes** this profile without
asserting anything. A passing result therefore means "every joint sensor
present is wired correctly", not "this asset reports joint state" — confirm
the sensor exists before treating conformance as evidence that it does.

## Required USD authoring

A joint state sensor reports the positions and velocities of the joints in an
articulation. The physics engine exposes that state through the articulation,
so the sensor must sit on the prim the engine treats as the articulation root.
Without `PhysicsArticulationRootAPI` the articulation is never initialized for
readback and the sensor returns nothing.

Note the difference from [`Sensor-IMU`](sensor-imu.md): `PS.001` requires an
*ancestor* carrying `PhysicsRigidBodyAPI`, while `PS.002` requires the API on
the *same prim* as the sensor. A parent with `PhysicsArticulationRootAPI` does
not satisfy `PS.002`.

```usd
# Valid: both the sensor type and the articulation root API on one prim
def IsaacJointStateSensor "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

```usd
# Invalid: the articulation is never initialized for joint state readback
def IsaacJointStateSensor "Robot"
{
}
```

In practice this prim is the root of the articulated robot, which means the
asset's articulation root and its joint sensor are the same prim. Confirm this
against the base articulation requirements in the asset's primary profile so
the two do not disagree about which prim is the root.

## Validation

A sensor profile is validated in its own run. "Stamping both profiles" means
validating the asset against each one; there is no combined invocation:

```bash
simready-validate --profile Robot-Body --version 3.0.0 path/to/asset.usd
simready-validate --profile Sensor-Joint --version 1.0.0 path/to/asset.usd
```

Both runs must pass. The sensor profile is not a substitute for the primary
one — on its own it says nothing about units, hierarchy, physics, materials,
or packaging.

If you record the result in the optional `validation` dictionary under
`SimReady_Metadata`, note that the documented form holds a single `profile`
and `profile_version`. Record the primary profile there and track sensor
conformance alongside it; the metadata has no multi-profile form today.

## Runtime verification

Static validation confirms the API is applied. It cannot confirm the sensor
reports usable joint state. The Benchmark test `joint_sensor_data` checks that
the sensor reports valid joint positions after a drive target moves:

```bash
pip install "simready-foundation-tier-sensors[benchmark]"
simready-benchmark --features FET_037_ISAAC
```

The `[benchmark]` extra installs the Benchmark engine; a validator-only tier
install does not include it.

## Samples

- Passing: `sample_content/common_assets/sensors/physics_sensors/JointSensorCheckerPass.usda`
- Failing: `sample_content/common_assets/sensors_fails/physics_sensors/JointSensorCheckerFail.usda`

## References

- [`FET_037_ISAAC` feature](../features/FET_037_ISAAC.md)
- [Physics Sensors capability](../capabilities/physics_bodies/physics_sensors/capability-physics_sensors.md)
- [`PS.002` joint-sensor-articulation-root](../capabilities/physics_bodies/physics_sensors/requirements/joint-sensor-articulation-root.md)
- `profiles.toml`, the profile definition alongside this document

# Sensor-LiDAR Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Sensor-LiDAR` profile.

`Sensor-LiDAR` is a sensor profile: it validates the LiDAR sensors an asset
carries, not the asset itself. Stamp it alongside the asset's primary profile
([`Robot-Body`](robot-body.md), [`Robotics-Prop`](robotics-prop.md), or whichever profile matches the host asset — see the [profile index](profiles.md#profile-comparison)).

LiDAR is an RTX rendering sensor. It fires rays and produces point cloud data
through the GPU render pipeline, which is why its capability sits under
`nonvisual_sensors/` — the output is rendered data rather than physics
simulation state. A LiDAR that writes through a `RenderProduct` is also
covered by [`Sensor-Camera`](sensor-camera.md), which owns the render product
and compression rules; stamp both.

Validating an asset against this profile requires both the Sensors tier and
the Core tier:

```bash
pip install simready-validate simready-foundation-tier-sensors simready-foundation-tier-core
```

## Profile definition

The `Sensor-LiDAR` profile contains a single feature (see `profiles.toml`
alongside this document, and the
[feature dependency graph](../features/feature-dependency-graph)):

```toml
[Sensor-LiDAR]
"1.0.0" = {features = [
    {"FET_036_RTX" = {version = "0.1.0"}}, # "LiDAR (OmniLidar RTX)"
]}
```

[`FET_036_RTX`](../features/FET_036_RTX.md) defines the schema and parameter
consistency contract for OmniLidar sensor prims.

## What the profile checks

All four requirements belong to the
[Non-Visual Sensors/LiDAR](../capabilities/nonvisual_sensors/lidar/capability-lidar.md)
capability.

| Requirement | Summary |
|---|---|
| [`LI.001`](../capabilities/nonvisual_sensors/lidar/requirements/lidar-omni-lidar-schema.md) | A LiDAR must be an `OmniLidar` prim with `OmniSensorGenericLidarCoreAPI` applied. The legacy `Camera` with `cameraSensorType="lidar"` pattern is not allowed. |
| [`LI.002`](../capabilities/nonvisual_sensors/lidar/requirements/lidar-emitter-state-length.md) | Every emitter state array must have the same length as `omni:sensor:Core:numberOfEmitters`, and the arrays must agree with each other. |
| [`LI.003`](../capabilities/nonvisual_sensors/lidar/requirements/lidar-scan-rate-minimum.md) | `omni:sensor:Core:scanRateBaseHz` must be at least 0.466 Hz. |
| [`LI.004`](../capabilities/nonvisual_sensors/lidar/requirements/lidar-solid-state-rays-per-line.md) | For solid-state LiDARs, the elements of `omni:sensor:Core:numRaysPerLine` must sum to `omni:sensor:Core:numberOfEmitters`. |

These checks apply only to the `OmniLidar` prims a stage actually contains.
An asset with no LiDAR **passes** this profile without asserting anything, and
`LI.004` additionally does not apply to rotary sensors. A passing result
therefore means "every LiDAR present is configured consistently", not "this
asset produces a point cloud" — confirm the sensor exists before treating
conformance as evidence that it does.

## Required USD authoring

### Use the OmniLidar schema

```usd
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    uint omni:sensor:Core:numberOfEmitters = 1
}
```

The legacy pattern of a `UsdGeom.Camera` prim carrying
`cameraSensorType = "lidar"` is rejected by `LI.001`. Assets migrating from
that pattern need the prim retyped, not just re-tagged.

### Keep the emitter arrays consistent

`omni:sensor:Core:numberOfEmitters` declares how many laser emitters the
sensor has. Per-emitter configuration is stored in parallel arrays named
`omni:sensor:Core:emitterState:<instance>:<attr>`, for example:

```
omni:sensor:Core:emitterState:s001:azimuthDeg
omni:sensor:Core:emitterState:s001:elevationDeg
omni:sensor:Core:emitterState:s001:channelId
```

Each of these must contain exactly `numberOfEmitters` elements, and they must
agree with one another (`LI.002`). The one exception is `isRoiState`, which
may have a different length. A mismatch hands the sensor runtime malformed
parameters and the output is wrong rather than absent.

### Respect the scan rate floor

`omni:sensor:Core:scanRateBaseHz` must be at least 0.466 Hz (`LI.003`). The
reason is a hard limit rather than a style preference: the runtime stores
per-point time offsets in `GenericModelOutput` as signed 32-bit nanosecond
integers, which top out at roughly 2.147 seconds. Below 0.466 Hz a single
scan cycle exceeds that, and `timeOffsetNs` overflows, corrupting the timing
data in the point cloud.

### Match rays per line to emitter count on solid-state sensors

Solid-state LiDARs (`omni:sensor:Core:scanType = "SOLID_STATE"`) arrange a
fixed 2-D emitter array into lines, with `omni:sensor:Core:numRaysPerLine`
declaring how many emitters fire per line. Those values must sum to
`numberOfEmitters` (`LI.004`). For example, `numberOfEmitters = 4` with
`numRaysPerLine = [2, 2]` is consistent.

This does not apply to rotary LiDARs (`scanType = "ROTARY"`), which do not use
the attribute. A mismatch on a solid-state sensor makes the simulation reject
the configuration at startup, so validating it early turns a runtime error
into an authoring-time one.

## Validation

A sensor profile is validated in its own run. "Stamping both profiles" means
validating the asset against each one; there is no combined invocation:

```bash
simready-validate --profile Robotics-Prop --version 4.0.0 path/to/asset.usd
simready-validate --profile Sensor-LiDAR --version 1.0.0 path/to/asset.usd
```

Both runs must pass. The sensor profile is not a substitute for the primary
one — on its own it says nothing about units, hierarchy, physics, materials,
or packaging.

If you record the result in the optional `validation` dictionary under
`SimReady_Metadata`, note that the documented form holds a single `profile`
and `profile_version`. Record the primary profile there and track sensor
conformance alongside it; the metadata has no multi-profile form today.

## Runtime verification

Static validation confirms the schema and parameter consistency. It cannot
confirm the sensor measures accurately. The Benchmark test
`lidar_point_cloud` surrounds each sensor with 16 cubes at asymmetric known
distances, runs 120 RTX scan frames, and checks each return against the
expected wall distance. It passes when fewer than 1% of returns exceed 2%
range error, measured across non-edge returns:

```bash
pip install "simready-foundation-tier-sensors[benchmark]"
simready-benchmark --features FET_036_RTX
```

The `[benchmark]` extra installs the Benchmark engine; a validator-only tier
install does not include it.

This test requires GPU driver 576.x or newer for RTX LiDAR CUDA 12.9 support
in Isaac Sim 6.0.1. On an older driver every scan buffer comes back empty and
the test **skips rather than fails**, so confirm it actually ran before
treating a clean report as evidence that the sensor measures correctly.

## Samples

Passing:

- `sample_content/common_assets/sensors/lidar/OmniLidarCheckerPass.usda`
- `sample_content/common_assets/sensors/lidar/OmniLidarSolidStateCheckerPass.usda`
- `sample_content/common_assets/sensors/lidar/OmniLidarSolidStateRTXPass.usda`

Failing, one per rule:

- `OmniLidarCheckerFail.usda` (`LI.001`)
- `OmniLidarEmitterStateCheckerFail.usda` (`LI.002`)
- `OmniLidarScanRateCheckerFail.usda` (`LI.003`)
- `OmniLidarSolidStateCheckerFail.usda` (`LI.004`)
- `OmniLidarRangeCountCheckerFail.usda`

All under `sample_content/common_assets/sensors_fails/lidar/`.

## References

- [`FET_036_RTX` feature](../features/FET_036_RTX.md)
- [LiDAR capability](../capabilities/nonvisual_sensors/lidar/capability-lidar.md)
- [`Sensor-Camera` profile](sensor-camera.md)
- `profiles.toml`, the profile definition alongside this document

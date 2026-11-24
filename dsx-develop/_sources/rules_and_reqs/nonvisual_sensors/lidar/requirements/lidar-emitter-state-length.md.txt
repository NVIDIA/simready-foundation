# lidar-emitter-state-length

| Code     | LI.002 |
|----------|--------|
| Tags     | {tag}`correctness` |

## Summary

Every emitter state array attribute on an OmniLidar prim must have the same length as `omni:sensor:Core:numberOfEmitters`, and all emitter state arrays must be mutually consistent in length.

## Description

An OmniLidar prim with `OmniSensorGenericLidarCoreAPI` applied declares the number of laser emitters via the scalar attribute `omni:sensor:Core:numberOfEmitters`. Each per-emitter configuration is stored as a set of parallel arrays following the naming pattern:

```
omni:sensor:Core:emitterState:<instance>:<attr>
```

For example:
```
omni:sensor:Core:emitterState:s001:azimuthDeg
omni:sensor:Core:emitterState:s001:elevationDeg
omni:sensor:Core:emitterState:s001:channelId
```

Every such array (except `isRoiState`, which may have a different length) must contain exactly `numberOfEmitters` elements. If any array has a different length, the sensor runtime will receive malformed parameters and produce incorrect output.

## Why is it required?

The OmniLidar sensor runtime (`LidarCoreSensorCheckerImpl`) validates this constraint before simulation begins and rejects the sensor configuration if array lengths do not match `numberOfEmitters`. A mismatch at authoring time will cause a runtime error that is difficult to diagnose. Catching it statically during asset validation prevents broken sensor configurations from reaching simulation.

## Examples

```usd
# Valid: numberOfEmitters = 1, all emitter state arrays have length 1
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    uint omni:sensor:Core:numberOfEmitters = 1
    float[] omni:sensor:Core:emitterState:s001:azimuthDeg   = [0]
    float[] omni:sensor:Core:emitterState:s001:elevationDeg = [5]
    uint[]  omni:sensor:Core:emitterState:s001:channelId    = [0]
}

# Invalid: numberOfEmitters = 2 but elevationDeg only has 1 element
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    uint omni:sensor:Core:numberOfEmitters = 2
    float[] omni:sensor:Core:emitterState:s001:azimuthDeg   = [0, 90]
    float[] omni:sensor:Core:emitterState:s001:elevationDeg = [5]      # wrong length
    uint[]  omni:sensor:Core:emitterState:s001:channelId    = [0, 1]
}
```

## How to comply

- Set `omni:sensor:Core:numberOfEmitters` to the correct emitter count.
- Ensure every `omni:sensor:Core:emitterState:*` array attribute (except `isRoiState`) has exactly that many elements.
- The attribute `omni:sensor:Core:emitterState:*:isRoiState` is exempt from this length requirement.

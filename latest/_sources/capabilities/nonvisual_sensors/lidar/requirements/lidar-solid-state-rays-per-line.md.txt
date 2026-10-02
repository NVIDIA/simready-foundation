# lidar-solid-state-rays-per-line

| Code     | LI.004 |
|----------|--------|
| Tags     | {tag}`correctness` |

## Summary

For solid-state OmniLidar prims, the sum of all elements in `omni:sensor:Core:numRaysPerLine` must equal `omni:sensor:Core:numberOfEmitters`.

## Description

Solid-state LiDARs (`omni:sensor:Core:scanType = "SOLID_STATE"`) use a fixed 2-D array of emitters organised into lines. The attribute `omni:sensor:Core:numRaysPerLine` declares how many emitters fire on each line. The total number of emitters across all lines must equal the value of `omni:sensor:Core:numberOfEmitters`.

This constraint is enforced by `LidarCoreSensorCheckerImpl::validateNumRaysPerLine` in the RTX sensor plugin, which is applied only for solid-state scan types.

This requirement does not apply to rotary lidars (`scanType = "ROTARY"`), which do not use the `numRaysPerLine` attribute.

## Why is it required?

A mismatch between the declared number of emitters and the sum of rays per line means the sensor runtime cannot construct a consistent emitter layout. The simulation will reject the configuration at startup with a runtime error. Catching this at asset validation time makes the failure visible before any simulation is run.

## Examples

```usd
# Valid: numberOfEmitters = 4, numRaysPerLine = [2, 2], sum = 4
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    token omni:sensor:Core:scanType = "SOLID_STATE"
    uint omni:sensor:Core:numberOfEmitters = 4
    uint omni:sensor:Core:numberOfLines = 2
    uint[] omni:sensor:Core:numRaysPerLine = [2, 2]
}

# Invalid: numberOfEmitters = 4 but sum(numRaysPerLine) = 3
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    token omni:sensor:Core:scanType = "SOLID_STATE"
    uint omni:sensor:Core:numberOfEmitters = 4
    uint omni:sensor:Core:numberOfLines = 2
    uint[] omni:sensor:Core:numRaysPerLine = [1, 2]
}
```

## How to comply

Ensure `sum(numRaysPerLine) == numberOfEmitters`. If the sensor has `N` emitters divided equally across `L` lines, set `numRaysPerLine` to an array of `L` elements each with value `N / L`. Non-uniform distributions are supported as long as the total is exactly `numberOfEmitters`.

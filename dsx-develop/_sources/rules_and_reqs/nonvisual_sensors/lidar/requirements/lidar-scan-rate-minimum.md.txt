# lidar-scan-rate-minimum

| Code     | LI.003 |
|----------|--------|
| Tags     | {tag}`correctness` |

## Summary

The `omni:sensor:Core:scanRateBaseHz` attribute on an OmniLidar prim must be at least 0.466 Hz.

## Description

The OmniLidar runtime stores per-point time offsets in the `GenericModelOutput` buffer as signed 32-bit nanosecond integers. One scan cycle at a rate of `f` Hz takes `1/f` seconds = `1e9/f` nanoseconds. The maximum value of a signed 32-bit integer is 2,147,483,647 ns (~2.147 seconds). At scan rates below 0.466 Hz the nanosecond duration of one scan cycle exceeds this limit, causing integer overflow in the `timeOffsetNs` output field.

The minimum supported scan rate is 0.466 Hz, as enforced by `LidarCoreSensorCheckerImpl::validateElementDataType` in the RTX sensor plugin.

## Why is it required?

A scan rate below 0.466 Hz causes `timeOffsetNs` values in the point cloud to overflow, corrupting timing data. Catching this at asset validation time prevents a misconfigured sensor from producing silently incorrect simulation output.

## Examples

```usd
# Valid: 10 Hz scan rate (well above minimum)
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    uint omni:sensor:Core:scanRateBaseHz = 10
    token omni:sensor:Core:scanType = "ROTARY"
}

# Invalid: 0.1 Hz is below the 0.466 Hz minimum
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    float omni:sensor:Core:scanRateBaseHz = 0.1
    token omni:sensor:Core:scanType = "ROTARY"
}
```

## How to comply

Set `omni:sensor:Core:scanRateBaseHz` to a value of 0.466 or greater. Typical LiDAR scan rates are 5–25 Hz, well above this threshold. A value of 0 is also invalid; omit the attribute entirely if the scan rate is not applicable to the sensor configuration.

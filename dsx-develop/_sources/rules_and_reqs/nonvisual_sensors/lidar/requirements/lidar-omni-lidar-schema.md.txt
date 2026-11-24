# lidar-omni-lidar-schema

| Code     | LI.001 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

LiDAR sensors must be represented as OmniLidar prims with OmniSensorGenericLidarCoreAPI applied. The legacy UsdGeom.Camera with cameraSensorType="lidar" pattern is not allowed.

## Examples

```usd
# Invalid: legacy Camera prim used as a LiDAR
def Camera "Lidar"
{
    token cameraSensorType = "lidar"
}

# Valid: OmniLidar prim with OmniSensorGenericLidarCoreAPI
def OmniLidar "Lidar" (
    prepend apiSchemas = ["OmniSensorGenericLidarCoreAPI"]
)
{
    uint omni:sensor:Core:numberOfEmitters = 1
}
```

## How to comply

- Use an `OmniLidar` prim type (not `Camera`) for all LiDAR sensors.
- Apply `OmniSensorGenericLidarCoreAPI` to the prim.
- Remove any `cameraSensorType = "lidar"` attributes.

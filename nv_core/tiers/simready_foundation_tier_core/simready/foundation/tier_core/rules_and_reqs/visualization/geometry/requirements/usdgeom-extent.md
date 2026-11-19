# usdgeom-extent

| Code     | VG.002 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`OpenUSD`  |
| Tags     | {tag}`performance` |

## Summary

Boundable geometry primitives must have valid extent values.

## Description

The extent of a geometry primitive represents its bounding box in local space.
For time-varying geometry, the extent must be computed at each time sample where the geometry changes, but should only be authored when it differs from the previous time sample's extent to minimize data storage.

## Why is it required?
- Enables rendering performance through efficient culling
- Enables fast spatial queries and collision detection
- Supports efficient scene traversal and bounding box calculations
- Provides accurate bounds for time-varying geometry

## Examples

### Invalid: Incorrect extent on static geometry

```usd
#usda 1.0

def Mesh "MeshWithIncorrectExtent" {
    point3f[] points = [(0,0,0), (1,1,1)]
    float3[] extent = [(-1,-1,-1), (1,1,1)]
}
```

### Invalid: Missing extent on time-varying geometry

```usd
#usda 1.0

def Mesh "MeshWithoutExtent" {
    float[] times = [0, 1]
    point3f[] points.timeSamples = {
        0: [(0,0,0), (1,1,1)],
        1: [(0,0,0), (2,2,2)]
    }
    # Missing extent attribute
}
```

### Valid: Extent authored only when it changes

```usd
#usda 1.0

def Mesh "MeshWithExtent" {
    float[] times = [0, 1]
    point3f[] points.timeSamples = {
        0: [(0,0,0), (1,1,1)],
        1: [(0,0,0), (2,2,2)]
    }
    float3[] extent.timeSamples = {
        0: [(0,0,0), (1,1,1)],  # Initial extent
        1: [(0,0,0), (2,2,2)]   # Extent changes with geometry
    }
}
```

## How to comply
- Author extent for boundable geometry
- For time-varying geometry:
  - Compute extent at each time sample of attributes which may influence the extent. See `ComputeExtent` and `ComputeExtentFromPlugins` in [UsdGeomBoundable](https://openusd.org/release/api/class_usd_geom_boundable.html) for more information.
  - Only author when value changes

## For More Information
- [UsdGeom Extent Documentation](https://openusd.org/release/api/class_usd_geom_boundable.html)

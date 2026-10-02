# usdgeom-boundable-size-rtx-limit

| Code     | VG.RTX.001 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`RTX`  |
| Tags     | {tag}`limitation` |

## Summary

World space bounds must not exceed RTX limit.

## Description

The world space extents of any Boundable must be within 2^40 units of the origin.
Failure to meet this requirement will result in the offending object being discarded by the RTX renderer.
In order to avoid reaching the RTX imposed limit an "almost extreme" check should be used that looks for Boundable Prims that a more than 2^38 units from the origin.

## Why is it required?
- Correct visualization

## Examples

```usd
#usda 1.0
(
    metersPerUnit = 0.01
)

def Xform "World"
{
    def Cube "Sphere"
    {
        float3[] extent = [(-1, -1, -1), (1, 1, 1)]
        double size = 2.0
        double3 xformOp:translate = (2000000000000.0, 0.0, 0.0)
        double3 xformOp:scale = (1.0, 1.0, 1.0)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
}
```

## How to comply
- Use a higher linear unit (meters per unit) value
- Move the stage origin so that contents are centered around the origin

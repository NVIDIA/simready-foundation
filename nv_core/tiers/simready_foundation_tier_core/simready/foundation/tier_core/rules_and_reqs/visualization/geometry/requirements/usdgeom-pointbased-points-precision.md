# usdgeom-pointbased-points-precision

| Code     | VG.020 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

The values of `points` must not exceed the limit at which a given precision can be represented using 32-bit floats.

## Description

Point values must remain within a range where a given precision, represented as the smallest possible increment, can be accurately preserved using
32-bit (single precision) floats.

A point value is considered unsafe if it exceeds:

```python
maxSafeValue: float = minIncrement * pow(2, 23)
```

Failure to meet this requirement will result in loss of precision, where small changes are rounded away or entirely lost. This can lead to visible
artifacts in geometry, inaccurate positioning, or instability in rendering and simulation workflows.

The minimum increment must be adapted according to the Stage's linear units (metersPerUnit).

## Why is it required?
To ensure correct visual representation of geometry, accurate placement, and stable rendering or simulation behavior.

## Examples

With a linear unit of meters the `points` of the `Mesh` could not safely express an increment of 1 meter.

```usd
#usda 1.0
(
    metersPerUnit = 0.01
)

def Xform "World"
{
    def Mesh "Mesh"
    {
        uniform token subdivisionScheme = "none"
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(9000000, 0, 9000000), (-9000000, 0, 9000000), (-9000000, 0, -9000000), (9000000, 0, -9000000)]
    }
}
```

## How to comply
- Apply a transform to the Prim and subtract that from the `points` values.

## For more information
- [USDGeom Point Attribute datatype](https://openusd.org/release/api/class_usd_geom_point_based.html#ade9b7ab444b88ff2bb20ac5533dae030)
- [USDGeom XformOp Attribute datatype](https://openusd.org/dev/api/class_usd_geom_xformable.html#ad6dfc740dcec052482489647af9ed36b)
- [Discussion about Geometry Precision on AOUSD Forum](https://forum.aousd.org/t/double-support-in-geometry-data/808)

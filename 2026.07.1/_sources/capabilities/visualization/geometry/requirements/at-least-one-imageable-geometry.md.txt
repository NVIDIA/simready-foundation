# at-least-one-imageable-geometry

| Code     | VG.001 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`essential` |

## Summary

Assets must contain at least one Imageable Geometry  

## Description

Assets must contain at least one imageable geometry primitive to be visualized or simulated. An imageable geometry primitive is any USD prim that inherits from UsdGeomGprim and has a computed purpose of "render" or "default".

## Why is it required?

- Asset cannot be visualized
- Asset cannot be simulated
- Asset validation will fail

## Examples

```usd
# Invalid: No imageable geometry
def Xform "EmptyAsset" {
}

# Invalid: Geometry with wrong purpose
def Mesh "InvisibleCube" (
    purpose = "guide"
) {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [...]
    point3f[] points = [...]
}

# Valid: Mesh with default purpose
def Mesh "Cube" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [...]
    point3f[] points = [...]
}
```

## How to comply
Add at least one imageable geometry prim (Mesh, Cube, Sphere etc.) with purpose "render" or "default".

## For More Information
- [UsdGeom Documentation](https://openusd.org/release/api/usd_geom_page_front.html)
- [USD Purpose Documentation](https://openusd.org/release/api/class_usd_geom_imageable.html#a7a3c451ea53d1b4c6d3f56c28c1cd4b3) 
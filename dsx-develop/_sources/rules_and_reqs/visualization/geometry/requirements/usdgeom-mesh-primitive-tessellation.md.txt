# usdgeom-mesh-primitive-tessellation

| Code     | VG.017 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Avoid tessellating primitive shapes

## Description

Simple shapes that are available as native USD primitives (such as Spheres, Cylinders, etc.) should use those primitive types rather than mesh tessellation when possible. Native primitives provide better memory efficiency and rendering quality when varying primvars/UVs/Texture Coordinates are not needed.

## Why is it required?
- Unnecessary memory usage
- Potential loss of geometric precision
- Larger file sizes
- Slower load times

## Examples

```usd
# Not recommended: Tessellated sphere
def Mesh "TessellatedSphere" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4, ...]  # Many faces
    int[] faceVertexIndices = [...]
    point3f[] points = [...]  # Many vertices approximating a sphere
}

# Recommended: Native USD primitive
def Sphere "PerfectSphere" {
    double radius = 0.5
    double height = 2
    point3f[] extent = [(-0.5, -1, -0.5), (0.5, 1, 0.5)]
}
```

## How to comply
- Replace tessellated geometry with native USD primitives where possible
- Only use mesh tessellation when required for UV mapping or deformation
- Re-export from source application using primitive types


## For More Information
- [UsdGeom Primitives Documentation](https://openusd.org/release/api/usd_geom_page_front.html#UsdGeom_Primitives)
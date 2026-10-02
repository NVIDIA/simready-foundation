# usdgeom-boundable-size

| Code     | VG.005 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`RTX`  |
| Tags     | {tag}`performance` |

## Summary

Meshes should maintain appropriate scale and boundary volumes

## Description

Meshes should maintain appropriate scale and boundary volumes for efficient raytracing and rendering. The boundary volume of a mesh should be sized appropriately for its purpose and visual requirements. Large meshes with significant bounding box overlap of other meshes slow down raytracing performance significantly.

## Why is it required?
- Slow raytracing performance
- Inefficient BVH traversal
- Reduced rendering performance
- Memory inefficiency

## Examples

```usd
#usda 1.0
(
    metersPerUnit = 1.0
)

# Not recommended: Excessively large mesh
def Mesh "mesh_0"
{
    # 84km mesh. Precision will also be limited to > 1cm
    float3[] extent = [(-42000, -42000, -42000), (42000, 42000, 42000)]
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [0, 1, 3, 2, 4, 5, 7, 6, 6, 7, 2, 3, 5, 4, 1, 0, 5, 0, 2, 7, 1, 4, 6, 3]
    point3f[] points = [(42000, -42000, 42000), (-42000, -42000, 42000), (42000, 42000, 42000), (-42000, 42000, 42000), (-42000, -42000, -42000), (42000, -42000, -42000), (-42000, 42000, -42000), (42000, 42000, -42000)]
}
```

## How to comply
- Split into multiple smaller meshes
- Reduce boundary volume where possible
- Fix in source application and re-convert

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)


# usdgeom-mesh-tessellation-density

| Code     | VG.013 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Use appropriate tessellation density for geometry

## Description

Meshes should use appropriate tessellation density for their visual requirements. The tessellation density should balance visual fidelity with performance and memory usage.

## Why is it required?
- High memory usage
- Slower rendering performance
- Increased file size

## Examples

```usd
# Not recommended: Excessive tessellation for a simple shape
def Mesh "OverTessellatedPlane" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4]  # 10 quads for flat surface
    int[] faceVertexIndices = [...]  # Many vertices for a simple shape
    point3f[] points = [...]
}

# Recommended: Efficient tessellation
def Mesh "OptimizedPlane" {
    int[] faceVertexCounts = [4]  # Single quad for flat surface
    int[] faceVertexIndices = [0, 1, 2, 3]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
}
```

## How to comply
- Re-tessellate with adjusted density settings
- Use decimation tools to reduce polygon count
- Convert to USD with optimized tessellation parameters
- Scene Optimizer - Decimate Mesh

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
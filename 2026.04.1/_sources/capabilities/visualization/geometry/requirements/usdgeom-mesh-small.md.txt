# usdgeom-mesh-small

| Code     | VG.012 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Combine small meshes into larger ones where appropriate

## Description

Optimize scene performance by combining small meshes into larger ones where appropriate. Fewer, larger meshes often perform better than many small ones.

## Why is it required?
- Higher memory overhead
- Slower scene loading
- Reduced rendering performance

## Examples

```usd
# Not recommended: Many tiny separate meshes
def Xform "TinyMeshes" {
    def Mesh "SmallCube_1" {
        float3[] extent = [(-0.001, -0.001, -0.001), (0.001, 0.001, 0.001)]
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, ...]
        point3f[] points = [(-0.001, -0.001, -0.001), ...]
    }
    
    def Mesh "SmallCube_2" {
        float3[] extent = [(-0.001, -0.001, 0.002), (0.001, 0.001, 0.004)]
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, ...]
        point3f[] points = [(-0.001, -0.001, 0.002), ...]
    }
}

# Recommended: Combined into efficient single mesh
def Mesh "CombinedMesh" {
    float3[] extent = [(-0.001, -0.001, -0.001), (0.001, 0.001, 0.004)]
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, ...]
    point3f[] points = [(-0.001, -0.001, -0.001), ...]
}
```

## How to comply
- Combine small meshes into larger ones
- Review mesh generation settings
- Scene Optimizer - Merge Static Meshes

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
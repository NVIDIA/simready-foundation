# usdgeom-mesh-empty-spaces

| Code     | VG.004 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`RTX`  |
| Tags     | {tag}`performance` |

## Summary

Use efficient mesh boundaries for performance

## Description

Mesh bounding volume hierarchies (BVH) should be as compact as possible for optimal raytracing performance. Meshes should be organized to minimize empty space in their bounding volumes.

## Why is it required?
- Slow raytracing performance
- Inefficient BVH structure
- Reduced simulation performance

## Examples

```usd
# Not recommended: Inefficient mesh organization
def Mesh "InefficientMesh" {
    # A single mesh containing two cubes far apart
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [
        0, 1, 2, 3,    # Cube 1 faces
        4, 5, 6, 7,
        ...
        24, 25, 26, 27  # Cube 2 faces far away
    ]
    point3f[] points = [
        # Cube 1 points
        (0,0,0), (1,0,0), (1,1,0), (0,1,0),
        ...
        # Cube 2 points with large gap
        (99999990,0,0), (99999991,0,0), (99999991,1,0), (99999990,1,0)
    ]
}

# Recommended: Efficient mesh organization
def Xform "OptimizedGeometry" {
    def Mesh "Cube1" {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, ...]
        point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
    }
    def Mesh "Cube2" {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, ...]
        point3f[] points = [(10,0,0), (11,0,0), (11,1,0), (10,1,0), ...]
    }
}
```

## How to comply
- Split large meshes into multiple smaller ones
- Group geometry by spatial proximity
- Use Scene Optimizer - Split/Merge tool

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
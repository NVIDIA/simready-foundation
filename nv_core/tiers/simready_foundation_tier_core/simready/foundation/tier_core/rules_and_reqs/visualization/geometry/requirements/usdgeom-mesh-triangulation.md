# usdgeom-mesh-triangulation

| Code     | VG.021 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` {tag}`correctness` |

## Summary

Meshes must be triangulated for optimal rendering performance and compatibility when considering automatic collider creation (convex-hull, convex-decomposition, etc...). Triangulating mesh will provide predictable results versus n-gons.

## Description

All mesh geometry should be triangulated to ensure consistent rendering behavior across different renderers and to optimize performance. Non-triangulated meshes (quads, n-gons) may cause rendering artifacts, inconsistent behavior, or performance degradation in certain rendering engines.

A mesh is considered properly triangulated when all faces in `faceVertexCounts` have exactly 3 vertices, and the corresponding `faceVertexIndices` are grouped in sets of 3.


## Examples

```usd
#usda 1.0

# Invalid: Non-triangulated mesh with quads
def Mesh "QuadMesh" {
    uniform token subdivisionScheme = "none"
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]  # Quads
    int[] faceVertexIndices = [
        0, 1, 2, 3,    # Quad face
        4, 5, 6, 7,    # Quad face
        8, 9, 10, 11,  # Quad face
        12, 13, 14, 15, # Quad face
        16, 17, 18, 19, # Quad face
        20, 21, 22, 23  # Quad face
    ]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
}

# Valid: Properly triangulated mesh
def Mesh "TriangulatedMesh" {
    uniform token subdivisionScheme = "none"
    int[] faceVertexCounts = [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]  # All triangles
    int[] faceVertexIndices = [
        0, 1, 2,    # Triangle 1
        0, 2, 3,    # Triangle 2
        4, 5, 6,    # Triangle 3
        4, 6, 7,    # Triangle 4
        8, 9, 10,   # Triangle 5
        8, 10, 11,  # Triangle 6
        12, 13, 14, # Triangle 7
        12, 14, 15, # Triangle 8
        16, 17, 18, # Triangle 9
        16, 18, 19, # Triangle 10
        20, 21, 22, # Triangle 11
        20, 22, 23  # Triangle 12
    ]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
}
```

## How to comply

- **Triangulate in Source Application**: Use your 3D modeling software's triangulation tools
- **USD Tools**: Use `usdmesh` or similar USD utilities to triangulate existing meshes

## For more information

- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)

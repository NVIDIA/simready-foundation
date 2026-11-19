# usdgeom-mesh-manifold

| Code     | VG.007 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vg-007` |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |

## Summary

Mesh geometry must be manifold

## Description

Mesh geometry must maintain manifold topology to ensure proper simulation and rendering behavior. Non-manifold issues include:

- Non-manifold vertices: Vertices are repeated in the geometry
- Non-manifold edges: Edges are repeated multiple times  
- Inconsistent winding: Polygon winding appears inconsistent

## Why is it required?
- Memory usage inefficiency
- Visual artifacts
- Simulation instability

## Examples

```usd
# Invalid: Non-manifold edge
def Mesh "BadMesh" {
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, 3, 2, 4, 5]  # Edge 2-3 used twice
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), (1,2,0), (0,2,0)]
}

# Valid: Manifold mesh
def Mesh "GoodMesh" {
    int[] faceVertexCounts = [4]
    int[] faceVertexIndices = [0, 1, 2, 3]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
}
```

## How to comply
- Use mesh repair tools to weld edges and vertices
- Fill holes in geometry
- Align face normals
- Reconvert to USD after repair
- Scene Optimizer - Remesher


## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html) 
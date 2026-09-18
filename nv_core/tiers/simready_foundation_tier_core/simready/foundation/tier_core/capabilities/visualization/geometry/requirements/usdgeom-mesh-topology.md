# usdgeom-mesh-topology

| Code     | VG.014 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vg-014` |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |

## Summary

Mesh topology must be valid

## Description

Mesh topology must be valid for proper rendering and simulation. Invalid topology includes incorrect face winding, degenerate faces, and invalid vertex indices.

## Why is it required?

- Ensures clean rendering without artifacts
- Improves simulation behavior
- Enables accurate collision detection

## Examples

### Invalid: Degenerate faces and invalid indices

```usd
#usda 1.0

def Mesh "BadTopology" {
    int[] faceVertexCounts = [4, 3]
    int[] faceVertexIndices = [
        0, 0, 0, 0,  # Degenerate face (all vertices same)
        0, 1, 99     # Invalid index (99 > number of points)
    ]
    point3f[] points = [(0,0,0), (1,0,0)]
}
```

### Valid: Proper topology

```usd
#usda 1.0

def Mesh "GoodTopology" {
    int[] faceVertexCounts = [4, 3]
    int[] faceVertexIndices = [
        0, 1, 2, 3,  # Proper quad
        0, 1, 2      # Proper triangle
    ]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
}
```

## How to comply
- Fix topology in source application
- Verify vertex indices
- Check face winding order

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html) 
# usdgeom-mesh-zero-area

| Code     | VG.019 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vg-019` |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Faces should have non-zero area. 

Faces where all vertices are co-linear or coincident waste memory and can cause rendering artifacts.

## Why is it required?

- Memory inefficiency
- Rendering artifacts
- Physics simulation issues

## Examples

```usd
#usda 1.0

# Invalid: Zero area faces
def Mesh "MeshWithZeroAreaFaces" {
    int[] faceVertexCounts = [4, 3]
    int[] faceVertexIndices = [
        0, 0, 1, 1,  # Zero area quad (two points repeated)
        2, 2, 2      # Zero area triangle (same point three times)
    ]
    point3f[] points = [
        (0,0,0),
        (1,0,0),
        (2,0,0)
    ]
}

# Valid: All faces have area
def Mesh "CleanMesh" {
    int[] faceVertexCounts = [4]
    int[] faceVertexIndices = [0, 1, 2, 3]
    point3f[] points = [
        (0,0,0),
        (1,0,0),
        (1,1,0),
        (0,1,0)
    ]
}
```

## How to comply
- Merge co-linear points
- Remove zero area faces
- Fix mesh generation settings

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html) 
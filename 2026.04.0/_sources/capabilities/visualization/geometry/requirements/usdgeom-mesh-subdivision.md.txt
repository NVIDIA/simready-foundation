# usdgeom-mesh-subdivision

| Code     | VG.010 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vg-010` |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Use subdivision only when needed for smooth surfaces or displacement

## Description

Subdivision should be used selectively to create smooth surfaces or enable displacement. Using subdivision on flat surfaces or when not needed for visual quality Why is it required?s performance without benefit.

## Why is it required?
- Increased computation time
- Higher memory usage
- Slower scene loading
- Reduced rendering performance

## Examples

```usd
#usda 1.0

# Invalid: Unnecessary subdivision on simple shape
def Mesh "OverSubdividedCube" {
    uniform token subdivisionScheme = "catmullClark"
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, ...]
    normal3f[] normals = [(0,0,1), (0,0,1), (0,0,1), (0,0,1), ...] # Meshes that have normals should not have subdivision attributes
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
}

# Valid: No subdivision for simple shape
def Mesh "SimpleCube" {
    uniform token subdivisionScheme = "none"
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, ...]
    normal3f[] normals = [(0,0,1), (0,0,1), (0,0,1), (0,0,1), ...]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
}
```

## How to comply
- Remove unnecessary subdivision attributes
- Fix in source application

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html) 
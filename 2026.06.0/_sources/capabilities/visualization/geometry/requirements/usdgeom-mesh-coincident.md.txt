# usdgeom-mesh-coincident

| Code     | VG.008 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Meshes should not share the exact same space

## Description

Each mesh should occupy its own unique space to ensure proper rendering and physics simulation. When multiple meshes need to share the same visual space, consider using visibility attributes so that only one mesh is visible at a time.

## Why is it required?
- Visual artifacts (z-fighting)
- Physics simulation issues
- Raytracing performance Why is it required?
- Increased memory usage

## Examples

```usd
# Not recommended: Coincident meshes
def Xform "CoincidentPlanes" {
    def Mesh "Plane1" {
        float3[] extent = [(-1, 0, -1), (1, 0, 1)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
    }
    
    def Mesh "Plane2" {
        # Exactly same position as Plane1
        float3[] extent = [(-1, 0, -1), (1, 0, 1)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
    }
}

# Valid: Meshes with proper spacing
def Xform "ProperlySpacedMeshes" {
    def Mesh "Plane1" {
        float3[] extent = [(-1, 0, -1), (1, 0, 1)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
    }
    
    def Mesh "Plane2" {
        # Offset in Y axis
        xformOp:translate = (0, 1, 0)
        token xformOpOrder = ["translate"]

        # Visibility is off
        hidden = true

        float3[] extent = [(-1, 0, -1), (1, 0, 1)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
    }
}
```

## How to comply
- Check for accidental duplicates
- Ensure proper spacing between meshes
- Review transform hierarchies
- Set coincident meshes to be hidden
- Fix in source application and re-convert

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
# identical-mesh-consistency

| Code     | VG.024 |
|----------|-----------|
| Validator| {manual-validation}`manual-validation-required` |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |

## Summary

Repeated occurrences of identically shaped objects should have identical mesh connectivity

## Description

When identically shaped and parameterized objects appear multiple times in an asset, all occurrences should have identical mesh connectivity - point positions and connections / edges between the vertices. This enables proper memory de-duplication optimizations and primvar usage (texture coordinates, normals, etc.)

```{figure} /_static/images/identical-meshes.jpg

The locks on this toolbox are identical and should have identical mesh connectivity.
```


## Why is it required?

- Enables efficient memory de-duplication of identical meshes
- Ensures consistent behavior across different instances of the same mesh, for example when applying a textured material or applying mesh decimation operations
- Reduces file size and memory usage

**Performance Impact Example:**

Consider a .usdc file containing 100 identical screw meshes, each with 1000 polygons:

- **Compliant approach** (identical meshes): 1MB
- **Non-compliant approach** (unique meshes with different vertex connectivity): 11MB

This represents an **11x increase** in file size when identical geometry is not properly deduplicated.



## Examples

```usd
#usda 1.0

# Optimal: Identical meshes with same point positions and vertex connectivity
def Mesh "pPlane1"
{
    float3[] extent = [(-0.5, 0, -0.5), (0.5, 0, 0.5)]
    int[] faceVertexCounts = [3, 3]
    int[] faceVertexIndices = [0, 1, 2, 2, 1, 3]
    point3f[] points = [(-0.5, 0, 0.5), (0.5, 0, 0.5), (-0.5, 0, -0.5), (0.5, 0, -0.5)]
}

def Mesh "pPlane2"
{
    float3[] extent = [(-0.5, 0, -0.5), (0.5, 0, 0.5)]
    int[] faceVertexCounts = [3, 3]
    int[] faceVertexIndices = [0, 1, 2, 2, 1, 3]
    point3f[] points = [(-0.5, 0, 0.5), (0.5, 0, 0.5), (-0.5, 0, -0.5), (0.5, 0, -0.5)]
}

# Suboptimal: Identical meshes with same point positions and different vertex connectivity
def Mesh "pPlane1"
{
    float3[] extent = [(-0.5, 0, -0.5), (0.5, 0, 0.5)]
    int[] faceVertexCounts = [3, 3]
    int[] faceVertexIndices = [0, 1, 2, 2, 1, 3]
    point3f[] points = [(-0.5, 0, 0.5), (0.5, 0, 0.5), (-0.5, 0, -0.5), (0.5, 0, -0.5)]
}

def Mesh "pPlane2"
{
    float3[] extent = [(-0.5, 0, -0.5), (0.5, 0, 0.5)]
    int[] faceVertexCounts = [3, 3]
    int[] faceVertexIndices = [0, 1, 3, 0, 3, 2]
    point3f[] points = [(-0.5, 0, 0.5), (0.5, 0, 0.5), (-0.5, 0, -0.5), (0.5, 0, -0.5)]
}

```

## How to comply

- Use Scene Optimizer Fuzzy Deduplicate to deduplicate meshes with identical shape but different connectivity
- When splitting a previously merged mesh into multiple separate meshes, de-duplicate/replace any resulting geometry that should be identical with other geometry. For example bolts and screws or wheels in a vehicle.
- When positioning duplicated geometry, don't do so by moving the points / vertices directly. Instead, apply transformation (xform ops) to the geometry to position it.
- Use identical mesh data for geometrically identical objects
- Consider using USD's instancing capabilities for repeated geometry

## For more information

- [USD Scene Graph Instancing](https://openusd.org/release/glossary.html#usdglossary-scenegraphinstancing)
- [UsdGeomMesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
- [USD Composition Arcs](https://openusd.org/release/glossary.html#usdglossary-compositionarcs)
- [Scene Optimizer Deduplicate Meshes - Fuzzy mode](https://docs.omniverse.nvidia.com/extensions/latest/ext_scene-optimizer/operations.html#de-duplicate-geometry)
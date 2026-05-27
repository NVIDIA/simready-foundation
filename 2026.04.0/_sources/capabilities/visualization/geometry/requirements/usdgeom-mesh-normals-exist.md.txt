# usdgeom-mesh-normals-exist

| Code          | VG.027                              |
|---------------|-------------------------------------|
| Validator     | {oav-validator-latest-link}`vg-027` |
| Compatibility | {compatibility}`Core USD`          |
| Tags          | {tag}`correctness`                 |

## Summary

All non-subdivided meshes must have normals.

## Description

Shading of hard edges and smooth surfaces described by non-subdivided meshes in rendering systems requires surface normals. Normals should be authored with the intention to accurately represent the intended surface appearance (e.g. smooth, hard edge, crease, etc.). When converting from other formats, the normals should be preserved or accurately sampled from the source surface.

Normals can be represented by the "normals" or the "primvars:normals" attributes, but only one of these representations should exist on each mesh to avoid confusion. "primvars:normals" is the preferred representation as it allows for indexing.

## Why is it required?

- Missing normals may lead to unrealistic faceting or soft edges.
- Automatic generation of normals may not accurately represent the intended surface appearance.


````{grid} 1 1 2 2

```{grid-item-card} Incorrect
![normals_incorrect](/_static/images/normals_incorrect.jpg)
```

```{grid-item-card} Correct
![normals_correct](/_static/images/normals_correct.jpg)
```
````

## Examples

### Valid: Soft edge between two faces

```usd
#usda 1.0
(
    metersPerUnit = 1
    upAxis = "Z"
)

def Mesh "soft"
{
    float3[] extent = [(-0.05, -0.05, -0.025), (0.05, 0.05, 0)]
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 3, 4, 1, 1, 4, 5, 2]
    point3f[] points = [(-0.05, 0.05, -0.025), (0, 0.05, 0), (0.05, 0.05, -0.025), (-0.05, -0.05, -0.025), (0, -0.05, 0), (0.05, -0.05, -0.025)]
    normal3f[] primvars:normals = [(-0.447, 0, 0.894), (-0.447, 0, 0.894), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0.447, 0, 0.894), (0.447, 0, 0.894)] (
        interpolation = "faceVarying"
    )
    uniform token subdivisionScheme = "none"
}
```

### Valid: Hard edge between two faces

```usd
#usda 1.0

def Mesh "sharp"
{
    float3[] extent = [(-0.05, -0.05, -0.025), (0.05, 0.05, 0)]
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 3, 4, 1, 1, 4, 5, 2]
    point3f[] points = [(-0.05, 0.05, -0.025), (0, 0.05, 0), (0.05, 0.05, -0.025), (-0.05, -0.05, -0.025), (0, -0.05, 0), (0.05, -0.05, -0.025)]
    normal3f[] primvars:normals = [(-0.447, 0, 0.894), (-0.447, 0, 0.894), (-0.447, 0, 0.894), (-0.447, 0, 0.894), (0.447, 0, 0.894), (0.447, 0, 0.894), (0.447, 0, 0.894), (0.447, 0, 0.894)] (
        interpolation = "faceVarying"
    )
    uniform token subdivisionScheme = "none"
}
```

### Invalid: No normals to define soft or hard edge

```usd
#usda 1.0

def Mesh "none"
{
    float3[] extent = [(-0.05, -0.05, -0.025), (0.05, 0.05, 0)]
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 3, 4, 1, 1, 4, 5, 2]
    point3f[] points = [(-0.05, 0.05, -0.025), (0, 0.05, 0), (0.05, 0.05, -0.025), (-0.05, -0.05, -0.025), (0, -0.05, 0), (0.05, -0.05, -0.025)]
    uniform token subdivisionScheme = "none"
}
```

### Invalid: Both `normals` and `primvars:normals` exist

```usd
#usda 1.0

def Mesh "both"
{
    float3[] extent = [(-0.05, -0.05, -0.025), (0.05, 0.05, 0)]
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 3, 4, 1, 1, 4, 5, 2]
    point3f[] points = [(-0.05, 0.05, -0.025), (0, 0.05, 0), (0.05, 0.05, -0.025), (-0.05, -0.05, -0.025), (0, -0.05, 0), (0.05, -0.05, -0.025)]
    normal3f[] normals = [(-0.447, 0, 0.894), (-0.447, 0, 0.894), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0.447, 0, 0.894), (0.447, 0, 0.894)] (
        interpolation = "faceVarying"
    )
    point3f[] points = [(-0.05, 0.05, -0.025), (0, 0.05, 0), (0.05, 0.05, -0.025), (-0.05, -0.05, -0.025), (0, -0.05, 0), (0.05, -0.05, -0.025)]
    normal3f[] primvars:normals = [(-0.447, 0, 0.894), (0, 0, 1), (0.447, 0, 0.894)] (
        interpolation = "faceVarying"
    )
    int[] primvars:normals:indices = [0, 0, 1, 1, 1, 1, 2, 2]
    uniform token subdivisionScheme = "none"
}
```

### Valid: Only `primvars:normals` exists

```usd
#usda 1.0

def Mesh "only"
{
    float3[] extent = [(-0.05, -0.05, -0.025), (0.05, 0.05, 0)]
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 3, 4, 1, 1, 4, 5, 2]
    point3f[] points = [(-0.05, 0.05, -0.025), (0, 0.05, 0), (0.05, 0.05, -0.025), (-0.05, -0.05, -0.025), (0, -0.05, 0), (0.05, -0.05, -0.025)]
    normal3f[] primvars:normals = [(-0.447, 0, 0.894), (0, 0, 1), (0.447, 0, 0.894)] (
        interpolation = "faceVarying"
    )
    int[] primvars:normals:indices = [0, 0, 1, 1, 1, 1, 2, 2]
    uniform token subdivisionScheme = "none"
}
```

# How to comply

- Author normals on all mesh geometry intended for visualization.
- Author normals that accurately represent the intended surface appearance.
- Remove `normals` if both `normals` and `primvars:normals` exist on a mesh.

# For More Information

- [USD Normals Documentation](https://openusd.org/dev/api/class_usd_geom_point_based.html#ac9a057e1f221d9a20b99887f35f84480)
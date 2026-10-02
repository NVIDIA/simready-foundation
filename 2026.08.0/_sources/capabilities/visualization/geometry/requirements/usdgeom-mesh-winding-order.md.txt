# usdgeom-mesh-winding-order

| Code     | VG.029 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |

## Summary

The winding order of faces in a mesh must correctly represent the orientation (front/back) of the face.

## Description

In order to correctly represent the orientation (front/back) of a face, the winding order of faces in a mesh must be correct. In OpenUSD, the winding order is defined by the `faceVertexIndices` array of a mesh and is running in counter-clockwise (CCW) order.

## Why is it required?

Visualization, culling and other algorithms rely on correct winding order to determine the front/back sides of a mesh. For example, when calculating shadows. Surface normals, which are used primarily for shading, should be consistent with the winding order to avoid potential artifacts.

## Examples

### Invalid: Inconsistent winding order

```{figure} /_static/images/winding_order.jpg

Visual artifacts when the winding order is incorrect in Storm.
```

```usd
# Invalid: Cube with flipped winding order for the top face
#usda 1.0
(
    metersPerUnit = 1.0
    upAxis = "Z"
)

def Xform "World"
{
    def Mesh "Cube"
    {
        point3f[] points = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]

        # Indices for each quad face, CCW by default
        # Let's flip the winding order for the top face (face 5)
        int[] faceVertexIndices = [
            0, 1, 2, 3,      # Bottom (-Z)
            3, 2, 6, 7,      # Front (+Y)
            2, 1, 5, 6,      # Right (+X)
            1, 0, 4, 5,      # Back (-Y)
            0, 3, 7, 4,      # Left (-X)
            4, 7, 6, 5       # Top (+Z) -- FLIPPED WINDING
        ]
    }
}

```

# mesh-xform-positioning

| Code     | VG.023 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |

## Summary

Meshes should be positioned with xform ops rather than by "baking" transformations into point positions.

## Description

Transformations should be applied through USD's transformation stack (xform ops) rather than being baked into the mesh point positions. This maintains flexibility for transformation operations and enables memory de-duplication in serialized layers (USD crate) as well as the renderer.

## Why is it required?

- Preserves mesh data integrity and reusability
- Allows for proper transformation manipulation in applications
- Enables efficient memory de-duplication of identical meshes
- Maintains separation between geometry and transformation data

```{note}
In OpenUSD, gPrims (such as Meshes, Curves, Xforms, etc.) are all transformable. It is not required to use an explicit Xform prim to apply transformations to a mesh.

In some cases / workflows there might be a conventional choice to use an explicit Xform prim to apply transformations to a mesh. This is not a technical requirement and may lead to performance overheads (see "Leverage transformable gprims" [here](https://openusd.org/release/maxperf.html)).
```


## Examples

```usd
#usda 1.0

def Xform "MyObject" (
) {
    # Recommended: Mesh positioned using xform ops
    def Mesh "Geometry" {
        float3 xformOp:translate = (5, 0, 0)
        float3 xformOp:rotateXYZ = (0, 45, 0)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]


        point3f[] points = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
        # Mesh points are in local space, transformations applied via xform ops
    }

    # Not Recommended: Transformation baked into mesh points
    def Mesh "BadGeometry" {
        point3f[] points = [(2.54, 0, -2.54), (7.54, 0, -2.54), (7.54, 0, 2.54), (2.54, 0, 2.54)]
        # Mesh points have transformation baked in, making reuse difficult
    }
}
```

## How to comply

- Keep mesh points in local coordinate space
- Apply transformations using xform ops on xformable prims (xforms, meshes, cubes, etc.)
- Use UsdGeomXformCommonAPI for consistent transformation handling
- Avoid pre-transforming mesh vertices during asset creation
- Separate geometry data from transformation data in the USD hierarchy

## For more information

- [USD Transform Operations](https://openusd.org/release/api/class_usd_geom_xformable.html)
- [UsdGeomMesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
- [Maximizing USD Performance](https://openusd.org/release/maxperf.html)
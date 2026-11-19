# root is xformable

| Code     | HI.003 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`essential` |

## Summary

The root prim of a hierarchy must be transformable, meaning its' prim type must inherit from UsdGeomXformable and be capable of receiving transform operations.

## Description

This requirement ensures that the root prim of any hierarchy is transformable, allowing the entire hierarchy to be manipulated through standard USD transform operations. The root prim must inherit from UsdGeomXformable, which provides the necessary schema for applying transforms such as translation, rotation, and scaling.

A transformable root is essential for:

- Enabling the entire hierarchy to be positioned, oriented, and scaled as a unit
- Supporting animation and keyframe-based transformations
- Allowing proper integration with scene graphs and transform systems
- Ensuring compatibility with USD's transform evaluation pipeline

## Why is it required?

- Enables the entire hierarchy to be transformed as a cohesive unit
- Provides a single point of control for positioning and orienting the asset
- Ensures compatibility with USD's transform evaluation system
- Supports animation workflows and keyframe-based transformations
- Maintains consistency with USD's transformable prim expectations

## Examples

```usd
# Valid: Root is an Xform prim (naturally transformable)
def Xform "RootXform"
{
    double3 xformOp:translate = (0, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    
    def Xform "ChildXform" {}
}

# Valid (but not recommended): Root is a SphereLight prim (contains UsdGeomXformable)
def SphereLight "RootLight"
{
    double3 xformOp:translate = (0, 0, 0)
    double3 xformOp:rotateXYZ = (0, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
    
    def Xform "ChildXform" {}
}

# Invalid: Root is a Material prim (not transformable)
def Material "RootMaterial"
{
    def Mesh "ChildMesh" {}  # This violates the requirement
}

# Invalid: Root is a Shader prim (not transformable)
def Shader "RootShader"
{
    def Xform "ChildXform" {}  # This violates the requirement
}
```

## How to comply

- Ensure the root prim contains UsdGeomXformable
- Use prim types that naturally contain UsdGeomXformable (Xform, Mesh, Sphere, Cube, etc.)
- Avoid using non-transformable prims (Material, Shader, etc.) as the root
- Verify that the root prim can receive transform operations
- Test that the entire hierarchy can be transformed through standard USD operations

## Exceptions to watch out for

- **Nested Gprims**: Geometric primitives (Gprims) such as Mesh, Sphere, Cube, Cylinder, etc. cannot be nested within other Gprims. For example, a Mesh cannot have a Sphere as a child, and a Sphere cannot have a Cube as a child. Use Xform prims as intermediate nodes when you need to group multiple Gprims together.
- **Non-transformable prims**: Prims like Material, Shader, and other non-geometric types cannot serve as transformable roots or be part of a transformable hierarchy.

## For More Information

- [USD Transform Operations](https://openusd.org/release/api/class_usd_geom_xformable.html)
- [USD Prim Types](https://openusd.org/release/api/class_usd_prim.html)
- [USD Stage Traversal](https://openusd.org/release/api/class_usd_stage.html)
- [USD No Nesting GPrims](https://openusd.org/release/glossary.html#usdglossary-gprim)

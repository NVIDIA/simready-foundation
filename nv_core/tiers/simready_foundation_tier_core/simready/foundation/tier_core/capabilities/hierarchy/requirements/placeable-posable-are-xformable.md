# placeable-posable-are-xformable

| Code     | HI.006 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`essential` |
| Version | 0.1.0      |

## Summary

All prims representing distinct objects or groups that require placement, posing or animation shall inherit from UsdGeomXformable.

## Description

This requirement ensures that any prim in the USD scene graph that represents a distinct object or group and requires spatial transformation capabilities (placement, posing, or animation) must inherit from the UsdGeomXformable schema.

UsdGeomXformable provides the fundamental transformation capabilities needed for:
- Positioning objects in 3D space
- Rotating and orienting objects
- Scaling objects
- Animating transformations over time
- Supporting hierarchical transformations

Without inheriting from UsdGeomXformable, prims cannot be properly transformed, positioned, or animated in the scene.

## Why is it required?

- Enables proper positioning, posing, and animation of objects
- Ensures compatibility with USD's transform evaluation pipeline
- Provides consistent transformation capabilities across all transformable prims
- Supports animation workflows and keyframe-based transformations
- Maintains consistency with USD's transformable prim expectations

## Examples

```usd
# Valid: Mesh prim inherits UsdGeomXformable
def Mesh "TransformableMesh"
{
    double3 xformOp:translate = (0, 0, 0)
    double3 xformOp:rotateXYZ = (0, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
}

# Valid: Xform prim inherits UsdGeomXformable
def Xform "TransformableXform"
{
    double3 xformOp:translate = (1, 2, 3)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    
    def Mesh "ChildMesh" {}  # Also inherits UsdGeomXformable
}

# Valid: Light prim inherits UsdGeomXformable
def SphereLight "TransformableLight"
{
    double3 xformOp:translate = (0, 5, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
}

# Invalid: Material prim does not inherit UsdGeomXformable
def Material "NonTransformableMaterial"
{
    # Cannot be positioned, posed, or animated
}
```

## How to comply

- Ensure all prims that need transformation capabilities inherit from UsdGeomXformable
- Use prim types that naturally inherit UsdGeomXformable (Xform, Mesh, Sphere, Cube, Lights, etc.)
- Avoid using non-transformable prims (Material, Shader, etc.) for objects that need placement or animation
- Verify that transformation operations can be applied to the prims
- Test that animation of transformations is supported

## Exceptions to watch out for

- **Non-transformable prims**: Prims like Material, Shader, and other non-geometric types cannot be transformed and should not be used for objects requiring placement or animation
- **Reference prims**: When referencing other assets, ensure the referenced prims also inherit from UsdGeomXformable if they need transformation capabilities

## For More Information

- [USD Transform Operations](https://openusd.org/release/api/class_usd_geom_xformable.html)
- [USD Prim Types](https://openusd.org/release/api/class_usd_prim.html)
- [USD Stage Traversal](https://openusd.org/release/api/class_usd_stage.html)

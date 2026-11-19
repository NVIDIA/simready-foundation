# exclusive-xform-parent-for-usdgeom

| Code     | HI.002 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`essential` |

## Summary

Every UsdGeomGprim must have a parent Xform with specific transform operations and hierarchy constraints.

## Description

This requirement enforces a strict hierarchy structure for UsdGeomGprims:

1. Every UsdGeomGprim must have a parent Xform
2. The parent Xform must have at least:
   - One xformOp:translate
   - One xformOp:rotateXYZ
   - (xformOp:scale is optional)
3. The parent Xform can only have one UsdGeomGprim as its child
4. If a referencePrim/xform has an authored reference, the hierarchy of the reference must also comply with these requirements


## Examples

```usd
# Invalid: UsdGeomGprim without proper Xform parent
#usda 1.0
def Cube "MyCube"  # Missing Xform parent
{
    double size = 1.0
}

# Invalid: Xform with multiple UsdGeomGprim children
def Xform "Parent"
{
    def Cube "Cube1" {}
    def Sphere "Sphere1" {}  # Multiple UsdGeomGprim children
}

# Valid: Proper hierarchy with single UsdGeomGprim child
def Xform "Parent"
{
    double3 xformOp:translate = (0, 0, 0)
    float3 xformOp:rotateXYZ = (0, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
    
    def Cube "MyCube"
    {
        double size = 1.0
    }
}
```

## How to comply

- Ensure every UsdGeomGprim has a parent Xform
- Include required transform operations (translate and rotate) on parent Xform
- Maintain single UsdGeomGprim child per Xform parent
- Verify referenced content follows the same hierarchy rules

## For More Information

- [USD Transform Operations](https://openusd.org/release/api/class_usd_geom_xformable.html)
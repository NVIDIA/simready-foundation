# xform-common-api-usage

| Code     | HI.005 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |

## Summary

Transformations (translate, rotate, scale, pivot) on prims that are intended to be translated, rotated or scaled by users (e.g. the root prim of an asset) should conform to the UsdGeomXformCommonAPI.

## Description

UsdGeomXformCommonAPI provides a standardized interface for authoring common transformation operations. Developers are encouraged to avoid direct manipulation of the xformOpOrder and individual xformOp attributes unless advanced control is explicitly required.

For prims that are not intended to be translated, rotated or scaled by users, the fallback is to use:

1. UsdGeomXformCommonAPI (e.g. ["xformOp:translate", "xformOp:translate:pivot", "xformOp:rotateXYZ", "xformOp:scale", "!invert!xformOp:translate:pivot"])
2. Transform Matrix (e.g. ["xformOp:transform"])
3. Translate + Quaternion (e.g. ["xformOp:translate", "xformOp:orient"])

## Why is it required?

- Ensures consistent transformation interpretation across applications
- Simplifies asset manipulation workflows
- Reduces complexity in transformation handling
- Improves interoperability between different USD tools

## Examples

```usd
#usda 1.0

# Recommended: Using UsdGeomXformCommonAPI
def Xform "MyAsset" ()
{
    float3 xformOp:translate = (0.0, 0.0, 0.0)
    float3 xformOp:rotateXYZ = (0.0, 0.0, 0.0)
    float3 xformOp:scale = (1.0, 1.0, 1.0)
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]
    
    def Scope "Geometry" {
        def Xform "Door" {
            float3 xformOp:translate = (0.0, 0.0, 0.0)
            float3 xformOp:rotateXYZ = (0.0, 0.0, 45.0)
            float3 xformOp:scale = (1.0, 1.0, 1.0)
            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]
        }
    }
}


# Not recommended: Direct manipulation of xformOp attributes without UsdGeomXformCommonAPI
def Xform "MyAsset"
{
    matrix4d xformOp:transform = ((1, 0, 0, 1), (0, 1, 0, 0), (0, 0, 1, 2), (0, 0, 0, 1))
    uniform token[] xformOpOrder = ["xformOp:transform"]
    
    def Mesh "Geometry" {
        # Asset geometry
    }
}
```

## How to comply

- Use the UsdGeomXformCommonAPI to author transformations on prims that are intended to be translated, rotated or scaled by users (e.g. the root prim of an asset)
- Use the standard translate, rotate, scale, pivot and inverse pivot attributes provided by the API
- Avoid direct manipulation of xformOpOrder unless advanced control is needed

## For more information

- [UsdGeomXformCommonAPI Documentation](https://openusd.org/release/api/class_usd_geom_xform_common_a_p_i.html)
- [USD Transform Operations](https://openusd.org/release/api/class_usd_geom_xformable.html) 
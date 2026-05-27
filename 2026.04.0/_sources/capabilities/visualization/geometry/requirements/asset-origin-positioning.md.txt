# asset-origin-positioning

| Code     | VG.025 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`essential` |


## Summary

Geometry shall be defined as such that the asset is correctly positioned and oriented at the origin (0,0,0).

## Description

Assets should be authored with their local transformation setup so that when referenced into a scene at a particular location, the asset appears at that location as intended. This ensures predictable behavior when aggregating assets in larger scenes.
This requirement establishes specific guidelines for common object types:

- **Objects placed on the ground plane**: Objects that sit on a surface should have their origin at the center of their base
- **Rotating and hinged objects**: Objects designed to rotate around a specific point should have their origin at that rotation center
- **Attached objects**: Objects which are intended to be attached to other objects should have their origin at (one of) their intended attachment points


## Why is it required?

- Ensures predictable asset placement in aggregate scenes
- Simplifies asset referencing workflows
- Provides consistent baseline for transformation operations
- Facilitates automated scene composition and layout tools

## Examples

### Valid: Asset positioned correctly at origin

```usd
#usda 1.0

def Xform "Table_Valid" ()
{
    float3 xformOp:translate = (0, 0, 0)
    float3 xformOp:rotateXYZ = (0, 0, 0)
    float3 xformOp:scale = (1, 1, 1)
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]

    def Cube "TableTop" {
        float3 xformOp:translate = (0, 0, 0.6)
        float3 xformOp:scale = (1, 1, 0.2)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
}
```

### Invalid: Asset with non-identity default transforms

```usd
#usda 1.0

def Xform "Table_Invalid" (
)
{
    float3 xformOp:translate = (0, 0, 0.6)  # Asset offset from origin by default
    uniform token[] xformOpOrder = ["xformOp:translate"]

    def Cube "TableTop" {
        float3 xformOp:scale = (1, 1, 0.2)
        uniform token[] xformOpOrder = ["xformOp:scale"]
    }
}
```

## How to comply

- Position assets at the origin (0,0,0) in their local space
- Set default rotation to (0,0,0) for neutral orientation
- Set default scale to (1,1,1) for unit scale
- Use transformation operations for instance-specific positioning when referencing into scenes
- Test assets by referencing them into a scene at the origin to verify correct placement
- Test assets by verifying that their bounding box is overlapping or touching the origin (0,0,0)

## For more information

- [USD Scene Composition](https://openusd.org/release/glossary.html#usdglossary-scenegraphinstancing)
- [UsdGeomXformCommonAPI Documentation](https://openusd.org/release/api/class_usd_geom_xform_common_a_p_i.html) 
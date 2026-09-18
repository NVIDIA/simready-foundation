# logical-pivot-positioning

| Code     | VG.026 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |


## Summary

The pivot point of an asset should be positioned logically: at the center of the object's base for ground plane objects, and at the center of rotation for objects that rotate around specific points.

## Description

Asset pivot points should be positioned to enable intuitive transformation behavior based on the object's real-world function and placement. This requirement establishes specific guidelines for common object types:

- **Ground plane objects**: Objects that sit on a surface should have their pivot at the center of their base
- **Rotating objects**: Objects designed to rotate around a specific point should have their pivot at that rotation center
- **Hinged objects**: Doors, lids, and similar objects should have pivots at their hinge points

Proper pivot placement ensures predictable behavior when positioning, rotating, and scaling assets in scenes.

## Why is it required?

- Enables intuitive manipulation of assets in 3D applications
- Provides predictable transformation behavior for different object types
- Supports realistic animation and simulation workflows
- Facilitates automated placement and layout tools
- Ensures consistent user experience across different assets

## Examples

```usd
#usda 1.0

# Valid: Table with pivot at center of base
def Xform "Table" ()
{
    float3 xformOp:translate = (0, 0, 0)
    float3 xformOp:pivot = (0, 0, 0)  # Pivot at base center - table sits correctly on ground
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:pivot", "!invert!xformOp:pivot"]
    
    def Cube "TableTop" {
        float3 xformOp:translate = (0, 0.4, 0)  # Table surface above pivot
        float3 xformOp:scale = (2, 0.1, 1)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
    
    def Cube "TableLeg" {
        float3 xformOp:translate = (0, 0.2, 0)  # Leg extends from pivot upward
        float3 xformOp:scale = (0.1, 0.4, 0.1)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
}

# Valid: Door with pivot at hinge point
def Xform "Door" ()
{
    float3 xformOp:translate = (0, 0, 0)
    float3 xformOp:rotateXYZ = (0, 0, 0)  # Door rotation around hinge
    float3 xformOp:pivot = (0, 0, 0)  # Pivot at hinge location
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:pivot", "xformOp:rotateXYZ", "!invert!xformOp:pivot"]
    
    def Cube "DoorPanel" {
        float3 xformOp:translate = (0.5, 1, 0)  # Door panel offset from hinge
        float3 xformOp:scale = (1, 2, 0.05)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
}

# Valid: Ceiling fan with pivot at rotation center
def Xform "CeilingFan" ()
{
    float3 xformOp:translate = (0, 2.5, 0)  # Fan mounted on ceiling
    float3 xformOp:rotateXYZ = (0, 0, 0)  # Fan blade rotation
    float3 xformOp:pivot = (0, 0, 0)  # Pivot at motor center
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:pivot", "xformOp:rotateXYZ", "!invert!xformOp:pivot"]
    
    def Cube "FanBlade" {
        float3 xformOp:translate = (0.5, 0, 0)  # Blade extends from center
        float3 xformOp:scale = (1, 0.02, 0.1)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
}

# Invalid: Chair with pivot at arbitrary location
def Xform "Chair_Invalid" ()
{
    float3 xformOp:translate = (0, 0, 0)
    float3 xformOp:pivot = (0, 1, 0)  # Pivot in mid-air above chair
    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:pivot", "!invert!xformOp:pivot"]
    
    def Cube "ChairSeat" {
        float3 xformOp:translate = (0, -0.5, 0)  # Chair appears to float when placed
        float3 xformOp:scale = (1, 0.1, 1)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
}
```

## How to comply

### For Ground Plane Objects:

- Position pivot at the center of the object's base (bottom surface)
- Ensure the object sits correctly on a ground plane when pivot is at Y=0
- Examples: chairs, tables, lamps, trees, buildings

### For Rotating Objects:

- Position pivot at the mechanical center of rotation
- Align pivot with the axis around which the object naturally rotates
- Examples: doors (at hinge), wheels (at axle), ceiling fans (at motor)

### For General Objects:

- Consider the object's primary function and typical manipulation
- Place pivot where users would intuitively expect the transformation center
- Test by rotating the object to ensure natural behavior

## For more information

- [UsdGeomXformCommonAPI Documentation](https://openusd.org/release/api/class_usd_geom_xform_common_a_p_i.html)
- [USD Transform Operations](https://openusd.org/release/api/class_usd_geom_xformable.html)
- [USD Transformations Tutorial](https://openusd.org/dev/tut_xforms.html)
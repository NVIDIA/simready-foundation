# gripper-max-opening

| Code     | GR.004 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every gripper site prim must declare a `custom:maxOpening` float attribute with a positive value (in meters) recording the maximum jaw separation.

## Description

`custom:maxOpening` stores the maximum distance between the gripper fingertips when fully open, in meters. This is a kinematic property — the physical travel limit of the gripper joints — and is distinct from the `grip_line` segment length, which encodes the width of the grip pads (finger contact surface area).

Grasp planning algorithms consume this value to determine whether the gripper can physically open wide enough to fit around a given object before attempting a grasp.

> **Note:** The `custom:` prefix indicates this attribute is not yet part of a registered USD schema. A future `GraspAPI` schema is anticipated to formalize this attribute.

## Why is it required?

- Grasp planners need the max opening to filter candidate grasps by object width.
- Without it the gripper site does not provide sufficient information for autonomous grasping.
- Expressed in meters for consistency with `metersPerUnit = 1` USD convention.

## Examples

```usd
# Invalid: maxOpening not authored
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
}

# Invalid: maxOpening is zero or negative
def Xform "gripper_01"
{
    float custom:maxOpening = 0    # invalid — must be > 0
}

# Valid: 85 mm jaw opening (Robotiq 2F-85)
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    float custom:maxOpening = 0.085

    def BasisCurves "forward_axis"
    {
        point3f[] points = [(0, -0.15, 0), (0, 0.15, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }

    def BasisCurves "grip_line"
    {
        point3f[] points = [(-0.04, 0, 0), (0.04, 0, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }
}
```

## How to comply

- Author `custom:maxOpening` as a `float` attribute on the gripper site prim.
- Set the value to the physical maximum jaw separation in **meters**.
- Ensure the value is strictly positive (`> 0`).
- The value must be greater than or equal to the `grip_line` segment length.

## Related Requirements

- [gripper-site-naming](gripper-site-naming.md)
- [gripper-grip-line](gripper-grip-line.md)

## For More Information

- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)

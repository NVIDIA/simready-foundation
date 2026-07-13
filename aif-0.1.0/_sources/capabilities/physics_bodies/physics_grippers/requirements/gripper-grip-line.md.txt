# gripper-grip-line

| Code     | GR.003 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every gripper site prim must contain a child `BasisCurves` prim named `grip_line` with at least 2 points defining the axis of the imaginary tube the gripper can grasp.

## Description

The `grip_line` curve is a linear `BasisCurves` prim that encodes the axis of an imaginary tube running through the graspable region — the direction along which a cylindrical or elongated object would be oriented when held by the gripper.

The three axes of a gripper site are mutually orthogonal:
- `forward_axis` — approach direction (gripper moves toward object along this axis)
- `grip_line` — axis of the graspable tube (perpendicular to finger motion)
- Grip motion — direction the finger pads move when opening/closing (implied third axis, perpendicular to both)

The `grip_line` is **not** the jaw closure direction — it is perpendicular to it. The length of the segment (`|p1 - p0|`) encodes the physical width of the grip pads along the tube axis, representing how much of the object the pads can contact.

This definition generalizes to hand grippers and multi-finger grippers, not just parallel-jaw grippers.

## Why is it required?

- Defines the axis of the graspable tube so planners can align cylindrical or elongated objects correctly.
- Segment length (`|p1 - p0|`) is the grip pad width — the extent of the finger contact surfaces along the tube axis.
- Together with `forward_axis`, the three orthogonal axes (forward, grip_line, grip motion) fully define the grasp frame.
- A visual representation aids authoring and debugging in any USD viewer.

## Examples

```usd
# Invalid: gripper site without grip_line
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
    # Missing grip_line — invalid
}

# Valid
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
        point3f[] points = [(-0.2, 0, 0), (0.2, 0, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }
}
```

## How to comply

1. Add a child prim named exactly `grip_line` under the gripper site prim.
2. Set the prim type to `BasisCurves`.
3. Author at least 2 points spanning the jaw closure axis, centered at the local origin.
4. Set `curveVertexCounts = [2]` and `type = "linear"`.
5. Orient the segment perpendicular to `forward_axis` and size it so that `|p1 - p0|` equals the physical width of the grip pads.

## Related Requirements

- [gripper-site-naming](gripper-site-naming.md)
- [gripper-forward-axis](gripper-forward-axis.md)
- [gripper-max-opening](gripper-max-opening.md)

## For More Information

- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)

# gripper-grip-line

| Code     | GR.003 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every gripper site prim must contain a child `BasisCurves` prim named `gripper_grip_line` with at least 2 points defining the axis of the imaginary tube the gripper can grasp.

## Description

The `gripper_grip_line` curve is a linear `BasisCurves` prim that encodes the axis of an imaginary tube running through the graspable region — the direction along which a cylindrical or elongated object would be oriented when held by the gripper.

The unprefixed child name `grip_line` is also accepted for existing assets.
New assets should use `gripper_grip_line`. When both are present the
`gripper_`-prefixed name wins.

The intended roles of the three axes are:
- `gripper_forward_axis` — approach direction (gripper moves toward object along this axis)
- `gripper_grip_line` — axis of the graspable tube (typically perpendicular to finger motion)
- Grip motion — direction the finger pads move when opening/closing (implied third
  axis, typically `gripper_forward_axis × gripper_grip_line`)

Keeping `gripper_forward_axis` and `gripper_grip_line` mutually orthogonal is
**suggested** so planners can derive a stable closure axis from their cross
product. It is not validated: GR.003 only requires a `BasisCurves` child with
at least 2 points. Nearly parallel curves still pass static validation;
consumers may fall back when the cross product degenerates.

The `gripper_grip_line` is **not** the jaw closure direction — it is typically
perpendicular to it. The length of the segment (`|p1 - p0|`) encodes the
physical width of the grip pads along the tube axis, representing how much of
the object the pads can contact.

This definition generalizes to hand grippers and multi-finger grippers, not just parallel-jaw grippers.

## Why is it required?

- Defines the axis of the graspable tube so planners can align cylindrical or elongated objects correctly.
- Segment length (`|p1 - p0|`) is the grip pad width — the extent of the finger contact surfaces along the tube axis.
- Together with `gripper_forward_axis`, the axes (forward, grip_line, grip motion)
  describe the grasp frame; orthogonal authoring is suggested but not required.
- A visual representation aids authoring and debugging in any USD viewer.

## Examples

```usd
# Invalid: gripper site without gripper_grip_line
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    float gripper_maxOpening = 0.085

    def BasisCurves "gripper_forward_axis"
    {
        point3f[] points = [(0, -0.15, 0), (0, 0.15, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }
    # Missing gripper_grip_line — invalid
}

# Valid
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    float gripper_maxOpening = 0.085

    def BasisCurves "gripper_forward_axis"
    {
        point3f[] points = [(0, -0.15, 0), (0, 0.15, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }

    def BasisCurves "gripper_grip_line"
    {
        point3f[] points = [(-0.2, 0, 0), (0.2, 0, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }
}
```

## How to comply

1. Add a child prim named `gripper_grip_line` under the gripper site prim
   (the unprefixed name `grip_line` is accepted for existing assets).
2. Set the prim type to `BasisCurves`.
3. Author at least 2 points spanning the jaw closure axis, centered at the local origin.
4. Set `curveVertexCounts = [2]` and `type = "linear"`.
5. Suggested: orient the segment perpendicular to `gripper_forward_axis` and size
   it so that `|p1 - p0|` equals the physical width of the grip pads.
   Orthogonality is not checked by the validator.

## Related Requirements

- [gripper-socket-type](gripper-socket-type.md)
- [gripper-forward-axis](gripper-forward-axis.md)
- [gripper-max-opening](gripper-max-opening.md)

## For More Information

- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)

# gripper-forward-axis

| Code     | GR.002 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every gripper site prim must contain a child `BasisCurves` prim named `forward_axis` with at least 2 points defining the gripper approach direction.

## Description

The `forward_axis` curve is a linear `BasisCurves` prim that encodes the direction from which the gripper approaches the object. The direction vector is computed as `p1 - p0` (from first point to second point).

The curve is used in preference to `IsaacSiteAPI`'s `forwardAxis` token attribute because:
- The approach direction may be non-axis-aligned in local space
- Negative axis directions cannot be expressed by the token enum (`"X"`, `"Y"`, `"Z"` only)
- The curve provides an unambiguous, visually verifiable representation in any USD editor

## Why is it required?

- Robot motion planners need the approach vector to compute pre-grasp poses.
- Without a forward axis the gripper cannot be oriented correctly during approach.
- A visual BasisCurves representation aids authoring and debugging in any USD viewer.

## Examples

```usd
# Invalid: gripper site without forward_axis child
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    float custom:maxOpening = 0.085

    def BasisCurves "grip_line"
    {
        point3f[] points = [(-0.2, 0, 0), (0.2, 0, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }
    # Missing forward_axis — invalid
}

# Valid: approach along local +Y
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

# Valid: non-axis-aligned approach direction
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    float custom:maxOpening = 0.085

    def BasisCurves "forward_axis"
    {
        point3f[] points = [(0, 0, 0), (0.1, 0.2, 0.05)]
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

1. Add a child prim named exactly `forward_axis` under the gripper site prim.
2. Set the prim type to `BasisCurves`.
3. Author at least 2 points that define the approach direction vector (`direction = p1 - p0`).
4. Set `curveVertexCounts = [2]` and `type = "linear"`.

## Related Requirements

- [gripper-site-naming](gripper-site-naming.md)
- [gripper-grip-line](gripper-grip-line.md)

## For More Information

- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)

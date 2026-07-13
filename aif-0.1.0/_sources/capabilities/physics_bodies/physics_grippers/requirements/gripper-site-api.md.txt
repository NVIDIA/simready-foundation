# gripper-site-api

| Code     | GR.ISA.001 |
|----------|------------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`Isaac` |
| Tags     | {tag}`essential` |

## Summary

Every gripper site prim must have `IsaacSiteAPI` applied and `isaac:Description` authored so Isaac Sim tooling can discover and configure it automatically.

## Description

In the Isaac Format, gripper site prims are discovered by Isaac Sim via `IsaacSiteAPI` in addition to the `gripper_*` naming convention required by the Neutral Format. Each such prim must carry `IsaacSiteAPI` and a non-empty `isaac:Description` string.

Without `IsaacSiteAPI` the prim is not visible to Isaac Sim's gripper discovery pipeline and site-dependent runtime features (Robot Poser, IK visualization, state reporting) will not function.

## Why is it required?

- Isaac Sim gripper control relies on `IsaacSiteAPI` to locate gripper sites at runtime.
- `isaac:Description` communicates the semantic role of the site to downstream systems.
- Consistent schema application allows tooling to enumerate all gripper interaction points.

## Examples

```usd
# Invalid: missing IsaacSiteAPI (Neutral format only — not valid for Isaac format)
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

# Valid: Isaac Format — IsaacSiteAPI applied
def Xform "gripper_01" (
    prepend apiSchemas = ["IsaacSiteAPI"]
)
{
    string isaac:Description = "Grasp approach point"
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

1. Apply `IsaacSiteAPI` via `prepend apiSchemas = ["IsaacSiteAPI"]` on every `gripper_*` prim.
2. Author a non-empty `string isaac:Description` attribute describing the site's role.

## Related Requirements

- [gripper-site-naming](gripper-site-naming.md) (Neutral, GR.001)
- [gripper-forward-axis](gripper-forward-axis.md) (Neutral, GR.002)
- [gripper-grip-line](gripper-grip-line.md) (Neutral, GR.003)
- [gripper-max-opening](gripper-max-opening.md) (Neutral, GR.004)

## For More Information

- [Isaac Sim Robot Schema](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/omniverse_usd/robot_schema.html)

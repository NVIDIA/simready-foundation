# mate-insertion-vector

| Code     | MC.005 |
|----------|--------|
| Validator| MateInsertionVectorChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

If a mate site has a child `mate_insertion_vector`, it must be a `BasisCurves` prim with `type = "linear"`, `curveVertexCounts = [2]`, and a non-zero direction `p1 - p0`.

## Description

The insertion vector is optional. It describes the trajectory taken to reach the seated mate frame, which may be perpendicular to the mate axis.

When the child is **absent**, insertion defaults to the socket's `-Z`. That default is normative: consumers must not invent a different fallback.

When both socket and plug author a vector, the socket wins and a validator should warn (not fail). Multi-segment paths are unspecified.

Shape matches `GR.002` so gripper-axis parsers can reuse the same curve read. `purpose = "guide"` is recommended so the curve stays out of render captures.

## Why is it required?

- A malformed optional curve would be worse than no curve: consumers would disagree on the approach.

## Examples

```usd
# Invalid: not two points
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"

    def BasisCurves "mate_insertion_vector"
    {
        point3f[] points = [(0, 0, 0)]
        int[] curveVertexCounts = [1]
        uniform token type = "linear"
    }
}

# Valid: omit the child entirely (axial insertion along socket -Z)
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"
}

# Valid: lateral then seat
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"

    def BasisCurves "mate_insertion_vector"
    {
        point3f[] points = [(0, 0, 0), (0.04, 0, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
        uniform token purpose = "guide"
    }
}
```

## How to comply

1. Omit `mate_insertion_vector` unless the approach is not along socket `-Z`.
2. If authored, use a two-point linear `BasisCurves` child named `mate_insertion_vector` with non-zero `p1 - p0`.

## Related Requirements

- [gripper-forward-axis](../../../physics_bodies/physics_grippers/requirements/gripper-forward-axis.md) (`GR.002`)

## For More Information

- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)

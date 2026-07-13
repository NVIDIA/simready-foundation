# Physics Grippers

This capability defines structured gripper interaction points on end-effector robot assets.

## Summary

Gripper sites encode the approach direction, graspable-tube axis, and maximum jaw separation needed by grasp planning and robot control systems. Two compliance levels are defined: Neutral (plain OpenUSD, discovery via `simready:attactment:socketType = "Gripper"` attribute) and Isaac (superset of Neutral, adds `IsaacSiteAPI` for Isaac Sim runtime discovery).

## Schema / OpenUSD Specification

Gripper sites use core USD geometry and, optionally, the Isaac Sim site schema.

- [UsdGeomXform](https://openusd.org/dev/api/class_usd_geom_xform.html)
- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)
- [IsaacSiteAPI](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/omniverse_usd/robot_schema.html)

## Implementation

{doc}`Full Requirements List <requirements>`

```{toctree}
:maxdepth: 1
:hidden:

requirements
```

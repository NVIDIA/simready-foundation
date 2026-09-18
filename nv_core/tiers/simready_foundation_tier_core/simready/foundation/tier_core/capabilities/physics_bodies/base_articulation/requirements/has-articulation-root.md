# Has Articulation Root

| Code     | BA.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

An articulated USD stage must contain exactly one prim with the
UsdPhysicsArticulationRootAPI applied.

## Why
The ArticulationRootAPI is required for proper articulation simulation in physics. Without the articulation root, the physics engine will make assumptions with the robot articulations. More than one articulation root on a single asset is ambiguous and is also rejected.

```{note}
Scope: this check only runs when the stage contains at least one `UsdPhysicsJoint`.
Rigid-body-only stages (vehicles, non-articulated props) are exempt because they are
not expected to carry an articulation root. When joints are present, the check fails
both when **no** articulation root exists and when **more than one** exists.
```

## How to comply

- Apply `PhysicsArticulationRootAPI` to the root prim of the articulation hierarchy.
- Ensure only one ArticulationRootAPI exists per articulated asset.
- The ArticulationRootAPI should be applied to the prim that serves as the base of the kinematic chain.

## Example

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
    # Other properties ...
}
```
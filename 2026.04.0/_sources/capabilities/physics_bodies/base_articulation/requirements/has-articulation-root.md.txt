# Has Articulation Root

| Code     | BA.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The USD stage must contain at least one prim with the
UsdPhysicsArticulationRootAPI applied. 

## Why
The ArticulationRootAPI is required for proper articulation simulation in physics. Without the articulation root, the physics engine will make assumptions with the robot articulations.

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
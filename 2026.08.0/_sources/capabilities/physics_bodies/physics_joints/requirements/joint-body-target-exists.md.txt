# joint-body-target-exists

| Code     | JT.002 |
|----------|---------|
| Validator| {oav-validator-latest-link}`jt-002` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Targets set to Body0 and Body1 relationships must exist.

## Description

UsdPhysicsJoint and its subtypes define two relationships: **Body0** and **Body1**. Both relationships must target prims that exist in the stage or remain empty.

## Why is it required?

* If either relationship targets a prim that doesn't exist in the stage, the joint cannot function properly during simulation.

## Examples

```usd
# Invalid: Joint prim's target does not exist in the stage
def PhysicsFixedJoint "FixedJoint"
{
   rel physics:body1 = </Cube>
}

# Valid: Joint prim's target exists in the stage
def Cube "Cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def PhysicsFixedJoint "FixedJoint"
{
   rel physics:body1 = </Cube>
}
```

## How to comply

Set Body0 and Body1 targets to existing prims in the stage or leave them empty.

## For More Information

* [Joint Bodies](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_jointed_bodies)


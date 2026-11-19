# joint-no-multiple-body-targets

| Code     | JT.003 |
|----------|---------|
| Validator| {oav-validator-latest-link}`jt-003` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Body0 and Body1 relationships must not have more than one target.

## Description

UsdPhysicsJoint and its subtypes define two relationships: **Body0** and **Body1**. Both relationships can target at most one prim.

## Why is it required?

* If either relationship targets more prims the target used for simulation is undefined.

## Examples

```usd
# Invalid: One of the Body relationships have more than one target
def PhysicsFixedJoint "FixedJoint"
{
   rel physics:body1 = [</Cube0>, </Cube1>]
}

# Valid: Both relationships have at most one target
def PhysicsFixedJoint "FixedJoint"
{
   rel physics:body0 = </Cube0>
   rel physics:body1 = </Cube1>
}
```

## How to comply

Set Body0 and Body1 targets to at most one prim per relationship.

## For More Information

* [Joint Bodies](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_jointed_bodies)

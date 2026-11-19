# articulation-not-on-static-body

| Code     | JT.ART.004 |
|----------|---------|
| Validator| {oav-validator-latest-link}`jt-art-004` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Articulations are not allowed on static bodies.

## Description

Articulations are only allowed on enabled rigid bodies.

## Why is it required?

* Articulations require bodies that can be dynamically simulated to function properly

## Examples

```usd
# Invalid: UsdPhysicsArticulationRootAPI applied to a static body
def Cube "Cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsArticulationRootAPI"]
) {
   bool physics:rigidBodyEnabled = 0
}

# Valid: UsdPhysicsArticulationRootAPI applied to an enabled rigid body (the Enabled attribute has a default of True)
def Cube "Cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsArticulationRootAPI"]
) {
}
```

## How to comply

Set the Enabled attribute of a UsdPhysicsRigidBodyAPI to True.

## For More Information

* [Articulations Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_articulations)
* [UsdPhysicsArticulationRootAPI Documentation](https://openusd.org/dev/api/class_usd_physics_articulation_root_a_p_i.html)
* [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)

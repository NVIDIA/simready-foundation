# rigid-body-schema-application

| Code     | RB.003 |
|----------|---------|
| Validator| {oav-validator-latest-link}`rb-003` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Rigid bodies have to be UsdGeomXformable prims.

## Description

The UsdPhysicsRigidBodyAPI has to be applied to any **UsdGeomXformable prim** so that the xformOps can be authored when simulation steps.

## Why is it required?

- Assets with UsdPhysicsRigidBodyAPI define a rigid body for the simulator. Prims with this API will have their xformOp attributes updated after each simulation step.

## Examples

```usd
# Invalid: UsdPhysicsRigidBodyAPI applied to a Scope
def Scope "scope" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {
}

# Valid: Rigid body and collision on UsdGeomXformable
def Cube "cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
) {
}
```

## How to comply

UsdPhysicsRigidBodyAPI must be applied to a UsdGeomXformable.

## For More Information

- [UsdPhysics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)
- [UsdGeomXformable Documentation](https://openusd.org/dev/api/class_usd_geom_xformable.html)

# rigid-body-multibody-capability

| Code     | RB.MB.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Assets must contain at least two rigid bodies

## Description

If an asset is expected to simulate multiple bodies, the **UsdPhysicsRigidBodyAPI must be applied** to at least two UsdGeomXformable prim representing separate rigid body hierarchies.

## Why is it required?

- Multiple bodies simulating separately within one asset necessarily requires multiple bodies defined in the asset.

## Examples

```usd
# Valid: Two separate rigid bodies with collision on UsdGeomGPrims
def Cube1 "cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
) {
}
def Cube2 "cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
) {
}

```

## How to comply

The **UsdPhysicsRigidBodyAPI** schema must be applied to at least two UsdGeomXformables with separate prim hierarchies.

## For More Information

- [UsdPhysics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)

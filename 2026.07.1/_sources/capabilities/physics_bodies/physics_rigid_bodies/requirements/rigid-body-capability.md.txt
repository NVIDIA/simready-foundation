# rigid-body-capability

| Code     | RB.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Assets must contain at least one rigid body

## Description

If an asset is simulated and the movement is expected to be driven by physics, the **UsdPhysicsRigidBodyAPI must be applied** to any UsdGeomXformable prim represents a rigid body hierarchy.

## Why is it required?

- Assets with UsdPhysicsRigidBodyAPI applied define a rigid body for the simulator. Prims with this API will have their xformOp attributes updated after each simulation step.

## Examples

```usd
# Invalid: Just Collision on UsdGeomGPrim that should move
def Cube "cube" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
}

# Valid: Rigid body and collision on UsdGeomGPrim
def Cube "cube" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
) {
}
```

## How to comply

The **UsdPhysicsRigidBodyAPI** schema must be applied to a UsdGeomXformable that is intended to be dynamically simulated.

## For More Information

- [UsdPhysics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)

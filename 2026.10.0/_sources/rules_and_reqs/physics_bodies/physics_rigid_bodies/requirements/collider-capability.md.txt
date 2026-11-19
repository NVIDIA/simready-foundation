# collider-capability

| Code     | RB.COL.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Colliding Gprims must apply the Collision API.

## Description

UsdPhysics defines collisions through **UsdPhysicsCollisionAPI**. UsdGeomGPrim types that should be part of the collision representation must have UsdPhysicsCollisionAPI.

The Collision API can not be applied to xforms.

## Why is it required?

* Assets with collision API will collide during simulation based on the UsdGeomGPrim geometry definition.
* Assets with collision API define volume hence mass properties can be computed.

## Examples

```usd
# Invalid: Collision on non UsdGeomGPrim
def Xform "xform" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
}

# Valid: Collision on UsdGeomGPrim
def Cube "cube" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
}
```

## How to comply

UsdPhysicsCollisionAPI has to be applied to a UsdGeomGPrim.

## For More Information

* [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
* [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)

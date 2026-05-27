# rigid-body-no-nesting

| Code     | RB.006 |
|----------|---------|
| Validator| {oav-validator-latest-link}`rb-006` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Rigid bodies can not be nested unless xformOp reset xform stack is used.

## Description

Since UsdPhysicsRigidBodyAPI simulation ends up with changes to the world transformation, **it has to be applied to the local transformation stack of the UsdGeomXformable**. If rigid bodies are nested, it requires a defined order in which the schema is applied, and that is an unnecessary complication. To avoid this complication, **if rigid bodies are nested, they must have their xformOp stack reset set.**

## Why is it required?

- Assets with UsdPhysicsRigidBodyAPI define rigid body for the simulator. Prims with this API will have their xformOp attributes updated after each simulation step hence there has to be a clear target where the transformation should end up.

## Examples

```usd
# Invalid: Nested rigid bodies
def Xform "Xform" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
   def Cube "cube" (
      prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
   ) {
   }
}

# Valid: Rigid bodies nested but with xformOp stack reset
def Xform "Xform" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
   def Cube "cube" (
      prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
   ) {
      quatd xformOp:orient = (1, 0, 0, 0)
      double3 xformOp:scale = (1, 1, 1)
      double3 xformOp:translate = (0, 0, 0)
      uniform token[] xformOpOrder = ["!resetXformStack!", "xformOp:translate", "xformOp:orient", "xformOp:scale"]
   }
}
```

## How to comply

The UsdPhysicsRigidBodyAPI cannot be nested unless xformOp resetXformStack is used.

## For More Information

- [UsdPhysics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)
- [UsdGeomXformable Documentation](https://openusd.org/dev/api/class_usd_geom_xformable.html)

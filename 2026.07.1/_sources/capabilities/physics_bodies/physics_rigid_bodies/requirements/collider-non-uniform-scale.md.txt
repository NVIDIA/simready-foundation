# collider-non-uniform-scale

| Code     | RB.COL.004 |
|----------|---------|
| Validator| {oav-validator-latest-link}`rb-col-004` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

The collision shape scale must be uniform for the following geometries: Sphere, Capsule, Cylinder, Cone & Points.

## Description

Simulation does not support scale, hence simple geometries that are algorithmically defined like Sphere, Capsule, Cylinder, Cone **must have their world transform matrix scale uniform** in order to have a proper shape representation of the geometry in the simulation engine.

## Why is it required?

- Assets with non-uniform world scale on the above UsdGeomGPrims won't have correct collision behavior in simulation runtime.

## Examples

```usd
# Invalid: Non-Uniform scale on a Sphere
def Sphere "Sphere" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
   float3 xformOp:scale = (1, 2, 3)
   uniform token[] xformOpOrder = ["xformOp:scale"]   
}

# Valid: Uniform scale on a Sphere
def Sphere "Sphere" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
   float3 xformOp:scale = (2, 2, 2)
   uniform token[] xformOpOrder = ["xformOp:scale"]   
}
```

## How to comply

UsdPhysicsCollisionAPI can only be applied to a UsdGeomGPrim with non-uniform world scale for these types - Mesh & Cube. Other than these exceptions, the scale (world scale) **must** be uniform.

## For More Information

- [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
- [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)

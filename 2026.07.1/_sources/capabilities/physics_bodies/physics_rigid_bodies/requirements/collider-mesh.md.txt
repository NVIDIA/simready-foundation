# collider-mesh

| Code     | RB.COL.003 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

The Mesh Collision API can only be assigned to Mesh Prims.

## Description

**UsdPhysicsMeshCollisionAPI** extends the collision for mesh specific attributes. It does not define the collision itself and UsdPhysicsCollisionAPI is still required to be present. The mesh collision API is *optional* API to define additional parameters like the desired approximation for the mesh.

## Examples

```usd
# Invalid: Mesh collision API on a mesh does not define a collision
def Mesh "mesh" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI"]
) {
}

# Invalid: Mesh collision API on a cube is not valid as it defines only mesh properties
def Cube "cube" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI", "PhysicsCollisionAPI"]
) {
}

# Valid: Mesh collision API together with Collision API define a proper mesh collider
def Mesh "mesh" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI", "PhysicsCollisionAPI"]
) {
}
```

## How to comply

The **UsdPhysicsMeshCollisionAPI** can extend a UsdGeomMesh primitive that already has the UsdPhysicsCollisionAPI schema applied with additional parameters including the desired approximation for the mesh collision.

## For More Information

- [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
- [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)
- [UsdPhysicsMeshCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mesh_collision_a_p_i.html)

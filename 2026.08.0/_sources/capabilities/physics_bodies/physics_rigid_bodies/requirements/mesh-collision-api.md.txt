# mesh-collision-api

| Code     | RB.COL.002 |
|----------|---------|
| Validator| RigidBodyColliderMeshChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

**UsdPhysicsMeshCollisionAPI** may only be applied to **UsdGeom.Mesh** prims, and any prim with MeshCollisionAPI must also have **UsdPhysicsCollisionAPI** applied.

## Description

The validator checks each prim for two conditions:

1. **Mesh type**: If a prim has **UsdPhysicsMeshCollisionAPI**, it must be a **UsdGeom.Mesh**. Applying MeshCollisionAPI to other geometry types (e.g. Cube, Sphere, Xform) is invalid because the API defines mesh-specific collision attributes.

2. **Collision API required**: **UsdPhysicsMeshCollisionAPI** extends collision with mesh-specific options; it does not define the collision itself. Therefore any prim with MeshCollisionAPI must also have **UsdPhysicsCollisionAPI** applied.

Failure messages from the implementation:

- *"Prim '...' has MeshCollisionAPI but is not a UsdGeom Mesh."*
- *"Prim '...' has MeshCollisionAPI but does not have CollisionAPI."*

## Why is it required?

* Mesh collision is defined over mesh geometry; applying MeshCollisionAPI to non-mesh prims is undefined and unsupported.
* CollisionAPI is the base schema that enables collision; MeshCollisionAPI only adds mesh-specific parameters and must be used together with CollisionAPI.

## Examples

```usd
# Invalid: MeshCollisionAPI on a non-mesh prim (e.g. Cube)
def Cube "cube" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI", "PhysicsCollisionAPI"]
) {
}

# Invalid: MeshCollisionAPI without CollisionAPI
def Mesh "mesh" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI"]
) {
}

# Valid: MeshCollisionAPI on a Mesh with CollisionAPI
def Mesh "mesh" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI", "PhysicsCollisionAPI"]
) {
}
```

## How to comply

* Apply **UsdPhysicsMeshCollisionAPI** only to **UsdGeom.Mesh** prims.
* Whenever **UsdPhysicsMeshCollisionAPI** is applied, also apply **UsdPhysicsCollisionAPI** on the same prim.

## For More Information

* [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
* [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)
* [UsdPhysicsMeshCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mesh_collision_a_p_i.html)

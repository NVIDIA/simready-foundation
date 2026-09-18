# physx-collider-mesh

| Code     | PHYSX.COL.002 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`correctness` |

## Summary

MeshCollisionAPI may only be applied to a UsdGeom Mesh or to a prim that has PhysxMeshMergeCollisionAPI. CollisionAPI is required whenever MeshCollisionAPI is applied.

## Description

**UsdPhysicsMeshCollisionAPI** extends collision with mesh-specific attributes (e.g. approximation). It does not define the collision itself; **UsdPhysicsCollisionAPI** must also be present.

Under PhysX, MeshCollisionAPI is valid in two cases: (1) on a **UsdGeom.Mesh** prim, or (2) on a prim that has **PhysxMeshMergeCollisionAPI** (a merge collider that aggregates mesh geometry via its collisionmeshes collection). In both cases CollisionAPI must be applied. This differs from the OpenUSD-only rule (RB.COL.002), which allows MeshCollisionAPI only on a UsdGeom.Mesh.

## Why is it required?

* MeshCollisionAPI defines mesh-specific collision behavior; applying it to a non-mesh, non-merge prim (e.g. a Cube or plain Xform) has no well-defined meaning and can cause incorrect or unsupported behavior.
* CollisionAPI is required to define the collision shape; MeshCollisionAPI only adds mesh parameters.

## Examples

```usd
# Invalid: MeshCollisionAPI on a cube (not a Mesh or merge)
def Cube "cube" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI", "PhysicsCollisionAPI"]
) {
}

# Invalid: MeshCollisionAPI without CollisionAPI
def Mesh "mesh" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI"]
) {
}

# Valid: MeshCollisionAPI on a UsdGeom Mesh with CollisionAPI
def Mesh "mesh" (
   prepend apiSchemas = ["PhysicsMeshCollisionAPI", "PhysicsCollisionAPI"]
) {
}

# Valid: MeshCollisionAPI on Xform with PhysxMeshMergeCollisionAPI and CollisionAPI
def Xform "MergedCollider" (
   prepend apiSchemas = ["PhysicsCollisionAPI", "PhysxMeshMergeCollisionAPI", "PhysicsMeshCollisionAPI"]
) {
    def Mesh "Part" {}
}
```

## How to comply

1. Apply MeshCollisionAPI only to a **UsdGeom.Mesh** or to a prim that has **PhysxMeshMergeCollisionAPI**.
2. Always apply **CollisionAPI** when using MeshCollisionAPI.
3. For merge colliders, ensure the collisionmeshes collection includes at least one Gprim (see PHYSX.COL.001).

## For More Information

* [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
* [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)
* [UsdPhysicsMeshCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mesh_collision_a_p_i.html)
* physx-collider-capability (PHYSX.COL.001) for CollisionAPI and PhysxMeshMergeCollisionAPI rules
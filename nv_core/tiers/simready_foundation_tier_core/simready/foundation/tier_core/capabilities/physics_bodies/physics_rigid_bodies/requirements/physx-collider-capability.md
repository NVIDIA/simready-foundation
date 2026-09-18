# physx-collider-capability

| Code     | PHYSX.COL.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

CollisionAPI may only be applied to a UsdGeom Gprim or to an Xform that has PhysxMeshMergeCollisionAPI and whose collisionmeshes collection includes at least one Gprim.

## Description

PhysX allows CollisionAPI on (1) any UsdGeom Gprim (Mesh, Cube, Sphere, Capsule, etc.), or (2) an Xform that has PhysxMeshMergeCollisionAPI. In the mesh-merge case, the prim does not provide geometry itself; the **collisionmeshes** collection (see `GetCollisionMeshesCollectionAPI()`) defines which prims are merged for collision. That collection uses `collection:collisionmeshes:includes` (and optionally `collection:collisionmeshes:includeRoot`) to specify the roots for gathering geometry; with the default expansion rule, all prims at or below those roots are members. The collection must include at least one UsdGeom Gprim for the collider to be valid.

## Why is it required?

* CollisionAPI on a non-Gprim that is not a valid mesh-merge Xform has no well-defined geometry and would cause incorrect or missing collision behavior.
* For mesh-merge colliders, an empty or non-Gprim-only collection would produce no collision shape.

## Examples

```usd
# Invalid: CollisionAPI on a plain Xform without PhysxMeshMergeCollisionAPI
def Xform "BadCollider" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
    # Not a Gprim and no PhysxMeshMergeCollisionAPI
}

# Valid: CollisionAPI on a Gprim
def Cube "Box" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
}

# Valid: CollisionAPI on Xform with PhysxMeshMergeCollisionAPI and collection including a Gprim
def Xform "MergedCollider" (
   prepend apiSchemas = ["PhysicsCollisionAPI", "PhysxMeshMergeCollisionAPI"]
) {
    def Mesh "Part" {}
    # collisionmeshes collection includes this prim or its descendants so at least one Gprim is present
}
```

## How to comply

1. Apply CollisionAPI only to a prim that is a UsdGeom Gprim, or to an Xform that has PhysxMeshMergeCollisionAPI.
2. For mesh-merge Xforms, ensure the collisionmeshes collection (includes and optionally includeRoot) resolves to at least one Gprim.

## For More Information

* [UsdPhysics Rigid Bodies](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
* [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
* [UsdGeom GPrim](https://openusd.org/dev/api/class_usd_geom_gprim.html)
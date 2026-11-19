# MuJoCo Mesh Collision API

| Code     | MUJOCO.COL.002 |
|----------|----------------|
| Validator| MuJoCoMeshCollisionAPIChecker |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo mesh collision data must use valid `MjcMeshCollisionAPI` and convex-hull mesh collision authoring.

## Description

The official MuJoCo USD schema defines `MjcMeshCollisionAPI` for mesh collider metadata. The MJCF-to-USD converter also writes USD mesh collision geoms with `physics:approximation = "convexHull"` because MuJoCo uses convex hulls for mesh collision.

When mesh collision data is authored for MuJoCo:

- `MjcMeshCollisionAPI` must be authored only on `UsdGeom.Mesh` prims
- `mjc:inertia`, when authored, must be one of `legacy`, `convex`, `exact`, or `shell`
- `mjc:maxhullvert`, when authored, must be an integer greater than or equal to `-1`
- mesh collision shapes that apply both `UsdPhysics.MeshCollisionAPI` and `MjcCollisionAPI` must author `physics:approximation = "convexHull"`

## Why is it required?

* Keeps MuJoCo mesh collider metadata on mesh prims.
* Matches MuJoCo's convex-hull mesh collision behavior.
* Catches invalid mesh inertia and hull settings before MuJoCo import.

## Examples

```usd
def Mesh "collision_mesh" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI", "MjcCollisionAPI"]
)
{
    uniform token physics:approximation = "convexHull"
}

def Mesh "source_mesh" (
    prepend apiSchemas = ["MjcMeshCollisionAPI"]
)
{
    uniform token mjc:inertia = "convex"
    uniform int mjc:maxhullvert = -1
}
```

## How to comply

* Apply `MjcMeshCollisionAPI` only to mesh prims.
* Use the schema-defined `mjc:inertia` tokens.
* Use convex-hull approximation for MuJoCo mesh collision geoms.

## Related requirements

- [mujoco-collider-api](mujoco-collider-api.md)

## For More Information

* [MuJoCo OpenUSD mjcPhysics schema](https://github.com/google-deepmind/mujoco/blob/main/doc/OpenUSD/mjcPhysics.rst)
* [MuJoCo MJCF to USD converter](https://github.com/google-deepmind/mujoco/blob/main/src/experimental/usd/plugins/mjcf/mujoco_to_usd.cc)

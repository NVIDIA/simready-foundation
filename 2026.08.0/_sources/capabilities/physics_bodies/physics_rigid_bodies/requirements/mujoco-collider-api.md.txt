# MuJoCo Collider API

| Code     | MUJOCO.COL.001 |
|----------|----------------|
| Validator| MuJoCoColliderAPIChecker |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo collision shapes must apply `MjcCollisionAPI` on valid USD collision geometry.

## Description

The official MuJoCo USD schema defines `MjcCollisionAPI` as the API for MuJoCo collider data. In a MuJoCo runtime physics layer:

- every active `UsdPhysics.CollisionAPI` collider must apply `MjcCollisionAPI`
- `MjcCollisionAPI` must be authored only on `UsdGeom.Gprim` collision shapes
- a prim with `MjcCollisionAPI` must also apply `UsdPhysics.CollisionAPI`
- authored integer attributes such as `mjc:group`, `mjc:priority`, and `mjc:condim` must be integer values
- authored numeric attributes such as `mjc:solmix`, `mjc:margin`, and `mjc:gap` must be finite and non-negative
- authored contact parameter arrays such as `mjc:solref` and `mjc:solimp` must be numeric arrays

`MjcCollisionAPI` prepends `NewtonCollisionAPI` in the MuJoCo schema, but this feature validates the MuJoCo runtime surface directly instead of asking authors to manually duplicate inherited schema names.

## Why is it required?

* Ensures MuJoCo can identify all collision shapes in the runtime layer.
* Keeps MuJoCo contact parameters on the collider prims that consume them.
* Avoids invalid MuJoCo collision metadata on non-collider prims.

## Examples

```usd
def Cube "collision_box" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "MjcCollisionAPI"]
)
{
    uniform int mjc:group = 0
    uniform int mjc:condim = 3
    uniform double[] mjc:solref = [0.02, 1.0]
    uniform double[] mjc:solimp = [0.9, 0.95, 0.001, 0.5, 2.0]
}
```

## How to comply

* Apply `MjcCollisionAPI` to every active MuJoCo collider.
* Keep `MjcCollisionAPI` on concrete USD geometry collision shapes.
* Author finite MuJoCo contact values when overriding schema defaults.

## Related requirements

- [mujoco-mesh-collision-api](mujoco-mesh-collision-api.md)

## For More Information

* [MuJoCo OpenUSD mjcPhysics schema](https://github.com/google-deepmind/mujoco/blob/main/doc/OpenUSD/mjcPhysics.rst)
* [MuJoCo MJCF to USD converter](https://github.com/google-deepmind/mujoco/blob/main/src/experimental/usd/plugins/mjcf/mujoco_to_usd.cc)

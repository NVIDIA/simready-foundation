# MuJoCo Standard Articulation Root

| Code     | MUJOCO.BA.001 |
|----------|---------------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo articulations must use standard `UsdPhysics.ArticulationRootAPI` and must not author unsupported MuJoCo-specific articulation-root schemas.

## Description

The official MuJoCo USD schema defines MuJoCo scene, collider, mesh-collider, site, joint, actuator, equality, and tendon schemas, but it does not define a `MjcArticulationRootAPI` or `MjcArticulationRoot` prim type. MuJoCo articulation roots therefore remain standard USD physics articulation roots.

For a MuJoCo-ready base articulation:

- the Standard base-articulation feature supplies the required single `UsdPhysics.ArticulationRootAPI`
- no prim may apply `MjcArticulationRootAPI`
- no prim may use the `MjcArticulationRoot` type

## Why is it required?

* Prevents assets from depending on an invented MuJoCo articulation-root schema.
* Keeps MuJoCo robot articulation authoring aligned with official MuJoCo USD.
* Lets MuJoCo-specific joint, actuator, collision, and scene data layer around standard USD articulation topology.

## Examples

```usd
# Valid: standard USD articulation root.
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}

# Invalid: invented MuJoCo articulation-root API.
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI", "MjcArticulationRootAPI"]
)
{
}
```

## How to comply

* Apply `PhysicsArticulationRootAPI` to the single intended articulation root.
* Do not author `MjcArticulationRootAPI`.
* Do not create `MjcArticulationRoot` prims.
* Put MuJoCo runtime data on the supported MuJoCo schemas, such as `MjcSceneAPI`, `MjcJointAPI`, `MjcActuator`, and collider/site APIs.

## Related requirements

- [has-articulation-root](has-articulation-root.md)

## For More Information

* [MuJoCo OpenUSD mjcPhysics schema](https://github.com/google-deepmind/mujoco/blob/main/src/experimental/usd/mjcPhysics/schema.usda)

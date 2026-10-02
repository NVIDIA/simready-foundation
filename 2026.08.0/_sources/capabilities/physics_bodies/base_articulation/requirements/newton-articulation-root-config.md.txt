# Newton Articulation Root Config

| Code     | NEWTON.BA.001 |
|----------|---------------|
| Validator| CheckStage |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

Newton articulation roots must use standard `UsdPhysics.ArticulationRootAPI` and author explicit Newton self-collision configuration.

## Description

Newton imports standard USD articulation roots and resolves `newton:selfCollisionEnabled` on the articulation root prim. For a Newton-ready articulation:

- the stage must contain exactly one prim with `UsdPhysics.ArticulationRootAPI`
- that articulation root must author `newton:selfCollisionEnabled`
- `newton:selfCollisionEnabled` must be a boolean value
- if `NewtonArticulationRootAPI` is applied, it must be applied only to the articulation root prim

This requirement keeps Newton articulation behavior authored in the asset instead of relying on importer defaults.

## Why is it required?

* Makes Newton self-collision behavior explicit and portable with the asset.
* Uses the Newton articulation mapping documented by the Newton USD importer.
* Avoids using PhysX-only articulation attributes as Newton requirements.

## Examples

```usd
# Valid: standard articulation root with explicit Newton self-collision config.
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
    bool newton:selfCollisionEnabled = false
}

# Invalid: Newton self-collision value is not authored.
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

## How to comply

* Apply `PhysicsArticulationRootAPI` to the single intended articulation root.
* Author `bool newton:selfCollisionEnabled` on that same prim.
* Use `true` only when the Newton runtime should enable self-collisions for the articulation.
* Do not author `newton:selfCollisionEnabled` on non-articulation prims.

## Related requirements

- [has-articulation-root](has-articulation-root.md)

## For More Information

* [Newton USD Parsing and Schema Resolver System](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
* [Newton USD Import Source](https://github.com/newton-physics/newton/blob/main/newton/_src/utils/import_usd.py)

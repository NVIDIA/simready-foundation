# runtime-physics-isolation

| Code     | RV.011 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

When a single physics runtime variant is selected, the composed stage must contain only that runtime's physics schemas and attributes plus the runtime-neutral base. Foreign-runtime schemas and conflicting attribute values are not allowed.

## Description

Each declared physics runtime variant (`PhysX`, `Newton`, `MuJoCo`) is validated on the **composed** stage for that selection: the runtime's variant set is `Enabled` and every other physics variant set is `Disabled`. The neutral base (all variants `Disabled`) is validated the same way as a "Standard" selection.

For the selected target runtime, every authored physics-domain schema and attribute on the composed prims is classified by namespace and checked against the runtime isolation policy:

- **Neutral** `UsdPhysics.*` schemas and `physics:*` attributes are always allowed (every runtime layers on top of them).
- The **target runtime's own** schemas/attributes are allowed (and required where the prim role demands it).
- **Foreign-runtime** schemas/attributes (belonging to a different runtime) are a failure.
- Some attributes are neutral by name but runtime-sensitive by value; these are checked by value.

Namespaces: PhysX = schema prefix `Physx`, attribute prefixes `physx*:`; Newton = schema prefix `Newton`, attribute prefix `newton:`; MuJoCo = schema prefix `Mjc`, attribute prefix `mjc:`.

The single documented cross-runtime allowance is inheritance: `MjcCollisionAPI` builds on `NewtonCollisionAPI`, so under a MuJoCo selection the inherited `NewtonCollisionAPI` and its `newton:contact*` attributes are permitted. This inheritance is one-directional; a Newton selection must not carry MuJoCo (`Mjc*` / `mjc:*`) data.

### Value-level rule: `physics:approximation`

- PhysX: any valid PhysX approximation token; when `sdf`, pair with `PhysxSDFMeshCollisionAPI`.
- MuJoCo: must be `convexHull` when `MjcCollisionAPI` and `PhysicsMeshCollisionAPI` are both present (see `MUJOCO.COL.002`).
- Newton: not consumed by Newton; an authored value of `sdf` is a failure. A neutral fallback token is a non-fatal leak (warning).
- Neutral base: unauthored or a neutral OpenUSD token; `sdf` must not appear on the base.

### Severity

- **Failure:** any foreign-runtime schema/attribute for the selected runtime, and any value conflict (for example `physics:approximation = "sdf"` under Newton, or a non-`convexHull` value under MuJoCo).
- **Warning:** a not-consumed but harmless leak (for example a neutral `physics:approximation` token appearing under Newton).

## Why is it required?

- Guarantees that selecting a runtime yields a composed stage the runtime can actually consume.
- Catches cross-runtime pollution that the scaffolding rules (`RV.001`–`RV.009`) do not inspect.
- Protects against composition (LIVRPS) leaks from the base or from other variant sections that a per-layer check would miss.

## Examples

```usd
# Valid: Newton selection composes only Newton + neutral data
def Mesh "collision_mesh" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI", "NewtonCollisionAPI", "NewtonMeshCollisionAPI"]
)
{
    float newton:contactGap = 0
}
```

```usd
# Invalid: Newton selection composes MuJoCo collision data (foreign) ...
def Mesh "collision_mesh" (
    prepend apiSchemas = ["NewtonCollisionAPI", "MjcCollisionAPI", "PhysicsMeshCollisionAPI", "NewtonMeshCollisionAPI"]
)
{
    uniform int mjc:group = 2
    float newton:contactGap = 0
}

# Invalid: Newton selection composes physics:approximation = "sdf" (conflict)
def Mesh "collision_mesh" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI", "NewtonSDFCollisionAPI"]
)
{
    custom token physics:approximation = "sdf"
}
```

## How to comply

- Keep each runtime's data in its own `runnables/physics/<runtime>.usd` payload and keep variant sections empty except the payload arc (see `RV.010`).
- Do not author foreign-runtime schemas/attributes in a runtime payload.
- Author `physics:approximation` only where the runtime consumes it: PhysX (`sdf`/etc.), MuJoCo (`convexHull`); do not author `sdf` under Newton or on the neutral base.
- Keep the neutral base free of any `Physx*`, `Newton*`, or `Mjc*` schemas/attributes.

## Related Requirements

- [runtime-variant-section-purity](runtime-variant-section-purity) (RV.010)
- [physx-runtime-payload](physx-runtime-payload) (RV.002)
- [newton-runtime-payload](newton-runtime-payload) (RV.005)
- [mujoco-runtime-payload](mujoco-runtime-payload) (RV.008)

## For More Information

- Runtime Physics Isolation Matrix: `../runtime-physics-isolation-matrix.md`
- [USD Value Resolution / LIVRPS](https://openusd.org/release/glossary.html#usdglossary-livrpsstrengthordering)

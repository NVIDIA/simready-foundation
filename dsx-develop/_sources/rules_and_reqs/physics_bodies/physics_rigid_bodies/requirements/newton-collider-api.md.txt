# newton-collider-api

| Code     | NEWTON.COL.001 |
|----------|----------------|
| Validator| NewtonColliderAPIChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

Newton colliders must use a valid Newton collision schema.

## Description

For Newton runtime physics, collision prims must identify the Newton collision representation they use:

- `NewtonCollisionAPI` provides shared Newton collision attributes such as `newton:contactMargin` and `newton:contactGap`.
- `NewtonMeshCollisionAPI` identifies a Newton mesh collision representation on a `UsdGeom.Mesh` collider.
- `NewtonSDFCollisionAPI` identifies Newton SDF-backed collision and hydroelastic-contact configuration on a `UsdGeom.Gprim` collider.

For mesh colliders, choose either `NewtonMeshCollisionAPI` or `NewtonSDFCollisionAPI`. Do not apply both to the same prim. `NewtonSDFCollisionAPI` inherits the base Newton collision behavior, so explicitly listing `NewtonCollisionAPI` with SDF is redundant. `NewtonMeshCollisionAPI` may be paired with `NewtonCollisionAPI` when shared Newton collision settings are authored.

## Why is it required?

Newton supports more than one mesh collision representation. Without an explicit Newton collision schema, a composed asset may satisfy generic USDPhysics requirements but leave the Newton runtime to infer or ignore collider-specific behavior. Mixing `NewtonMeshCollisionAPI` and `NewtonSDFCollisionAPI` on the same prim is ambiguous; Newton warns and uses the SDF configuration.

## Examples

```usd
# Invalid: mesh collider has generic mesh collision but no Newton representation
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI"]
)
{
}
```

```usd
# Invalid: both Newton mesh and Newton SDF collision representations on one prim
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["PhysicsMeshCollisionAPI", "NewtonMeshCollisionAPI", "NewtonSDFCollisionAPI"]
)
{
}
```

```usd
# Invalid: NewtonMeshCollisionAPI on a non-mesh prim
def Xform "ColliderRoot" (
    prepend apiSchemas = ["NewtonMeshCollisionAPI"]
)
{
}
```

```usd
# Valid: ordinary Newton mesh collision
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI", "NewtonCollisionAPI", "NewtonMeshCollisionAPI"]
)
{
    float newton:contactGap = 0
}
```

```usd
# Valid: Newton SDF collision
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["NewtonSDFCollisionAPI"]
)
{
    uniform int newton:sdfMaxResolution = 256
}
```

## How to comply

For Newton mesh colliders, apply either `NewtonMeshCollisionAPI` or `NewtonSDFCollisionAPI` on the collider prim. Use `NewtonMeshCollisionAPI` for ordinary Newton mesh collision and `NewtonSDFCollisionAPI` for SDF-backed or hydroelastic collision. Use `NewtonCollisionAPI` for shared Newton collision settings when the chosen representation does not already inherit it.

## For More Information

- [Newton USD parsing documentation](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
- Newton SDF collision examples in `code_samples/newton.md`

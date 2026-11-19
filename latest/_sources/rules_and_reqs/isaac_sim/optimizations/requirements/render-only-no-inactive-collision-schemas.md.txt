# render-only-no-inactive-collision-schemas

| Code     | OPT.003 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`performance` |

## Summary

Renderable prims with no active collision shape must not retain collision API schemas.

## Description

This requirement implements source optimization item `USD-011`, render and
collision separation. A prim is renderable when its composed `purpose` is
`default` or `render`. Its collision schema stack is inactive when
`PhysicsCollisionAPI` is absent or when the composed
`physics:collisionEnabled` value is false.

The check covers the standard collision schemas and the PhysX, Newton, and
MuJoCo collision-extension schemas already used by this repository. An enabled
collider may remain renderable: it serves both render and collision purposes and
is not render-only. The requirement removes inactive collision metadata without
requiring authors to duplicate geometry.

This is a composed-stage condition. Authored-schema counts can differ from the
effective schema list because list operations and composition may add or remove
schemas. The validator reports the effective inactive stack that a consumer sees.

Visual topology may be instanced or combined only when the active collision
representation stays equivalent. That before/after invariant belongs to the
adapter evidence rather than this single-stage validator: active collider
ownership, world transforms, and physics-material bindings must remain
unchanged.

## Examples

```usd
# Fails: this mesh is drawn but its collision stack cannot produce a shape.
def Mesh "render" (
    prepend apiSchemas = [
        "PhysicsCollisionAPI",
        "PhysicsMeshCollisionAPI",
        "PhysxCollisionAPI"
    ]
)
{
    uniform token purpose = "render"
    bool physics:collisionEnabled = false
}
```

```usd
# Passes: render-only geometry carries no collision schema.
def Mesh "render"
{
    uniform token purpose = "render"
}
```

```usd
# Passes: the prim intentionally serves both render and collision purposes.
def Mesh "render_and_collision" (
    prepend apiSchemas = ["PhysicsCollisionAPI"]
)
{
    uniform token purpose = "render"
    bool physics:collisionEnabled = true
}
```

## Why is it required?

- Inactive collision schema stacks add metadata without active collision
  behavior. Runtime shape-slot savings require simulator measurements and
  cannot be inferred from schema counts alone.
- Separating render-only data keeps visual optimization from accidentally
  treating stale collider metadata as an active physics contract.
- Requiring collider equivalence around topology changes prevents a rendering
  optimization from changing contact geometry or material response.

## How to comply

- Run `remove_inactive_render_collision_schemas` on a staged copy to remove the
  inactive stack, then reopen and validate the output.
- If a prim is intentionally both render and collision geometry, keep collision
  enabled and preserve its collider ownership, transform, approximation, and
  physics-material binding.
- Do not enable collision merely to silence this rule.
- When changing instances or combining visual topology, compare active collider
  ownership, world transforms, and physics-material bindings before and after.

# Invisible Collision Mesh Has Purpose Guide

| Code     | RB.010 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Invisible collision meshes must have their purpose attribute set to 'guide' to be properly excluded from rendering.

## Why

When collision meshes are meant to be invisible (used only for physics simulation, not rendering), they should have their `purpose` attribute set to `guide`. This ensures:
- Renderers correctly exclude these meshes from final output
- The collision geometry is clearly marked as non-renderable
- Tools and pipelines can correctly identify physics-only geometry

## How to comply

- Set the `purpose` attribute to `guide` on all collision meshes that should not be rendered.
- Ensure collision-only geometry does not have `purpose` set to `default` or `render`.

## Example

```usd
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["PhysicsCollisionAPI"]
)
{
    uniform token purpose = "guide"
    # Collision mesh geometry...
}
```

```text
Good: Collision mesh with purpose = guide
┌────────────────────────┐
│ Mesh "CollisionMesh"   │
│   purpose = "guide"    │  ← Correctly marked as non-renderable
│   + PhysicsCollisionAPI│
└────────────────────────┘

Bad: Collision mesh with default purpose
┌────────────────────────┐
│ Mesh "CollisionMesh"   │
│   purpose = "default"  │  ← Will be rendered!
│   + PhysicsCollisionAPI│
└────────────────────────┘
```


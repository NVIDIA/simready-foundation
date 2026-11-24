# Render-Collision Separation

| Property | Value |
| --- | --- |
| Capability | `CAP104_RenderCollisionSeparation.Isaac.0-1-0` |
| Owning tier | Isaac |
| Requirement | [`OPT.003`](../rules_and_reqs/isaac_sim/optimizations/requirements/render-only-no-inactive-collision-schemas.md) |
| Dependencies | None |
| Profile | [Asset-Optimization@1.0.0](../profiles/asset-optimization.md) |

## Pass condition

Renderable prims with no enabled collision representation carry no inactive
collision schema stack.

The validator inspects default- and render-purpose prims. It reports known
collision schemas when PhysicsCollisionAPI is absent or collisionEnabled is
false. A prim may intentionally serve both render and collision purposes;
enabled colliders pass this check.

The input is one composed USD stage with a default prim. No original model,
conversion history, or SimReady stamp is needed. An asset with no applicable
content passes. A pass establishes this structural condition for the asset's
selected composition.

## Validate and repair

1. Run `simready-validate --profile Asset-Optimization --version 1.0.0 asset.usd`
   and inspect `OPT.003`.
2. If this check passes, leave the asset unchanged.
3. If it fails, run `remove_inactive_render_collision_schemas` on a staged copy.
4. Save, reopen, and validate again. Report repair blockers with the affected
   prim and missing precondition.

The adapter removes only known inactive collision schema tokens and preserves
unrelated schemas and properties. Active collider ownership, world transforms,
and physics-material bindings must remain unchanged.

Instance-proxy candidates are reported by validation but block automatic repair.
Repair their source prototype through an explicit authoring workflow. The adapter
does not de-instance geometry or enable collision to make the check pass.
It runs between body collapse and visual merge in the full profile.

The callback is independently available from
`simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization`.
The installed `simready.feature_adapters` provider declares this capability as
the adapter's exact output, selected by `Asset-Optimization@1.0.0`.

## Validation evidence

Tests compare authored and effective schemas, inactive schema stacks, and active
collider paths, ownership, transforms, and physics materials. Actual simulator
shape counts require an Isaac/PhysX measurement and are not a validation input.

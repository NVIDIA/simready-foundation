# rigid-body-collider

| Code     | RB.013 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`high-quality` |

## Summary

Enabled rigid bodies must have collision geometry.

## Description

A prim with an **enabled** `UsdPhysicsRigidBodyAPI` must have the `UsdPhysicsCollisionAPI`
applied either on itself or on a descendant prim. Without a collider the body has no shape
for the solver to resolve contacts against, so it will fall through the world and never
collide with anything.

The check only applies when `physics:rigidBodyEnabled` is true; disabled rigid bodies are
skipped. Descendants are traversed with instance proxies included, so a collider authored
inside a referenced/instanced payload still satisfies the requirement.

## Why is it required?

- A rigid body without any collision geometry cannot participate in contact resolution. It
  will pass through other bodies and the ground plane, producing physically meaningless
  simulation results.

## Examples

```usd
# Invalid: enabled rigid body with no collider anywhere in its subtree
def Xform "Body" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {
}

# Valid: collider applied on a descendant mesh
def Xform "Body" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {
   def Mesh "Collision" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
   }
}
```

## How to comply

- Apply `UsdPhysicsCollisionAPI` to the rigid body prim or to at least one descendant Gprim.
- If a body is intentionally shapeless, disable it by setting `physics:rigidBodyEnabled = false`.

## Related Requirements

- [rigid-body-capability](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-capability)
- [collider-capability](/capabilities/physics_bodies/physics_rigid_bodies/requirements/collider-capability)

## For More Information

- [UsdPhysics Collision Shapes Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
- [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)

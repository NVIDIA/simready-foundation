# Authored, not derived, physical properties

| Code | AV.009 |
|---|---|
| Validator | AuthoredPhysicalPropertiesChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`physics` |

## Summary

An asset with a `Collision` variation MUST author its mass, center of mass, and
inertia explicitly with `UsdPhysics.MassAPI`, and those values MUST be identical
across every collider option.

## Description

A `Collision` variation changes collider fidelity, which would otherwise change
the runtime-derived mass, center of mass, and inertia tensor computed from the
collider geometry. To keep bulk dynamics independent of collider fidelity, the
rigid body MUST carry explicitly authored `physics:mass`, `physics:centerOfMass`,
and `physics:diagonalInertia` (via `UsdPhysics.MassAPI`), with finite, physically
valid values (positive mass).

These authored values MUST be invariant across the `Collision` options: because
they are authored on the rigid body outside the switched collider sections
(`AV.004`), a fidelity swap cannot change them. A rigid body that relies on
collider-derived mass, or whose authored mass/center-of-mass/inertia differs
between options, fails.

This rule applies to the body affected by a `Collision` variation. Visual-only
variations do not require authored mass, though they must not change any authored
mass they happen to carry (`AV.007`).

## Why

If mass came from the collider, a user picking a coarser or finer collider would
silently change the asset's weight and inertia, and therefore its dynamics. The
simulation team requires these values to be author-owned so a collider swap is a
fidelity choice, not a physics change.

## Examples

Valid:

```usd
def Xform "RootNode" (
    prepend apiSchemas = ["PhysicsMassAPI", "PhysicsRigidBodyAPI"]
)
{
    float physics:mass = 2.5
    point3f physics:centerOfMass = (0, 0, 0.12)
    float3 physics:diagonalInertia = (0.04, 0.04, 0.02)
}
```

Invalid: a rigid body with a `Collision` variant set but no authored `physics:mass`;
authored mass that differs between the `ConvexHull` and `TriangleMesh` options.

## How to comply

Derive the mass, center of mass, and inertia from the actual asset once and
author them on the rigid body with `UsdPhysics.MassAPI`, outside every collider
variant section. Do not fabricate values to force a pass.

## Related requirements and references

`AV.006` owns the collision envelope that must also stay invariant; `AV.007`
owns the impact-class honesty this supports; `AV.004` owns the isolation that
keeps the authored body outside the switched sections. `RB.*` own rigid-body and
mass schema conventions.

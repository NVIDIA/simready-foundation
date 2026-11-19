# newton-mass-attributes

| Code     | NEWTON.MAS.001 |
|----------|----------------|
| Validator| NewtonMassAttributesChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

`NewtonMassAPI` must be applied on an `Xformable`, and any authored Newton mass attributes must be valid.

## Description

`NewtonMassAPI` extends `PhysicsMassAPI` with Newton-specific mass and inertia controls. It
applies on an `Xformable` (a rigid body or a collision-shape `Gprim`). Base mass, density, and
center of mass stay on `PhysicsMassAPI`; the Newton attributes add a compact inertia override
and implicit mass-integration controls.

When `NewtonMassAPI` is applied:

- the prim must be an `Xformable`
- `newton:inertia`, when authored non-empty, must contain exactly 6 finite elements
  (`[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]`); the diagonal terms `Ixx`, `Iyy`, `Izz` must be
  non-negative. An empty array (the default) means "no opinion" and defers to standard
  `UsdPhysics` mass resolution.
- `newton:massModel`, when authored, must be `solid` or `shell`
- `newton:shellThickness`, when authored, must be finite and greater than `0`, except for the
  sentinel `-inf`, which lets the active solver choose the thickness. It is only meaningful when
  `newton:massModel = "shell"`.

Newton applies schema defaults for unauthored attributes, so this requirement validates authored
values rather than requiring every attribute to be present.

## Why is it required?

`newton:inertia` lets an asset carry the full symmetric inertia tensor directly, avoiding the
eigenvalue decomposition needed by `physics:diagonalInertia` + `physics:principalAxes`. A tensor
with the wrong element count, non-finite terms, or negative diagonal moments is physically
invalid and will destabilize or reject the body. `newton:massModel` / `newton:shellThickness`
control implicit mass integration; an out-of-range thickness or unknown mass model produces
incorrect mass properties.

## Examples

```usd
# Valid: explicit inertia tensor override.
def Xform "Link" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI", "NewtonMassAPI"]
)
{
    float physics:mass = 2.0
    double[] newton:inertia = [0.01, 0.01, 0.005, 0, 0, 0]
}

# Valid: hollow shell mass model on a collision shape.
def Mesh "Shell" (
    prepend apiSchemas = ["PhysicsCollisionAPI", "NewtonMassAPI"]
)
{
    uniform token newton:massModel = "shell"
    float newton:shellThickness = 0.002
}

# Invalid: inertia tensor with the wrong element count.
def Xform "BadLink" (
    prepend apiSchemas = ["NewtonMassAPI"]
)
{
    double[] newton:inertia = [0.01, 0.01, 0.005]
}
```

## How to comply

- Apply `NewtonMassAPI` only on `Xformable` prims that carry the rigid-body or collision data.
- Author `newton:inertia` either empty or as exactly 6 finite elements with non-negative diagonal
  moments.
- Keep `newton:massModel` in `{solid, shell}` and `newton:shellThickness` finite and `> 0` (or the
  `-inf` sentinel) and only meaningful under the `shell` model.

## For More Information

- [Newton USD Schema Definitions (NewtonMassAPI)](https://github.com/newton-physics/newton-usd-schemas)
- [UsdPhysicsMassAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html)

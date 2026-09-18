# newton-material-attributes

| Code     | NEWTON.MAT.001 |
|----------|----------------|
| Validator| NewtonMaterialAttributesChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

`NewtonMaterialAPI` must be applied on a physics `Material` — a `UsdShade.Material` that also carries `PhysicsMaterialAPI`.

## Description

`NewtonMaterialAPI` extends `PhysicsMaterialAPI` with Newton-specific contact and friction
tuning. It applies on a `UsdShade.Material` (the same material bound to colliders via
`material:binding:physics`) and must be applied alongside `PhysicsMaterialAPI`. Base friction
and restitution stay on `PhysicsMaterialAPI` (`physics:staticFriction`,
`physics:dynamicFriction`, `physics:restitution`); the Newton attributes add torsional/rolling
friction and contact response (`newton:torsionalFriction`, `newton:rollingFriction`,
`newton:contactStiffness`, `newton:contactDamping`, `newton:contactFrictionGain`,
`newton:contactAdhesion`).

When `NewtonMaterialAPI` is applied:

- the prim must be a `UsdShade.Material`
- the prim must also carry `PhysicsMaterialAPI`

Consistent with the way foundations treats `UsdPhysicsMaterialAPI` (see
{doc}`collider-material-binding`, `PMT.001`), this requirement validates **schema placement
only**. The `newton:*` attribute values are documented but not policed — the same way
`physics:density`/`physics:staticFriction`/`physics:dynamicFriction`/`physics:restitution`
on `PhysicsMaterialAPI` are trusted rather than validated. Newton applies schema defaults for
unauthored attributes.

## Why is it required?

`NewtonMaterialAPI` extends `PhysicsMaterialAPI`, so it only has meaning on a physics material.
Applying it to a non-material prim, or to a material that does not carry `PhysicsMaterialAPI`,
leaves the Newton runtime without a valid material to configure. Newton reads the material's
attributes to configure contact response (`newton:contactStiffness` -> `ke`,
`newton:contactDamping` -> `kd`, `newton:contactFrictionGain` -> `kf`,
`newton:contactAdhesion` -> `ka`, plus torsional and rolling friction), but the authored values
are the author's responsibility, matching the `physics:*` convention.

## Examples

```{code-block} usd
:force:

# Valid: NewtonMaterialAPI applied alongside PhysicsMaterialAPI on a Material.
def Material "RubberMaterial" (
    prepend apiSchemas = ["PhysicsMaterialAPI", "NewtonMaterialAPI"]
)
{
    float physics:staticFriction = 1.0
    float physics:dynamicFriction = 0.8
    float newton:torsionalFriction = 0.005
    float newton:rollingFriction = 0.0001
    float newton:contactStiffness = -inf
    float newton:contactDamping = -inf
    float newton:contactFrictionGain = -inf
    float newton:contactAdhesion = -inf
}

# Invalid: NewtonMaterialAPI applied on a non-material prim.
def Xform "NotAMaterial" (
    prepend apiSchemas = ["NewtonMaterialAPI"]
)
{
}

# Invalid: NewtonMaterialAPI without PhysicsMaterialAPI.
def Material "MissingBaseMaterial" (
    prepend apiSchemas = ["NewtonMaterialAPI"]
)
{
}
```

## How to comply

- Apply `NewtonMaterialAPI` only on `UsdShade.Material` prims that also carry
  `PhysicsMaterialAPI`.
- Author the `newton:*` tuning values as needed for the material; their values are trusted
  (leave them unauthored, or at the `-inf` sentinel for the contact attributes, to use the
  Newton engine default).

## For More Information

- [Newton USD parsing documentation](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
- [Newton USD Schema Definitions (NewtonMaterialAPI)](https://github.com/newton-physics/newton-usd-schemas)
- [UsdPhysicsMaterialAPI Documentation](https://openusd.org/dev/api/class_usd_physics_material_a_p_i.html)

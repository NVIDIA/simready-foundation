# rigid-body-detailed-mass

| Code     | RB.008 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`high-quality` |

## Summary

Rigid bodies _or_ their descendent collision shapes may have detailed mass properties including density, center of mass, and inertia tensor.

## Description

While basic mass specification is required, rigid bodies can have additional mass properties for more accurate physics simulation:

- `physics:density`: Specifies the mass density of the object in kg/m³. When specified, mass is computed as density × volume.
- `physics:centerOfMass`: Defines the center of mass in the prim's local space (in meters).
- `physics:diagonalInertia`: Specifies the diagonalized inertia tensor along principal axes (in kg⋅m²).
- `physics:principalAxes`: Defines the orientation of the inertia tensor's principal axes in the prim's local space.

All units must be consistent with the stage's unit system as defined by [meters-per-unit](/capabilities/core/units/requirements/meters-per-unit) and [kilograms-per-unit](/capabilities/core/units/requirements/kilograms-per-unit).

Note: Density can be specified either through the MassAPI or through the [MaterialAPI](https://openusd.org/dev/api/class_usd_physics_material_a_p_i.html). When both specify density, the MassAPI's density takes precedence. Additionally, if MassAPI specifies a mass value, it takes precedence over any density values.

## Why is it required?

- Detailed mass properties enable more accurate physics simulation:
  - Density allows mass to be computed from volume
  - Center of mass affects rotational behavior
  - Inertia tensor determines how the object rotates around different axes
  - Principal axes alignment ensures correct rotational behavior

## Examples

```usd
#usda 1.0
(
    metersPerUnit = 0.01  # 1cm = 0.01m
    kilogramsPerUnit = 0.001  # 1g = 0.001kg
)

def Xform "RigidBody" (
      prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
) {
      # Basic mass specification
      physics:mass = 1000.0  # 1000g = 1kg
}


# Detailed mass properties
def Xform "RigidBody" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
) {
   # Basic mass (1000g = 1kg)
   physics:mass = 1000.0
   
   # Density (1g/cm³ = 1000kg/m³)
   physics:density = 1000.0
   
   # Center of mass offset (10cm = 0.1m)
   physics:centerOfMass = (10.0, 0.0, 0.0)
   
   # Inertia tensor (diagonalized) in g⋅cm²
   physics:diagonalInertia = (100.0, 200.0, 100.0)
   
   # Principal axes orientation
   physics:principalAxes = (0.0, 0.0, 0.0, 1.0)  # quaternion
}

# Example showing MassAPI density taking precedence over MaterialAPI
def Material "steel" (
   prepend apiSchemas = ["PhysicsMaterialAPI"]
) {
   physics:density = 800.0  # 0.8g/cm³
}

def Xform "RigidBody" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
) {
   # This density (1g/cm³) takes precedence over the material's density
   physics:density = 1000.0
   
   # This mass takes precedence over both density values
   physics:mass = 2000.0
}
```

## How to comply

- Add the desired mass properties using the UsdPhysicsMassAPI attributes
- Note the precedence rules for mass and density:
  - MassAPI mass value takes precedence over any density values
  - MassAPI density takes precedence over MaterialAPI density
  - If no mass or density is specified, simulators will compute mass automatically
- Center of mass should be specified in the prim's local space
- Inertia tensor should be diagonalized and aligned with principal axes
- All units must be consistent with the stage's unit system:
  - Linear measurements (centerOfMass) should use the stage's metersPerUnit
  - Mass measurements (mass, density) should use the stage's kilogramsPerUnit
  - Inertia measurements should use the appropriate combination of mass and length units

## Related Requirements

- [rigid-body-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass)
- [meters-per-unit](/capabilities/core/units/requirements/meters-per-unit)
- [kilograms-per-unit](/capabilities/core/units/requirements/kilograms-per-unit)
<!-- - [physics-material](/capabilities/physics_bodies/physics_materials/requirements/physics-material) -->

## For More Information

- [UsdPhysicsMassAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)
- [UsdPhysicsMaterialAPI Documentation](https://openusd.org/dev/api/class_usd_physics_material_a_p_i.html)

# Rigid Body Mass

| Code     | RB.007 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`high-quality` |

## Summary

Rigid bodies _or_ their descendant collision shapes must have a mass specification.

## Description

Rigid bodies _or_ their descendent collision shapes must have a mass specification using the `physics:mass` attribute. The mass unit is specified in [kilograms per unit](/capabilities/core/units/requirements/kilograms-per-unit).


## Why is it required?

- If mass is not specified, simulators will compute mass automatically. This is often inaccurate as objects are modelled without internal details. Specifying mass allows for more accurate simulation.

## Examples

```usd
# Invalid: No mass specified

def Xform "RobotHead" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {

   def Mesh "Head" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
   }

   # Valid: Mass specified
   def Cube "Jaw" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
      physics:mass = 1.0
   }
}

# Valid: Mass specified on Rigid Body
def Xform "RobotBody" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
) {
   physics:mass = 1.0

   def Mesh "Body" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
   }
  
   def Cube "Leg" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {      
   }
}

```

## How to comply

- Add the `physics:mass` attribute to the rigid body.

## Related Requirements

-[kilograms-per-unit](/capabilities/core/units/requirements/kilograms-per-unit)

## For More Information

- [UsdPhysicsMassAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)
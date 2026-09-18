# Nested Rigid Body Mass

| Code     | RB.011 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`high-quality` |

## Summary

Every rigid body must have a valid (positive) `physics:mass` on itself or on at least one of its child colliders. Nested rigid body subtrees are excluded from the traversal. Negative mass is always a failure.

## Description

This is a hierarchy-aware companion to [rigid-body-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass) that correctly handles hierarchies containing nested rigid bodies.

The validator recursively traverses the subtree rooted at each rigid body prim, but **prunes any child that has its own `PhysicsRigidBodyAPI`** (along with that child's entire subtree), since those children are validated independently as separate rigid bodies.

Within the remaining (unpruned) scope the check evaluates `MassAPI` mass values:

- If **any** mass source in scope carries a valid positive mass — the rigid body itself, or one of its child colliders (a prim with `PhysicsCollisionAPI`) — the body **passes**.
- If **no** mass source in scope has a valid positive mass (i.e. the body has no valid `MassAPI` **and** all of its child colliders lack a valid `MassAPI`), the check **fails**.
- Any prim in scope with a **negative** `physics:mass` is reported as a failure regardless.

The mass unit is specified in [kilograms per unit](/capabilities/core/units/requirements/kilograms-per-unit).

## Why is it required?

- A rigid body with no mass source anywhere in its own scope cannot be simulated meaningfully; PhysX auto-computation also needs a mass or density to work from.
- In multi-body hierarchies (e.g. robots), each rigid body link owns a distinct subtree. A flat traversal may incorrectly include collision shapes belonging to a nested child rigid body. This check correctly scopes mass validation to each rigid body's own subtree.
- Negative mass is physically invalid and destabilizes the solver.

## Examples

```usd
# Invalid: No valid mass source under RobotHead itself.
# The nested rigid body "Arm" (and its MassAPI) is excluded from RobotHead's
# scope, so RobotHead is left with no mass on itself or its own colliders.

def Xform "RobotHead" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]

   def Xform "Arm" () {
      prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
      physics:mass = 2.0

      def Mesh "ArmMesh" (
         prepend apiSchemas = ["PhysicsCollisionAPI"]
      ) {
      }
   }
}

# Valid: Mass specified on the rigid body itself.
def Xform "RobotBody" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
   physics:mass = 5.0

   def Xform "Leg" () {
      prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
      physics:mass = 1.5

      def Cube "LegCollider" (
         prepend apiSchemas = ["PhysicsCollisionAPI"]
      ) {
      }
   }
}

# Valid: No mass on the body, but a child collider carries a valid MassAPI mass.
def Xform "Wheel" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]

   def Cylinder "WheelCollider" (
      prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMassAPI"]
   ) {
      physics:mass = 0.75
   }
}
```

## How to comply

- Add a positive `physics:mass` (via `PhysicsMassAPI`) to the rigid body, or to at least one collider directly owned by it (not inside a nested rigid body).
- Never author a negative `physics:mass`.

## Related Requirements

- [rigid-body-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass)
- [rigid-body-detailed-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-detailed-mass)
- [kilograms-per-unit](/capabilities/core/units/requirements/kilograms-per-unit)

## For More Information

- [UsdPhysicsMassAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)

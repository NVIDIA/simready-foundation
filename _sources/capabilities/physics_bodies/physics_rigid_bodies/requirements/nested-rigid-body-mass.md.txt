# Nested Rigid Body Mass

| Code     | RB.011 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`high-quality` |

## Summary

Rigid bodies must have an explicit mass specification, or their descendant collision shapes must have non-zero volume to allow mass auto-computation. Nested rigid body subtrees are excluded from the traversal.

## Description

This is an enhanced version of [rigid-body-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass) that correctly handles hierarchies containing nested rigid bodies.

The validator recursively traverses the subtree rooted at each rigid body prim, but **prunes any child that has its own `PhysicsRigidBodyAPI`** (along with that child's entire subtree), since those children are validated independently as separate rigid bodies.

For the remaining (unpruned) subtree, the `physics:mass` attribute is summed across all visited prims:

- If the total mass is greater than zero, the rigid body has an explicit mass specification and **passes**.
- If the total mass is zero (or no mass is authored), the physics engine must auto-compute mass from density and collider volume. For this to produce a valid result, at least one descendant collision shape within the pruned subtree must be a valid collider with **non-zero volume** (all three extent dimensions > 0). If no such collider is found, the check **fails**.

The mass unit is specified in [kilograms per unit](/capabilities/core/units/requirements/kilograms-per-unit).

## Why is it required?

- If mass is not specified, simulators will compute mass automatically. This is often inaccurate as objects are modelled without internal details. Specifying mass allows for more accurate simulation.
- In multi-body hierarchies (e.g. robots), each rigid body link owns a distinct subtree. The original `RB.007` check uses a flat traversal that may incorrectly include collision shapes belonging to a nested child rigid body. This check correctly scopes mass validation to each rigid body's own subtree.
- When mass is left to auto-computation, there must be at least one valid collider with non-zero volume; otherwise the computed mass will be zero, leading to simulation instability.

## Examples

```usd
# Invalid: No mass and no valid colliders under RobotHead
# (the nested rigid body "Arm" and its subtree are excluded)

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

# Valid: Mass specified on Rigid Body
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

# Valid: No explicit mass, but a valid collider with non-zero volume
# exists directly under this rigid body (not inside a nested one)
def Xform "Wheel" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]

   def Cylinder "WheelCollider" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
      # Extent with non-zero volume enables mass auto-computation
      extent = [(-0.5, -0.5, -0.25), (0.5, 0.5, 0.25)]
   }
}
```

## How to comply

- Add the `physics:mass` attribute with a positive value to the rigid body or its descendant collision shapes.
- If relying on mass auto-computation, ensure that at least one collision shape directly owned by the rigid body (not inside a nested rigid body) has non-zero volume (authored extent with all three dimensions > 0).

## Related Requirements

- [rigid-body-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass)
- [rigid-body-detailed-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-detailed-mass)
- [kilograms-per-unit](/capabilities/core/units/requirements/kilograms-per-unit)

## For More Information

- [UsdPhysicsMassAPI Documentation](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)

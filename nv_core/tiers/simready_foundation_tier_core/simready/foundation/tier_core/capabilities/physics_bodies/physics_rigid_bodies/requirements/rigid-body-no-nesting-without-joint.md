# rigid-body-no-nesting-without-joint

| Code     | RB.012 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Rigid bodies should not be nested unless they are connected by a joint.

## Description

This is an enhanced version of [rigid-body-no-nesting](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-nesting) designed for multi-body assets such as robots and articulated mechanisms.

When two `UsdPhysicsRigidBodyAPI` prims are nested in the scene hierarchy (one is an ancestor of the other), there must be a `UsdPhysicsJoint` somewhere in the stage whose `physics:body0` and `physics:body1` relationships connect the two rigid bodies. Without a joint, the physics engine has no constraint information linking the bodies, leading to unpredictable simulation behaviour.

The validator performs a **stage-wide** scan of all joints because a joint can be defined anywhere in the scene — not necessarily between the nested prims in the hierarchy. For each joint, the `body0` and `body1` relationship targets are resolved; if a target points to a collision mesh, the mesh's parent is treated as the rigid body (matching standard USD joint authoring conventions). Every nested rigid-body pair is then checked against the collected set of joint-connected pairs.

## Why is it required?

- In multi-body hierarchies (e.g. robots), rigid bodies are intentionally nested to represent link-joint chains. Each parent-child rigid body pair must be connected by a joint so the physics solver can compute the correct constrained motion.
- A nested rigid body without a connecting joint will be simulated independently of its parent, causing the bodies to drift apart or interpenetrate during simulation.
- This check complements RB.006 (which requires `!resetXformStack!` for nested rigid bodies) by ensuring the structural correctness of articulated assets where nesting is expected.

## Examples

```usd
# Invalid: Nested rigid bodies with no joint connecting them
def Xform "Robot" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]

   def Xform "Link1" () {
      prepend apiSchemas = ["PhysicsRigidBodyAPI"]
   }
}

# Valid: Nested rigid bodies connected by a joint
def Xform "Robot" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]

   def Xform "Link1" () {
      prepend apiSchemas = ["PhysicsRigidBodyAPI"]
   }

   def PhysicsRevoluteJoint "Joint1" () {
      rel physics:body0 = </Robot>
      rel physics:body1 = </Robot/Link1>
   }
}

# Valid: Joint defined elsewhere in the scene (not between the nested prims)
def Xform "Robot" () {
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]

   def Xform "Arm" () {
      prepend apiSchemas = ["PhysicsRigidBodyAPI"]
   }
}

def PhysicsRevoluteJoint "ExternalJoint" () {
   rel physics:body0 = </Robot>
   rel physics:body1 = </Robot/Arm>
}
```

## How to comply

- For every pair of nested rigid bodies, ensure a `UsdPhysicsJoint` (or subtype such as `PhysicsRevoluteJoint`, `PhysicsPrismaticJoint`, `PhysicsFixedJoint`, etc.) exists in the stage with its `physics:body0` and `physics:body1` relationships targeting the two rigid body prims.
- The joint does not need to be a child of either rigid body — it can be authored anywhere in the scene graph.

## Related Requirements

- [rigid-body-no-nesting](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-nesting) (RB.006)
- [nested-rigid-body-mass](/capabilities/physics_bodies/physics_rigid_bodies/requirements/nested-rigid-body-mass) (RB.011)
- [joint-capability](/capabilities/physics_bodies/physics_joints/requirements/joint-capability) (JT.001)

## For More Information

- [UsdPhysics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)
- [UsdPhysicsJoint Documentation](https://openusd.org/dev/api/class_usd_physics_joint.html)

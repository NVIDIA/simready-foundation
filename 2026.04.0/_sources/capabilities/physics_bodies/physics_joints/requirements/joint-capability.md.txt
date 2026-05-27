# joint-multibody-capability

| Code     | JT.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Rigid bodies which are not free floating should be connected using joints.

## Description

Rigid bodies that need to move in relation to each other or are fixed in the world, should use a **UsdPhysicsJoint prim** or one of its subtypes to properly constrain their motion.

## Why is it required?

* To describe constraints between rigid bodies for simulation in a physics engine.

## Examples

```usd
# Invalid: No joint between rigid bodies
def RigidBody "Box" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def RigidBody "Sphere" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

# Valid: Joint between rigid bodies
def PhysicsFixedJoint "FixedJoint"
{
   rel physics:body0 = </Box>
   rel physics:body1 = </Sphere>
}

# Valid: Joint between rigid body and World
def PhysicsFixedJoint "FixedJoint"
{
   rel physics:body0 = </Box>
}
```

## How to comply

* Use a **UsdPhysicsJoint prim** or one of its subtypes to constrain rigid bodies together.
* Use a **UsdPhysicsJoint prim** or one of its subtypes to constrain a rigid body to the World.

## Related requirements

- [joint-body-target-exists](/capabilities/physics_bodies/physics_joints/requirements/joint-body-target-exists)
- [joint-no-multiple-body-targets](/capabilities/physics_bodies/physics_joints/requirements/joint-no-multiple-body-targets)

## For More Information

* [OpenUSD PhysicsJoint Schema](https://openusd.org/dev/api/class_usd_physics_joint.html#details)
* [OpenUSd Jointed Bodies Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_jointed_bodies)

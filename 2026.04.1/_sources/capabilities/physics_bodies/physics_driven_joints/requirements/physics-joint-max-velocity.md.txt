# physics-joint-max-velocity

| Code     | DJ.005 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

PhysX driven joints must have appropriate maximum velocity limits configured.

## Description

Maximum velocity limits prevent unrealistic joint motion and ensure simulation stability. These limits should be set based on the physical characteristics of the mechanism being simulated and the requirements of the application.

For joints with PhysxJointAPI, a positive maximum velocity is required:

- Revolute joints: physxJoint:maxJointVelocity > 0
- Prismatic joints: physxJoint:maxJointVelocity > 0

## Why is it required?

* To prevent unrealistic joint velocities that could destabilize simulation
* To ensure joints behave within physically reasonable bounds
* To maintain simulation performance and accuracy

## Examples

```usd
# Valid: Joint with velocity limits
def PhysicsRevoluteJoint "RevoluteJoint" (
    prepend apiSchemas = ["PhysicsDriveAPI:angular"]
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Y"
    float physxJoint:maxJointVelocity = 146.46
}

# Valid: Prismatic joint with linear velocity limit
def PhysicsPrismaticJoint "PrismaticJoint" (
    prepend apiSchemas = ["PhysicsDriveAPI:linear"]
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "X"
    float physxJoint:maxJointVelocity = 10
}

# Invalid: Joint with negative, 0, or undefined maxJointVelocity
def PhysicsRevoluteJoint "RevoluteJoint" (
    prepend apiSchemas = ["PhysicsDriveAPI:angular"]
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Y"
    float physxJoint:maxJointVelocity = -1
}
```

## How to comply

* Set appropriate physxJoint:maxJointVelocity for revolute joints
* Set appropriate physxJoint:maxJointVelocity for prismatic joints
* Configure limits based on physical constraints and application requirements

## Related requirements

- [physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md)
- [drive-joint-value-reasonable](drive-joint-value-reasonable.md)

## For More Information

* [PhysX Joint Limits Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joint_limits)
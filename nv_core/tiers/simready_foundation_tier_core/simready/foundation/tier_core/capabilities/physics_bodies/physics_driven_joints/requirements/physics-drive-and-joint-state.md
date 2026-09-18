# physics-drive-and-joint-state

| Code     | DJ.001 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

Validate that each driven joint has correct drive configuration and joint state, including required limits and consistency checks against the current joint state values.

## Description

For each joint prim, drives and joint state APIs are collected and validated together. Mimic joints with zero stiffness and damping are skipped. For each active drive, the rule enforces:

- drive maxForce must be authored, finite, and strictly greater than 0
- the drive targetPosition/targetVelocity should be consistent with the joint state position/velocity within tolerance

Consistency checks compare drive targets with PhysicsJointStateAPI-derived values and warn when the absolute differences exceed 1e-2.

## Why is it required?

* Ensures the drives can be driven and the joint states are recorded

## Examples

```usd
# Valid: Angular drive and state schemas applied to revolute joint
def PhysicsRevoluteJoint "RevoluteJoint" (
    prepend apiSchemas =  ["PhysxJointAPI", "PhysicsDriveAPI:angular", "PhysicsJointStateAPI:angular"] # apply angular drive and state schemas to angular joints
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Y"
    float drive:angular:physics:maxForce = 10 # Newton
}

# Invalid: Angular drive and state schemas applied to a physics prismatic joint
def PhysicsPrismaticJoint "PrismaticJoint" (
    prepend apiSchemas =  ["PhysxJointAPI", "PhysicsDriveAPI:angular", "PhysicsJointStateAPI:angular"] # apply angular drive and state schemas to prismatic joints
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Y"
    float drive:linear:physics:maxForce = 0 # Invalid, max force is 0N
}
```

## How to comply

* Apply the appropriate prim type to the appropriate schemas type on joints (Revolute, Prismatic)
* Max force applied to the joint must be a natural number and cannot be infinite

## Related requirements

- [physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md)
- [drive-joint-value-reasonable](drive-joint-value-reasonable.md)

## For More Information

* [OpenUSD PhysicsDriveAPI Schema](https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html)
* [USD Physics Joint Drive Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joint_drive)
* [PhysxSchemaJointStateAPI Class Reference](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_joint_state_a_p_i.html)
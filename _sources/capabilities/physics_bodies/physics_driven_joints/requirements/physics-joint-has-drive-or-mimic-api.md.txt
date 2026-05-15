# physics-joint-has-drive-or-mimic-api

| Code     | DJ.004 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

PhysX driven joints must implement drive API or mimic functionality for controlled motion.

## Description

PhysX joints require either drive APIs for direct control or mimic APIs for coordinated motion. This enables advanced joint control mechanisms including position control, velocity control, and coordinated multi-joint motion patterns.

Additional checks:

- If a joint has both drive and mimic APIs, the drive stiffness and damping must be exactly 0.0
- Non-fixed joints are expected to have either drive or mimic API applied unless explicitly excluded from articulation

## Why is it required?

* To enable PhysX-specific drive control features
* To support advanced joint control mechanisms
* To provide coordinated motion capabilities through mimic joints

## Examples

```usd
# valid joint with drive 
def PhysicsRevoluteJoint "ref_joint" (
    prepend apiSchemas = ["PhysxJointAPI", "PhysicsDriveAPI:angular", "PhysicsJointStateAPI:angular"] # Driving joints must contain joint drive api
)
{
    uniform token physics:axis = "Z"
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
}

# valid joint with mimic joint
def PhysicsRevoluteJoint "mimic_joint" (
    prepend apiSchemas = ["PhysxJointAPI", "PhysxMimicJointAPI:rotZ", "PhysicsJointStateAPI:angular"] #Mimic joint must contain mimic api
)
{
    float drive:angular:physics:damping = 0 # damping must be 0
    float drive:angular:physics:stiffness = 0 # stiffness must be 0
    uniform token physics:axis = "Z"
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_2> 
    rel physxMimicJoint:rotZ:referenceJoint = </ref_joint>

}
```

## How to comply

* Apply PhysicsDriveAPI for direct joint control
* Apply PhysxMimicJointAPI for coordinated joint motion
* If both drive and mimic are present, set drive stiffness and damping to 0.0

## Related requirements

- [physics-drive-and-joint-state](physics-drive-and-joint-state.md)
- [physics-joint-max-velocity](physics-joint-max-velocity.md)

## For More Information

* [PhysX Drive API Documentation](https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html)
* [PhysX Mimic API Documentation](https://openusd.org/dev/api/class_usd_physics_mimic_a_p_i.html)
* [PhysxSchemaJointStateAPI Class Reference](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_joint_state_a_p_i.html)
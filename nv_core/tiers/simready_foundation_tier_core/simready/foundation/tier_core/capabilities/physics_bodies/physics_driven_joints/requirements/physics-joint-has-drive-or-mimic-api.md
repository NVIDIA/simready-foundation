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

- Non-fixed joints are expected to have either drive or mimic API applied unless explicitly excluded from articulation
- When both drive and mimic APIs are present, the required drive gains depend on the joint type:
  - **Revolute (and other non-prismatic) followers:** drive stiffness and damping must be exactly 0.0 so the mimic constraint owns the DOF
  - **Prismatic followers:** drive stiffness must be non-zero. PhysX does not currently enforce `PhysxMimicJointAPI` on linear DOFs, so the follower drive is what couples the mechanism (for example a parallel-jaw gripper). Damping alone cannot hold a position target. Keep the mimic API authored for runtimes that do honour linear coupling (Newton, MuJoCo)

## Why is it required?

* To enable PhysX-specific drive control features
* To support advanced joint control mechanisms
* To provide coordinated motion capabilities through mimic joints
* To keep prismatic couplings physically correct under PhysX while still authoring mimic for multi-runtime assets

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

# valid revolute mimic joint: zero drive gains; mimic owns the DOF
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

# valid prismatic mimic follower: keep non-zero drive gains (PhysX workaround)
def PhysicsPrismaticJoint "finger_right" (
    prepend apiSchemas = ["PhysxJointAPI", "PhysxMimicJointAPI:Z", "PhysicsDriveAPI:linear", "PhysicsJointStateAPI:linear"]
)
{
    uniform token physics:axis = "Z"
    float drive:linear:physics:stiffness = 5000
    float drive:linear:physics:damping = 41.28
    rel physics:body0 = </base>
    rel physics:body1 = </right>
    rel physxMimicJoint:Z:referenceJoint = </finger_left>
}
```

## How to comply

* Apply PhysicsDriveAPI for direct joint control
* Apply PhysxMimicJointAPI for coordinated joint motion
* If both drive and mimic are present on a revolute (non-prismatic) follower, set drive stiffness and damping to 0.0
* If both drive and mimic are present on a prismatic follower, keep non-zero drive stiffness

## Related requirements

- [physics-drive-and-joint-state](physics-drive-and-joint-state.md)
- [physics-joint-max-velocity](physics-joint-max-velocity.md)
- [drive-joint-value-reasonable](drive-joint-value-reasonable.md)
- [mimic-api-check](mimic-api-check.md)

## For More Information

* [PhysX Drive API Documentation](https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html)
* [PhysX Mimic API Documentation](https://openusd.org/dev/api/class_usd_physics_mimic_a_p_i.html)
* [PhysxSchemaJointStateAPI Class Reference](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_joint_state_a_p_i.html)

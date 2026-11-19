# joint-has-correct-transform-and-state

| Code     | DJ.003 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

Driven joints must maintain correct transform relationships and state consistency.
## Description

Joint transforms and states must be properly configured to ensure correct kinematic behavior. This includes proper parent-child relationships, transform hierarchies, and state synchronization between joint configuration and actual simulation state.

## Why is it required?

* To ensure proper kinematic chain behavior
* To maintain consistency between joint configuration and simulation
* To provide predictable joint motion and positioning

## Examples

```usd
# Valid: Joint with correct transforms
def PhysicsRevoluteJoint "finger_joint" (
    prepend apiSchemas = ["PhysxJointAPI", "PhysicsDriveAPI:angular", "PhysicsJointStateAPI:angular"]
)
{

    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    point3f physics:localPos0 = (0, -0.0306, 0.05466) # valid translate
    point3f physics:localPos1 = (0, -0.0306, 0.05466) # valid translate
    quatf physics:localRot0 = (0.5, 0.5, -0.5, -0.5) # valid quaternion
    quatf physics:localRot1 = (0.5, 0.5, -0.5, -0.5) # valid quaternion
}
```

## How to comply

* Ensure joint transforms are properly configured in the hierarchy
* Maintain consistent transform relationships between connected bodies
* Verify joint state properties match the configured transforms

Checks performed (for Revolute and Prismatic joints only):

* Resolve body0/body1; skip if invalid
* Compute expected world transforms from each body
* Build a joint_state_transform from PhysxSchema.JointStateAPI
* Compare translations (tolerance 1e-4) and rotations (tolerance 1e-3)
  * If both bodies disagree → Error: position/rotation not well-defined
  * If bodies agree but state disagrees → Error: state not matching robot pose

## Related requirements

- [physics-drive-and-joint-state](physics-drive-and-joint-state.md)
- [joint-has-joint-state-api](joint-has-joint-state-api.md)

## For More Information

* [OpenUSD Transform Documentation](https://openusd.org/dev/api/class_usd_geom_xformable.html)
* [USD Physics Joint Relationships](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
* [PhysxSchemaJointStateAPI Class Reference](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_joint_state_a_p_i.html)
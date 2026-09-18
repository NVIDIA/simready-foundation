# joint-has-joint-state-api

| Code     | DJ.002 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

Driven joints must implement proper joint state API for simulation state management.

## Description

Joint state APIs provide the necessary interface for tracking and controlling joint position, velocity, and other simulation properties. This ensures that driven joints can be properly monitored and controlled during simulation.

> **Note:** Despite the `Physics` prefix in its USD schema token (`PhysicsJointStateAPI`), this schema is defined in the PhysX extension (`PhysxSchema` module), not in core `UsdPhysics`. In Python it is accessed as `PhysxSchema.JointStateAPI`.

## Why is it required?

* To enable real-time monitoring of joint states during simulation
* To provide interface for joint control and feedback systems
* To ensure compatibility with robotics and control frameworks

## Examples

```usd
# Valid: Joint with state API
def PhysicsRevoluteJoint "RevoluteJoint" ( 
    prepend apiSchemas = ["PhysicsJointStateAPI:angular"] # Valid Joint State API
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Y"
}
```

## How to comply

* Apply PhysicsJointStateAPI (axis-specific) to driven joints
* Ensure joint state properties are properly exposed
* Configure state tracking for simulation requirements

## Related requirements

- [physics-drive-and-joint-state](physics-drive-and-joint-state.md)
- [joint-capability](/capabilities/physics_bodies/physics_joints/requirements/joint-capability)

## For More Information

* [OpenUSD JointStateAPI Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joint_state)
* [PhysxSchemaJointStateAPI Class Reference](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_joint_state_a_p_i.html)
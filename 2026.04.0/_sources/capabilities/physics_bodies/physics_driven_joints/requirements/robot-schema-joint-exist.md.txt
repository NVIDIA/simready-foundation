# robot-schema-joint-exist

| Code     | DJ.008 |
|----------|--------|
| Validator| CheckStage |
| Compatibility | {compatibility}`Isaac` |
| Tags     | {tag}`essential` |

## Summary

Robot schema joints must exist and be properly defined for Isaac Sim integration.

## Description

Isaac Sim requires joints to be properly defined within the robot schema structure. This includes proper joint naming, hierarchy, and schema conformance to ensure compatibility with Isaac Sim's robotics framework and URDF import/export capabilities.

## Why is it required?

* To ensure compatibility with Isaac Sim robotics framework
* To enable proper URDF conversion and robot model loading
* To support robotic simulation and control features

## Examples

```usd
# Valid: Proper robot schema joint definition
over "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    string isaac:namespace (
        displayName = "Namespace"
        doc = "Namespace of the prim in Isaac Sim"
    )
    rel isaac:physics:robotJoints = [
        </joints_0>,
        </joints_1>,
        </joints_2>,
    ]
}
```

## How to comply

* Ensure robot assets have at least one prim with the JointAPI applied, which is typically required for articulated robots.

## Related requirements

- [robot-schema-links-exist](robot-schema-links-exist.md)
- [check-robot-relationships](check-robot-relationships.md)

## For More Information

* [Isaac Sim Robot Schema Documentation](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_core_hello_world.html)
* [URDF to USD Conversion Guide](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_advanced_import_urdf.html)

# robot-schema-links-exist

| Code     | DJ.009 |
|----------|--------|
| Validator| CheckStage |
| Compatibility | {compatibility}`Isaac` |
| Tags     | {tag}`essential` |

## Summary

Robot schema links must exist and be properly connected to joints for kinematic chain definition.

## Description

Isaac Sim requires link definitions that are connected through joints to form a valid kinematic chain. Links must maintain correct parent-child relationships through joint connections.

## Why is it required?

* To establish proper kinematic chain structure for robotics simulation
* To ensure links are correctly associated with joints
* To support robot model validation and physics simulation

## Examples

```usd
# Valid: Proper robot schema with links and joints
over "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    string isaac:namespace (
        displayName = "Namespace"
        doc = "Namespace of the prim in Isaac Sim"
    )
    rel isaac:physics:robotLinks = [
        </link_0>,
        </link_1>,
        </link_2>,

    ]
}
```

## How to comply

* Ensure robot assets have at least one prim with the LinkAPI applied, which is typically required for articulated robots.

## Related requirements

- [robot-schema-joint-exist](robot-schema-joint-exist.md)
- [check-robot-relationships](check-robot-relationships.md)

## For More Information

* [Isaac Sim Link Schema Documentation](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_core_hello_world.html)
* [Robot Model Structure Guide](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_advanced_import_urdf.html)
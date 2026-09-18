# robot-type

| Code     | RC.008 |
|----------|--------|
| Validator| CheckStage |
| Compatibility | {compatibility}`Isaac Sim` |
| Tags     | {tag}`essential` |

## Summary

Robot assets must declare a valid robot type on the default prim. The `isaac:robotType` attribute must be present, must be one of the schema-defined allowed tokens, and must not be `"Default"`.
Allowed values are : "End Effector", "Manipulator", "Humanoid", "Wheeled", "Holonomic", "Quadruped", "Mobile Manipulators", "Aerial"

## Description

The default prim of a robot asset must have the `isaac:robotType` attribute. The value must come from the allowed tokens defined by the Robot schema (e.g. `Manipulator`, `End Effector`, or other schema-defined types). The placeholder value `"Default"` is not allowed and will fail validation.

## Why is it required?

* To ensure robots are correctly classified for simulation and tooling
* To enable type-specific behavior (e.g. root joint pinning for manipulators)
* To keep validation aligned with the schema’s allowed tokens

## Examples

```usd
# Valid: Robot type set to a schema-allowed value (e.g. Manipulator)
over "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    token isaac:robotType = "Manipulator"
    rel isaac:physics:robotJoints = [ </joints/root>, </joints/joint_1> ]
    rel isaac:physics:robotLinks = [ </links/base>, </links/link_1> ]
}

# Invalid: Missing isaac:robotType
# over "Robot" (
#     prepend apiSchemas = ["IsaacRobotAPI"]
# )
# {
#     rel isaac:physics:robotJoints = [ </joints/root> ]
#     rel isaac:physics:robotLinks = [ </links/base> ]
# }

# Invalid: Placeholder value "Default" is not allowed
# token isaac:robotType = "Default"

# Invalid: Value not in schema allowedTokens
# token isaac:robotType = "CustomType"
```

## How to comply

* Set the default prim to the root robot prim that has `IsaacRobotAPI`.
* Add `isaac:robotType` on that default prim.
* Use a value from the schema’s allowed tokens (e.g. `Manipulator`, `End Effector`).
* Do not use `"Default"` as the robot type.

## Related requirements

- [robot-schema](robot-schema.md)
- [root-joint-pinned](root-joint-pinned.md)

## For More Information

* [Isaac Sim Robot API](https://docs.omniverse.nvidia.com/isaacsim/latest/)
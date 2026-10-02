# check-robot-relationships

| Code     | DJ.010 |
|----------|--------|
| Validator| CheckStage |
| Compatibility | {compatibility}`Isaac` |
| Tags     | {tag}`essential` |

## Summary

Robot joint and link relationships must be validated for proper kinematic tree structure.

## Description

The relationships between joints and links must form a valid kinematic tree without cycles or orphaned components. All joints must properly connect two links (or one link fixed to the world position), and the resulting structure must be a valid robot model for Isaac Sim.

## Why is it required?

* To ensure the robot forms a valid kinematic tree structure
* To prevent simulation issues from malformed robot hierarchies  
* To validate robot model integrity for Isaac Sim compatibility

## Examples

```text
# Valid: Proper kinematic tree structure
def "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    # Base link (root of kinematic tree)
    def Xform "base_link" (
        prepend apiSchemas = ["IsaacLinkAPI"]
    )
    {
        string isaac:linkName = "base_link"
    }
    
    # Connected through joint
    def Xform "link1" (
        prepend apiSchemas = ["IsaacLinkAPI"]
    )
    {
        string isaac:linkName = "link1"
    }

    # Another link connected to link1
    def Xform "link2" (
        prepend apiSchemas = ["IsaacLinkAPI"]
    )
    {
        string isaac:linkName = "link2"
    }
    
    # Valid joint connecting base to link1
    def PhysicsRevoluteJoint "joint1"
    {
        rel physics:body0 = </Robot/base_link>  # Parent
        rel physics:body1 = </Robot/link1>      # Child
    }
    
    
    # Valid joint connecting link1 to link2
    def PhysicsRevoluteJoint "joint2"
    {
        rel physics:body0 = </Robot/link1>      # Parent
        rel physics:body1 = </Robot/link2>      # Child
    }
}
```

```text
# Invalid: Proper kinematic tree structure
def "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    # Base link (root of kinematic tree)
    def Xform "base_link" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
    }
    
    # Connected through joint
    def Xform "link1" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
    }
    
    # Valid joint connecting base to link1
    def PhysicsRevoluteJoint "joint1"
    {
        rel physics:body0 = </Robot/base_link>  # Parent
        rel physics:body1 = </Robot/link1>      # Child
    }
    
    
    # Invalid joint connecting link1 to base_link (circular dependency)
    def PhysicsRevoluteJoint "joint2"
    {
        rel physics:body0 = </Robot/link1>      # Parent
        rel physics:body1 = </Robot/base_link>      # Child
    }
}
```

```text
# Invalid: Circular dependency
# joint1: base -> link1
# joint2: link1 -> base  (creates cycle)
```
```

## How to comply

* Ensure all joints connect exactly two links (or one link to world)
* Validate the kinematic structure forms a tree (no cycles)
* Check that all links are reachable from the root link
* Verify no orphaned links or joints exist

## Related requirements

- [robot-schema-joint-exist](robot-schema-joint-exist.md) 
- [robot-schema-links-exist](robot-schema-links-exist.md)

## For More Information

* [Isaac Sim Robot Validation](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_advanced_import_urdf.html)
* [Kinematic Tree Structure](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/tutorial_core_hello_world.html)

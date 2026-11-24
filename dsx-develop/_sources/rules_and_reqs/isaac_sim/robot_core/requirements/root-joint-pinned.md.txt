# root-joint-pinned

| Code     | RC.009 |
|----------|--------|
| Validator| CheckStage |
| Compatibility | {compatibility}`Isaac Sim` |
| Tags     | {tag}`essential` |

## Summary

The root joint (the first target of `isaac:physics:robotJoints`) must be pinned for robot types that require a fixed base (e.g. Manipulator, End Effector) and must not be pinned for other robot types.

## Description

The root joint is the first joint in the `isaac:physics:robotJoints` relationship. A joint is considered pinned when one of its two bodies is not a rigid body (e.g. body is the world or a non-physics prim). For types such as **Manipulator** and **End Effector**, the root joint must be pinned (fixed base). For all other valid robot types, the root joint must not be pinned.

## Why is it required?

* To match simulation expectations for fixed-base vs mobile robots
* To prevent incorrect physics behavior (e.g. floating manipulators or incorrectly fixed mobile bases)
* To keep asset configuration consistent with the declared robot type

## Examples

### Passing — Manipulator pinned via empty `body0` (world)

A `UsdPhysics.Joint` with no `physics:body0` target is implicitly connected to the
world frame. This is the most common way to pin a fixed-base robot.

```usd
over "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    token isaac:robotType = "Manipulator"
    rel isaac:physics:robotJoints = [ </Robot/joints/root>, </Robot/joints/joint_1> ]
    rel isaac:physics:robotLinks = [ </Robot/links/base>, </Robot/links/link_1> ]
}

def Scope "joints"
{
    def PhysicsJoint "root"
    {
        # body0 has no target — interpreted as the world (pinned)
        rel physics:body1 = </Robot/links/base>
    }
}

def Scope "links"
{
    def Xform "base" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
    }
}
```

### Passing — Manipulator pinned via empty `body1` (world)

The world side can be on either relationship. Here `body1` is left empty instead.

```usd
def Scope "joints"
{
    def PhysicsJoint "root"
    {
        rel physics:body0 = </Robot/links/base>
        # body1 has no target — interpreted as the world (pinned)
    }
}
```

### Passing — Manipulator pinned via non-rigid body prim

Instead of leaving a body relationship empty, you can point it at a prim that does
**not** have `PhysicsRigidBodyAPI`. The validator treats this the same as the world.

```usd
def Xform "world_anchor"
{
    # No PhysicsRigidBodyAPI — acts as a fixed anchor
}

def Scope "joints"
{
    def PhysicsJoint "root"
    {
        rel physics:body0 = </Robot/world_anchor>
        rel physics:body1 = </Robot/links/base>
    }
}
```

### Passing — End Effector pinned (same rules as Manipulator)

End Effectors follow the same pinning requirement. Any of the pinning
methods above apply.

```usd
over "Gripper" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    token isaac:robotType = "End Effector"
    rel isaac:physics:robotJoints = [ </Gripper/joints/root>, </Gripper/joints/finger_1> ]
    rel isaac:physics:robotLinks = [ </Gripper/links/base>, </Gripper/links/finger_1> ]
}

def Scope "joints"
{
    def PhysicsJoint "root"
    {
        # Pinned: body0 is empty (world)
        rel physics:body1 = </Gripper/links/base>
    }
}
```

### Passing — Mobile robot with root joint **not** pinned

For robot types other than Manipulator and End Effector, the root joint must have
**both** bodies targeting prims with `PhysicsRigidBodyAPI`.

```usd
over "MobileBot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    token isaac:robotType = "Mobile"
    rel isaac:physics:robotJoints = [ </MobileBot/joints/root>, </MobileBot/joints/wheel_1> ]
    rel isaac:physics:robotLinks = [ </MobileBot/links/chassis>, </MobileBot/links/wheel_1> ]
}

def Scope "joints"
{
    def PhysicsJoint "root"
    {
        rel physics:body0 = </MobileBot/links/chassis>
        rel physics:body1 = </MobileBot/links/body>
    }
}

def Scope "links"
{
    def Xform "chassis" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
    }

    def Xform "body" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
    }
}
```

### Failing — Manipulator with both bodies rigid (not pinned)

```usd
# FAILS: Both body0 and body1 are rigid bodies, so the root joint is not pinned.
# Manipulators require a pinned root joint.
def Scope "joints"
{
    def PhysicsJoint "root"
    {
        rel physics:body0 = </Robot/links/chassis>   # has PhysicsRigidBodyAPI
        rel physics:body1 = </Robot/links/base>      # has PhysicsRigidBodyAPI
    }
}
```

### Failing — Mobile robot with a pinned root joint

```usd
# FAILS: body0 is empty (world), making the root joint pinned.
# Non-manipulator types must not have a pinned root joint.
over "MobileBot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    token isaac:robotType = "Mobile"
}

def Scope "joints"
{
    def PhysicsJoint "root"
    {
        # body0 is empty — pinned to world, which is wrong for Mobile
        rel physics:body1 = </MobileBot/links/chassis>
    }
}
```

## How to comply

* Ensure the default prim has `isaac:robotType` and `isaac:physics:robotJoints` (see [robot-type](robot-type.md) and [robot-schema](robot-schema.md)).
* For **Manipulator** and **End Effector**: make the root joint pinned by having one of its `physics:body0` or `physics:body1` targets be the world or a prim without `RigidBodyAPI`.
* For all other robot types: ensure both bodies of the root joint are rigid bodies (root joint not pinned).

## Related requirements

- [robot-type](robot-type.md)
- [robot-schema](robot-schema.md)

## For More Information

* [Isaac Sim Robot API](https://docs.omniverse.nvidia.com/isaacsim/latest/)
* [USD Physics Joints](https://openusd.org/dev/api/usd_physics_page_front.html)

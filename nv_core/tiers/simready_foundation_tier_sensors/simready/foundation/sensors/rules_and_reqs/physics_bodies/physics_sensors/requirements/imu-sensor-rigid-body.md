# imu-sensor-rigid-body

| Code     | PS.001 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

An `IsaacImuSensor` prim must be a descendant of a prim that has `PhysicsRigidBodyAPI` applied.

## Examples

```usd
# Invalid: IsaacImuSensor is not under a RigidBodyAPI prim
def Xform "Robot"
{
    def IsaacImuSensor "IMU" {}
}

# Valid: IsaacImuSensor is parented under a prim with PhysicsRigidBodyAPI
def Xform "Robot"
{
    def Xform "Base" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
        def IsaacImuSensor "IMU" {}
    }
}
```

## How to comply

- Place the `IsaacImuSensor` prim as a child (or descendant) of a prim that has `PhysicsRigidBodyAPI` applied.
- The rigid body prim must be an ancestor in the prim hierarchy, not a sibling.

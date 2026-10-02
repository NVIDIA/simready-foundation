# joint-sensor-articulation-root

| Code     | PS.002 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

An `IsaacJointStateSensor` prim must also have `PhysicsArticulationRootAPI` applied.

## Examples

```usd
# Invalid: IsaacJointStateSensor without PhysicsArticulationRootAPI
def IsaacJointStateSensor "Robot"
{
}

# Valid: IsaacJointStateSensor with PhysicsArticulationRootAPI on the same prim
def IsaacJointStateSensor "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

## How to comply

- Apply `PhysicsArticulationRootAPI` to the same prim that uses the `IsaacJointStateSensor` prim type.
- Typically this is the root prim of the articulated robot.

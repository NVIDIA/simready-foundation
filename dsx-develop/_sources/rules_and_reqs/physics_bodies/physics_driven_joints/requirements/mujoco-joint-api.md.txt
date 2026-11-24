# MuJoCo Joint API

| Code     | MUJOCO.DJ.001 |
|----------|---------------|
| Validator| MuJoCoJointAPIChecker |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo driven joints must use standard `UsdPhysics.Joint` prims with `MjcJointAPI` applied to every non-fixed articulation joint.

## Description

MuJoCo USD overlays keep the articulation topology in standard USD physics joint prims while adding MuJoCo-specific joint import data through `MjcJointAPI` and `mjc:*` joint attributes. For every non-fixed joint that participates in an articulation:

- the prim must be a valid `UsdPhysics.Joint`
- `MjcJointAPI` must be applied
- authored MuJoCo joint tuning attributes must be authored on the joint prim
- `mjc:armature`, when authored, must be finite and non-negative

This requirement deliberately does not use `PhysicsDriveAPI` as the MuJoCo actuation contract. A MuJoCo-driven asset uses `MjcActuator` prims to define runtime actuation.

## Why is it required?

* Ensures MuJoCo can identify which USD joints participate in the MuJoCo runtime model.
* Keeps MuJoCo joint tuning data attached to the standard USD joint topology.
* Catches invalid numeric joint values before MuJoCo import.

## Examples

```usd
# Valid: MuJoCo metadata is applied to a standard USD revolute joint.
def PhysicsRevoluteJoint "shoulder" (
    prepend apiSchemas = ["MjcJointAPI"]
)
{
    rel physics:body0 = </robot/base>
    rel physics:body1 = </robot/upper_arm>
    uniform token physics:axis = "Z"
    float mjc:armature = 0.1
}

# Invalid: MuJoCo joint data is authored on a non-joint prim.
def Xform "bad_shoulder" (
    prepend apiSchemas = ["MjcJointAPI"]
)
{
    float mjc:armature = 0.1
}
```

## How to comply

* Preserve the standard `UsdPhysics.Joint` topology and body relationships.
* Apply `MjcJointAPI` to every non-fixed articulation joint that is part of the MuJoCo driven-joint contract.
* Author MuJoCo joint tuning values only on joint prims.
* Keep authored `mjc:armature` values finite and non-negative.
* Use `MjcActuator` prims for MuJoCo actuation instead of relying on `PhysicsDriveAPI` as the MuJoCo runtime contract.

## Related requirements

- [mujoco-actuator-targets](mujoco-actuator-targets.md)
- [no-articulation-loops](no-articulation-loops.md)

## For More Information

* MuJoCo USD converter output and schema authoring conventions.

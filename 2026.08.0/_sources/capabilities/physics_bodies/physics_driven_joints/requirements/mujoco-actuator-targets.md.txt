# MuJoCo Actuator Targets

| Code     | MUJOCO.DJ.002 |
|----------|---------------|
| Validator| MuJoCoActuatorTargetsChecker |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo actuator prims must target valid MuJoCo-driven USD physics joints and author valid actuator parameter values.

## Description

MuJoCo-driven articulation control is represented by `MjcActuator` prims. Every `MjcActuator` prim must:

- target exactly one joint with `mjc:target`
- target a valid non-fixed `UsdPhysics.Joint`
- target a joint that applies `MjcJointAPI`
- author paired range attributes when ranges are present
- keep `mjc:ctrlRange:min`, `mjc:ctrlRange:max`, `mjc:forceRange:min`, and `mjc:forceRange:max` finite, with min less than or equal to max
- keep authored `mjc:gainPrm` and `mjc:biasPrm` values as non-empty numeric arrays
- author a non-empty `mjc:biasType` value when `mjc:biasType` is present

Every non-fixed MuJoCo joint in the feature contract must be targeted by at least one `MjcActuator`.

## Why is it required?

* Ensures MuJoCo actuators resolve to concrete USD joints.
* Prevents orphaned actuators and unactuated MuJoCo-driven joints.
* Catches invalid control, force, gain, and bias values before MuJoCo import.

## Examples

```usd
# Valid: actuator targets a MuJoCo-marked USD joint.
def MjcActuator "shoulder_actuator"
{
    rel mjc:target = </robot/Physics/shoulder>
    float mjc:ctrlRange:min = -3.14
    float mjc:ctrlRange:max = 3.14
    float mjc:forceRange:min = -150.0
    float mjc:forceRange:max = 150.0
    float[] mjc:gainPrm = [100.0, 0.0, 0.0]
    float[] mjc:biasPrm = [0.0, -100.0, -10.0]
    token mjc:biasType = "affine"
}

# Invalid: actuator target is missing.
def MjcActuator "bad_actuator"
{
    float mjc:ctrlRange:min = -1.0
    float mjc:ctrlRange:max = 1.0
}
```

## How to comply

* Author one or more `MjcActuator` prims for MuJoCo-driven articulation joints.
* Set `rel mjc:target` to exactly one valid non-fixed `UsdPhysics.Joint` that applies `MjcJointAPI`.
* Keep authored control and force ranges finite and ordered.
* Keep authored gain and bias parameters numeric.
* Do not leave MuJoCo-driven joints without an actuator target.

## Related requirements

- [mujoco-joint-api](mujoco-joint-api.md)
- [no-articulation-loops](no-articulation-loops.md)

## For More Information

* MuJoCo USD converter output and actuator authoring conventions.
